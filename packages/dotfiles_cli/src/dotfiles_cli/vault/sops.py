"""sops-based secret operations.

Replaces the Ansible Vault path in ``operations.py`` for the sops migration.
A single age keypair (private key in the OS keychain, public key recorded in
``.sops.yaml``) protects every profile's ``secrets.yml``.

All sops subprocesses run with ``cwd=DOTFILES_DIR`` so sops can discover the
repo-root ``.sops.yaml`` and apply its ``creation_rules`` ``path_regex`` (the
regex is a substring match, so absolute file paths still match). When a
decrypt is involved, the age private key is injected as ``SOPS_AGE_KEY``;
callers may override with an explicit ``age_key`` argument.
"""

from __future__ import annotations

import io
import os
import re
import subprocess
from pathlib import Path

import yaml

from ..constants import get_dotfiles_dir
from ..profiles import get_profile_names, get_profile_path
from .age import read_age_key


class SopsError(RuntimeError):
    """Raised when a sops invocation fails or sops is unavailable."""


# --------------------------------------------------------------- file helpers


def get_secrets_file(location: str) -> Path:
    """Return the path to the ``secrets.yml`` for a profile.

    Mirrors ``operations.get_secrets_file`` so the two backends agree on
    layout, including multi-level profiles (e.g. ``myrepo-work`` maps to
    ``profiles/myrepo/work/secrets.yml``).

    Raises:
        ValueError: if the profile is not found.
    """
    profile_path = get_profile_path(location)
    if profile_path is None:
        raise ValueError(f"Profile not found: {location}")
    return profile_path / "secrets.yml"


def get_all_secret_locations() -> list[str]:
    """Return all profile names that could hold secrets."""
    return get_profile_names()


def is_sops_encrypted(path: Path) -> bool:
    """Return True if ``path`` is a sops-encrypted YAML file.

    sops embeds a top-level ``sops:`` mapping (with ``version``, ``mac``,
    recipient metadata, …). We parse the YAML and look for that key. Parsing
    is cheap and far more robust than a string prefix check, since sops does
    not put its metadata at the top of the file.
    """
    if not path.exists():
        return False
    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError, OSError:
        return False
    return isinstance(data, dict) and isinstance(data.get("sops"), dict)


def get_profiles_with_sops_secrets() -> list[str]:
    """Return profiles whose ``secrets.yml`` is sops-encrypted."""
    found: list[str] = []
    for profile in get_profile_names():
        profile_path = get_profile_path(profile)
        if profile_path is None:
            continue
        if is_sops_encrypted(profile_path / "secrets.yml"):
            found.append(profile)
    return found


# Kept under the operations-compatible name so callers can swap the import
# without renaming. Returns sops-encrypted profiles (the migration target).
def get_profiles_with_secrets() -> list[str]:
    """Alias for :func:`get_profiles_with_sops_secrets`."""
    return get_profiles_with_sops_secrets()


# ----------------------------------------------------------- .sops.yaml config


def get_sops_config_path() -> Path:
    """Path to the repo-root ``.sops.yaml``."""
    return Path(get_dotfiles_dir()) / ".sops.yaml"


def get_configured_recipients() -> list[str]:
    """Return the age recipients currently listed in ``.sops.yaml``.

    Reads the first creation rule's ``age`` field (string or list). Empty
    placeholders (``""``) are filtered out. Returns ``[]`` when the config is
    missing, unparseable, or has no recipient yet.
    """
    path = get_sops_config_path()
    if not path.exists():
        return []
    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError, OSError:
        return []
    if not isinstance(data, dict):
        return []
    recipients: list[str] = []
    for rule in data.get("creation_rules", []) or []:
        if not isinstance(rule, dict):
            continue
        age = rule.get("age")
        if isinstance(age, str):
            recipients.extend(_split_recipients(age))
        elif isinstance(age, list):
            for item in age:
                if isinstance(item, str):
                    recipients.extend(_split_recipients(item))
    # De-dup, preserve order, drop blanks.
    seen: list[str] = []
    for r in recipients:
        if r and r not in seen:
            seen.append(r)
    return seen


def _split_recipients(value: str) -> list[str]:
    """Split a possibly comma/space/newline-separated recipient string."""
    return [p for p in re.split(r"[,\s]+", value.strip()) if p]


