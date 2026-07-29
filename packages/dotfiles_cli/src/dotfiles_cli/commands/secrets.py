"""Secrets management commands (sops + age, per-machine key model).

Each machine has one age keypair; its private key lives in the OS keychain and
its public key is enrolled — per profile — as a recipient in that profile's
``.sops.yaml``. Recipient sets diverge per profile on purpose (a profile can
list two machines plus an opt-in escrow key while another lists just one), so
there is no single global key.

Command surface:

  set / get / list / edit   operate on a profile's sops-encrypted secrets.yml
  init                      provision THIS machine's age key (import or generate)
  enroll                    add this machine as a recipient of a profile
  revoke                    remove a recipient (public key) from a profile
  keychain status/push/     manage the stored key (import, export, escrow backup,
    export-key/backup/rm      remove)

`get` preserves the machine contract other tooling depends on: multi-key,
``-0/--zero`` NUL-separated output, and clipboard-with-auto-clear on a single
interactive key.
"""

from __future__ import annotations

import getpass
import os
import shutil
import subprocess
import sys
from pathlib import Path

import click

from ..profiles import get_profile_names
from ..vault import sops
from ..vault.age import (
    AGE_KEY_LABEL,
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
    SOPS_MISSING_MESSAGE,
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


def _require_sops() -> None:
    """Exit with a helpful message if sops is not installed."""
    if not is_sops_available():
        click.echo(f"Error: {SOPS_MISSING_MESSAGE}", err=True)
        sys.exit(1)


def _list_keys(obj: dict, prefix: str = "") -> list[str]:
    """Flatten a nested dict into dot-notation key paths (leaves only)."""
    keys: list[str] = []
    for k, v in obj.items():
        full_key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            keys.extend(_list_keys(v, full_key))
        else:
            keys.append(full_key)
    return keys


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

    # Encryption needs the profile's .sops.yaml recipients; without it sops
    # cannot know who to encrypt for. Point the user at `enroll`.
    if not sops.has_sops_config(profile):
        click.echo(
            f"Error: {profile!r} has no {sops.SOPS_CONFIG_NAME}. "
            f"Enroll this machine first: dotfiles secret enroll -p {profile}",
            err=True,
        )
        sys.exit(1)

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
            f"Migrate it first, or remove it.",
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

        all_keys = _list_keys(secrets)

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

    if not sops.has_sops_config(profile):
        click.echo(
            f"Error: {profile!r} has no {sops.SOPS_CONFIG_NAME}. "
            f"Enroll this machine first: dotfiles secret enroll -p {profile}",
            err=True,
        )
        sys.exit(1)

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


# ------------------------------------------------------------- identity helper


def _acquire_identity(
    profile: str,
    secrets_file: Path,
    *,
    force_escrow: bool = False,
    identity_path: str | None = None,
) -> tuple[str, str]:
    """Return (age_private_key_text, source_label) able to decrypt ``secrets_file``.

    ``sops updatekeys`` must decrypt the file's current data key before it can
    re-wrap it for a new recipient set, so we need an identity that is a
    *current* recipient of the ciphertext. Each candidate is verified with a
    trial ``sops -d`` (authoritative — it checks the ciphertext's real
    recipients, not just what ``.sops.yaml`` claims).

    Probe order, unless a flag forces one source:
      1. this machine's keychain key,
      2. the escrow key mirrored in 1Password (only used if it actually
         decrypts — i.e. the profile opted the escrow key in as a recipient),
      3. an age identity file at ``identity_path``.

    The escrow / provided key is passed to sops via ``SOPS_AGE_KEY`` for that
    one subprocess only; it is never written to this machine's keychain or to
    disk. Raises SopsError naming what was tried if none can decrypt.
    """
    candidates: list[tuple[str, str | None]] = []

    if identity_path is not None:
        try:
            key_text = Path(identity_path).read_text()
        except OSError as exc:
            raise SopsError(f"could not read identity file {identity_path!r}: {exc}")
        if "AGE-SECRET-KEY-" not in key_text:
            raise SopsError(
                f"{identity_path!r} does not contain an age private key "
                f"(missing 'AGE-SECRET-KEY-')."
            )
        candidates.append((f"identity file {identity_path}", key_text))
    elif force_escrow:
        escrow = read_age_key_from_op()
        if escrow is None:
            raise SopsError(
                "no escrow key available in 1Password (item "
                f"{OP_ITEM_TITLE!r}); cannot use --from-escrow."
            )
        candidates.append(("escrow key (1Password)", escrow))
    else:
        machine = read_age_key()
        if machine is not None:
            candidates.append(("this machine's keychain key", machine))
        escrow = read_age_key_from_op()
        if escrow is not None:
            candidates.append(("escrow key (1Password)", escrow))

    for label, key_text in candidates:
        if key_text is not None and sops.can_decrypt(secrets_file, key_text):
            return key_text, label

    tried = ", ".join(label for label, _ in candidates) or "no identities"
    raise SopsError(
        f"no usable identity could decrypt {secrets_file.name} (tried: {tried}). "
        f"Pass --identity <age-key-file> with a key that is a current recipient, "
        f"or --from-escrow if the escrow key is enrolled for {profile!r}."
    )


def _resolve_targets(profile: str | None, do_all: bool) -> list[str]:
    """Validate the -p/--all selection and return the target profile list."""
    if not profile and not do_all:
        click.echo("Error: Either -p/--profile or --all is required", err=True)
        sys.exit(1)
    if profile and do_all:
        click.echo("Error: Cannot specify both -p/--profile and --all", err=True)
        sys.exit(1)
    return get_profile_names() if do_all else [profile]


# ----------------------------------------------------------------------- enroll


@secret.command("enroll")
@click.option(
    "--profile",
    "-p",
    type=SecretLocationChoice(),
    default=None,
    help="Profile to enroll this machine into.",
)
@click.option(
    "--all",
    "-a",
    "enroll_all",
    is_flag=True,
    help="Enroll this machine into every discovered profile.",
)
@click.option(
    "--identity",
    "identity_path",
    default=None,
    help="Age identity file to decrypt the target with (for the updatekeys step).",
)
@click.option(
    "--from-escrow",
    "from_escrow",
    is_flag=True,
    help="Force using the 1Password escrow key to decrypt for updatekeys.",
)
def secret_enroll(
    profile: str | None,
    enroll_all: bool,
    identity_path: str | None,
    from_escrow: bool,
):
    """Add THIS machine's age public key as a recipient of a profile.

    Adds this machine to the profile's .sops.yaml, then runs `sops updatekeys`
    on its secrets.yml so the ciphertext is re-wrapped for the new recipient
    set. Re-wrapping requires decrypting the existing data key first; the
    identity used comes from --identity/--from-escrow, or is probed
    (this machine's key, then the escrow key).
    """
    _require_sops()

    if not is_age_keygen_available():
        click.echo(
            "Error: age-keygen not found. Install age: brew install age", err=True
        )
        sys.exit(1)

    machine_private = read_age_key()
    if machine_private is None:
        click.echo(
            "Error: no age private key in the keychain. Run "
            "`dotfiles secret init` first.",
            err=True,
        )
        sys.exit(1)

    try:
        machine_public = get_public_key_from_private(machine_private)
    except RuntimeError as exc:
        click.echo(f"Error deriving public key: {exc}", err=True)
        sys.exit(1)

    targets = _resolve_targets(profile, enroll_all)

    enrolled: list[str] = []
    already: list[str] = []

    for prof in targets:
        try:
            secrets_file = get_secrets_file(prof)
        except ValueError:
            click.echo(f"Skipping {prof!r}: profile not found.", err=True)
            continue

        has_ciphertext = secrets_file.exists() and sops.is_sops_encrypted(secrets_file)

        # Bootstrap case: no encrypted secrets yet — just record the recipient.
        if not has_ciphertext:
            changed = sops.add_sops_recipient(prof, machine_public)
            if changed:
                click.echo(
                    f"Enrolled this machine into {prof!r} "
                    f"(no secrets.yml yet — nothing to re-encrypt)."
                )
                enrolled.append(prof)
            else:
                already.append(prof)
            continue

        # There is ciphertext: add the recipient, then re-wrap. If anything
        # fails, roll back the .sops.yaml change to avoid leaving a recipient
        # listed that the ciphertext was never re-wrapped for.
        changed = sops.add_sops_recipient(prof, machine_public)
        if not changed:
            already.append(prof)
            continue

        try:
            key_text, source = _acquire_identity(
                prof,
                secrets_file,
                force_escrow=from_escrow,
                identity_path=identity_path,
            )
        except SopsError as exc:
            sops.remove_sops_recipient(prof, machine_public)
            click.echo(f"Error enrolling {prof!r}: {exc}", err=True)
            sys.exit(1)

        rc, _, stderr = sops.reencrypt_with_updated_keys(secrets_file, age_key=key_text)
        if rc != 0:
            sops.remove_sops_recipient(prof, machine_public)
            click.echo(
                f"Error re-encrypting {prof!r}: "
                f"{stderr.strip() or 'sops updatekeys failed'}",
                err=True,
            )
            sys.exit(1)

        click.echo(f"Enrolled this machine into {prof!r} (decrypted via {source}).")
        enrolled.append(prof)

    click.echo()
    click.echo(f"Public key: {machine_public}")
    if enrolled:
        click.echo(f"Enrolled: {', '.join(enrolled)}")
    if already:
        click.echo(f"Already a recipient: {', '.join(already)}")
    return 0


# ----------------------------------------------------------------------- revoke


@secret.command("revoke")
@click.argument("public_key")
@click.option(
    "--profile",
    "-p",
    type=SecretLocationChoice(),
    default=None,
    help="Profile to revoke the key from.",
)
@click.option(
    "--all",
    "-a",
    "revoke_all",
    is_flag=True,
    help="Revoke the key from every discovered profile.",
)
@click.option(
    "--identity",
    "identity_path",
    default=None,
    help="Age identity file to decrypt the target with (for the updatekeys step).",
)
@click.option(
    "--from-escrow",
    "from_escrow",
    is_flag=True,
    help="Force using the 1Password escrow key to decrypt for updatekeys.",
)
def secret_revoke(
    public_key: str,
    profile: str | None,
    revoke_all: bool,
    identity_path: str | None,
    from_escrow: bool,
):
    """Remove an age PUBLIC_KEY from a profile's recipients and re-wrap.

    Removes PUBLIC_KEY from the profile's .sops.yaml, then runs
    `sops updatekeys` so future ciphertext can no longer be decrypted by that
    key. NOTE: old ciphertext already in git history stays decryptable by the
    revoked key — this command prints the profile's secret key-paths so you can
    rotate the ones that matter. Rotation itself is manual.
    """
    _require_sops()

    targets = _resolve_targets(profile, revoke_all)

    revoked: list[str] = []
    not_listed: list[str] = []

    for prof in targets:
        if public_key not in sops.get_configured_recipients(prof):
            not_listed.append(prof)
            continue

        try:
            secrets_file = get_secrets_file(prof)
        except ValueError:
            click.echo(f"Skipping {prof!r}: profile not found.", err=True)
            continue

        has_ciphertext = secrets_file.exists() and sops.is_sops_encrypted(secrets_file)

        if not has_ciphertext:
            sops.remove_sops_recipient(prof, public_key)
            click.echo(f"Revoked {public_key} from {prof!r} (no secrets.yml).")
            revoked.append(prof)
            continue

        # Acquire a working identity BEFORE removing, so the trial decrypt runs
        # against the current recipient set.
        try:
            key_text, source = _acquire_identity(
                prof,
                secrets_file,
                force_escrow=from_escrow,
                identity_path=identity_path,
            )
        except SopsError as exc:
            click.echo(f"Error revoking from {prof!r}: {exc}", err=True)
            sys.exit(1)

        # Snapshot key-paths (for the rotation reminder) while we still hold a
        # working identity.
        try:
            current_dict = sops.decrypt_to_dict(secrets_file, age_key=key_text)
        except SopsError:
            current_dict = {}

        sops.remove_sops_recipient(prof, public_key)
        rc, _, stderr = sops.reencrypt_with_updated_keys(secrets_file, age_key=key_text)
        if rc != 0:
            # Roll back so the recipient list matches the (still-old) ciphertext.
            sops.add_sops_recipient(prof, public_key)
            click.echo(
                f"Error re-encrypting {prof!r}: "
                f"{stderr.strip() or 'sops updatekeys failed'}",
                err=True,
            )
            sys.exit(1)

        click.echo(f"Revoked {public_key} from {prof!r} (decrypted via {source}).")
        revoked.append(prof)

        key_paths = sorted(_list_keys(current_dict))
        if key_paths:
            click.echo(
                "  Consider rotating these values (old git history stays "
                "decryptable by the revoked key):"
            )
            for kp in key_paths:
                click.echo(f"    {kp}")

    click.echo()
    if revoked:
        click.echo(f"Revoked from: {', '.join(revoked)}")
    if not_listed:
        click.echo(f"Not a recipient of: {', '.join(not_listed)}")
    return 0


# ---------------------------------------------------------------- keychain group


@secret.group("keychain")
def secret_keychain():
    """Manage the OS-level age private key storage (keychain/gpg file)."""


@secret_keychain.command("status")
def keychain_status():
    """Print the backend state, this machine's age key, and stored labels."""
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
            click.echo(
                "Enroll it into the profiles you need: "
                "dotfiles secret enroll -p <profile>"
            )
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
    """Designate THIS machine's age key as the escrow key (save to 1Password).

    This is a deliberate escrow action, not automatic: it writes the private
    key to the 1Password Secure Note titled "{title}". A profile only trusts
    the escrow key once you also enroll its PUBLIC key as a recipient
    (`dotfiles secret enroll` from this machine, or add it to that profile's
    .sops.yaml). No profile is granted escrow implicitly.
    """.format(title=OP_ITEM_TITLE)
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

    click.echo(
        f"Age private key saved to 1Password item '{OP_ITEM_TITLE}' as the "
        f"escrow key.\nEnroll its public key into profiles that should trust "
        f"escrow: dotfiles secret enroll -p <profile>."
    )


@secret_keychain.command("rm")
@click.argument("label", required=False)
@click.option(
    "--age",
    "rm_age",
    is_flag=True,
    help="Remove this machine's stored age private key.",
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

    Pass --age to remove this machine's age private key, or LABEL to remove a
    leftover per-profile Ansible Vault password (unused after migration).
    """
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
    "--from",
    "from_path",
    default=None,
    help="Import an existing age identity file instead of generating a new key.",
)
def secret_init(from_path: str | None):
    """Provision THIS machine's age key and report per-profile enrollment.

    Looks for this machine's age key in the keychain. If absent, imports one
    from --from <path> (or an interactively supplied path) when given,
    otherwise generates a fresh keypair. The private key is stored in this
    machine's keychain and never printed; the public key is shown. Finally,
    reports for each profile whether this machine is already a recipient.

    Unlike a shared-key model, this never pulls a key from 1Password: the
    escrow key there is opt-in per profile and is not a machine's own identity.
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
        _report_enrollment(public_key)
        return 0

    private_key = _load_identity_to_import(from_path)

    if private_key is None:
        try:
            private_key, public_key = generate_keypair()
        except RuntimeError as exc:
            click.echo(f"Error generating keypair: {exc}", err=True)
            sys.exit(1)
        source_msg = "Generated and stored a new age private key in the keychain."
    else:
        try:
            public_key = get_public_key_from_private(private_key)
        except RuntimeError as exc:
            click.echo(f"Error deriving public key: {exc}", err=True)
            sys.exit(1)
        source_msg = "Imported age private key and stored it in the keychain."

    try:
        write_age_key(private_key)
    except Exception as exc:
        click.echo(f"Error storing age private key: {exc}", err=True)
        sys.exit(1)

    click.echo(source_msg)
    click.echo(f"\nPublic key: {public_key}")
    _report_enrollment(public_key)

    click.echo(
        "\nNext steps:"
        "\n  1. Enroll this machine into the profiles you need:"
        "\n       dotfiles secret enroll -p <profile>   (or --all)"
        "\n  2. Optionally designate this key as escrow: "
        "dotfiles secret keychain backup"
        "\n  3. Set or read secrets: dotfiles secret set/get -p <profile> <key>"
    )
    return 0


def _load_identity_to_import(from_path: str | None) -> str | None:
    """Return age private key text to import, or None to generate a fresh one.

    Reads --from when given; otherwise, on an interactive TTY, offers to import
    from a path (blank answer → generate). Validates the AGE-SECRET-KEY marker.
    """
    path = from_path
    if path is None and sys.stdin.isatty():
        answer = click.prompt(
            "Path to an existing age identity file to import "
            "(leave blank to generate a new key)",
            default="",
            show_default=False,
        ).strip()
        path = answer or None

    if path is None:
        return None

    try:
        key_text = Path(path).expanduser().read_text()
    except OSError as exc:
        click.echo(f"Error: could not read identity file {path!r}: {exc}", err=True)
        sys.exit(1)
    if "AGE-SECRET-KEY-" not in key_text:
        click.echo(
            f"Error: {path!r} does not contain an age private key "
            f"(missing 'AGE-SECRET-KEY-').",
            err=True,
        )
        sys.exit(1)
    return key_text


def _report_enrollment(public_key: str) -> None:
    """Report, per profile with a .sops.yaml, whether ``public_key`` is enrolled."""
    profiles = sops.get_profiles_with_sops_config()
    if not profiles:
        click.echo(
            "\nNo profiles carry a .sops.yaml yet. Enroll this machine to create "
            "one: dotfiles secret enroll -p <profile>."
        )
        return

    click.echo("\nEnrollment status:")
    for prof in profiles:
        recipients = sops.get_configured_recipients(prof)
        mark = "enrolled" if public_key in recipients else "NOT enrolled"
        click.echo(f"  {prof}: {mark}")
