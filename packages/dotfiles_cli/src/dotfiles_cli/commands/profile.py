"""Profile management commands."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from ruamel.yaml import YAML

from ..constants import DOTFILES_DIR
from ..profiles import (
    get_active_profiles,
)
from ..profiles.discovery import _get_profiles, get_profile_path

console = Console()


@click.group()
def profile():
    """Manage dotfiles profiles.

    Profiles organize your dotfiles, packages, and configurations by context
    (e.g., work, personal, company-specific).

    Supports up to three levels:
    - profiles/{name}/ (single level)
    - profiles/{repo}/{name}/ (nested, creates profile named repo-name)
    - profiles/{dir}/{repo}/{name}/ (deep nested, creates profile named dir-repo-name)
    """
    pass


@profile.command("list")
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    default=False,
    help="Only show profile names, one per line",
)
def profile_list(quiet: bool):
    """List all available profiles with their status and priority.

    Shows profiles in execution order (by priority, then alphabetically).
    Active profiles are marked with a checkmark.
    """
    profiles = _get_profiles()

    if not profiles:
        if quiet:
            return 0
        console.print("[yellow]No profiles found in profiles/ directory[/yellow]")
        return 0

    # Get active profiles from current configuration
    all_profile_names = [p.name for p in profiles]
    active_selection = get_active_profiles()
    active_profiles = set(active_selection.resolve(all_profile_names))

    # Sort profiles by priority, then alphabetically (execution order)
    profiles.sort(key=lambda x: (x.priority, x.name))

    if quiet:
        for p in profiles:
            click.echo(p.name)
        return 0

    # Build rich table
    table = Table(title="Profiles", show_header=True, header_style="bold")
    table.add_column("Status", justify="center", width=6)
    table.add_column("Profile", style="cyan")
    table.add_column("Path", style="dim")
    table.add_column("Priority", justify="right")
    table.add_column("Notes", style="dim")

    for p in profiles:
        is_active = p.name in active_profiles
        status = "[green]✓[/green]" if is_active else "[dim]○[/dim]"

        # Show relative path for nested profiles
        path_display = p.relative_path if "/" in p.relative_path else ""

        # Add notes for special profiles
        notes = ""
        if p.name == "common":
            notes = "base profile"
        elif p.priority == 200 and p.name in ("work", "personal"):
            notes = "built-in"
        elif p.priority != 1000:
            notes = "custom priority"

        table.add_row(status, p.name, path_display, str(p.priority), notes)

    console.print(table)

    # Show summary
    active_count = len(active_profiles)
    total_count = len(profiles)
    console.print(f"\n[dim]{active_count}/{total_count} profiles active[/dim]")

    if active_profiles:
        ordered_active = [p.name for p in profiles if p.name in active_profiles]
        console.print(f"[dim]Execution order: {' → '.join(ordered_active)}[/dim]")

    return 0


def _migrate_profile_config(
    config_file: Path, profile_name: str, dry_run: bool
) -> bool:
    """Migrate a single profile config from host to profile structure.

    Returns True if migration was performed, False if no changes needed.
    Preserves all comments in the YAML file.
    """
    from ruamel.yaml.comments import CommentedMap

    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)

    with open(config_file, "r") as f:
        data = yaml.load(f)

    if data is None:
        data = CommentedMap()

    # Check if already migrated or has no host node
    if "profile" in data:
        return False
    if "host" not in data:
        return False

    # Get host config and its position/comments
    host_config = data["host"]

    # Build new profile node
    profile_node = CommentedMap()

    # Set profile.name = directory name by default
    profile_node["name"] = profile_name

    # Map host.name -> profile.host (if it was different from default)
    old_host_name = host_config.get("name") if host_config else None
    if old_host_name and old_host_name != f"{profile_name}-profile":
        profile_node["host"] = old_host_name

    # Map host.priority -> profile.priority
    if host_config and "priority" in host_config:
        profile_node["priority"] = host_config["priority"]

    # Map host.connection -> profile.connection (if present)
    if host_config and "connection" in host_config:
        profile_node["connection"] = host_config["connection"]

    # Replace 'host' with 'profile' in place to preserve document order and comments
    keys = list(data.keys())

    # Remove 'host' key
    del data["host"]

    # Insert 'profile' at the same position
    # We need to rebuild the order since CommentedMap doesn't support insert
    new_data = CommentedMap()

    # Preserve start comment (document-level comments)
    if hasattr(data, "ca"):
        new_data.ca.comment = data.ca.comment

    for key in keys:
        if key == "host":
            new_data["profile"] = profile_node
        elif key in data:
            new_data[key] = data[key]
            # Copy any comments for this key
            if hasattr(data, "ca") and data.ca.items.get(key):
                new_data.ca.items[key] = data.ca.items[key]

    if dry_run:
        console.print(f"  [yellow]Would migrate[/yellow] {config_file}")
        return True

    with open(config_file, "w") as f:
        yaml.dump(new_data, f)

    return True


@profile.command("migrate")
@click.argument("profile_names", nargs=-1, required=False)
@click.option(
    "--all",
    "migrate_all",
    is_flag=True,
    default=False,
    help="Migrate all profiles",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Show what would be changed without making changes",
)
def profile_migrate(profile_names: tuple[str, ...], migrate_all: bool, dry_run: bool):
    """Migrate profile configs from old 'host' structure to new 'profile' structure.

    Old structure:

    \b
        host:
          name: my-profile
          priority: 200

    New structure:

    \b
        profile:
          name: my-profile
          host: my-profile  # optional, if different from {name}-profile
          priority: 200     # optional

    Examples:

    \b
        dotfiles profile migrate --all           # Migrate all profiles
        dotfiles profile migrate common personal # Migrate specific profiles
        dotfiles profile migrate --all --dry-run # Preview changes
    """
    if not profile_names and not migrate_all:
        console.print(
            "[red]Error:[/red] Specify profile names or use --all to migrate all profiles"
        )
        return 1

    # Get profiles to migrate
    if migrate_all:
        profiles = _get_profiles()
        profiles_to_migrate = [(p.name, p.path) for p in profiles]
    else:
        profiles_to_migrate = []
        for name in profile_names:
            path = get_profile_path(name)
            if path:
                profiles_to_migrate.append((name, path))
            else:
                console.print(f"  [dim]Skipping {name} (not found)[/dim]")

    if not profiles_to_migrate:
        console.print("[yellow]No profiles found to migrate[/yellow]")
        return 0

    migrated_count = 0
    skipped_count = 0

    for name, path in profiles_to_migrate:
        config_file = path / "config.yml"

        if not config_file.exists():
            console.print(f"  [dim]Skipping {name} (no config.yml)[/dim]")
            skipped_count += 1
            continue

        if _migrate_profile_config(config_file, name, dry_run):
            if dry_run:
                console.print(f"  [yellow]Would migrate:[/yellow] {name}")
            else:
                console.print(f"  [green]Migrated:[/green] {name}")
            migrated_count += 1
        else:
            console.print(
                f"  [dim]Skipped {name} (already migrated or no host node)[/dim]"
            )
            skipped_count += 1

    # Summary
    action = "Would migrate" if dry_run else "Migrated"
    console.print(f"\n{action} {migrated_count} profile(s), skipped {skipped_count}")

    return 0


def _generate_config_template(profile_name: str, schema_rel: str) -> str:
    """Generate comprehensive config.yml template with all configuration options.

    Args:
        profile_name: Name of the profile being created
        schema_rel: Relative path to config.schema.json

    Returns:
        Complete YAML config template as string with all 67+ properties documented
    """
    return f"""---