def set_sops_recipient(public_key: str) -> None:
    """Write ``public_key`` as the sole age recipient in every creation rule.

    Targeted text replacement of each ``age:`` value so the explanatory
    comment header in ``.sops.yaml`` survives (PyYAML round-tripping would
    drop it). Matches both ``age: ""`` placeholders and any prior single-line
    ``age: <value>``.

    Raises:
        SopsError: if ``.sops.yaml`` is missing or no ``age:`` line is found.
    """
    path = get_sops_config_path()
    if not path.exists():
        raise SopsError(f".sops.yaml not found at {path}")
    text = path.read_text()
    # Replace the value after `age:` on each creation-rule line, preserving
    # the original indentation. Only single-line scalar form is supported.
    pattern = re.compile(r"^(\s*age:).*$", re.MULTILINE)
    new_text, count = pattern.subn(rf'\1 "{public_key}"', text)
    if count == 0:
        raise SopsError(
            f"No 'age:' line found in {path}; cannot set recipient automatically."
        )
    path.write_text(new_text)


# ------------------------------------------------------------- sops plumbing


def _sops_env(age_key: str | None = None) -> dict[str, str]:
    """Build the subprocess env, injecting ``SOPS_AGE_KEY`` when a key exists.

    Precedence: explicit ``age_key`` argument → keychain (`read_age_key`) →
    whatever the caller's environment already provides. We only set the var
    when we actually have a key, so a pre-set ``SOPS_AGE_KEY`` /
    ``SOPS_AGE_KEY_FILE`` in the environment is preserved when the keychain
    is empty.
    """
    env = dict(os.environ)
    key = age_key if age_key is not None else read_age_key()
    if key:
        env["SOPS_AGE_KEY"] = key
    return env


def _run_sops(
    args: list[str],
    *,
    age_key: str | None = None,
    inject_key: bool = True,
    capture: bool = True,
) -> subprocess.CompletedProcess:
    """Run ``sops`` from the repo root.

    Args:
        args: arguments after the ``sops`` executable.
        age_key: explicit private key; only consulted when ``inject_key``.
        inject_key: whether to add ``SOPS_AGE_KEY`` (decrypt operations need
            it; pure encrypt operations only need ``.sops.yaml`` recipients).
        capture: capture stdout/stderr (False for interactive ``sops edit``).

    Raises:
        SopsError: if ``sops`` is not on PATH.
    """
    import shutil

    if shutil.which("sops") is None:
        raise SopsError("sops not found on PATH. Install sops: brew install sops")

    env = _sops_env(age_key) if inject_key else dict(os.environ)
    return subprocess.run(
        ["sops", *args],
        cwd=get_dotfiles_dir(),
        env=env,
        capture_output=capture,
        text=True,
    )


def _dot_to_extract(key_path: str) -> str:
    """Convert dot notation to a sops ``--extract`` path.

    ``"mcp.github.token"`` -> ``'["mcp"]["github"]["token"]'``.
    """
    parts = [p for p in key_path.split(".") if p != ""]
    if not parts:
        raise ValueError("Empty key path")
    return "".join(f'["{p}"]' for p in parts)


# ----------------------------------------------------------------- decryption


def decrypt_all(profile: str, age_key: str | None = None) -> dict:
    """Decrypt an entire profile's ``secrets.yml`` to a Python dict.

    Runs ``sops -d --output-type json <path>``. When ``age_key`` is None the
    key is taken from the keychain (or a pre-set ``SOPS_AGE_KEY``).

    Raises:
        ValueError: if the profile is unknown.
        SopsError: if decryption fails.
    """
    path = get_secrets_file(profile)
    return decrypt_to_dict(path, age_key=age_key)


def decrypt_to_dict(path: Path, age_key: str | None = None) -> dict:
    """Decrypt a sops file at ``path`` to a Python dict.

    Raises:
        SopsError: if decryption fails.
    """
    import json

    result = _run_sops(["-d", "--output-type", "json", str(path)], age_key=age_key)
    if result.returncode != 0:
        raise SopsError(
            f"sops decrypt failed for {path}: {result.stderr.strip() or 'unknown error'}"
        )
    try:
        data = json.loads(result.stdout) if result.stdout.strip() else {}
    except json.JSONDecodeError as exc:
        raise SopsError(f"sops produced invalid JSON for {path}: {exc}") from exc
    return data or {}


