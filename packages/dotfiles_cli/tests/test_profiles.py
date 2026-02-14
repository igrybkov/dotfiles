"""Tests for profile selection and discovery."""

from unittest.mock import patch


from dotfiles_cli.profiles.discovery import (
    get_all_profile_names,
    get_profile_names,
    get_profile_roles_paths,
    get_profile_requirements_paths,
)
from dotfiles_cli.profiles.selection import (
    ProfileSelection,
    parse_profile_selection,
)


def _create_profile(profiles_dir, name, config_content="---\n"):
    """Helper to create a profile directory with config.yml."""
    profile_dir = profiles_dir / name
    profile_dir.mkdir(parents=True, exist_ok=True)
    (profile_dir / "config.yml").write_text(config_content)
    return profile_dir


class TestProfileSelection:
    """Test ProfileSelection dataclass and resolution logic."""

    def test_resolve_explicit_profiles(self):
        """Test resolving explicit profile list."""
        selection = ProfileSelection(explicit_profiles=["common", "work"])
        available = ["common", "work", "personal"]
        result = selection.resolve(available)
        assert result == ["common", "work"]

    def test_resolve_include_all(self):
        """Test resolving 'all' selection."""
        selection = ProfileSelection(include_all=True)
        available = ["common", "work", "personal"]
        result = selection.resolve(available)
        assert result == ["common", "personal", "work"]

    def test_resolve_with_exclusions(self):
        """Test resolving with exclusions."""
        selection = ProfileSelection(include_all=True, excluded_profiles=["personal"])
        available = ["common", "work", "personal"]
        result = selection.resolve(available)
        assert result == ["common", "work"]

    def test_resolve_explicit_with_exclusions(self):
        """Test explicit profiles with exclusions."""
        selection = ProfileSelection(
            explicit_profiles=["common", "work", "personal"], excluded_profiles=["work"]
        )
        available = ["common", "work", "personal", "mycompany"]
        result = selection.resolve(available)
        assert result == ["common", "personal"]

    def test_resolve_filters_unavailable(self):
        """Test that unavailable profiles are filtered out."""
        selection = ProfileSelection(
            explicit_profiles=["common", "work", "nonexistent"]
        )
        available = ["common", "work"]
        result = selection.resolve(available)
        assert result == ["common", "work"]

    def test_resolve_default_common_only(self):
        """Test default resolution (no selection) returns common only."""
        selection = ProfileSelection()
        available = ["common", "work", "personal"]
        result = selection.resolve(available)
        assert result == ["common"]

    def test_resolve_empty_when_no_common(self):
        """Test resolution when common is not available."""
        selection = ProfileSelection()
        available = ["work", "personal"]
        result = selection.resolve(available)
        assert result == []


class TestParseProfileSelection:
    """Test profile selection string parsing."""

    def test_parse_explicit_profiles(self):
        """Test parsing explicit profile list."""
        selection = parse_profile_selection("common,work")
        assert selection.explicit_profiles == ["common", "work"]
        assert not selection.include_all
        assert selection.excluded_profiles == []

    def test_parse_all(self):
        """Test parsing 'all' selection."""
        selection = parse_profile_selection("all")
        assert selection.include_all
        assert selection.explicit_profiles == []
        assert selection.excluded_profiles == []

    def test_parse_exclusion_only(self):
        """Test parsing exclusion-only (implies all)."""
        selection = parse_profile_selection("-work")
        assert selection.include_all
        assert selection.excluded_profiles == ["work"]
        assert selection.explicit_profiles == []

    def test_parse_all_with_exclusions(self):
        """Test parsing 'all' with exclusions."""
        selection = parse_profile_selection("all,-work,-personal")
        assert selection.include_all
        assert selection.excluded_profiles == ["work", "personal"]

    def test_parse_explicit_with_exclusions(self):
        """Test parsing explicit list with exclusions."""
        selection = parse_profile_selection("common,work,personal,-work")
        # Parsing stores both explicit and excluded separately
        # The exclusion is applied during resolve(), not parsing
        assert selection.explicit_profiles == ["common", "work", "personal"]
        assert selection.excluded_profiles == ["work"]

    def test_parse_empty_string(self):
        """Test parsing empty string (default)."""
        selection = parse_profile_selection("")
        assert selection.explicit_profiles == []
        assert selection.excluded_profiles == []
        assert not selection.include_all

    def test_parse_none(self):
        """Test parsing None (default)."""
        selection = parse_profile_selection(None)
        assert selection.explicit_profiles == []
        assert selection.excluded_profiles == []
        assert not selection.include_all

    def test_parse_whitespace(self):
        """Test parsing handles whitespace."""
        selection = parse_profile_selection(" common , work ")
        assert selection.explicit_profiles == ["common", "work"]

    def test_parse_trailing_comma(self):
        """Test parsing handles trailing commas."""
        selection = parse_profile_selection("common,work,")
        assert selection.explicit_profiles == ["common", "work"]

    def test_parse_empty_exclusion(self):
        """Test parsing handles empty exclusion (-)."""
        selection = parse_profile_selection("common,-")
        assert selection.explicit_profiles == ["common"]
        assert selection.excluded_profiles == []

    def test_parse_case_insensitive_all(self):
        """Test 'all' is case-insensitive."""
        selection = parse_profile_selection("ALL")
        assert selection.include_all

        selection = parse_profile_selection("All")
        assert selection.include_all