# yaml-language-server: $schema={schema_rel}
# {profile_name.replace("-", " ").title()} profile configuration
#
# Auto-discovered variables (set by inventory plugin):
#   profile_name: {profile_name}
#   profile_dir: Path to this profile directory
#   dotfiles_dir: {{{{ profile_dir }}}}/files/dotfiles
#   dotfiles_copy_dir: {{{{ profile_dir }}}}/files/dotfiles-copy
#   packages_dir: {{{{ profile_dir }}}}/packages
#   profile_requirements_file: {{{{ profile_dir }}}}/requirements.yml

# ============================================================================
# Profile Metadata
# ============================================================================

profile:
  name: {profile_name}
  # host: {profile_name}-profile  # Ansible host name (default: {{{{name}}}}-profile)
  # priority: 1000                 # Execution order (lower = earlier, default: 1000)

# ============================================================================
# Homebrew Packages
# ============================================================================

# Homebrew formulae
# brew_packages:
#   - name: neovim                    # Simple package
#   - name: tmux
#     state: latest                   # Always upgrade to latest
#   - name: old-package
#     state: absent                   # Remove if installed
#   - name: specific-version
#     version: "1.2.3"                # Pin to specific version

# Homebrew taps
# brew_taps:
#   - name: homebrew/cask-fonts
#   - name: hashicorp/tap
#   - name: old-tap
#     state: absent                   # Remove tap

