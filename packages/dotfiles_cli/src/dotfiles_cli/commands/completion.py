"""Shell completion command."""

from __future__ import annotations

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
    if shell == "fish":
        # click >=8.4's fish source template is broken: `string split \n` in the
        # template renders as a literal newline, and each completion is emitted
        # as 3 lines (type/value/help) which `set -l response (cmd)` flattens.
        # Until upstream ships a fix, ship our own hand-rolled fish script and
        # refuse to install it programmatically — the canonical copy lives in
        # profiles/shell/files/dotfiles/config/fish/completions/dotfiles.fish
        # and is already symlinked into place by the dotfiles role.
        if install:
            raise click.ClickException(
                "fish completion is hand-maintained at "
                "profiles/shell/files/dotfiles/config/fish/completions/dotfiles.fish "
                "(click 8.4's generated fish script is broken). "
                "It's already symlinked by the dotfiles role — run "
                "`dotfiles install dotfiles` if it's missing."
            )
        click.echo(shell_completion.source())
        return 0

    completion_str = shell_completion.source()
    if not install:
        click.echo(completion_str)
        return 0
    raise NotImplementedError(
        f"Automatic installation for {shell} is not supported yet."
    )
