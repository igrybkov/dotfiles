"""Constants and configuration for the dotfiles CLI."""

import os
import sys
from pathlib import Path

# Root of the dotfiles repository
# Path: packages/dotfiles_cli/src/dotfiles_cli/constants.py -> need 5 levels up
DOTFILES_DIR = Path(__file__).parent.parent.parent.parent.parent.absolute().as_posix()


def get_dotfiles_dir() -> str:
    """Get path to dotfiles directory.

    Uses dynamic module lookup so tests can patch DOTFILES_DIR at runtime.
    """
    return sys.modules[__name__].DOTFILES_DIR


# Tags that require sudo password
SUDO_TAGS: set[str] = {"mas", "chsh", "brew", "cask"}

# Tags that require vault password (use vault_secret lookup)
VAULT_TAGS: set[str] = {"mcp-servers"}

# Sentinel value for --logfile when no filename is provided
LOGFILE_AUTO = "__AUTO__"

# Environment variable for profile selection
ENV_PROFILES_KEY = "DOTFILES_PROFILES"

# Environment variable to disable symlink creation
ENV_NO_SYMLINK_KEY = "DOTFILES_NO_SYMLINK"

# Vault password file permissions
VAULT_PASSWORD_FILE_MODE = 0o600

# Login-keychain service used for per-label vault passwords (macOS).
VAULT_KEYCHAIN_SERVICE = "com.grybkov.dotfiles.vault"

# GPG backend (Linux + anywhere non-macOS).
GPG_VAULT_DIR_NAME = "dotfiles"
GPG_VAULT_FILENAME = "vault-secrets.yml.gpg"
GPG_MASTER_PASSWORD_ENV = "DOTFILES_VAULT_MASTER_PASSWORD"

# Plain-JSON label index for macOS (label names aren't secrets).
MACOS_LABELS_FILENAME = "vault-labels.json"

# Ansible vault client script.
VAULT_CLIENT_SCRIPT_NAME = "dotfiles-vault-client"


def get_macos_labels_file() -> Path:
    """Path to the JSON file tracking known vault-label names on macOS."""
    return (
        Path.home()
        / "Library"
        / "Application Support"
        / "dotfiles-cli"
        / MACOS_LABELS_FILENAME
    )


def get_gpg_vault_dir() -> Path:
    """XDG-ish config dir for the GPG-encrypted vault file."""
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / GPG_VAULT_DIR_NAME


def get_gpg_vault_file() -> Path:
    """Path to the GPG-symmetric-encrypted vault-secrets file."""
    return get_gpg_vault_dir() / GPG_VAULT_FILENAME


def get_vault_client_script() -> Path:
    """Absolute path to bin/dotfiles-vault-client.

    Used in Ansible's `vault_identity_list` entries so ansible-vault spawns
    the client script and reads the password from its stdout.
    """
    return Path(get_dotfiles_dir()) / "bin" / VAULT_CLIENT_SCRIPT_NAME


def get_env_file() -> Path:
    """Get path to .env file.

    Uses get_dotfiles_dir() so tests can patch DOTFILES_DIR at runtime.
    """
    return Path(get_dotfiles_dir()) / ".env"


def get_env_dist_file() -> Path:
    """Get path to .env.dist file.

    Uses get_dotfiles_dir() so tests can patch DOTFILES_DIR at runtime.
    """
    return Path(get_dotfiles_dir()) / ".env.dist"


def get_vault_password_file() -> Path:
    """Get path to .vault_password file.

    Uses get_dotfiles_dir() so tests can patch DOTFILES_DIR at runtime.
    """
    return Path(get_dotfiles_dir()) / ".vault_password"
