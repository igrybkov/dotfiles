"""Tests for vault operations and password management."""

import pytest
from unittest.mock import Mock, patch


from dotfiles_cli.vault.operations import (
    get_all_secret_locations,
    get_profiles_with_secrets,
    get_secrets_file,
    run_ansible_vault,
)
from dotfiles_cli.vault.password import (
    clear_vault_password_cache,
    ensure_vault_password_permissions,
    get_vault_id,
    get_vault_password,
    get_vault_password_file,
    validate_vault_password,
    write_vault_password_file,
)


class TestGetSecretsFile:
    """Test secrets file path resolution."""

    def test_get_secrets_file_alpha(self, tmp_path):
        """Test getting secrets file for alpha profile."""
        profile_path = tmp_path / "profiles" / "alpha"
        with patch(
            "dotfiles_cli.vault.operations.get_profile_path", return_value=profile_path
        ):
            result = get_secrets_file("alpha")

        assert result == profile_path / "secrets.yml"

    def test_get_secrets_file_bravo(self, tmp_path):
        """Test getting secrets file for bravo profile."""
        profile_path = tmp_path / "profiles" / "bravo"
        with patch(
            "dotfiles_cli.vault.operations.get_profile_path", return_value=profile_path
        ):
            result = get_secrets_file("bravo")

        assert result == profile_path / "secrets.yml"

    def test_get_secrets_file_custom_profile(self, tmp_path):
        """Test getting secrets file for a custom profile."""
        profile_path = tmp_path / "profiles" / "mycompany"
        with patch(
            "dotfiles_cli.vault.operations.get_profile_path", return_value=profile_path
        ):
            result = get_secrets_file("mycompany")

        assert result == profile_path / "secrets.yml"

    def test_get_secrets_file_nested_profile(self, tmp_path):
        """Test getting secrets file for a multi-level nested profile."""
        # For profile name "myrepo-work", the path should be profiles/myrepo/work/
        profile_path = tmp_path / "profiles" / "myrepo" / "work"
        with patch(
            "dotfiles_cli.vault.operations.get_profile_path", return_value=profile_path
        ):
            result = get_secrets_file("myrepo-work")

        assert result == profile_path / "secrets.yml"

    def test_get_secrets_file_profile_not_found(self):
        """Test that ValueError is raised when profile is not found."""
        with patch("dotfiles_cli.vault.operations.get_profile_path", return_value=None):
            with pytest.raises(ValueError, match="Profile not found: nonexistent"):
                get_secrets_file("nonexistent")


class TestGetAllSecretLocations:
    """Test getting all secret locations."""

    def test_get_all_secret_locations(self, tmp_path):
        """Test getting all secret locations returns all profiles."""
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        (profiles_dir / "alpha").mkdir()
        (profiles_dir / "bravo").mkdir()
        (profiles_dir / "charlie").mkdir()

        with patch(
            "dotfiles_cli.vault.operations.get_profile_names",
            return_value=["alpha", "bravo", "charlie"],
        ):
            result = get_all_secret_locations()

        assert "alpha" in result
        assert "bravo" in result
        assert "charlie" in result
        assert len(result) == 3


