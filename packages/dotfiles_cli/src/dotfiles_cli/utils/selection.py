"""Interactive selection utilities for the dotfiles CLI."""

from __future__ import annotations

import subprocess

import click


def fzf_select(options: list[str], prompt: str) -> str | None:
    """Use fzf for interactive selection.

    Args:
        options: List of options to choose from
        prompt: Prompt to display

    Returns:
        Selected option or None if cancelled
    """
    try:
        result = subprocess.run(
            [
                "fzf",
                "--prompt",
                f"{prompt}: ",
                "--height=40%",
                "--layout=reverse",
                "--border",
            ],
            input="\n".join(options),
            capture_output=True,
            text=True,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except subprocess.SubprocessError:
        return None


def numbered_select(options: list[str], prompt: str) -> str | None:
    """Use numbered selection as fallback.

    Args:
        options: List of options to choose from
        prompt: Prompt to display

    Returns:
        Selected option or None if cancelled
    """
    click.echo(f"\n{prompt}:")
    for i, option in enumerate(options, 1):
        click.echo(f"  {i}. {option}")

    while True:
        try:
            choice = click.prompt("\nEnter number", type=int)
            if 1 <= choice <= len(options):
                return options[choice - 1]
            click.echo(f"Please enter a number between 1 and {len(options)}")
        except click.Abort:
            return None
