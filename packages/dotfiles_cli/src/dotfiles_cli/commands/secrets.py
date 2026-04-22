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
import yaml

from ..profiles import get_profile_names
from ..utils import fzf_select, numbered_select
from ..vault import (
    get_all_secret_locations,
    get_backend,
    get_profiles_with_secrets,
    get_secrets_file,
    get_vault_id,
    get_vault_password,
    run_ansible_vault,
)
from ..vault.backends import onepassword
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
        sys.exit(1)

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
                sys.exit(1)
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
        sys.exit(1)

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
@click.option(
    "--zero",
    "-0",
    "zero",
    is_flag=True,
    help="NUL-separate values (safe for any byte; meant for machine consumption).",
)
@click.option(
    "--clipboard/--no-clipboard",
    "clipboard",
    default=None,
    help=(
        "Copy value to clipboard with auto-clear (macOS: pbcopy; "
        "Linux: wl-copy or xclip). Defaults to on for single-key "
        "interactive TTY usage; off under --zero or when piped."
    ),
)
@click.argument("keys", nargs=-1, required=True)
def secret_get(profile: str, zero: bool, clipboard: bool | None, keys: tuple[str, ...]):
    """Get one or more decrypted secret values.

    KEYS use dot notation, e.g., 'mcp.github.token'. Multiple KEYS share a
    single decrypt pass. Default output is newline-separated; pass --zero/-0
    to NUL-separate values (required when callers need to read values that
    may contain newlines). Use --clipboard to copy to the system clipboard
    with a 30s auto-clear instead of printing.
    """
    secrets_file = get_secrets_file(profile)

    if not secrets_file.exists():
        click.echo(f"Error: Secrets file not found: {secrets_file}", err=True)
        sys.exit(1)

    rc, stdout, stderr = run_ansible_vault(
        ["decrypt", "--output", "-", str(secrets_file)], location=profile
    )
    if rc != 0:
        click.echo(f"Error decrypting secrets file: {stderr}", err=True)
        sys.exit(1)

    secrets = yaml.safe_load(stdout) or {}

    def _lookup(key: str):
        current = secrets
        for part in key.split("."):
            if not isinstance(current, dict) or part not in current:
                click.echo(f"Error: Key '{key}' not found", err=True)
                sys.exit(1)
            current = current[part]
        return current

    values = [_lookup(k) for k in keys]

    if clipboard is None:
        clipboard = sys.stdout.isatty() and not zero and len(keys) == 1

    if clipboard:
        if len(keys) != 1:
            click.echo("Error: --clipboard requires exactly one key.", err=True)
            sys.exit(2)
        try:
            _copy_to_clipboard_with_clear(str(values[0]))
        except RuntimeError as exc:
            click.echo(f"Error: {exc}", err=True)
            sys.exit(1)
        click.echo(f"(copied {keys[0]!r} to clipboard, clears in 30s)", err=True)
        return

    sep = b"\0" if zero else b"\n"
    buf = sys.stdout.buffer
    for v in values:
        buf.write(str(v).encode("utf-8"))
        buf.write(sep)
    buf.flush()


def _clipboard_write_command() -> list[str] | None:
    """Return the shell command that writes stdin to the clipboard, or None."""
    if shutil.which("pbcopy"):
        return ["pbcopy"]
    if os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-copy"):
        return ["wl-copy"]
    if shutil.which("xclip"):
        return ["xclip", "-selection", "clipboard"]
    return None


