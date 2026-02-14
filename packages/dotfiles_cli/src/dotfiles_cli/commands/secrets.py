"""Secrets management commands."""

from __future__ import annotations

import getpass
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import click
import dotenv
import yaml

from ..constants import (
    DOTFILES_DIR,
    get_vault_password_file as get_global_vault_password_file,
)
from ..profiles import get_profile_names
from ..utils import fzf_select, numbered_select
from ..vault import (
    get_all_secret_locations,
    get_secrets_file,
    get_vault_id,
    get_vault_password,
    get_vault_password_file,
    run_ansible_vault,
    write_vault_password_file,
)
from ..vault.password import clear_vault_password_cache


class SecretLocationChoice(click.Choice):
    """Dynamic choice type that includes workstations and discovered profiles."""

    def __init__(self):
        super().__init__([], case_sensitive=True)

    @property
    def choices(self) -> list[str]:
        return get_all_secret_locations()

    @choices.setter
    def choices(self, value: list[str]) -> None:
        pass


@click.group()
def secret():
    """Manage encrypted secrets for MCP servers and other sensitive data."""
    pass


@secret.command("set")
@click.option(
    "--profile",
    "-p",
    type=SecretLocationChoice(),
    required=True,
    help="Profile name (e.g., 'common', 'work', 'personal')",
)
@click.argument("key")
def secret_set(profile: str, key: str):
    """Set an encrypted secret value.

    KEY should be in dot notation, e.g., 'mcp.github.token'

    Value can be provided interactively or via stdin:
        echo "myvalue" | dotfiles secret set -p common key.path
    """
    secrets_file = get_secrets_file(profile)

    # Read from stdin if piped, otherwise prompt interactively
    if sys.stdin.isatty():
        value = getpass.getpass(f"Enter value for {key}: ")
    else:
        value = sys.stdin.read().rstrip("\n")

    if not value:
        click.echo("Error: Empty value provided", err=True)
        return 1

    secrets = {}
    if secrets_file.exists():
        file_content = secrets_file.read_text()
        if file_content.startswith("$ANSIBLE_VAULT"):
            rc, stdout, stderr = run_ansible_vault(
                ["decrypt", "--output", "-", str(secrets_file)], location=profile
            )
            if rc == 0:
                secrets = yaml.safe_load(stdout) or {}
            else:
                click.echo(f"Error decrypting secrets file: {stderr}", err=True)
                return 1
        else:
            secrets = yaml.safe_load(file_content) or {}

    keys = key.split(".")
    current = secrets
    for k in keys[:-1]:
        if k not in current:
            current[k] = {}
        current = current[k]
    current[keys[-1]] = value

    yaml_content = yaml.dump(secrets, default_flow_style=False)

    secrets_file.write_text(yaml_content)
    rc, stdout, stderr = run_ansible_vault(
        ["encrypt", str(secrets_file)], location=profile
    )
    if rc != 0:
        click.echo(f"Error encrypting secrets file: {stderr}", err=True)
        return 1

    click.echo(f"Secret '{key}' set in {secrets_file.name}")
    return 0


@secret.command("get")
@click.option(
    "--profile",
    "-p",
    type=SecretLocationChoice(),
    required=True,
    help="Profile name (e.g., 'common', 'work', 'personal')",
)
@click.argument("key")
def secret_get(profile: str, key: str):
    """Get a decrypted secret value.

    KEY should be in dot notation, e.g., 'mcp.github.token'
    """
    secrets_file = get_secrets_file(profile)

    if not secrets_file.exists():
        click.echo(f"Error: Secrets file not found: {secrets_file}", err=True)
        return 1

    rc, stdout, stderr = run_ansible_vault(
        ["decrypt", "--output", "-", str(secrets_file)], location=profile
    )
    if rc != 0:
        click.echo(f"Error decrypting secrets file: {stderr}", err=True)
        return 1

    secrets = yaml.safe_load(stdout) or {}

    keys = key.split(".")
    current = secrets
    for k in keys:
        if not isinstance(current, dict) or k not in current:
            click.echo(f"Error: Key '{key}' not found", err=True)
            return 1
        current = current[k]

    click.echo(current)
    return 0


