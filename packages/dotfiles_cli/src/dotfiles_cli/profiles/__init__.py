"""Profile management for the dotfiles CLI."""

from .selection import ProfileSelection, parse_profile_selection
from .discovery import (
    get_profile_names,
    get_all_profile_names,
    get_profile_path,
    get_profile_priority,
    get_profile_roles_paths,
    get_profile_requirements_paths,
)
from .config import (
    get_active_profiles,
    save_profile_selection,
    show_current_config,
    interactive_profile_config,
    interactive_settings_config,
)
from .git import (
    get_profile_repos,
    get_repos_with_unpushed_changes,
    sync_profile_repos,
)

__all__ = [
    # Selection
    "ProfileSelection",
    "parse_profile_selection",
    # Discovery
    "get_profile_names",
    "get_all_profile_names",
    "get_profile_path",
    "get_profile_priority",
    "get_profile_roles_paths",
    "get_profile_requirements_paths",
    # Config
    "get_active_profiles",
    "save_profile_selection",
    "show_current_config",
    "interactive_profile_config",
    "interactive_settings_config",
    # Git
    "get_profile_repos",
    "get_repos_with_unpushed_changes",
    "sync_profile_repos",
]
