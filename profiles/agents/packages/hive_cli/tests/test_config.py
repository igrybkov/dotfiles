"""Tests for the configuration module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from hive_cli.config import (
    KNOWN_AGENTS,
    AgentConfig,
    deep_merge,
    find_config_files,
    find_global_config,
    get_xdg_config_home,
    load_config,
    reload_config,
)


class TestDeepMerge:
    """Tests for the deep_merge utility function."""

    def test_merge_flat_dicts(self):
        """Merge two flat dictionaries."""
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_merge_nested_dicts(self):
        """Nested dicts are merged recursively."""
        base = {"a": {"b": 1, "c": 2}}
        override = {"a": {"c": 3, "d": 4}}
        result = deep_merge(base, override)
        assert result == {"a": {"b": 1, "c": 3, "d": 4}}

    def test_lists_are_replaced(self):
        """Lists are replaced, not merged."""
        base = {"a": [1, 2, 3]}
        override = {"a": [4, 5]}
        result = deep_merge(base, override)
        assert result == {"a": [4, 5]}

    def test_base_not_modified(self):
        """Original dictionaries are not modified."""
        base = {"a": 1}
        override = {"b": 2}
        _ = deep_merge(base, override)
        assert base == {"a": 1}
        assert override == {"b": 2}

    def test_deeply_nested(self):
        """Test deeply nested structure."""
        base = {"a": {"b": {"c": 1}}}
        override = {"a": {"b": {"d": 2}}}
        result = deep_merge(base, override)
        assert result == {"a": {"b": {"c": 1, "d": 2}}}


class TestXDGConfigHome:
    """Tests for XDG config home resolution."""

    def test_default_config_home(self, monkeypatch):
        """Default to ~/.config when XDG_CONFIG_HOME not set."""
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        result = get_xdg_config_home()
        assert result == Path.home() / ".config"

    def test_custom_config_home(self, monkeypatch):
        """Use XDG_CONFIG_HOME when set."""
        monkeypatch.setenv("XDG_CONFIG_HOME", "/custom/config")
        result = get_xdg_config_home()
        assert result == Path("/custom/config")


class TestFindGlobalConfig:
    """Tests for global config file discovery."""

    def test_no_global_config(self, tmp_path, monkeypatch):
        """Returns None when no global config exists."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        result = find_global_config()
        assert result is None

    def test_find_hive_yml(self, tmp_path, monkeypatch):
        """Finds hive.yml in config directory."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        hive_dir = tmp_path / "hive"
        hive_dir.mkdir()
        config_file = hive_dir / "hive.yml"
        config_file.write_text("agents:\n  order: [claude]\n")
        result = find_global_config()
        assert result == config_file

    def test_find_hive_yaml(self, tmp_path, monkeypatch):
        """Finds hive.yaml in config directory."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        hive_dir = tmp_path / "hive"
        hive_dir.mkdir()
        config_file = hive_dir / "hive.yaml"
        config_file.write_text("agents:\n  order: [gemini]\n")
        result = find_global_config()
        assert result == config_file

    def test_yml_takes_precedence(self, tmp_path, monkeypatch):
        """hive.yml takes precedence over hive.yaml."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        hive_dir = tmp_path / "hive"
        hive_dir.mkdir()
        yml_file = hive_dir / "hive.yml"
        yaml_file = hive_dir / "hive.yaml"
        yml_file.write_text("agents:\n  order: [claude]\n")
        yaml_file.write_text("agents:\n  order: [gemini]\n")
        result = find_global_config()
        assert result == yml_file


class TestFindConfigFiles:
    """Tests for config file discovery."""

    def test_no_git_root(self, tmp_path, monkeypatch):
        """Returns empty list when not in git repo."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        # No .git directory, so find_git_root returns None
        result = find_config_files(git_root=None)
        # May return global config if it exists, but no project config
        assert all(
            not str(p).startswith(str(tmp_path))
            for p in result
            if ".config" not in str(p)
        )

    def test_finds_hive_yml(self, tmp_path, monkeypatch):
        """Finds .hive.yml in git root."""
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        config_file = tmp_path / ".hive.yml"
        config_file.write_text("agents:\n  order: [claude]\n")
        result = find_config_files(git_root=tmp_path)
        assert config_file in result

    def test_finds_hive_local_yml(self, tmp_path, monkeypatch):
        """Finds .hive.local.yml in git root."""
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        config_file = tmp_path / ".hive.local.yml"
        config_file.write_text("resume:\n  enabled: true\n")
        result = find_config_files(git_root=tmp_path)
        assert config_file in result

    def test_precedence_order(self, tmp_path, monkeypatch):
        """Files returned in correct precedence order."""
        # Set up XDG config
        xdg_dir = tmp_path / "xdg"
        xdg_dir.mkdir()
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_dir))
        hive_dir = xdg_dir / "hive"
        hive_dir.mkdir()
        global_config = hive_dir / "hive.yml"
        global_config.write_text("agents:\n  order: [gemini]\n")

        # Set up project config
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        project_config = project_dir / ".hive.yml"
        project_config.write_text("agents:\n  order: [claude]\n")
        local_config = project_dir / ".hive.local.yml"
        local_config.write_text("resume:\n  enabled: true\n")

        result = find_config_files(git_root=project_dir)

        # Order should be: global, project, local
        assert result == [global_config, project_config, local_config]