# Homebrew casks (GUI applications)
# cask_packages:
#   - name: visual-studio-code
#   - name: docker
#   - name: old-app
#     state: absent                   # Remove if installed

# Upgrade all Homebrew packages on every run
# brew_upgrade_all: false             # Default: false

# ============================================================================
# Mac App Store
# ============================================================================

# Mac App Store applications (requires mas CLI)
# mas_packages:
#   - name: Keynote
#     id: 409183694                   # Find ID with: mas search "app name"
#   - name: Xcode
#     id: 497799835
#   - name: old-app
#     id: 123456789
#     state: absent                   # Remove if installed

# Upgrade all Mac App Store apps on every run
# mas_upgrade_all: false              # Default: false

# ============================================================================
# Python Packages
# ============================================================================

# Pipx packages (isolated Python CLI tools)
# pipx_packages:
#   # Simple PyPI package
#   - name: black
#
#   # Local editable package (paths starting with "packages/" are relative to profile_dir)
#   - name: my-tool
#     path: packages/my-tool
#     editable: true                  # Default: true for local packages
#
#   # Package with native dependencies (auto-sets CFLAGS/LDFLAGS from brew prefixes)
#   - name: erdantic
#     build_deps:
#       - graphviz                    # Sets -I and -L flags for graphviz
#
#   # Package with custom environment variables
#   - name: custom-tool
#     env:
#       CUSTOM_VAR: "value"
#
#   # Remove a package
#   - name: old-tool
#     state: absent

# System pip packages (uses miniconda or system pip)
# pip_packages:
#   - name: ansible
#     state: latest                   # Default: latest
#   - name: git+https://github.com/user/repo  # Install from git
#   - name: old-package
#     state: absent                   # Remove if installed

# Pip configuration (advanced)
# pip_executable: /path/to/pip        # Override pip executable
# pip_miniconda_path: /opt/homebrew/Caskroom/miniconda/base  # Default miniconda path
# pip_system_pip_path: /usr/local/bin/pip3  # Default system pip path

# ============================================================================
# Other Package Managers
# ============================================================================

# Ruby gems
# gem_packages:
#   - name: bundler
#   - name: rails
#     version: "7.0.0"                # Pin to specific version
#   - name: old-gem
#     state: absent                   # Remove if installed

# Global npm packages
# npm_packages:
#   - name: typescript
#   - name: "@vue/cli"                # Scoped package
#   - name: prettier
#     state: latest                   # Always upgrade
#   - name: old-package
#     state: absent                   # Remove if installed

# Global composer packages (PHP)
# composer_packages:
#   - name: phpunit/phpunit
#     global_command: true            # Default: true
#   - name: local/package
#     working_dir: ~/projects/php     # Directory for local install

# ============================================================================
# Dotfiles Configuration
# ============================================================================

# Claude Code skills and agents directories
# skill_folders:
#   - ~/.claude/skills                # Destination for skills symlinks
# agent_folders:
#   - ~/.claude/agents                # Destination for agents symlinks

# Dotfiles symlinking settings (advanced, rarely needed)
# dotfiles_cleanup_depth: 3           # Recursion depth for dead symlink cleanup (default: 3)
# dotfiles_directory_marker: ".symlink-as-directory"  # Marker file for directory-level symlinks
# dotfiles_symlink_command: "symlink-dotfiles"  # Command to run symlink-dotfiles (default)

