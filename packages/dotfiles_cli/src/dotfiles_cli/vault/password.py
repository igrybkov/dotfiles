"""Vault password management."""

from __future__ import annotations

import getpass
from pathlib import Path

import click

from ..constants import (
    VAULT_PASSWORD_FILE_MODE,
    get_dotfiles_dir,
    get_vault_password_file as get_global_vault_password_file,
)

# Cached vault passwords for the session (keyed by location)
_vault_password_cache: dict[str, str] = {}


def clear_vault_password_cache() -> None:
    """Clear the vault password cache."""
    global _vault_password_cache
    _vault_password_cache = {}


def ensure_vault_password_permissions(password_file: Path) -> None:
    """Ensure vault password file has correct permissions (600).

    Checks if the file has the correct permissions and attempts to fix them
    if they're wrong. Raises an error with instructions if unable to fix.

    Args:
        password_file: Path to the vault password file

    Raises:
        click.ClickException: If permissions are wrong and cannot be fixed
    """
    if not password_file.exists():
        return

    current_mode = password_file.stat().st_mode & 0o777
    if current_mode == VAULT_PASSWORD_FILE_MODE:
        return

    # Permissions are wrong, try to fix them
    try:
        password_file.chmod(VAULT_PASSWORD_FILE_MODE)
        click.echo(
            f"Fixed permissions on {password_file} "
            f"(was {oct(current_mode)}, now {oct(VAULT_PASSWORD_FILE_MODE)})"
        )
    except OSError as e:
        raise click.ClickException(
            f"Vault password file {password_file} has insecure permissions "
            f"({oct(current_mode)}) and could not be fixed automatically.\n"
            f"Error: {e}\n\n"
            f"Please fix manually by running:\n"
            f"  chmod 600 {password_file}"
        )


def write_vault_password_file(password_file: Path, password: str) -> None:
    """Write password to vault password file with correct permissions.

    Creates or overwrites the file with mode 600.

    Args:
        password_file: Path to the vault password file
        password: The password to write
    """
    password_file.write_text(password)
    password_file.chmod(VAULT_PASSWORD_FILE_MODE)


def get_vault_password_file(location: str) -> Path:
    """Get the vault password file path for a profile.

    First checks for a profile-specific password file, then falls back
    to the global password file.

    Args:
        location: Profile name

    Returns:
        Path to the .vault_password file
    """
    profile_password_file = (
        Path(get_dotfiles_dir()) / "profiles" / location / ".vault_password"
    )
    if profile_password_file.exists():
        return profile_password_file
    return get_global_vault_password_file()


def get_vault_id(location: str) -> str:
    """Get the vault ID for a profile.

    Args:
        location: Profile name

    Returns:
        Vault ID string (profile name)
    """
    return location


def get_vault_password(location: str = "common") -> str:
    """Get vault password for a profile from file or prompt (cached for session).

    Args:
        location: Profile name

    Returns:
        The vault password string
    """
    global _vault_password_cache

    password_file = get_vault_password_file(location)
    # Use actual password file path as cache key (handles fallback to global)
    cache_key = str(password_file)

    if cache_key in _vault_password_cache:
        return _vault_password_cache[cache_key]

    if password_file.exists():
        ensure_vault_password_permissions(password_file)
        _vault_password_cache[cache_key] = password_file.read_text().strip()
    else:
        prompt = f"Vault password for {location}: "
        _vault_password_cache[cache_key] = getpass.getpass(prompt)

    return _vault_password_cache[cache_key]


def validate_vault_password(password: str) -> bool:
    """Validate vault password by attempting to decrypt a vault file.

    Args:
        password: Password to validate

    Returns:
        True if password is valid, False otherwise
    """
    from .operations import run_ansible_vault, get_secrets_file
    from ..profiles import get_profile_names

    # Try to find any vault file to validate against
    for profile in get_profile_names():
        profile_secrets = get_secrets_file(profile)
        if profile_secrets.exists():
            try:
                # Try to decrypt the file (just view, don't modify)
                rc, _, _ = run_ansible_vault(
                    ["view", str(profile_secrets)], password=password
                )
                if rc == 0:
                    return True
                # If decryption failed, password is wrong
                return False
            except Exception:
                # If we can't validate, assume it's invalid
                return False

    # No vault files found - can't validate, but that's okay
    # Return True to allow proceeding (maybe no secrets are needed)
    return True
