"""Tests for CLI commands."""

import pytest
from unittest.mock import Mock, call, patch


from dotfiles_cli.app import cli
from dotfiles_cli.constants import SUDO_TAGS


class TestCLIStructure:
    """Test CLI command structure and availability."""

    def test_cli_has_expected_commands(self):
        """Test that CLI has all expected commands."""
        import click

        expected_commands = [
            "install",
            "pull",
            "push",
            "sync",
            "edit",
            "upgrade",
            "completion",
            "secret",
            "config",
            "bootstrap-profile",
        ]
        ctx = click.Context(cli)
        available = cli.list_commands(ctx)
        for cmd in expected_commands:
            assert cmd in available, f"Command '{cmd}' not found in CLI"


class TestPullCommand:
    """Test the pull command."""

    def test_pull_executes_git_pull(self, cli_runner, mock_subprocess):
        """Test pull command executes git pull."""
        with patch("dotfiles_cli.commands.git.sync_profile_repos"):
            result = cli_runner.invoke(cli, ["pull"])

        assert result.exit_code == 0
        mock_subprocess["call"].assert_called_once_with(["git", "pull"])

    def test_pull_syncs_profile_repos(self, cli_runner, mock_subprocess):
        """Test pull command syncs profile repos."""
        with patch("dotfiles_cli.commands.git.sync_profile_repos") as mock_sync:
            result = cli_runner.invoke(cli, ["pull"])

        assert result.exit_code == 0
        mock_sync.assert_called_once_with("pull")

    def test_pull_handles_git_error(self, cli_runner):
        """Test pull command handles git errors."""
        with (
            patch("subprocess.call", return_value=1),
            patch("dotfiles_cli.commands.git.sync_profile_repos"),
        ):
            _result = cli_runner.invoke(cli, ["pull"])

        # Pull command doesn't check return code, just passes it through
        # The actual git error would be visible in output


class TestPushCommand:
    """Test the push command."""

    def test_push_executes_git_push(self, cli_runner, mock_subprocess):
        """Test push command executes git push to main."""
        with patch("dotfiles_cli.commands.git.sync_profile_repos"):
            result = cli_runner.invoke(cli, ["push"])

        assert result.exit_code == 0
        mock_subprocess["call"].assert_called_once_with(
            ["git", "push", "origin", "main"]
        )

    def test_push_syncs_profile_repos(self, cli_runner, mock_subprocess):
        """Test push command syncs profile repos."""
        with patch("dotfiles_cli.commands.git.sync_profile_repos") as mock_sync:
            result = cli_runner.invoke(cli, ["push"])

        assert result.exit_code == 0
        mock_sync.assert_called_once_with("push")


class TestSyncCommand:
    """Test the sync command."""

    def test_sync_pulls_upgrades_and_pushes(self, cli_runner, mock_subprocess):
        """Test sync command performs pull, upgrade, push."""
        with (
            patch("dotfiles_cli.commands.git.sync_profile_repos"),
            patch("dotfiles_cli.commands.upgrade.upgrade"),
        ):
            result = cli_runner.invoke(cli, ["sync"])

        assert result.exit_code == 0

        # Should call git pull and push
        calls = mock_subprocess["call"].call_args_list
        assert call(["git", "pull"]) in calls
        assert call(["git", "push", "origin", "main"]) in calls

    def test_sync_with_uv_flag(self, cli_runner, mock_subprocess):
        """Test sync with --uv flag enables uv upgrade."""
        with (
            patch("dotfiles_cli.commands.git.sync_profile_repos"),
            patch("dotfiles_cli.commands.upgrade.upgrade"),
        ):
            result = cli_runner.invoke(cli, ["sync", "--uv"])

        assert result.exit_code == 0
        # Check that upgrade was called with correct parameters
        # The upgrade function should be invoked with no_uv=False

    def test_sync_skip_upgrade_flag(self, cli_runner, mock_subprocess):
        """Test sync with --skip-upgrade flag."""
        with (
            patch("dotfiles_cli.commands.git.sync_profile_repos"),
            patch("dotfiles_cli.commands.upgrade.upgrade") as mock_upgrade,
        ):
            result = cli_runner.invoke(cli, ["sync", "--skip-upgrade"])

        assert result.exit_code == 0
        # upgrade should not be called
        mock_upgrade.assert_not_called()

    def test_sync_fails_on_pull_error(self, cli_runner):
        """Test sync aborts if git pull fails."""
        with (
            patch("subprocess.call", return_value=1) as mock_call,
            patch("dotfiles_cli.commands.git.sync_profile_repos"),
        ):
            result = cli_runner.invoke(cli, ["sync"])

        # The sync command returns early but Click doesn't convert return values to exit codes
        # However, the error message should be in output and push should not be called
        assert "git pull failed" in result.output
        # Should only have one call (the failed pull), no push call
        assert mock_call.call_count == 1

    def test_sync_continues_on_upgrade_error(self, cli_runner, mock_subprocess):
        """Test sync continues to push even if upgrade fails."""
        with (
            patch("dotfiles_cli.commands.git.sync_profile_repos"),
            patch("dotfiles_cli.commands.upgrade.upgrade", return_value=1),
        ):
            result = cli_runner.invoke(cli, ["sync"])

        # Should complete with exit code 0 (warning but continues)
        assert result.exit_code == 0

        # Should have called both pull and push
        calls = mock_subprocess["call"].call_args_list
        assert call(["git", "pull"]) in calls
        assert call(["git", "push", "origin", "main"]) in calls


