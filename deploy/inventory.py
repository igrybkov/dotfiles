"""pyinfra inventory — one local host, data computed from env vars.

Environment variables consumed:
  DOTFILES_SELECTED_PROFILES  comma-separated list of -p selected profile names
  DOTFILES_ENABLED_PROFILES   comma-separated list of all enabled profile names
  DOTFILES_TAGS               comma-separated list of selected tags (or 'all')
  SOPS_AGE_KEY                age private key for secret decryption (Phase 3)

Sudo: the CLI validates the password once up front and then keeps the OS sudo
ticket warm with a background `sudo -n -v` refresher for the run's duration
(see dotfiles_cli.utils.sudo.SudoKeepAlive) — the password itself is never
passed to pyinfra, so `_sudo=True` operations rely on the ticket cache alone.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotfiles_profile_discovery import discover_profiles
from dotfiles_pyinfra.merge import lists_mergeby, merge_var, sort_profiles
from dotfiles_pyinfra.tags import ALL_SELECTOR

# ---------------------------------------------------------------------------
# Resolve profiles
# ---------------------------------------------------------------------------
DOTFILES_DIR = Path(__file__).parent.parent

_selected_names_raw = os.environ.get("DOTFILES_SELECTED_PROFILES", "")
_enabled_names_raw = os.environ.get("DOTFILES_ENABLED_PROFILES", "")
_tags_raw = os.environ.get("DOTFILES_TAGS", ALL_SELECTOR)

_selected_names: list[str] = [n for n in _selected_names_raw.split(",") if n]
_enabled_names: list[str] = [n for n in _enabled_names_raw.split(",") if n]
_selected_tags: set[str] = set(_tags_raw.split(",")) if _tags_raw else {ALL_SELECTOR}

# Discover all profiles on disk.
# Prefixed with _ so pyinfra doesn't scan these as candidate host groups.
_all_discovered = sort_profiles(discover_profiles(DOTFILES_DIR / "profiles"))

# Active profile sets
if _enabled_names:
    _enabled_profiles = [p for p in _all_discovered if p.name in set(_enabled_names)]
else:
    _enabled_profiles = list(_all_discovered)

if _selected_names:
    _selected_profiles = [
        p for p in _enabled_profiles if p.name in set(_selected_names)
    ]
else:
    _selected_profiles = list(_enabled_profiles)

# ---------------------------------------------------------------------------
# Build merged data — two contexts
# ---------------------------------------------------------------------------
# merged_all: every enabled profile (for destructive config-file writes)
# merged_selected: only the -p subset (for safe package installs)


def _build_merged(profiles):
    """Merge all known config vars for a set of profiles."""
    # Lists (safe to install a subset) — use lists_mergeby for dedup
    brew_taps = lists_mergeby(merge_var(profiles, "brew_taps"), "name")
    brew_packages = lists_mergeby(merge_var(profiles, "brew_packages"), "name")
    cask_packages = lists_mergeby(merge_var(profiles, "cask_packages"), "name")
    mas_packages = lists_mergeby(merge_var(profiles, "mas_packages"), "id")
    npm_packages = lists_mergeby(merge_var(profiles, "npm_packages"), "name")
    pip_packages = lists_mergeby(merge_var(profiles, "pip_packages"), "name")
    # Resolve relative paths in pipx_packages against each profile's directory.
    _pipx_raw: list[list[dict[str, Any]]] = []
    for p in profiles:
        profile_pkgs = []
        for pkg in p.config.get("pipx_packages", []):
            if isinstance(pkg, dict) and "path" in pkg:
                raw = pkg["path"]
                if not Path(raw).is_absolute():
                    pkg = {**pkg, "path": str(p.path / raw)}
            profile_pkgs.append(pkg)
        if profile_pkgs:
            _pipx_raw.append(profile_pkgs)
    pipx_packages = lists_mergeby(_pipx_raw, "name")
    gem_packages = lists_mergeby(merge_var(profiles, "gem_packages"), "name")
    composer_packages = lists_mergeby(merge_var(profiles, "composer_packages"), "name")
    gh_extensions = lists_mergeby(merge_var(profiles, "gh_extensions"), "name")
    gh_repos = lists_mergeby(merge_var(profiles, "gh_repos"), "repo")
    ssh_client_config = lists_mergeby(merge_var(profiles, "ssh_client_config"), "host")
    json_configs = [item for sub in merge_var(profiles, "json_configs") for item in sub]
    yaml_configs = [item for sub in merge_var(profiles, "yaml_configs") for item in sub]
    # MCP servers: inject _profile per entry so merge_mcp_servers can route secrets
    mcp_servers: list[dict[str, Any]] = []
    for p in profiles:
        for entry in p.config.get("mcp_servers", []):
            if isinstance(entry, dict):
                mcp_servers.append({**entry, "_profile": p.name})

    # Claude plugins / marketplaces
    claude_plugins = lists_mergeby(merge_var(profiles, "claude_plugins"), "name")
    claude_plugin_marketplaces = lists_mergeby(
        merge_var(profiles, "claude_plugin_marketplaces"), "name"
    )

    # Scalars
    brew_upgrade_all = merge_var(profiles, "brew_upgrade_all", "any", default=False)
    mas_upgrade_all = merge_var(profiles, "mas_upgrade_all", "any", default=False)
    install_cursor_cli = merge_var(profiles, "install_cursor_cli", "any", default=False)
    gh_repos_default_dest = merge_var(
        profiles, "gh_repos_default_dest", "last", default="~/src"
    )

    # Multi-key dicts (later profile overrides)
    skill_folders = merge_var(profiles, "skill_folders", "dict")
    agent_folders = merge_var(profiles, "agent_folders", "dict")

    # Agent instruction destinations: list of {path, frontmatter?} dicts, deduped by path
    agent_instructions_destinations = lists_mergeby(
        merge_var(profiles, "agent_instructions_destinations"), "path"
    )

    # SSH raw blocks (just flatten — no dedup key)
    ssh_client_config_block = [
        block
        for sub in merge_var(profiles, "ssh_client_config_block")
        for block in (sub if isinstance(sub, list) else [sub])
    ]

    return {
        "brew_taps": brew_taps,
        "brew_packages": brew_packages,
        "cask_packages": cask_packages,
        "mas_packages": mas_packages,
        "npm_packages": npm_packages,
        "pip_packages": pip_packages,
        "pipx_packages": pipx_packages,
        "gem_packages": gem_packages,
        "composer_packages": composer_packages,
        "gh_extensions": gh_extensions,
        "gh_repos": gh_repos,
        "gh_repos_default_dest": gh_repos_default_dest,
        "ssh_client_config": ssh_client_config,
        "ssh_client_config_block": ssh_client_config_block,
        "json_configs": json_configs,
        "yaml_configs": yaml_configs,
        "mcp_servers": mcp_servers,
        "brew_upgrade_all": brew_upgrade_all,
        "mas_upgrade_all": mas_upgrade_all,
        "install_cursor_cli": install_cursor_cli,
        "skill_folders": skill_folders,
        "agent_folders": agent_folders,
        "agent_instructions_destinations": agent_instructions_destinations,
        "claude_plugins": claude_plugins,
        "claude_plugin_marketplaces": claude_plugin_marketplaces,
    }


merged_all = _build_merged(_enabled_profiles)
merged_selected = _build_merged(_selected_profiles)

# ---------------------------------------------------------------------------
# pyinfra inventory: one @local host with all the computed data
# ---------------------------------------------------------------------------
hosts = [
    (
        "@local",
        {
            # All deploy data nested under one key so pyinfra doesn't try to
            # interpret ProfileInfo lists as host groups.
            "dotfiles": {
                # Profile sets (ProfileInfo objects)
                "enabled_profiles": _enabled_profiles,
                "selected_profiles": _selected_profiles,
                "all_discovered_profiles": _all_discovered,
                # Merged data
                "merged_all": merged_all,
                "merged_selected": merged_selected,
                # Tag selection
                "tags": _selected_tags,
                # Paths
                "dotfiles_dir": DOTFILES_DIR,
                # sops age key (Phase 3, may be None until then)
                "sops_age_key": os.environ.get("SOPS_AGE_KEY"),
            },
        },
    )
]
