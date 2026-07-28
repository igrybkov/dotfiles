"""Install command for running the pyinfra deploy."""

from __future__ import annotations

import getpass
import os
import shlex
import shutil
import subprocess
import threading
from contextlib import contextmanager
from pathlib import Path

import click
from click import Context
from click.shell_completion import CompletionItem

from ..constants import (
    DOTFILES_DIR,
    LOGFILE_AUTO,
    SUDO_TAGS,
    VAULT_TAGS,
    get_env_file,
)
from ..profiles import (
    get_active_profiles,
    get_all_profile_names,
    get_repos_with_unpushed_changes,
    parse_profile_selection,
)
from ..types import ansible_tags_type
from ..utils import (
    SudoKeepAlive,
    cleanup_old_logs,
    generate_logfile_name,
    send_notification,
    validate_sudo_password,
)

try:
    from ..vault.age import read_age_key
except ImportError:

    def read_age_key() -> str | None:
        return None


_SUDO_PROMPT_NOTIFICATION_DELAY = 60


@contextmanager
def _notify_on_idle_prompt(
    title: str, message: str, delay: int = _SUDO_PROMPT_NOTIFICATION_DELAY
):
    """Send a notification if a password prompt is idle for too long."""
    timer = threading.Timer(delay, send_notification, args=[title, message])
    timer.daemon = True
    timer.start()
    try:
        yield
    finally:
        timer.cancel()