@secret.command("list")
@click.option(
    "--profile",
    "-p",
    type=SecretLocationChoice(),
    default=None,
    help="Profile name (default: show all)",
)
def secret_list(profile: str | None):
    """List all secret keys (without values)."""

    def list_keys(obj: dict, prefix: str = "") -> list[str]:
        keys = []
        for k, v in obj.items():
            full_key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                keys.extend(list_keys(v, full_key))
            else:
                keys.append(full_key)
        return keys

    def list_location_secrets(loc: str) -> bool:
        secrets_file = get_secrets_file(loc)

        if not secrets_file.exists():
            return False

        file_content = secrets_file.read_text()
        if not file_content.startswith("$ANSIBLE_VAULT"):
            click.echo(f"Warning: {secrets_file.name} is not encrypted", err=True)
            return False

        rc, stdout, stderr = run_ansible_vault(
            ["decrypt", "--output", "-", str(secrets_file)], location=loc
        )
        if rc != 0:
            click.echo(f"Error decrypting {secrets_file.name}: {stderr}", err=True)
            return False

        secrets = yaml.safe_load(stdout) or {}
        all_keys = list_keys(secrets)

        if all_keys:
            click.echo(f"{loc}:")
            for k in sorted(all_keys):
                click.echo(f"  {k}")
            return True
        return False

    locations = [profile] if profile else get_all_secret_locations()
    found_any = False

    for loc in locations:
        if list_location_secrets(loc):
            found_any = True
            if loc != locations[-1]:
                click.echo()

    if not found_any:
        click.echo("No secrets found")

    return 0


@secret.command("edit")
@click.option(
    "--profile",
    "-p",
    type=SecretLocationChoice(),
    required=True,
    help="Profile name (e.g., 'common', 'work', 'personal')",
)
def secret_edit(profile: str):
    """Edit secrets file in your editor."""
    secrets_file = get_secrets_file(profile)

    if not secrets_file.exists():
        secrets_file.write_text("# Secrets for " + profile + "\n")
        rc, _, stderr = run_ansible_vault(
            ["encrypt", str(secrets_file)], location=profile
        )
        if rc != 0:
            click.echo(f"Error creating secrets file: {stderr}", err=True)
            return 1

    editor = os.getenv("EDITOR", "vim")
    password = get_vault_password(profile)
    vault_id = get_vault_id(profile)

    with TemporaryDirectory() as tmpdir:
        pass_file = Path(tmpdir) / "vault_pass"
        pass_file.write_text(password)
        pass_file.chmod(0o600)

        rc = subprocess.call(
            [
                "ansible-vault",
                "edit",
                "--vault-id",
                f"{vault_id}@{pass_file}",
                str(secrets_file),
            ],
            env={**os.environ, "EDITOR": editor},
        )

    if rc != 0:
        click.echo("Error editing secrets file", err=True)
        return rc

    click.echo(f"Secrets file updated: {secrets_file.name}")
    return 0


