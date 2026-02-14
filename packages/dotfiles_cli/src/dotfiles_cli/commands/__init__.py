"""CLI commands for the dotfiles tool."""

from .cache import cache
from .git import pull, push, sync
from .install import install
from .upgrade import upgrade
from .edit import edit
from .config import config
from .profile import profile, bootstrap_profile
from .secrets import secret
from .completion import completion
from .link import link

__all__ = [
    "cache",
    "pull",
    "push",
    "sync",
    "install",
    "upgrade",
    "edit",
    "config",
    "profile",
    "bootstrap_profile",  # Legacy alias, kept for backward compatibility
    "secret",
    "completion",
    "link",
]
