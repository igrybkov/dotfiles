"""Profile configuration and interactive TUI."""

from __future__ import annotations

import os
import sys

import click
import dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..constants import (
    DOTFILES_DIR,
    ENV_NO_SYMLINK_KEY,
    ENV_PROFILES_KEY,
)
from ..settings import get_setting_for_display, get_settings, save_setting
from .discovery import get_all_profile_names, get_profile_priority
from .selection import ProfileSelection, parse_profile_selection

console = Console()


def get_active_profiles() -> ProfileSelection:
    """Get active profile selection from environment or config files.

    Checks in order (via pydantic-settings):
    1. Environment variables
    2. .env file
    3. .env.dist file (defaults)

    Returns:
        ProfileSelection object representing current selection
    """
    settings = get_settings()
    return parse_profile_selection(settings.dotfiles_profiles)


def save_profile_selection(profiles: list[str]) -> None:
    """Save profile selection to .env file.

    Args:
        profiles: List of profile names to save
    """
    profiles_str = ",".join(sorted(profiles))
    save_setting(ENV_PROFILES_KEY, profiles_str)


def show_current_config() -> None:
    """Display current profile configuration."""
    available = get_all_profile_names()
    selection = get_active_profiles()
    active = selection.resolve(available)

    table = Table(title="Profile Configuration", caption="Listed in execution order")
    table.add_column("Profile", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Type", style="dim")

    builtin = ["common", "work", "personal"]
    # Sort by priority (lower = earlier), then alphabetically
    sorted_profiles = sorted(available, key=lambda p: (get_profile_priority(p), p))
    for profile in sorted_profiles:
        if profile in active:
            status = "[green]Active[/green]"
        else:
            status = "[dim]Inactive[/dim]"
        profile_type = "built-in" if profile in builtin else "custom"
        table.add_row(profile, status, profile_type)

    console.print(table)
    console.print()

    # Show current DOTFILES_PROFILES value
    profiles_env = os.getenv(ENV_PROFILES_KEY, "")
    if profiles_env:
        console.print(f"[bold]DOTFILES_PROFILES=[/bold]{profiles_env}")
    else:
        console.print(
            "[dim]No profile selection configured (will use defaults from .env.dist)[/dim]"
        )


def interactive_profile_config() -> int:
    """Interactive TUI for profile configuration.

    Supports two modes:
    - Exclude mode: Start with all, mark profiles to exclude (saves as '-work' or 'all,-work')
    - Include mode: Select specific profiles to include (saves as 'common,work')

    Defaults to exclude mode for easier configuration (exclude what you don't want).

    Returns:
        Exit code (0 for success, 1 for cancelled)
    """
    import termios
    import tty

    available = get_all_profile_names()
    selection = get_active_profiles()
    current_active = set(selection.resolve(available))

    # Track user selections and mode
    # exclude_mode: True = exclude specific profiles (default), False = include specific profiles
    # Default to exclude mode unless user has explicitly configured include mode
    has_explicit_config = (
        bool(selection.explicit_profiles) and not selection.include_all
    )
    exclude_mode = not has_explicit_config
    if exclude_mode:
        # In exclude mode: start with all included, mark exclusions
        # If coming from include mode, convert selected to excluded
        if has_explicit_config:
            excluded = set(available) - current_active
        else:
            excluded = set(selection.excluded_profiles)
        selected = set()
    else:
        selected = current_active.copy()
        excluded = set()

    cursor_pos = 0
    profile_list = sorted(available, key=lambda p: (get_profile_priority(p), p))
    builtin = ["common", "work", "personal"]

    def get_key() -> str:
        """Read a single keypress."""
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == "\x1b":
                ch += sys.stdin.read(2)
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    def get_resolved() -> list[str]:
        """Get the resolved list of profiles that will run."""
        if exclude_mode:
            return sorted(set(available) - excluded)
        else:
            return sorted(selected)

    def get_selection_string() -> str:
        """Get the selection string that will be saved."""
        if exclude_mode:
            if not excluded:
                return "all"
            else:
                return ",".join([f"-{p}" for p in sorted(excluded)])
        else:
            return ",".join(sorted(selected))

    def render() -> None:
        """Render the current state."""
        console.clear()

        mode_text = (
            "[bold red]EXCLUDE[/bold red] mode (all profiles minus exclusions)"
            if exclude_mode
            else "[bold green]INCLUDE[/bold green] mode (only selected profiles)"
        )
        console.print(
            Panel.fit(
                f"[bold]Profile Configuration[/bold]\n"
                f"Mode: {mode_text}\n"
                f"[dim]Space: toggle, m: switch mode, Enter: save, q: cancel[/dim]",
                border_style="blue",
            )
        )
        console.print()

        console.print("[dim]Profiles (in execution order):[/dim]")
        for i, profile in enumerate(profile_list):
            cursor = "[bold cyan]>[/bold cyan] " if i == cursor_pos else "  "

            if exclude_mode:
                if profile in excluded:
                    checkbox = "[red][-][/red]"
                    status = "[red]excluded[/red]"
                else:
                    checkbox = "[green][+][/green]"
                    status = "[green]included[/green]"
            else:
                if profile in selected:
                    checkbox = "[green][X][/green]"
                    status = "[green]selected[/green]"
                else:
                    checkbox = "[ ]"
                    status = "[dim]not selected[/dim]"

            profile_type = "built-in" if profile in builtin else "custom"
            console.print(
                f"{cursor}{checkbox} {profile} {status} [dim]({profile_type})[/dim]"
            )

        console.print()

        resolved = get_resolved()
        selection_str = get_selection_string()
        if resolved:
            preview_text = f"Will run: {', '.join(resolved)}\nSaves as: DOTFILES_PROFILES={selection_str}"
            console.print(
                Panel.fit(preview_text, title="Preview", border_style="green")
            )
        else:
            console.print(
                Panel.fit(
                    "[yellow]Warning: No profiles will run![/yellow]",
                    title="Preview",
                    border_style="yellow",
                )
            )

        console.print()
        console.print(
            "[dim]Shortcuts: 'm' toggle mode, 'a' select/include all, 'n' select none/exclude all, 'c' common only[/dim]"
        )

    render()

    while True:
        key = get_key()

        if key == "q" or key == "\x03":
            console.clear()
            console.print("[yellow]Cancelled[/yellow]")
            return 1
        elif key == "\r" or key == "\n":
            break
        elif key == "m":
            if exclude_mode:
                selected = set(get_resolved())
                exclude_mode = False
            else:
                excluded = set(available) - selected
                exclude_mode = True
        elif key == " ":
            profile = profile_list[cursor_pos]
            if exclude_mode:
                if profile in excluded:
                    excluded.discard(profile)
                else:
                    excluded.add(profile)
            else:
                if profile in selected:
                    selected.discard(profile)
                else:
                    selected.add(profile)
        elif key == "\x1b[A":
            cursor_pos = max(0, cursor_pos - 1)
        elif key == "\x1b[B":
            cursor_pos = min(len(profile_list) - 1, cursor_pos + 1)
        elif key == "a":
            if exclude_mode:
                excluded = set()
            else:
                selected = set(available)
        elif key == "n":
            if exclude_mode:
                excluded = set(available)
            else:
                selected = set()
        elif key == "c":
            if exclude_mode:
                excluded = set(available) - {"common"}
            else:
                selected = {"common"}

        render()

    console.clear()
    resolved = get_resolved()
    selection_str = get_selection_string()

    if not resolved:
        if not click.confirm("No profiles will run. Continue anyway?", default=False):
            console.print("[yellow]Cancelled[/yellow]")
            return 1

    dotenv.set_key(
        dotenv_path=f"{DOTFILES_DIR}/.env",
        key_to_set=ENV_PROFILES_KEY,
        value_to_set=selection_str,
    )

    console.print(f"[green]Saved: DOTFILES_PROFILES={selection_str}[/green]")
    console.print(f"[dim]Will run: {', '.join(resolved)}[/dim]")
    return 0


def interactive_settings_config() -> int:
    """Interactive TUI for settings configuration.

    Allows toggling boolean settings like DOTFILES_NO_SYMLINK.

    Returns:
        Exit code (0 for success, 1 for cancelled)
    """
    import termios
    import tty

    # Define available settings
    # Format: (env_key, display_name, description, is_boolean)
    settings = [
        (
            ENV_NO_SYMLINK_KEY,
            "Disable symlink",
            "Don't create ~/.local/bin/dotfiles symlink",
            True,
        ),
    ]

    # Load current values
    current_values: dict[str, str | None] = {}
    for key, _, _, _ in settings:
        current_values[key] = get_setting_for_display(key)

    # Track modifications
    modified_values = current_values.copy()
    cursor_pos = 0

    def get_key() -> str:
        """Read a single keypress."""
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == "\x1b":
                ch += sys.stdin.read(2)
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    def is_truthy(value: str | None) -> bool:
        """Check if a value is truthy ('1', 'true', 'yes')."""
        if not value:
            return False
        return value.lower() in ("1", "true", "yes")

    def render() -> None:
        """Render the current state."""
        console.clear()

        console.print(
            Panel.fit(
                "[bold]Settings Configuration[/bold]\n"
                "[dim]Space: toggle, Enter: save, q: cancel[/dim]",
                border_style="blue",
            )
        )
        console.print()

        for i, (key, name, description, is_boolean) in enumerate(settings):
            cursor = "[bold cyan]>[/bold cyan] " if i == cursor_pos else "  "
            value = modified_values[key]

            if is_boolean:
                enabled = is_truthy(value)
                if enabled:
                    checkbox = "[green][X][/green]"
                    status = "[green]enabled[/green]"
                else:
                    checkbox = "[ ]"
                    status = "[dim]disabled[/dim]"
                console.print(f"{cursor}{checkbox} {name}: {status}")
                console.print(f"      [dim]{description}[/dim]")
            else:
                display_value = value if value else "[dim]not set[/dim]"
                console.print(f"{cursor}  {name}: {display_value}")
                console.print(f"      [dim]{description}[/dim]")

        console.print()

        # Show changes preview
        changes = []
        for key, _, _, _ in settings:
            old = current_values[key]
            new = modified_values[key]
            if old != new:
                if new is None:
                    changes.append(f"  [red]- {key}[/red]")
                elif old is None:
                    changes.append(f"  [green]+ {key}={new}[/green]")
                else:
                    changes.append(f"  [yellow]~ {key}: {old} → {new}[/yellow]")

        if changes:
            console.print(
                Panel.fit("\n".join(changes), title="Changes", border_style="yellow")
            )
        else:
            console.print(
                Panel.fit("[dim]No changes[/dim]", title="Changes", border_style="dim")
            )

    render()

    while True:
        key = get_key()

        if key == "q" or key == "\x03":
            console.clear()
            console.print("[yellow]Cancelled[/yellow]")
            return 1
        elif key == "\r" or key == "\n":
            break
        elif key == " ":
            setting_key, _, _, is_boolean = settings[cursor_pos]
            if is_boolean:
                current = modified_values[setting_key]
                if is_truthy(current):
                    modified_values[setting_key] = None
                else:
                    modified_values[setting_key] = "1"
        elif key == "\x1b[A":
            cursor_pos = max(0, cursor_pos - 1)
        elif key == "\x1b[B":
            cursor_pos = min(len(settings) - 1, cursor_pos + 1)

        render()

    console.clear()

    # Save changes
    changes_made = False
    for key, name, _, _ in settings:
        old = current_values[key]
        new = modified_values[key]
        if old != new:
            save_setting(key, new)
            changes_made = True
            if new is None:
                console.print(f"[red]Removed {key}[/red]")
            else:
                console.print(f"[green]Saved: {key}={new}[/green]")

    if not changes_made:
        console.print("[dim]No changes made[/dim]")

    return 0
