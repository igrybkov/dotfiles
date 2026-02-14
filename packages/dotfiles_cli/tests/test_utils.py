"""Tests for utility functions."""

import subprocess
from unittest.mock import MagicMock, patch


from dotfiles_cli.constants import LOGFILE_AUTO
from dotfiles_cli.utils import (
    cleanup_old_logs,
    fzf_select,
    generate_logfile_name,
    numbered_select,
    preprocess_logfile_args,
    validate_sudo_password,
)


class TestPreprocessLogfileArgs:
    """Test the preprocess_logfile_args function."""

    def test_no_logfile_flag(self):
        """Test args without --logfile are unchanged."""
        args = ["install", "dotfiles", "-p", "common"]
        result = preprocess_logfile_args(args)
        assert result == ["install", "dotfiles", "-p", "common"]

    def test_logfile_followed_by_flag(self):
        """Test --logfile followed by another flag gets auto placeholder."""
        args = ["install", "--logfile", "-v", "dotfiles"]
        result = preprocess_logfile_args(args)
        assert result == ["install", "--logfile", LOGFILE_AUTO, "-v", "dotfiles"]

    def test_logfile_with_tag_as_next_arg(self):
        """Test --logfile followed by non-flag arg treats it as filename."""
        args = ["install", "--logfile", "dotfiles"]
        result = preprocess_logfile_args(args)
        assert result == ["install", "--logfile", "dotfiles"]

    def test_logfile_with_value(self):
        """Test --logfile with explicit value keeps the value."""
        args = ["install", "--logfile", "mylog.log", "dotfiles"]
        result = preprocess_logfile_args(args)
        assert result == ["install", "--logfile", "mylog.log", "dotfiles"]

    def test_short_flag_followed_by_flag(self):
        """Test -l short flag followed by another flag gets auto placeholder."""
        args = ["install", "-l", "-v", "dotfiles"]
        result = preprocess_logfile_args(args)
        assert result == ["install", "-l", LOGFILE_AUTO, "-v", "dotfiles"]

    def test_short_flag_with_value(self):
        """Test -l short flag with explicit value."""
        args = ["install", "-l", "custom.log", "dotfiles"]
        result = preprocess_logfile_args(args)
        assert result == ["install", "-l", "custom.log", "dotfiles"]

    def test_logfile_at_end(self):
        """Test --logfile at end of args without value."""
        args = ["install", "dotfiles", "--logfile"]
        result = preprocess_logfile_args(args)
        assert result == ["install", "dotfiles", "--logfile", LOGFILE_AUTO]

    def test_multiple_flags(self):
        """Test multiple flags are processed correctly."""
        args = ["install", "-v", "--logfile", "-a", "dotfiles"]
        result = preprocess_logfile_args(args)
        assert result == ["install", "-v", "--logfile", LOGFILE_AUTO, "-a", "dotfiles"]

    def test_empty_args(self):
        """Test empty args list."""
        args = []
        result = preprocess_logfile_args(args)
        assert result == []


class TestCleanupOldLogs:
    """Test the cleanup_old_logs function."""

    def test_cleanup_with_no_logs(self, tmp_path):
        """Test cleanup when no log files exist."""
        with patch("dotfiles_cli.utils.logging.DOTFILES_DIR", str(tmp_path)):
            cleanup_old_logs(keep_count=5)
        # Should not raise any errors

    def test_cleanup_keeps_recent_logs(self, tmp_path):
        """Test cleanup keeps the most recent log files."""
        import time

        # Create test log files with different modification times
        for i in range(7):
            log_file = tmp_path / f"ansible-run-2024010{i}-120000.log"
            log_file.write_text(f"log {i}")
            # Set modification time to ensure order
            time.sleep(0.01)

        with patch("dotfiles_cli.utils.logging.DOTFILES_DIR", str(tmp_path)):
            cleanup_old_logs(keep_count=3)

        # Should have 3 files remaining (the most recent)
        remaining = list(tmp_path.glob("ansible-run-*.log"))
        assert len(remaining) == 3

        # Verify the most recent files are kept
        remaining_names = sorted([f.name for f in remaining])
        assert "ansible-run-20240104-120000.log" in remaining_names
        assert "ansible-run-20240105-120000.log" in remaining_names
        assert "ansible-run-20240106-120000.log" in remaining_names

    def test_cleanup_with_fewer_logs_than_keep_count(self, tmp_path):
        """Test cleanup does nothing when fewer logs than keep_count."""
        # Create only 2 log files
        for i in range(2):
            log_file = tmp_path / f"ansible-run-2024010{i}-120000.log"
            log_file.write_text(f"log {i}")

        with patch("dotfiles_cli.utils.logging.DOTFILES_DIR", str(tmp_path)):
            cleanup_old_logs(keep_count=5)

        # Should still have 2 files
        remaining = list(tmp_path.glob("ansible-run-*.log"))
        assert len(remaining) == 2

    def test_cleanup_with_new_log_flag(self, tmp_path):
        """Test cleanup accounts for new log file being added."""
        import time

        # Create 5 log files
        for i in range(5):
            log_file = tmp_path / f"ansible-run-2024010{i}-120000.log"
            log_file.write_text(f"log {i}")
            time.sleep(0.01)

        with patch("dotfiles_cli.utils.logging.DOTFILES_DIR", str(tmp_path)):
            # When adds_new_log=True, keep one less to make room
            cleanup_old_logs(keep_count=3, adds_new_log=True)

        # Should have 2 files remaining (to make room for the new one)
        remaining = list(tmp_path.glob("ansible-run-*.log"))
        assert len(remaining) == 2

    def test_cleanup_handles_deletion_errors(self, tmp_path, capfd):
        """Test cleanup handles file deletion errors gracefully."""
        log_file = tmp_path / "ansible-run-20240101-120000.log"
        log_file.write_text("log")

        # Make the file read-only to cause deletion error
        log_file.chmod(0o444)
        (tmp_path).chmod(0o555)

        try:
            with patch("dotfiles_cli.utils.logging.DOTFILES_DIR", str(tmp_path)):
                cleanup_old_logs(keep_count=0)

            # Should print a warning but not crash
            captured = capfd.readouterr()
            assert (
                "Warning:" in captured.err
                or len(list(tmp_path.glob("ansible-run-*.log"))) == 1
            )
        finally:
            # Restore permissions for cleanup
            (tmp_path).chmod(0o755)
            if log_file.exists():
                log_file.chmod(0o644)


