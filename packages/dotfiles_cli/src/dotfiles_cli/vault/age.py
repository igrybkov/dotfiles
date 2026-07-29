"""Age identity management — per-machine private key in the OS keychain.

Under the sops migration each machine has exactly ONE age keypair. The private
key text (the full multi-line output of ``age-keygen``) lives in the OS
keychain under the dedicated label ``_age_private_key`` via the same backend
that used to hold per-profile Ansible Vault passwords. The leading underscore
keeps it from colliding with any profile name.

Recipients (public keys) are enrolled per profile in each profile's
``.sops.yaml`` — see ``vault.sops``. Consumers that need to decrypt read this
machine's key with ``read_age_key()`` and export it as ``SOPS_AGE_KEY`` for
sops subprocesses.

The 1Password helpers here are generic key mirrors. In the per-machine model
they back the opt-in *escrow* key (a designated key whose public half a
profile may list as a recipient so it can recover that profile's secrets);
they are never used to seed a machine's own keychain automatically.
"""

from __future__ import annotations

import functools
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .backend import get_backend

# Backend label for this machine's age private key. Leading underscore avoids
# any clash with a profile name (profiles never start with an underscore).
AGE_KEY_LABEL = "_age_private_key"

# Bound on the `mise where` lookup. Generous for local metadata, but this runs
# on the path that spawns MCP servers, and a hung resolve would look to a host
# like a hung server rather than a missing tool.
_MISE_LOOKUP_TIMEOUT = 10.0

# `mise where` can fail to launch (OSError) or be killed/time out
# (SubprocessError). Named tuple keeps the formatter from rewriting an
# inline `except (A, B):` into the 3.14-only bare-tuple form.
_MISE_RUN_ERRORS = (OSError, subprocess.SubprocessError)


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
    except _MISE_RUN_ERRORS:
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
    """Read this machine's age private key from the OS keychain, or None."""
    backend = get_backend()
    try:
        return backend.read(AGE_KEY_LABEL)
    except Exception:
        return None


# Bound on the fresh-exec subprocess below. Generous for a local keychain
# read, but this can run on the path that spawns MCP servers, and a hung
# read would look to a host like a hung server rather than a keychain
# prompt waiting on Touch ID / a password.
_READ_AGE_KEY_SUBPROCESS_TIMEOUT = 10.0


def read_age_key_via_subprocess(
    timeout: float = _READ_AGE_KEY_SUBPROCESS_TIMEOUT,
) -> str | None:
    """Read this machine's age key via a fresh subprocess exec.

    ``read_age_key()`` calls python-keyring in-process, which touches the
    macOS Security framework. Ansible runs lookup plugins inside forked
    worker processes (fork without exec) — and macOS aborts any process
    that touches the Security framework after such a fork, killing the
    worker. Shelling out to a fresh ``python -m`` exec sidesteps the crash
    entirely, since the new process was never forked.

    Prefer ``read_age_key()`` for normal (non-forked) callers, e.g. the
    ``dotfiles secret`` CLI commands — the subprocess round-trip here is
    unnecessary overhead there. This function exists specifically for
    contexts that must be safe to call from a forked worker, such as the
    ``vault_secret`` Ansible lookup.

    Returns None on any failure (timeout, missing key, subprocess error) —
    matches ``read_age_key()``'s behavior of never raising for "no key".
    """
    try:
        result = subprocess.run(
            [sys.executable, "-m", "dotfiles_cli.vault._read_age_key_stdout"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    key = result.stdout.strip()
    return key or None


def write_age_key(private_key: str) -> None:
    """Store this machine's age private key (replacing any prior value)."""
    backend = get_backend()
    backend.ensure_ready()
    backend.write(AGE_KEY_LABEL, private_key)


def delete_age_key() -> None:
    """Remove this machine's age private key from the keychain. No-op if absent."""
    backend = get_backend()
    backend.delete(AGE_KEY_LABEL)


# ---------------------------------------------------------------------------
# 1Password-backed key storage (escrow key mirror, cross-machine bootstrap)
# ---------------------------------------------------------------------------

# Default title of the 1Password Secure Note that holds an age private key.
# Used for the opt-in escrow key. Parametrized so callers can mirror other
# keys (e.g. a per-purpose escrow) under a different title if needed.
OP_ITEM_TITLE = "dotfiles-age-key"


def is_op_available() -> bool:
    """Return True if the 1Password CLI (``op``) is on PATH."""
    return shutil.which("op") is not None


def read_age_key_from_op(item_title: str = OP_ITEM_TITLE) -> str | None:
    """Read an age private key from 1Password, or None if unavailable/absent.

    Uses ``op item get`` to fetch the ``notesPlain`` field of the Secure Note
    titled ``item_title``. Returns ``None`` on any failure (op not installed,
    not signed in, item missing, or value does not look like an age private
    key).
    """
    if not is_op_available():
        return None
    result = subprocess.run(
        ["op", "item", "get", item_title, "--fields", "label=notesPlain"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    key = result.stdout.strip()
    return key if "AGE-SECRET-KEY-" in key else None


def write_age_key_to_op(
    private_key: str, item_title: str = OP_ITEM_TITLE, vault: str | None = None
) -> None:
    """Store an age private key in 1Password as a Secure Note.

    Creates the ``item_title`` item if it does not exist; otherwise updates
    ``notesPlain`` in place. ``vault`` pins which vault a *new* item is
    created in (op's default vault otherwise); ignored on update since the
    item already lives somewhere.

    Raises:
        RuntimeError: if ``op`` is unavailable or the operation fails.
    """
    if not is_op_available():
        raise RuntimeError(
            "op CLI not found. Install 1Password CLI: brew install 1password-cli"
        )
    # Check whether the item already exists.
    check = subprocess.run(
        ["op", "item", "get", item_title],
        capture_output=True,
        text=True,
    )
    if check.returncode == 0:
        cmd = ["op", "item", "edit", item_title, f"notesPlain={private_key}"]
    else:
        cmd = [
            "op",
            "item",
            "create",
            "--category",
            "Secure Note",
            "--title",
            item_title,
        ]
        if vault:
            cmd += ["--vault", vault]
        cmd.append(f"notesPlain={private_key}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"1Password store failed: {result.stderr.strip() or result.stdout.strip()}"
        )
