"""Ansible lookup plugin for reading secrets from vault-encrypted files.

Usage in templates:
    {{ lookup('vault_secret', 'mcp_secrets.habitify.api_key') }}

Cross-profile (per-term override):
    {{ lookup('vault_secret', 'mcp_secrets.other.key@other-profile') }}

Usage in variables:
    env:
      API_KEY: "{{ lookup('vault_secret', 'mcp_secrets.habitify.api_key') }}"

The plugin searches for secrets in:
    1. secrets/<inventory_hostname>.yml
    2. secrets/common.yml
    3. profiles/<profile>/secrets.yml (using shared discovery for multi-level profiles)
    4. profiles/<profile>/secrets/*.yml
    5. profiles/common/secrets.yml
    6. profiles/common/secrets/*.yml

Decryption is done by reading the vault-id label from each file header and
invoking `bin/dotfiles-vault-client --vault-id <label>` to fetch the
password. The client script reads from the OS backend (login keychain on
macOS, GPG file on Linux). This makes the lookup self-sufficient and
independent of Ansible's loader-level vault-secrets wiring.

Per-term `@profile` suffix
--------------------------
A term of the form ``key.path@profile-name`` resolves against
``profile-name``'s vault file set instead of the current profile. The suffix
is split at the LAST ``@``, so profile names may contain ``/`` (e.g.
``@personal/productivity``). Files in ``secrets/`` (host-level + common) are
still consulted alongside the override profile — only the
``profiles/<name>/`` portion of the search path changes.
"""

from __future__ import annotations

import os
import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

# Add the shared package to Python path for Ansible plugin usage
# (Ansible plugins can't use pip dependencies directly)
_packages_dir = Path(__file__).parent.parent.parent / "packages"
_discovery_pkg = _packages_dir / "dotfiles_profile_discovery" / "src"
if str(_discovery_pkg) not in sys.path:
    sys.path.insert(0, str(_discovery_pkg))

import yaml  # noqa: E402
from ansible.errors import AnsibleError  # noqa: E402
from ansible.parsing.vault import AnsibleVaultError, VaultLib, VaultSecret  # noqa: E402
from ansible.plugins.lookup import LookupBase  # noqa: E402
from dotfiles_profile_discovery import get_profile_by_name  # noqa: E402

# Best-effort import of the 1Password fallback + backend writer. These live
# in the installed dotfiles_cli package (the venv Ansible runs under) and
# are only consulted when primary decryption fails.
try:
    from dotfiles_cli.vault.backend import get_backend as _get_backend  # noqa: E402
    from dotfiles_cli.vault.backends import onepassword as _onepassword  # noqa: E402
except Exception:  # pragma: no cover — env without dotfiles_cli on path
    _get_backend = None
    _onepassword = None

VAULT_HEADER_PREFIX = b"$ANSIBLE_VAULT"


class LookupModule(LookupBase):
    def run(
        self, terms: list[str], variables: dict | None = None, **kwargs
    ) -> list[Any]:
        playbook_dir = Path(
            variables.get("playbook_dir", os.getcwd()) if variables else os.getcwd()
        )
        inventory_hostname = (
            variables.get("inventory_hostname", "common") if variables else "common"
        )
        vault_profile = variables.get("_vault_profile") if variables else None
        default_profile = (
            vault_profile
            if vault_profile
            else inventory_hostname.replace("-profile", "")
        )

        client_script = _locate_client_script(str(playbook_dir))

        # Cache decrypted secrets per effective profile to amortize across
        # terms that hit the same profile.
        secrets_cache: dict[str, list[dict]] = {}

        results: list[Any] = []
        for term in terms:
            key_path, profile_override = _parse_term(term)
            effective_profile = profile_override or default_profile

            if effective_profile not in secrets_cache:
                secrets_cache[effective_profile] = _load_profile_secrets(
                    playbook_dir,
                    inventory_hostname,
                    effective_profile,
                    client_script,
                )

            all_secrets = secrets_cache[effective_profile]
            value = None
            for secrets in all_secrets:
                value = self._resolve_path(secrets, key_path)
                if value is not None:
                    break
            if value is None:
                scope = f" in profile {effective_profile!r}" if profile_override else ""
                raise AnsibleError(f"Secret not found: {key_path}{scope}")
            results.append(value)

        return results

    def _resolve_path(self, data: dict, path: str) -> Any:
        """Resolve a dot-notation path in the data dict."""
        current = data
        for part in path.split("."):
            if not isinstance(current, dict):
                return None
            current = current.get(part)
            if current is None:
                return None
        return current


def _parse_term(term: str) -> tuple[str, str | None]:
    """Split ``key.path@profile`` into ``(key_path, profile)``.

    Returns ``(term, None)`` when no ``@`` is present. Splits on the last
    ``@`` so profile names containing ``/`` work naturally. Empty key or
    empty profile after the split is an error.
    """
    if "@" not in term:
        return term, None
    key_path, _, profile = term.rpartition("@")
    if not profile:
        raise AnsibleError(f"Empty profile suffix in vault_secret term: {term!r}")
    if not key_path:
        raise AnsibleError(f"Empty key path in vault_secret term: {term!r}")
    return key_path, profile


