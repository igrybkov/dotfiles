"""Install command for running Ansible playbook."""

from __future__ import annotations

import getpass
from pathlib import Path
from tempfile import TemporaryDirectory

import ansible_runner
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
    get_profile_requirements_paths,
    get_profile_roles_paths,
    get_repos_with_unpushed_changes,
    parse_profile_selection,
)
from ..types import ansible_tags_type
from ..utils import (
    cleanup_old_logs,
    generate_logfile_name,
    send_notification,
    validate_sudo_password,
)
from ..vault import (
    ensure_vault_password_permissions,
    get_profiles_with_secrets,
    get_vault_password_file,
    validate_vault_password,
)


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
    help="Write output to log file (default: ansible-run-YYYYMMDD-HHMMSS.log)",
)
@click.option(
    "--timing",
    default=False,
    is_flag=True,
    help="Enable Ansible timing/profiling callbacks (timer, profile_tasks, profile_roles)",
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
    tag: list[str] = None,
    profile: tuple[str, ...] = (),
    verbose: int = 0,
    all: bool = False,
    timing: bool = False,
    run_sync: bool = False,
    dry_run: bool = False,
) -> int | None:
    """Run ansible playbook to install dotfiles."""
    from .git import sync

    # Run sync before playbook if --sync flag is set
    if run_sync:
        click.echo("Running sync before install...")
        sync_result = ctx.invoke(
            sync, uv=False, no_mise=False, no_ansible_galaxy=False, skip_upgrade=False
        )
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

    if profile:
        # Join multiple -p flags with commas (e.g., -p common -p work -> "common,work")
        profiles_str = ",".join(profile)
        selection = parse_profile_selection(profiles_str)
    else:
        selection = get_active_profiles()

    active_profiles = selection.resolve(available_profiles)

    if not active_profiles:
        click.echo(
            "No profiles configured. Run 'dotfiles config' to select profiles, "
            f"or use --profile flag. Available: {', '.join(available_profiles)}"
        )
        return 1

    # Create symlink to ~/.local/bin/dotfiles (respects DOTFILES_NO_SYMLINK)
    from .link import link

    ctx.invoke(link, quiet=True)

    with TemporaryDirectory() as tmpdir:
        # Install Ansible dependencies from main requirements
        ansible_runner.run_command(
            private_data_dir=tmpdir,
            project_dir=DOTFILES_DIR,
            envvars={"ANSIBLE_CONFIG": f"{DOTFILES_DIR}/ansible.cfg"},
            executable_cmd="ansible-galaxy",
            cmdline_args=["install", "-r", f"{DOTFILES_DIR}/requirements.yml"],
            quiet=False,
        )

        # Install profile-specific Galaxy requirements
        profile_requirements = get_profile_requirements_paths()
        for req_file in profile_requirements:
            ansible_runner.run_command(
                private_data_dir=tmpdir,
                project_dir=DOTFILES_DIR,
                envvars={"ANSIBLE_CONFIG": f"{DOTFILES_DIR}/ansible.cfg"},
                executable_cmd="ansible-galaxy",
                cmdline_args=["install", "-r", req_file],
                quiet=False,
            )

        envvars = {"ANSIBLE_CONFIG": f"{DOTFILES_DIR}/ansible.cfg"}

        profile_roles = get_profile_roles_paths()
        if profile_roles:
            default_roles_path = f"{DOTFILES_DIR}/roles"
            envvars["ANSIBLE_ROLES_PATH"] = ":".join(
                profile_roles + [default_roles_path]
            )

        if timing:
            envvars["ANSIBLE_CALLBACKS_ENABLED"] = "timer,profile_tasks,profile_roles"

        if set(tags) & SUDO_TAGS or "all" in tags:
            max_attempts = 3
            become_password = None

            for attempt in range(1, max_attempts + 1):
                try:
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
                            f"Error: Invalid sudo password. {remaining} "
                            f"attempt{'s' if remaining > 1 else ''} remaining.",
                            err=True,
                        )
                    else:
                        click.echo(
                            "Error: Invalid sudo password. No attempts remaining.",
                            err=True,
                        )
                        return 1

            envvars["ANSIBLE_BECOME_PASS"] = become_password

        if logfile == LOGFILE_AUTO:
            logfile = generate_logfile_name()
        log_file_handle = None
        event_handler = None
        if logfile is not None:
            log_file_handle = open(logfile, "w")

            def event_handler(event: dict) -> None:
                if "stdout" in event:
                    log_file_handle.write(event["stdout"] + "\n")
                    log_file_handle.flush()
                if "stderr" in event:
                    log_file_handle.write(event["stderr"] + "\n")
                    log_file_handle.flush()

        try:
            cmdline_args = []

            if dry_run:
                cmdline_args.append("--check")
                click.echo("Running in dry-run mode (no changes will be made)")

            vault_pass_file = Path(DOTFILES_DIR) / ".vault_password"
            needs_vault_password = len(set(tags) & VAULT_TAGS) > 0 or "all" in tags

            vault_passwords: dict[str, str] = {}
            vault_pass_files: dict[str, Path] = {}

            if needs_vault_password:
                vault_password = None
                if vault_pass_file.exists():
                    ensure_vault_password_permissions(vault_pass_file)
                    vault_password = vault_pass_file.read_text().strip()
                else:
                    try:
                        vault_password = getpass.getpass("Vault password: ")
                        if not vault_password:
                            click.echo(
                                "Error: Vault password cannot be empty.", err=True
                            )
                            return 1
                    except (KeyboardInterrupt, EOFError):
                        click.echo(
                            "\nError: Vault password prompt cancelled.", err=True
                        )
                        return 1

                    envvars["ANSIBLE_VAULT_PASSWORD"] = vault_password

                vault_passwords["default"] = vault_password

                click.echo("Validating vault password...")
                if not validate_vault_password(vault_password):
                    click.echo(
                        "Error: Invalid vault password. Please check your password and try again.",
                        err=True,
                    )
                    return 1
                click.echo("✓ Vault password validated")

                profiles_with_secrets = get_profiles_with_secrets()
                for profile in profiles_with_secrets:
                    profile_pass_file = get_vault_password_file(profile)
                    if profile_pass_file.exists():
                        ensure_vault_password_permissions(profile_pass_file)
                        vault_passwords[profile] = profile_pass_file.read_text().strip()
                    else:
                        try:
                            profile_pass = getpass.getpass(
                                f"Vault password for profile '{profile}': "
                            )
                            if profile_pass:
                                vault_passwords[profile] = profile_pass
                        except (KeyboardInterrupt, EOFError):
                            click.echo(
                                f"\nWarning: Skipping vault password for profile '{profile}'",
                                err=True,
                            )

                for vault_id, password in vault_passwords.items():
                    pass_file = Path(tmpdir) / f"vault_pass_{vault_id}"
                    pass_file.write_text(password)
                    pass_file.chmod(0o600)
                    vault_pass_files[vault_id] = pass_file
                    cmdline_args.extend(["--vault-id", f"{vault_id}@{pass_file}"])

            # Include localhost for Bootstrap and Finalize plays
            # Convert hyphens to underscores for Ansible group names (Ansible doesn't allow hyphens in group names)
            limit_profiles = [p.replace("-", "_") for p in active_profiles]
            limit_str = ",".join(limit_profiles + ["localhost"])
            click.echo(f"Running with profiles: {', '.join(active_profiles)}")

            r = ansible_runner.run(
                private_data_dir=tmpdir,
                project_dir=DOTFILES_DIR,
                envvars=envvars,
                playbook="playbook.yml",
                limit=limit_str,
                tags=",".join(tags) if tags else None,
                verbosity=verbose,
                quiet=False,
                event_handler=event_handler,
                cmdline=" ".join(cmdline_args) if cmdline_args else None,
            )
        finally:
            if log_file_handle:
                log_file_handle.close()

        if logfile is not None:
            click.echo(f"\nLog file: {logfile}")

        exit_code = r.rc if r.rc else 0

        # Send notification after playbook completes
        if exit_code == 0:
            send_notification("Dotfiles: Complete", "Successfully set up environment.")
        else:
            send_notification("Dotfiles: Failed", f"Failed with exit code {exit_code}")

        # Warn about uncommitted/unpushed changes at the end for visibility
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
                click.echo(
                    click.style(f"  - {repo} ({', '.join(issues)})", fg="yellow")
                )

        return exit_code
