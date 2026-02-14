"""Link command for symlinking dotfiles CLI to ~/.local/bin."""

from __future__ import annotations

from pathlib import Path

import click

from ..constants import DOTFILES_DIR, ENV_NO_SYMLINK_KEY
from ..settings import get_settings

# Target directory and filename
LOCAL_BIN = Path.home() / ".local" / "bin"
SYMLINK_NAME = "dotfiles"


@click.command("link")
@click.option(
    "--force",
    "-f",
    is_flag=True,
    default=False,
    help=f"Create symlink even if {ENV_NO_SYMLINK_KEY} is set",
)
@click.option(
    "--remove",
    "-r",
    is_flag=True,
    default=False,
    help="Remove the symlink instead of creating it",
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    default=False,
    help="Suppress output (for use in scripts)",
)
def link(force: bool = False, remove: bool = False, quiet: bool = False) -> int:
    """Symlink dotfiles CLI to ~/.local/bin for easy access.

    By default, creates a symlink at ~/.local/bin/dotfiles pointing to
    the dotfiles wrapper script in this repository.

    Set DOTFILES_NO_SYMLINK=1 to disable automatic symlinking.
    Use --force to override this setting.
    """
    symlink_path = LOCAL_BIN / SYMLINK_NAME
    source_path = Path(DOTFILES_DIR) / "dotfiles"

    if remove:
        if symlink_path.is_symlink():
            symlink_path.unlink()
            if not quiet:
                click.echo(f"Removed symlink: {symlink_path}")
        elif symlink_path.exists():
            click.echo(f"Error: {symlink_path} exists but is not a symlink", err=True)
            return 1
        elif not quiet:
            click.echo(f"Symlink does not exist: {symlink_path}")
        return 0

    # Check if symlinking is disabled (env var takes precedence, then .env, then .env.dist)
    settings = get_settings()
    if settings.dotfiles_no_symlink and not force:
        if not quiet:
            click.echo(
                f"Symlinking disabled ({ENV_NO_SYMLINK_KEY} is set). Use --force to override."
            )
        return 0

    # Create ~/.local/bin if it doesn't exist
    if not LOCAL_BIN.exists():
        LOCAL_BIN.mkdir(parents=True, mode=0o755)
        if not quiet:
            click.echo(f"Created directory: {LOCAL_BIN}")

    # Create or update the symlink
    if symlink_path.is_symlink():
        current_target = symlink_path.resolve()
        if current_target == source_path.resolve():
            if not quiet:
                click.echo(f"Symlink already exists: {symlink_path} -> {source_path}")
            return 0
        symlink_path.unlink()

    symlink_path.symlink_to(source_path)
    if not quiet:
        click.echo(f"Created symlink: {symlink_path} -> {source_path}")
    return 0
