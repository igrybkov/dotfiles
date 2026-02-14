"""Cache management commands."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from ..constants import DOTFILES_DIR

console = Console()

# Known cache markers with descriptions
CACHE_MARKERS = {
    "skip-homebrew": "Skip geerlingguy.mac.homebrew role (slow ownership check)",
    "skip-macos": "Skip macos role (system preferences)",
}


def get_cache_dir() -> Path:
    """Get the cache directory path."""
    return Path(DOTFILES_DIR) / ".cache"


def get_marker_path(marker: str) -> Path:
    """Get the path to a specific marker file."""
    return get_cache_dir() / marker


@click.group()
def cache():
    """Manage dotfiles cache markers.

    Cache markers allow skipping slow-running roles that rarely change.
    Markers are created automatically after successful role execution.

    \b
    Available markers:
      skip-homebrew  Skip Homebrew installation role (~17s)
      skip-macos     Skip macOS system preferences role (~8s)
    """
    pass


@cache.command("list")
def cache_list():
    """List all cache markers and their status."""
    cache_dir = get_cache_dir()

    table = Table(title="Cache Markers", show_header=True, header_style="bold")
    table.add_column("Status", justify="center", width=6)
    table.add_column("Marker", style="cyan")
    table.add_column("Description", style="dim")

    for marker, description in CACHE_MARKERS.items():
        marker_path = cache_dir / marker
        exists = marker_path.exists()
        status = "[green]✓[/green]" if exists else "[dim]○[/dim]"
        table.add_row(status, marker, description)

    console.print(table)

    # Also show other cache files
    if cache_dir.exists():
        other_files = [
            f.name
            for f in cache_dir.iterdir()
            if f.is_file() and f.name not in CACHE_MARKERS
        ]
        if other_files:
            console.print("\n[dim]Other cache files:[/dim]")
            for f in sorted(other_files):
                console.print(f"  [dim]{f}[/dim]")


@cache.command("clear")
@click.argument("markers", nargs=-1)
@click.option(
    "--all",
    "-a",
    "clear_all",
    is_flag=True,
    default=False,
    help="Clear all cache markers",
)
def cache_clear(markers: tuple[str, ...], clear_all: bool):
    """Clear cache markers to force roles to run again.

    \b
    Examples:
      dotfiles cache clear skip-homebrew    Clear homebrew marker
      dotfiles cache clear skip-macos       Clear macos marker
      dotfiles cache clear --all            Clear all markers
    """
    if not markers and not clear_all:
        console.print("[yellow]Specify markers to clear or use --all[/yellow]")
        console.print("\nAvailable markers:")
        for marker, description in CACHE_MARKERS.items():
            console.print(f"  [cyan]{marker}[/cyan] - {description}")
        raise SystemExit(1)

    if clear_all:
        markers = tuple(CACHE_MARKERS.keys())

    cleared = []
    not_found = []

    for marker in markers:
        if marker not in CACHE_MARKERS:
            console.print(f"[yellow]Unknown marker: {marker}[/yellow]")
            continue

        marker_path = get_marker_path(marker)
        if marker_path.exists():
            marker_path.unlink()
            cleared.append(marker)
        else:
            not_found.append(marker)

    if cleared:
        console.print(f"[green]Cleared:[/green] {', '.join(cleared)}")
    if not_found:
        console.print(f"[dim]Already cleared:[/dim] {', '.join(not_found)}")


@cache.command("create")
@click.argument("markers", nargs=-1, required=True)
def cache_create(markers: tuple[str, ...]):
    """Manually create cache markers to skip roles.

    \b
    Examples:
      dotfiles cache create skip-homebrew   Skip homebrew role on next run
      dotfiles cache create skip-macos      Skip macos role on next run
    """
    cache_dir = get_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)

    created = []
    already_exists = []

    for marker in markers:
        if marker not in CACHE_MARKERS:
            console.print(f"[yellow]Unknown marker: {marker}[/yellow]")
            continue

        marker_path = get_marker_path(marker)
        if marker_path.exists():
            already_exists.append(marker)
        else:
            marker_path.touch()
            created.append(marker)

    if created:
        console.print(f"[green]Created:[/green] {', '.join(created)}")
    if already_exists:
        console.print(f"[dim]Already exists:[/dim] {', '.join(already_exists)}")
