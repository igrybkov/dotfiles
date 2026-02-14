"""Shared profile discovery logic for dotfiles.

This package provides the core logic for discovering profiles in the dotfiles
repository. It is used by both the CLI and the Ansible inventory plugin to
ensure consistent profile discovery behavior.

Supports two-level profile structures:
- profiles/{profile}/config.yml (single level)
- profiles/{repo}/{profile}/config.yml (nested level)
"""

from .discovery import discover_profiles, get_profile_by_name
from .models import ProfileInfo
from .naming import get_default_priority, path_to_name

__all__ = [
    "ProfileInfo",
    "discover_profiles",
    "get_default_priority",
    "get_profile_by_name",
    "path_to_name",
]

__version__ = "0.1.0"
