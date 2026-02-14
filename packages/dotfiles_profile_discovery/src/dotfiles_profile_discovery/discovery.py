"""Core profile discovery logic.

Discovers profiles at up to three levels:
- Level 1: profiles/{profile}/config.yml
- Level 2: profiles/{repo}/{profile}/config.yml
- Level 3: profiles/{ignored}/{repo}/{profile}/config.yml

A directory is only considered a profile if it contains a config.yml file.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from .models import ProfileInfo
from .naming import get_default_priority, path_to_name


def discover_profiles(profiles_dir: Path) -> list[ProfileInfo]:
    """Discover all profiles at depth 1, 2, or 3 with config.yml.

    Scans the profiles directory for valid profiles. A directory is considered
    a profile if it contains a config.yml file. Supports three levels:
    - profiles/{profile}/config.yml (single level)
    - profiles/{repo}/{profile}/config.yml (nested level)
    - profiles/{dir}/{repo}/{profile}/config.yml (deep nested level)

    Demo mode (DEMO=1): Skips profiles under the "private" directory to avoid
    exposing private information in demos and documentation.

    Args:
        profiles_dir: Path to the profiles directory

    Returns:
        List of ProfileInfo objects for discovered profiles
    """
    profiles: list[ProfileInfo] = []

    if not profiles_dir.exists():
        return profiles

    demo_mode = os.environ.get("DEMO", "").strip() in ("1", "true", "True", "TRUE")

    for level1 in sorted(profiles_dir.iterdir()):
        if not level1.is_dir() or level1.name.startswith("."):
            continue

        # Skip private profiles in demo mode
        if demo_mode and level1.name == "private":
            continue

        config_file = level1 / "config.yml"
        if config_file.exists():
            # Depth 1: profiles/{profile}/config.yml
            profiles.append(_load_profile(profiles_dir, level1, config_file))
        else:
            # Check depth 2: profiles/{repo}/{profile}/config.yml
            for level2 in sorted(level1.iterdir()):
                if not level2.is_dir() or level2.name.startswith("."):
                    continue

                config_file = level2 / "config.yml"
                if config_file.exists():
                    # Depth 2: profiles/{repo}/{profile}/config.yml
                    profiles.append(_load_profile(profiles_dir, level2, config_file))
                else:
                    # Check depth 3: profiles/{dir}/{repo}/{profile}/config.yml
                    for level3 in sorted(level2.iterdir()):
                        if not level3.is_dir() or level3.name.startswith("."):
                            continue

                        config_file = level3 / "config.yml"
                        if config_file.exists():
                            # Depth 3: profiles/{dir}/{repo}/{profile}/config.yml
                            profiles.append(
                                _load_profile(profiles_dir, level3, config_file)
                            )

    return profiles


def _load_profile(
    profiles_dir: Path, profile_path: Path, config_file: Path
) -> ProfileInfo:
    """Load a profile from its config.yml.

    Args:
        profiles_dir: Root profiles directory
        profile_path: Path to the profile directory
        config_file: Path to the config.yml file

    Returns:
        ProfileInfo with parsed configuration
    """
    relative = profile_path.relative_to(profiles_dir)
    default_name = path_to_name(str(relative))

    config = _load_yaml(config_file)
    profile_meta = config.pop("profile", {})

    name = profile_meta.get("name", default_name)
    priority = profile_meta.get("priority", get_default_priority(name))
    host_name = profile_meta.get("host", f"{name}-profile")
    connection = profile_meta.get("connection", "local")

    return ProfileInfo(
        name=name,
        path=profile_path.resolve(),
        relative_path=str(relative),
        priority=priority,
        host_name=host_name,
        connection=connection,
        config=config,
    )


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file and return its contents.

    Args:
        path: Path to YAML file

    Returns:
        Parsed YAML contents as dict, or empty dict if file is empty
    """
    try:
        with open(path) as f:
            return yaml.safe_load(f) or {}
    except yaml.YAMLError:
        return {}


def get_profile_by_name(profiles_dir: Path, name: str) -> ProfileInfo | None:
    """Get a profile by its name.

    Args:
        profiles_dir: Path to the profiles directory
        name: Profile name to find

    Returns:
        ProfileInfo if found, None otherwise
    """
    for profile in discover_profiles(profiles_dir):
        if profile.name == name:
            return profile
    return None