def _build_vault_files(
    playbook_dir: Path, inventory_hostname: str, profile: str
) -> list[Path]:
    """Return the ordered list of potential vault files for a given profile."""
    secrets_dir = playbook_dir / "secrets"
    vault_files: list[Path] = [
        secrets_dir / f"{inventory_hostname}.yml",
        secrets_dir / "common.yml",
    ]
    profiles_dir = playbook_dir / "profiles"
    if profiles_dir.exists():
        for profile_name in [profile, "common"]:
            profile_info = get_profile_by_name(profiles_dir, profile_name)
            if profile_info is None:
                continue
            profile_dir = profile_info.path

            profile_secrets_file = profile_dir / "secrets.yml"
            if (
                profile_secrets_file.exists()
                and profile_secrets_file not in vault_files
            ):
                vault_files.append(profile_secrets_file)

            profile_secrets_subdir = profile_dir / "secrets"
            if profile_secrets_subdir.exists():
                for secret_file in sorted(profile_secrets_subdir.glob("*.yml")):
                    if secret_file not in vault_files:
                        vault_files.append(secret_file)
    return vault_files


def _load_profile_secrets(
    playbook_dir: Path,
    inventory_hostname: str,
    profile: str,
    client_script: Path,
) -> list[dict]:
    """Decrypt every vault file in scope for ``profile`` and return the parsed dicts."""
    vault_files = _build_vault_files(playbook_dir, inventory_hostname, profile)
    all_secrets: list[dict] = []
    for vault_file in vault_files:
        if not vault_file.exists():
            continue
        try:
            data = _decrypt_file(vault_file, client_script)
        except Exception as exc:
            raise AnsibleError(f"Failed to decrypt {vault_file}: {exc}")
        if data:
            all_secrets.append(data)

    if not all_secrets:
        checked_locations = [str(f) for f in vault_files if f.parent.exists()]
        raise AnsibleError(
            f"No vault secrets file found for profile {profile!r}. "
            "Checked locations:\n"
            + "\n".join(f"  - {loc}" for loc in checked_locations)
        )
    return all_secrets


def _locate_client_script(playbook_dir: str | os.PathLike) -> Path:
    """Resolve the absolute path to bin/dotfiles-vault-client."""
    candidate = Path(playbook_dir) / "bin" / "dotfiles-vault-client"
    if candidate.exists():
        return candidate
    # Fallback: walk up from this file (ansible_plugins/lookup/vault_secret.py)
    # to the repo root and check there.
    repo_root = Path(__file__).resolve().parent.parent.parent
    candidate = repo_root / "bin" / "dotfiles-vault-client"
    if candidate.exists():
        return candidate
    raise AnsibleError(
        "Could not locate bin/dotfiles-vault-client. "
        "Run this playbook from the dotfiles repo root."
    )


def _decrypt_file(vault_file: Path, client_script: Path) -> dict:
    """Decrypt `vault_file` by reading its vault-id and invoking the client script.

    On an `AnsibleVaultError` (typically: locally-cached password is stale
    because the vault was rekeyed on another machine), consult 1Password
    if configured, write the fresh value back to the local backend, and
    retry once. Matches the retry semantics `run_ansible_vault` already
    implements for the CLI path.
    """
    raw = vault_file.read_bytes()
    if not raw.startswith(VAULT_HEADER_PREFIX):
        return yaml.safe_load(raw) or {}

    header, _, body = raw.partition(b"\n")
    parts = header.decode("utf-8", errors="replace").split(";")
    vault_id = parts[3].strip() if len(parts) >= 4 else "default"

    password = _fetch_password(client_script, vault_id)
    try:
        decrypted = _try_decrypt(raw, vault_id, password)
    except AnsibleVaultError:
        fresh = _refresh_from_onepassword(vault_id)
        if fresh is None or fresh == password:
            raise
        decrypted = _try_decrypt(raw, vault_id, fresh)
        # Clear cached wrong password so concurrent callers in this process
        # pick up the refreshed value too.
        _fetch_password.cache_clear()
    return yaml.safe_load(decrypted) or {}


def _try_decrypt(raw: bytes, vault_id: str, password: str) -> bytes:
    vault = VaultLib(secrets=[(vault_id, VaultSecret(password.encode()))])
    return vault.decrypt(raw)


def _refresh_from_onepassword(vault_id: str) -> str | None:
    """Fetch a fresh password from 1P and persist it. Returns None if unavailable."""
    if _onepassword is None or not _onepassword.is_configured():
        return None
    fresh = _onepassword.read_field(vault_id)
    if not fresh:
        return None
    if _get_backend is not None:
        try:
            backend = _get_backend()
            backend.ensure_ready()
            backend.write(vault_id, fresh)
        except Exception:
            # Write-through best-effort; decrypt-retry proceeds regardless.
            pass
    return fresh


@lru_cache(maxsize=32)
def _fetch_password(client_script: Path, vault_id: str) -> str:
    """Call the client script for a vault-id; cache for the lookup's lifetime."""
    result = subprocess.run(
        [str(client_script), "--vault-id", vault_id],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AnsibleError(
            f"Client script failed for vault-id {vault_id!r}: "
            f"{result.stderr.strip() or f'exit {result.returncode}'}"
        )
    pw = result.stdout.rstrip("\n")
    if not pw:
        raise AnsibleError(
            f"Client script returned empty password for vault-id {vault_id!r}."
        )
    return pw
