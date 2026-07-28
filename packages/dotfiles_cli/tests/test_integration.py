"""Integration tests for the CLI."""

from unittest.mock import MagicMock, Mock, call, patch


from dotfiles_cli.app import cli


class TestInstallWorkflow:
    """Integration tests for the install command workflow."""

    def test_install_dotfiles_only_no_sudo(
        self, cli_runner, mock_pyinfra_subprocess, temp_dotfiles_dir
    ):
        """Test installing dotfiles doesn't prompt for sudo."""
        with (
            patch("dotfiles_cli.constants.DOTFILES_DIR", str(temp_dotfiles_dir)),
            patch(
                "dotfiles_cli.commands.install.get_active_profiles",
                return_value=Mock(resolve=lambda x: ["alpha"]),
            ),
            patch(
                "dotfiles_cli.commands.install.get_all_profile_names",
                return_value=["alpha"],
            ),
            patch(
                "dotfiles_cli.commands.install.get_repos_with_unpushed_changes",
                return_value=([], []),
            ),
            patch(
                "dotfiles_cli.types.PyinfraTagListType._get_all_supported_tags",
                return_value=["all", "brew", "cask", "dotfiles"],
            ),
            patch("getpass.getpass") as mock_getpass,
        ):
            result = cli_runner.invoke(cli, ["install", "dotfiles"])

        assert result.exit_code == 0
        # Should NOT prompt for password (dotfiles does not require sudo)
        mock_getpass.assert_not_called()

    def test_install_sudo_tag_prompts_sudo(
        self, cli_runner, mock_pyinfra_subprocess, temp_dotfiles_dir
    ):
        """Test installing a sudo-requiring tag prompts for sudo password."""
        with (
            patch("dotfiles_cli.constants.DOTFILES_DIR", str(temp_dotfiles_dir)),
            patch(
                "dotfiles_cli.commands.install.get_active_profiles",
                return_value=Mock(resolve=lambda x: ["alpha"]),
            ),
            patch(
                "dotfiles_cli.commands.install.get_all_profile_names",
                return_value=["alpha"],
            ),
            patch(
                "dotfiles_cli.commands.install.get_repos_with_unpushed_changes",
                return_value=([], []),
            ),
            patch(
                "dotfiles_cli.types.PyinfraTagListType._get_all_supported_tags",
                return_value=["all", "brew", "cask", "dotfiles", "mas", "chsh"],
            ),
            patch("getpass.getpass", return_value="sudo_password") as mock_getpass,
            patch(
                "dotfiles_cli.commands.install.validate_sudo_password",
                return_value=True,
            ),
        ):
            result = cli_runner.invoke(cli, ["install", "mas"])

        assert result.exit_code == 0
        # Should prompt for password (mas is in SUDO_TAGS)
        mock_getpass.assert_called()

    def test_install_with_multiple_profiles(
        self, cli_runner, mock_pyinfra_subprocess, temp_dotfiles_dir
    ):
        """Test installing with multiple profiles."""
        with (
            patch("dotfiles_cli.constants.DOTFILES_DIR", str(temp_dotfiles_dir)),
            patch(
                "dotfiles_cli.commands.install.get_all_profile_names",
                return_value=["alpha", "bravo", "charlie"],
            ),
            patch(
                "dotfiles_cli.commands.install.get_repos_with_unpushed_changes",
                return_value=([], []),
            ),
            patch(
                "dotfiles_cli.types.PyinfraTagListType._get_all_supported_tags",
                return_value=["all", "brew", "cask", "dotfiles"],
            ),
            patch("getpass.getpass", return_value="password"),
        ):
            result = cli_runner.invoke(
                cli, ["install", "--profile", "alpha,bravo", "dotfiles"]
            )

        assert result.exit_code == 0

        # Verify pyinfra was invoked with the correct profiles via env vars
        # (no more Ansible --limit).
        env = mock_pyinfra_subprocess.call_args.kwargs["env"]
        assert env["DOTFILES_SELECTED_PROFILES"] == "alpha,bravo"

    def test_install_with_sync_workflow(
        self, cli_runner, mock_pyinfra_subprocess, temp_dotfiles_dir
    ):
        """Test install --sync performs full workflow."""
        with (
            patch("dotfiles_cli.constants.DOTFILES_DIR", str(temp_dotfiles_dir)),
            patch(
                "dotfiles_cli.commands.install.get_active_profiles",
                return_value=Mock(resolve=lambda x: ["alpha"]),
            ),
            patch(
                "dotfiles_cli.commands.install.get_all_profile_names",
                return_value=["alpha"],
            ),
            patch(
                "dotfiles_cli.commands.install.get_repos_with_unpushed_changes",
                return_value=([], []),
            ),
            patch(
                "dotfiles_cli.types.PyinfraTagListType._get_all_supported_tags",
                return_value=["all", "brew", "cask", "dotfiles"],
            ),
            patch("dotfiles_cli.commands.git._sync_all_repos", return_value=True),
            patch("dotfiles_cli.commands.upgrade.upgrade", return_value=0),
        ):
            result = cli_runner.invoke(cli, ["install", "--sync", "dotfiles"])

        assert result.exit_code == 0
        assert "Running sync before install" in result.output
        assert "Sync completed successfully" in result.output