# Additional dotfiles directories (from custom inventories)
# additional_dotfiles_dirs:
#   - /path/to/extra/dotfiles

# Profile bin directory (for scripts)
# bin_dir: {{{{ profile_dir }}}}/bin

# ============================================================================
# SSH Configuration
# ============================================================================

# SSH client configuration (structured format)
# ssh_client_config:
#   # Full example with all options
#   - host: "*.example.com"           # Host pattern
#     hostname: example.com           # Real hostname or IP
#     port: 22                        # SSH port (default: 22)
#     remote_user: username           # SSH username
#     identity_file: ~/.ssh/id_rsa    # Path to identity file
#     identities_only: true           # Only use specified identities
#     forward_agent: true             # Agent forwarding
#     proxycommand: "ssh gateway nc %h %p"  # Proxy command
#     proxyjump: gateway.example.com  # Proxy jump host
#     dynamicforward: "localhost:1080"  # SOCKS proxy
#     strict_host_key_checking: "no"  # StrictHostKeyChecking
#     add_keys_to_agent: "yes"        # AddKeysToAgent
#     user_known_hosts_file: ~/.ssh/known_hosts  # Known hosts file
#     other_options:                  # Additional SSH options
#       TCPKeepAlive: "no"
#       ServerAliveInterval: "60"
#
#   # Simple example
#   - host: "simple.com"
#     hostname: simple.com
#     remote_user: myuser
#
#   # Remove a host entry
#   - host: "old-host.com"
#     state: absent

# SSH config text blocks (for unsupported options)
# ssh_client_config_block:
#   - content: |
#       Include ~/.ssh/config.d/*
#     position: top                   # top | bottom
#   - content: |
#       Host *
#           AddKeysToAgent confirm
#     position: bottom

# SSH config file path
# ssh_config_file: ~/.ssh/config      # Default: ~/.ssh/config

# ============================================================================
# Git Configuration
# ============================================================================

# Git config directories and files
# gitconfig_conf_d: ~/.config/git/conf.d  # Directory for config fragments
# gitconfig_includes_file: ~/.config/git/conf.d/includes.gitconfig  # Generated includes file
# gitignore_file: ~/.config/git/gitignore  # Global gitignore file

# Git configuration is managed through:
#   1. files/gitconfig/*.gitconfig - Config fragments (symlinked to conf.d/)
#   2. files/gitconfig/.gitignore - Global gitignore patterns
# See the generated files/gitconfig/gitconfig.gitconfig for examples

# ============================================================================
# GitHub Integration
# ============================================================================

# GitHub CLI extensions
# gh_extensions:
#   - name: owner/gh-extension
#   - name: owner/another-ext
#     state: latest                   # Always upgrade
#   - name: owner/old-ext
#     state: absent                   # Remove if installed

# GitHub repositories to clone
# gh_repos:
#   # Simple clone (dest: ~/Projects/simple-repo)
#   - repo: owner/simple-repo
#
#   # Custom destination
#   - repo: owner/another-repo
#     dest: ~/Code/custom-path
#     state: latest                   # Fetch and pull on every run
#
#   # Clone specific tag
#   - repo: owner/versioned-repo
#     tag: v1.0.0
#
#   # Clone specific branch
#   - repo: owner/feature-repo
#     branch: develop

# Default destination for repositories
# gh_repos_default_dest: ~/Projects

# ============================================================================
# MCP Servers (Model Context Protocol)
# ============================================================================
# Configure AI coding agent integrations
# Secrets: Use lookup('vault_secret', 'path') or "op://vault/item/field"