class TestGetProfileNames:
    """Test profile discovery from filesystem."""

    def test_get_profile_names(self, tmp_path):
        """Test getting profile names from directory."""
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        _create_profile(profiles_dir, "common")
        _create_profile(profiles_dir, "work")
        _create_profile(profiles_dir, "personal")
        # Hidden directories are ignored
        (profiles_dir / ".hidden").mkdir()
        (profiles_dir / ".hidden" / "config.yml").write_text("---\n")
        # Files are ignored
        (profiles_dir / "file.txt").write_text("not a dir")
        # Directories without config.yml are not profiles
        (profiles_dir / "no-config").mkdir()

        with patch("dotfiles_cli.profiles.discovery.DOTFILES_DIR", str(tmp_path)):
            result = get_profile_names()

        assert result == ["common", "personal", "work"]
        assert ".hidden" not in result
        assert "no-config" not in result

    def test_get_profile_names_empty_dir(self, tmp_path):
        """Test getting profile names from empty directory."""
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()

        with patch("dotfiles_cli.profiles.discovery.DOTFILES_DIR", str(tmp_path)):
            result = get_profile_names()

        assert result == []

    def test_get_profile_names_no_profiles_dir(self, tmp_path):
        """Test getting profile names when profiles dir doesn't exist."""
        with patch("dotfiles_cli.profiles.discovery.DOTFILES_DIR", str(tmp_path)):
            result = get_profile_names()

        assert result == []

    def test_get_all_profile_names_delegates(self, tmp_path):
        """Test get_all_profile_names delegates to get_profile_names."""
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        _create_profile(profiles_dir, "test")

        with patch("dotfiles_cli.profiles.discovery.DOTFILES_DIR", str(tmp_path)):
            result = get_all_profile_names()

        assert result == ["test"]

    def test_get_nested_profile_names(self, tmp_path):
        """Test getting profile names from nested structure."""
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        # Single level
        _create_profile(profiles_dir, "common")
        # Nested level - repo directory without config.yml, profiles inside
        repo_dir = profiles_dir / "myrepo"
        repo_dir.mkdir()
        _create_profile(repo_dir, "work")
        _create_profile(repo_dir, "personal")

        with patch("dotfiles_cli.profiles.discovery.DOTFILES_DIR", str(tmp_path)):
            result = get_profile_names()

        # Nested profiles use dash-separated names
        assert "common" in result
        assert "myrepo-work" in result
        assert "myrepo-personal" in result
        assert len(result) == 3

    def test_get_deep_nested_profile_names(self, tmp_path):
        """Test getting profile names from 3-level nested structure."""
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        # Single level
        _create_profile(profiles_dir, "common")
        # 3-level nested: profiles/private/myrepo/work
        private_dir = profiles_dir / "private"
        repo_dir = private_dir / "myrepo"
        repo_dir.mkdir(parents=True)
        _create_profile(repo_dir, "work")
        _create_profile(repo_dir, "personal")

        with patch("dotfiles_cli.profiles.discovery.DOTFILES_DIR", str(tmp_path)):
            result = get_profile_names()

        # Deep nested profiles use dash-separated names
        assert "common" in result
        assert "private-myrepo-work" in result
        assert "private-myrepo-personal" in result
        assert len(result) == 3


class TestGetProfileRolesPaths:
    """Test getting profile roles directories."""

    def test_get_profile_roles_paths(self, tmp_path):
        """Test getting roles paths from profiles."""
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()

        # Create profiles with and without roles
        common_dir = _create_profile(profiles_dir, "common")
        common_roles = common_dir / "roles"
        common_roles.mkdir()

        # work has no roles directory
        _create_profile(profiles_dir, "work")

        personal_dir = _create_profile(profiles_dir, "personal")
        personal_roles = personal_dir / "roles"
        personal_roles.mkdir()

        with patch("dotfiles_cli.profiles.discovery.DOTFILES_DIR", str(tmp_path)):
            result = get_profile_roles_paths()

        # Should only include profiles that have roles directories
        assert len(result) == 2
        assert str(common_roles) in result
        assert str(personal_roles) in result

    def test_get_profile_roles_paths_none_exist(self, tmp_path):
        """Test when no profile has roles directory."""
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        _create_profile(profiles_dir, "common")
        _create_profile(profiles_dir, "work")

        with patch("dotfiles_cli.profiles.discovery.DOTFILES_DIR", str(tmp_path)):
            result = get_profile_roles_paths()

        assert result == []

    def test_get_profile_roles_paths_no_profiles(self, tmp_path):
        """Test when profiles directory doesn't exist."""
        with patch("dotfiles_cli.profiles.discovery.DOTFILES_DIR", str(tmp_path)):
            result = get_profile_roles_paths()

        assert result == []


