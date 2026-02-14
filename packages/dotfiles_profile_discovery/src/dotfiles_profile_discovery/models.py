"""Data models for profile discovery."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ProfileInfo:
    """Information about a discovered profile.

    Attributes:
        name: Effective profile name (e.g., "myrepo-work" for nested profiles)
        path: Absolute path to profile directory
        relative_path: Relative path from profiles/ (e.g., "myrepo/work")
        priority: Execution priority (lower = earlier)
        host_name: Ansible host name (e.g., "myrepo-work-profile")
        connection: Ansible connection type (default: "local")
        config: Parsed config.yml contents (without profile key)
    """

    name: str
    path: Path
    relative_path: str
    priority: int
    host_name: str
    connection: str
    config: dict[str, Any]