@secret.command("rekey")
@click.option(
    "--profile",
    "-p",
    type=SecretLocationChoice(),
    default=None,
    help="Profile name (e.g., 'common', 'work', 'personal')",
)
@click.option(
    "--all",
    "-a",
    "rekey_all",
    is_flag=True,
    help="Rekey all profiles with secrets files",
)
def secret_rekey(profile: str | None, rekey_all: bool):
    """Change the vault password for secrets files.

    Use -p to rekey a specific profile, or --all to rekey all profiles.
    """
    if not profile and not rekey_all:
        click.echo("Error: Either -p/--profile or --all is required", err=True)
        return 1

    if profile and rekey_all:
        click.echo("Error: Cannot specify both -p/--profile and --all", err=True)
        return 1

    if rekey_all:
        locations_to_rekey = get_profile_names()
    else:
        locations_to_rekey = [profile]

    total_rekeyed = []

    for prof in locations_to_rekey:
        secrets_file = get_secrets_file(prof)
        if not secrets_file.exists():
            if profile:  # Only show skip message if explicitly requested
                click.echo(f"Skipping profile '{prof}': no secrets file found")
            continue

        if not secrets_file.read_text().startswith("$ANSIBLE_VAULT"):
            click.echo(f"Skipping profile '{prof}': secrets file not encrypted")
            continue

        click.echo(f"\n=== Rekeying profile: {prof} ===")
        old_password = get_vault_password(prof)

        new_password = getpass.getpass(f"Enter new vault password for {prof}: ")
        new_password_confirm = getpass.getpass(
            f"Confirm new vault password for {prof}: "
        )

        if new_password != new_password_confirm:
            click.echo("Error: Passwords do not match", err=True)
            return 1

        if not new_password:
            click.echo("Error: Password cannot be empty", err=True)
            return 1

        vault_id = get_vault_id(prof)
        with TemporaryDirectory() as tmpdir:
            old_pass_file = Path(tmpdir) / "old_pass"
            new_pass_file = Path(tmpdir) / "new_pass"
            old_pass_file.write_text(old_password)
            new_pass_file.write_text(new_password)
            old_pass_file.chmod(0o600)
            new_pass_file.chmod(0o600)

            result = subprocess.run(
                [
                    "ansible-vault",
                    "rekey",
                    "--vault-id",
                    f"{vault_id}@{old_pass_file}",
                    "--new-vault-id",
                    f"{vault_id}@{new_pass_file}",
                    str(secrets_file),
                ],
                capture_output=True,
                text=True,
            )

        if result.returncode != 0:
            click.echo(f"Error rekeying {prof}: {result.stderr}", err=True)
            return 1

        total_rekeyed.append(prof)

        prof_pass_file = get_vault_password_file(prof)
        if prof_pass_file.exists():
            if click.confirm(f"Update {prof}/.vault_password with new password?"):
                write_vault_password_file(prof_pass_file, new_password)
                click.echo(f"Updated {prof}/.vault_password")
        elif get_global_vault_password_file().exists():
            if click.confirm("Update global .vault_password with new password?"):
                write_vault_password_file(
                    get_global_vault_password_file(), new_password
                )
                click.echo("Updated .vault_password")

    clear_vault_password_cache()

    if total_rekeyed:
        click.echo(f"\nRekeyed: {', '.join(total_rekeyed)}")
    else:
        click.echo("No secrets files found to rekey")

    return 0


@secret.command("init")
@click.option(
    "--profile",
    "-p",
    type=SecretLocationChoice(),
    default=None,
    help="Profile name to initialize (default: global vault password)",
)
def secret_init(profile: str | None):
    """Initialize vault password (via 1Password or direct entry)."""
    if profile:
        return _init_profile_password(profile)

    dotenv_file = Path(DOTFILES_DIR) / ".env"

    existing_op_secret = os.environ.get("OP_SECRET")
    if existing_op_secret:
        click.echo(f"OP_SECRET is already set: {existing_op_secret}")
        if not click.confirm("Reconfigure?"):
            return 0

    global_vault_file = get_global_vault_password_file()
    if global_vault_file.exists():
        click.echo(f".vault_password file already exists at {global_vault_file}")
        if not click.confirm("Reconfigure?"):
            return 0

    click.echo("\nHow would you like to store the vault password?\n")
    click.echo("  1. 1Password (recommended) - Store reference in .env file")
    click.echo("  2. Direct entry - Store password in .vault_password file\n")

    choice = click.prompt("Choose option", type=click.Choice(["1", "2"]), default="1")

    if choice == "1":
        return _init_1password(dotenv_file)
    else:
        return _init_direct_password()


