"""Git-related commands (pull, push, sync)."""

from __future__ import annotations

import subprocess

import click

from ..profiles import sync_profile_repos


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


@click.command()
def sync():
    """Pull the latest changes and then push local changes."""
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