def complete_profiles(
    ctx: Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    """Shell completion for profile names.

    Supports:
    - Simple profile names: common, work
    - Comma-separated: common,work (completes after last comma)
    - Exclusions: -work, all,-personal (completes with - prefix)
    """
    profiles = get_all_profile_names()

    # Handle comma-separated completion
    if "," in incomplete:
        prefix, _, current = incomplete.rpartition(",")
        prefix += ","  # Include the comma in prefix
    else:
        prefix = ""
        current = incomplete

    # Handle exclusion prefix
    if current.startswith("-"):
        profile_prefix = "-"
        current = current[1:]
    else:
        profile_prefix = ""

    # Filter profiles matching current input
    completions = []
    for profile in profiles:
        if profile.startswith(current):
            completions.append(CompletionItem(f"{prefix}{profile_prefix}{profile}"))

    # Also add "all" as an option if it matches
    if "all".startswith(current) and profile_prefix == "":
        completions.append(CompletionItem(f"{prefix}all"))

    return completions


@click.command("install")
@click.argument(
    "tag",
    nargs=-1,
    type=ansible_tags_type,
)
@click.option(
    "--profile",
    "-p",
    envvar="DOTFILES_PROFILES",
    multiple=True,
    shell_complete=complete_profiles,
    help="Profile selection (e.g., '-p common -p work' or '-p common,work')",
)
@click.option("--all", "-a", default=False, is_flag=True)
@click.option("-v", "--verbose", count=True, default=0)
@click.option(
    "--logfile",
    "-l",
    default=None,
    help="Write output to log file (default: dotfiles-run-YYYYMMDD-HHMMSS.log)",
)
@click.option(
    "--sync",
    "run_sync",
    default=False,
    is_flag=True,
    help="Run sync (pull, upgrade, push) before executing the playbook",
)
@click.option(
    "--dry-run",
    "--check",
    "dry_run",
    default=False,
    is_flag=True,
    help="Run playbook in check mode (dry run, no changes made)",
)
@click.pass_context
def install(
    ctx: Context,
    logfile: str | None = None,
    tag: list[str] | None = None,
    profile: tuple[str, ...] = (),
    verbose: int = 0,
    all: bool = False,
    run_sync: bool = False,
    dry_run: bool = False,
) -> int | None:
    """Run the pyinfra deploy to install dotfiles."""
    from .git import sync

    # Run sync before playbook if --sync flag is set
    if run_sync:
        click.echo("Running sync before install...")
        sync_result = ctx.invoke(sync)
        if sync_result != 0:
            click.echo("Error: sync failed, aborting install", err=True)
            return sync_result
        click.echo("Sync completed successfully\n")

    # Clean up old log files before starting
    cleanup_old_logs(keep_count=5, adds_new_log=logfile is not None)

    # Run interactive config if .env doesn't exist and no explicit profile selection
    if not get_env_file().exists() and not profile:
        from .config import config

        click.echo("No configuration found. Running initial setup...\n")
        config_result = ctx.invoke(config)
        if config_result != 0:
            return config_result
        click.echo()

    tags: list[str] = list(tag) if tag else []
    if all:
        tags = list(set(tags + ["all"]))
    elif len(tags) == 0:
        tags = ["all"]

    available_profiles = get_all_profile_names()

    # Always resolve the full enabled set (used by all_profiles=True lookups in Ansible)
    all_enabled_selection = get_active_profiles()
    all_enabled_profiles = all_enabled_selection.resolve(available_profiles)

    if profile:
        # Join multiple -p flags with commas (e.g., -p common -p work -> "common,work")
        profiles_str = ",".join(profile)
        selection = parse_profile_selection(profiles_str)
    else:
        selection = all_enabled_selection

    active_profiles = selection.resolve(available_profiles)

    if not all_enabled_profiles:
        all_enabled_profiles = active_profiles

    if not active_profiles:
        click.echo(
            f"No profiles configured. Run 'dotfiles config' to select profiles, or use --profile flag. Available: {', '.join(available_profiles)}"
        )
        return 1

    # Create symlink to ~/.local/bin/dotfiles (respects DOTFILES_NO_SYMLINK)
    from .link import link

    ctx.invoke(link, quiet=True)

    # Install mise-managed tools from lockfile
    mise_cmd = shutil.which("mise")
    if mise_cmd:
        result = subprocess.run(
            [mise_cmd, "install"],
            cwd=DOTFILES_DIR,
            check=False,
        )
        if result.returncode != 0:
            click.echo("Warning: mise install failed", err=True)
    else:
        click.echo("Warning: mise not found in PATH", err=True)

    # Homebrew bootstrap (must happen before pyinfra reads brew facts).
    # Skipped when a marker file exists (e.g. CI / non-macOS environments).
    if (
        not shutil.which("brew")
        and not (Path(DOTFILES_DIR) / ".cache" / "skip-homebrew").exists()
    ):
        click.echo("Installing Homebrew...")
        result = subprocess.run(
            [
                "/bin/bash",
                "-c",
                "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)",
            ],
            check=False,
        )
        if result.returncode != 0:
            click.echo("Warning: Homebrew install failed", err=True)

    # Prompt for the sudo password when any selected tag needs root. The
    # password only primes the OS sudo ticket cache (via `sudo -S -v`) — it is
    # never passed to pyinfra or held beyond this block. A background thread
    # then refreshes that same ticket for the life of the deploy so it can't
    # expire mid-run (see SudoKeepAlive).
    sudo_keepalive: SudoKeepAlive | None = None
    become_password: str | None = None
    if set(tags) & SUDO_TAGS or "all" in tags:
        max_attempts = 3

        for attempt in range(1, max_attempts + 1):
            try:
                with _notify_on_idle_prompt(
                    "Dotfiles: Sudo Required",
                    "Waiting for sudo password...",
                ):
                    become_password = getpass.getpass("SUDO password: ")
            except (KeyboardInterrupt, EOFError):
                click.echo("\nError: Password prompt cancelled.", err=True)
                return 1

            if not become_password:
                click.echo("Error: Password cannot be empty.", err=True)
                if attempt < max_attempts:
                    continue
                return 1

            click.echo("Validating sudo password...")
            if validate_sudo_password(become_password):
                click.echo("✓ Sudo password validated")
                break
            else:
                remaining = max_attempts - attempt
                if remaining > 0:
                    click.echo(
                        f"Error: Invalid sudo password. {remaining} attempt{'s' if remaining > 1 else ''} remaining.",
                        err=True,
                    )
                else:
                    click.echo(
                        "Error: Invalid sudo password. No attempts remaining.",
                        err=True,
                    )
                    return 1

        become_password = None
        sudo_keepalive = SudoKeepAlive()
        sudo_keepalive.start()

    # Read the age private key when secret-sensitive tags are selected.
    sops_age_key = None
    if set(tags) & VAULT_TAGS or "all" in tags:
        sops_age_key = read_age_key()
        if sops_age_key is None:
            click.echo(
                "Warning: No age key found. Run 'dotfiles secret init' first. Continuing without secret decryption.",
                err=True,
            )

    # Build the environment for the pyinfra subprocess. The deploy's
    # inventory.py reads these env vars (never argv) to select profiles,
    # tags, and the age key. The sudo password is deliberately not included —
    # pyinfra relies on the OS sudo ticket kept warm by `sudo_keepalive` above.
    env = dict(os.environ)
    env["DOTFILES_SELECTED_PROFILES"] = ",".join(active_profiles)
    env["DOTFILES_ENABLED_PROFILES"] = ",".join(all_enabled_profiles)
    env["DOTFILES_TAGS"] = ",".join(tags)
    if sops_age_key:
        env["SOPS_AGE_KEY"] = sops_age_key

    # Find pyinfra — prefer `mise x -- pyinfra`, fall back to PATH.
    if mise_cmd:
        cmd = [mise_cmd, "x", "--", "pyinfra", "deploy/inventory.py", "deploy/site.py"]
    else:
        pyinfra_cmd = shutil.which("pyinfra")
        if not pyinfra_cmd:
            click.echo("Error: pyinfra not found. Run 'mise install'.", err=True)
            return 1
        cmd = [pyinfra_cmd, "deploy/inventory.py", "deploy/site.py"]

    if dry_run:
        cmd.append("--dry")
        click.echo("Running in dry-run mode (no changes will be made)")

    # Verbosity: pyinfra uses -v/-vv/-vvv.
    if verbose > 0:
        cmd.append("-" + "v" * verbose)

    click.echo(f"Running with profiles: {', '.join(active_profiles)}")

    if logfile == LOGFILE_AUTO:
        logfile = generate_logfile_name()

    try:
        if logfile:
            # Tee pyinfra output to both the terminal and the log file.
            # `set -o pipefail` makes the pipeline exit status reflect pyinfra's
            # rc rather than tee's, so a failed deploy is reported correctly.
            tee_cmd = (
                "set -o pipefail; "
                + " ".join(shlex.quote(c) for c in cmd)
                + " 2>&1 | tee "
                + shlex.quote(logfile)
            )
            result = subprocess.run(["bash", "-c", tee_cmd], cwd=DOTFILES_DIR, env=env)
            click.echo(f"\nLog file: {logfile}")
        else:
            result = subprocess.run(cmd, cwd=DOTFILES_DIR, env=env)
    finally:
        if sudo_keepalive:
            sudo_keepalive.stop()

    exit_code = result.returncode

    # Send notification after the deploy completes.
    if exit_code == 0:
        send_notification("Dotfiles: Complete", "Successfully set up environment.")
    else:
        send_notification("Dotfiles: Failed", f"Failed with exit code {exit_code}")

    # Warn about uncommitted/unpushed changes at the end for visibility.
    uncommitted, unpushed = get_repos_with_unpushed_changes()
    if uncommitted or unpushed:
        # Collect all unique repos with their issues
        all_repos = sorted(set(uncommitted) | set(unpushed))
        click.echo(
            click.style("\nWarning: ", fg="yellow", bold=True)
            + "Unsaved changes detected:"
        )
        for repo in all_repos:
            issues = []
            if repo in uncommitted:
                issues.append("uncommitted")
            if repo in unpushed:
                issues.append("unpushed")
            click.echo(click.style(f"  - {repo} ({', '.join(issues)})", fg="yellow"))

    return exit_code
