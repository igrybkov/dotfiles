"""Configuration file discovery and loading."""

from __future__ import annotations

import os
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any

import yaml
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .merge import deep_merge
from .schema import (
    AgentConfig,
    AgentsConfig,
    AutoSelectConfig,
    GitHubConfig,
    HiveConfig,
    PostCreateCommand,
    ResumeConfig,
    WorktreesConfig,
    ZellijConfig,
)

# Config file names
CONFIG_FILE = ".hive.yml"
LOCAL_CONFIG_FILE = ".hive.local.yml"

# Global config directory and file names
GLOBAL_CONFIG_DIR = "hive"
GLOBAL_CONFIG_FILES = ["hive.yml", "hive.yaml"]

# Environment variable prefix
ENV_PREFIX = "HIVE_"
ENV_NESTED_DELIMITER = "_"

# Legacy environment variable names (for backward compatibility)
LEGACY_ENV_WORKTREES_HOME = "GIT_WORKTREES_HOME"


class HiveEnvSettings(BaseSettings):
    """Environment variable settings with HIVE_ prefix.

    Uses pydantic-settings to automatically load from environment variables.
    Nested fields use single underscore delimiter (e.g., HIVE_AGENTS_ORDER).
    """

    model_config = SettingsConfigDict(
        env_prefix="HIVE_",
        env_nested_delimiter="_",
        extra="ignore",
    )

    # Flat env vars that map to nested config
    # HIVE_AGENTS_ORDER -> agents.order (comma-separated list)
    agents_order: list[str] | None = None

    @field_validator("agents_order", mode="before")
    @classmethod
    def parse_csv_agents_order(cls, v: Any) -> list[str] | None:
        """Parse comma-separated string into list."""
        if v is None:
            return None
        if isinstance(v, str):
            return [a.strip() for a in v.split(",") if a.strip()]
        return v

    # HIVE_RESUME_ENABLED -> resume.enabled
    resume_enabled: bool | None = None

    # HIVE_WORKTREES_ENABLED -> worktrees.enabled
    worktrees_enabled: bool | None = None

    # HIVE_WORKTREES_PARENT_DIR -> worktrees.parent_dir
    worktrees_parent_dir: str | None = None

    # HIVE_WORKTREES_USE_HOME -> worktrees.use_home
    worktrees_use_home: bool | None = None

    # HIVE_WORKTREES_RESUME -> worktrees.resume
    worktrees_resume: bool | None = None

    # HIVE_WORKTREES_SKIP_PERMISSIONS -> worktrees.skip_permissions
    worktrees_skip_permissions: bool | None = None

    # HIVE_ZELLIJ_LAYOUT -> zellij.layout
    zellij_layout: str | None = None

    # HIVE_ZELLIJ_SESSION_NAME -> zellij.session_name
    zellij_session_name: str | None = None

    # HIVE_GITHUB_FETCH_ISSUES -> github.fetch_issues
    github_fetch_issues: bool | None = None

    # HIVE_GITHUB_ISSUE_LIMIT -> github.issue_limit
    github_issue_limit: int | None = None


def find_git_root() -> Path | None:
    """Find the git repository root.

    Returns:
        Path to git root, or None if not in a git repository.
    """
    import subprocess

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip()).resolve()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def get_xdg_config_home() -> Path:
    """Get the XDG config home directory.

    Returns:
        Path to XDG_CONFIG_HOME, or ~/.config if not set.
    """
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        return Path(xdg_config)
    return Path.home() / ".config"


def find_global_config() -> Path | None:
    """Find the global user configuration file.

    Searches for hive.yml or hive.yaml in $XDG_CONFIG_HOME/hive/.

    Returns:
        Path to global config file if found, None otherwise.
    """
    config_dir = get_xdg_config_home() / GLOBAL_CONFIG_DIR

    for filename in GLOBAL_CONFIG_FILES:
        path = config_dir / filename
        if path.exists():
            return path

    return None


def find_config_files(git_root: Path | None = None) -> list[Path]:
    """Find configuration files in order of precedence.

    Files are returned in load order (lowest to highest precedence):
    1. $XDG_CONFIG_HOME/hive/hive.yml (global user config)
    2. .hive.yml (version-controlled project config)
    3. .hive.local.yml (git-ignored local overrides)

    Args:
        git_root: Git repository root. If None, auto-detected.

    Returns:
        List of config file paths that exist.
    """
    files: list[Path] = []

    # Global config (lowest precedence)
    global_config = find_global_config()
    if global_config:
        files.append(global_config)

    # Project config files
    if git_root is None:
        git_root = find_git_root()

    if git_root is not None:
        for filename in [CONFIG_FILE, LOCAL_CONFIG_FILE]:
            path = git_root / filename
            if path.exists():
                files.append(path)

    return files