# mcp_servers:
#   # --- STDIO Transport (command-based) ---
#
#   # Simple npx server
#   - name: filesystem
#     command: npx
#     args: ["-y", "@modelcontextprotocol/server-filesystem", "/path"]
#
#   # UV tool (no local install)
#   - name: omnifocus
#     command: uv
#     args: ["tool", "run", "--from", "git+https://github.com/user/mcp", "mcp-server"]
#
#   # Server with vault secret
#   - name: habitify
#     command: npx
#     args: ["-y", "@sargonpiraev/habitify-mcp-server"]
#     env:
#       HABITIFY_API_KEY: "{{{{ lookup('vault_secret', 'mcp_secrets.habitify.api_key') }}}}"
#
#   # Server with 1Password secret
#   - name: github
#     command: npx
#     args: ["-y", "@modelcontextprotocol/server-github"]
#     env:
#       GITHUB_TOKEN: "op://Private/github-mcp/token"
#
#   # Git-based server (auto-cloned to ~/.local/share/mcp-servers/)
#   - name: things
#     git_repo: https://github.com/user/things-mcp
#     command: uv
#     args: ["--directory", "~/.local/share/mcp-servers/things-mcp", "run", "server.py"]
#
#   # Git server with specific version and post-clone setup
#   - name: ynab
#     git_repo: https://github.com/user/mcp-ynab
#     git_version: main               # Branch, tag, or commit
#     git_dest: ~/.local/share/mcp-servers/mcp-ynab  # Custom destination
#     post_clone: "uv sync"           # Command to run after clone
#     command: ~/.local/share/mcp-servers/mcp-ynab/.venv/bin/mcp-ynab
#
#   # Git server with force options (dangerous!)
#   - name: dev-server
#     git_repo: https://github.com/user/dev-mcp
#     git_force: true                 # Force clone even if exists
#     git_force_reset: true           # Allow destructive operations
#     command: some-command
#
#   # --- URL Transport (HTTP/SSE) ---
#
#   # URL-based server with auth
#   - name: authenticated-api
#     url: "https://api.example.com/mcp"
#     transport: sse                  # sse | streamable-http
#     headers:
#       x-api-key: "{{{{ lookup('vault_secret', 'api.key') }}}}"
#
#   # Custom config files per server
#   - name: desktop-only
#     command: some-command
#     config_files:
#       - path: ~/Library/Application Support/Claude/claude_desktop_config.json
#         state: present              # present | absent
#
#   # Remove a server from all config files
#   - name: deprecated-server
#     state: absent
#     command: placeholder            # Required but ignored when state=absent

# Default config files (when not specified per server)
# mcp_default_config_files:
#   - ~/.mcp.json
#   - ~/Library/Application Support/Claude/claude_desktop_config.json

# Base directory for git-cloned MCP servers
# mcp_servers_git_base: ~/.local/share/mcp-servers

# ============================================================================
# Config Merging (JSON/YAML)
# ============================================================================

# JSON config settings (merged into existing files)
# json_configs:
#   # Create new file with settings
#   - file: ~/.config/myapp/settings.json
#     create_file: true               # Create if doesn't exist
#     content:
#       editor:
#         vimMode: true
#         fontSize: 14
#
#   # Merge into existing file
#   - file: ~/.config/vscode/settings.json
#     content:
#       "editor.formatOnSave": true

# YAML config settings (merged into existing files)
# yaml_configs:
#   # Create new file with settings
#   - file: ~/.config/myapp/config.yml
#     create_file: true               # Create if doesn't exist
#     content:
#       feature:
#         enabled: true
#         timeout: 30
#
#   # Merge into existing file
#   - file: ~/.config/tool/config.yml
#     content:
#       theme: dark

# ============================================================================
# AI Agents
# ============================================================================

