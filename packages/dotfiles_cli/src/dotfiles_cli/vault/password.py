"""Vault password resolution.

Delegates to the OS-specific backend (`backend.get_backend()`) for storage.
On a miss with a TTY, prompts the user and best-effort persists to the
backend so the next run is non-interactive.

The legacy disk-backed helpers (`get_vault_password_file`,
`write_vault_password_file`, `ensure_vault_password_permissions`) are kept
for the install flow + Phase 4 one-shot migration, then removed.
"""

from __future__ import annotations

import getpass
import sys
from pathlib import Path

import click

from ..constants import (
    VAULT_PASSWORD_FILE_MODE,
    get_dotfiles_dir,
    get_vault_password_file as get_global_vault_password_file,
)
from .backend import get_backend
from .backends import onepassword


def clear_vault_password_cache() -> None:
    """No-op. Retained for backwards-compat with callers (e.g. secret rekey).

    The backend handles its own caching (gpg-agent, keychain session), and
    the CLI lives for seconds; there's nothing to clear.
    """


def ensure_vault_password_permissions(password_file: Path) -> None:
    """Ensure vault password file has correct permissions (600).

    Legacy helper for the install flow reading existing disk files during
    the transition. Removed once install.py is refactored (Phase 3).
    """
    if not password_file.exists():
        return

    current_mode = password_file.stat().st_mode & 0o777
    if current_mode == VAULT_PASSWORD_FILE_MODE:
        return

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

    Legacy helper retained for the Phase 4 migration command (reads disk,
    writes to backend, offers to delete). Removed after migration lands.
    """
    password_file.write_text(password)
    password_file.chmod(VAULT_PASSWORD_FILE_MODE)


def get_vault_password_file(location: str) -> Path:
    """Return the profile-specific or global .vault_password file path.

    Legacy helper — callers should move to `get_backend().read(location)`.
    """
    profile_password_file = (
        Path(get_dotfiles_dir()) / "profiles" / location / ".vault_password"
    )
    if profile_password_file.exists():
        return profile_password_file
    return get_global_vault_password_file()


def get_vault_id(location: str) -> str:
    """Vault ID for a profile — the profile name."""
    return location


def get_vault_password(location: str = "common") -> str:
    """Return the vault password for `location`, reading from the backend.

    Resolution:
        1. `backend.read(location)` — keychain (macOS) or gpg file (Linux).
        2. 1Password fallback if DOTFILES_VAULT_OP_ITEM is configured.
        3. TTY prompt with best-effort backend persist.
        4. Click exception with guidance if no TTY.
    """
    backend = get_backend()
    try:
        password = backend.read(location)
    except Exception:
        # Backend surfaced a read error (gpg missing, wrong master password,
        # keychain unreachable). Fall through to 1P / prompt; don't block.
        password = None

    if password is not None:
        return password

    # 1Password fallback — single-item, one field per profile.
    fallback = onepassword.read_field(location)
    if fallback is not None:
        # Write-through so the next run is fast and offline-capable.
        try:
            backend.ensure_ready()
            backend.write(location, fallback)
        except Exception as exc:
            click.echo(
                f"Note: fetched vault password for {location!r} from 1Password "
                f"but could not persist it locally ({exc}).",
                err=True,
            )
        return fallback

    if not sys.stdin.isatty() and not Path("/dev/tty").exists():
        raise click.ClickException(
            f"No vault password stored for {location!r} and no TTY to prompt.\n"
            f"Run `dotfiles secret init` or "
            f"`dotfiles secret keychain push {location}` to register one."
        )

    try:
        password = getpass.getpass(f"Vault password for {location}: ")
    except (KeyboardInterrupt, EOFError):
        raise click.ClickException("Vault password prompt cancelled.")
    if not password:
        raise click.ClickException("Vault password cannot be empty.")

    # Best-effort persist — if the backend refuses (gpg missing, permission),
    # keep running with the in-memory password and advise the user.
    try:
        backend.ensure_ready()
        backend.write(location, password)
    except Exception as exc:
        click.echo(
            f"Note: could not save vault password for {location!r} to backend "
            f"({exc}).\nRun `dotfiles secret init` when ready to persist it.",
            err=True,
        )

    return password


def validate_vault_password(password: str) -> bool:
    """Try decrypting the first profile's secrets file with `password`.

    Returns True if decryption succeeds, False otherwise.
    """
    from .operations import (
        run_ansible_vault,
        get_profiles_with_secrets,
        get_secrets_file,
    )

    for profile in get_profiles_with_secrets():
        profile_secrets = get_secrets_file(profile)
        try:
            rc, _, _ = run_ansible_vault(
                ["view", str(profile_secrets)], password=password
            )
            return rc == 0
        except Exception:
            return False

    return True