class TestSyncWorkflow:
    """Integration tests for sync workflow."""

    def test_sync_full_workflow(self, cli_runner):
        """Test sync performs pull and push."""
        with patch(
            "dotfiles_cli.commands.git._sync_all_repos", return_value=True
        ) as mock_sync:
            result = cli_runner.invoke(cli, ["sync"])

        assert result.exit_code == 0
        assert mock_sync.call_args_list == [call("pull"), call("push")]


class TestProfileSelectionWorkflow:
    """Integration tests for profile selection."""

    def test_profile_selection_explicit(self, tmp_path):
        """Test explicit profile selection workflow."""
        from dotfiles_cli.profiles.discovery import get_all_profile_names
        from dotfiles_cli.profiles.selection import parse_profile_selection

        # Create profile structure with config.yml files
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        (profiles_dir / "alpha").mkdir()
        (profiles_dir / "alpha" / "config.yml").write_text("---\n")
        (profiles_dir / "bravo").mkdir()
        (profiles_dir / "bravo" / "config.yml").write_text("---\n")
        (profiles_dir / "charlie").mkdir()
        (profiles_dir / "charlie" / "config.yml").write_text("---\n")

        with patch("dotfiles_cli.profiles.discovery.DOTFILES_DIR", str(tmp_path)):
            # Get available profiles
            available = get_all_profile_names()
            assert set(available) == {"alpha", "bravo", "charlie"}

            # Parse and resolve selection
            selection = parse_profile_selection("alpha,bravo")
            active = selection.resolve(available)

            assert active == ["alpha", "bravo"]

    def test_profile_selection_exclusion(self, tmp_path):
        """Test profile exclusion workflow."""
        from dotfiles_cli.profiles.discovery import get_all_profile_names
        from dotfiles_cli.profiles.selection import parse_profile_selection

        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        (profiles_dir / "alpha").mkdir()
        (profiles_dir / "alpha" / "config.yml").write_text("---\n")
        (profiles_dir / "bravo").mkdir()
        (profiles_dir / "bravo" / "config.yml").write_text("---\n")
        (profiles_dir / "charlie").mkdir()
        (profiles_dir / "charlie" / "config.yml").write_text("---\n")

        with patch("dotfiles_cli.profiles.discovery.DOTFILES_DIR", str(tmp_path)):
            available = get_all_profile_names()
            selection = parse_profile_selection("-bravo")
            active = selection.resolve(available)

            assert "alpha" in active
            assert "charlie" in active
            assert "bravo" not in active


class TestVaultWorkflow:
    """Integration tests for vault operations."""

    def test_vault_password_from_backend(self):
        """Vault password retrieval delegates to the backend."""
        from unittest.mock import MagicMock

        from dotfiles_cli.vault.password import get_vault_password

        fake_backend = MagicMock()
        fake_backend.read.return_value = "my_secret_password"

        with patch(
            "dotfiles_cli.vault.password.get_backend",
            return_value=fake_backend,
        ):
            password = get_vault_password("alpha")

        assert password == "my_secret_password"
        fake_backend.read.assert_called_once_with("alpha")

    def test_vault_encrypt_decrypt_workflow(self, tmp_path):
        """Test encrypting and decrypting with vault."""
        from dotfiles_cli.vault.operations import run_ansible_vault

        secrets_file = tmp_path / "secrets.yml"
        secrets_file.write_text("api_key: secret123")

        # Mock subprocess calls for encrypt/decrypt
        with (
            patch("subprocess.run") as mock_run,
            patch("dotfiles_cli.vault.operations.DOTFILES_DIR", str(tmp_path)),
        ):
            # Test encrypt
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
            rc, stdout, stderr = run_ansible_vault(
                ["encrypt", str(secrets_file)], password="vault_pass"
            )
            assert rc == 0

            # Test decrypt
            mock_run.return_value = Mock(
                returncode=0, stdout="api_key: secret123", stderr=""
            )
            rc, stdout, stderr = run_ansible_vault(
                ["decrypt", "--output", "-", str(secrets_file)], password="vault_pass"
            )
            assert rc == 0
            assert "api_key" in stdout