def load_yaml_file(path: Path) -> dict[str, Any]:
    """Load a YAML configuration file.

    Args:
        path: Path to the YAML file.

    Returns:
        Parsed YAML content as a dictionary.
    """
    with open(path) as f:
        content = yaml.safe_load(f)
        return content if content else {}


def load_default_config() -> dict[str, Any]:
    """Load the default configuration shipped with the package.

    Returns:
        Default configuration as a dictionary.
    """
    # Use importlib.resources to load the default config
    # This works whether installed as package or running from source
    try:
        # Python 3.9+ style
        config_pkg = resources.files("hive_cli.config")
        default_file = config_pkg.joinpath("default.yml")
        content = default_file.read_text()
        return yaml.safe_load(content) or {}
    except (TypeError, AttributeError):
        # Fallback for older Python or edge cases
        import hive_cli.config as config_module

        config_dir = Path(config_module.__file__).parent
        default_path = config_dir / "default.yml"
        return load_yaml_file(default_path)


def _get_env_overrides() -> dict[str, Any]:
    """Get configuration overrides from environment variables.

    Supports both new HIVE_* variables and legacy variables for
    backward compatibility.

    Returns:
        Dictionary with environment-based overrides.
    """
    overrides: dict[str, Any] = {}

    # Load new HIVE_* env vars using pydantic-settings
    env_settings = HiveEnvSettings()

    # Map flat env settings to nested config structure
    if env_settings.agents_order is not None:
        overrides.setdefault("agents", {})["order"] = env_settings.agents_order

    if env_settings.resume_enabled is not None:
        overrides.setdefault("resume", {})["enabled"] = env_settings.resume_enabled

    if env_settings.worktrees_enabled is not None:
        overrides.setdefault("worktrees", {})["enabled"] = (
            env_settings.worktrees_enabled
        )

    if env_settings.worktrees_parent_dir is not None:
        overrides.setdefault("worktrees", {})["parent_dir"] = (
            env_settings.worktrees_parent_dir
        )

    if env_settings.worktrees_use_home is not None:
        overrides.setdefault("worktrees", {})["use_home"] = (
            env_settings.worktrees_use_home
        )

    if env_settings.worktrees_resume is not None:
        overrides.setdefault("worktrees", {})["resume"] = env_settings.worktrees_resume

    if env_settings.worktrees_skip_permissions is not None:
        overrides.setdefault("worktrees", {})["skip_permissions"] = (
            env_settings.worktrees_skip_permissions
        )

    if env_settings.zellij_layout is not None:
        overrides.setdefault("zellij", {})["layout"] = env_settings.zellij_layout

    if env_settings.zellij_session_name is not None:
        overrides.setdefault("zellij", {})["session_name"] = (
            env_settings.zellij_session_name
        )

    if env_settings.github_fetch_issues is not None:
        overrides.setdefault("github", {})["fetch_issues"] = (
            env_settings.github_fetch_issues
        )

    if env_settings.github_issue_limit is not None:
        overrides.setdefault("github", {})["issue_limit"] = (
            env_settings.github_issue_limit
        )

    # Legacy env vars (lower precedence than HIVE_* vars)
    # Only apply if the new vars haven't set the same field
    if "worktrees" not in overrides or "use_home" not in overrides.get("worktrees", {}):
        legacy_home = os.environ.get(LEGACY_ENV_WORKTREES_HOME)
        if legacy_home == "true":
            overrides.setdefault("worktrees", {})["use_home"] = True

    return overrides


def _parse_agent_config(data: dict[str, Any]) -> AgentConfig:
    """Parse agent configuration from YAML data.

    Args:
        data: Dictionary with agent config.

    Returns:
        AgentConfig instance.
    """
    return AgentConfig(
        resume_args=data.get("resume_args", []),
        skip_permissions_args=data.get("skip_permissions_args", []),
    )


def _parse_agents_config(data: dict[str, Any]) -> AgentsConfig:
    """Parse agents configuration from YAML data.

    Args:
        data: Dictionary with agents config.

    Returns:
        AgentsConfig instance.
    """
    order = data.get("order", [])
    configs: dict[str, AgentConfig] = {}

    configs_data = data.get("configs", {})
    for agent_name, agent_data in configs_data.items():
        if isinstance(agent_data, dict):
            configs[agent_name] = _parse_agent_config(agent_data)

    return AgentsConfig(order=order, configs=configs)


