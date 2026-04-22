"""Unit tests for the Ansible vault client-script entrypoint."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from dotfiles_cli.vault import vault_client
from dotfiles_cli.vault.backend import reset_backend_cache


@pytest.fixture(autouse=True)
def _clear_backend_cache():
    reset_backend_cache()
    yield
    reset_backend_cache()


@pytest.fixture
def fake_backend(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    backend = MagicMock()
    monkeypatch.setattr(vault_client, "get_backend", lambda: backend)
    return backend


class TestClientScript:
    def test_hit_prints_password_and_exits_zero(
        self, fake_backend: MagicMock, capsys: pytest.CaptureFixture
    ):
        fake_backend.read.return_value = "secret-pw"
        rc = vault_client.main(["--vault-id", "common"])
        captured = capsys.readouterr()
        assert rc == 0
        assert captured.out == "secret-pw\n"
        assert captured.err == ""
        fake_backend.read.assert_called_once_with("common")

    def test_default_label_is_common(
        self, fake_backend: MagicMock, capsys: pytest.CaptureFixture
    ):
        fake_backend.read.return_value = "pw"
        rc = vault_client.main([])
        captured = capsys.readouterr()
        assert rc == 0
        assert captured.out == "pw\n"
        fake_backend.read.assert_called_once_with("common")

    def test_miss_exits_2_with_guidance(
        self, fake_backend: MagicMock, capsys: pytest.CaptureFixture
    ):
        fake_backend.read.return_value = None
        rc = vault_client.main(["--vault-id", "adobe"])
        captured = capsys.readouterr()
        assert rc == 2
        assert captured.out == ""
        assert "adobe" in captured.err
        assert "dotfiles secret keychain push" in captured.err

    def test_backend_exception_exits_3(
        self, fake_backend: MagicMock, capsys: pytest.CaptureFixture
    ):
        fake_backend.read.side_effect = RuntimeError("bad passphrase")
        rc = vault_client.main(["--vault-id", "common"])
        captured = capsys.readouterr()
        assert rc == 3
        assert captured.out == ""
        assert "bad passphrase" in captured.err
        assert "dotfiles secret" in captured.err

    def test_preserves_label_with_hyphens(
        self, fake_backend: MagicMock, capsys: pytest.CaptureFixture
    ):
        fake_backend.read.return_value = "x"
        rc = vault_client.main(["--vault-id", "private-personal-productivity"])
        assert rc == 0
        fake_backend.read.assert_called_once_with("private-personal-productivity")


class TestOnePasswordFallback:
    """Client script falls back to 1Password on a local-backend miss."""

    def test_miss_fetches_from_1p_and_persists(
        self,
        fake_backend: MagicMock,
        capsys: pytest.CaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
    ):
        fake_backend.read.return_value = None
        monkeypatch.setattr(
            vault_client.onepassword, "read_field", lambda label: "from-1p"
        )

        rc = vault_client.main(["--vault-id", "adobe"])
        captured = capsys.readouterr()

        assert rc == 0
        assert captured.out == "from-1p\n"
        assert captured.err == ""
        fake_backend.write.assert_called_once_with("adobe", "from-1p")

    def test_miss_and_1p_miss_still_exits_2(
        self,
        fake_backend: MagicMock,
        capsys: pytest.CaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
    ):
        fake_backend.read.return_value = None
        monkeypatch.setattr(vault_client.onepassword, "read_field", lambda label: None)

        rc = vault_client.main(["--vault-id", "adobe"])
        captured = capsys.readouterr()

        assert rc == 2
        assert captured.out == ""
        assert "adobe" in captured.err

    def test_1p_hit_persist_failure_still_succeeds(
        self,
        fake_backend: MagicMock,
        capsys: pytest.CaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
    ):
        fake_backend.read.return_value = None
        fake_backend.write.side_effect = RuntimeError("keychain locked")
        monkeypatch.setattr(
            vault_client.onepassword, "read_field", lambda label: "from-1p"
        )

        rc = vault_client.main(["--vault-id", "adobe"])
        captured = capsys.readouterr()

        assert rc == 0
        assert captured.out == "from-1p\n"
