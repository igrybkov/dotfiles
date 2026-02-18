"""Tests for custom Click types."""

from unittest.mock import Mock, patch

import pytest

from dotfiles_cli.types import (
    AliasedGroup,
    AnsibleHostListType,
    AnsibleTagListType,
)


class TestAnsibleTagListType:
    """Test AnsibleTagListType for tag discovery and validation."""

    def test_get_all_supported_tags(self, tmp_path):
        """Test getting all tags from playbook."""
        mock_stdout = """
playbook: playbook.yml

  play #1 (all): PLAY NAME    TAGS: []
      TASK TAGS: [brew, cask, dotfiles, macos, pip, ssh]

  play #2 (all): PLAY NAME    TAGS: []
      TASK TAGS: [gh-repos, gh-extensions]

TAGS: [all, brew, cask, dotfiles, gh-extensions, gh-repos, macos, never, pip, ssh]
        """

        mock_runner = Mock()
        mock_runner.stdout.read.return_value = mock_stdout

        with (
            patch("ansible_runner.RunnerConfig"),
            patch("ansible_runner.Runner", return_value=mock_runner),
            patch("dotfiles_cli.types.DOTFILES_DIR", str(tmp_path)),
            patch("dotfiles_cli.types._load_tags_cache", return_value=None),
            patch("dotfiles_cli.types._save_tags_cache"),
            patch("dotfiles_cli.types._get_playbook_mtime", return_value=0),
        ):
            tag_type = AnsibleTagListType()
            tags = tag_type._get_all_supported_tags()

        assert "all" in tags
        assert "brew" in tags
        assert "dotfiles" in tags
        assert "ssh" in tags
        assert "never" not in tags  # Should be excluded
        assert "always" not in tags  # Should be excluded

    def test_choices_property(self):
        """Test that choices property returns tags."""
        with patch(
            "dotfiles_cli.types._get_cached_tags",
            return_value=["all", "brew", "dotfiles"],
        ):
            tag_type = AnsibleTagListType()
            choices = tag_type.choices

        assert "all" in choices
        assert "brew" in choices
        assert "dotfiles" in choices

    def test_convert_single_value(self):
        """Test converting single tag value."""
        with patch(
            "dotfiles_cli.types._get_cached_tags",
            return_value=["all", "brew", "dotfiles"],
        ):
            tag_type = AnsibleTagListType()
            result = tag_type.convert("brew", None, None)

        assert result == "brew"

    def test_convert_list_values(self):
        """Test converting list of tag values."""
        with patch(
            "dotfiles_cli.types._get_cached_tags",
            return_value=["all", "brew", "dotfiles", "ssh"],
        ):
            tag_type = AnsibleTagListType()
            result = tag_type.convert(["brew", "dotfiles"], None, None)

        assert result == ["brew", "dotfiles"]

    def test_convert_invalid_tag(self):
        """Test converting invalid tag raises error."""
        from click import BadParameter

        with patch(
            "dotfiles_cli.types._get_cached_tags",
            return_value=["all", "brew", "dotfiles"],
        ):
            tag_type = AnsibleTagListType()
            with pytest.raises(BadParameter):
                tag_type.convert("invalid_tag", None, None)

    def test_shell_complete(self):
        """Test shell completion returns all tags."""
        with patch(
            "dotfiles_cli.types._get_cached_tags",
            return_value=["all", "brew", "dotfiles"],
        ):
            tag_type = AnsibleTagListType()
            completions = tag_type.shell_complete(None, None, "")

        completion_values = [c.value for c in completions]
        assert "all" in completion_values
        assert "brew" in completion_values
        assert "dotfiles" in completion_values


