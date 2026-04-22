"""1Password fallback for vault-unlock passwords.

A thin helper, not a full `VaultBackend`. Used as a backup source when the
local backend (macOS keychain / gpg file) has no entry for a profile, or
when the entry it returned fails to decrypt the corresponding vault.

Storage convention:
    Env var `DOTFILES_VAULT_OP_ITEM` holds a 1Password item reference of the
    form `op://<vault>/<item>`. Each profile's password lives in a custom
    field on that single item; the field label equals the profile/vault-id
    label. Per-profile reads are `op read op://<vault>/<item>/<label>`.

Design choices:
    - Hot-path reads return `None` on any failure (missing field, unauth'd
      session, `op` not installed). Callers decide how to escalate — the
      fallback must never break the primary path.
    - Writes surface errors so sync/push flows can report them to the user.
    - All `op` invocations accept `op --account` if `OP_ACCOUNT` is set,
      letting multi-account users pin the right session.
"""

from __future__ import annotations

import os
import shutil
import subprocess

ENV_ITEM = "DOTFILES_VAULT_OP_ITEM"
ENV_ACCOUNT = "OP_ACCOUNT"


def is_configured() -> bool:
    """True if `DOTFILES_VAULT_OP_ITEM` is set (non-blank) and `op` is on PATH."""
    return bool(os.environ.get(ENV_ITEM, "").strip()) and shutil.which("op") is not None


def _item_ref() -> str | None:
    """Return the configured `op://vault/item` reference, or None."""
    ref = os.environ.get(ENV_ITEM, "").strip()
    return ref or None


def _base_cmd() -> list[str]:
    """Build the base `op` command with optional --account flag."""
    cmd = ["op"]
    account = os.environ.get(ENV_ACCOUNT, "").strip()
    if account:
        cmd.extend(["--account", account])
    return cmd


def read_field(label: str) -> str | None:
    """Return the password stored under `label` in the configured 1P item.

    Returns None on any failure (not configured, `op` missing, unauthenticated,
    field absent). Never raises — the caller decides how to escalate.
    """
    if not is_configured():
        return None

    ref = _item_ref()
    if ref is None:
        return None

    # `op read op://vault/item/field` — -n suppresses the trailing newline.
    cmd = [*_base_cmd(), "read", "-n", f"{ref}/{label}"]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None

    if result.returncode != 0:
        return None
    password = result.stdout
    return password if password else None


def _parse_item_ref(ref: str) -> tuple[str, str] | None:
    """Split `op://<vault>/<item>` into (vault, item). Returns None if malformed."""
    prefix = "op://"
    if not ref.startswith(prefix):
        return None
    remainder = ref[len(prefix) :].strip("/")
    parts = remainder.split("/", 1)
    if len(parts) != 2:
        return None
    vault, item = parts[0].strip(), parts[1].strip()
    if not vault or not item:
        return None
    return vault, item


def _item_exists(vault: str, title: str) -> bool:
    """True if the item `title` exists in `vault`. None-safe on op failures."""
    cmd = [
        *_base_cmd(),
        "item",
        "get",
        title,
        f"--vault={vault}",
        "--format=json",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def write_field(label: str, value: str) -> None:
    """Set the `label` field on the configured 1P item to `value`.

    Creates the item first if it doesn't exist (category: Password, title
    taken from the `op://vault/item` reference). Raises `OnePasswordError`
    on failure — intended for sync/push flows where the user is waiting
    for feedback.
    """
    if not is_configured():
        raise OnePasswordError(f"{ENV_ITEM} is not set, or `op` CLI is not on PATH.")

    ref = _item_ref()
    assert ref is not None  # guaranteed by is_configured()

    parsed = _parse_item_ref(ref)
    if parsed is None:
        raise OnePasswordError(
            f"{ENV_ITEM}={ref!r} is not a valid op://vault/item reference."
        )
    vault, title = parsed

    assignment = f"{label}[password]={value}"

    if not _item_exists(vault, title):
        # Login category has no required fields and accepts arbitrary concealed
        # custom fields — unlike Password category, which requires its built-in
        # main password to be non-empty and would reject edits that only set
        # custom fields.
        cmd = [
            *_base_cmd(),
            "item",
            "create",
            "--category=Login",
            f"--vault={vault}",
            f"--title={title}",
            assignment,
        ]
        _run_op_write(cmd, "op item create")
        return

    cmd = [
        *_base_cmd(),
        "item",
        "edit",
        title,
        f"--vault={vault}",
        assignment,
    ]
    _run_op_write(cmd, "op item edit")


def _run_op_write(cmd: list[str], label_for_error: str) -> None:
    """Run an `op` write command, raising OnePasswordError on any failure."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise OnePasswordError(f"`{label_for_error}` failed to run: {exc}") from exc

    if result.returncode != 0:
        raise OnePasswordError(
            f"`{label_for_error}` returned {result.returncode}: "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )


class OnePasswordError(RuntimeError):
    """Raised when a 1Password write operation fails."""
