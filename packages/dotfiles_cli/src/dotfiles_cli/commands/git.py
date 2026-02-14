"""Git-related commands (pull, push, sync)."""

from __future__ import annotations

import subprocess

import click
from click import Context

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
@click.option(
    "--uv/--no-uv",
    is_flag=True,
    default=False,
    help="Upgrade uv (disabled by default)",
)
@click.option(
    "--no-mise",
    is_flag=True,
    default=False,
    help="Skip upgrading mise",
)
@click.option(
    "--no-ansible-galaxy",
    is_flag=True,
    default=False,
    help="Skip upgrading Ansible roles and collections",
)
@click.option(
    "--skip-upgrade",
    is_flag=True,
    default=False,
    help="Skip running upgrade command",
)
@click.pass_context
def sync(
    ctx: Context,
    uv: bool,
    no_mise: bool,
    no_ansible_galaxy: bool,
    skip_upgrade: bool,
):
    """Pull the latest changes, upgrade dependencies, and then push local changes."""
    from .upgrade import upgrade

    # Pull latest changes from main repo
    pull_result = subprocess.call(["git", "pull"])
    if pull_result != 0:
        click.echo("Error: git pull failed", err=True)
        return pull_result

    # Pull profile repos (if they are git repositories)
    if not sync_profile_repos("pull"):
        click.echo("Warning: some profile repos failed to pull", err=True)

    # Run upgrade unless skipped
    if not skip_upgrade:
        upgrade_result = ctx.invoke(
            upgrade, no_uv=not uv, no_mise=no_mise, no_ansible_galaxy=no_ansible_galaxy
        )
        if upgrade_result != 0:
            click.echo(
                "Warning: upgrade encountered errors, continuing with sync", err=True
            )

    # Push changes to main repo
    push_result = subprocess.call(["git", "push", "origin", "main"])
    if push_result != 0:
        click.echo("Error: git push failed", err=True)
        return push_result

    # Push profile repos (if they are git repositories)
    if not sync_profile_repos("push"):
        click.echo("Warning: some profile repos failed to push", err=True)

    return 0
