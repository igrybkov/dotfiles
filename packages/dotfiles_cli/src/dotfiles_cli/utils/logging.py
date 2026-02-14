"""Log file utilities for the dotfiles CLI."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import click

from ..constants import DOTFILES_DIR, LOGFILE_AUTO


def cleanup_old_logs(keep_count: int = 5, adds_new_log: bool = False) -> None:
    """Clean up old log files, keeping only the most recent ones.

    Args:
        keep_count: Number of most recent log files to keep (default: 5)
        adds_new_log: Whether a new log file will be created
    """
    log_dir = Path(DOTFILES_DIR)
    log_pattern = "ansible-run-*.log"

    # Find all log files matching the pattern
    log_files = list(log_dir.glob(log_pattern))

    if len(log_files) <= keep_count:
        return

    # Sort by modification time (most recent first)
    log_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

    # Get files to delete (all except the most recent keep_count)
    how_many_files_to_delete = keep_count - 1 if adds_new_log else keep_count
    files_to_delete = log_files[how_many_files_to_delete:]

    if files_to_delete:
        click.echo(f"Cleaning up old log files (keeping {keep_count} most recent)...")
        for log_file in files_to_delete:
            try:
                log_file.unlink()
            except OSError as e:
                click.echo(f"Warning: Could not delete {log_file.name}: {e}", err=True)


def preprocess_logfile_args(args: list[str]) -> list[str]:
    """Handle --logfile with optional argument.

    Converts:
      --logfile         -> --logfile __AUTO__
      --logfile foo.log -> --logfile foo.log
      -l                -> -l __AUTO__
      -l foo.log        -> -l foo.log
    """
    result = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("--logfile", "-l"):
            result.append(arg)
            # Check if next arg exists and doesn't start with -
            if i + 1 < len(args) and not args[i + 1].startswith("-"):
                result.append(args[i + 1])
                i += 2
            else:
                result.append(LOGFILE_AUTO)
                i += 1
        else:
            result.append(arg)
            i += 1
    return result


def generate_logfile_name() -> str:
    """Generate a timestamped log file name."""
    return f"ansible-run-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"