def decrypt_key(profile: str, key_path: str, age_key: str | None = None) -> str:
    """Decrypt a single value from a profile's ``secrets.yml``.

    ``key_path`` is dot notation (e.g. ``mcp.github.token``). Runs
    ``sops -d --extract '["mcp"]["github"]["token"]' <path>``. For a string
    leaf sops prints the raw value with no surrounding quotes.

    Raises:
        ValueError: if the profile is unknown or the key path is empty.
        SopsError: if the key is missing or decryption fails.
    """
    path = get_secrets_file(profile)
    extract = _dot_to_extract(key_path)
    result = _run_sops(["-d", "--extract", extract, str(path)], age_key=age_key)
    if result.returncode != 0:
        raise SopsError(
            f"sops could not extract {key_path!r} from {path}: "
            f"{result.stderr.strip() or 'key not found or decryption failed'}"
        )
    # --extract on a scalar emits a trailing newline; strip a single one.
    return result.stdout.rstrip("\n")


# ----------------------------------------------------------------- encryption


def encrypt_file(path: Path) -> tuple[int, str, str]:
    """Encrypt a plaintext YAML file in place with sops.

    Runs ``sops --encrypt --in-place <path>``. Recipients come from
    ``.sops.yaml`` (no private key needed). Returns ``(returncode, stdout,
    stderr)`` so callers can surface the failure — important because the
    file is plaintext on disk until this succeeds.
    """
    result = _run_sops(["--encrypt", "--in-place", str(path)], inject_key=False)
    return result.returncode, result.stdout, result.stderr


def write_and_encrypt(path: Path, data: dict) -> None:
    """Write ``data`` as plaintext YAML, then encrypt in place with sops.

    sops applies ``.sops.yaml`` creation rules by matching the *file path*
    against ``path_regex`` — so encryption must happen at the real ``path``
    (a temp name like ``secrets.yml.tmp`` would not match ``secrets\\.yml$``).
    To avoid destroying the prior encrypted copy when ``sops --encrypt``
    fails, any existing file is backed up to a sibling ``.sops-bak`` first and
    restored on failure. On any error the real path is never left containing
    plaintext.

    Raises:
        SopsError: if encryption fails (original restored, no plaintext left).
    """
    backup: Path | None = None
    if path.exists():
        backup = path.with_name(path.name + ".sops-bak")
        backup.write_bytes(path.read_bytes())
        try:
            backup.chmod(0o600)
        except OSError:
            pass

    buf = io.StringIO()
    yaml.dump(data, buf, default_flow_style=False, sort_keys=False)
    path.write_text(buf.getvalue())
    try:
        path.chmod(0o600)
    except OSError:
        pass

    rc, _, stderr = encrypt_file(path)
    if rc != 0:
        # Encryption failed: restore the prior encrypted copy (or remove the
        # plaintext stub for a brand-new file) so plaintext never lingers.
        if backup is not None:
            path.write_bytes(backup.read_bytes())
            backup.unlink(missing_ok=True)
        else:
            path.unlink(missing_ok=True)
        raise SopsError(
            f"sops failed to encrypt {path}: {stderr.strip() or 'unknown error'}. "
            f"No changes were written (original preserved)."
        )

    # Success: drop the backup.
    if backup is not None:
        backup.unlink(missing_ok=True)


def reencrypt_with_updated_keys(path: Path) -> tuple[int, str, str]:
    """Re-encrypt an existing sops file to match updated ``.sops.yaml`` keys.

    Runs ``sops updatekeys -y <path>``. This decrypts the data key with the
    current age private key and re-wraps it for the recipient set in
    ``.sops.yaml`` — so the private key is injected. Returns
    ``(returncode, stdout, stderr)``.
    """
    result = _run_sops(["updatekeys", "-y", str(path)])
    return result.returncode, result.stdout, result.stderr


# ----------------------------------------------------------------- editing


def run_sops_edit(path: Path, editor: str = "vim") -> int:
    """Open a sops-encrypted file in an editor and re-encrypt on save.

    Runs ``sops edit <path>`` (interactive; decrypts to a tmpfile, re-encrypts
    on exit). The age private key is injected so the decrypt step works, and
    ``EDITOR`` is set so sops launches the requested editor. Returns the sops
    exit code.

    Raises:
        SopsError: if ``sops`` is not on PATH.
    """
    import shutil

    if shutil.which("sops") is None:
        raise SopsError("sops not found on PATH. Install sops: brew install sops")

    env = _sops_env()
    env["EDITOR"] = editor
    return subprocess.run(
        ["sops", "edit", str(path)],
        cwd=get_dotfiles_dir(),
        env=env,
    ).returncode