def _copy_to_clipboard_with_clear(value: str, delay_seconds: int = 30) -> None:
    """Copy `value` to the clipboard and schedule a clear after `delay_seconds`."""
    cmd = _clipboard_write_command()
    if cmd is None:
        raise RuntimeError(
            "No clipboard utility found (need pbcopy, wl-copy, or xclip)."
        )

    result = subprocess.run(cmd, input=value, text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"Clipboard write failed: {result.stderr.strip() or 'non-zero exit'}"
        )

    # Detached clearer — survives parent exit, writes empty input to the
    # same clipboard utility after `delay_seconds`.
    import shlex

    clear_cmd = f"sleep {int(delay_seconds)} && printf '' | " + " ".join(
        shlex.quote(c) for c in cmd
    )
    subprocess.Popen(
        ["sh", "-c", clear_cmd],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


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
            sys.exit(1)

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
        sys.exit(rc)

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
@click.option(
    "--sync/--no-sync",
    "sync_to_op",
    default=True,
    help=(
        "Push the new password to 1Password after rekey "
        "(only when DOTFILES_VAULT_OP_ITEM is configured). Default: --sync."
    ),
)
def secret_rekey(profile: str | None, rekey_all: bool, sync_to_op: bool):
    """Change the vault password for secrets files.

    Use -p to rekey a specific profile, or --all to rekey all profiles.

    If `DOTFILES_VAULT_OP_ITEM` is set, the new password is also pushed to
    the corresponding field on the 1Password item. Use `--no-sync` to skip
    the 1P write (e.g. when rotating temporarily on a single machine).
    """
    if not profile and not rekey_all:
        click.echo("Error: Either -p/--profile or --all is required", err=True)
        sys.exit(1)

    if profile and rekey_all:
        click.echo("Error: Cannot specify both -p/--profile and --all", err=True)
        sys.exit(1)

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
            sys.exit(1)

        if not new_password:
            click.echo("Error: Password cannot be empty", err=True)
            sys.exit(1)

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
            sys.exit(1)

        total_rekeyed.append(prof)

        # Push the new password into the backend so the next ansible run
        # doesn't fall back to the old cached value.
        backend = get_backend()
        try:
            backend.ensure_ready()
            backend.write(prof, new_password)
            click.echo(f"Updated backend password for {prof!r}.")
        except Exception as exc:
            click.echo(
                f"Warning: could not update backend for {prof!r}: {exc}",
                err=True,
            )

        # Mirror to 1Password when configured so other machines can pull
        # the new password via the fallback path without extra steps.
        if sync_to_op and onepassword.is_configured():
            try:
                onepassword.write_field(prof, new_password)
                click.echo(f"Pushed new password for {prof!r} to 1Password.")
            except onepassword.OnePasswordError as exc:
                click.echo(
                    f"Warning: could not push {prof!r} to 1Password: {exc}\n"
                    f"The local backend is up to date; rerun "
                    f"`dotfiles secret rekey -p {prof}` after fixing 1Password, "
                    f"or push manually with `op item edit`.",
                    err=True,
                )

    clear_vault_password_cache()

    if total_rekeyed:
        click.echo(f"\nRekeyed: {', '.join(total_rekeyed)}")
    else:
        click.echo("No secrets files found to rekey")

    return 0


# ---------------------------------------------------------------- keychain group


@secret.group("keychain")
def secret_keychain():
    """Manage the OS-level vault password storage (keychain/gpg file)."""


@secret_keychain.command("status")
def keychain_status():
    """Print the backend state and the labels it holds (no values)."""
    backend = get_backend()
    try:
        state = backend.status()
    except Exception as exc:
        click.echo(f"Error reading backend status: {exc}", err=True)
        sys.exit(1)

    click.echo(f"Backend: {state.get('backend', 'unknown')}")
    for key in (
        "service",
        "keyring_backend",
        "vault_file",
        "exists",
        "gpg_installed",
        "master_password_env_set",
        "decryption_error",
        "labels_path",
    ):
        if key in state and state[key] is not None:
            click.echo(f"  {key}: {state[key]}")

    labels = state.get("labels", [])
    if labels:
        click.echo(f"Labels ({len(labels)}):")
        for label in labels:
            click.echo(f"  - {label}")
    else:
        click.echo("Labels: (none)")


@secret_keychain.command("push")
@click.argument("label")
def keychain_push(label: str):
    """Store a vault password for LABEL, replacing any existing value.

    Prompts twice (confirm). Use for manually adding a label without going
    through `secret init`'s full setup flow.
    """
    backend = get_backend()
    try:
        backend.ensure_ready()
    except Exception as exc:
        click.echo(f"Backend not ready: {exc}", err=True)
        sys.exit(1)

    password = getpass.getpass(f"Vault password for {label!r}: ")
    if not password:
        click.echo("Error: Password cannot be empty.", err=True)
        sys.exit(1)
    confirm = getpass.getpass(f"Confirm vault password for {label!r}: ")
    if password != confirm:
        click.echo("Error: Passwords do not match.", err=True)
        sys.exit(1)

    try:
        backend.write(label, password)
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    click.echo(f"Stored password for {label!r}.")


@secret_keychain.command("rm")
@click.argument("label")
@click.option(
    "--yes",
    "-y",
    "assume_yes",
    is_flag=True,
    help="Skip the confirmation prompt.",
)
def keychain_rm(label: str, assume_yes: bool):
    """Delete the stored vault password for LABEL."""
    backend = get_backend()
    if label not in backend.list_labels():
        click.echo(f"No stored password for {label!r}; nothing to do.")
        return 0
    if not assume_yes and not click.confirm(
        f"Delete stored vault password for {label!r}?", default=False
    ):
        click.echo("Aborted.")
        return 0
    try:
        backend.delete(label)
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    click.echo(f"Deleted password for {label!r}.")


# ------------------------------------------------------------------------- init


@secret.command("init")
@click.option(
    "--profile",
    "-p",
    type=SecretLocationChoice(),
    default=None,
    help="Provision a single label (default: every profile with an encrypted secrets.yml).",
)
def secret_init(profile: str | None):
    """Initialize the OS-level vault password storage.

    On macOS: creates the dedicated keychain + unlock chain, then stores
    one item per label with ACL scoped to `bin/dotfiles-vault-client`.

    On Linux: verifies `gpg` is available and stores labels in a single
    gpg-symmetric-encrypted file unlocked by one master password.

    Only labels that have an associated encrypted `secrets.yml` are
    auto-provisioned. Use `dotfiles secret keychain push <label>` to
    register other labels explicitly.
    """
    backend = get_backend()
    try:
        backend.ensure_ready()
    except Exception as exc:
        click.echo(f"Backend setup failed: {exc}", err=True)
        sys.exit(1)

    if profile:
        labels = [profile]
    else:
        labels = get_profiles_with_secrets()

    if not labels:
        click.echo("No profiles with encrypted secrets found; nothing to provision.")
        return 0

    existing = set(backend.list_labels())
    stored: list[str] = []
    skipped: list[str] = []

    for label in labels:
        if label in existing:
            if not click.confirm(
                f"Password for {label!r} already stored. Overwrite?",
                default=False,
            ):
                click.echo(f"Skipping {label!r}.")
                skipped.append(label)
                continue

        click.echo(f"\n=== Vault password for {label!r} ===")
        password = _prompt_for_password(label)
        if not password:
            click.echo(f"No password entered for {label!r}; skipping.")
            skipped.append(label)
            continue

        try:
            backend.write(label, password)
        except Exception as exc:
            click.echo(f"Failed to store {label!r}: {exc}", err=True)
            sys.exit(1)
        click.echo(f"Stored password for {label!r}.")
        stored.append(label)

    click.echo()
    if stored:
        click.echo(f"Stored: {', '.join(stored)}")
    if skipped:
        click.echo(f"Skipped: {', '.join(skipped)}")
    click.echo("Run `dotfiles secret keychain status` to verify.")
    return 0


MAX_VAULT_PASSWORD_ATTEMPTS = 3


def _prompt_for_password(label: str) -> str:
    """Ask the user for a password for `label` — direct entry or 1P import."""
    if shutil.which("op"):
        click.echo("  1. Enter directly")
        click.echo("  2. Import from 1Password")
        choice = click.prompt(
            "Source", type=click.Choice(["1", "2"]), default="1", show_default=True
        )
    else:
        choice = "1"

    if choice == "2":
        return _fetch_value_from_1password() or ""
    return _prompt_and_validate(label)


def _prompt_and_validate(label: str) -> str:
    """Prompt for a password and validate it against the label's secrets file.

    If the label has an encrypted secrets.yml, the entered password is
    verified by attempting a decrypt; wrong passwords re-prompt up to
    MAX_VAULT_PASSWORD_ATTEMPTS times. Labels without an encrypted file
    (e.g. fresh profile) are accepted as-entered since there's nothing to
    verify against — first `secret set` will establish the encryption.
    """
    try:
        secrets_file = get_secrets_file(label)
    except ValueError:
        secrets_file = None

    can_validate = (
        secrets_file is not None
        and secrets_file.exists()
        and secrets_file.read_text().startswith("$ANSIBLE_VAULT")
    )

    for attempt in range(1, MAX_VAULT_PASSWORD_ATTEMPTS + 1):
        pw = getpass.getpass(f"Vault password for {label!r}: ")
        if not pw:
            click.echo("Error: Password cannot be empty.", err=True)
            return ""

        if not can_validate:
            # No encrypted file to check against — trust the user.
            return pw

        rc, _, _ = run_ansible_vault(
            ["view", str(secrets_file)], password=pw, location=label
        )
        if rc == 0:
            return pw

        remaining = MAX_VAULT_PASSWORD_ATTEMPTS - attempt
        if remaining > 0:
            click.echo(
                f"Password did not decrypt {secrets_file.name}. "
                f"{remaining} attempt{'s' if remaining != 1 else ''} remaining.",
                err=True,
            )

    click.echo("Error: Too many failed attempts.", err=True)
    return ""


def _fetch_value_from_1password() -> str | None:
    """Interactive walk through op vaults/items/fields; return the value or None."""
    if not shutil.which("op"):
        click.echo("1Password CLI (op) is not installed.", err=True)
        return None

    use_fzf = shutil.which("fzf") is not None

    try:
        click.echo("Fetching vaults from 1Password...")
        result = subprocess.run(
            ["op", "vault", "list", "--format=json"],
            capture_output=True,
            text=True,
            check=True,
        )
        vaults = json.loads(result.stdout)
        if not vaults:
            click.echo("No vaults found in 1Password.", err=True)
            return None
        vault_names = sorted([v["name"] for v in vaults])
        selected_vault = (
            fzf_select(vault_names, "Select Vault")
            if use_fzf
            else numbered_select(vault_names, "Select Vault")
        )
        if not selected_vault:
            return None
        vault_id = next(v["id"] for v in vaults if v["name"] == selected_vault)

        click.echo("Fetching items...")
        result = subprocess.run(
            ["op", "item", "list", "--format=json", f"--vault={vault_id}"],
            capture_output=True,
            text=True,
            check=True,
        )
        items = json.loads(result.stdout)
        if not items:
            click.echo("No items found in vault.", err=True)
            return None
        item_names = sorted([i["title"] for i in items])
        selected_item = (
            fzf_select(item_names, "Select Item")
            if use_fzf
            else numbered_select(item_names, "Select Item")
        )
        if not selected_item:
            return None

        click.echo("Fetching fields...")
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
        field_labels = [f["label"] for f in fields if f.get("label")]
        if not field_labels:
            click.echo("No fields found in item.", err=True)
            return None
        selected_field = (
            fzf_select(field_labels, "Select Field")
            if use_fzf
            else numbered_select(field_labels, "Select Field")
        )
        if not selected_field:
            return None

        # Read the value (not the reference) — we want to store the raw
        # password in the backend, not an op:// URL.
        result = subprocess.run(
            [
                "op",
                "read",
                "--no-newline",
                f"op://{vault_id}/{selected_item}/{selected_field}",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        value = result.stdout
        if not value:
            click.echo("1Password returned an empty value.", err=True)
            return None
        return value

    except subprocess.CalledProcessError as exc:
        click.echo(f"Error running 1Password CLI: {exc.stderr}", err=True)
        return None
    except json.JSONDecodeError as exc:
        click.echo(f"Error parsing 1Password output: {exc}", err=True)
        return None
