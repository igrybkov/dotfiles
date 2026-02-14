"""Tests for ProfileInfo model."""

from pathlib import Path


from dotfiles_profile_discovery.models import ProfileInfo


class TestProfileInfo:
    """Tests for ProfileInfo dataclass."""

    def test_all_fields_accessible(self):
        """All fields are accessible."""
        profile = ProfileInfo(
            name="work",
            path=Path("/profiles/work"),
            relative_path="work",
            priority=200,
            host_name="work-profile",
            connection="local",
            config={"brew_packages": [{"name": "vim"}]},
        )

        assert profile.name == "work"
        assert profile.path == Path("/profiles/work")
        assert profile.relative_path == "work"
        assert profile.priority == 200
        assert profile.host_name == "work-profile"
        assert profile.connection == "local"
        assert profile.config == {"brew_packages": [{"name": "vim"}]}

    def test_nested_profile_info(self):
        """ProfileInfo correctly represents nested profile."""
        profile = ProfileInfo(
            name="myrepo-work",
            path=Path("/profiles/myrepo/work"),
            relative_path="myrepo/work",
            priority=1000,
            host_name="myrepo-work-profile",
            connection="local",
            config={},
        )

        assert profile.name == "myrepo-work"
        assert profile.relative_path == "myrepo/work"
        assert "/" in profile.relative_path
        assert "-" in profile.name
