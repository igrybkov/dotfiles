"""Build-time sops secret reads for deploys.

Some deploys need secret material while *rendering* operations — URL-based MCP
servers with ``secret_headers``, or profile ``deploy.py`` scripts that bake
credentials into generated files. Spawn-time resolution
(``bin/run-with-secrets.sh``) cannot help there, so this module shells out to
``sops -d --extract`` directly. It deliberately does not import
``dotfiles_cli`` — the deploy engine only depends on profile discovery.

The age private key is taken from ``SOPS_AGE_KEY`` in the environment; the CLI
exports it before invoking pyinfra (see ``dotfiles_cli.commands.install``).
``SOPS_AGE_KEY_FILE`` set by the caller is honored too. All failure modes
(missing key, unknown profile, missing secrets file, sops error) degrade to
``None`` with a logged warning so deploys can skip secret-dependent work
instead of writing broken output.
"""

from __future__ import annotations

import functools
import os
import subprocess
from pathlib import Path

from dotfiles_profile_discovery import discover_profiles
from pyinfra import logger


def _dot_to_extract(key_path: str) -> str:
    """Convert dot notation to a sops ``--extract`` path.

    ``"mcp.github.token"`` -> ``'["mcp"]["github"]["token"]'``. Mirrors
    ``dotfiles_cli.vault.sops._dot_to_extract``.
    """
    parts = [p for p in key_path.split(".") if p != ""]
    if not parts:
        raise ValueError("Empty key path")
    return "".join(f'["{p}"]' for p in parts)


@functools.lru_cache(maxsize=None)
def _profile_secrets_files(dotfiles_dir: Path) -> dict[str, Path]:
    """Map effective profile name -> secrets.yml path (existing files only)."""
    found: dict[str, Path] = {}
    for profile in discover_profiles(dotfiles_dir / "profiles"):
        secrets_file = profile.path / "secrets.yml"
        if secrets_file.exists():
            found[profile.name] = secrets_file
    return found


@functools.lru_cache(maxsize=None)
def decrypt_key(profile: str, key_path: str, dotfiles_dir: Path) -> str | None:
    """Decrypt one value from a profile's sops ``secrets.yml``, or ``None``.

    ``key_path`` is dot notation (e.g. ``mcp_secrets.service.token``).
    Results are cached for the process lifetime — a deploy may reference the
    same key from several operations.
    """
    if not (os.environ.get("SOPS_AGE_KEY") or os.environ.get("SOPS_AGE_KEY_FILE")):
        logger.warning(
            f"secrets: SOPS_AGE_KEY not set — cannot decrypt {key_path!r} "
            f"for profile {profile!r} (run 'dotfiles secret init'?)"
        )
        return None

    secrets_file = _profile_secrets_files(dotfiles_dir).get(profile)
    if secrets_file is None:
        logger.warning(
            f"secrets: profile {profile!r} has no secrets.yml — "
            f"cannot resolve {key_path!r}"
        )
        return None

    try:
        extract = _dot_to_extract(key_path)
    except ValueError:
        logger.warning(f"secrets: empty key path for profile {profile!r}")
        return None

    try:
        result = subprocess.run(
            ["sops", "-d", "--extract", extract, str(secrets_file)],
            capture_output=True,
            text=True,
            cwd=dotfiles_dir,
            check=False,
        )
    except FileNotFoundError:
        logger.warning("secrets: 'sops' binary not found on PATH")
        return None

    if result.returncode != 0:
        logger.warning(
            f"secrets: could not extract {key_path!r} from {secrets_file}: "
            f"{result.stderr.strip() or 'key not found or decryption failed'}"
        )
        return None

    # --extract on a scalar emits a trailing newline; strip a single one.
    return result.stdout.rstrip("\n")
