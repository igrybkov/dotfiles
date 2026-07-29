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

import functools
import os
import shutil
import subprocess
from pathlib import Path

from .backend import get_backend

# Backend label for the age private key. Leading underscore avoids any clash
# with a profile name (profiles never start with an underscore).
AGE_KEY_LABEL = "_age_private_key"

# Bound on the `mise where` lookup. Generous for local metadata, but this runs
# on the path that spawns MCP servers, and a hung resolve would look to a host
# like a hung server rather than a missing tool.
_MISE_LOOKUP_TIMEOUT = 10.0


def is_age_keygen_available() -> bool:
    """Return True if ``age-keygen`` is on PATH."""
    return shutil.which("age-keygen") is not None


def _find_mise() -> str | None:
    """Locate the mise executable, on PATH or via the repo's vendored shim.

    Processes launched outside a shell — a GUI MCP host, launchd, cron — get
    ``PATH=/usr/bin:/bin:/usr/sbin:/sbin`` and never see an ambient mise. But
    this repo vendors a self-contained mise bootstrap at ``bin/mise`` (own
    project-local install under ``.mise/``, no Homebrew or system mise
    required), so falling back to it is safe rather than guessing at system
    install locations that may not exist or may be a different version.
    """
    found = shutil.which("mise")
    if found:
        return found

    # Imported lazily: `constants` is a leaf today, and keeping this edge out of
    # module scope avoids growing the import graph around vault.sops -> vault.age.
    from ..constants import get_dotfiles_dir

    candidate = Path(get_dotfiles_dir()) / "bin" / "mise"
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return str(candidate)
    return None


def _mise_tool_path(tool: str) -> str | None:
    """Ask mise where it installed ``tool``, or None if it can't say.

    ``-C`` pins the lookup to this repo's ``mise.toml`` so another project's
    active config can't answer with a different version.
    """
    mise = _find_mise()
    if mise is None:
        return None

    # Imported lazily: `constants` is a leaf today, and keeping this edge out of
    # module scope avoids growing the import graph around vault.sops -> vault.age.
    from ..constants import get_dotfiles_dir

    try:
        result = subprocess.run(
            [mise, "where", tool, "-C", str(get_dotfiles_dir())],
            capture_output=True,
            text=True,
            timeout=_MISE_LOOKUP_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None

    candidate = Path(result.stdout.strip()) / tool
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return str(candidate)
    return None


@functools.lru_cache(maxsize=1)
def resolve_sops() -> str | None:
    """Return the path to the ``sops`` executable, or None if unavailable.

    PATH wins when it has an answer. Otherwise fall back to the version mise
    pins for this repo, because the CLI is routinely run from contexts that
    never activated mise — MCP servers spawned by a host, cron, launchd — and
    mise only puts sops on PATH for shells started inside the repo. Depending on
    ambient PATH alone made secret resolution fail in exactly those contexts
    while working fine interactively.

    Cached because a single command would otherwise pay for the lookup several
    times over: the availability check, then each sops invocation. Call
    ``resolve_sops.cache_clear()`` if a test changes what is installed.
    """
    return shutil.which("sops") or _mise_tool_path("sops")


def is_sops_available() -> bool:
    """Return True if ``sops`` can be found, on PATH or via mise."""
    return resolve_sops() is not None


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
