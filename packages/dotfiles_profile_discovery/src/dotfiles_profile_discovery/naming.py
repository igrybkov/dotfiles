"""Naming conventions and utilities for profile discovery."""

from __future__ import annotations


def path_to_name(relative_path: str) -> str:
    """Convert relative path to profile name.

    Replaces path separators with dashes to create a flat name.

    Examples:
        path_to_name("work") -> "work"
        path_to_name("myrepo/work") -> "myrepo-work"

    Args:
        relative_path: Path relative to profiles/ directory

    Returns:
        Profile name with slashes replaced by dashes
    """
    return relative_path.replace("/", "-")


def get_default_priority(profile_name: str) -> int:
    """Get default priority based on profile name.

    Special profiles get lower priorities (run earlier):
    - 'default' / 'shell': 100
    - 'neovim': 110
    - 'development': 120
    - 'macos-desktop': 130
    - 'work' / 'personal': 200 (built-in workstation types)
    - All others: 1000

    Args:
        profile_name: Name of the profile

    Returns:
        Default priority value
    """
    special_priorities = {
        "default": 100,
        "shell": 100,
        "neovim": 110,
        "development": 120,
        "macos-desktop": 130,
        "work": 200,
        "personal": 200,
    }
    return special_priorities.get(profile_name, 1000)