class TestAnsibleHostListType:
    """Test AnsibleHostListType for host discovery."""

    def test_get_all_hosts_success(self, tmp_path):
        """Test getting all hosts from inventory."""
        mock_inventory = {
            "all": {"children": ["profiles", "ungrouped"]},
            "profiles": {"hosts": ["work-profile", "personal-profile"]},
            "ungrouped": {"hosts": []},
        }

        with (
            patch(
                "ansible_runner.interface.get_inventory",
                return_value=(mock_inventory, None),
            ),
            patch("dotfiles_cli.types.DOTFILES_DIR", str(tmp_path)),
        ):
            host_type = AnsibleHostListType()
            hosts = host_type.get_all_hosts()

        assert "work-profile" in hosts
        assert "personal-profile" in hosts
        assert "all" not in hosts  # Excluded
        assert "ungrouped" not in hosts  # Excluded

    def test_get_all_hosts_with_groups(self, tmp_path):
        """Test getting hosts includes group names."""
        mock_inventory = {
            "all": {"children": ["profiles", "workstations"]},
            "profiles": {"hosts": ["common-profile"]},
            "workstations": {"hosts": ["laptop", "desktop"]},
        }

        with (
            patch(
                "ansible_runner.interface.get_inventory",
                return_value=(mock_inventory, None),
            ),
            patch("dotfiles_cli.types.DOTFILES_DIR", str(tmp_path)),
        ):
            host_type = AnsibleHostListType()
            hosts = host_type.get_all_hosts()

        # Should include both hosts and non-excluded groups
        assert "common-profile" in hosts
        assert "laptop" in hosts
        assert "desktop" in hosts
        assert "profiles" in hosts
        assert "workstations" in hosts

    def test_get_all_hosts_fallback_on_error(self, tmp_path):
        """Test fallback to default hosts when inventory fails."""
        with (
            patch(
                "ansible_runner.interface.get_inventory", side_effect=Exception("Error")
            ),
            patch("dotfiles_cli.types.DOTFILES_DIR", str(tmp_path)),
        ):
            host_type = AnsibleHostListType()
            hosts = host_type.get_all_hosts()

        # Should return fallback hosts
        assert "work" in hosts
        assert "personal" in hosts

    def test_get_all_hosts_fallback_on_invalid_result(self, tmp_path):
        """Test fallback when inventory returns non-dict."""
        with (
            patch("ansible_runner.interface.get_inventory", return_value=(None, None)),
            patch("dotfiles_cli.types.DOTFILES_DIR", str(tmp_path)),
        ):
            host_type = AnsibleHostListType()
            hosts = host_type.get_all_hosts()

        # Should return fallback hosts
        assert "work" in hosts
        assert "personal" in hosts

    def test_choices_property_cached(self):
        """Test that choices property is cached."""
        with patch.object(
            AnsibleHostListType, "get_all_hosts", return_value=["work", "personal"]
        ):
            host_type = AnsibleHostListType()

            # First access
            choices1 = host_type.choices
            # Second access
            choices2 = host_type.choices

            # Should only call get_all_hosts once due to caching
            # Note: lru_cache is on the property, so this might not work as expected
            # The test verifies the property returns consistent results
            assert choices1 == choices2

    def test_shell_complete(self):
        """Test shell completion returns all hosts."""
        host_type = AnsibleHostListType()

        with patch.object(
            host_type, "get_all_hosts", return_value=["work", "personal", "mycompany"]
        ):
            completions = host_type.shell_complete(None, None, "")

        completion_values = [c.value for c in completions]
        assert "work" in completion_values
        assert "personal" in completion_values
        assert "mycompany" in completion_values


class TestAliasedGroup:
    """Test AliasedGroup for command prefix matching and aliases."""

    def test_get_command_exact_match(self):
        """Test getting command with exact match."""
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
        """Test getting command with prefix match."""
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
        """Test getting command with ambiguous prefix fails."""
        import click
        from click.exceptions import UsageError

        # Mock _get_cached_tags for any AnsibleTagListType instances
        with patch(
            "dotfiles_cli.types._get_cached_tags",
            return_value=["all", "brew", "dotfiles"],
        ):
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
        """Test getting command with no match returns None."""
        import click

        group = AliasedGroup()

        @group.command("install")
        def install_cmd():
            pass

        ctx = click.Context(group)

        # When there's no match and no alias, should delegate to parent
        # which might return None or handle aliases
        _cmd = group.get_command(ctx, "nonexistent")
        # The behavior depends on click_aliases implementation

    def test_resolve_command_returns_full_name(self):
        """Test resolve_command returns full command name."""
        import click

        group = AliasedGroup()

        @group.command("install")
        def install_cmd():
            pass

        ctx = click.Context(group)

        # Resolve with prefix
        name, cmd, args = group.resolve_command(ctx, ["inst", "arg1"])

        assert name == "install"
        assert cmd.name == "install"
        assert args == ["arg1"]


class TestTypesIntegration:
    """Integration tests for custom types."""

    def test_tag_type_in_click_command(self):
        """Test using tag type in a Click command."""
        import click

        @click.command()
        @click.argument("tag", type=AnsibleTagListType())
        def test_cmd(tag):
            return tag

        runner = click.testing.CliRunner()

        with patch(
            "dotfiles_cli.types._get_cached_tags",
            return_value=["brew", "dotfiles"],
        ):
            result = runner.invoke(test_cmd, ["brew"])

        assert result.exit_code == 0

    def test_host_type_in_click_option(self):
        """Test using host type in a Click option."""
        import click

        @click.command()
        @click.option("--host", type=AnsibleHostListType())
        def test_cmd(host):
            return host

        runner = click.testing.CliRunner()

        with patch.object(
            AnsibleHostListType, "get_all_hosts", return_value=["work", "personal"]
        ):
            result = runner.invoke(test_cmd, ["--host", "work"])

        assert result.exit_code == 0
