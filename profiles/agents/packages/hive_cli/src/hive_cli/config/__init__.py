"""Hive CLI configuration module.

Configuration is loaded from YAML files with the following precedence
(highest to lowest):

1. Environment variables (HIVE_* prefix, e.g., HIVE_AGENTS_ORDER)
2. .hive.local.yml (local overrides, git-ignored)
3. .hive.yml (project config, version-controlled)
4. $XDG_CONFIG_HOME/hive/hive.yml (global user config)
5. Package default config (default.yml)

Environment Variables:
    HIVE_AGENTS_ORDER         - Comma-separated list of agents, e.g., 'claude,gemini'
    HIVE_RESUME_ENABLED       - Enable resume by default (true/false)
    HIVE_WORKTREES_ENABLED    - Enable worktrees feature (true/false)
    HIVE_WORKTREES_PARENT_DIR - Directory for worktrees
    HIVE_WORKTREES_USE_HOME   - Use ~/.git-worktrees/ (true/false)
    HIVE_WORKTREES_RESUME     - Resume default for worktrees (true/false)
    HIVE_ZELLIJ_LAYOUT        - Zellij layout name
    HIVE_ZELLIJ_SESSION_NAME  - Session name template
    HIVE_GITHUB_FETCH_ISSUES  - Fetch GitHub issues (true/false)
    HIVE_GITHUB_ISSUE_LIMIT   - Max issues to fetch (integer)

Legacy environment variables (still supported):
    GIT_WORKTREES_HOME  - Set to "true" for home worktrees mode

Usage:
    from hive_cli.config import load_config, reload_config

    config = load_config()
    print(config.agents.order)
    print(config.worktrees.parent_dir)
"""

from .defaults import KNOWN_AGENTS
from .loader import (
    CONFIG_FILE,
    GLOBAL_CONFIG_DIR,
    GLOBAL_CONFIG_FILES,
    LOCAL_CONFIG_FILE,
    find_config_files,
    find_git_root,
    find_global_config,
    get_xdg_config_home,
    load_config,
    load_default_config,
    load_yaml_file,
    reload_config,
)
from .merge import deep_merge
from .schema import (
    AgentConfig,
    AgentsConfig,
    GitHubConfig,
    HiveConfig,
    PostCreateCommand,
    ResumeConfig,
    WorktreesConfig,
    ZellijConfig,
)

# Backward-compatible constants
ENV_HIVE_AGENT = "HIVE_AGENT"


def get_agent_config(agent_name: str) -> AgentConfig:
    """Get configuration for a specific agent.

    Args:
        agent_name: Name of the agent.

    Returns:
        AgentConfig for the agent, or default config if not found.
    """
    config = load_config()
    return config.agents.configs.get(agent_name, AgentConfig())


def get_agent_order() -> list[str]:
    """Get agent priority order.

    Uses configuration from .hive.yml/.hive.local.yml files,
    falling back to defaults.

    Returns:
        List of agent names in priority order.
    """
    config = load_config()
    return config.agents.order


__all__ = [
    # Schema
    "AgentConfig",
    "AgentsConfig",
    "GitHubConfig",
    "HiveConfig",
    "PostCreateCommand",
    "ResumeConfig",
    "WorktreesConfig",
    "ZellijConfig",
    # Loader
    "CONFIG_FILE",
    "GLOBAL_CONFIG_DIR",
    "GLOBAL_CONFIG_FILES",
    "LOCAL_CONFIG_FILE",
    "find_config_files",
    "find_git_root",
    "find_global_config",
    "get_xdg_config_home",
    "load_config",
    "load_default_config",
    "load_yaml_file",
    "reload_config",
    # Defaults
    "KNOWN_AGENTS",
    # Merge
    "deep_merge",
    # Backward-compatible
    "ENV_HIVE_AGENT",
    "get_agent_config",
    "get_agent_order",
]