class TestGetProfilesWithSecrets:
    """Test discovering profiles with encrypted secrets."""

    def test_get_profiles_with_secrets(self, tmp_path):
        """Test finding profiles that have encrypted secrets."""
        profiles_dir = tmp_path / "profiles"

        # Create profile with encrypted secrets
        profile_with_secrets = profiles_dir / "mycompany"
        profile_with_secrets.mkdir(parents=True)
        (profile_with_secrets / "secrets.yml").write_text(
            "$ANSIBLE_VAULT;1.1;AES256\nencrypted"
        )

        # Create profile without secrets
        profile_no_secrets = profiles_dir / "work"
        profile_no_secrets.mkdir()

        # Create profile with unencrypted secrets
        profile_plain = profiles_dir / "personal"
        profile_plain.mkdir(parents=True)
        (profile_plain / "secrets.yml").write_text("plain: text")

        def mock_get_profile_path(name):
            return profiles_dir / name

        with (
            patch(
                "dotfiles_cli.vault.operations.get_profile_names",
                return_value=["mycompany", "work", "personal"],
            ),
            patch(
                "dotfiles_cli.vault.operations.get_profile_path",
                side_effect=mock_get_profile_path,
            ),
        ):
            result = get_profiles_with_secrets()

        assert "mycompany" in result
        assert "work" not in result
        assert "personal" not in result

    def test_get_profiles_with_secrets_none(self, tmp_path):
        """Test when no profiles have secrets."""
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        (profiles_dir / "work").mkdir()

        with (
            patch(
                "dotfiles_cli.vault.operations.get_profile_names", return_value=["work"]
            ),
            patch(
                "dotfiles_cli.vault.operations.get_profile_path",
                return_value=profiles_dir / "work",
            ),
        ):
            result = get_profiles_with_secrets()

        assert result == []

    def test_get_profiles_with_secrets_nested_profile(self, tmp_path):
        """Test finding secrets in multi-level nested profiles."""
        profiles_dir = tmp_path / "profiles"

        # Create nested profile (myrepo-work -> profiles/myrepo/work/)
        nested_profile = profiles_dir / "myrepo" / "work"
        nested_profile.mkdir(parents=True)
        (nested_profile / "secrets.yml").write_text(
            "$ANSIBLE_VAULT;1.1;AES256\nencrypted"
        )

        def mock_get_profile_path(name):
            if name == "myrepo-work":
                return nested_profile
            return None

        with (
            patch(
                "dotfiles_cli.vault.operations.get_profile_names",
                return_value=["myrepo-work"],
            ),
            patch(
                "dotfiles_cli.vault.operations.get_profile_path",
                side_effect=mock_get_profile_path,
            ),
        ):
            result = get_profiles_with_secrets()

        assert "myrepo-work" in result


class TestRunAnsibleVault:
    """Test running ansible-vault commands."""

    def test_run_ansible_vault_success(self, tmp_path):
        """Test successful ansible-vault command."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "decrypted content"
        mock_result.stderr = ""

        with (
            patch("subprocess.run", return_value=mock_result),
            patch(
                "dotfiles_cli.vault.operations.get_vault_password",
                return_value="test_pass",
            ),
            patch("dotfiles_cli.vault.operations.get_vault_id", return_value="default"),
            patch("dotfiles_cli.vault.operations.DOTFILES_DIR", str(tmp_path)),
        ):
            rc, stdout, stderr = run_ansible_vault(["decrypt", "secrets.yml"])

        assert rc == 0
        assert stdout == "decrypted content"
        assert stderr == ""

    def test_run_ansible_vault_with_explicit_password(self, tmp_path):
        """Test ansible-vault with explicit password."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "output"
        mock_result.stderr = ""

        with (
            patch("subprocess.run", return_value=mock_result),
            patch("dotfiles_cli.vault.operations.get_vault_id", return_value="default"),
            patch("dotfiles_cli.vault.operations.DOTFILES_DIR", str(tmp_path)),
        ):
            rc, stdout, stderr = run_ansible_vault(
                ["encrypt", "file.yml"], password="explicit_pass"
            )

        assert rc == 0
        # Should use explicit password, not call get_vault_password

    def test_run_ansible_vault_with_location(self, tmp_path):
        """Test ansible-vault with specific location."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        with (
            patch("subprocess.run", return_value=mock_result),
            patch(
                "dotfiles_cli.vault.operations.get_vault_password", return_value="pass"
            ) as mock_get_pass,
            patch(
                "dotfiles_cli.vault.operations.get_vault_id", return_value="mycompany"
            ),
            patch("dotfiles_cli.vault.operations.DOTFILES_DIR", str(tmp_path)),
        ):
            run_ansible_vault(["view", "file.yml"], location="mycompany")

        mock_get_pass.assert_called_once_with("mycompany")

    def test_run_ansible_vault_failure(self, tmp_path):
        """Test ansible-vault command failure."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Decryption failed"

        with (
            patch("subprocess.run", return_value=mock_result),
            patch(
                "dotfiles_cli.vault.operations.get_vault_password",
                return_value="wrong_pass",
            ),
            patch("dotfiles_cli.vault.operations.get_vault_id", return_value="default"),
            patch("dotfiles_cli.vault.operations.DOTFILES_DIR", str(tmp_path)),
        ):
            rc, stdout, stderr = run_ansible_vault(["decrypt", "file.yml"])

        assert rc == 1
        assert stderr == "Decryption failed"


