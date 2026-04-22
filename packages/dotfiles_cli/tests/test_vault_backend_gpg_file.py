"""Unit tests for the GPG-file vault backend.

Pure-mock tests for logic, plus an optional round-trip integration test
against real `gpg` when it's available (validates the --passphrase-fd
pipe mechanics that mocks cannot meaningfully exercise).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from dotfiles_cli.constants import GPG_MASTER_PASSWORD_ENV
from dotfiles_cli.vault.backends.gpg_file import (
    GpgFileBackend,
    GpgNotInstalledError,
)


def _completed(
    returncode: int = 0, stdout: bytes = b"", stderr: bytes = b""
) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=stderr
    )


@pytest.fixture
def backend(tmp_path: Path) -> GpgFileBackend:
    return GpgFileBackend(
        vault_file=tmp_path / "vault-secrets.yml.gpg",
        config_dir=tmp_path,
    )


class TestEnsureReady:
    def test_raises_when_gpg_missing(self, backend: GpgFileBackend):
        with patch("shutil.which", return_value=None):
            with pytest.raises(GpgNotInstalledError):
                backend.ensure_ready()

    def test_creates_config_dir_mode_700(self, tmp_path: Path, backend: GpgFileBackend):
        backend.config_dir = tmp_path / "new-config"
        with patch("shutil.which", return_value="/usr/bin/gpg"):
            backend.ensure_ready()
        assert backend.config_dir.exists()
        # Mode check — skip if we can't rely on umask / test runner perms.
        mode = backend.config_dir.stat().st_mode & 0o777
        assert mode == 0o700


class TestRead:
    def test_missing_file_returns_none(self, backend: GpgFileBackend):
        assert backend.read("common") is None

    def test_hit(self, backend: GpgFileBackend):
        backend.vault_file.touch()
        payload = yaml.safe_dump({"common": "the-pw", "adobe": "x"}).encode()
        with patch("subprocess.run", return_value=_completed(0, stdout=payload)):
            assert backend.read("common") == "the-pw"

    def test_miss_returns_none(self, backend: GpgFileBackend):
        backend.vault_file.touch()
        payload = yaml.safe_dump({"adobe": "x"}).encode()
        with patch("subprocess.run", return_value=_completed(0, stdout=payload)):
            assert backend.read("common") is None

    def test_decrypt_failure_raises(self, backend: GpgFileBackend):
        backend.vault_file.touch()
        with patch(
            "subprocess.run",
            return_value=_completed(2, stderr=b"bad passphrase"),
        ):
            with pytest.raises(RuntimeError, match="bad passphrase"):
                backend.read("common")


class TestWrite:
    def test_creates_new_file(
        self, backend: GpgFileBackend, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv(GPG_MASTER_PASSWORD_ENV, "masterpw")
        monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/gpg")

        with patch("subprocess.run") as mock_run:

            def _effect(cmd, *a, **kw):  # noqa: ARG001
                # The encrypt path writes to --output; simulate that.
                if "--output" in cmd:
                    out_idx = cmd.index("--output") + 1
                    Path(cmd[out_idx]).write_bytes(b"encrypted-bytes")
                return _completed(0)

            mock_run.side_effect = _effect
            backend.write("common", "vault-pw-1")

        assert backend.vault_file.exists()
        # File should be mode 600.
        assert backend.vault_file.stat().st_mode & 0o777 == 0o600

    def test_updates_existing_file(
        self, backend: GpgFileBackend, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv(GPG_MASTER_PASSWORD_ENV, "masterpw")
        monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/gpg")

        backend.vault_file.write_bytes(b"existing-ciphertext")
        existing = yaml.safe_dump({"adobe": "old"}).encode()

        encrypted_payloads = []

        def _effect(cmd, *a, **kw):  # noqa: ARG001
            if "--decrypt" in cmd:
                return _completed(0, stdout=existing)
            if "--symmetric" in cmd:
                # Capture plaintext input and write a placeholder to --output.
                encrypted_payloads.append(kw.get("input"))
                out_idx = cmd.index("--output") + 1
                Path(cmd[out_idx]).write_bytes(b"new-ciphertext")
            return _completed(0)

        with patch("subprocess.run", side_effect=_effect):
            backend.write("common", "fresh-pw")

        assert encrypted_payloads, "expected --symmetric to be invoked"
        decoded = yaml.safe_load(encrypted_payloads[0])
        assert decoded == {"adobe": "old", "common": "fresh-pw"}


class TestDelete:
    def test_missing_file_is_noop(self, backend: GpgFileBackend):
        with patch("subprocess.run") as mock_run:
            backend.delete("common")
        mock_run.assert_not_called()

    def test_absent_label_is_noop(
        self, backend: GpgFileBackend, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv(GPG_MASTER_PASSWORD_ENV, "masterpw")
        backend.vault_file.write_bytes(b"ciphertext")
        with patch(
            "subprocess.run",
            return_value=_completed(0, stdout=yaml.safe_dump({"adobe": "x"}).encode()),
        ) as mock_run:
            backend.delete("common")
        # Only the decrypt call; no re-encrypt.
        assert mock_run.call_count == 1

    def test_removes_label(
        self, backend: GpgFileBackend, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv(GPG_MASTER_PASSWORD_ENV, "masterpw")
        monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/gpg")
        backend.vault_file.write_bytes(b"ciphertext")

        captured_plaintext = []

        def _effect(cmd, *a, **kw):  # noqa: ARG001
            if "--decrypt" in cmd:
                return _completed(
                    0,
                    stdout=yaml.safe_dump({"adobe": "x", "common": "y"}).encode(),
                )
            if "--symmetric" in cmd:
                captured_plaintext.append(kw.get("input"))
                out_idx = cmd.index("--output") + 1
                Path(cmd[out_idx]).write_bytes(b"new")
            return _completed(0)

        with patch("subprocess.run", side_effect=_effect):
            backend.delete("common")

        assert captured_plaintext
        assert yaml.safe_load(captured_plaintext[0]) == {"adobe": "x"}

    def test_removes_file_when_dict_empty(
        self, backend: GpgFileBackend, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv(GPG_MASTER_PASSWORD_ENV, "masterpw")
        backend.vault_file.write_bytes(b"ciphertext")

        def _effect(cmd, *a, **kw):  # noqa: ARG001
            if "--decrypt" in cmd:
                return _completed(0, stdout=yaml.safe_dump({"common": "y"}).encode())
            return _completed(0)

        with patch("subprocess.run", side_effect=_effect):
            backend.delete("common")
        assert not backend.vault_file.exists()


class TestListLabels:
    def test_missing_file(self, backend: GpgFileBackend):
        assert backend.list_labels() == []

    def test_sorted_keys(
        self, backend: GpgFileBackend, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv(GPG_MASTER_PASSWORD_ENV, "masterpw")
        backend.vault_file.write_bytes(b"ciphertext")
        payload = yaml.safe_dump({"zebra": "z", "alpha": "a"}).encode()
        with patch("subprocess.run", return_value=_completed(0, stdout=payload)):
            assert backend.list_labels() == ["alpha", "zebra"]


class TestStatus:
    def test_missing_file(
        self, backend: GpgFileBackend, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/gpg")
        monkeypatch.delenv(GPG_MASTER_PASSWORD_ENV, raising=False)
        status = backend.status()
        assert status["backend"] == "gpg-file"
        assert status["exists"] is False
        assert status["gpg_installed"] is True
        assert status["master_password_env_set"] is False
        assert status["labels"] == []
        assert status["decryption_error"] is None

    def test_decryption_error_captured(
        self, backend: GpgFileBackend, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/gpg")
        monkeypatch.setenv(GPG_MASTER_PASSWORD_ENV, "wrongpw")
        backend.vault_file.write_bytes(b"ciphertext")
        with patch(
            "subprocess.run",
            return_value=_completed(2, stderr=b"bad passphrase"),
        ):
            status = backend.status()
        assert status["decryption_error"] is not None
        assert "bad passphrase" in status["decryption_error"]


class TestGpgInvocation:
    def test_loopback_when_env_set(
        self, backend: GpgFileBackend, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv(GPG_MASTER_PASSWORD_ENV, "masterpw")
        backend.vault_file.touch()
        with patch("subprocess.run", return_value=_completed(0, stdout=b"{}")) as mr:
            backend._decrypt()
        cmd = mr.call_args.args[0]
        assert "--pinentry-mode" in cmd
        assert "loopback" in cmd
        assert "--passphrase-fd" in cmd

    def test_no_loopback_when_env_unset(
        self, backend: GpgFileBackend, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.delenv(GPG_MASTER_PASSWORD_ENV, raising=False)
        backend.vault_file.touch()
        with patch("subprocess.run", return_value=_completed(0, stdout=b"{}")) as mr:
            backend._decrypt()
        cmd = mr.call_args.args[0]
        assert "--pinentry-mode" not in cmd
        assert "--passphrase-fd" not in cmd


@pytest.mark.skipif(shutil.which("gpg") is None, reason="gpg not installed")
class TestRealGpgRoundTrip:
    """Integration test — exercises real gpg with --passphrase-fd pipe.

    Validates the fd-pipe mechanics that pure mocks cannot meaningfully
    test (we use `os.pipe` + `pass_fds` + `--passphrase-fd`).
    """

    def test_write_then_read(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        # Isolate a throwaway GNUPGHOME so we don't touch the user's keyring.
        gnupghome = tmp_path / "gnupghome"
        gnupghome.mkdir(mode=0o700)
        monkeypatch.setenv("GNUPGHOME", str(gnupghome))
        monkeypatch.setenv(GPG_MASTER_PASSWORD_ENV, "test-master-password")

        backend = GpgFileBackend(
            vault_file=tmp_path / "vault.yml.gpg",
            config_dir=tmp_path,
        )
        backend.write("common", "vault-password-1")
        backend.write("adobe", "vault-password-2")

        assert backend.read("common") == "vault-password-1"
        assert backend.read("adobe") == "vault-password-2"
        assert backend.read("missing") is None
        assert backend.list_labels() == ["adobe", "common"]

        backend.delete("common")
        assert backend.read("common") is None
        assert backend.read("adobe") == "vault-password-2"

        backend.delete("adobe")
        assert not backend.vault_file.exists()
