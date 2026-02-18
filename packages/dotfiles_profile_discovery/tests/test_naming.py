"""Tests for naming utilities."""

from dotfiles_profile_discovery.naming import get_default_priority, path_to_name


class TestPathToName:
    """Tests for path_to_name function."""

    def test_single_level_path(self):
        """Single level path returns unchanged."""
        assert path_to_name("work") == "work"
        assert path_to_name("shell") == "shell"
        assert path_to_name("my-profile") == "my-profile"

    def test_nested_path_converts_slash_to_dash(self):
        """Nested path converts slash to dash."""
        assert path_to_name("myrepo/work") == "myrepo-work"
        assert path_to_name("company/personal") == "company-personal"

    def test_handles_special_characters(self):
        """Handles paths with dashes."""
        assert path_to_name("my-company/my-profile") == "my-company-my-profile"


class TestGetDefaultPriority:
    """Tests for get_default_priority function."""

    def test_default_profile_priority(self):
        """Default profile has priority 100."""
        assert get_default_priority("default") == 100

    def test_shell_profile_priority(self):
        """Shell profile has priority 100."""
        assert get_default_priority("shell") == 100

    def test_neovim_profile_priority(self):
        """Neovim profile has priority 110."""
        assert get_default_priority("neovim") == 110

    def test_development_profile_priority(self):
        """Development profile has priority 120."""
        assert get_default_priority("development") == 120

    def test_macos_desktop_profile_priority(self):
        """macOS desktop profile has priority 130."""
        assert get_default_priority("macos-desktop") == 130

    def test_work_profile_priority(self):
        """Work profile has priority 200."""
        assert get_default_priority("work") == 200

    def test_personal_profile_priority(self):
        """Personal profile has priority 200."""
        assert get_default_priority("personal") == 200

    def test_unknown_profile_priority(self):
        """Unknown profiles have priority 1000."""
        assert get_default_priority("mycompany") == 1000
        assert get_default_priority("custom-profile") == 1000
        assert get_default_priority("myrepo-work") == 1000