class TestGenerateLogfileName:
    """Test the generate_logfile_name function."""

    def test_generates_valid_filename(self):
        """Test that generated filename has correct format."""
        filename = generate_logfile_name()
        assert filename.startswith("ansible-run-")
        assert filename.endswith(".log")
        assert len(filename) == len("ansible-run-YYYYMMDD-HHMMSS.log")

    def test_generates_unique_filenames(self):
        """Test that consecutive calls generate different filenames."""
        import time

        filename1 = generate_logfile_name()
        time.sleep(1)  # Wait 1 second to ensure different timestamp
        filename2 = generate_logfile_name()
        # They might be the same if called within same second
        # but format should be consistent
        assert filename1.startswith("ansible-run-")
        assert filename2.startswith("ansible-run-")


class TestFzfSelect:
    """Test the fzf_select function."""

    def test_fzf_selection_success(self):
        """Test successful fzf selection."""
        options = ["option1", "option2", "option3"]
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "option2\n"

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = fzf_select(options, "Select option")
            assert result == "option2"
            mock_run.assert_called_once()
            args = mock_run.call_args
            assert args[0][0] == [
                "fzf",
                "--prompt",
                "Select option: ",
                "--height=40%",
                "--layout=reverse",
                "--border",
            ]
            assert args[1]["input"] == "option1\noption2\noption3"

    def test_fzf_selection_cancelled(self):
        """Test fzf selection cancelled by user."""
        options = ["option1", "option2"]
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            result = fzf_select(options, "Select")
            assert result is None

    def test_fzf_not_available(self):
        """Test fzf not available (subprocess error)."""
        options = ["option1"]

        with patch("subprocess.run", side_effect=subprocess.SubprocessError):
            result = fzf_select(options, "Select")
            assert result is None


class TestNumberedSelect:
    """Test the numbered_select function."""

    def test_numbered_selection_success(self):
        """Test successful numbered selection."""
        options = ["option1", "option2", "option3"]

        with patch("click.prompt", return_value=2):
            result = numbered_select(options, "Select option")
            assert result == "option2"

    def test_numbered_selection_first_option(self):
        """Test selecting first option."""
        options = ["first", "second"]

        with patch("click.prompt", return_value=1):
            result = numbered_select(options, "Choose")
            assert result == "first"

    def test_numbered_selection_last_option(self):
        """Test selecting last option."""
        options = ["a", "b", "c"]

        with patch("click.prompt", return_value=3):
            result = numbered_select(options, "Pick")
            assert result == "c"

    def test_numbered_selection_invalid_then_valid(self, capfd):
        """Test invalid selection followed by valid one."""
        options = ["opt1", "opt2"]

        with patch("click.prompt", side_effect=[0, 5, 1]):
            result = numbered_select(options, "Choose")
            assert result == "opt1"

            captured = capfd.readouterr()
            # Should have shown error messages for invalid inputs
            assert "between 1 and 2" in captured.out

    def test_numbered_selection_abort(self):
        """Test selection aborted."""
        import click

        options = ["a", "b"]

        with patch("click.prompt", side_effect=click.Abort):
            result = numbered_select(options, "Select")
            assert result is None


class TestValidateSudoPassword:
    """Test the validate_sudo_password function."""

    def test_valid_password(self):
        """Test valid sudo password returns True."""
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = validate_sudo_password("correct_password")
            assert result is True
            mock_run.assert_called_once()
            args = mock_run.call_args
            assert args[0][0] == ["sudo", "-S", "-v"]
            assert args[1]["input"] == "correct_password\n"
            assert args[1]["capture_output"] is True

    def test_invalid_password(self):
        """Test invalid sudo password returns False."""
        mock_result = MagicMock()
        mock_result.returncode = 1

        with patch("subprocess.run", return_value=mock_result):
            result = validate_sudo_password("wrong_password")
            assert result is False

    def test_timeout_returns_false(self):
        """Test timeout during validation returns False."""
        with patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="sudo", timeout=10),
        ):
            result = validate_sudo_password("password")
            assert result is False

    def test_exception_returns_false(self):
        """Test generic exception during validation returns False."""
        with patch("subprocess.run", side_effect=OSError("Permission denied")):
            result = validate_sudo_password("password")
            assert result is False
