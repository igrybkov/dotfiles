"""Unit tests for the macOS login-keychain vault backend.

Exercises `keyring` mocks — no real keychain calls. Gated to macOS only
so Linux CI skips these cleanly.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

if sys.platform != "darwin":
    pytest.skip("macOS login-keychain backend is macOS-only", allow_module_level=True)

from dotfiles_cli.vault.backends.macos import MacOSKeyringBackend


@pytest.fixture
def backend(tmp_path: Path) -> MacOSKeyringBackend:
    return MacOSKeyringBackend(
        service="com.test.dotfiles.vault",
        labels_path=tmp_path / "vault-labels.json",
    )


class TestEnsureReady:
    def test_is_noop(self, backend: MacOSKeyringBackend):
        # No subprocess / keyring calls expected.
        backend.ensure_ready()


class TestRead:
    def test_hit(self, backend: MacOSKeyringBackend):
        with patch("keyring.get_password", return_value="stored-pw") as mock:
            assert backend.read("common") == "stored-pw"
        mock.assert_called_once_with(backend.service, "common")

    def test_miss_returns_none(self, backend: MacOSKeyringBackend):
        with patch("keyring.get_password", return_value=None):
            assert backend.read("absent") is None

    def test_keyring_error_returns_none(self, backend: MacOSKeyringBackend):
        from keyring.errors import KeyringError

        with patch("keyring.get_password", side_effect=KeyringError("backend failure")):
            assert backend.read("x") is None


class TestWrite:
    def test_happy_path(self, backend: MacOSKeyringBackend):
        with patch("keyring.set_password") as mock:
            backend.write("common", "pw-value")
        mock.assert_called_once_with(backend.service, "common", "pw-value")
        # Label should be persisted to the JSON index.
        assert backend.labels_path.exists()
        assert json.loads(backend.labels_path.read_text()) == ["common"]
        assert backend.labels_path.stat().st_mode & 0o777 == 0o600

    def test_multiple_writes_accumulate_labels(self, backend: MacOSKeyringBackend):
        with patch("keyring.set_password"):
            backend.write("common", "pw-a")
            backend.write("adobe", "pw-b")
        assert json.loads(backend.labels_path.read_text()) == ["adobe", "common"]

    def test_overwrite_keeps_single_label(self, backend: MacOSKeyringBackend):
        with patch("keyring.set_password"):
            backend.write("common", "first")
            backend.write("common", "second")
        assert json.loads(backend.labels_path.read_text()) == ["common"]


class TestDelete:
    def test_removes_label_from_index(self, backend: MacOSKeyringBackend):
        with patch("keyring.set_password"), patch("keyring.delete_password"):
            backend.write("common", "pw")
            backend.write("adobe", "pw")
            backend.delete("common")
        assert json.loads(backend.labels_path.read_text()) == ["adobe"]

    def test_delete_absent_is_noop(self, backend: MacOSKeyringBackend):
        from keyring.errors import PasswordDeleteError

        with patch(
            "keyring.delete_password",
            side_effect=PasswordDeleteError("not found"),
        ):
            # Should not raise.
            backend.delete("absent")


class TestListLabels:
    def test_empty_when_file_missing(self, backend: MacOSKeyringBackend):
        assert backend.list_labels() == []

    def test_reads_from_json(self, backend: MacOSKeyringBackend):
        backend.labels_path.parent.mkdir(parents=True, exist_ok=True)
        backend.labels_path.write_text(json.dumps(["zebra", "alpha"]))
        assert backend.list_labels() == ["alpha", "zebra"]

    def test_tolerates_malformed_json(self, backend: MacOSKeyringBackend):
        backend.labels_path.parent.mkdir(parents=True, exist_ok=True)
        backend.labels_path.write_text("not-json")
        assert backend.list_labels() == []

    def test_tolerates_non_list_json(self, backend: MacOSKeyringBackend):
        backend.labels_path.parent.mkdir(parents=True, exist_ok=True)
        backend.labels_path.write_text('{"not": "a list"}')
        assert backend.list_labels() == []


class TestStatus:
    def test_shape(self, backend: MacOSKeyringBackend):
        with patch("keyring.set_password"):
            backend.write("common", "pw")
        status = backend.status()
        assert status["backend"] == "macos-login-keychain"
        assert status["service"] == backend.service
        assert status["labels"] == ["common"]
        assert status["labels_path"] == str(backend.labels_path)
        assert "keyring_backend" in status
