"""Tests for the wt command."""

from __future__ import annotations

from conftest import CycloptsTestRunner

from hive_cli.app import app


class TestWtCommand:
    """Tests for hive wt command."""

    def test_wt_help(self, cli_runner: CycloptsTestRunner):
        """Test that wt --help shows help text."""
        result = cli_runner.invoke(app, ["wt", "--help"])
        assert result.exit_code == 0
        assert "Manage git worktrees" in result.output
        assert "cd" in result.output
        assert "list" in result.output
        assert "create" in result.output


class TestWtListCommand:
    """Tests for hive wt list command."""

    def test_list_shows_worktrees(self, cli_runner: CycloptsTestRunner, temp_git_repo):
        """Test that list shows worktrees."""
        result = cli_runner.invoke(app, ["wt", "list"])
        assert result.exit_code == 0
        assert "main:" in result.output
        assert str(temp_git_repo) in result.output


class TestWtPathCommand:
    """Tests for hive wt path command."""

    def test_path_main(self, cli_runner: CycloptsTestRunner, temp_git_repo):
        """Test path for main returns main repo."""
        result = cli_runner.invoke(app, ["wt", "path", "main"])
        assert result.exit_code == 0
        assert str(temp_git_repo) in result.output

    def test_path_one(self, cli_runner: CycloptsTestRunner, temp_git_repo):
        """Test path for '1' returns main repo."""
        result = cli_runner.invoke(app, ["wt", "path", "1"])
        assert result.exit_code == 0
        assert str(temp_git_repo) in result.output

    def test_path_branch(self, cli_runner: CycloptsTestRunner, temp_git_repo):
        """Test path for branch returns worktree path."""
        result = cli_runner.invoke(app, ["wt", "path", "feature-123"])
        assert result.exit_code == 0
        assert ".worktrees" in result.output
        assert "feature-123" in result.output


class TestWtBaseCommand:
    """Tests for hive wt base command."""

    def test_base_shows_directory(self, cli_runner: CycloptsTestRunner, temp_git_repo):
        """Test base shows worktrees directory."""
        result = cli_runner.invoke(app, ["wt", "base"])
        assert result.exit_code == 0
        assert ".worktrees" in result.output


class TestWtExistsCommand:
    """Tests for hive wt exists command."""

    def test_exists_main(self, cli_runner: CycloptsTestRunner, temp_git_repo):
        """Test exists returns 0 for main."""
        result = cli_runner.invoke(app, ["wt", "exists", "main"])
        assert result.exit_code == 0

    def test_exists_nonexistent(self, cli_runner: CycloptsTestRunner, temp_git_repo):
        """Test exists returns 1 for non-existent worktree."""
        result = cli_runner.invoke(app, ["wt", "exists", "nonexistent"])
        assert result.exit_code == 1


class TestWtCdCommand:
    """Tests for hive wt cd command."""

    def test_cd_main(self, cli_runner: CycloptsTestRunner, temp_git_repo):
        """Test cd main outputs main repo path."""
        result = cli_runner.invoke(app, ["wt", "cd", "main"])
        assert result.exit_code == 0
        assert str(temp_git_repo) in result.output

    def test_cd_nonexistent_branch(self, cli_runner: CycloptsTestRunner, temp_git_repo):
        """Test cd non-existent branch fails."""
        result = cli_runner.invoke(app, ["wt", "cd", "nonexistent"])
        assert result.exit_code == 1
        assert "does not exist" in result.output

    def test_cd_no_branch_non_interactive(
        self, cli_runner: CycloptsTestRunner, temp_git_repo
    ):
        """Test cd without branch in non-interactive mode fails."""
        # CycloptsTestRunner is non-interactive by default
        result = cli_runner.invoke(app, ["wt", "cd"])
        assert result.exit_code == 1
        assert "not in interactive mode" in result.output


class TestWtDeleteCommand:
    """Tests for hive wt delete command."""

    def test_delete_main_fails(self, cli_runner: CycloptsTestRunner, temp_git_repo):
        """Test delete main fails."""
        result = cli_runner.invoke(app, ["wt", "delete", "main"])
        assert result.exit_code == 1
        assert "Cannot delete main" in result.output

    def test_delete_nonexistent_fails(
        self, cli_runner: CycloptsTestRunner, temp_git_repo
    ):
        """Test delete non-existent worktree fails."""
        result = cli_runner.invoke(app, ["wt", "delete", "nonexistent"])
        assert result.exit_code == 1
        assert "does not exist" in result.output


class TestWtCreateCommand:
    """Tests for hive wt create command."""

    def test_create_main_fails(self, cli_runner: CycloptsTestRunner, temp_git_repo):
        """Test create main fails."""
        result = cli_runner.invoke(app, ["wt", "create", "main"])
        assert result.exit_code == 1

    def test_create_new_branch(self, cli_runner: CycloptsTestRunner, temp_git_repo):
        """Test create new branch worktree."""
        result = cli_runner.invoke(
            app, ["wt", "create", "test-feature", "--no-install"]
        )
        assert result.exit_code == 0
        assert "Created worktree" in result.output
        assert "test-feature" in result.output


class TestWtEnsureCommand:
    """Tests for hive wt ensure command."""

    def test_ensure_agent_1(self, cli_runner: CycloptsTestRunner, temp_git_repo):
        """Test ensure agent 1 returns main repo."""
        result = cli_runner.invoke(app, ["wt", "ensure", "1"])
        assert result.exit_code == 0
        assert str(temp_git_repo) in result.output

    def test_ensure_agent_2_non_interactive(
        self, cli_runner: CycloptsTestRunner, temp_git_repo
    ):
        """Test ensure agent 2 in non-interactive mode fails."""
        result = cli_runner.invoke(app, ["wt", "ensure", "2"])
        assert result.exit_code == 1
        assert "Interactive mode required" in result.output
