"""sops-based secret operations (per-machine key model).

Replaces the Ansible Vault path in ``operations.py`` for the sops migration.
Each machine holds one age keypair (private key in the OS keychain — see
``vault.age``); each profile carries its OWN ``.sops.yaml`` next to its
``secrets.yml`` listing the age *public keys* allowed to decrypt it. Recipient
sets diverge per profile on purpose: a profile can enroll two machines plus an
opt-in escrow key while another enrolls just one — so there is no single global
recipient list.

sops discovers its config from the current directory, not from the file being
encrypted, so every encrypt / ``updatekeys`` invocation is pinned to the
profile-local config with an explicit ``--config <profile>/.sops.yaml``. Decrypt
reads recipient metadata straight from the ciphertext and needs no config; when
a decrypt is involved this machine's age private key is injected as
``SOPS_AGE_KEY`` (callers may override with an explicit ``age_key``).
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
from .age import read_age_key, resolve_sops

# Shown when sops can be found neither on PATH nor via mise. Points at `mise
# install` because that is how this repo pins it (see mise.toml); suggesting
# Homebrew sent people to install a second, unpinned copy.
SOPS_MISSING_MESSAGE = (
    "sops not found. This repo pins it with mise — run: mise install "
    "(or install sops yourself and put it on PATH)"
)

# Basename of each profile's sops recipient config, a sibling of secrets.yml.
SOPS_CONFIG_NAME = ".sops.yaml"

# yaml.safe_load raises YAMLError on malformed YAML and OSError on read
# failures; both mean "not a usable file" here. Named so the formatter
# can't reduce an inline `except (A, B):` to the 3.14-only bare-tuple form
# `except A, B:` (a SyntaxError on older interpreters).
_YAML_LOAD_ERRORS = (yaml.YAMLError, OSError)


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
    except _YAML_LOAD_ERRORS:
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


def get_sops_config_path(profile: str) -> Path:
    """Path to a profile's ``.sops.yaml`` (sibling of its ``secrets.yml``).

    Raises:
        ValueError: if the profile is not found.
    """
    profile_path = get_profile_path(profile)
    if profile_path is None:
        raise ValueError(f"Profile not found: {profile}")
    return profile_path / SOPS_CONFIG_NAME


def _config_for_secrets(secrets_file: Path) -> Path:
    """Return the ``.sops.yaml`` that governs ``secrets_file`` (its sibling)."""
    return secrets_file.parent / SOPS_CONFIG_NAME


def has_sops_config(profile: str) -> bool:
    """Return True if the profile has a ``.sops.yaml`` on disk."""
    try:
        return get_sops_config_path(profile).exists()
    except ValueError:
        return False


def get_profiles_with_sops_config() -> list[str]:
    """Return profiles that carry a ``.sops.yaml`` recipient config."""
    return [p for p in get_profile_names() if has_sops_config(p)]


def get_configured_recipients(profile: str) -> list[str]:
    """Return the age recipients listed in a profile's ``.sops.yaml``.

    Reads the ``age`` field of each creation rule (string or list; a string
    may be comma/space separated). Empty placeholders (``""``) are filtered.
    Returns ``[]`` when the config is missing, unparseable, or empty. The
    repo's invariant is that every creation rule shares the same recipient
    set, so the union is de-duplicated in first-seen order.
    """
    try:
        path = get_sops_config_path(profile)
    except ValueError:
        return []
    if not path.exists():
        return []
    try:
        data = yaml.safe_load(path.read_text())
    except _YAML_LOAD_ERRORS:
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


# Template for a fresh per-profile config. `{recipients}` is a comma-separated
# age recipient string. Two rules cover both `secrets.yml` and a `secrets/`
# directory; encryption always passes `--config` so the regex only needs to
# match the file's basename.
_SOPS_CONFIG_TEMPLATE = """\
---
# sops + age recipients for this profile's encrypted secrets.
#
# Managed by `dotfiles secret enroll` / `dotfiles secret revoke`. Each `age:`
# value is a comma-separated list of age public keys — one per enrolled
# machine, plus any opt-in escrow key. To add this machine:
#   dotfiles secret enroll -p <profile>
# To remove a key (e.g. a lost machine):
#   dotfiles secret revoke <age1...> -p <profile>
creation_rules:
  - path_regex: secrets\\.yml$
    age: "{recipients}"
  - path_regex: secrets/.*\\.yml$
    age: "{recipients}"