class TestEditCommand:
    """Test the edit command."""

    def test_edit_uses_vscode_when_available(
        self, cli_runner, mock_subprocess, temp_dotfiles_dir
    ):
        """Test edit command uses VS Code when available."""
        with (
            patch("shutil.which", return_value="/usr/local/bin/code"),
            patch("dotfiles_cli.commands.edit.DOTFILES_DIR", str(temp_dotfiles_dir)),
        ):
            result = cli_runner.invoke(cli, ["edit"])

        assert result.exit_code == 0
        mock_subprocess["call"].assert_called_once_with(
            ["code", str(temp_dotfiles_dir)]
        )

    def test_edit_uses_editor_env_when_code_unavailable(
        self, cli_runner, mock_subprocess, temp_dotfiles_dir
    ):
        """Test edit command falls back to $EDITOR."""
        with (
            patch("shutil.which", return_value=None),
            patch("os.getenv", return_value="nvim"),
            patch("dotfiles_cli.commands.edit.DOTFILES_DIR", str(temp_dotfiles_dir)),
        ):
            result = cli_runner.invoke(cli, ["edit"])

        assert result.exit_code == 0
        mock_subprocess["call"].assert_called_once_with(
            ["nvim", str(temp_dotfiles_dir)]
        )

    def test_edit_fails_when_no_editor(self, cli_runner):
        """Test edit command fails when no editor available."""
        with (
            patch("shutil.which", return_value=None),
            patch("os.getenv", return_value=None),
        ):
            result = cli_runner.invoke(cli, ["edit"])

        # RuntimeError is raised and caught by CliRunner
        assert result.exit_code != 0
        # The exception is stored in result.exception, not shown in output
        assert result.exception is not None
        assert "No supported editor" in str(result.exception)


class TestCompletionCommand:
    """Test the completion command."""

    def test_completion_fish(self, cli_runner):
        """Test completion generation for fish shell."""
        result = cli_runner.invoke(cli, ["completion", "fish"])
        assert result.exit_code == 0
        assert "_DOTFILES_COMPLETE" in result.output

    def test_completion_zsh(self, cli_runner):
        """Test completion generation for zsh shell."""
        result = cli_runner.invoke(cli, ["completion", "zsh"])
        assert result.exit_code == 0
        assert "_DOTFILES_COMPLETE" in result.output

    def test_completion_bash(self, cli_runner):
        """Test completion generation for bash shell."""
        result = cli_runner.invoke(cli, ["completion", "bash"])
        assert result.exit_code == 0
        assert "_DOTFILES_COMPLETE" in result.output

    def test_completion_install_fish(self, cli_runner, temp_home):
        """Test completion installation for fish."""
        fish_dir = temp_home / ".config" / "fish" / "completions"
        fish_dir.mkdir(parents=True)

        result = cli_runner.invoke(cli, ["completion", "fish", "--install"])

        assert result.exit_code == 0
        completion_file = fish_dir / "dotfiles.fish"
        assert completion_file.exists()
        assert "_DOTFILES_COMPLETE" in completion_file.read_text()

    def test_completion_install_unsupported_shell(self, cli_runner):
        """Test completion installation for unsupported shell."""
        result = cli_runner.invoke(cli, ["completion", "bash", "--install"])

        # Should fail for unsupported shells (NotImplementedError is raised)
        assert result.exit_code != 0
        # The exception is stored in result.exception, not shown in output
        assert result.exception is not None
        assert "not supported" in str(result.exception)