class TestCommandAliases:
    """Integration tests for command aliases and shortcuts."""

    def test_install_alias_run(
        self, cli_runner, mock_pyinfra_subprocess, temp_dotfiles_dir
    ):
        """Test 'run' alias for install command."""
        with (
            patch("dotfiles_cli.constants.DOTFILES_DIR", str(temp_dotfiles_dir)),
            patch(
                "dotfiles_cli.commands.install.get_active_profiles",
                return_value=Mock(resolve=lambda x: ["alpha"]),
            ),
            patch(
                "dotfiles_cli.commands.install.get_all_profile_names",
                return_value=["alpha"],
            ),
            patch(
                "dotfiles_cli.commands.install.get_repos_with_unpushed_changes",
                return_value=([], []),
            ),
            patch(
                "dotfiles_cli.types.PyinfraTagListType._get_all_supported_tags",
                return_value=["all", "brew", "cask", "dotfiles"],
            ),
        ):
            result = cli_runner.invoke(cli, ["run", "dotfiles"])

        # Both should work
        assert result.exit_code == 0


class TestErrorHandling:
    """Integration tests for error handling."""

    def test_install_fails_gracefully_on_pyinfra_error(
        self, cli_runner, mock_pyinfra_subprocess, temp_dotfiles_dir
    ):
        """Test install handles a failing pyinfra deploy gracefully."""
        mock_pyinfra_subprocess.return_value = MagicMock(
            returncode=1, stdout="", stderr=""
        )

        with (
            patch("dotfiles_cli.constants.DOTFILES_DIR", str(temp_dotfiles_dir)),
            patch(
                "dotfiles_cli.commands.install.get_active_profiles",
                return_value=Mock(resolve=lambda x: ["alpha"]),
            ),
            patch(
                "dotfiles_cli.commands.install.get_all_profile_names",
                return_value=["alpha"],
            ),
            patch(
                "dotfiles_cli.commands.install.get_repos_with_unpushed_changes",
                return_value=([], []),
            ),
            patch(
                "dotfiles_cli.types.PyinfraTagListType._get_all_supported_tags",
                return_value=["all", "brew", "cask", "dotfiles"],
            ),
            patch("getpass.getpass", return_value="password"),
        ):
            # Click's standalone mode discards a command's plain `return`
            # value (it never becomes the process/CliRunner exit code unless
            # ctx.exit()/SystemExit is used), so disable it to inspect the
            # actual value install() returns.
            result = cli_runner.invoke(
                cli, ["install", "dotfiles"], standalone_mode=False
            )

        # dotfiles does not require sudo, no password should be prompted, and
        # install() returns the pyinfra process's exit code (1).
        assert result.exception is None, result.output
        assert result.return_value == 1

    def test_sync_aborts_on_pull_failure(self, cli_runner):
        """Test sync aborts when pull fails."""
        with patch(
            "dotfiles_cli.commands.git._sync_all_repos", return_value=False
        ) as mock_sync:
            result = cli_runner.invoke(cli, ["sync"])

        assert "failed" in result.output
        # Should only call pull (which failed), not push
        mock_sync.assert_called_once_with("pull")

    def test_edit_fails_when_no_editor(self, cli_runner):
        """Test edit fails gracefully when no editor available."""
        with (
            patch("shutil.which", return_value=None),
            patch("os.getenv", return_value=None),
        ):
            result = cli_runner.invoke(cli, ["edit"])

        assert result.exit_code != 0
        # The error is in the exception, not the output
        assert result.exception is not None
        assert "No supported editor" in str(result.exception)