class TestGetVaultId:
    """Test vault ID assignment."""

    def test_get_vault_id_returns_profile_name(self):
        """Test vault ID returns the profile name."""
        assert get_vault_id("alpha") == "alpha"
        assert get_vault_id("bravo") == "bravo"
        assert get_vault_id("charlie") == "charlie"
        assert get_vault_id("mycompany") == "mycompany"
        assert get_vault_id("custom") == "custom"


class TestGetVaultPasswordFile:
    """Test vault password file path resolution."""

    def test_get_vault_password_file_profile_specific_exists(self, tmp_path):
        """Test that profile-specific password file is preferred when it exists."""
        profile_pass_file = tmp_path / "profiles" / "mycompany" / ".vault_password"
        profile_pass_file.parent.mkdir(parents=True)
        profile_pass_file.write_text("profile_password")

        with patch("dotfiles_cli.constants.DOTFILES_DIR", str(tmp_path)):
            result = get_vault_password_file("mycompany")

        assert result == profile_pass_file

    def test_get_vault_password_file_fallback_to_global(self, tmp_path):
        """Test fallback to global password file when profile-specific doesn't exist."""
        global_pass_file = tmp_path / ".vault_password"

        with patch("dotfiles_cli.constants.DOTFILES_DIR", str(tmp_path)):
            result = get_vault_password_file("alpha")

        assert result == global_pass_file


class TestEnsureVaultPasswordPermissions:
    """Test vault password file permissions."""

    def test_ensure_permissions_fixes_wrong_permissions(self, tmp_path):
        """Test that wrong permissions are fixed."""
        vault_file = tmp_path / ".vault_password"
        vault_file.write_text("password")
        vault_file.chmod(0o644)  # Wrong permissions

        ensure_vault_password_permissions(vault_file)

        # Should be fixed to 0o600
        assert oct(vault_file.stat().st_mode)[-3:] == "600"

    def test_ensure_permissions_leaves_correct_permissions(self, tmp_path):
        """Test that correct permissions are left alone."""
        vault_file = tmp_path / ".vault_password"
        vault_file.write_text("password")
        vault_file.chmod(0o600)  # Correct permissions

        ensure_vault_password_permissions(vault_file)

        # Should still be 0o600
        assert oct(vault_file.stat().st_mode)[-3:] == "600"


class TestWriteVaultPasswordFile:
    """Test writing vault password file."""

    def test_write_vault_password_file(self, tmp_path):
        """Test writing password file with correct permissions."""
        vault_file = tmp_path / ".vault_password"

        write_vault_password_file(vault_file, "test_password")

        assert vault_file.exists()
        assert vault_file.read_text() == "test_password"
        assert oct(vault_file.stat().st_mode)[-3:] == "600"


