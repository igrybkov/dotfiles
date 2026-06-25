"""Secrets management commands."""

from __future__ import annotations

import getpass
import os
import shutil
import subprocess
import sys

import click

from ..profiles import get_profile_names
from ..vault import sops
from ..vault.age import (
    OP_ITEM_TITLE,
    delete_age_key,
    generate_keypair,
    get_public_key_from_private,
    is_age_keygen_available,
    is_op_available,
    is_sops_available,
    read_age_key,
    read_age_key_from_op,
    write_age_key,
    write_age_key_to_op,
)
from ..vault.backend import get_backend
from ..vault.sops import (
    SopsError,
    get_all_secret_locations,
    get_secrets_file,
)


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
    _require_sops()

    secrets_file = get_secrets_file(profile)

    # Read from stdin if piped, otherwise prompt interactively
    if sys.stdin.isatty():
        value = getpass.getpass(f"Enter value for {key}: ")
    else:
        value = sys.stdin.read().rstrip("\n")

    if not value:
        click.echo("Error: Empty value provided", err=True)
        sys.exit(1)

    # Start from the existing decrypted secrets when the file is sops-encrypted;
    # a fresh (non-existent) file starts empty.
    secrets: dict = {}
    if sops.is_sops_encrypted(secrets_file):
        try:
            secrets = sops.decrypt_to_dict(secrets_file)
        except SopsError as exc:
            click.echo(f"Error decrypting secrets file: {exc}", err=True)
            sys.exit(1)
    elif secrets_file.exists():
        click.echo(
            f"Error: {secrets_file} exists but is not sops-encrypted. "
            f"Migrate it first with bin/migrate-to-sops.sh, or remove it.",
            err=True,
        )
        sys.exit(1)

    keys = key.split(".")
    current = secrets
    for k in keys[:-1]:
        node = current.get(k)
        if not isinstance(node, dict):
            node = {}
            current[k] = node
        current = node
    current[keys[-1]] = value

    secrets_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        sops.write_and_encrypt(secrets_file, secrets)
    except SopsError as exc:
        # write_and_encrypt restores the prior encrypted copy on failure, so
        # no plaintext is left behind; just surface the error clearly.
        click.echo(f"Error: {exc}", err=True)
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
    _require_sops()

    secrets_file = get_secrets_file(profile)

    if not secrets_file.exists():
        click.echo(f"Error: Secrets file not found: {secrets_file}", err=True)
        sys.exit(1)

    try:
        secrets = sops.decrypt_to_dict(secrets_file)
    except SopsError as exc:
        click.echo(f"Error decrypting secrets file: {exc}", err=True)
        sys.exit(1)

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
    _require_sops()

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

        if not sops.is_sops_encrypted(secrets_file):
            click.echo(f"Warning: {secrets_file.name} is not sops-encrypted", err=True)
            return False

        try:
            secrets = sops.decrypt_to_dict(secrets_file)
        except SopsError as exc:
            click.echo(f"Error decrypting {secrets_file.name}: {exc}", err=True)
            return False

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
    """Edit secrets file in your editor (sops-encrypted in place)."""
    _require_sops()

    secrets_file = get_secrets_file(profile)

    # Create a fresh, sops-encrypted file when none exists yet, so `sops edit`
    # has something to decrypt.
    if not secrets_file.exists():
        secrets_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            sops.write_and_encrypt(secrets_file, {})
        except SopsError as exc:
            click.echo(f"Error creating secrets file: {exc}", err=True)
            sys.exit(1)

    editor = os.getenv("EDITOR", "vim")
    try:
        rc = sops.run_sops_edit(secrets_file, editor=editor)
    except SopsError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

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
    help="Rekey all sops-encrypted profiles",
)
def secret_rekey(profile: str | None, rekey_all: bool):
    """Re-encrypt secrets to match the recipients in .sops.yaml.

    Unlike the old Ansible-Vault flow, there is no password to rotate. The age
    recipients live in .sops.yaml. To add or remove a machine/teammate:

      1. Edit .sops.yaml and update the 'age:' recipient list.
      2. Run `dotfiles secret rekey --all` (or `-p <profile>`).

    This runs `sops updatekeys` on each sops-encrypted secrets.yml, which
    re-wraps the data key for the new recipient set. Your current age private
    key (from the keychain) must still be a recipient so sops can decrypt the
    data key to re-wrap it.
    """
    _require_sops()

    if not profile and not rekey_all:
        click.echo("Error: Either -p/--profile or --all is required", err=True)
        sys.exit(1)

    if profile and rekey_all:
        click.echo("Error: Cannot specify both -p/--profile and --all", err=True)
        sys.exit(1)

    if read_age_key() is None:
        click.echo(
            "Error: no age private key in the keychain. Run "
            "`dotfiles secret init` first.",
            err=True,
        )
        sys.exit(1)

    locations_to_rekey = get_profile_names() if rekey_all else [profile]

    total_rekeyed: list[str] = []

    for prof in locations_to_rekey:
        secrets_file = get_secrets_file(prof)
        if not secrets_file.exists():
            if profile:  # Only show skip message if explicitly requested
                click.echo(f"Skipping profile '{prof}': no secrets file found")
            continue

        if not sops.is_sops_encrypted(secrets_file):
            click.echo(f"Skipping profile '{prof}': secrets file not sops-encrypted")
            continue

        click.echo(f"\n=== Rekeying profile: {prof} ===")
        rc, _, stderr = sops.reencrypt_with_updated_keys(secrets_file)
        if rc != 0:
            click.echo(
                f"Error rekeying {prof}: {stderr.strip() or 'sops updatekeys failed'}",
                err=True,
            )
            sys.exit(1)

        total_rekeyed.append(prof)

    if total_rekeyed:
        click.echo(f"\nRekeyed: {', '.join(total_rekeyed)}")
    else:
        click.echo("No sops-encrypted secrets files found to rekey")

    return 0