class TestLogfileHandling:
    """Integration tests for logfile handling."""

    def test_install_with_logfile_creates_file(
        self, cli_runner, mock_pyinfra_subprocess, temp_dotfiles_dir, tmp_path
    ):
        """Test install with --logfile creates log file."""
        log_file = tmp_path / "test.log"

        with (
            patch("dotfiles_cli.constants.DOTFILES_DIR", str(temp_dotfiles_dir)),
            patch(
                "dotfiles_cli.commands.install.get_active_profiles",
                return_value=Mock(resolve=lambda x: ["alpha"]),
            ),
            patch(
                "dotfiles_cli.commands.install.get_all_profile_names",
                return_value=["alpha"],
            ),
            patch(
                "dotfiles_cli.commands.install.get_repos_with_unpushed_changes",
                return_value=([], []),
            ),
            patch(
                "dotfiles_cli.types.PyinfraTagListType._get_all_supported_tags",
                return_value=["all", "brew", "cask", "dotfiles"],
            ),
        ):
            result = cli_runner.invoke(
                cli, ["install", "--logfile", str(log_file), "dotfiles"]
            )

        assert result.exit_code == 0
        assert f"Log file: {log_file}" in result.output

        # The tee pipeline (not a direct pyinfra argv) is what gets run when
        # a logfile is requested.
        deploy_call = mock_pyinfra_subprocess.call_args
        assert deploy_call.args[0][:2] == ["bash", "-c"]
        assert "pyinfra" in deploy_call.args[0][2]
        assert str(log_file) in deploy_call.args[0][2]

    def test_install_with_auto_logfile(
        self, cli_runner, mock_pyinfra_subprocess, temp_dotfiles_dir, tmp_path
    ):
        """Test install with --logfile generates timestamped file when value is provided."""
        # Note: --logfile requires a value; auto-generation happens with flag_value which isn't configured
        # This test demonstrates that --logfile takes the next argument as its value
        test_logfile = tmp_path / "test-auto.log"

        with (
            patch("dotfiles_cli.constants.DOTFILES_DIR", str(temp_dotfiles_dir)),
            patch(
                "dotfiles_cli.commands.install.get_active_profiles",
                return_value=Mock(resolve=lambda x: ["alpha"]),
            ),
            patch(
                "dotfiles_cli.commands.install.get_all_profile_names",
                return_value=["alpha"],
            ),
            patch(
                "dotfiles_cli.commands.install.get_repos_with_unpushed_changes",
                return_value=([], []),
            ),
            patch(
                "dotfiles_cli.types.PyinfraTagListType._get_all_supported_tags",
                return_value=["all", "brew", "cask", "dotfiles"],
            ),
        ):
            result = cli_runner.invoke(
                cli, ["install", "--logfile", str(test_logfile), "dotfiles"]
            )

        assert result.exit_code == 0
        assert "Log file:" in result.output
        assert str(test_logfile) in result.output


class TestCompletionGeneration:
    """Integration tests for completion generation."""

    def test_completion_fish_output(self, cli_runner):
        """Test fish completion generates valid output."""
        result = cli_runner.invoke(cli, ["completion", "fish"])

        assert result.exit_code == 0
        assert "complete" in result.output
        assert "_DOTFILES_COMPLETE" in result.output
        assert "dotfiles" in result.output

    def test_completion_install_fish_refuses(self, cli_runner, temp_home):
        """Fish --install refuses with a pointer to the hand-maintained script."""
        fish_dir = temp_home / ".config" / "fish" / "completions"
        fish_dir.mkdir(parents=True)

        result = cli_runner.invoke(cli, ["completion", "fish", "--install"])

        assert result.exit_code != 0
        assert "hand-maintained" in result.output
        assert not (fish_dir / "dotfiles.fish").exists()


class TestEndToEndScenarios:
    """End-to-end scenario tests."""

    def test_fresh_install_scenario(
        self, cli_runner, mock_pyinfra_subprocess, temp_dotfiles_dir
    ):
        """Test complete fresh install scenario."""
        with (
            patch("dotfiles_cli.constants.DOTFILES_DIR", str(temp_dotfiles_dir)),
            patch(
                "dotfiles_cli.commands.install.get_all_profile_names",
                return_value=["alpha", "bravo"],
            ),
            patch(
                "dotfiles_cli.commands.install.get_repos_with_unpushed_changes",
                return_value=([], []),
            ),
            patch("getpass.getpass", return_value="password"),
            patch(
                "dotfiles_cli.commands.install.validate_sudo_password",
                return_value=True,
            ),
            patch("dotfiles_cli.commands.git._sync_all_repos", return_value=True),
            patch("dotfiles_cli.commands.upgrade.upgrade", return_value=0),
        ):
            # Step 1: Install with all tags and sync
            result = cli_runner.invoke(
                cli, ["install", "--profile", "alpha,bravo", "--sync", "--all"]
            )

        assert result.exit_code == 0
        assert "Running sync before install" in result.output
        assert "Running with profiles: alpha, bravo" in result.output

    def test_update_and_push_scenario(self, cli_runner):
        """Test updating and pushing changes scenario."""
        with patch("dotfiles_cli.commands.git._sync_all_repos", return_value=True):
            # Pull latest
            result1 = cli_runner.invoke(cli, ["pull"])
            assert result1.exit_code == 0

            # Make changes (simulated by install)
            # ... user makes changes ...

            # Push changes
            result2 = cli_runner.invoke(cli, ["push"])
            assert result2.exit_code == 0