# Install Cursor CLI (for Cursor AI editor)
# install_cursor_cli: false           # Default: false
"""


@profile.command("bootstrap")
@click.argument("profile_path")
@click.option(
    "--git/--no-git",
    default=True,
    help="Initialize as a git repository (default: yes)",
)
def profile_bootstrap(profile_path: str, git: bool):
    """Bootstrap a new profile with standard directory structure.

    PROFILE_PATH can be:

    \b
    - Single level: "myprofile" creates profiles/myprofile/
    - Two levels: "myrepo/work" creates profiles/myrepo/work/
    - Three levels: "private/myrepo/work" creates profiles/private/myrepo/work/

    For nested profiles, git is initialized at the second-to-last level:

    \b
    - "myrepo/work" → git at profiles/myrepo/
    - "private/myrepo/work" → git at profiles/private/myrepo/

    Creates:

    \b
    - config.yml (profile configuration)
    - files/dotfiles/ and files/dotfiles/config/
    - files/gitconfig/ (git config fragments and gitignore)
    - packages/ (local Python packages installed via pipx)
    - tasks/main.yml (custom Ansible tasks)
    - roles/ (custom Ansible roles)

    Host is auto-generated as {profile_name}-profile by the inventory plugin.
    """
    profiles_dir = Path(DOTFILES_DIR) / "profiles"
    path_parts = profile_path.split("/")

    # Validate depth
    if len(path_parts) > 3:
        click.echo("Error: Maximum depth is 3 (e.g., private/repo/profile)", err=True)
        return 1

    # Determine paths based on structure
    if len(path_parts) == 1:
        # Single level: profiles/myprofile/
        profile_dir = profiles_dir / path_parts[0]
        git_init_dir = profile_dir
        profile_name = path_parts[0]
        relative_path = path_parts[0]
    elif len(path_parts) == 2:
        # Two level: profiles/myrepo/work/
        repo_dir = profiles_dir / path_parts[0]
        profile_dir = repo_dir / path_parts[1]
        git_init_dir = repo_dir  # Git at repo level
        profile_name = f"{path_parts[0]}-{path_parts[1]}"
        relative_path = profile_path
    else:
        # Three level: profiles/private/myrepo/work/
        parent_dir = profiles_dir / path_parts[0]
        repo_dir = parent_dir / path_parts[1]
        profile_dir = repo_dir / path_parts[2]
        git_init_dir = repo_dir  # Git at repo level (second-to-last)
        profile_name = f"{path_parts[0]}-{path_parts[1]}-{path_parts[2]}"
        relative_path = profile_path

    if profile_dir.exists():
        click.echo(
            f"Error: Profile '{profile_name}' already exists at {profile_dir}", err=True
        )
        return 1

    click.echo(f"Creating profile '{profile_name}'...")
    if len(path_parts) >= 2:
        click.echo(f"  Structure: nested (profiles/{relative_path}/)")

    dirs_to_create = [
        profile_dir / "files" / "dotfiles" / "config",
        profile_dir / "packages",
        profile_dir / "tasks",
        profile_dir / "roles",
    ]

    for dir_path in dirs_to_create:
        dir_path.mkdir(parents=True, exist_ok=True)
        gitkeep = dir_path / ".gitkeep"
        gitkeep.touch()

    config_file = profile_dir / "config.yml"
    schema_path = Path(DOTFILES_DIR) / "schemas" / "config.schema.json"
    schema_rel = os.path.relpath(schema_path, profile_dir)
    config_content = _generate_config_template(profile_name, schema_rel)
    config_file.write_text(config_content)
    click.echo(f"  Created {config_file.relative_to(profiles_dir)}")

    gitconfig_dir = profile_dir / "files" / "gitconfig"
    gitconfig_dir.mkdir(parents=True, exist_ok=True)
    gitconfig_fragment = gitconfig_dir / "gitconfig.gitconfig"
    gitconfig_content = f"""# {profile_name.replace("-", " ").title()} git configuration fragment
# This file is symlinked to ~/.config/git/conf.d/ by the gitconfig role
# Uncomment and customize as needed:

# [user]
# name = Your Name
# email = your.email@example.com
# signingkey = ssh-ed25519 AAAA...

# [includeIf "hasconfig:remote.*.url:git@github.com:your-org/**"]
# path = ~/.config/git/{profile_name}.gitconfig
"""
    gitconfig_fragment.write_text(gitconfig_content)
    click.echo(f"  Created {gitconfig_fragment.relative_to(profiles_dir)}")

    tasks_main = profile_dir / "tasks" / "main.yml"
    tasks_content = f"""---
# {profile_name.replace("-", " ").title()} profile custom tasks
# These tasks run after all standard roles complete.
#
# Available variables (auto-discovered by inventory plugin):
#   profile_name: {profile_name}
#   profile_dir: Path to this profile directory
#   profile_roles_dir: Path to roles/ in this profile
#   profile_requirements_file: Path to requirements.yml in this profile
#   dotfiles_dir: Path to files/dotfiles/ in this profile
#   dotfiles_copy_dir: Path to files/dotfiles-copy/ in this profile
#   packages_dir: Path to packages/ in this profile (for pipx local packages)
#
# To include a custom role from this profile:
#   - name: Include my custom role
#     ansible.builtin.include_role:
#       name: "{{{{ profile_roles_dir }}}}/my_role"