class TestGetVaultPassword:
    """Test vault password retrieval."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_vault_password_cache()

    def test_get_vault_password_from_file(self, tmp_path):
        """Test getting password from file."""
        vault_file = tmp_path / ".vault_password"
        vault_file.write_text("file_password")

        with patch(
            "dotfiles_cli.vault.password.get_vault_password_file",
            return_value=vault_file,
        ):
            password = get_vault_password("alpha")

        assert password == "file_password"

    def test_get_vault_password_prompts_when_no_file(self, tmp_path):
        """Test prompting for password when file doesn't exist."""
        vault_file = tmp_path / ".vault_password"
        # File doesn't exist

        with (
            patch(
                "dotfiles_cli.vault.password.get_vault_password_file",
                return_value=vault_file,
            ),
            patch("getpass.getpass", return_value="prompted_password"),
        ):
            password = get_vault_password("alpha")

        assert password == "prompted_password"

    def test_get_vault_password_caches_result(self, tmp_path):
        """Test that password is cached after first retrieval."""
        vault_file = tmp_path / ".vault_password"
        vault_file.write_text("cached_password")

        with patch(
            "dotfiles_cli.vault.password.get_vault_password_file",
            return_value=vault_file,
        ):
            # First call
            password1 = get_vault_password("common")
            # Second call
            password2 = get_vault_password("common")

        assert password1 == "cached_password"
        assert password2 == "cached_password"


class TestValidateVaultPassword:
    """Test vault password validation."""

    def test_validate_vault_password_success(self, tmp_path):
        """Test validating correct password."""
        secrets_file = tmp_path / "profiles" / "alpha" / "secrets.yml"
        secrets_file.parent.mkdir(parents=True)
        secrets_file.write_text("$ANSIBLE_VAULT;1.1;AES256\nencrypted")

        with (
            patch("dotfiles_cli.profiles.get_profile_names", return_value=["alpha"]),
            patch(
                "dotfiles_cli.vault.operations.get_secrets_file",
                return_value=secrets_file,
            ),
            patch(
                "dotfiles_cli.vault.operations.run_ansible_vault",
                return_value=(0, "decrypted", ""),
            ),
        ):
            result = validate_vault_password("correct_password")

        assert result is True

    def test_validate_vault_password_failure(self, tmp_path):
        """Test validating incorrect password."""
        secrets_file = tmp_path / "profiles" / "alpha" / "secrets.yml"
        secrets_file.parent.mkdir(parents=True)
        secrets_file.write_text("$ANSIBLE_VAULT;1.1;AES256\nencrypted")

        with (
            patch("dotfiles_cli.profiles.get_profile_names", return_value=["alpha"]),
            patch(
                "dotfiles_cli.vault.operations.get_secrets_file",
                return_value=secrets_file,
            ),
            patch(
                "dotfiles_cli.vault.operations.run_ansible_vault",
                return_value=(1, "", "ERROR"),
            ),
        ):
            result = validate_vault_password("wrong_password")

        assert result is False

    def test_validate_vault_password_no_secrets_file(self, tmp_path):
        """Test validation when no secrets file exists (returns True)."""
        with patch("dotfiles_cli.profiles.get_profile_names", return_value=[]):
            result = validate_vault_password("any_password")

        # Should return True when no file to validate against
        assert result is True


class TestVaultIntegration:
    """Integration tests for vault operations."""

    def test_full_encrypt_decrypt_cycle(self, tmp_path):
        """Test encrypting and decrypting a file."""
        secrets_file = tmp_path / "test.yml"
        secrets_file.write_text("secret: value")

        # Mock the actual ansible-vault calls
        with (
            patch("subprocess.run") as mock_run,
            patch("dotfiles_cli.vault.operations.DOTFILES_DIR", str(tmp_path)),
        ):
            # Encrypt
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
            rc, stdout, stderr = run_ansible_vault(
                ["encrypt", str(secrets_file)], password="test_pass"
            )
            assert rc == 0

            # Decrypt
            mock_run.return_value = Mock(
                returncode=0, stdout="secret: value", stderr=""
            )
            rc, stdout, stderr = run_ansible_vault(
                ["decrypt", "--output", "-", str(secrets_file)], password="test_pass"
            )
            assert rc == 0
            assert "secret: value" in stdout
