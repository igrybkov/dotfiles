"""Ansible vault operations."""

from __future__ import annotations

import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from ..constants import DOTFILES_DIR, get_vault_client_script
from ..profiles import get_profile_names, get_profile_path
from .backend import get_backend
from .backends import onepassword
from .password import get_vault_id


def _looks_like_decryption_failure(stderr: str) -> bool:
    """Heuristic: did ansible-vault fail because the password is wrong?

    Matches the stable markers ansible-vault emits on bad passwords. Any of:
      - "Decryption failed"
      - "no vault secrets were found that could decrypt"
    """
    if not stderr:
        return False
    lowered = stderr.lower()
    return (
        "decryption failed" in lowered
        or "no vault secrets were found that could decrypt" in lowered
    )


def get_secrets_file(location: str) -> Path:
    """Get the path to the secrets file for a profile.

    Supports multi-level profiles where the profile name contains dashes
    (e.g., 'myrepo-work' maps to 'profiles/myrepo/work/secrets.yml').

    Args:
        location: Profile name (e.g., 'common', 'work', or 'myrepo-work')

    Returns:
        Path to the secrets file (profiles/{path}/secrets.yml)

    Raises:
        ValueError: If the profile is not found
    """
    profile_path = get_profile_path(location)
    if profile_path is None:
        raise ValueError(f"Profile not found: {location}")
    return profile_path / "secrets.yml"


def get_all_secret_locations() -> list[str]:
    """Get all available secret locations (profiles)."""
    return get_profile_names()


def get_profiles_with_secrets() -> list[str]:
    """Get list of profiles that have an encrypted secrets.yml file.

    Supports multi-level profiles where secrets are stored at the actual
    profile path (e.g., 'profiles/myrepo/work/secrets.yml' for 'myrepo-work').
    """
    profiles_with_secrets = []
    for profile in get_profile_names():
        profile_path = get_profile_path(profile)
        if profile_path is None:
            continue
        secrets_file = profile_path / "secrets.yml"
        if secrets_file.exists():
            try:
                if secrets_file.read_text().startswith("$ANSIBLE_VAULT"):
                    profiles_with_secrets.append(profile)
            except Exception:
                pass
    return profiles_with_secrets


def run_ansible_vault(
    args: list[str], password: str | None = None, location: str = "common"
) -> tuple[int, str, str]:
    """Run ansible-vault for `location`, optionally with an explicit password.

    Default path: invokes ansible-vault with the dotfiles-vault-client
    script as the vault-id source. The client script reads from the OS
    backend at call time (no temp password files).

    Override path (password != None): used by `validate_vault_password` and
    `secret rekey` where we need to pass an explicit — not backend-stored —
    password. Writes a short-lived tempfile in mode 600 and passes that.

    Returns (returncode, stdout, stderr).
    """
    vault_id = get_vault_id(location)

    if password is not None:
        return _run_with_explicit_password(args, password, vault_id)

    client_path = str(get_vault_client_script())
    cmd = [
        "ansible-vault",
        *args,
        "--vault-id",
        f"{vault_id}@{client_path}",
    ]
    result = subprocess.run(
        cmd,
        cwd=DOTFILES_DIR,
        capture_output=True,
        text=True,
    )

    # If decryption failed, the locally-cached password may be stale.
    # Refresh from 1Password (if configured) and retry once.
    if (
        result.returncode != 0
        and _looks_like_decryption_failure(result.stderr)
        and onepassword.is_configured()
    ):
        fresh = onepassword.read_field(location)
        if fresh:
            try:
                backend = get_backend()
                backend.ensure_ready()
                backend.write(location, fresh)
            except Exception:
                # Write-through failed; retry anyway — an explicit-password
                # run still works and will succeed if fresh is correct.
                pass
            return _run_with_explicit_password(args, fresh, vault_id)

    return result.returncode, result.stdout, result.stderr


def _run_with_explicit_password(
    args: list[str], password: str, vault_id: str
) -> tuple[int, str, str]:
    """Invoke ansible-vault with a short-lived password file (mode 600)."""
    with TemporaryDirectory() as tmpdir:
        pass_file = Path(tmpdir) / "vault_pass"
        pass_file.write_text(password)
        pass_file.chmod(0o600)
        cmd = [
            "ansible-vault",
            *args,
            "--vault-id",
            f"{vault_id}@{pass_file}",
        ]
        result = subprocess.run(
            cmd,
            cwd=DOTFILES_DIR,
            capture_output=True,
            text=True,
        )
    return result.returncode, result.stdout, result.stderr
