"""Fast symlink management for dotfiles."""

from symlink_dotfiles.core import (
    DEFAULT_DIRECTORY_MARKER,
    DEFAULT_EXCLUDE_PATTERNS,
    SymlinkResult,
    create_symlink,
    find_marker_directories,
    is_inside_marker_dir,
    matches_exclude_pattern,
    symlink_dotfiles,
)

__all__ = [
    "DEFAULT_DIRECTORY_MARKER",
    "DEFAULT_EXCLUDE_PATTERNS",
    "SymlinkResult",
    "create_symlink",
    "find_marker_directories",
    "is_inside_marker_dir",
    "matches_exclude_pattern",
    "symlink_dotfiles",
]
