"""Tests for the zellij command."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from conftest import CycloptsTestRunner

from hive_cli.app import app
from hive_cli.config import reload_config


class TestZellijCommand:
    """Tests for hive zellij command."""

    def test_zellij_not_installed(self, cli_runner: CycloptsTestRunner):
        """Test error when zellij is not installed."""
        with patch("shutil.which", return_value=None):
            result = cli_runner.invoke(app, ["zellij"])
            assert result.exit_code == 1
            assert "zellij is not installed" in result.output

    def test_zellij_no_agent_available(
        self, cli_runner: CycloptsTestRunner, monkeypatch
    ):
        """Test error when no agent is available."""
        monkeypatch.setenv("HIVE_AGENTS_ORDER", "claude,gemini")
        monkeypatch.delenv("AGENT", raising=False)

        def mock_which(cmd):
            return "/usr/bin/zellij" if cmd == "zellij" else None

        with (
            patch("shutil.which", side_effect=mock_which),
            patch("hive_cli.config.loader.find_config_files", return_value=[]),
        ):
            reload_config()
            result = cli_runner.invoke(app, ["zellij"])
            assert result.exit_code == 1
            assert "No AI coding agent found" in result.output

    def test_zellij_preferred_agent_not_found(self, cli_runner: CycloptsTestRunner):
        """Test error when specified agent is not found."""

        def mock_which(cmd):
            return "/usr/bin/zellij" if cmd == "zellij" else None

        with patch("shutil.which", side_effect=mock_which):
            result = cli_runner.invoke(app, ["zellij", "-a", "nonexistent"])
            assert result.exit_code == 1
            assert "nonexistent" in result.output
            assert "not available" in result.output

    def test_zellij_launches_with_agent(
        self, cli_runner: CycloptsTestRunner, temp_git_repo
    ):
        """Test zellij launches with correct session name (no layout by default)."""

        def mock_which(cmd):
            if cmd in ["zellij", "claude"]:
                return f"/usr/bin/{cmd}"
            return None

        with (
            patch("shutil.which", side_effect=mock_which),
            patch("os.execvpe") as mock_execvpe,
        ):
            cli_runner.invoke(app, ["zellij", "-a", "claude"])
            mock_execvpe.assert_called_once()
            call_args = mock_execvpe.call_args
            assert call_args[0][0] == "zellij"
            cmd_list = call_args[0][1]
            assert cmd_list[0] == "zellij"
            # No layout by default
            assert "--layout" not in cmd_list
            assert "attach" in cmd_list
            assert "--create" in cmd_list
            # Session name should include agent name
            session_name = cmd_list[-1]
            assert "claude" in session_name

    def test_zellij_uses_configured_layout(
        self, cli_runner: CycloptsTestRunner, temp_git_repo, monkeypatch
    ):
        """Test that zellij uses layout from config when specified."""
        monkeypatch.setenv("HIVE_ZELLIJ_LAYOUT", "custom-layout")

        # Clear config cache to pick up env var
        from hive_cli.config import reload_config

        reload_config()

        def mock_which(cmd):
            if cmd in ["zellij", "claude"]:
                return f"/usr/bin/{cmd}"
            return None

        with (
            patch("shutil.which", side_effect=mock_which),
            patch("os.execvpe") as mock_execvpe,
        ):
            cli_runner.invoke(app, ["zellij", "-a", "claude"])
            mock_execvpe.assert_called_once()
            cmd_list = mock_execvpe.call_args[0][1]
            assert "--layout" in cmd_list
            layout_idx = cmd_list.index("--layout")
            assert cmd_list[layout_idx + 1] == "custom-layout"

    def test_zellij_sets_agent_env(self, cli_runner: CycloptsTestRunner, temp_git_repo):
        """Test that HIVE_AGENT env var is passed to child process."""

        def mock_which(cmd):
            if cmd in ["zellij", "claude"]:
                return f"/usr/bin/{cmd}"
            return None

        captured_env = {}

        def capture_execvpe(cmd, args, env):
            captured_env["HIVE_AGENT"] = env.get("HIVE_AGENT")
            raise SystemExit(0)

        with (
            patch("shutil.which", side_effect=mock_which),
            patch("os.execvpe", side_effect=capture_execvpe),
        ):
            cli_runner.invoke(app, ["zellij", "-a", "claude"])
            assert captured_env["HIVE_AGENT"] == "claude"


class TestZellijHelp:
    """Tests for zellij command help."""

    def test_zellij_help(self, cli_runner: CycloptsTestRunner):
        """Test that zellij --help shows help text."""
        result = cli_runner.invoke(app, ["zellij", "--help"])
        assert result.exit_code == 0
        assert "Open Zellij with AI agent layout" in result.output
        assert "--agent" in result.output

    def test_zellij_help_shows_subcommands(self, cli_runner: CycloptsTestRunner):
        """Test that zellij --help shows set-status and set-title subcommands."""
        result = cli_runner.invoke(app, ["zellij", "--help"])
        assert result.exit_code == 0
        assert "set-status" in result.output
        assert "set-title" in result.output


class TestPaneStateManagement:
    """Tests for pane title state management functions."""

    @pytest.fixture
    def zellij_env(self, monkeypatch, tmp_path):
        """Set up Zellij environment for testing."""
        monkeypatch.setenv("ZELLIJ", "0")
        monkeypatch.setenv("ZELLIJ_SESSION_NAME", "test-session")
        monkeypatch.setenv("ZELLIJ_PANE_ID", "42")
        monkeypatch.setenv("HIVE_AGENT", "claude")
        monkeypatch.setenv("HIVE_PANE_ID", "1")

        # Use tmp_path for state files instead of /tmp
        state_dir = tmp_path / "hive-zellij" / "test-session"
        state_dir.mkdir(parents=True)

        # Patch _get_state_file to use tmp_path
        def mock_get_state_file():
            return state_dir / "42.json"

        with patch(
            "hive_cli.utils.zellij._get_state_file", side_effect=mock_get_state_file
        ):
            yield state_dir

    def test_get_state_file_not_in_zellij(self, monkeypatch):
        """Test _get_state_file returns None when not in Zellij."""
        monkeypatch.delenv("ZELLIJ", raising=False)

        from hive_cli.utils.zellij import _get_state_file

        assert _get_state_file() is None

    def test_get_state_file_in_zellij(self, monkeypatch):
        """Test _get_state_file returns correct path when in Zellij."""
        monkeypatch.setenv("ZELLIJ", "0")
        monkeypatch.setenv("ZELLIJ_SESSION_NAME", "my-session")
        monkeypatch.setenv("ZELLIJ_PANE_ID", "5")

        from hive_cli.utils.zellij import _get_state_file

        result = _get_state_file()
        assert result is not None
        assert str(result).endswith("5.json")
        assert "my-session" in str(result)

    def test_read_state_empty(self, zellij_env):
        """Test _read_state returns defaults when no state file exists."""
        from hive_cli.utils.zellij import _read_state

        state = _read_state()
        assert state == {"status": None, "branch": None, "custom_title": None}

    def test_read_write_state(self, zellij_env):
        """Test _write_state and _read_state round-trip."""
        from hive_cli.utils.zellij import _read_state, _write_state

        test_state = {
            "status": "[working]",
            "branch": "feature-x",
            "custom_title": "Test",
        }
        _write_state(test_state)

        read_state = _read_state()
        assert read_state == test_state

    def test_rebuild_pane_title_not_in_zellij(self, monkeypatch):
        """Test rebuild_pane_title returns False when not in Zellij."""
        monkeypatch.delenv("ZELLIJ", raising=False)

        from hive_cli.utils.zellij import rebuild_pane_title

        assert rebuild_pane_title() is False

    def test_rebuild_pane_title_minimal(self, zellij_env):
        """Test rebuild_pane_title with no state components.

        When HIVE_PANE_ID is set (in layout), we're appending to a layout-defined
        base name (e.g., "chat-1"), so we append [agent-name] with leading space.
        """
        from hive_cli.utils.zellij import rebuild_pane_title

        with patch("hive_cli.utils.zellij.rename_pane") as mock_rename:
            result = rebuild_pane_title()
            assert result is True
            # When HIVE_PANE_ID is set, append with leading space
            mock_rename.assert_called_once_with(" [claude]")

    def test_rebuild_pane_title_fallback_to_cwd(self, monkeypatch, tmp_path):
        """Test rebuild_pane_title uses cwd path relative to home when not set."""
        monkeypatch.setenv("ZELLIJ", "0")
        # Use a unique session name to avoid state pollution from other tests
        monkeypatch.setenv("ZELLIJ_SESSION_NAME", "test-fallback")
        monkeypatch.setenv("ZELLIJ_PANE_ID", "99")
        # Don't set HIVE_AGENT or HIVE_PANE_ID
        monkeypatch.delenv("HIVE_AGENT", raising=False)
        monkeypatch.delenv("HIVE_PANE_ID", raising=False)

        # tmp_path is not under home, so we'll get the absolute path
        test_dir = tmp_path / "my-project"
        test_dir.mkdir()
        monkeypatch.chdir(test_dir)

        from hive_cli.utils.zellij import rebuild_pane_title

        with patch("hive_cli.utils.zellij.rename_pane") as mock_rename:
            result = rebuild_pane_title()
            assert result is True
            # tmp_path is not under home, so expect absolute path
            mock_rename.assert_called_once_with(str(test_dir))

    def test_rebuild_pane_title_with_status(self, zellij_env):
        """Test rebuild_pane_title with status set.

        When HIVE_PANE_ID is set (in layout), we append [agent] and status
        with leading space.
        """
        from hive_cli.utils.zellij import _write_state, rebuild_pane_title

        _write_state({"status": "[working]", "branch": None, "custom_title": None})

        with patch("hive_cli.utils.zellij.rename_pane") as mock_rename:
            rebuild_pane_title()
            # Format: [agent] [status] with leading space
            mock_rename.assert_called_once_with(" [claude] [working]")

    def test_rebuild_pane_title_with_branch(self, zellij_env):
        """Test rebuild_pane_title with branch set.

        When HIVE_PANE_ID is set (in layout), we append [agent] and [branch]
        with leading space.
        """
        from hive_cli.utils.zellij import _write_state, rebuild_pane_title

        _write_state({"status": None, "branch": "feature-branch", "custom_title": None})

        with patch("hive_cli.utils.zellij.rename_pane") as mock_rename:
            rebuild_pane_title()
            # Format: [agent] [branch] with leading space
            mock_rename.assert_called_once_with(" [claude] [feature-branch]")

    def test_rebuild_pane_title_full(self, zellij_env):
        """Test rebuild_pane_title with all components set.

        When HIVE_PANE_ID is set (in layout), we append [agent] and all
        other info with leading space.
        """
        from hive_cli.utils.zellij import _write_state, rebuild_pane_title

        _write_state(
            {
                "status": "[working]",
                "branch": "feature-branch",
                "custom_title": "Fixing bug",
            }
        )

        with patch("hive_cli.utils.zellij.rename_pane") as mock_rename:
            rebuild_pane_title()
            # Format: [agent] [status] [branch] custom_title with leading space
            mock_rename.assert_called_once_with(
                " [claude] [working] [feature-branch] Fixing bug"
            )

    def test_set_pane_status(self, zellij_env):
        """Test set_pane_status updates state and rebuilds title."""
        from hive_cli.utils.zellij import _read_state, set_pane_status

        with patch("hive_cli.utils.zellij.rename_pane"):
            result = set_pane_status("[working]")
            assert result is True

        state = _read_state()
        assert state["status"] == "[working]"

    def test_set_pane_status_clear(self, zellij_env):
        """Test set_pane_status clears status when None is passed."""
        from hive_cli.utils.zellij import _read_state, _write_state, set_pane_status

        _write_state({"status": "[working]", "branch": None, "custom_title": None})

        with patch("hive_cli.utils.zellij.rename_pane"):
            set_pane_status(None)

        state = _read_state()
        assert state["status"] is None

    def test_set_pane_branch(self, zellij_env):
        """Test set_pane_branch updates state and rebuilds title."""
        from hive_cli.utils.zellij import _read_state, set_pane_branch

        with patch("hive_cli.utils.zellij.rename_pane"):
            result = set_pane_branch("feature-x")
            assert result is True

        state = _read_state()
        assert state["branch"] == "feature-x"

    def test_set_pane_custom_title(self, zellij_env):
        """Test set_pane_custom_title updates state and rebuilds title."""
        from hive_cli.utils.zellij import _read_state, set_pane_custom_title

        with patch("hive_cli.utils.zellij.rename_pane"):
            result = set_pane_custom_title("My task")
            assert result is True

        state = _read_state()
        assert state["custom_title"] == "My task"

    def test_set_pane_custom_title_replaces(self, zellij_env):
        """Test set_pane_custom_title replaces previous title (not appends)."""
        from hive_cli.utils.zellij import (
            _read_state,
            _write_state,
            set_pane_custom_title,
        )

        _write_state({"status": None, "branch": None, "custom_title": "Old title"})

        with patch("hive_cli.utils.zellij.rename_pane"):
            set_pane_custom_title("New title")

        state = _read_state()
        assert state["custom_title"] == "New title"


class TestSetStatusCommand:
    """Tests for hive zellij set-status command."""

    def test_set_status_not_in_zellij(
        self, cli_runner: CycloptsTestRunner, monkeypatch
    ):
        """Test set-status shows message when not in Zellij."""
        monkeypatch.delenv("ZELLIJ", raising=False)

        result = cli_runner.invoke(app, ["zellij", "set-status", "[working]"])
        assert "Not running in Zellij session" in result.output

    def test_set_status_in_zellij(self, cli_runner: CycloptsTestRunner, monkeypatch):
        """Test set-status works when in Zellij."""
        monkeypatch.setenv("ZELLIJ", "0")
        monkeypatch.setenv("ZELLIJ_SESSION_NAME", "test")
        monkeypatch.setenv("ZELLIJ_PANE_ID", "1")
        monkeypatch.setenv("HIVE_AGENT", "claude")
        monkeypatch.setenv("HIVE_PANE_ID", "1")

        with patch("hive_cli.utils.zellij.rename_pane"):
            result = cli_runner.invoke(app, ["zellij", "set-status", "[working]"])
            assert "Not running in Zellij session" not in result.output


class TestSetTitleCommand:
    """Tests for hive zellij set-title command."""

    def test_set_title_not_in_zellij(self, cli_runner: CycloptsTestRunner, monkeypatch):
        """Test set-title shows message when not in Zellij."""
        monkeypatch.delenv("ZELLIJ", raising=False)

        result = cli_runner.invoke(app, ["zellij", "set-title", "My task"])
        assert "Not running in Zellij session" in result.output

    def test_set_title_in_zellij(self, cli_runner: CycloptsTestRunner, monkeypatch):
        """Test set-title works when in Zellij."""
        monkeypatch.setenv("ZELLIJ", "0")
        monkeypatch.setenv("ZELLIJ_SESSION_NAME", "test")
        monkeypatch.setenv("ZELLIJ_PANE_ID", "1")
        monkeypatch.setenv("HIVE_AGENT", "claude")
        monkeypatch.setenv("HIVE_PANE_ID", "1")

        with patch("hive_cli.utils.zellij.rename_pane"):
            result = cli_runner.invoke(app, ["zellij", "set-title", "My task"])
            assert "Not running in Zellij session" not in result.output