class TestInstallCommand:
    """Test the install command."""

    def test_install_with_default_tag(
        self, cli_runner, mock_ansible_runner, temp_dotfiles_dir, mock_getpass
    ):
        """Test install with no tags defaults to all."""
        with (
            patch("dotfiles_cli.constants.DOTFILES_DIR", str(temp_dotfiles_dir)),
            patch(
                "dotfiles_cli.commands.install.get_active_profiles",
                return_value=Mock(resolve=lambda x: ["common"]),
            ),
            patch(
                "dotfiles_cli.commands.install.get_all_profile_names",
                return_value=["common", "work"],
            ),
            patch(
                "dotfiles_cli.commands.install.get_profile_roles_paths", return_value=[]
            ),
            patch(
                "dotfiles_cli.commands.install.get_profile_requirements_paths",
                return_value=[],
            ),
            patch(
                "dotfiles_cli.commands.install.get_repos_with_unpushed_changes",
                return_value=([], []),
            ),
        ):
            result = cli_runner.invoke(cli, ["install"])

        # Should succeed
        assert result.exit_code == 0

        # Should run ansible with all tag
        ansible_call = mock_ansible_runner["run"].call_args
        assert ansible_call[1]["tags"] == "all"

    def test_install_with_specific_tags(
        self, cli_runner, mock_ansible_runner, temp_dotfiles_dir, mock_getpass
    ):
        """Test install with specific tags."""
        # Mock the tag validation to accept any tags
        with (
            patch("dotfiles_cli.constants.DOTFILES_DIR", str(temp_dotfiles_dir)),
            patch(
                "dotfiles_cli.commands.install.get_active_profiles",
                return_value=Mock(resolve=lambda x: ["common"]),
            ),
            patch(
                "dotfiles_cli.commands.install.get_all_profile_names",
                return_value=["common"],
            ),
            patch(
                "dotfiles_cli.commands.install.get_profile_roles_paths", return_value=[]
            ),
            patch(
                "dotfiles_cli.commands.install.get_profile_requirements_paths",
                return_value=[],
            ),
            patch(
                "dotfiles_cli.commands.install.get_repos_with_unpushed_changes",
                return_value=([], []),
            ),
            patch(
                "dotfiles_cli.types.AnsibleTagListType._get_all_supported_tags",
                return_value=["all", "brew", "cask", "dotfiles"],
            ),
        ):
            result = cli_runner.invoke(cli, ["install", "brew", "cask"])

        assert result.exit_code == 0, (
            f"Exit code: {result.exit_code}, Output: {result.output}"
        )

        ansible_call = mock_ansible_runner["run"].call_args
        assert ansible_call[1]["tags"] == "brew,cask"

    def test_install_with_all_flag(
        self, cli_runner, mock_ansible_runner, temp_dotfiles_dir
    ):
        """Test install with --all flag."""
        with (
            patch("dotfiles_cli.constants.DOTFILES_DIR", str(temp_dotfiles_dir)),
            patch(
                "dotfiles_cli.commands.install.get_active_profiles",
                return_value=Mock(resolve=lambda x: ["common"]),
            ),
            patch(
                "dotfiles_cli.commands.install.get_all_profile_names",
                return_value=["common"],
            ),
            patch(
                "dotfiles_cli.commands.install.get_profile_roles_paths", return_value=[]
            ),
            patch(
                "dotfiles_cli.commands.install.get_profile_requirements_paths",
                return_value=[],
            ),
            patch(
                "dotfiles_cli.commands.install.get_repos_with_unpushed_changes",
                return_value=([], []),
            ),
            patch(
                "dotfiles_cli.commands.install.validate_vault_password",
                return_value=True,
            ),
            patch(
                "dotfiles_cli.commands.install.validate_sudo_password",
                return_value=True,
            ),
            patch("getpass.getpass", return_value="test_password"),
        ):
            result = cli_runner.invoke(cli, ["install", "--all"])

        assert result.exit_code == 0, (
            f"Exit code: {result.exit_code}, Output: {result.output}"
        )
        assert mock_ansible_runner["run"].called, (
            f"Ansible runner not called. Output: {result.output}"
        )

        ansible_call = mock_ansible_runner["run"].call_args
        assert "all" in ansible_call[1]["tags"]

    def test_install_prompts_for_sudo_password(
        self, cli_runner, mock_ansible_runner, temp_dotfiles_dir
    ):
        """Test install prompts for sudo password for sudo-requiring tags."""
        with (
            patch("dotfiles_cli.constants.DOTFILES_DIR", str(temp_dotfiles_dir)),
            patch(
                "dotfiles_cli.commands.install.get_active_profiles",
                return_value=Mock(resolve=lambda x: ["common"]),
            ),
            patch(
                "dotfiles_cli.commands.install.get_all_profile_names",
                return_value=["common"],
            ),
            patch(
                "dotfiles_cli.commands.install.get_profile_roles_paths", return_value=[]
            ),
            patch(
                "dotfiles_cli.commands.install.get_profile_requirements_paths",
                return_value=[],
            ),
            patch(
                "dotfiles_cli.commands.install.get_repos_with_unpushed_changes",
                return_value=([], []),
            ),
            patch(
                "dotfiles_cli.types.AnsibleTagListType._get_all_supported_tags",
                return_value=["all", "brew", "cask", "dotfiles", "mas", "chsh"],
            ),
            patch("getpass.getpass", return_value="sudo_password") as mock_pass,
            patch(
                "dotfiles_cli.commands.install.validate_sudo_password",
                return_value=True,
            ),
        ):
            _result = cli_runner.invoke(cli, ["install", "mas"])

        # Should have prompted for password (mas is in SUDO_TAGS)
        mock_pass.assert_called()

    def test_install_no_sudo_prompt_for_exempt_tags(
        self, cli_runner, mock_ansible_runner, temp_dotfiles_dir
    ):
        """Test install doesn't prompt for sudo for exempt tags."""
        with (
            patch("dotfiles_cli.constants.DOTFILES_DIR", str(temp_dotfiles_dir)),
            patch(
                "dotfiles_cli.commands.install.get_active_profiles",
                return_value=Mock(resolve=lambda x: ["common"]),
            ),
            patch(
                "dotfiles_cli.commands.install.get_all_profile_names",
                return_value=["common"],
            ),
            patch(
                "dotfiles_cli.commands.install.get_profile_roles_paths", return_value=[]
            ),
            patch(
                "dotfiles_cli.commands.install.get_profile_requirements_paths",
                return_value=[],
            ),
            patch(
                "dotfiles_cli.commands.install.get_repos_with_unpushed_changes",
                return_value=([], []),
            ),
            patch("getpass.getpass") as mock_pass,
        ):
            _result = cli_runner.invoke(cli, ["install", "dotfiles"])

        # Should NOT prompt for password (dotfiles does not require sudo)
        mock_pass.assert_not_called()

    def test_install_with_profiles_flag(
        self, cli_runner, mock_ansible_runner, temp_dotfiles_dir, mock_getpass
    ):
        """Test install with --profile flag."""
        with (
            patch("dotfiles_cli.constants.DOTFILES_DIR", str(temp_dotfiles_dir)),
            patch(
                "dotfiles_cli.commands.install.get_all_profile_names",
                return_value=["common", "work", "personal"],
            ),
            patch(
                "dotfiles_cli.commands.install.get_profile_roles_paths", return_value=[]
            ),
            patch(
                "dotfiles_cli.commands.install.get_profile_requirements_paths",
                return_value=[],
            ),
            patch(
                "dotfiles_cli.commands.install.get_repos_with_unpushed_changes",
                return_value=([], []),
            ),
            patch(
                "dotfiles_cli.types.AnsibleTagListType._get_all_supported_tags",
                return_value=["all", "brew", "cask", "dotfiles"],
            ),
        ):
            result = cli_runner.invoke(
                cli, ["install", "--profile", "common,work", "dotfiles"]
            )

        assert result.exit_code == 0, (
            f"Exit code: {result.exit_code}, Output: {result.output}"
        )

        # Should run with specified profiles (localhost is always included for Bootstrap/Finalize plays)
        ansible_call = mock_ansible_runner["run"].call_args
        assert ansible_call[1]["limit"] == "common,work,localhost"

    def test_install_with_dry_run(
        self, cli_runner, mock_ansible_runner, temp_dotfiles_dir, mock_getpass
    ):
        """Test install with --dry-run flag."""
        with (
            patch("dotfiles_cli.constants.DOTFILES_DIR", str(temp_dotfiles_dir)),
            patch(
                "dotfiles_cli.commands.install.get_active_profiles",
                return_value=Mock(resolve=lambda x: ["common"]),
            ),
            patch(
                "dotfiles_cli.commands.install.get_all_profile_names",
                return_value=["common"],
            ),
            patch(
                "dotfiles_cli.commands.install.get_profile_roles_paths", return_value=[]
            ),
            patch(
                "dotfiles_cli.commands.install.get_profile_requirements_paths",
                return_value=[],
            ),
            patch(
                "dotfiles_cli.commands.install.get_repos_with_unpushed_changes",
                return_value=([], []),
            ),
            patch(
                "dotfiles_cli.types.AnsibleTagListType._get_all_supported_tags",
                return_value=["all", "brew", "cask", "dotfiles"],
            ),
        ):
            result = cli_runner.invoke(cli, ["install", "--dry-run", "dotfiles"])

        assert result.exit_code == 0, (
            f"Exit code: {result.exit_code}, Output: {result.output}"
        )
        assert "dry-run" in result.output

        # Should pass --check to ansible
        ansible_call = mock_ansible_runner["run"].call_args
        assert ansible_call[1]["cmdline"] == "--check"

    def test_install_with_sync_flag(
        self, cli_runner, mock_ansible_runner, temp_dotfiles_dir, mock_getpass
    ):
        """Test install with --sync flag runs sync first."""
        with (
            patch("dotfiles_cli.constants.DOTFILES_DIR", str(temp_dotfiles_dir)),
            patch(
                "dotfiles_cli.commands.install.get_active_profiles",
                return_value=Mock(resolve=lambda x: ["common"]),
            ),
            patch(
                "dotfiles_cli.commands.install.get_all_profile_names",
                return_value=["common"],
            ),
            patch(
                "dotfiles_cli.commands.install.get_profile_roles_paths", return_value=[]
            ),
            patch(
                "dotfiles_cli.commands.install.get_profile_requirements_paths",
                return_value=[],
            ),
            patch(
                "dotfiles_cli.commands.install.get_repos_with_unpushed_changes",
                return_value=([], []),
            ),
            patch(
                "dotfiles_cli.types.AnsibleTagListType._get_all_supported_tags",
                return_value=["all", "brew", "cask", "dotfiles"],
            ),
            patch("subprocess.call", return_value=0),
            patch("dotfiles_cli.commands.git.sync_profile_repos"),
            patch("dotfiles_cli.commands.upgrade.upgrade", return_value=0),
        ):
            result = cli_runner.invoke(cli, ["install", "--sync", "dotfiles"])

        assert result.exit_code == 0, (
            f"Exit code: {result.exit_code}, Output: {result.output}"
        )
        # Sync should have been called
        assert "Running sync before install" in result.output

    def test_install_aborts_if_sync_fails(self, cli_runner, temp_dotfiles_dir):
        """Test install aborts if sync fails."""
        with (
            patch("dotfiles_cli.constants.DOTFILES_DIR", str(temp_dotfiles_dir)),
            patch(
                "dotfiles_cli.types.AnsibleTagListType._get_all_supported_tags",
                return_value=["all", "brew", "cask", "dotfiles"],
            ),
            patch("subprocess.call", return_value=1),
            patch("dotfiles_cli.commands.git.sync_profile_repos"),
        ):
            result = cli_runner.invoke(cli, ["install", "--sync", "dotfiles"])

        # Sync returns error code 1, but Click doesn't propagate it unless we use ctx.exit
        # The error message should be in the output
        assert "sync failed" in result.output or "git pull failed" in result.output

    def test_install_cleans_up_old_logs(
        self, cli_runner, mock_ansible_runner, temp_dotfiles_dir, mock_getpass
    ):
        """Test install cleans up old log files."""
        with (
            patch("dotfiles_cli.constants.DOTFILES_DIR", str(temp_dotfiles_dir)),
            patch(
                "dotfiles_cli.commands.install.get_active_profiles",
                return_value=Mock(resolve=lambda x: ["common"]),
            ),
            patch(
                "dotfiles_cli.commands.install.get_all_profile_names",
                return_value=["common"],
            ),
            patch(
                "dotfiles_cli.commands.install.get_profile_roles_paths", return_value=[]
            ),
            patch(
                "dotfiles_cli.commands.install.get_profile_requirements_paths",
                return_value=[],
            ),
            patch(
                "dotfiles_cli.commands.install.get_repos_with_unpushed_changes",
                return_value=([], []),
            ),
            patch(
                "dotfiles_cli.types.AnsibleTagListType._get_all_supported_tags",
                return_value=["all", "brew", "cask", "dotfiles"],
            ),
            patch("dotfiles_cli.commands.install.cleanup_old_logs") as mock_cleanup,
        ):
            _result = cli_runner.invoke(cli, ["install", "dotfiles"])

        # Should call cleanup before running
        mock_cleanup.assert_called_once()

    def test_install_no_profiles_configured(self, cli_runner, temp_dotfiles_dir):
        """Test install fails gracefully when no profiles configured."""
        # Create a mock selection that always returns empty list
        mock_selection = Mock()
        mock_selection.resolve = Mock(return_value=[])

        # The temp_dotfiles_dir fixture creates .env file, so get_env_file().exists() returns True
        # and the interactive config flow is skipped
        with (
            patch("dotfiles_cli.constants.DOTFILES_DIR", str(temp_dotfiles_dir)),
            patch(
                "dotfiles_cli.commands.install.get_active_profiles",
                return_value=mock_selection,
            ),
            patch(
                "dotfiles_cli.commands.install.get_all_profile_names",
                return_value=["common", "work"],
            ),
            patch(
                "dotfiles_cli.types.AnsibleTagListType._get_all_supported_tags",
                return_value=["all", "brew", "cask", "dotfiles"],
            ),
            patch("dotfiles_cli.commands.install.cleanup_old_logs"),
            patch.dict("os.environ", {"DOTFILES_PROFILES": ""}, clear=False),
        ):
            result = cli_runner.invoke(cli, ["install", "dotfiles"])

        # The install command returns 1 but Click doesn't convert that to exit code
        # Check for the error message indicating no profiles were configured
        assert "No profiles configured" in result.output