class TestGetProfileRequirementsPaths:
    """Test getting profile Galaxy requirements files."""

    def test_get_profile_requirements_paths(self, tmp_path):
        """Test getting requirements paths from profiles."""
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()

        # Create profiles with and without requirements
        common_dir = _create_profile(profiles_dir, "common")
        common_req = common_dir / "requirements.yml"
        common_req.write_text("---\ncollections: []")

        # work has no requirements file
        _create_profile(profiles_dir, "work")

        personal_dir = _create_profile(profiles_dir, "personal")
        personal_req = personal_dir / "requirements.yml"
        personal_req.write_text("---\ncollections: []")

        with patch("dotfiles_cli.profiles.discovery.DOTFILES_DIR", str(tmp_path)):
            result = get_profile_requirements_paths()

        # Should only include profiles that have requirements.yml
        assert len(result) == 2
        assert str(common_req) in result
        assert str(personal_req) in result

    def test_get_profile_requirements_paths_none_exist(self, tmp_path):
        """Test when no profile has requirements file."""
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        _create_profile(profiles_dir, "common")
        _create_profile(profiles_dir, "work")

        with patch("dotfiles_cli.profiles.discovery.DOTFILES_DIR", str(tmp_path)):
            result = get_profile_requirements_paths()

        assert result == []

    def test_get_profile_requirements_paths_no_profiles(self, tmp_path):
        """Test when profiles directory doesn't exist."""
        with patch("dotfiles_cli.profiles.discovery.DOTFILES_DIR", str(tmp_path)):
            result = get_profile_requirements_paths()

        assert result == []

    def test_get_profile_requirements_paths_ignores_directories(self, tmp_path):
        """Test that directories named requirements.yml are ignored."""
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()

        # Create a profile with a directory named requirements.yml
        common_dir = _create_profile(profiles_dir, "common")
        (common_dir / "requirements.yml").mkdir()  # directory, not file

        with patch("dotfiles_cli.profiles.discovery.DOTFILES_DIR", str(tmp_path)):
            result = get_profile_requirements_paths()

        assert result == []


class TestProfileIntegration:
    """Integration tests for profile selection and discovery."""

    def test_full_workflow_explicit_selection(self, tmp_path):
        """Test complete workflow with explicit profile selection."""
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        _create_profile(profiles_dir, "common")
        _create_profile(profiles_dir, "work")
        _create_profile(profiles_dir, "personal")

        with patch("dotfiles_cli.profiles.discovery.DOTFILES_DIR", str(tmp_path)):
            available = get_all_profile_names()
            selection = parse_profile_selection("common,work")
            result = selection.resolve(available)

        assert result == ["common", "work"]

    def test_full_workflow_all_minus_one(self, tmp_path):
        """Test complete workflow with 'all except' selection."""
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        _create_profile(profiles_dir, "common")
        _create_profile(profiles_dir, "work")
        _create_profile(profiles_dir, "personal")

        with patch("dotfiles_cli.profiles.discovery.DOTFILES_DIR", str(tmp_path)):
            available = get_all_profile_names()
            selection = parse_profile_selection("-work")
            result = selection.resolve(available)

        assert result == ["common", "personal"]

    def test_full_workflow_default(self, tmp_path):
        """Test complete workflow with default (common only)."""
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        _create_profile(profiles_dir, "common")
        _create_profile(profiles_dir, "work")

        with patch("dotfiles_cli.profiles.discovery.DOTFILES_DIR", str(tmp_path)):
            available = get_all_profile_names()
            selection = parse_profile_selection(None)
            result = selection.resolve(available)

        assert result == ["common"]

    def test_full_workflow_nested_profiles(self, tmp_path):
        """Test complete workflow with nested profile selection."""
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        _create_profile(profiles_dir, "common")
        repo_dir = profiles_dir / "myrepo"
        repo_dir.mkdir()
        _create_profile(repo_dir, "work")

        with patch("dotfiles_cli.profiles.discovery.DOTFILES_DIR", str(tmp_path)):
            available = get_all_profile_names()
            selection = parse_profile_selection("common,myrepo-work")
            result = selection.resolve(available)

        assert result == ["common", "myrepo-work"]
