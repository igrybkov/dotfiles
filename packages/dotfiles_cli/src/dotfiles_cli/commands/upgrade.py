"""Upgrade command for updating dependencies."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

import ansible_runner
import click

from ..constants import DOTFILES_DIR
from ..profiles import get_profile_requirements_paths

# Prep stamp used by the bash wrapper to skip redundant preparation
PREP_STAMP = Path(DOTFILES_DIR) / ".cache" / ".prep_stamp"


def invalidate_prep_stamp() -> None:
    """Remove the prep stamp so the next wrapper invocation re-runs preparation."""
    try:
        PREP_STAMP.unlink(missing_ok=True)
    except OSError:
        pass


@click.command()
@click.option(
    "--no-uv",
    is_flag=True,
    default=False,
    help="Skip upgrading uv",
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
def upgrade(no_uv: bool, no_mise: bool, no_ansible_galaxy: bool):
    """Upgrade all dependencies including Ansible roles/collections, mise, and uv."""
    failed = False
    upgraded_items = []

    # Upgrade Ansible Galaxy roles and collections
    if not no_ansible_galaxy:
        click.echo("Upgrading Ansible roles and collections...")
        with TemporaryDirectory() as tmpdir:
            # Upgrade main requirements
            out, err, rc = ansible_runner.run_command(
                private_data_dir=tmpdir,
                project_dir=DOTFILES_DIR,
                envvars={"ANSIBLE_CONFIG": f"{DOTFILES_DIR}/ansible.cfg"},
                executable_cmd="ansible-galaxy",
                cmdline_args=[
                    "install",
                    "-r",
                    f"{DOTFILES_DIR}/requirements.yml",
                    "--force",
                ],
                quiet=False,
            )
            if rc != 0:
                click.echo(f"Error upgrading Ansible Galaxy: {err}", err=True)
                failed = True
            else:
                click.echo("✓ Ansible roles and collections upgraded")
                upgraded_items.append("Ansible roles/collections")

            # Upgrade profile-specific requirements
            profile_requirements = get_profile_requirements_paths()
            for req_file in profile_requirements:
                out, err, rc = ansible_runner.run_command(
                    private_data_dir=tmpdir,
                    project_dir=DOTFILES_DIR,
                    envvars={"ANSIBLE_CONFIG": f"{DOTFILES_DIR}/ansible.cfg"},
                    executable_cmd="ansible-galaxy",
                    cmdline_args=[
                        "install",
                        "-r",
                        req_file,
                        "--force",
                    ],
                    quiet=False,
                )
                if rc != 0:
                    click.echo(
                        f"Error upgrading profile Galaxy deps ({req_file}): {err}",
                        err=True,
                    )
                    failed = True
    else:
        click.echo("Skipping Ansible Galaxy upgrade (--no-ansible-galaxy)")

    # Upgrade mise
    if not no_mise:
        click.echo("Upgrading mise...")
        mise_cmd = shutil.which("mise")
        if mise_cmd:
            try:
                result = subprocess.run(
                    [mise_cmd, "upgrade"],
                    cwd=DOTFILES_DIR,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if result.returncode != 0:
                    click.echo(f"Error upgrading mise: {result.stderr}", err=True)
                    failed = True
                else:
                    click.echo("✓ mise upgraded")
                    upgraded_items.append("mise")

                    # Run mise lock after upgrade
                    click.echo("Updating mise lock file...")
                    lock_result = subprocess.run(
                        [mise_cmd, "lock"],
                        cwd=DOTFILES_DIR,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    if lock_result.returncode != 0:
                        click.echo(
                            f"Warning: mise lock failed: {lock_result.stderr}",
                            err=True,
                        )
                    else:
                        click.echo("✓ mise lock file updated")
            except Exception as e:
                click.echo(f"Error upgrading mise: {e}", err=True)
                failed = True
        else:
            click.echo("mise not found in PATH, skipping", err=True)
            failed = True
    else:
        click.echo("Skipping mise upgrade (--no-mise)")

    # Upgrade uv
    if not no_uv:
        click.echo("Upgrading uv...")
        mise_cmd = shutil.which("mise")
        uv_upgraded = False
        if mise_cmd:
            try:
                result = subprocess.run(
                    [mise_cmd, "x", "--", "uv", "self", "update"],
                    cwd=DOTFILES_DIR,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if result.returncode == 0:
                    click.echo("✓ uv upgraded")
                    uv_upgraded = True
                    upgraded_items.append("uv")
            except Exception as e:
                click.echo(f"Error upgrading uv via mise: {e}", err=True)

        if not uv_upgraded:
            uv_cmd = shutil.which("uv")
            if uv_cmd:
                try:
                    result = subprocess.run(
                        [uv_cmd, "self", "update"],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    if result.returncode == 0:
                        click.echo("✓ uv upgraded")
                        uv_upgraded = True
                        upgraded_items.append("uv")
                    elif (
                        "Self-update is only available for uv binaries installed via the standalone installation scripts"
                        in result.stderr
                    ):
                        click.echo(
                            "ℹ uv self-update not available (installed via package manager), skipping"
                        )
                    else:
                        click.echo(
                            f"Warning: uv self-update failed: {result.stderr}", err=True
                        )
                except Exception as e:
                    click.echo(f"Warning: Error upgrading uv: {e}", err=True)
            else:
                click.echo("uv not found in PATH, skipping", err=True)
                failed = True

        if uv_upgraded or shutil.which("uv"):
            click.echo("Upgrading Python dependencies with uv...")
            sync_success = False
            if mise_cmd:
                try:
                    sync_result = subprocess.run(
                        [mise_cmd, "x", "--", "uv", "sync", "--upgrade"],
                        cwd=DOTFILES_DIR,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    if sync_result.returncode == 0:
                        click.echo("✓ Python dependencies upgraded")
                        sync_success = True
                    else:
                        click.echo(
                            f"Warning: uv sync --upgrade failed: {sync_result.stderr}",
                            err=True,
                        )
                except Exception as e:
                    click.echo(f"Error running uv sync via mise: {e}", err=True)

            if not sync_success:
                uv_cmd = shutil.which("uv")
                if uv_cmd:
                    try:
                        sync_result = subprocess.run(
                            [uv_cmd, "sync", "--upgrade"],
                            cwd=DOTFILES_DIR,
                            capture_output=True,
                            text=True,
                            check=False,
                        )
                        if sync_result.returncode == 0:
                            click.echo("✓ Python dependencies upgraded")
                        else:
                            click.echo(
                                f"Warning: uv sync --upgrade failed: {sync_result.stderr}",
                                err=True,
                            )
                    except Exception as e:
                        click.echo(f"Error running uv sync: {e}", err=True)
    else:
        click.echo("Skipping uv upgrade (--no-uv)")

    # Invalidate prep stamp so next wrapper invocation re-runs preparation
    invalidate_prep_stamp()

    if failed:
        return 1

    if upgraded_items:
        click.echo(f"\n✓ Successfully upgraded: {', '.join(upgraded_items)}")
    else:
        click.echo("\n✓ No upgrades performed (all were skipped)")
    return 0
