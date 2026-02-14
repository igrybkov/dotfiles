"""CLI entry point for symlink-dotfiles."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from symlink_dotfiles.core import (
    DEFAULT_DIRECTORY_MARKER,
    DEFAULT_EXCLUDE_PATTERNS,
    symlink_dotfiles,
)


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Symlink dotfiles from source directories to target directory."
    )
    parser.add_argument(
        "--source",
        "-s",
        action="append",
        required=True,
        type=Path,
        dest="source_dirs",
        help="Source directory (can be specified multiple times)",
    )
    parser.add_argument(
        "--target",
        "-t",
        required=True,
        type=Path,
        help="Target directory for symlinks",
    )
    parser.add_argument(
        "--prefix",
        "-p",
        default="",
        help="Prefix for target filenames (e.g., '.' for dotfiles)",
    )
    parser.add_argument(
        "--exclude",
        "-e",
        action="append",
        default=[],
        dest="exclude_dirs",
        help="Top-level directories to exclude",
    )
    parser.add_argument(
        "--marker",
        "-m",
        default=DEFAULT_DIRECTORY_MARKER,
        dest="marker_name",
        help=f"Marker file name for directory-level symlinks (default: {DEFAULT_DIRECTORY_MARKER})",
    )
    parser.add_argument(
        "--exclude-pattern",
        "-x",
        action="append",
        default=[],
        dest="exclude_patterns",
        help="File patterns to exclude (can be specified multiple times)",
    )
    parser.add_argument(
        "--no-default-excludes",
        action="store_true",
        help=f"Don't use default exclude patterns ({', '.join(DEFAULT_EXCLUDE_PATTERNS)})",
    )
    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--json",
        "-j",
        action="store_true",
        dest="json_output",
        help="Output results as JSON (for Ansible integration)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print detailed progress",
    )

    args = parser.parse_args()

    # Expand ~ in paths
    target_dir = args.target.expanduser()
    source_dirs = [s.expanduser() for s in args.source_dirs]

    # Build exclude patterns list
    if args.no_default_excludes:
        exclude_patterns = args.exclude_patterns if args.exclude_patterns else []
    else:
        exclude_patterns = list(DEFAULT_EXCLUDE_PATTERNS) + args.exclude_patterns

    result = symlink_dotfiles(
        source_dirs=source_dirs,
        target_dir=target_dir,
        prefix=args.prefix,
        exclude_dirs=args.exclude_dirs,
        exclude_patterns=exclude_patterns,
        marker_name=args.marker_name,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )

    if args.json_output:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(f"Created: {len(result.created)}")
        print(f"Updated: {len(result.updated)}")
        print(f"Skipped: {len(result.skipped)}")
        if result.conflicts:
            print(f"Conflicts: {len(result.conflicts)}")
            for conflict in result.conflicts:
                print(f"  - {conflict}")
        if result.errors:
            print(f"Errors: {len(result.errors)}")
            for error in result.errors:
                print(f"  - {error}")

    return 1 if result.failed else 0


if __name__ == "__main__":
    sys.exit(main())
