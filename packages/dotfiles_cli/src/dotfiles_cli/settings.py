"""Settings management using pydantic-settings."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .constants import get_env_dist_file, get_env_file


class Settings(BaseSettings):
    """Dotfiles CLI settings.

    Settings are loaded from (in order of precedence):
    1. Environment variables
    2. .env file
    3. .env.dist file (defaults)
    """

    model_config = SettingsConfigDict(
        # Later files take precedence, so: defaults first, then user overrides
        env_file=(str(get_env_dist_file()), str(get_env_file())),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Profile Selection
    # Comma-separated list of profiles to activate
    dotfiles_profiles: str = Field(
        default="all",
        description="Comma-separated list of profiles (e.g., 'common,work' or 'all,-personal')",
    )

    # Symlink Settings
    # Whether to disable creating ~/.local/bin/dotfiles symlink
    dotfiles_no_symlink: bool = Field(
        default=False,
        description="Disable creating ~/.local/bin/dotfiles symlink",
    )

    @field_validator("dotfiles_no_symlink", mode="before")
    @classmethod
    def parse_bool(cls, v: str | bool | None) -> bool:
        """Parse boolean from string values like '0', 'false', '1', 'true'."""
        if v is None:
            return False
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ("1", "true", "yes")
        return bool(v)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    Returns a cached Settings instance. The cache ensures settings are only
    loaded once per process, improving performance.

    To reload settings (e.g., after modifying .env), use:
        get_settings.cache_clear()
        settings = get_settings()
    """
    return Settings()


def save_setting(key: str, value: str | None) -> None:
    """Save or remove a setting in .env file.

    Args:
        key: Setting name (will be uppercased for env var)
        value: Value to set, or None to remove
    """
    import dotenv

    env_path = str(get_env_file())
    if value is None:
        dotenv.unset_key(env_path, key.upper())
    else:
        dotenv.set_key(env_path, key.upper(), value)

    # Clear settings cache so next get_settings() reloads
    get_settings.cache_clear()


def get_setting_for_display(key: str) -> str | None:
    """Get raw setting value for display in UI.

    Unlike Settings model which parses values, this returns the raw string
    value for display purposes.

    Args:
        key: Setting name (case-insensitive)

    Returns:
        Raw string value or None if not set
    """
    import dotenv

    key_upper = key.upper()

    # Check .env first
    env_file = get_env_file()
    if env_file.exists():
        values = dotenv.dotenv_values(env_file)
        if key_upper in values:
            return values[key_upper]

    # Fall back to .env.dist
    env_dist_file = get_env_dist_file()
    if env_dist_file.exists():
        values = dotenv.dotenv_values(env_dist_file)
        if key_upper in values:
            return values[key_upper]

    return None