def _init_1password(dotenv_file: Path) -> int:
    """Initialize vault password using 1Password."""
    if not shutil.which("op"):
        click.echo("Error: 1Password CLI (op) is not installed.", err=True)
        click.echo("Install it with: brew install 1password-cli", err=True)
        return 1

    use_fzf = shutil.which("fzf") is not None

    try:
        click.echo("\nFetching vaults from 1Password...")
        result = subprocess.run(
            ["op", "vault", "list", "--format=json"],
            capture_output=True,
            text=True,
            check=True,
        )
        vaults = json.loads(result.stdout)
        if not vaults:
            click.echo("Error: No vaults found in 1Password", err=True)
            return 1

        vault_names = sorted([v["name"] for v in vaults])

        if use_fzf:
            selected_vault = fzf_select(vault_names, "Select Vault")
        else:
            selected_vault = numbered_select(vault_names, "Select Vault")

        if not selected_vault:
            click.echo("No vault selected, exiting.")
            return 1

        vault_id = next(v["id"] for v in vaults if v["name"] == selected_vault)
        click.echo(f"Selected vault: {selected_vault}")

        click.echo("\nFetching items...")
        result = subprocess.run(
            ["op", "item", "list", "--format=json", f"--vault={vault_id}"],
            capture_output=True,
            text=True,
            check=True,
        )
        items = json.loads(result.stdout)
        if not items:
            click.echo("Error: No items found in vault", err=True)
            return 1

        item_names = sorted([i["title"] for i in items])

        if use_fzf:
            selected_item = fzf_select(item_names, "Select Item")
        else:
            selected_item = numbered_select(item_names, "Select Item")

        if not selected_item:
            click.echo("No item selected, exiting.")
            return 1

        click.echo(f"Selected item: {selected_item}")

        click.echo("\nFetching fields...")
        result = subprocess.run(
            [
                "op",
                "item",
                "get",
                "--format=json",
                f"--vault={vault_id}",
                selected_item,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        item_data = json.loads(result.stdout)
        fields = item_data.get("fields", [])
        if not fields:
            click.echo("Error: No fields found in item", err=True)
            return 1

        field_labels = [f["label"] for f in fields if f.get("label")]

        if use_fzf:
            selected_field = fzf_select(field_labels, "Select Field")
        else:
            selected_field = numbered_select(field_labels, "Select Field")

        if not selected_field:
            click.echo("No field selected, exiting.")
            return 1

        click.echo(f"Selected field: {selected_field}")

        result = subprocess.run(
            [
                "op",
                "item",
                "get",
                "--format=json",
                f"--vault={vault_id}",
                selected_item,
                f"--field={selected_field}",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        field_data = json.loads(result.stdout)
        op_secret_ref = field_data.get("reference")

        if not op_secret_ref:
            click.echo("Error: Could not get secret reference", err=True)
            return 1

        dotenv.set_key(
            str(dotenv_file), "OP_SECRET", op_secret_ref, quote_mode="always"
        )
        click.echo(f"\nSaved OP_SECRET to {dotenv_file}")
        click.echo(f"Reference: {op_secret_ref}")

        global_vault_file = get_global_vault_password_file()
        if global_vault_file.exists():
            if click.confirm(
                "\n.vault_password file exists. Remove it (since using 1Password now)?"
            ):
                global_vault_file.unlink()
                click.echo(f"Removed {global_vault_file}")

        return 0

    except subprocess.CalledProcessError as e:
        click.echo(f"Error running 1Password CLI: {e.stderr}", err=True)
        return 1
    except json.JSONDecodeError as e:
        click.echo(f"Error parsing 1Password output: {e}", err=True)
        return 1


def _init_direct_password() -> int:
    """Initialize vault password with direct entry."""
    password = getpass.getpass("Enter vault password: ")
    password_confirm = getpass.getpass("Confirm vault password: ")

    if password != password_confirm:
        click.echo("Error: Passwords do not match", err=True)
        return 1

    if not password:
        click.echo("Error: Password cannot be empty", err=True)
        return 1

    global_vault_file = get_global_vault_password_file()
    write_vault_password_file(global_vault_file, password)
    click.echo(f"Created {global_vault_file}")
    return 0


def _init_profile_password(profile: str) -> int:
    """Initialize vault password for a profile."""
    password_file = get_vault_password_file(profile)

    if password_file.exists():
        click.echo(f".vault_password file already exists at {password_file}")
        if not click.confirm("Reconfigure?"):
            return 0

    profile_dir = Path(DOTFILES_DIR) / "profiles" / profile
    if not profile_dir.exists():
        click.echo(f"Error: Profile directory does not exist: {profile_dir}", err=True)
        click.echo("Create it first with: dotfiles bootstrap-profile " + profile)
        return 1

    password = getpass.getpass(f"Enter vault password for profile '{profile}': ")
    password_confirm = getpass.getpass(
        f"Confirm vault password for profile '{profile}': "
    )

    if password != password_confirm:
        click.echo("Error: Passwords do not match", err=True)
        return 1

    if not password:
        click.echo("Error: Password cannot be empty", err=True)
        return 1

    write_vault_password_file(password_file, password)
    click.echo(f"Created {password_file}")
    return 0
