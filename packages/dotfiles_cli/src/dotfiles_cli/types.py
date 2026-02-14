"""Custom Click types for Ansible integration."""

from __future__ import annotations

import importlib
import itertools
import json
import os
import re
from functools import lru_cache
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Optional

import click
from click import Context, Parameter
from click.shell_completion import CompletionItem

from .constants import DOTFILES_DIR

# Cache directory for storing computed values
CACHE_DIR = Path(DOTFILES_DIR) / ".cache"
TAGS_CACHE_FILE = CACHE_DIR / "ansible_tags.json"


class AnsibleTagListType(click.Choice):
    """Click type for Ansible playbook tags with dynamic completion."""

    name = "Ansible Tag"
    envvar_list_splitter: str = ","

    def __init__(self):
        super().__init__([], case_sensitive=True)

    @property
    def choices(self) -> list[str]:
        """Get all supported tags from the playbook."""
        return self._get_all_supported_tags()

    @choices.setter
    def choices(self, choices: list[str]) -> None:
        pass

    @staticmethod
    def _get_all_supported_tags() -> list[str]:
        """Get all supported tags from the playbook with file-based caching."""
        return _get_cached_tags()

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


def _get_playbook_mtime() -> float:
    """Get the max modification time of playbook.yml and roles directory."""
    playbook_path = Path(DOTFILES_DIR) / "playbook.yml"
    roles_path = Path(DOTFILES_DIR) / "roles"

    mtime = playbook_path.stat().st_mtime if playbook_path.exists() else 0

    # Also check roles directory for any changes
    if roles_path.exists():
        for root, _, files in os.walk(roles_path):
            for f in files:
                if f.endswith((".yml", ".yaml")):
                    file_path = Path(root) / f
                    mtime = max(mtime, file_path.stat().st_mtime)

    return mtime


def _load_tags_cache() -> tuple[list[str], float] | None:
    """Load tags from cache file. Returns (tags, cached_mtime) or None if cache invalid."""
    if not TAGS_CACHE_FILE.exists():
        return None

    try:
        with open(TAGS_CACHE_FILE) as f:
            data = json.load(f)
            return data.get("tags", []), data.get("mtime", 0)
    except (json.JSONDecodeError, OSError):
        return None


def _save_tags_cache(tags: list[str], mtime: float) -> None:
    """Save tags to cache file."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(TAGS_CACHE_FILE, "w") as f:
        json.dump({"tags": tags, "mtime": mtime}, f)


def _fetch_tags_from_ansible() -> list[str]:
    """Fetch tags by running ansible-playbook --list-tags."""
    import ansible_runner

    all_tags = {"all"}
    excluded_tags = {"never", "always"}
    with TemporaryDirectory() as tmpdir:
        rc = ansible_runner.RunnerConfig(
            private_data_dir=tmpdir,
            project_dir=DOTFILES_DIR,
            envvars={"ANSIBLE_CONFIG": f"{DOTFILES_DIR}/ansible.cfg"},
            playbook="playbook.yml",
            cmdline="--list-tags",
            quiet=True,
        )
        rc.prepare()
        r = ansible_runner.Runner(config=rc)
        r.run()
        stdout = r.stdout.read()
        # Match all occurrence of TAGS: [tag1, complex-tag, another_tag]
        for match in re.findall(r"TAGS: \[([^\]]+)\]", stdout):
            all_tags.update(match.split(", "))
    return sorted(list(all_tags - excluded_tags))


def _get_cached_tags() -> list[str]:
    """Get tags from cache if valid, otherwise fetch and cache."""
    current_mtime = _get_playbook_mtime()

    # Try to use cached tags
    cache_result = _load_tags_cache()
    if cache_result is not None:
        cached_tags, cached_mtime = cache_result
        if cached_mtime >= current_mtime and cached_tags:
            return cached_tags

    # Cache miss or stale - fetch fresh tags
    tags = _fetch_tags_from_ansible()
    _save_tags_cache(tags, current_mtime)
    return tags


class AnsibleHostListType(click.Choice):
    """Click type for Ansible hosts with dynamic completion."""

    name = "Ansible Host"
    envvar_list_splitter: str = ","

    def __init__(self):
        super().__init__([], case_sensitive=True)

    @property
    @lru_cache()
    def choices(self) -> list[str]:
        """Get all supported hosts from inventory."""
        return self.get_all_hosts()

    @choices.setter
    def choices(self, choices: list[str]) -> None:
        pass

    @staticmethod
    def get_all_hosts() -> list[str]:
        """Get all supported hosts from inventory (uses ansible.cfg settings)."""
        import ansible_runner

        excluded_hosts = {"common", "all", "ungrouped"}

        try:
            with TemporaryDirectory() as tmpdir:
                result, _ = ansible_runner.interface.get_inventory(
                    action="list",
                    private_data_dir=tmpdir,
                    project_dir=DOTFILES_DIR,
                    envvars={"ANSIBLE_CONFIG": f"{DOTFILES_DIR}/ansible.cfg"},
                    response_format="json",
                    quiet=True,
                )
            if not isinstance(result, dict):
                # Fallback if inventory parsing fails (e.g., vault issues)
                return ["work", "personal"]
            all_groups = result.get("all", {}).get("children", [])
            all_hosts = set(
                itertools.chain.from_iterable(
                    [result.get(group, {}).get("hosts", []) for group in all_groups]
                    + [all_groups]
                )
            )
            return sorted(list(all_hosts - excluded_hosts))
        except Exception:
            # Fallback to known hosts if parsing fails
            return ["work", "personal"]

    def shell_complete(self, ctx, param, incomplete):
        """Provide shell completion for hosts."""
        return [CompletionItem(host) for host in self.get_all_hosts()]


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

    def __init__(self, *args: Any, lazy_commands: dict | None = None, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._lazy_commands: dict[str, dict] = lazy_commands or {}
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
ansible_tags_type = AnsibleTagListType()
ansible_hosts_type = AnsibleHostListType()
