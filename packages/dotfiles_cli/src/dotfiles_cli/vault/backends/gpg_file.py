"""GPG-symmetric-encrypted file vault backend (Linux default).

Stores all vault passwords as a YAML dict inside a single
`gpg --symmetric`-encrypted file. A single master password unlocks every
vault-id at once.

Master password sources, in order:
    1. `DOTFILES_VAULT_MASTER_PASSWORD` env var (CI / unattended).
    2. gpg-agent cache (interactive, after first prompt within TTL).
    3. `/dev/tty` prompt as last-resort fallback.

Passwords are passed to `gpg` via `--passphrase-fd` on an anonymous pipe —
never on argv — so they never appear in `ps(1)` output.
"""

from __future__ import annotations

import getpass
import os
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

from ..backend import VaultBackend  # noqa: F401 (for IDE/type-check)
from ...constants import (
    GPG_MASTER_PASSWORD_ENV,
    get_gpg_vault_dir,
    get_gpg_vault_file,
)


_DISTRO_HINTS = (
    ("/etc/debian_version", "apt-get install -y gnupg"),
    ("/etc/alpine-release", "apk add --no-cache gnupg"),
    ("/etc/arch-release", "pacman -S --needed gnupg"),
    ("/etc/redhat-release", "dnf install -y gnupg2"),
)


def _install_hint() -> str:
    for marker, cmd in _DISTRO_HINTS:
        if Path(marker).exists():
            return cmd
    return "install gnupg using your system package manager"


class GpgNotInstalledError(RuntimeError):
    """Raised when `gpg` isn't on PATH."""


