"""Constants and configuration for the dotfiles CLI."""

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
SUDO_TAGS: set[str] = {"mas", "chsh"}

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
