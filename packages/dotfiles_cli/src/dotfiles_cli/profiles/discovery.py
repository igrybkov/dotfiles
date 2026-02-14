"""Profile discovery functions.

Uses the shared dotfiles_profile_discovery package for core discovery logic.
"""

from __future__ import annotations

from pathlib import Path

from dotfiles_profile_discovery import ProfileInfo, discover_profiles

from ..constants import DOTFILES_DIR


def _get_profiles() -> list[ProfileInfo]:
    """Get all discovered profiles using shared discovery logic."""
    return discover_profiles(Path(DOTFILES_DIR) / "profiles")


def get_profile_names() -> list[str]:
    """Get list of profile names from profiles/ directory.

    Returns profile names (including nested profiles with dash-separated names).
    The dynamic inventory plugin generates hosts as {name}-profile.

    Returns:
        Sorted list of profile names
    """
    profiles = _get_profiles()
    return sorted(p.name for p in profiles)


def get_all_profile_names() -> list[str]:
    """Get all available profile names from profiles/ directory.

    All profiles are discovered dynamically from the profiles/ directory.
    A directory is considered a profile only if it has config.yml.

    Returns:
        Sorted list of profile names
    """
    return get_profile_names()


def get_profile_path(name: str) -> Path | None:
    """Get filesystem path for a profile by name.

    Args:
        name: Profile name (e.g., "work" or "myrepo-work")

    Returns:
        Path to profile directory, or None if not found
    """
    for p in _get_profiles():
        if p.name == name:
            return p.path
    return None


def get_profile_priority(profile_name: str) -> int:
    """Get priority for a profile (matches inventory plugin logic).

    Args:
        profile_name: Name of the profile

    Returns:
        Priority value (lower = processed earlier)
    """
    for p in _get_profiles():
        if p.name == profile_name:
            return p.priority
    # Fall back to default priority calculation for unknown profiles
    from dotfiles_profile_discovery import get_default_priority

    return get_default_priority(profile_name)


def get_profile_roles_paths() -> list[str]:
    """Get list of roles directories from all profiles.

    Returns paths to profile roles directories that exist.
    These are added to ANSIBLE_ROLES_PATH so profiles can define custom roles.

    Returns:
        List of paths to profile roles directories
    """
    roles_paths = []
    for p in _get_profiles():
        roles_dir = p.path / "roles"
        if roles_dir.exists() and roles_dir.is_dir():
            roles_paths.append(str(roles_dir))
    return roles_paths


def get_profile_requirements_paths() -> list[str]:
    """Get list of Galaxy requirements files from all profiles.

    Returns paths to profile requirements.yml files that exist.
    These are installed in addition to the main requirements.yml file.

    Returns:
        List of paths to profile requirements files
    """
    requirements_paths = []
    for p in _get_profiles():
        requirements_file = p.path / "requirements.yml"
        if requirements_file.exists() and requirements_file.is_file():
            requirements_paths.append(str(requirements_file))
    return requirements_paths