# ---------------------------------------------------------------- keychain group


@secret.group("keychain")
def secret_keychain():
    """Manage the OS-level age private key storage (keychain/gpg file)."""


@secret_keychain.command("status")
def keychain_status():
    """Print the backend state, age key presence, and stored labels."""
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

    # Age key presence + public key (the private key is never printed).
    private_key = read_age_key()
    if private_key:
        click.echo("Age private key: present")
        if is_age_keygen_available():
            try:
                pub = get_public_key_from_private(private_key)
                click.echo(f"  public key: {pub}")
            except RuntimeError as exc:
                click.echo(f"  (could not derive public key: {exc})", err=True)
    else:
        click.echo("Age private key: (not stored — run `dotfiles secret init`)")

    labels = state.get("labels", [])
    if labels:
        click.echo(f"Labels ({len(labels)}):")
        for label in labels:
            click.echo(f"  - {label}")
    else:
        click.echo("Labels: (none)")


@secret_keychain.command("push")
def keychain_push():
    """Store an existing age private key in the OS keychain.

    Use to import a key created elsewhere (or to restore from backup) without
    generating a new one. Paste the full `age-keygen` output (the comment
    lines plus the AGE-SECRET-KEY-... line) and finish with EOF (Ctrl-D).
    """
    if read_age_key() is not None and not click.confirm(
        "An age private key is already stored. Overwrite?", default=False
    ):
        click.echo("Aborted.")
        return 0

    if sys.stdin.isatty():
        click.echo("Paste the age private key, then press Ctrl-D:")
    private_key = sys.stdin.read().strip()
    if not private_key:
        click.echo("Error: No key provided.", err=True)
        sys.exit(1)
    if "AGE-SECRET-KEY-" not in private_key:
        click.echo(
            "Error: input does not look like an age private key "
            "(missing 'AGE-SECRET-KEY-').",
            err=True,
        )
        sys.exit(1)

    try:
        write_age_key(private_key)
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    click.echo("Stored age private key in the keychain.")
    if is_age_keygen_available():
        try:
            pub = get_public_key_from_private(private_key)
            click.echo(f"Public key: {pub}")
            click.echo("Ensure this recipient is present in .sops.yaml.")
        except RuntimeError:
            pass
    return 0


@secret_keychain.command("export-key")
def keychain_export_key():
    """Print the age private key so it can be backed up (e.g. to 1Password).

    The key is printed to stdout only when stdout is NOT a tty, or after an
    explicit warning prompt when it is. Pipe to a password manager or a
    secure file — do not share or commit.
    """
    private_key = read_age_key()
    if private_key is None:
        click.echo(
            "Error: no age private key in keychain. Run `dotfiles secret init` first.",
            err=True,
        )
        sys.exit(1)

    if sys.stdout.isatty():
        click.echo(
            "WARNING: this will print your age private key to the terminal.",
            err=True,
        )
        if not click.confirm("Continue?", default=False):
            click.echo("Aborted.", err=True)
            return
    click.echo(private_key)


@secret_keychain.command("backup")
def keychain_backup():
    """Save the age private key to 1Password for cross-machine portability.

    Stores the key as a Secure Note titled "dotfiles-age-key" in 1Password.
    On a new machine:

      1. Install 1Password and sign in (public profile, no secrets needed)
      2. Run `dotfiles secret init` — it pulls the key from 1Password
      3. Run `dotfiles install --all`
    """
    if not is_op_available():
        click.echo(
            "Error: op CLI not found. Install 1Password CLI: brew install 1password-cli",
            err=True,
        )
        sys.exit(1)

    private_key = read_age_key()
    if private_key is None:
        click.echo(
            "Error: no age private key in keychain. Run `dotfiles secret init` first.",
            err=True,
        )
        sys.exit(1)

    try:
        write_age_key_to_op(private_key)
    except RuntimeError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    click.echo(f"Age private key saved to 1Password item '{OP_ITEM_TITLE}'.")


