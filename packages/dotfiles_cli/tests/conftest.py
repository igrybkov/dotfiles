"""Shared test fixtures for dotfiles CLI tests."""

import os
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from click.testing import CliRunner


@pytest.fixture(autouse=True)
def clean_dotfiles_env():
    """Clear DOTFILES_PROFILES env var to prevent leakage into tests.

    Click's --profile option uses envvar="DOTFILES_PROFILES", so any value
    in the environment bypasses get_active_profiles() entirely.
    """
    with patch.dict(os.environ, {"DOTFILES_PROFILES": ""}, clear=False):
        yield


@pytest.fixture
def cli_runner():
    """Create a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def temp_home(tmp_path):
    """Create a temporary home directory for testing."""
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    with patch.dict(os.environ, {"HOME": str(home_dir)}):
        yield home_dir


@pytest.fixture
def temp_dotfiles_dir(tmp_path):
    """Create a temporary dotfiles directory structure."""
    dotfiles = tmp_path / "dotfiles"
    dotfiles.mkdir()

    # Create basic directory structure
    (dotfiles / "profiles").mkdir()
    (dotfiles / "profiles" / "alpha").mkdir()
    (dotfiles / "profiles" / "bravo").mkdir()
    (dotfiles / "profiles" / "charlie").mkdir()
    (dotfiles / ".cache").mkdir()

    # Create config files
    (dotfiles / "profiles" / "alpha" / "config.yml").write_text("---\n")
    (dotfiles / "profiles" / "bravo" / "config.yml").write_text("---\n")
    (dotfiles / "profiles" / "charlie" / "config.yml").write_text("---\n")

    # Create .env file
    (dotfiles / ".env").write_text("DOTFILES_PROFILES=alpha,bravo\n")

    # Create playbook
    (dotfiles / "playbook.yml").write_text("---\n")

    return dotfiles


@pytest.fixture
def mock_subprocess():
    """Mock subprocess.call and subprocess.run."""
    with patch("subprocess.call") as mock_call, patch("subprocess.run") as mock_run:
        mock_call.return_value = 0
        mock_run.return_value = Mock(
            returncode=0,
            stdout="",
            stderr="",
        )
        yield {"call": mock_call, "run": mock_run}


@pytest.fixture
def mock_pyinfra_subprocess():
    """Mock the subprocess calls install.py shells out to (mise, Homebrew,
    pyinfra) for CLI tests.

    Patches `shutil.which` so `mise`/`brew` appear present (skipping the real
    Homebrew bootstrap), patches `subprocess.run` in the install module so no
    real process is spawned, and patches `read_age_key` to return None so
    tests never touch the real OS keychain/GPG backend unless they override
    it themselves. The pyinfra deploy invocation is always the *last*
    recorded call — inspect `mock_run.call_args` (or
    `mock_run.call_args_list[-1]`) for its `env`/argv.
    """
    with (
        patch("dotfiles_cli.commands.install.subprocess.run") as mock_run,
        patch("shutil.which", return_value="/usr/local/bin/mise"),
        patch("dotfiles_cli.commands.install.read_age_key", return_value=None),
    ):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        yield mock_run


@pytest.fixture
def mock_getpass():
    """Mock getpass.getpass and sudo-password validation for install command.

    Vault password validation moved into the client-script path (Phase 3);
    install no longer validates locally.
    """
    with (
        patch("getpass.getpass") as mock,
        patch(
            "dotfiles_cli.commands.install.validate_sudo_password", return_value=True
        ),
    ):
        mock.return_value = "test_password"
        yield mock


@pytest.fixture
def mock_dotfiles_dir(temp_dotfiles_dir):
    """Mock the DOTFILES_DIR constant."""
    with patch("dotfiles_cli.constants.DOTFILES_DIR", str(temp_dotfiles_dir)):
        yield temp_dotfiles_dir


@pytest.fixture
def isolated_env(tmp_path):
    """Create an isolated environment for testing."""
    env = {
        "HOME": str(tmp_path / "home"),
        "DOTFILES_PROFILES": "",
    }

    # Create home directory
    Path(env["HOME"]).mkdir(parents=True, exist_ok=True)

    with patch.dict(os.environ, env, clear=False):
        yield env


@pytest.fixture
def mock_vault_operations():
    """Mock vault password operations."""
    with (
        patch("dotfiles_cli.vault.password.get_vault_password") as mock_get,
        patch("dotfiles_cli.vault.password.validate_vault_password") as mock_validate,
        patch("dotfiles_cli.vault.operations.run_ansible_vault") as mock_vault,
    ):
        mock_get.return_value = "test_password"
        mock_validate.return_value = True
        mock_vault.return_value = (0, "decrypted: value", "")

        yield {
            "get": mock_get,
            "validate": mock_validate,
            "vault": mock_vault,
        }


@pytest.fixture
def sample_profiles_data():
    """Sample profile data for testing."""
    return {
        "alpha": {
            "name": "alpha",
            "priority": 100,
        },
        "bravo": {
            "name": "bravo",
            "priority": 200,
        },
        "charlie": {
            "name": "charlie",
            "priority": 200,
        },
    }
