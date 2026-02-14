"""Tests for git worktree module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from hive_cli.config import reload_config
from hive_cli.git.worktree import (
    WorktreeInfo,
    get_worktree_path,
    get_worktrees_base,
    list_worktrees,
    sanitize_branch_name,
    worktree_exists,
)


class TestSanitizeBranchName:
    """Tests for sanitize_branch_name function."""

    def test_simple_branch(self):
        """Test branch name with no special characters."""
        assert sanitize_branch_name("feature-123") == "feature-123"

    def test_branch_with_slash(self):
        """Test branch name with slashes becomes double dashes."""
        assert sanitize_branch_name("user/feat/update") == "user--feat--update"

    def test_single_slash(self):
        """Test branch with single slash."""
        assert sanitize_branch_name("user/feature") == "user--feature"

    def test_special_characters(self):
        """Test special characters are replaced with dashes."""
        assert sanitize_branch_name("feat@test!") == "feat-test"

    def test_leading_trailing_dashes_removed(self):
        """Test leading/trailing dashes are trimmed."""
        assert sanitize_branch_name("-feat-") == "feat"

    def test_underscores_preserved(self):
        """Test underscores are preserved."""
        assert sanitize_branch_name("feat_test_123") == "feat_test_123"

    def test_dots_preserved(self):
        """Test dots are preserved."""
        assert sanitize_branch_name("v1.2.3-fix") == "v1.2.3-fix"


class TestGetWorktreesBase:
    """Tests for get_worktrees_base function."""

    def test_default_local_mode(self, monkeypatch, tmp_path):
        """Test default uses local .worktrees directory."""
        # Set XDG to empty dir to avoid global config
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
        monkeypatch.delenv("GIT_WORKTREES_HOME", raising=False)
        reload_config()

        with patch("hive_cli.git.worktree.get_main_repo", return_value=tmp_path):
            base = get_worktrees_base()
            assert base == tmp_path / ".worktrees"

    def test_home_mode_from_env(self, monkeypatch, tmp_path):
        """Test GIT_WORKTREES_HOME=true uses home directory."""
        # Set XDG to empty dir to avoid global config
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
        monkeypatch.setenv("GIT_WORKTREES_HOME", "true")
        reload_config()

        with patch("hive_cli.git.worktree.get_main_repo", return_value=tmp_path):
            base = get_worktrees_base()
            assert base == Path.home() / ".git-worktrees"

    def test_home_mode_from_config(self, monkeypatch, tmp_path):
        """Test worktrees.use_home from config file."""
        # Create config file
        config_file = tmp_path / ".hive.yml"
        config_file.write_text("worktrees:\n  use_home: true\n")

        # Set XDG to empty dir to avoid global config
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
        monkeypatch.delenv("GIT_WORKTREES_HOME", raising=False)

        with patch(
            "hive_cli.config.loader.find_config_files", return_value=[config_file]
        ):
            reload_config()
            with patch("hive_cli.git.worktree.get_main_repo", return_value=tmp_path):
                base = get_worktrees_base()
                assert base == Path.home() / ".git-worktrees"

    def test_custom_parent_dir(self, monkeypatch, tmp_path):
        """Test custom worktrees.parent_dir from config."""
        # Create config file
        config_file = tmp_path / ".hive.yml"
        config_file.write_text("worktrees:\n  parent_dir: custom-wt\n")

        # Set XDG to empty dir to avoid global config
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
        monkeypatch.delenv("GIT_WORKTREES_HOME", raising=False)

        with patch(
            "hive_cli.config.loader.find_config_files", return_value=[config_file]
        ):
            reload_config()
            with patch("hive_cli.git.worktree.get_main_repo", return_value=tmp_path):
                base = get_worktrees_base()
                assert base == tmp_path / "custom-wt"

    def test_explicit_main_repo(self, monkeypatch, tmp_path):
        """Test passing explicit main_repo."""
        # Set XDG to empty dir to avoid global config
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
        monkeypatch.delenv("GIT_WORKTREES_HOME", raising=False)
        reload_config()

        base = get_worktrees_base(tmp_path)
        assert base == tmp_path / ".worktrees"


class TestGetWorktreePath:
    """Tests for get_worktree_path function."""

    def test_main_returns_main_repo(self, tmp_path):
        """Test 'main' returns main repo path."""
        path = get_worktree_path("main", tmp_path)
        assert path == tmp_path

    def test_one_returns_main_repo(self, tmp_path):
        """Test '1' returns main repo path."""
        path = get_worktree_path("1", tmp_path)
        assert path == tmp_path

    def test_branch_returns_worktree_path(self, monkeypatch, tmp_path):
        """Test branch name returns worktree path."""
        # Set XDG to empty dir to avoid global config
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
        monkeypatch.delenv("GIT_WORKTREES_HOME", raising=False)
        reload_config()

        path = get_worktree_path("feature-123", tmp_path)
        assert path == tmp_path / ".worktrees" / "feature-123"

    def test_branch_with_slash(self, monkeypatch, tmp_path):
        """Test branch with slashes is sanitized."""
        # Set XDG to empty dir to avoid global config
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
        monkeypatch.delenv("GIT_WORKTREES_HOME", raising=False)
        reload_config()

        path = get_worktree_path("user/feat/update", tmp_path)
        assert path == tmp_path / ".worktrees" / "user--feat--update"


class TestWorktreeExists:
    """Tests for worktree_exists function."""

    def test_main_always_exists(self, tmp_path):
        """Test 'main' always returns True."""
        assert worktree_exists("main", tmp_path) is True

    def test_one_always_exists(self, tmp_path):
        """Test '1' always returns True."""
        assert worktree_exists("1", tmp_path) is True

    def test_nonexistent_branch(self, monkeypatch, tmp_path):
        """Test non-existent worktree returns False."""
        # Set XDG to empty dir to avoid global config
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
        monkeypatch.delenv("GIT_WORKTREES_HOME", raising=False)
        reload_config()

        assert worktree_exists("nonexistent", tmp_path) is False

    def test_existing_worktree(self, monkeypatch, tmp_path):
        """Test existing worktree returns True."""
        # Set XDG to empty dir to avoid global config
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
        monkeypatch.delenv("GIT_WORKTREES_HOME", raising=False)
        reload_config()

        # Create the worktree directory
        (tmp_path / ".worktrees" / "feature-123").mkdir(parents=True)
        assert worktree_exists("feature-123", tmp_path) is True


class TestListWorktrees:
    """Tests for list_worktrees function."""

    def test_main_repo_always_included(self, temp_git_repo):
        """Test main repo is always in the list."""
        worktrees = list_worktrees(temp_git_repo)
        assert len(worktrees) >= 1
        assert worktrees[0].branch == "main"
        assert worktrees[0].is_main is True
        assert worktrees[0].path == temp_git_repo


class TestWorktreeInfo:
    """Tests for WorktreeInfo dataclass."""

    def test_creation(self, tmp_path):
        """Test creating a WorktreeInfo instance."""
        info = WorktreeInfo(branch="feature", path=tmp_path, is_main=False)
        assert info.branch == "feature"
        assert info.path == tmp_path
        assert info.is_main is False

    def test_default_is_main(self, tmp_path):
        """Test default is_main is False."""
        info = WorktreeInfo(branch="feature", path=tmp_path)
        assert info.is_main is False