# Example tasks:
# - name: Ensure custom directory exists
#   ansible.builtin.file:
#     path: ~/custom-dir
#     state: directory
#     mode: "0755"

# - name: Include a profile-specific role
#   ansible.builtin.include_role:
#     name: "{{{{ profile_roles_dir }}}}/my_custom_role"
"""
    tasks_main.write_text(tasks_content)
    click.echo(f"  Created {tasks_main.relative_to(profiles_dir)}")

    (profile_dir / "tasks" / ".gitkeep").unlink(missing_ok=True)

    profile_gitignore = profile_dir / ".gitignore"
    profile_gitignore_content = """# Python cache
__pycache__/

# Vault password file (never commit)
.vault_password
"""
    profile_gitignore.write_text(profile_gitignore_content)
    click.echo(f"  Created {profile_gitignore.relative_to(profiles_dir)}")

    if git:
        # Check if git repo already exists at repo level (for nested profiles)
        if git_init_dir.exists() and (git_init_dir / ".git").exists():
            click.echo(f"  Git repository already exists at {git_init_dir.name}/")
            # Just add the new profile to the existing repo
            subprocess.run(["git", "add", "."], cwd=profile_dir, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", f"Add {profile_name} profile"],
                cwd=git_init_dir,
                capture_output=True,
            )
            click.echo("  Added profile to existing git repository")
        else:
            click.echo(f"  Initializing git repository at {git_init_dir.name}/...")
            subprocess.run(["git", "init"], cwd=git_init_dir, capture_output=True)
            subprocess.run(["git", "add", "."], cwd=git_init_dir, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", f"Initial {profile_name} profile structure"],
                cwd=git_init_dir,
                capture_output=True,
            )
            click.echo("  Git repository initialized with initial commit")

    click.echo(f"\n✓ Profile '{profile_name}' created at {profile_dir}")
    click.echo("\nNext steps:")
    click.echo(
        f"  1. Add dotfiles to {(profile_dir / 'files' / 'dotfiles').relative_to(Path(DOTFILES_DIR))}/"
    )
    click.echo(
        f"  2. (Optional) Add Python CLI tools to {(profile_dir / 'packages').relative_to(Path(DOTFILES_DIR))}/"
    )
    click.echo(
        f"  3. (Optional) Add custom tasks to {(profile_dir / 'tasks' / 'main.yml').relative_to(Path(DOTFILES_DIR))}"
    )
    click.echo(
        f"  4. (Optional) Add custom roles to {(profile_dir / 'roles').relative_to(Path(DOTFILES_DIR))}/"
    )
    click.echo(
        f"  5. (Optional) Edit {config_file.relative_to(Path(DOTFILES_DIR))} for custom settings"
    )
    click.echo("  6. Run: ./dotfiles install --profile common," + profile_name)
    if git:
        click.echo(
            f"  7. Add remote: cd {git_init_dir.relative_to(Path(DOTFILES_DIR))} && git remote add origin <url>"
        )
    click.echo(f"\nFor secrets, run: ./dotfiles secret init -p {profile_name}")

    return 0


# Legacy alias for backward compatibility
@click.command("bootstrap-profile", hidden=True)
@click.argument("profile_name")
@click.option(
    "--git/--no-git",
    default=True,
    help="Initialize as a git repository (default: yes)",
)
@click.pass_context
def bootstrap_profile(ctx, profile_name: str, git: bool):
    """[DEPRECATED] Use 'dotfiles profile bootstrap' instead."""
    click.echo(
        "[yellow]Warning: 'bootstrap-profile' is deprecated. "
        "Use 'dotfiles profile bootstrap' instead.[/yellow]\n",
        err=True,
    )
    ctx.invoke(profile_bootstrap, profile_path=profile_name, git=git)
