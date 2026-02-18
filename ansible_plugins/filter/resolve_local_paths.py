"""
Ansible filter plugin for resolving relative paths in package lists.

Usage in playbooks:
    {{ pipx_packages | resolve_local_paths(profile_dir) }}

Resolves relative `path` fields (e.g., 'packages/foo') to absolute paths
using the provided profile_dir. This is used during aggregation so that
local package paths from different profiles are pre-resolved before merging.
"""

from __future__ import annotations

from typing import Any


class FilterModule:
    """Ansible filter plugin for resolving relative package paths."""

    def filters(self) -> dict[str, Any]:
        return {
            "resolve_local_paths": self.resolve_local_paths,
        }

    def resolve_local_paths(self, packages: list[Any], profile_dir: str) -> list[Any]:
        """
        Resolve relative path fields to absolute using profile_dir.

        Args:
            packages: List of package dicts (or strings) from a profile.
            profile_dir: The profile's directory path for resolving relative paths.

        Returns:
            List with relative paths resolved to absolute.
        """
        result = []
        for pkg in packages:
            if isinstance(pkg, dict) and "path" in pkg:
                path = pkg["path"]
                if not path.startswith("/"):
                    pkg = {**pkg, "path": f"{profile_dir}/{path}"}
            result.append(pkg)
        return result
