"""Tests for custom Click types."""

from unittest.mock import patch

import pytest

from dotfiles_cli.types import (
    AliasedGroup,
    ProfileListType,
    PyinfraTagListType,
)


class TestPyinfraTagListType:
    """Test PyinfraTagListType against the static pyinfra tag registry."""

    def test_get_all_supported_tags(self):
        """Tags come from the registry, plus the 'all' selector."""
        tags = PyinfraTagListType._get_all_supported_tags()

        assert "all" in tags
        assert "brew" in tags
        assert "dotfiles" in tags
        assert "mcp-servers" in tags
        assert tags == sorted(tags)

    def test_choices_property(self):
        """The choices property mirrors the registry."""
        tag_type = PyinfraTagListType()

        assert tag_type.choices == PyinfraTagListType._get_all_supported_tags()

    def test_convert_single_value(self):
        tag_type = PyinfraTagListType()

        assert tag_type.convert("brew", None, None) == "brew"

    def test_convert_list_values(self):
        tag_type = PyinfraTagListType()

        assert tag_type.convert(["brew", "dotfiles"], None, None) == [
            "brew",
            "dotfiles",
        ]

    def test_convert_invalid_tag(self):
        from click import BadParameter

        tag_type = PyinfraTagListType()

        with pytest.raises(BadParameter):
            tag_type.convert("invalid_tag", None, None)

    def test_shell_complete(self):
        tag_type = PyinfraTagListType()
        completions = tag_type.shell_complete(None, None, "")

        completion_values = [c.value for c in completions]
        assert "all" in completion_values
        assert "brew" in completion_values
        assert "dotfiles" in completion_values


class TestProfileListType:
    """Test ProfileListType for profile-name discovery."""

    def test_convert_valid_profile(self):
        with patch.object(
            ProfileListType, "get_all_profiles", return_value=["work", "personal"]
        ):
            profile_type = ProfileListType()

            assert profile_type.convert("work", None, None) == "work"

    def test_convert_invalid_profile(self):
        from click import BadParameter

        with patch.object(
            ProfileListType, "get_all_profiles", return_value=["work", "personal"]
        ):
            profile_type = ProfileListType()

            with pytest.raises(BadParameter):
                profile_type.convert("nonexistent", None, None)

    def test_shell_complete(self):
        profile_type = ProfileListType()

        with patch.object(
            profile_type,
            "get_all_profiles",
            return_value=["work", "personal", "mycompany"],
        ):
            completions = profile_type.shell_complete(None, None, "")

        completion_values = [c.value for c in completions]
        assert "work" in completion_values
        assert "personal" in completion_values
        assert "mycompany" in completion_values

    def test_get_all_profiles_discovers_from_disk(self, tmp_path):
        """Discovery reads profiles/ under DOTFILES_DIR."""
        profile_dir = tmp_path / "profiles" / "sample"
        profile_dir.mkdir(parents=True)
        (profile_dir / "config.yml").write_text("profile:\n  priority: 100\n")

        with patch("dotfiles_cli.types.DOTFILES_DIR", str(tmp_path)):
            assert ProfileListType.get_all_profiles() == ["sample"]


class TestAliasedGroup:
    """Test AliasedGroup for command prefix matching and aliases."""

    def test_get_command_exact_match(self):
        import click

        group = AliasedGroup()

        @group.command("install")
        def install_cmd():
            pass

        ctx = click.Context(group)
        cmd = group.get_command(ctx, "install")

        assert cmd is not None
        assert cmd.name == "install"

    def test_get_command_prefix_match(self):
        import click

        group = AliasedGroup()

        @group.command("install")
        def install_cmd():
            pass

        @group.command("completion")
        def completion_cmd():
            pass

        ctx = click.Context(group)
        cmd = group.get_command(ctx, "inst")

        assert cmd is not None
        assert cmd.name == "install"

    def test_get_command_ambiguous_prefix(self):
        import click
        from click.exceptions import UsageError

        group = AliasedGroup()

        @group.command("install")
        def install_cmd():
            pass

        @group.command("init")
        def init_cmd():
            pass

        ctx = click.Context(group)

        with pytest.raises(UsageError):  # ctx.fail raises UsageError
            group.get_command(ctx, "in")

    def test_get_command_no_match(self):
        import click

        group = AliasedGroup()

        @group.command("install")
        def install_cmd():
            pass

        ctx = click.Context(group)

        assert group.get_command(ctx, "nonexistent") is None

    def test_resolve_command_returns_full_name(self):
        import click

        group = AliasedGroup()

        @group.command("install")
        def install_cmd():
            pass

        ctx = click.Context(group)

        name, cmd, args = group.resolve_command(ctx, ["inst", "arg1"])

        assert name == "install"
        assert cmd.name == "install"
        assert args == ["arg1"]


class TestTypesIntegration:
    """Integration tests for custom types."""

    def test_tag_type_in_click_command(self):
        import click

        @click.command()
        @click.argument("tag", type=PyinfraTagListType())
        def test_cmd(tag):
            return tag

        runner = click.testing.CliRunner()
        result = runner.invoke(test_cmd, ["brew"])

        assert result.exit_code == 0

    def test_profile_type_in_click_option(self):
        import click

        @click.command()
        @click.option("--profile", type=ProfileListType())
        def test_cmd(profile):
            return profile

        runner = click.testing.CliRunner()

        with patch.object(
            ProfileListType, "get_all_profiles", return_value=["work", "personal"]
        ):
            result = runner.invoke(test_cmd, ["--profile", "work"])

        assert result.exit_code == 0
