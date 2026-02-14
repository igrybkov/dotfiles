"""Core symlink functionality."""

from __future__ import annotations

import fnmatch
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

# Marker file that indicates a directory should be symlinked as a whole
DEFAULT_DIRECTORY_MARKER = ".symlink-as-directory"

# Default file patterns to exclude from symlinking
# Note: dotfiles (files starting with .) in source are excluded by default
# because the source should use non-hidden names and rely on --prefix to add the dot
DEFAULT_EXCLUDE_PATTERNS = [
    ".*",  # All dotfiles (hidden files) in source
    "*~",  # Backup files
    "*.bak",  # Backup files
    "*.swp",  # Vim swap files
]


@dataclass
class SymlinkResult:
    """Result of symlink operations."""

    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.created or self.updated)

    @property
    def failed(self) -> bool:
        return bool(self.conflicts or self.errors)

    def to_dict(self) -> dict:
        return {
            "changed": self.changed,
            "failed": self.failed,
            "created": len(self.created),
            "updated": len(self.updated),
            "skipped": len(self.skipped),
            "conflicts": self.conflicts,
            "errors": self.errors,
        }


def matches_exclude_pattern(filename: str, patterns: list[str]) -> bool:
    """Check if filename matches any of the exclude patterns."""
    for pattern in patterns:
        if fnmatch.fnmatch(filename, pattern):
            return True
    return False


def find_marker_directories(source_dir: Path, marker_name: str) -> list[Path]:
    """Find directories containing the marker file."""
    marker_dirs = []
    for marker_file in source_dir.rglob(marker_name):
        marker_dirs.append(marker_file.parent)
    return marker_dirs


def is_inside_marker_dir(path: Path, marker_dirs: list[Path]) -> bool:
    """Check if path is inside any marker directory."""
    for marker_dir in marker_dirs:
        try:
            path.relative_to(marker_dir)
            return True
        except ValueError:
            continue
    return False


def create_symlink(
    source: Path,
    target: Path,
    dry_run: bool = False,
) -> Literal["created", "updated", "skipped", "conflict"]:
    """
    Create or update a symlink.

    Args:
        source: Source path (will be stored as absolute path in symlink)
        target: Target path where symlink will be created
        dry_run: If True, don't actually create/modify symlinks

    Returns:
        Status string: "created", "updated", "skipped", or "conflict"
    """
    # Ensure source is absolute for consistent symlink targets
    source_absolute = source.resolve()

    if target.exists() or target.is_symlink():
        if target.is_symlink():
            # Get the raw symlink target and resolve it for comparison
            current_target = target.readlink()
            # Handle both absolute and relative symlink targets
            if current_target.is_absolute():
                current_resolved = current_target
            else:
                current_resolved = (target.parent / current_target).resolve()

            if current_resolved == source_absolute:
                return "skipped"
            # Different symlink - update it
            if not dry_run:
                target.unlink()
                target.symlink_to(source_absolute)
            return "updated"
        else:
            # Regular file or directory - conflict
            return "conflict"
    else:
        # Create new symlink
        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(source_absolute)
        return "created"


def symlink_dotfiles(
    source_dirs: list[Path],
    target_dir: Path,
    prefix: str = "",
    exclude_dirs: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
    marker_name: str = DEFAULT_DIRECTORY_MARKER,
    dry_run: bool = False,
    verbose: bool = False,
) -> SymlinkResult:
    """
    Create symlinks from source directories to target directory.

    Args:
        source_dirs: List of source directories to process
        target_dir: Target directory for symlinks
        prefix: Prefix for target filenames (e.g., "." for dotfiles)
        exclude_dirs: Top-level directory names to exclude
        exclude_patterns: File patterns to exclude (defaults to DEFAULT_EXCLUDE_PATTERNS)
        marker_name: Name of marker file for directory-level symlinks
        dry_run: If True, don't actually create symlinks
        verbose: If True, print detailed progress to stderr

    Returns:
        SymlinkResult with statistics and any conflicts/errors
    """
    result = SymlinkResult()
    exclude_dirs = exclude_dirs or []
    exclude_patterns = (
        exclude_patterns if exclude_patterns is not None else DEFAULT_EXCLUDE_PATTERNS
    )

    for source_dir in source_dirs:
        if not source_dir.exists():
            if verbose:
                print(f"Skipping non-existent source: {source_dir}", file=sys.stderr)
            continue

        if verbose:
            print(f"Processing: {source_dir}", file=sys.stderr)

        # Find marker directories
        marker_dirs = find_marker_directories(source_dir, marker_name)

        # Symlink marker directories first
        for marker_dir in marker_dirs:
            rel_path = marker_dir.relative_to(source_dir)

            # Skip hidden directories (e.g., .git, .svn, .venv, .cache)
            if any(part.startswith(".") for part in rel_path.parts):
                continue

            # Check if in excluded directory
            if rel_path.parts and rel_path.parts[0] in exclude_dirs:
                continue

            target_path = target_dir / f"{prefix}{rel_path}"

            status = create_symlink(marker_dir, target_path, dry_run)
            target_str = str(target_path)

            if status == "created":
                result.created.append(target_str)
            elif status == "updated":
                result.updated.append(target_str)
            elif status == "skipped":
                result.skipped.append(target_str)
            elif status == "conflict":
                result.conflicts.append(target_str)

            if verbose:
                print(f"  [{status}] {target_path} -> {marker_dir}", file=sys.stderr)

        # Find and symlink all files
        for source_file in source_dir.rglob("*"):
            if not source_file.is_file():
                continue

            # Skip marker files
            if source_file.name == marker_name:
                continue

            # Skip files matching exclude patterns
            if matches_exclude_pattern(source_file.name, exclude_patterns):
                continue

            rel_path = source_file.relative_to(source_dir)

            # Skip files inside hidden directories (e.g., .git, .svn, .venv, .cache)
            if any(part.startswith(".") for part in rel_path.parts[:-1]):
                continue

            # Check if in excluded directory
            if rel_path.parts and rel_path.parts[0] in exclude_dirs:
                continue

            # Check if inside a marker directory (already handled)
            if is_inside_marker_dir(source_file, marker_dirs):
                continue

            target_path = target_dir / f"{prefix}{rel_path}"

            status = create_symlink(source_file, target_path, dry_run)
            target_str = str(target_path)

            if status == "created":
                result.created.append(target_str)
            elif status == "updated":
                result.updated.append(target_str)
            elif status == "skipped":
                result.skipped.append(target_str)
            elif status == "conflict":
                result.conflicts.append(target_str)

            if verbose:
                print(f"  [{status}] {target_path} -> {source_file}", file=sys.stderr)

    return result
