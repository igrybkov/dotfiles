"""Main CLI application definition."""

from __future__ import annotations

import click

from .types import LazyAliasedGroup

# Lazy command registry: commands are only imported when actually invoked.
# For --help, only the "help" strings below are used (no module imports).
_COMMANDS = {
    "cache": {
        "import_path": "dotfiles_cli.commands.cache:cache",
        "help": "Manage dotfiles cache markers.",
    },
    "completion": {
        "import_path": "dotfiles_cli.commands.completion:completion",
        "help": "Generate completion script for the specified shell.",
    },
    "config": {
        "import_path": "dotfiles_cli.commands.config:config",
        "help": "Configure dotfiles profiles and settings.",
    },
    "edit": {
        "import_path": "dotfiles_cli.commands.edit:edit",
        "help": "Edit the dotfiles.",
    },
    "install": {
        "import_path": "dotfiles_cli.commands.install:install",
        "help": "Run ansible playbook to install dotfiles.",
        "aliases": ["run"],
    },
    "link": {
        "import_path": "dotfiles_cli.commands.link:link",
        "help": "Symlink dotfiles CLI to ~/.local/bin for easy access.",
    },
    "profile": {
        "import_path": "dotfiles_cli.commands.profile:profile",
        "help": "Manage dotfiles profiles.",
    },
    "pull": {
        "import_path": "dotfiles_cli.commands.git:pull",
        "help": "Pull the latest changes from the remote repository.",
    },
    "push": {
        "import_path": "dotfiles_cli.commands.git:push",
        "help": "Push the latest changes to the remote repository.",
    },
    "secret": {
        "import_path": "dotfiles_cli.commands.secrets:secret",
        "help": "Manage encrypted secrets for MCP servers and other sensitive data.",
    },
    "sync": {
        "import_path": "dotfiles_cli.commands.git:sync",
        "help": "Pull the latest changes, upgrade dependencies, and then push local"
        " changes.",
    },
    "upgrade": {
        "import_path": "dotfiles_cli.commands.upgrade:upgrade",
        "help": "Upgrade all dependencies including Ansible roles/collections,"
        " mise, and uv.",
    },
    # Legacy alias (hidden), use `dotfiles profile bootstrap` instead
    "bootstrap-profile": {
        "import_path": "dotfiles_cli.commands.profile:bootstrap_profile",
        "help": "[DEPRECATED] Use 'dotfiles profile bootstrap' instead.",
        "hidden": True,
    },
}


@click.group(cls=LazyAliasedGroup, lazy_commands=_COMMANDS)
def cli():
    """Dotfiles management CLI.

    Manage your dotfiles, profiles, and development environment with Ansible.
    """
    pass