@secret_keychain.command("rm")
@click.argument("label", required=False)
@click.option(
    "--age",
    "rm_age",
    is_flag=True,
    help="Remove the stored age private key.",
)
@click.option(
    "--yes",
    "-y",
    "assume_yes",
    is_flag=True,
    help="Skip the confirmation prompt.",
)
def keychain_rm(label: str | None, rm_age: bool, assume_yes: bool):
    """Delete a stored keychain item.

    Pass --age to remove the age private key, or LABEL to remove a leftover
    per-profile Ansible Vault password (these become unused after migration).
    """
    from ..vault.age import AGE_KEY_LABEL

    if rm_age and label:
        click.echo("Error: pass either --age or LABEL, not both.", err=True)
        sys.exit(1)
    if not rm_age and not label:
        click.echo("Error: provide LABEL or use --age.", err=True)
        sys.exit(1)

    target = AGE_KEY_LABEL if rm_age else label
    descriptor = "age private key" if rm_age else f"password for {target!r}"

    backend = get_backend()
    if target not in backend.list_labels():
        click.echo(f"No stored {descriptor}; nothing to do.")
        return 0
    if not assume_yes and not click.confirm(
        f"Delete stored {descriptor}?", default=False
    ):
        click.echo("Aborted.")
        return 0
    try:
        if rm_age:
            delete_age_key()
        else:
            backend.delete(target)
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    click.echo(f"Deleted {descriptor}.")


# ------------------------------------------------------------------------- init


@secret.command("init")
@click.option(
    "--profile",
    "-p",
    "profile",
    default=None,
    help="[unused, kept for compatibility]",
)
def secret_init(profile: str | None):
    """Generate an age keypair and store the private key in the OS keychain.

    A single age keypair protects every profile's sops-encrypted secrets.yml.
    This generates one (if absent), stores the private key in the OS keychain,
    and writes the public key into .sops.yaml's creation rules so sops can
    encrypt. The private key is never printed; the public key is safe to
    commit.
    """
    if not is_age_keygen_available():
        click.echo(
            "Error: age-keygen not found. Install age: brew install age", err=True
        )
        sys.exit(1)

    existing = read_age_key()
    if existing:
        click.echo("Age private key already stored in keychain.")
        try:
            public_key = get_public_key_from_private(existing)
        except RuntimeError as exc:
            click.echo(f"Error deriving public key: {exc}", err=True)
            sys.exit(1)
        click.echo(f"Public key: {public_key}")
        _ensure_recipient_in_sops_config(public_key)
        return 0

    # No key in keychain — try 1Password before generating a fresh keypair.
    if is_op_available():
        click.echo("Checking 1Password for an existing age key …")
        op_key = read_age_key_from_op()
        if op_key is not None:
            try:
                write_age_key(op_key)
            except Exception as exc:
                click.echo(f"Error storing age private key: {exc}", err=True)
                sys.exit(1)
            click.echo(
                "Age private key imported from 1Password and stored in keychain."
            )
            try:
                public_key = get_public_key_from_private(op_key)
                click.echo(f"Public key: {public_key}")
                _ensure_recipient_in_sops_config(public_key)
            except RuntimeError as exc:
                click.echo(f"Warning: could not derive public key: {exc}", err=True)
            return 0
        click.echo("No age key found in 1Password — generating a new keypair.")

    try:
        private_key, public_key = generate_keypair()
    except RuntimeError as exc:
        click.echo(f"Error generating keypair: {exc}", err=True)
        sys.exit(1)

    try:
        write_age_key(private_key)
    except Exception as exc:
        click.echo(f"Error storing age private key: {exc}", err=True)
        sys.exit(1)

    click.echo("Generated and stored age private key in the OS keychain.")
    click.echo(f"\nPublic key: {public_key}")
    _ensure_recipient_in_sops_config(public_key)

    click.echo(
        "\nNext steps:"
        "\n  1. Commit .sops.yaml."
        "\n  2. Back up your key to 1Password: dotfiles secret keychain backup"
        "\n  3. Migrate existing profiles: bin/migrate-to-sops.sh <profile>"
        "\n  4. Or create new secrets: dotfiles secret set -p <profile> <key>"
    )
    return 0


def _ensure_recipient_in_sops_config(public_key: str) -> None:
    """Write ``public_key`` into .sops.yaml unless it's already the recipient."""
    config_path = sops.get_sops_config_path()
    if not config_path.exists():
        click.echo(
            f"Warning: {config_path} not found. Add this recipient manually:\n"
            f"  age: {public_key}",
            err=True,
        )
        return

    current = sops.get_configured_recipients()
    if current == [public_key]:
        click.echo(".sops.yaml already lists this recipient.")
        return

    try:
        sops.set_sops_recipient(public_key)
    except SopsError as exc:
        click.echo(
            f"Warning: could not update .sops.yaml automatically ({exc}). "
            f"Add this recipient manually:\n  age: {public_key}",
            err=True,
        )
        return
    click.echo(f"Updated {config_path.name} with the age recipient.")


def _require_sops() -> None:
    """Exit with a helpful message if sops is not installed."""
    if not is_sops_available():
        click.echo(
            "Error: sops not found on PATH. Install sops: brew install sops",
            err=True,
        )
        sys.exit(1)
