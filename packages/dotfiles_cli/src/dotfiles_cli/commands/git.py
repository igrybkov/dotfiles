"""Git-related commands (pull, push, sync)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import click

from ..constants import DOTFILES_DIR
from ..profiles import get_all_repo_statuses
from ..profiles.git import _run_git_command, _sync_single_repo, get_profile_repos


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

    async def run_all() -> bool:
        # Build tasks for all repos (main + profiles)
        tasks = []

        # Main repo task
        if action == "pull":
            click.echo("Pulling dotfiles...")
            tasks.append(_run_git_command(["git", "pull"], main_repo))
        else:
            click.echo("Pushing dotfiles...")
            tasks.append(_run_git_command(["git", "push", "origin", "main"], main_repo))

        # Profile repo tasks
        profile_tasks = [
            _sync_single_repo(action, repo, profiles_dir) for repo in repos
        ]

        # Run main repo and all profile repos concurrently
        main_result, *profile_results = await asyncio.gather(tasks[0], *profile_tasks)

        success = True
        if main_result.returncode != 0:
            click.echo(f"Error: git {action} failed for dotfiles", err=True)
            if main_result.stderr.strip():
                click.echo(f"  {main_result.stderr.strip()}", err=True)
            success = False

        for _, profile_ok in profile_results:
            if not profile_ok:
                success = False

        return success

    return asyncio.run(run_all())


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
