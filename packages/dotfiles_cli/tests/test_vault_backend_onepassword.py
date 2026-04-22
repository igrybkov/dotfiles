"""Unit tests for the 1Password fallback helper."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from dotfiles_cli.vault.backends import onepassword


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch):
    """Clear env vars that influence op invocations."""
    monkeypatch.delenv(onepassword.ENV_ITEM, raising=False)
    monkeypatch.delenv(onepassword.ENV_ACCOUNT, raising=False)


class TestIsConfigured:
    def test_requires_env_var_and_op_on_path(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv(onepassword.ENV_ITEM, "op://Private/vaults")
        with patch("shutil.which", return_value="/opt/homebrew/bin/op"):
            assert onepassword.is_configured() is True

    def test_false_when_env_var_missing(self):
        with patch("shutil.which", return_value="/opt/homebrew/bin/op"):
            assert onepassword.is_configured() is False

    def test_false_when_op_missing(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv(onepassword.ENV_ITEM, "op://Private/vaults")
        with patch("shutil.which", return_value=None):
            assert onepassword.is_configured() is False

    def test_false_when_env_var_is_empty_string(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv(onepassword.ENV_ITEM, "   ")
        with patch("shutil.which", return_value="/opt/homebrew/bin/op"):
            assert onepassword.is_configured() is False


class TestReadField:
    def test_returns_none_when_not_configured(self):
        # No env var set → immediate None without shelling out.
        with patch("subprocess.run") as run:
            assert onepassword.read_field("agents") is None
            run.assert_not_called()

    def test_invokes_op_read_with_ref_and_label(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv(onepassword.ENV_ITEM, "op://Private/vaults")
        fake = MagicMock(returncode=0, stdout="sekret", stderr="")
        with (
            patch("shutil.which", return_value="/opt/homebrew/bin/op"),
            patch("subprocess.run", return_value=fake) as run,
        ):
            result = onepassword.read_field("agents")

        assert result == "sekret"
        cmd = run.call_args[0][0]
        assert cmd[0] == "op"
        assert "read" in cmd and "-n" in cmd
        assert "op://Private/vaults/agents" in cmd

    def test_passes_account_flag_when_env_set(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv(onepassword.ENV_ITEM, "op://Private/vaults")
        monkeypatch.setenv(onepassword.ENV_ACCOUNT, "my.1password.com")
        fake = MagicMock(returncode=0, stdout="pw", stderr="")
        with (
            patch("shutil.which", return_value="/opt/homebrew/bin/op"),
            patch("subprocess.run", return_value=fake) as run,
        ):
            onepassword.read_field("agents")

        cmd = run.call_args[0][0]
        assert "--account" in cmd
        assert cmd[cmd.index("--account") + 1] == "my.1password.com"

    def test_returns_none_on_nonzero_exit(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv(onepassword.ENV_ITEM, "op://Private/vaults")
        fake = MagicMock(returncode=1, stdout="", stderr="not found")
        with (
            patch("shutil.which", return_value="/opt/homebrew/bin/op"),
            patch("subprocess.run", return_value=fake),
        ):
            assert onepassword.read_field("missing") is None

    def test_returns_none_on_empty_stdout(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv(onepassword.ENV_ITEM, "op://Private/vaults")
        fake = MagicMock(returncode=0, stdout="", stderr="")
        with (
            patch("shutil.which", return_value="/opt/homebrew/bin/op"),
            patch("subprocess.run", return_value=fake),
        ):
            assert onepassword.read_field("empty") is None

    def test_returns_none_on_timeout(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv(onepassword.ENV_ITEM, "op://Private/vaults")
        with (
            patch("shutil.which", return_value="/opt/homebrew/bin/op"),
            patch(
                "subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd="op", timeout=15),
            ),
        ):
            assert onepassword.read_field("slow") is None

    def test_returns_none_on_missing_op(self, monkeypatch: pytest.MonkeyPatch):
        # is_configured() → True via env + which, but subprocess raises FileNotFound.
        monkeypatch.setenv(onepassword.ENV_ITEM, "op://Private/vaults")
        with (
            patch("shutil.which", return_value="/opt/homebrew/bin/op"),
            patch("subprocess.run", side_effect=FileNotFoundError),
        ):
            assert onepassword.read_field("x") is None


class TestWriteField:
    def test_raises_when_not_configured(self):
        with pytest.raises(onepassword.OnePasswordError):
            onepassword.write_field("agents", "pw")

    def test_invokes_op_item_edit_when_item_exists(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Existing item → `op item edit <title> --vault=<vault>` sets the field."""
        monkeypatch.setenv(onepassword.ENV_ITEM, "op://Private/vaults")
        # First call is `op item get` (exists check), then `op item edit`.
        calls = [
            MagicMock(returncode=0, stdout='{"id":"x"}', stderr=""),
            MagicMock(returncode=0, stdout="", stderr=""),
        ]
        with (
            patch("shutil.which", return_value="/opt/homebrew/bin/op"),
            patch("subprocess.run", side_effect=calls) as run,
        ):
            onepassword.write_field("agents", "new-pw")

        assert run.call_count == 2
        get_cmd = run.call_args_list[0][0][0]
        assert get_cmd[:3] == ["op", "item", "get"]
        assert "vaults" in get_cmd
        assert "--vault=Private" in get_cmd

        edit_cmd = run.call_args_list[1][0][0]
        assert edit_cmd[:3] == ["op", "item", "edit"]
        assert "vaults" in edit_cmd
        assert "--vault=Private" in edit_cmd
        assert "agents[password]=new-pw" in edit_cmd

    def test_creates_item_when_missing(self, monkeypatch: pytest.MonkeyPatch):
        """Missing item → `op item create` with --vault/--title parsed from ref."""
        monkeypatch.setenv(onepassword.ENV_ITEM, "op://Private/dotfiles-vaults")
        calls = [
            MagicMock(returncode=1, stdout="", stderr="isn't an item"),
            MagicMock(returncode=0, stdout="", stderr=""),
        ]
        with (
            patch("shutil.which", return_value="/opt/homebrew/bin/op"),
            patch("subprocess.run", side_effect=calls) as run,
        ):
            onepassword.write_field("agents", "new-pw")

        assert run.call_count == 2
        create_cmd = run.call_args_list[1][0][0]
        assert "create" in create_cmd
        assert "--vault=Private" in create_cmd
        assert "--title=dotfiles-vaults" in create_cmd
        assert "--category=Login" in create_cmd
        assert "agents[password]=new-pw" in create_cmd

    def test_raises_on_edit_failure(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv(onepassword.ENV_ITEM, "op://Private/vaults")
        calls = [
            MagicMock(returncode=0, stdout='{"id":"x"}', stderr=""),
            MagicMock(returncode=1, stdout="", stderr="permission denied"),
        ]
        with (
            patch("shutil.which", return_value="/opt/homebrew/bin/op"),
            patch("subprocess.run", side_effect=calls),
        ):
            with pytest.raises(onepassword.OnePasswordError, match="permission denied"):
                onepassword.write_field("agents", "pw")

    def test_raises_on_create_failure(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv(onepassword.ENV_ITEM, "op://Private/vaults")
        calls = [
            MagicMock(returncode=1, stdout="", stderr="isn't an item"),
            MagicMock(returncode=1, stdout="", stderr="vault does not exist"),
        ]
        with (
            patch("shutil.which", return_value="/opt/homebrew/bin/op"),
            patch("subprocess.run", side_effect=calls),
        ):
            with pytest.raises(
                onepassword.OnePasswordError, match="vault does not exist"
            ):
                onepassword.write_field("agents", "pw")

    def test_malformed_ref_raises_early(self, monkeypatch: pytest.MonkeyPatch):
        """A ref that can't be parsed into vault/item fails before shelling out."""
        monkeypatch.setenv(onepassword.ENV_ITEM, "not-a-real-ref")
        with (
            patch("shutil.which", return_value="/opt/homebrew/bin/op"),
            patch("subprocess.run") as run,
        ):
            with pytest.raises(onepassword.OnePasswordError, match="valid op://"):
                onepassword.write_field("agents", "pw")
            run.assert_not_called()


class TestParseItemRef:
    def test_parses_simple_ref(self):
        assert onepassword._parse_item_ref("op://Private/my-item") == (
            "Private",
            "my-item",
        )

    def test_rejects_missing_prefix(self):
        assert onepassword._parse_item_ref("Private/my-item") is None

    def test_rejects_missing_item(self):
        assert onepassword._parse_item_ref("op://Private") is None

    def test_rejects_empty_segments(self):
        assert onepassword._parse_item_ref("op:///item") is None
        assert onepassword._parse_item_ref("op://vault/") is None

    def test_preserves_hyphens_and_spaces(self):
        # 1P allows vault names with spaces — treat them as one segment.
        assert onepassword._parse_item_ref("op://My Vault/my-item") == (
            "My Vault",
            "my-item",
        )