"""


def ensure_sops_config(profile: str, recipients: list[str]) -> Path:
    """Create the profile's ``.sops.yaml`` from a template if it is absent.

    No-op when the config already exists (recipients are only used to seed a
    brand-new file). Returns the config path.

    Raises:
        ValueError: if the profile is not found.
    """
    path = get_sops_config_path(profile)
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_SOPS_CONFIG_TEMPLATE.format(recipients=",".join(recipients)))
    return path


def set_sops_recipients(profile: str, recipients: list[str]) -> None:
    """Write ``recipients`` (comma-joined) as the age list in every rule.

    Targeted text replacement of each ``age:`` value so the explanatory
    comment header survives (PyYAML round-tripping would drop it). Matches
    both ``age: ""`` placeholders and any prior single-line ``age: <value>``.

    Raises:
        ValueError: if the profile is not found.
        SopsError: if ``.sops.yaml`` is missing or has no ``age:`` line.
    """
    path = get_sops_config_path(profile)
    if not path.exists():
        raise SopsError(f".sops.yaml not found at {path}")
    text = path.read_text()
    joined = ",".join(recipients)
    # Replace the value after `age:` on each creation-rule line, preserving
    # the original indentation. Only single-line scalar form is supported.
    pattern = re.compile(r"^(\s*age:).*$", re.MULTILINE)
    new_text, count = pattern.subn(rf'\1 "{joined}"', text)
    if count == 0:
        raise SopsError(
            f"No 'age:' line found in {path}; cannot set recipients automatically."
        )
    path.write_text(new_text)


def set_sops_recipient(profile: str, public_key: str) -> None:
    """Write ``public_key`` as the sole age recipient in the profile config."""
    set_sops_recipients(profile, [public_key])


def add_sops_recipient(profile: str, public_key: str) -> bool:
    """Add ``public_key`` to the profile's recipient list if not present.

    Creates a fresh ``.sops.yaml`` (seeded with just this key) when the
    profile has none yet. Returns True if the recipient set changed, False
    when ``public_key`` was already listed.

    Raises:
        ValueError: if the profile is not found.
        SopsError: if an existing config has no ``age:`` line.
    """
    if not has_sops_config(profile):
        ensure_sops_config(profile, [public_key])
        return True
    current = get_configured_recipients(profile)
    if public_key in current:
        return False
    set_sops_recipients(profile, current + [public_key])
    return True


def remove_sops_recipient(profile: str, public_key: str) -> bool:
    """Remove ``public_key`` from the profile's recipient list.

    Returns True if the recipient set changed, False when ``public_key`` was
    not listed (or the profile has no config).

    Raises:
        ValueError: if the profile is not found.
        SopsError: if the config has no ``age:`` line.
    """
    if not has_sops_config(profile):
        return False
    current = get_configured_recipients(profile)
    if public_key not in current:
        return False
    set_sops_recipients(profile, [r for r in current if r != public_key])
    return True


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
            it; pure encrypt operations only need the ``.sops.yaml``
            recipients passed via ``--config``).
        capture: capture stdout/stderr (False for interactive ``sops edit``).

    Raises:
        SopsError: if ``sops`` cannot be found.
    """
    sops_bin = resolve_sops()
    if sops_bin is None:
        raise SopsError(SOPS_MISSING_MESSAGE)

    env = _sops_env(age_key) if inject_key else dict(os.environ)
    return subprocess.run(
        [sops_bin, *args],
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


def can_decrypt(path: Path, age_key: str | None = None) -> bool:
    """Return True if ``age_key`` (or the keychain key) can decrypt ``path``.

    Used to probe which identity is usable before a ``sops updatekeys`` — the
    identity must be a recipient of the file's *current* ciphertext, which is
    exactly what a trial decrypt verifies. Runs ``sops -d`` and discards the
    plaintext; only the exit status matters.
    """
    try:
        result = _run_sops(["-d", str(path)], age_key=age_key)
    except SopsError:
        return False
    return result.returncode == 0


# ----------------------------------------------------------------- encryption


def encrypt_file(path: Path) -> tuple[int, str, str]:
    """Encrypt a plaintext YAML file in place with sops.

    Runs ``sops --config <profile>/.sops.yaml --encrypt --in-place <path>``.
    Recipients come from the profile-local ``.sops.yaml`` (no private key
    needed). ``--config`` is explicit because sops otherwise resolves config
    from the working directory, not the file's location. Returns
    ``(returncode, stdout, stderr)`` so callers can surface the failure —
    important because the file is plaintext on disk until this succeeds.
    """
    config = _config_for_secrets(path)
    result = _run_sops(
        ["--config", str(config), "--encrypt", "--in-place", str(path)],
        inject_key=False,
    )
    return result.returncode, result.stdout, result.stderr


def write_and_encrypt(path: Path, data: dict) -> None:
    """Write ``data`` as plaintext YAML, then encrypt in place with sops.

    Encryption happens at the real ``path`` (a temp name would not match the
    ``.sops.yaml`` ``path_regex``). To avoid destroying the prior encrypted
    copy when ``sops --encrypt`` fails, any existing file is backed up to a
    sibling ``.sops-bak`` first and restored on failure. On any error the real
    path is never left containing plaintext.

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


def reencrypt_with_updated_keys(
    path: Path, age_key: str | None = None
) -> tuple[int, str, str]:
    """Re-encrypt an existing sops file to match its ``.sops.yaml`` recipients.

    Runs ``sops --config <profile>/.sops.yaml updatekeys -y <path>``. This
    decrypts the data key with a current recipient's private key and re-wraps
    it for the recipient set in ``.sops.yaml`` — so the private key is
    injected (from ``age_key`` when given, else this machine's keychain key).
    Returns ``(returncode, stdout, stderr)``.
    """
    config = _config_for_secrets(path)
    result = _run_sops(
        ["--config", str(config), "updatekeys", "-y", str(path)],
        age_key=age_key,
    )
    return result.returncode, result.stdout, result.stderr


# ----------------------------------------------------------------- editing


def run_sops_edit(path: Path, editor: str = "vim") -> int:
    """Open a sops-encrypted file in an editor and re-encrypt on save.

    Runs ``sops --config <profile>/.sops.yaml edit <path>`` (interactive;
    decrypts to a tmpfile, re-encrypts on exit). The age private key is
    injected so the decrypt step works, ``--config`` pins the recipient set
    for the re-encrypt, and ``EDITOR`` selects the editor. Returns the sops
    exit code.

    Raises:
        SopsError: if ``sops`` cannot be found.
    """
    sops_bin = resolve_sops()
    if sops_bin is None:
        raise SopsError(SOPS_MISSING_MESSAGE)

    config = _config_for_secrets(path)
    env = _sops_env()
    env["EDITOR"] = editor
    return subprocess.run(
        [sops_bin, "--config", str(config), "edit", str(path)],
        cwd=get_dotfiles_dir(),
        env=env,
    ).returncode
