"""Edit command for opening dotfiles in an editor."""

from __future__ import annotations

import os
import shutil
import subprocess

import click

from ..constants import DOTFILES_DIR


@click.command()
def edit():
    """Edit the dotfiles."""
    if shutil.which("code") is not None:
        subprocess.call(["code", DOTFILES_DIR])
    elif os.getenv("EDITOR"):
        subprocess.call([os.getenv("EDITOR"), DOTFILES_DIR])
    else:
        raise RuntimeError(
            f"No supported editor found in the environment to open the directory for editing: {DOTFILES_DIR}"
        )