class GpgFileBackend:
    """GPG-symmetric vault backend backed by one file and one master password."""

    def __init__(
        self,
        vault_file: Path | None = None,
        config_dir: Path | None = None,
    ) -> None:
        self.vault_file = vault_file or get_gpg_vault_file()
        self.config_dir = config_dir or get_gpg_vault_dir()

    # ------------------------------------------------------------------ setup

    def ensure_ready(self) -> None:
        """Verify gpg is available and the config directory exists."""
        if shutil.which("gpg") is None:
            raise GpgNotInstalledError(
                "gpg is required for the GPG-file vault backend.\n"
                f"Install it: {_install_hint()}"
            )
        self.config_dir.mkdir(parents=True, exist_ok=True)
        # Tighten directory mode — the parent ~/.config is typically 700 on
        # Linux, but we enforce our dir explicitly.
        self.config_dir.chmod(0o700)

    # --------------------------------------------------------------- read/write

    def read(self, label: str) -> str | None:
        if not self.vault_file.exists():
            return None
        data = self._decrypt()
        if not isinstance(data, dict):
            return None
        value = data.get(label)
        return value if isinstance(value, str) else None

    def write(self, label: str, password: str) -> None:
        self.ensure_ready()
        data = self._decrypt() if self.vault_file.exists() else {}
        if not isinstance(data, dict):
            data = {}
        data[label] = password
        self._encrypt(data)

    def delete(self, label: str) -> None:
        if not self.vault_file.exists():
            return
        data = self._decrypt()
        if not isinstance(data, dict) or label not in data:
            return
        del data[label]
        if data:
            self._encrypt(data)
        else:
            self.vault_file.unlink()

    def list_labels(self) -> list[str]:
        if not self.vault_file.exists():
            return []
        data = self._decrypt()
        if not isinstance(data, dict):
            return []
        return sorted(k for k in data.keys() if isinstance(k, str))

    def status(self) -> dict:
        exists = self.vault_file.exists()
        labels: list[str] = []
        decryption_error: str | None = None
        if exists:
            try:
                labels = self.list_labels()
            except RuntimeError as exc:
                decryption_error = str(exc)
        return {
            "backend": "gpg-file",
            "vault_file": str(self.vault_file),
            "exists": exists,
            "labels": labels,
            "gpg_installed": shutil.which("gpg") is not None,
            "master_password_env_set": bool(os.environ.get(GPG_MASTER_PASSWORD_ENV)),
            "decryption_error": decryption_error,
        }

    # ----------------------------------------------------- crypto internals

    def _master_password(self) -> str | None:
        """Return a master password if we have one in hand (env or prompt).

        Returns None to delegate to gpg-agent + pinentry chain.
        """
        env_value = os.environ.get(GPG_MASTER_PASSWORD_ENV)
        if env_value:
            return env_value
        return None

    def _prompt_master_password(self, *, confirm: bool = False) -> str:
        """Interactive prompt on /dev/tty, used for first-time setup only.

        Returns the entered password. Raises if no TTY available.
        """
        if not sys.stdin.isatty() and not os.path.exists("/dev/tty"):
            raise RuntimeError(
                f"No TTY and {GPG_MASTER_PASSWORD_ENV} not set; "
                "cannot prompt for vault master password."
            )
        pw = getpass.getpass("Vault master password: ")
        if confirm:
            pw2 = getpass.getpass("Confirm vault master password: ")
            if pw != pw2:
                raise RuntimeError("Passwords do not match.")
        if not pw:
            raise RuntimeError("Vault master password cannot be empty.")
        return pw

    def _decrypt(self) -> dict:
        passphrase = self._master_password()
        result = _run_gpg(
            ["--decrypt", str(self.vault_file)],
            passphrase=passphrase,
            capture_output=True,
        )
        if result.returncode != 0:
            err = result.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"gpg --decrypt failed: {err or 'non-zero exit'}")
        if not result.stdout:
            return {}
        data = yaml.safe_load(result.stdout)
        return data if isinstance(data, dict) else {}

    def _encrypt(self, data: dict) -> None:
        """Serialize `data` to YAML and gpg-symmetric-encrypt to vault_file.

        Requires a master password — if the file is new and no env var is
        set, prompts once on /dev/tty with confirmation.
        """
        passphrase = self._master_password()
        if passphrase is None and not self.vault_file.exists():
            passphrase = self._prompt_master_password(confirm=True)
        # For existing files, passphrase=None is acceptable: gpg-agent/pinentry
        # handle it. But `--symmetric` wants a passphrase, and if the agent
        # doesn't know it either, gpg will fail. Users re-prompt via init.

        plaintext = yaml.safe_dump(data, sort_keys=True).encode("utf-8")

        self.vault_file.parent.mkdir(parents=True, exist_ok=True)
        # Encrypt to a temp file in same dir, then atomic-rename — avoids
        # a half-written file if gpg crashes.
        tmp_path = self.vault_file.with_suffix(self.vault_file.suffix + ".tmp")
        if tmp_path.exists():
            tmp_path.unlink()

        result = _run_gpg(
            [
                "--symmetric",
                "--cipher-algo",
                "AES256",
                "--s2k-mode",
                "3",
                "--s2k-digest-algo",
                "SHA512",
                "--s2k-count",
                "65011712",
                "--output",
                str(tmp_path),
                "-",
            ],
            passphrase=passphrase,
            stdin_bytes=plaintext,
            capture_output=True,
        )
        if result.returncode != 0:
            if tmp_path.exists():
                tmp_path.unlink()
            err = result.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"gpg --symmetric failed: {err or 'non-zero exit'}")
        tmp_path.chmod(0o600)
        tmp_path.replace(self.vault_file)


def _run_gpg(
    args: list[str],
    *,
    passphrase: str | None,
    stdin_bytes: bytes | None = None,
    capture_output: bool = True,
) -> subprocess.CompletedProcess:
    """Run gpg, optionally passing a master passphrase via --passphrase-fd.

    When `passphrase` is provided, we open an anonymous pipe, write the
    passphrase to our end, and hand the read end to gpg via an extra fd
    plus `--pinentry-mode loopback --passphrase-fd <n>`. Passphrase never
    touches argv.

    When `passphrase` is None, gpg relies on its normal pinentry / agent
    chain — appropriate when gpg-agent has the key cached.
    """
    if passphrase is None:
        return subprocess.run(
            ["gpg", "--batch", "--yes", "--quiet", *args],
            input=stdin_bytes,
            capture_output=capture_output,
        )

    pass_r, pass_w = os.pipe()
    os.set_inheritable(pass_r, True)
    try:
        os.write(pass_w, passphrase.encode("utf-8") + b"\n")
    finally:
        os.close(pass_w)

    try:
        cmd = [
            "gpg",
            "--batch",
            "--yes",
            "--quiet",
            "--pinentry-mode",
            "loopback",
            "--passphrase-fd",
            str(pass_r),
            *args,
        ]
        return subprocess.run(
            cmd,
            input=stdin_bytes,
            capture_output=capture_output,
            pass_fds=(pass_r,),
        )
    finally:
        try:
            os.close(pass_r)
        except OSError:
            pass
