"""Shell completion command."""

from __future__ import annotations

import os

import click


@click.command()
@click.argument(
    "shell",
    type=click.Choice(["bash", "zsh", "fish"], case_sensitive=True),
)
@click.option("--install/--no-install", help="Install Shell completion", default=False)
@click.pass_context
def completion(ctx, shell: str, install: bool = False):
    """Generate completion script for the specified shell."""
    # Get the root CLI from context
    cli = ctx.find_root().command

    shell_completion: click.shell_completion.ShellComplete = (
        click.shell_completion.get_completion_class(shell)(
            cli=cli,
            complete_var="_DOTFILES_COMPLETE",
            prog_name="dotfiles",
            ctx_args={},
        )
    )
    completion_str = shell_completion.source()
    if not install:
        click.echo(completion_str)
        return 0
    # Install the completion script
    if shell == "fish":
        with open(
            f"{os.getenv('HOME')}/.config/fish/completions/dotfiles.fish", "w"
        ) as f:
            f.write(completion_str)
            return 0
    raise NotImplementedError(
        f"Automatic installation for {shell} is not supported yet."
    )
