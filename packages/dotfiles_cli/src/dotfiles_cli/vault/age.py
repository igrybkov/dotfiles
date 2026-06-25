"""Age identity management — private key stored in OS keychain.

A single age keypair protects every profile's sops-encrypted ``secrets.yml``.
The private key text (the full multi-line output of ``age-keygen``) lives in
the OS keychain under the dedicated label ``_age_private_key`` via the same
backend that used to hold per-profile Ansible Vault passwords. The leading
underscore keeps it from colliding with any profile name.

Consumers that need to decrypt (e.g. ``vault.sops``) read the key with
``read_age_key()`` and export it as ``SOPS_AGE_KEY`` for sops subprocesses.
"""

from __future__ import annotations

import shutil
import subprocess

from .backend import get_backend

# Backend label for the age private key. Leading underscore avoids any clash
# with a profile name (profiles never start with an underscore).
AGE_KEY_LABEL = "_age_private_key"


def is_age_keygen_available() -> bool:
    """Return True if ``age-keygen`` is on PATH."""
    return shutil.which("age-keygen") is not None


def is_sops_available() -> bool:
    """Return True if ``sops`` is on PATH."""
    return shutil.which("sops") is not None


def generate_keypair() -> tuple[str, str]:
    """Generate a fresh age keypair.

    Returns ``(private_key_text, public_key)`` where ``private_key_text`` is
    the *full* ``age-keygen`` output (a created-at comment, the public-key
    comment, then the ``AGE-SECRET-KEY-...`` line) and ``public_key`` is the
    ``age1...`` recipient string extracted from the ``# public key:`` comment.

    Requires ``age-keygen`` on PATH.

    Raises:
        RuntimeError: if ``age-keygen`` is missing or exits non-zero.
    """
    if not is_age_keygen_available():
        raise RuntimeError(
            "age-keygen not found on PATH. Install age: brew install age"
        )

    try:
        result = subprocess.run(
            ["age-keygen"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"age-keygen failed: {exc.stderr.strip() or exc}") from exc

    private_key_text = result.stdout
    public_key = _extract_public_key_comment(private_key_text)
    if public_key is None:
        # Fall back to deriving it from the private key directly.
        public_key = get_public_key_from_private(private_key_text)
    return private_key_text, public_key


def _extract_public_key_comment(private_key_text: str) -> str | None:
    """Pull the recipient out of the ``# public key: age1...`` comment line."""
    for line in private_key_text.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("# public key:"):
            return stripped.split(":", 1)[1].strip()
    return None


def get_public_key_from_private(private_key: str) -> str:
    """Derive the age public key from private key text via ``age-keygen -y``.

    ``age-keygen -y`` reads an identity from stdin and writes the matching
    recipient (``age1...``) to stdout. The identity parser ignores comment
    and blank lines, so passing the full ``age-keygen`` output is fine.

    Raises:
        RuntimeError: if ``age-keygen`` is missing or exits non-zero.
    """
    if not is_age_keygen_available():
        raise RuntimeError(
            "age-keygen not found on PATH. Install age: brew install age"
        )
    try:
        result = subprocess.run(
            ["age-keygen", "-y"],
            input=private_key,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"age-keygen -y failed: {exc.stderr.strip() or exc}"
        ) from exc
    public_key = result.stdout.strip()
    if not public_key:
        raise RuntimeError("age-keygen -y returned an empty public key.")
    return public_key


def read_age_key() -> str | None:
    """Read the age private key from the OS keychain, or None if absent."""
    backend = get_backend()
    try:
        return backend.read(AGE_KEY_LABEL)
    except Exception:
        return None


def write_age_key(private_key: str) -> None:
    """Store the age private key in the OS keychain (replacing any prior value)."""
    backend = get_backend()
    backend.ensure_ready()
    backend.write(AGE_KEY_LABEL, private_key)


def delete_age_key() -> None:
    """Remove the age private key from the OS keychain. No-op if absent."""
    backend = get_backend()
    backend.delete(AGE_KEY_LABEL)


# ---------------------------------------------------------------------------
# 1Password-backed key storage (for cross-machine bootstrap)
# ---------------------------------------------------------------------------

# Title of the 1Password Secure Note that holds the age private key.
OP_ITEM_TITLE = "dotfiles-age-key"


def is_op_available() -> bool:
    """Return True if the 1Password CLI (``op``) is on PATH."""
    return shutil.which("op") is not None


def read_age_key_from_op() -> str | None:
    """Read the age private key from 1Password, or None if unavailable/absent.

    Uses ``op item get`` to fetch the ``notesPlain`` field of the
    ``dotfiles-age-key`` Secure Note. Returns ``None`` on any failure (op not
    installed, not signed in, item missing, or value does not look like an age
    private key).
    """
    if not is_op_available():
        return None
    result = subprocess.run(
        ["op", "item", "get", OP_ITEM_TITLE, "--fields", "label=notesPlain"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    key = result.stdout.strip()
    return key if "AGE-SECRET-KEY-" in key else None


def write_age_key_to_op(private_key: str) -> None:
    """Store the age private key in 1Password as a Secure Note.

    Creates the ``dotfiles-age-key`` item if it does not exist; otherwise
    updates ``notesPlain`` in place.

    Raises:
        RuntimeError: if ``op`` is unavailable or the operation fails.
    """
    if not is_op_available():
        raise RuntimeError(
            "op CLI not found. Install 1Password CLI: brew install 1password-cli"
        )
    # Check whether the item already exists.
    check = subprocess.run(
        ["op", "item", "get", OP_ITEM_TITLE],
        capture_output=True,
        text=True,
    )
    if check.returncode == 0:
        cmd = ["op", "item", "edit", OP_ITEM_TITLE, f"notesPlain={private_key}"]
    else:
        cmd = [
            "op",
            "item",
            "create",
            "--category",
            "Secure Note",
            "--title",
            OP_ITEM_TITLE,
            f"notesPlain={private_key}",
        ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"1Password store failed: {result.stderr.strip() or result.stdout.strip()}"
        )