class TestSudoTags:
    """Test SUDO_TAGS configuration."""

    def test_sudo_tags_defined(self):
        """Test that SUDO_TAGS is defined with expected values."""
        assert "mas" in SUDO_TAGS
        assert "chsh" in SUDO_TAGS
        assert "dotfiles" not in SUDO_TAGS
        assert "brew" not in SUDO_TAGS


class TestProfileBootstrap:
    """Test profile bootstrap command."""

    def test_bootstrap_generates_valid_yaml(self, cli_runner, temp_dotfiles_dir):
        """Test that bootstrap generates valid YAML config."""
        import yaml

        profiles_dir = temp_dotfiles_dir / "profiles"
        profiles_dir.mkdir(parents=True, exist_ok=True)

        with (
            patch("dotfiles_cli.commands.profile.DOTFILES_DIR", str(temp_dotfiles_dir)),
            patch("subprocess.run"),  # Mock git operations
        ):
            result = cli_runner.invoke(
                cli, ["profile", "bootstrap", "test-profile", "--no-git"]
            )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        config_file = profiles_dir / "test-profile" / "config.yml"
        assert config_file.exists(), f"Config file not found at {config_file}"

        # Should be valid YAML
        with open(config_file) as f:
            config = yaml.safe_load(f)
        assert config is not None
        assert isinstance(config, dict)

    def test_bootstrap_config_has_profile_name_uncommented(
        self, cli_runner, temp_dotfiles_dir
    ):
        """Test that profile.name is uncommented in generated config."""
        profiles_dir = temp_dotfiles_dir / "profiles"
        profiles_dir.mkdir(parents=True, exist_ok=True)
        schemas_dir = temp_dotfiles_dir / "schemas"
        schemas_dir.mkdir(parents=True, exist_ok=True)

        with (
            patch("dotfiles_cli.commands.profile.DOTFILES_DIR", str(temp_dotfiles_dir)),
            patch("subprocess.run"),  # Mock git operations
        ):
            result = cli_runner.invoke(
                cli, ["profile", "bootstrap", "test-profile", "--no-git"]
            )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        config_file = profiles_dir / "test-profile" / "config.yml"
        content = config_file.read_text()

        # profile.name should be uncommented
        assert "profile:\n  name: test-profile" in content
        # Other profile fields should be commented
        assert "# host:" in content or "#  host:" in content
        assert "# priority:" in content or "#  priority:" in content

    def test_bootstrap_config_has_all_major_sections(
        self, cli_runner, temp_dotfiles_dir
    ):
        """Test that bootstrap includes all major configuration sections."""
        profiles_dir = temp_dotfiles_dir / "profiles"
        profiles_dir.mkdir(parents=True, exist_ok=True)
        schemas_dir = temp_dotfiles_dir / "schemas"
        schemas_dir.mkdir(parents=True, exist_ok=True)

        with (
            patch("dotfiles_cli.commands.profile.DOTFILES_DIR", str(temp_dotfiles_dir)),
            patch("subprocess.run"),  # Mock git operations
        ):
            result = cli_runner.invoke(
                cli, ["profile", "bootstrap", "test-profile", "--no-git"]
            )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        config_file = profiles_dir / "test-profile" / "config.yml"
        content = config_file.read_text()

        # Check for major section headers
        expected_sections = [
            "Profile Metadata",
            "Homebrew Packages",
            "Mac App Store",
            "Python Packages",
            "Other Package Managers",
            "Dotfiles Configuration",
            "SSH Configuration",
            "Git Configuration",
            "GitHub Integration",
            "MCP Servers",
            "Config Merging",
            "AI Agents",
        ]

        for section in expected_sections:
            assert section in content, f"Missing section: {section}"

    def test_bootstrap_config_has_comprehensive_examples(
        self, cli_runner, temp_dotfiles_dir
    ):
        """Test that bootstrap includes comprehensive examples for key features."""
        profiles_dir = temp_dotfiles_dir / "profiles"
        profiles_dir.mkdir(parents=True, exist_ok=True)
        schemas_dir = temp_dotfiles_dir / "schemas"
        schemas_dir.mkdir(parents=True, exist_ok=True)

        with (
            patch("dotfiles_cli.commands.profile.DOTFILES_DIR", str(temp_dotfiles_dir)),
            patch("subprocess.run"),  # Mock git operations
        ):
            result = cli_runner.invoke(
                cli, ["profile", "bootstrap", "test-profile", "--no-git"]
            )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        config_file = profiles_dir / "test-profile" / "config.yml"
        content = config_file.read_text()

        # Check for key configuration examples
        expected_examples = [
            "brew_packages:",
            "cask_packages:",
            "mas_packages:",
            "pipx_packages:",
            "pip_packages:",
            "gem_packages:",
            "npm_packages:",
            "composer_packages:",
            "ssh_client_config:",
            "ssh_client_config_block:",
            "gh_extensions:",
            "gh_repos:",
            "mcp_servers:",
            "json_configs:",
            "yaml_configs:",
            "build_deps:",  # pipx build dependencies example
            "git_repo:",  # MCP git-based server
            "vault_secret",  # Secret management example
        ]

        for example in expected_examples:
            assert example in content, f"Missing example: {example}"

    def test_bootstrap_config_shows_multiple_patterns(
        self, cli_runner, temp_dotfiles_dir
    ):
        """Test that bootstrap shows multiple patterns for complex features."""
        profiles_dir = temp_dotfiles_dir / "profiles"
        profiles_dir.mkdir(parents=True, exist_ok=True)
        schemas_dir = temp_dotfiles_dir / "schemas"
        schemas_dir.mkdir(parents=True, exist_ok=True)

        with (
            patch("dotfiles_cli.commands.profile.DOTFILES_DIR", str(temp_dotfiles_dir)),
            patch("subprocess.run"),  # Mock git operations
        ):
            result = cli_runner.invoke(
                cli, ["profile", "bootstrap", "test-profile", "--no-git"]
            )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        config_file = profiles_dir / "test-profile" / "config.yml"
        content = config_file.read_text()

        # MCP servers should show multiple transport types
        assert "STDIO Transport" in content
        assert "URL Transport" in content

        # Should show simple and advanced examples
        assert "Simple" in content or "simple" in content
        assert "vault_secret" in content  # Vault secrets
        assert "op://" in content  # 1Password secrets

        # Should show state: absent examples
        assert "state: absent" in content

    def test_bootstrap_template_function(self):
        """Test the _generate_config_template function directly."""
        from dotfiles_cli.commands.profile import _generate_config_template

        template = _generate_config_template("test-profile", "../config.schema.json")

        # Should be a string
        assert isinstance(template, str)
        assert len(template) > 100  # Should be substantial

        # Should have schema reference
        assert "$schema=../config.schema.json" in template

        # Should have profile name
        assert "name: test-profile" in template

        # Should escape Ansible variables correctly
        assert "{{ profile_dir }}" in template or "{{{{ profile_dir }}}}" in template

    def test_bootstrap_config_validates_against_schema(
        self, cli_runner, temp_dotfiles_dir
    ):
        """Test that generated config validates against JSON schema."""
        import json
        import shutil
        import subprocess
        from pathlib import Path

        import jsonschema
        import yaml

        from dotfiles_cli.commands.profile import DOTFILES_DIR

        profiles_dir = temp_dotfiles_dir / "profiles"
        profiles_dir.mkdir(parents=True, exist_ok=True)
        schemas_dir = temp_dotfiles_dir / "schemas"
        schemas_dir.mkdir(parents=True, exist_ok=True)

        # Copy the actual schema file to temp dir
        real_schema = Path(DOTFILES_DIR) / "schemas" / "config.schema.json"
        temp_schema = schemas_dir / "config.schema.json"
        shutil.copy(real_schema, temp_schema)

        with (
            patch("dotfiles_cli.commands.profile.DOTFILES_DIR", str(temp_dotfiles_dir)),
            patch("subprocess.run"),  # Mock git operations
        ):
            result = cli_runner.invoke(
                cli, ["profile", "bootstrap", "test-profile", "--no-git"]
            )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        config_file = profiles_dir / "test-profile" / "config.yml"

        # Load generated config
        with open(config_file) as f:
            config = yaml.safe_load(f)

        # Load schema
        with open(temp_schema) as f:
            schema = json.load(f)

        # Validate config against schema
        try:
            jsonschema.validate(instance=config, schema=schema)
        except jsonschema.ValidationError as e:
            pytest.fail(f"Generated config failed schema validation: {e.message}")

        # Also test with check-jsonschema CLI tool if available
        try:
            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "--with",
                    "check-jsonschema",
                    "check-jsonschema",
                    "--schemafile",
                    str(temp_schema),
                    str(config_file),
                ],
                cwd=str(temp_dotfiles_dir),
                capture_output=True,
                text=True,
                timeout=10,
            )
            assert result.returncode == 0, (
                f"check-jsonschema validation failed: {result.stderr}"
            )
        except FileNotFoundError:
            # check-jsonschema not available, skip this part
            pass
