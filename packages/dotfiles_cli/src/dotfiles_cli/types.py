"""Custom Click types for pyinfra integration."""

from __future__ import annotations

import importlib
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import click
from click import Context, Parameter
from click.shell_completion import CompletionItem

from .constants import DOTFILES_DIR


class PyinfraTagListType(click.Choice[str]):
    """Click type for pyinfra deploy tags — reads from static registry."""

    name = "Tag"
    envvar_list_splitter: str | None = ","

    def __init__(self):
        super().__init__([], case_sensitive=True)

    @property
    def choices(self) -> list[str]:
        """Get all supported tags from the pyinfra tag registry."""
        return self._get_all_supported_tags()

    @choices.setter
    def choices(self, choices: list[str]) -> None:
        pass

    @staticmethod
    def _get_all_supported_tags() -> list[str]:
        """Get all supported tags from the static pyinfra registry."""
        from dotfiles_pyinfra.tags import ALL_SELECTOR, ALL_TAGS

        return sorted([ALL_SELECTOR] + list(ALL_TAGS))

    def convert(
        self, value: Any, param: Optional["Parameter"], ctx: Optional["Context"]
    ) -> Any:
        """Convert and validate the tag value."""
        # For single values, validate using parent class
        if isinstance(value, str):
            return super().convert(value, param, ctx)
        # For tuples/lists (when nargs=-1), validate each value
        if isinstance(value, (tuple, list)):
            return [super().convert(tag, param, ctx) for tag in value]
        return super().convert(value, param, ctx)

    def shell_complete(self, ctx, param, incomplete):
        """Provide shell completion for tags."""
        return [CompletionItem(tag) for tag in self._get_all_supported_tags()]


class ProfileListType(click.Choice[str]):
    """Click type for profile names — reads from profile discovery."""

    name = "Profile"
    envvar_list_splitter: str | None = ","

    def __init__(self):
        super().__init__([], case_sensitive=True)

    @property
    @lru_cache()
    def choices(self) -> list[str]:
        """Get all profile names from on-disk discovery."""
        return self.get_all_profiles()

    @choices.setter
    def choices(self, choices: list[str]) -> None:
        pass

    @staticmethod
    def get_all_profiles() -> list[str]:
        """Discover all profile names on disk."""
        from dotfiles_profile_discovery import discover_profiles

        profiles = discover_profiles(Path(DOTFILES_DIR) / "profiles")
        return sorted(p.name for p in profiles)

    def shell_complete(self, ctx, param, incomplete):
        """Provide shell completion for profile names."""
        return [CompletionItem(p) for p in self.get_all_profiles()]


class AliasedGroup(click.Group):
    """Click group that supports command aliases and prefix matching."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._commands_aliases: dict[str, list[str]] = {}
        self._alias_map: dict[str, str] = {}

    def add_command(self, *args: Any, **kwargs: Any) -> None:
        aliases = kwargs.pop("aliases", [])
        super().add_command(*args, **kwargs)
        if aliases:
            cmd = args[0]
            name = args[1] if len(args) > 1 else None
            name = name or cmd.name
            if name is None:
                raise TypeError("Command has no name.")
            self._commands_aliases[name] = aliases
            for alias in aliases:
                self._alias_map[alias] = name

    def get_command(self, ctx, cmd_name):
        """Get command by name, supporting prefix matching and aliases."""
        # Try alias resolution first
        cmd_name = self._alias_map.get(cmd_name, cmd_name)
        rv = click.Group.get_command(self, ctx, cmd_name)
        if rv is not None:
            return rv
        # Try prefix matching
        matches = [x for x in self.list_commands(ctx) if x.startswith(cmd_name)]
        if len(matches) == 1:
            return click.Group.get_command(self, ctx, matches[0])
        elif len(matches) > 1:
            ctx.fail(f"Too many matches: {', '.join(sorted(matches))}")
        return None

    def resolve_command(self, ctx, args):
        """Resolve command, always returning the full command name."""
        _, cmd, args = super().resolve_command(ctx, args)
        assert cmd is not None
        return cmd.name, cmd, args

    def format_commands(self, ctx, formatter):
        """Format command listing with alias display."""
        rows = []
        for sub_command in self.list_commands(ctx):
            cmd = self.get_command(ctx, sub_command)
            if cmd is None:
                continue
            if getattr(cmd, "hidden", False):
                continue
            if sub_command in self._commands_aliases:
                aliases = ",".join(sorted(self._commands_aliases[sub_command]))
                sub_command = f"{sub_command} ({aliases})"
            help_text = cmd.get_short_help_str(limit=formatter.width - 6)
            rows.append((sub_command, help_text))
        if rows:
            with formatter.section("Commands"):
                formatter.write_dl(rows)


class LazyAliasedGroup(click.Group):
    """Click group with lazy command loading, alias support, and prefix matching.

    Commands are specified as a dict of metadata and only imported when invoked.
    For --help, only command names and pre-defined help strings are used.
    """

    def __init__(
        self, *args: Any, lazy_commands: dict[str, Any] | None = None, **kwargs: Any
    ):
        super().__init__(*args, **kwargs)
        self._lazy_commands: dict[str, Any] = lazy_commands or {}
        # Build alias -> canonical name mapping
        self._alias_map: dict[str, str] = {}
        for name, info in self._lazy_commands.items():
            for alias in info.get("aliases", []):
                self._alias_map[alias] = name

    def list_commands(self, ctx) -> list[str]:
        return sorted(self._lazy_commands.keys())

    def _resolve_name(self, ctx, cmd_name: str) -> str | None:
        """Resolve a command name through aliases and prefix matching."""
        # Try alias resolution
        cmd_name = self._alias_map.get(cmd_name, cmd_name)
        if cmd_name in self._lazy_commands:
            return cmd_name
        # Try prefix matching
        matches = [n for n in self._lazy_commands if n.startswith(cmd_name)]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            ctx.fail(f"Too many matches: {', '.join(sorted(matches))}")
        return None

    def get_command(self, ctx, cmd_name) -> click.Command | None:
        """Lazily import and return the command."""
        resolved = self._resolve_name(ctx, cmd_name)
        if resolved is None:
            return None
        info = self._lazy_commands[resolved]
        mod_path, attr = info["import_path"].rsplit(":", 1)
        mod = importlib.import_module(mod_path)
        return getattr(mod, attr)

    def resolve_command(self, ctx, args):
        """Resolve command, always returning the full command name."""
        _, cmd, args = super().resolve_command(ctx, args)
        assert cmd is not None
        return cmd.name, cmd, args

    def format_commands(self, ctx, formatter):
        """Format command listing using pre-defined help strings (no imports)."""
        rows = []
        for name in self.list_commands(ctx):
            info = self._lazy_commands[name]
            if info.get("hidden", False):
                continue
            display_name = name
            aliases = info.get("aliases", [])
            if aliases:
                display_name = f"{name} ({','.join(sorted(aliases))})"
            rows.append((display_name, info.get("help", "")))
        if rows:
            with formatter.section("Commands"):
                formatter.write_dl(rows)


# Singleton instances for use in commands
ansible_tags_type = PyinfraTagListType()
ansible_hosts_type = ProfileListType()