class TestLoadConfig:
    """Tests for configuration loading."""

    def test_default_config(self, tmp_path, monkeypatch):
        """Returns default config when no files exist."""
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.delenv("HIVE_AGENTS_ORDER", raising=False)
        monkeypatch.delenv("GIT_WORKTREES_HOME", raising=False)

        # Clear cache and mock find_config_files to return empty
        reload_config.cache_clear() if hasattr(reload_config, "cache_clear") else None
        load_config.cache_clear()

        with patch("hive_cli.config.loader.find_config_files", return_value=[]):
            config = load_config()

        assert config.agents.order == KNOWN_AGENTS
        assert config.resume.enabled is False
        assert config.worktrees.enabled is True
        assert config.worktrees.parent_dir == ".worktrees"
        assert config.zellij.layout is None  # No layout by default

    def test_config_from_file(self, tmp_path, monkeypatch):
        """Loads config from file."""
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.delenv("HIVE_AGENTS_ORDER", raising=False)

        config_file = tmp_path / ".hive.yml"
        config_file.write_text("""
agents:
  order: [gemini, claude]
resume:
  enabled: true
worktrees:
  parent_dir: ".wt"
zellij:
  layout: "custom-layout"
""")

        load_config.cache_clear()
        with patch(
            "hive_cli.config.loader.find_config_files", return_value=[config_file]
        ):
            config = load_config()

        assert config.agents.order == ["gemini", "claude"]
        assert config.resume.enabled is True
        assert config.worktrees.parent_dir == ".wt"
        assert config.zellij.layout == "custom-layout"

    def test_local_overrides_project(self, tmp_path, monkeypatch):
        """Local config overrides project config."""
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.delenv("HIVE_AGENTS_ORDER", raising=False)

        project_config = tmp_path / ".hive.yml"
        project_config.write_text("""
agents:
  order: [gemini, claude]
resume:
  enabled: false
""")

        local_config = tmp_path / ".hive.local.yml"
        local_config.write_text("""
resume:
  enabled: true
""")

        load_config.cache_clear()
        with patch(
            "hive_cli.config.loader.find_config_files",
            return_value=[project_config, local_config],
        ):
            config = load_config()

        # agents.order from project config (not overridden)
        assert config.agents.order == ["gemini", "claude"]
        # resume.enabled overridden by local
        assert config.resume.enabled is True

    def test_env_var_fallback(self, tmp_path, monkeypatch):
        """Environment variables used as fallback."""
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.setenv("HIVE_AGENTS_ORDER", "codex,claude")
        monkeypatch.setenv("HIVE_WORKTREES_USE_HOME", "true")

        load_config.cache_clear()
        with patch("hive_cli.config.loader.find_config_files", return_value=[]):
            config = load_config()

        assert config.agents.order == ["codex", "claude"]
        assert config.worktrees.use_home is True

    def test_legacy_git_worktrees_home_env(self, tmp_path, monkeypatch):
        """Legacy GIT_WORKTREES_HOME environment variable still works."""
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.setenv("GIT_WORKTREES_HOME", "true")

        load_config.cache_clear()
        with patch("hive_cli.config.loader.find_config_files", return_value=[]):
            config = load_config()

        assert config.worktrees.use_home is True

    def test_env_overrides_config(self, tmp_path, monkeypatch):
        """Environment variables take precedence over config files."""
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.setenv("HIVE_AGENTS_ORDER", "codex,claude")

        config_file = tmp_path / ".hive.yml"
        config_file.write_text("""
agents:
  order: [gemini]
""")

        load_config.cache_clear()
        with patch(
            "hive_cli.config.loader.find_config_files", return_value=[config_file]
        ):
            config = load_config()

        # Environment variable takes precedence over config file
        assert config.agents.order == ["codex", "claude"]

    def test_new_env_overrides_legacy_worktrees(self, tmp_path, monkeypatch):
        """New HIVE_* env vars take precedence over legacy env vars."""
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.setenv("GIT_WORKTREES_HOME", "true")
        monkeypatch.setenv("HIVE_WORKTREES_USE_HOME", "false")

        load_config.cache_clear()
        with patch("hive_cli.config.loader.find_config_files", return_value=[]):
            config = load_config()

        # New HIVE_* env var takes precedence over legacy
        assert config.worktrees.use_home is False

    def test_hive_worktrees_enabled_env(self, tmp_path, monkeypatch):
        """HIVE_WORKTREES_ENABLED env var works."""
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.setenv("HIVE_WORKTREES_ENABLED", "false")

        load_config.cache_clear()
        with patch("hive_cli.config.loader.find_config_files", return_value=[]):
            config = load_config()

        assert config.worktrees.enabled is False

    def test_hive_worktrees_parent_dir_env(self, tmp_path, monkeypatch):
        """HIVE_WORKTREES_PARENT_DIR env var works."""
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.setenv("HIVE_WORKTREES_PARENT_DIR", "/custom/worktrees")

        load_config.cache_clear()
        with patch("hive_cli.config.loader.find_config_files", return_value=[]):
            config = load_config()

        assert config.worktrees.parent_dir == "/custom/worktrees"

    def test_hive_resume_enabled_env(self, tmp_path, monkeypatch):
        """HIVE_RESUME_ENABLED env var works."""
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.setenv("HIVE_RESUME_ENABLED", "true")

        load_config.cache_clear()
        with patch("hive_cli.config.loader.find_config_files", return_value=[]):
            config = load_config()

        assert config.resume.enabled is True

    def test_hive_zellij_layout_env(self, tmp_path, monkeypatch):
        """HIVE_ZELLIJ_LAYOUT env var works."""
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.setenv("HIVE_ZELLIJ_LAYOUT", "custom-layout")

        load_config.cache_clear()
        with patch("hive_cli.config.loader.find_config_files", return_value=[]):
            config = load_config()

        assert config.zellij.layout == "custom-layout"

    def test_hive_github_issue_limit_env(self, tmp_path, monkeypatch):
        """HIVE_GITHUB_ISSUE_LIMIT env var works."""
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.setenv("HIVE_GITHUB_ISSUE_LIMIT", "50")

        load_config.cache_clear()
        with patch("hive_cli.config.loader.find_config_files", return_value=[]):
            config = load_config()

        assert config.github.issue_limit == 50