def _parse_post_create_command(data: dict[str, Any] | str) -> PostCreateCommand:
    """Parse a post_create command from YAML data.

    Args:
        data: Dictionary with command config, or just a command string.

    Returns:
        PostCreateCommand instance.
    """
    if isinstance(data, str):
        return PostCreateCommand(command=data)

    return PostCreateCommand(
        command=data.get("command", ""),
        if_exists=data.get("if_exists"),
    )


def _parse_auto_select_config(data: dict[str, Any]) -> AutoSelectConfig:
    """Parse auto_select configuration from YAML data.

    Args:
        data: Dictionary with auto_select config.

    Returns:
        AutoSelectConfig instance.
    """
    return AutoSelectConfig(
        enabled=data.get("enabled", False),
        branch=data.get("branch", "-"),
        timeout=data.get("timeout", 3.0),
    )


def _parse_worktrees_config(data: dict[str, Any]) -> WorktreesConfig:
    """Parse worktrees configuration from YAML data.

    Args:
        data: Dictionary with worktrees config.

    Returns:
        WorktreesConfig instance.
    """
    post_create_data = data.get("post_create", [])
    post_create = [_parse_post_create_command(cmd) for cmd in post_create_data]

    auto_select_data = data.get("auto_select", {})
    auto_select = _parse_auto_select_config(auto_select_data)

    return WorktreesConfig(
        enabled=data.get("enabled", True),
        auto_select=auto_select,
        parent_dir=data.get("parent_dir", ".worktrees"),
        use_home=data.get("use_home", False),
        post_create=post_create,
        copy_files=data.get("copy_files", []),
        symlink_files=data.get("symlink_files", []),
        resume=data.get("resume", False),
        skip_permissions=data.get("skip_permissions", False),
    )


def _parse_zellij_config(data: dict[str, Any]) -> ZellijConfig:
    """Parse zellij configuration from YAML data.

    Args:
        data: Dictionary with zellij config.

    Returns:
        ZellijConfig instance.
    """
    return ZellijConfig(
        layout=data.get("layout"),  # None by default
        session_name=data.get("session_name", "{repo}-{agent}"),
    )


def _parse_github_config(data: dict[str, Any]) -> GitHubConfig:
    """Parse github configuration from YAML data.

    Args:
        data: Dictionary with github config.

    Returns:
        GitHubConfig instance.
    """
    return GitHubConfig(
        fetch_issues=data.get("fetch_issues", True),
        issue_limit=data.get("issue_limit", 20),
    )


def _parse_resume_config(data: dict[str, Any]) -> ResumeConfig:
    """Parse resume configuration from YAML data.

    Args:
        data: Dictionary with resume config.

    Returns:
        ResumeConfig instance.
    """
    return ResumeConfig(
        enabled=data.get("enabled", False),
    )


def _parse_config(data: dict[str, Any]) -> HiveConfig:
    """Parse full configuration from merged YAML data.

    Args:
        data: Merged configuration dictionary.

    Returns:
        HiveConfig instance.
    """
    return HiveConfig(
        agents=_parse_agents_config(data.get("agents", {})),
        resume=_parse_resume_config(data.get("resume", {})),
        worktrees=_parse_worktrees_config(data.get("worktrees", {})),
        zellij=_parse_zellij_config(data.get("zellij", {})),
        github=_parse_github_config(data.get("github", {})),
    )


@lru_cache(maxsize=1)
def load_config() -> HiveConfig:
    """Load configuration with caching.

    Configuration precedence (highest to lowest):
    1. Environment variables (HIVE_*, plus legacy GIT_WORKTREES_HOME)
    2. .hive.local.yml (local overrides, git-ignored)
    3. .hive.yml (project config, version-controlled)
    4. $XDG_CONFIG_HOME/hive/hive.yml (global user config)
    5. Package default config (default.yml)

    Returns:
        HiveConfig instance with merged configuration.
    """
    # Start with package defaults
    merged = load_default_config()

    # Load config files in order (lowest to highest precedence)
    config_files = find_config_files()
    for path in config_files:
        file_data = load_yaml_file(path)
        merged = deep_merge(merged, file_data)

    # Apply environment variable overrides (highest precedence)
    env_overrides = _get_env_overrides()
    merged = deep_merge(merged, env_overrides)

    return _parse_config(merged)


def reload_config() -> HiveConfig:
    """Force reload of configuration.

    Clears the cache and reloads configuration from files.

    Returns:
        Fresh HiveConfig instance.
    """
    load_config.cache_clear()
    return load_config()
