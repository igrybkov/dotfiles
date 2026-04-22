"""Ansible lookup plugin for reading secrets from vault-encrypted files.

Usage in templates:
    {{ lookup('vault_secret', 'mcp_secrets.habitify.api_key') }}

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
from ansible.parsing.vault import VaultLib, VaultSecret  # noqa: E402
from ansible.plugins.lookup import LookupBase  # noqa: E402
from dotfiles_profile_discovery import get_profile_by_name  # noqa: E402

VAULT_HEADER_PREFIX = b"$ANSIBLE_VAULT"


class LookupModule(LookupBase):
    def run(
        self, terms: list[str], variables: dict | None = None, **kwargs
    ) -> list[Any]:
        playbook_dir = (
            variables.get("playbook_dir", os.getcwd()) if variables else os.getcwd()
        )
        inventory_hostname = (
            variables.get("inventory_hostname", "common") if variables else "common"
        )
        vault_profile = variables.get("_vault_profile") if variables else None
        current_profile = (
            vault_profile
            if vault_profile
            else inventory_hostname.replace("-profile", "")
        )

        secrets_dir = Path(playbook_dir) / "secrets"
        vault_files = [
            secrets_dir / f"{inventory_hostname}.yml",
            secrets_dir / "common.yml",
        ]

        profiles_dir = Path(playbook_dir) / "profiles"
        if profiles_dir.exists():
            for profile_name in [current_profile, "common"]:
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

                profile_secrets_dir = profile_dir / "secrets"
                if profile_secrets_dir.exists():
                    for secret_file in sorted(profile_secrets_dir.glob("*.yml")):
                        if secret_file not in vault_files:
                            vault_files.append(secret_file)

        client_script = _locate_client_script(playbook_dir)

        all_secrets = []
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
                "No vault secrets file found. Checked locations:\n"
                + "\n".join(f"  - {loc}" for loc in checked_locations)
            )

        results = []
        for term in terms:
            value = None
            for secrets in all_secrets:
                value = self._resolve_path(secrets, term)
                if value is not None:
                    break
            if value is None:
                raise AnsibleError(f"Secret not found: {term}")
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
    """Decrypt `vault_file` by reading its vault-id and invoking the client script."""
    raw = vault_file.read_bytes()
    if not raw.startswith(VAULT_HEADER_PREFIX):
        # Not encrypted — load as plain YAML.
        return yaml.safe_load(raw) or {}

    header, _, body = raw.partition(b"\n")
    # Header format: $ANSIBLE_VAULT;VERSION;CIPHER[;VAULT_ID]
    parts = header.decode("utf-8", errors="replace").split(";")
    vault_id = parts[3].strip() if len(parts) >= 4 else "default"

    password = _fetch_password(client_script, vault_id)
    vault = VaultLib(secrets=[(vault_id, VaultSecret(password.encode()))])
    decrypted = vault.decrypt(raw)
    return yaml.safe_load(decrypted) or {}


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