class TestAgentConfig:
    """Tests for agent-specific configuration."""

    def test_empty_resume_args_by_default(self):
        """AgentConfig dataclass has empty resume_args by default."""
        config = AgentConfig()
        assert config.resume_args == []

    def test_custom_resume_args(self):
        """Custom resume args work."""
        config = AgentConfig(resume_args=["resume", "--last"])
        assert config.resume_args == ["resume", "--last"]

    def test_claude_resume_args_from_default_config(self, tmp_path, monkeypatch):
        """Claude gets --continue from default.yml config."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
        monkeypatch.delenv("HIVE_AGENTS_ORDER", raising=False)

        load_config.cache_clear()
        with patch("hive_cli.config.loader.find_config_files", return_value=[]):
            config = load_config()

        # Claude should have --continue from default.yml
        assert config.agents.configs.get("claude") is not None
        assert config.agents.configs["claude"].resume_args == ["--continue"]


class TestPostCreateCommands:
    """Tests for post_create command configuration."""

    def test_parse_simple_command(self, tmp_path, monkeypatch):
        """Parse simple command string."""
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

        config_file = tmp_path / ".hive.yml"
        config_file.write_text("""
worktrees:
  post_create:
    - "npm install"
""")

        load_config.cache_clear()
        with patch(
            "hive_cli.config.loader.find_config_files", return_value=[config_file]
        ):
            config = load_config()

        assert len(config.worktrees.post_create) == 1
        assert config.worktrees.post_create[0].command == "npm install"
        assert config.worktrees.post_create[0].if_exists is None

    def test_parse_conditional_command(self, tmp_path, monkeypatch):
        """Parse command with if_exists condition."""
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

        config_file = tmp_path / ".hive.yml"
        config_file.write_text("""
worktrees:
  post_create:
    - command: "pnpm install"
      if_exists: "pnpm-lock.yaml"
""")

        load_config.cache_clear()
        with patch(
            "hive_cli.config.loader.find_config_files", return_value=[config_file]
        ):
            config = load_config()

        assert len(config.worktrees.post_create) == 1
        assert config.worktrees.post_create[0].command == "pnpm install"
        assert config.worktrees.post_create[0].if_exists == "pnpm-lock.yaml"


class TestCaching:
    """Tests for configuration caching."""

    def test_reload_clears_cache(self, tmp_path, monkeypatch):
        """reload_config clears cache and reloads."""
        # Set XDG to empty dir to avoid picking up real global config
        empty_xdg = tmp_path / "empty_xdg"
        empty_xdg.mkdir()
        monkeypatch.setenv("XDG_CONFIG_HOME", str(empty_xdg))
        monkeypatch.delenv("HIVE_AGENTS_ORDER", raising=False)

        config_file = tmp_path / ".hive.yml"
        config_file.write_text("agents:\n  order: [claude]\n")

        load_config.cache_clear()
        with patch(
            "hive_cli.config.loader.find_config_files", return_value=[config_file]
        ):
            config1 = load_config()
            assert config1.agents.order == ["claude"]

            # Update file
            config_file.write_text("agents:\n  order: [gemini]\n")

            # Without reload, still returns cached
            config2 = load_config()
            assert config2.agents.order == ["claude"]

            # After reload, returns new value
            config3 = reload_config()
            assert config3.agents.order == ["gemini"]
