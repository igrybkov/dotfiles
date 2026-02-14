"""Config command group for managing configuration."""

from __future__ import annotations

import click
from rich.console import Console

from ..profiles import (
    get_all_profile_names,
    interactive_profile_config,
    interactive_settings_config,
    parse_profile_selection,
    save_profile_selection,
    show_current_config,
)

console = Console()


@click.group(invoke_without_command=True)
@click.pass_context
def config(ctx: click.Context) -> None:
    """Configure dotfiles profiles and settings.

    When called without a subcommand, runs both profiles and settings
    configuration sequentially.

    \b
    Subcommands:
      profiles  Select which profiles to activate
      settings  Configure behavior settings (symlinks, etc.)
    """
    if ctx.invoked_subcommand is None:
        # Run both profiles and settings when no subcommand specified
        result = interactive_profile_config()
        if result != 0:
            ctx.exit(result)

        console.print()
        result = interactive_settings_config()
        ctx.exit(result if result else 0)


@config.command("profiles")
@click.option(
    "--non-interactive",
    is_flag=True,
    default=False,
    help="Show current configuration without interactive prompt",
)
@click.argument("selection", required=False, default=None)
def config_profiles_cmd(non_interactive: bool, selection: str | None) -> int:
    """Configure active profiles.

    Interactively select which profiles to enable, or pass a selection string.

    \b
    Selection syntax:
        common,work     Select specific profiles
        -mycompany          All profiles except mycompany
        all             All profiles
        all,-work       All except work

    \b
    Examples:
        dotfiles config profiles                    # Interactive TUI
        dotfiles config profiles --non-interactive # Show current config
        dotfiles config profiles common,personal   # Set specific profiles
        dotfiles config profiles all,-work         # All except work
    """
    available = get_all_profile_names()

    # If selection provided as argument, apply it directly
    if selection:
        parsed = parse_profile_selection(selection)
        resolved = parsed.resolve(available)
        if not resolved:
            console.print("[red]Error: No valid profiles in selection[/red]")
            return 1
        save_profile_selection(resolved)
        console.print(f"[green]Saved: DOTFILES_PROFILES={','.join(resolved)}[/green]")
        return 0

    # Non-interactive mode: just show current config
    if non_interactive:
        show_current_config()
        return 0

    # Interactive mode
    return interactive_profile_config()


@config.command("settings")
@click.option(
    "--non-interactive",
    is_flag=True,
    default=False,
    help="Show current settings without interactive prompt",
)
def config_settings_cmd(non_interactive: bool) -> int:
    """Configure behavior settings.

    Interactively toggle settings like symlink creation.

    \b
    Available settings:
        DOTFILES_NO_SYMLINK  Disable ~/.local/bin/dotfiles symlink

    \b
    Examples:
        dotfiles config settings                    # Interactive TUI
        dotfiles config settings --non-interactive # Show current settings
    """
    if non_interactive:
        # TODO: Implement non-interactive settings display
        console.print("[dim]Settings display not yet implemented[/dim]")
        return 0

    return interactive_settings_config()


# Legacy alias for backward compatibility
config_profiles = config
