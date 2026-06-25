"""dotfiles deploy — pyinfra site.

Run:  pyinfra deploy/inventory.py deploy/site.py
Dry:  pyinfra deploy/inventory.py deploy/site.py --dry

Tags are selected via the DOTFILES_TAGS env var (comma-separated) or 'all'.
"""

from __future__ import annotations

from pyinfra import host, logger

from dotfiles_pyinfra.deploys import (
    agent_instructions as agent_instructions_deploy,
    brew as brew_deploy,
    chsh as chsh_deploy,
    claude_plugins as claude_plugins_deploy,
    composer as composer_deploy,
    cursor_cli as cursor_cli_deploy,
    dotfiles as dotfiles_deploy,
    gem as gem_deploy,
    gh_extensions as gh_extensions_deploy,
    gh_repos as gh_repos_deploy,
    gitconfig as gitconfig_deploy,
    github_binary as github_binary_deploy,
    json_config as json_config_deploy,
    mas as mas_deploy,
    mcp_servers as mcp_servers_deploy,
    npm as npm_deploy,
    pip as pip_deploy,
    pipx as pipx_deploy,
    ssh_config as ssh_config_deploy,
    yaml_config as yaml_config_deploy,
)
from dotfiles_pyinfra.profile_deploys import run_profile_deploys
from dotfiles_pyinfra.tags import tag_selected

# ---------------------------------------------------------------------------
# Read baked-in data from inventory (everything nested under host.data.dotfiles)
# ---------------------------------------------------------------------------
_d = host.data.dotfiles
tags: set[str] = _d["tags"]
merged_all = _d["merged_all"]
merged_selected = _d["merged_selected"]
enabled_profiles = _d["enabled_profiles"]
selected_profiles = _d["selected_profiles"]
dotfiles_dir = _d["dotfiles_dir"]

logger.info(
    "dotfiles deploy starting — "
    f"tags={sorted(tags)}, "
    f"profiles={[p.name for p in selected_profiles]}"
)

# ---------------------------------------------------------------------------
# Phase 1a: Homebrew — taps, formulas, casks (merged_selected: safe subset)
# ---------------------------------------------------------------------------
if tag_selected("brew", tags) or tag_selected("cask", tags):
    brew_deploy.deploy(merged=merged_selected)

# ---------------------------------------------------------------------------
# Phase 1b: Dotfiles symlinks (additive — selected profiles own their files)
# ---------------------------------------------------------------------------
if tag_selected("dotfiles", tags):
    dotfiles_deploy.deploy(profiles=selected_profiles, dotfiles_dir=dotfiles_dir)

# ---------------------------------------------------------------------------
# Phase 1c: Package managers (merged_selected: safe to install a subset)
# ---------------------------------------------------------------------------
if tag_selected("npm", tags):
    npm_deploy.deploy(merged=merged_selected)

if tag_selected("gem", tags):
    gem_deploy.deploy(merged=merged_selected)

if tag_selected("pip", tags) or tag_selected("python", tags):
    pip_deploy.deploy(merged=merged_selected)

if tag_selected("pipx", tags) or tag_selected("python", tags):
    pipx_deploy.deploy(merged=merged_selected)

if tag_selected("composer", tags):
    composer_deploy.deploy(merged=merged_selected)

# ---------------------------------------------------------------------------
# Phase 1d: Mac App Store (merged_selected; errors written to .cache/)
# ---------------------------------------------------------------------------
if tag_selected("mas", tags):
    mas_deploy.deploy(merged=merged_selected, dotfiles_dir=dotfiles_dir)

# ---------------------------------------------------------------------------
# Phase 1e: GitHub CLI extensions and repos (merged_selected)
# ---------------------------------------------------------------------------
if tag_selected("gh-extensions", tags):
    gh_extensions_deploy.deploy(merged=merged_selected)

if tag_selected("gh-repos", tags):
    gh_repos_deploy.deploy(merged=merged_selected)

# ---------------------------------------------------------------------------
# Phase 2a: Config-merge / destructive writes — use merged_ALL so a -p subset
#           never truncates shared config files.
# ---------------------------------------------------------------------------
if tag_selected("gitconfig", tags):
    gitconfig_deploy.deploy(profiles=enabled_profiles, dotfiles_dir=dotfiles_dir)

if tag_selected("ssh", tags):
    ssh_config_deploy.deploy(merged=merged_all)

if tag_selected("json-config", tags) or tag_selected("coding-agents", tags):
    json_config_deploy.deploy(merged=merged_all)

if tag_selected("yaml-config", tags):
    yaml_config_deploy.deploy(merged=merged_all)

if tag_selected("agent-instructions", tags) or tag_selected("coding-agents", tags):
    agent_instructions_deploy.deploy(profiles=enabled_profiles, merged=merged_all)

if tag_selected("mcp-servers", tags):
    mcp_servers_deploy.deploy(merged=merged_all, dotfiles_dir=dotfiles_dir)

# ---------------------------------------------------------------------------
# Phase 2b: Tool-specific config / install
# ---------------------------------------------------------------------------
if tag_selected("cursor-cli", tags):
    cursor_cli_deploy.deploy(merged=merged_all)

if tag_selected("claude-plugins", tags) or tag_selected("coding-agents", tags):
    claude_plugins_deploy.deploy(merged=merged_all)

if tag_selected("chsh", tags):
    chsh_deploy.deploy(merged=merged_all)

if tag_selected("github-binary", tags):
    github_binary_deploy.deploy(merged=merged_all)

# ---------------------------------------------------------------------------
# Phase 3: Per-profile custom deploys (profiles/{name}/deploy.py)
# ---------------------------------------------------------------------------
run_profile_deploys(profiles=selected_profiles, tags=tags, dotfiles_dir=dotfiles_dir)
