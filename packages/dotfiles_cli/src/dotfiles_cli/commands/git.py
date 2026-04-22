"""Git-related commands (pull, push, sync)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import click

from ..constants import DOTFILES_DIR
from ..profiles import get_all_repo_statuses
from ..profiles.git import (
    SyncResult,
    _pull_with_summary,
    _push_with_summary,
    _sync_single_repo,
    get_profile_repos,
)


def _print_sync_summaries(action: str, results: list[SyncResult]) -> None:
    """Print the commits and file-change stats captured during a sync."""
    to_print = [r for r in results if r.success and r.commits]
    if not to_print:
        return

    heading = "Pulled:" if action == "pull" else "Pushed:"
    click.echo("")
    click.echo(click.style(heading, bold=True))
    for i, result in enumerate(to_print):
        if i > 0:
            click.echo("")
        click.echo(f"  {click.style(result.display_name, bold=True)}")
        for line in result.commits.splitlines():
            click.echo(f"    {line}")
        if result.stat:
            click.echo("")
            for line in result.stat.splitlines():
                click.echo(f"    {line}")


def _sync_all_repos(action: str) -> bool:
    """Run git action on main repo and all profile repos in parallel.

    Args:
        action: Either "pull" or "push"

    Returns:
        True if all repos synced successfully, False otherwise
    """
    repos = get_profile_repos()
    profiles_dir = Path(DOTFILES_DIR) / "profiles"
    main_repo = Path(DOTFILES_DIR)

    async def run_all() -> tuple[bool, list[SyncResult]]:
        if action == "pull":
            main_task = _pull_with_summary(main_repo, "dotfiles")
        else:
            main_task = _push_with_summary(main_repo, "dotfiles", "main")

        profile_tasks = [
            _sync_single_repo(action, repo, profiles_dir) for repo in repos
        ]

        results: list[SyncResult] = list(
            await asyncio.gather(main_task, *profile_tasks)
        )
        return all(r.success for r in results), results

    success, results = asyncio.run(run_all())
    _print_sync_summaries(action, results)
    return success


@click.command()
def pull():
    """Pull the latest changes from the remote repository."""
    _sync_all_repos("pull")


@click.command()
def push():
    """Push the latest changes to the remote repository."""
    _sync_all_repos("push")


def _print_status():
    """Check and display git status for all repositories."""
    statuses = get_all_repo_statuses()

    for status in statuses:
        parts = []

        # Branch
        parts.append(status.branch)

        # Sync status
        sync_parts = []
        if not status.has_remote:
            sync_parts.append("no remote")
        else:
            if status.ahead:
                sync_parts.append(f"{status.ahead} ahead")
            if status.behind:
                sync_parts.append(f"{status.behind} behind")
        if sync_parts:
            parts.append(", ".join(sync_parts))

        # Working tree status
        change_parts = []
        if status.staged:
            change_parts.append(f"{status.staged} staged")
        if status.modified:
            change_parts.append(f"{status.modified} modified")
        if status.untracked:
            change_parts.append(f"{status.untracked} untracked")
        if change_parts:
            parts.append(", ".join(change_parts))

        # Status indicator
        if status.dirty or status.ahead:
            indicator = click.style("*", fg="yellow")
        else:
            indicator = click.style("ok", fg="green")

        name = click.style(status.name, bold=True)
        detail = " | ".join(parts)
        click.echo(f"  {indicator} {name}: {detail}")

        if status.last_commit:
            commit_msg = status.last_commit[:60]
            if len(status.last_commit) > 60:
                commit_msg += "..."
            click.echo(f"      last: {commit_msg}")


@click.command()
@click.option(
    "--status", "show_status", is_flag=True, help="Show git status for all repos."
)
def sync(show_status):
    """Pull the latest changes and then push local changes."""
    if show_status:
        _print_status()
        return

    # Pull all repos in parallel
    if not _sync_all_repos("pull"):
        click.echo("Warning: some repos failed to pull", err=True)
        return 1

    # Push all repos in parallel
    if not _sync_all_repos("push"):
        click.echo("Warning: some repos failed to push", err=True)
        return 1

    return 0
