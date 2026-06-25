"""Static tag registry — the pyinfra equivalent of ansible-playbook --list-tags."""

from __future__ import annotations

# Every tag the deploy understands.
# Tags select which operations run; use --tags / DOTFILES_TAGS env var.
ALL_TAGS: tuple[str, ...] = (
    "always",  # runs regardless of tag selection
    "brew",  # Homebrew packages, casks, taps
    "cask",  # Homebrew casks only
    "fonts",  # font files copy
    "dotfiles",  # dotfile symlinks
    "gitconfig",  # git conf.d + gitignore + allowed-signers
    "ssh",  # SSH client config
    "mas",  # Mac App Store apps
    "npm",  # npm global packages
    "pip",  # pip packages
    "pipx",  # pipx/uv-tool packages
    "gem",  # Ruby gems
    "composer",  # PHP Composer global packages
    "mcp-servers",  # MCP server config (secrets-sensitive)
    "gh-extensions",  # GitHub CLI extensions
    "gh-repos",  # GitHub repo clones
    "json-config",  # JSON config file merges (claude settings, etc.)
    "yaml-config",  # YAML config file merges
    "agent-instructions",  # CLAUDE.md / cursor instruction assembly
    "cursor-cli",  # cursor CLI install/upgrade
    "coding-agents",  # alias for json-config + agent-instructions
    "docker",  # docker system prune
    "chsh",  # change default shell
    "mise",  # mise install (always runs in preamble too)
    "macos",  # macOS system defaults (osx_defaults)
    "python",  # alias for pip + pipx
    "claude-plugins",  # Claude Code plugin marketplace sync
    "github-binary",  # GitHub release binary downloads
)

# Tags that imply ALL tags should run (same semantics as Ansible's "all")
ALL_SELECTOR = "all"

# Tags that write config files — must aggregate from ALL enabled profiles,
# not just the -p selected subset (mirrors all_profiles=True in the old lookup).
DESTRUCTIVE_CONFIG_TAGS: frozenset[str] = frozenset(
    {
        "gitconfig",
        "ssh",
        "mcp-servers",
        "json-config",
        "yaml-config",
        "agent-instructions",
    }
)

# Tags requiring sudo (password prompted before pyinfra invocation)
# macos: the Touch-ID-for-sudo write to /etc/pam.d/sudo_local needs root.
SUDO_TAGS: frozenset[str] = frozenset({"mas", "chsh", "brew", "cask", "macos"})

# Tags requiring vault/sops secret access
VAULT_TAGS: frozenset[str] = frozenset({"mcp-servers"})


def tag_selected(tag: str, selected: set[str]) -> bool:
    """Return True if `tag` should run given the selected tag set."""
    if ALL_SELECTOR in selected:
        return True
    if tag == "always":
        return True
    # Alias expansion
    if tag in ("pip", "pipx") and "python" in selected:
        return True
    if (
        tag in ("json-config", "agent-instructions", "github-binary")
        and "coding-agents" in selected
    ):
        return True
    return tag in selected


def validate_tags(requested: list[str]) -> list[str]:
    """Return list of invalid tags (not in ALL_TAGS and not 'all')."""
    known = set(ALL_TAGS) | {ALL_SELECTOR}
    return [t for t in requested if t not in known]
