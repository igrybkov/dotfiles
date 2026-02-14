"""Ansible vault operations."""

from __future__ import annotations

import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from ..constants import DOTFILES_DIR
from ..profiles import get_profile_names, get_profile_path
from .password import get_vault_password, get_vault_id


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
    """Get all available secret locations (profiles).

    Returns:
        List of all profile names
    """
    return get_profile_names()


def get_profiles_with_secrets() -> list[str]:
    """Get list of profiles that have encrypted secrets.yml file.

    Supports multi-level profiles where secrets are stored at the actual
    profile path (e.g., 'profiles/myrepo/work/secrets.yml' for 'myrepo-work').

    Returns:
        List of profile names that have encrypted secrets
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
    """Run ansible-vault command with the given or location-specific password.

    Uses vault IDs to support multiple passwords:
    - Built-in locations (common/work/personal) use vault ID 'default'
    - Profile locations use their profile name as vault ID

    Args:
        args: Arguments to pass to ansible-vault
        password: Explicit password (if None, uses location-specific password)
        location: Secret location for password lookup (default: common)

    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    if password is None:
        password = get_vault_password(location)

    vault_id = get_vault_id(location)

    # Create a temporary password file for ansible-vault
    with TemporaryDirectory() as tmpdir:
        pass_file = Path(tmpdir) / "vault_pass"
        pass_file.write_text(password)
        pass_file.chmod(0o600)

        # Use --vault-id for proper multi-password support
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
