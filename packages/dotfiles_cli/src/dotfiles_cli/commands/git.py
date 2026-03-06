"""Git-related commands (pull, push, sync)."""

from __future__ import annotations

import subprocess

import click

from ..profiles import get_all_repo_statuses, sync_profile_repos


@click.command()
def pull():
    """Pull the latest changes from the remote repository."""
    subprocess.call(["git", "pull"])
    # Also pull profile repos (if they are git repositories)
    sync_profile_repos("pull")


@click.command()
def push():
    """Push the latest changes to the remote repository."""
    subprocess.call(["git", "push", "origin", "main"])
    # Also push profile repos (if they are git repositories)
    sync_profile_repos("push")


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

    # Pull latest changes from main repo
    pull_result = subprocess.call(["git", "pull"])
    if pull_result != 0:
        click.echo("Error: git pull failed", err=True)
        return pull_result

    # Pull profile repos (if they are git repositories)
    if not sync_profile_repos("pull"):
        click.echo("Warning: some profile repos failed to pull", err=True)

    # Push changes to main repo
    push_result = subprocess.call(["git", "push", "origin", "main"])
    if push_result != 0:
        click.echo("Error: git push failed", err=True)
        return push_result

    # Push profile repos (if they are git repositories)
    if not sync_profile_repos("push"):
        click.echo("Warning: some profile repos failed to push", err=True)

    return 0
