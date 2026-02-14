"""Tests for profile discovery."""

import pytest

from dotfiles_profile_discovery import discover_profiles, get_profile_by_name


@pytest.fixture
def temp_profiles_dir(tmp_path):
    """Create a temporary profiles directory."""
    return tmp_path / "profiles"


class TestDiscoverProfiles:
    """Tests for discover_profiles function."""

    def test_empty_directory(self, temp_profiles_dir):
        """Empty directory returns empty list."""
        temp_profiles_dir.mkdir()
        assert discover_profiles(temp_profiles_dir) == []

    def test_nonexistent_directory(self, temp_profiles_dir):
        """Nonexistent directory returns empty list."""
        assert discover_profiles(temp_profiles_dir) == []

    def test_single_level_profile(self, temp_profiles_dir):
        """Single level profile is discovered."""
        temp_profiles_dir.mkdir()
        work_dir = temp_profiles_dir / "work"
        work_dir.mkdir()
        (work_dir / "config.yml").write_text("profile:\n  name: work\n")

        profiles = discover_profiles(temp_profiles_dir)

        assert len(profiles) == 1
        assert profiles[0].name == "work"
        assert profiles[0].relative_path == "work"
        assert profiles[0].priority == 200  # Special priority for "work"

    def test_nested_profile(self, temp_profiles_dir):
        """Nested profile is discovered with dash-separated name."""
        temp_profiles_dir.mkdir()
        repo_dir = temp_profiles_dir / "myrepo"
        work_dir = repo_dir / "work"
        work_dir.mkdir(parents=True)
        (work_dir / "config.yml").write_text("---\n")

        profiles = discover_profiles(temp_profiles_dir)

        assert len(profiles) == 1
        assert profiles[0].name == "myrepo-work"
        assert profiles[0].relative_path == "myrepo/work"
        assert profiles[0].host_name == "myrepo-work-profile"

    def test_mixed_levels(self, temp_profiles_dir):
        """Both single and nested profiles discovered."""
        temp_profiles_dir.mkdir()

        # Single level
        common_dir = temp_profiles_dir / "common"
        common_dir.mkdir()
        (common_dir / "config.yml").write_text("profile:\n  name: common\n")

        # Nested level
        repo_dir = temp_profiles_dir / "myrepo"
        work_dir = repo_dir / "work"
        work_dir.mkdir(parents=True)
        (work_dir / "config.yml").write_text("---\n")

        profiles = discover_profiles(temp_profiles_dir)

        assert len(profiles) == 2
        names = {p.name for p in profiles}
        assert names == {"common", "myrepo-work"}

    def test_custom_name_override(self, temp_profiles_dir):
        """Custom name in config.yml overrides default."""
        temp_profiles_dir.mkdir()
        profile_dir = temp_profiles_dir / "work-profile"
        profile_dir.mkdir()
        (profile_dir / "config.yml").write_text(
            "profile:\n  name: custom-name\n  priority: 500\n"
        )

        profiles = discover_profiles(temp_profiles_dir)

        assert len(profiles) == 1
        assert profiles[0].name == "custom-name"
        assert profiles[0].priority == 500

    def test_directory_without_config_skipped(self, temp_profiles_dir):
        """Directory without config.yml is not a profile."""
        temp_profiles_dir.mkdir()

        # Directory with config.yml (valid profile)
        work_dir = temp_profiles_dir / "work"
        work_dir.mkdir()
        (work_dir / "config.yml").write_text("---\n")

        # Directory without config.yml (not a profile)
        invalid_dir = temp_profiles_dir / "not-a-profile"
        invalid_dir.mkdir()

        profiles = discover_profiles(temp_profiles_dir)

        assert len(profiles) == 1
        assert profiles[0].name == "work"

    def test_depth_three_profile(self, temp_profiles_dir):
        """Profiles at depth 3 are discovered."""
        temp_profiles_dir.mkdir()

        # Depth 3: profiles/private/myrepo/work/config.yml
        deep_dir = temp_profiles_dir / "private" / "myrepo" / "work"
        deep_dir.mkdir(parents=True)
        (deep_dir / "config.yml").write_text("---\n")

        profiles = discover_profiles(temp_profiles_dir)

        assert len(profiles) == 1
        assert profiles[0].name == "private-myrepo-work"
        assert profiles[0].relative_path == "private/myrepo/work"

    def test_depth_four_ignored(self, temp_profiles_dir):
        """Profiles at depth 4+ are not discovered."""
        temp_profiles_dir.mkdir()

        # Depth 4: profiles/a/b/c/d/config.yml - should be ignored
        deep_dir = temp_profiles_dir / "a" / "b" / "c" / "d"
        deep_dir.mkdir(parents=True)
        (deep_dir / "config.yml").write_text("---\n")

        # Depth 3: profiles/a/b/c/config.yml - should be found
        (temp_profiles_dir / "a" / "b" / "c" / "config.yml").write_text("---\n")

        profiles = discover_profiles(temp_profiles_dir)

        # Should find depth 3 only
        assert len(profiles) == 1
        assert profiles[0].relative_path == "a/b/c"

    def test_hidden_directories_ignored(self, temp_profiles_dir):
        """Hidden directories are ignored at all levels."""
        temp_profiles_dir.mkdir()

        # Hidden directory at level 1
        hidden_dir = temp_profiles_dir / ".hidden"
        hidden_dir.mkdir()
        (hidden_dir / "config.yml").write_text("---\n")

        # Hidden directory at level 2
        repo_dir = temp_profiles_dir / "myrepo"
        repo_dir.mkdir()
        hidden_nested = repo_dir / ".private"
        hidden_nested.mkdir()
        (hidden_nested / "config.yml").write_text("---\n")

        profiles = discover_profiles(temp_profiles_dir)

        assert len(profiles) == 0

    def test_config_values_loaded(self, temp_profiles_dir):
        """Config values are loaded into ProfileInfo."""
        temp_profiles_dir.mkdir()
        work_dir = temp_profiles_dir / "work"
        work_dir.mkdir()
        (work_dir / "config.yml").write_text(
            """---
profile:
  name: work
brew_packages:
  - name: vim
ssh_client_config:
  - host: example.com
"""
        )

        profiles = discover_profiles(temp_profiles_dir)

        assert len(profiles) == 1
        assert profiles[0].config["brew_packages"] == [{"name": "vim"}]
        assert profiles[0].config["ssh_client_config"] == [{"host": "example.com"}]

    def test_profile_meta_not_in_config(self, temp_profiles_dir):
        """Profile metadata is not included in config dict."""
        temp_profiles_dir.mkdir()
        work_dir = temp_profiles_dir / "work"
        work_dir.mkdir()
        (work_dir / "config.yml").write_text(
            """---
profile:
  name: work
  priority: 200
brew_packages:
  - name: vim
"""
        )

        profiles = discover_profiles(temp_profiles_dir)

        assert len(profiles) == 1
        assert "profile" not in profiles[0].config
        assert "brew_packages" in profiles[0].config


class TestGetProfileByName:
    """Tests for get_profile_by_name function."""

    def test_find_existing_profile(self, temp_profiles_dir):
        """Find an existing profile by name."""
        temp_profiles_dir.mkdir()
        work_dir = temp_profiles_dir / "work"
        work_dir.mkdir()
        (work_dir / "config.yml").write_text("---\n")

        profile = get_profile_by_name(temp_profiles_dir, "work")

        assert profile is not None
        assert profile.name == "work"

    def test_find_nested_profile(self, temp_profiles_dir):
        """Find a nested profile by dash-separated name."""
        temp_profiles_dir.mkdir()
        repo_dir = temp_profiles_dir / "myrepo"
        work_dir = repo_dir / "work"
        work_dir.mkdir(parents=True)
        (work_dir / "config.yml").write_text("---\n")

        profile = get_profile_by_name(temp_profiles_dir, "myrepo-work")

        assert profile is not None
        assert profile.name == "myrepo-work"

    def test_nonexistent_profile(self, temp_profiles_dir):
        """Return None for nonexistent profile."""
        temp_profiles_dir.mkdir()

        profile = get_profile_by_name(temp_profiles_dir, "nonexistent")

        assert profile is None
