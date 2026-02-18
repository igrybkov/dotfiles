# Architecture

## Overview

This is an Ansible-based dotfiles management system for macOS that automates the setup of a development environment from scratch. The system uses a Python CLI wrapper (via UV and mise) to orchestrate Ansible playbooks that configure system settings, install packages, and manage dotfiles through symlinks.

## Key Components

- **`dotfiles` (bash wrapper)**: Entry point that sets up Python environment via mise/uv, installs dependencies, and delegates to the Python CLI
- **`packages/` (UV workspace)**: Three Python packages managed as a UV workspace:
  - `dotfiles_cli/`: Main CLI using Click (commands: install, edit, pull, push, sync, completion, profile, secret)
  - `dotfiles_profile_discovery/`: Shared profile discovery logic used by CLI and Ansible inventory plugin
  - `symlink_dotfiles/`: Standalone package for dotfile symlinking
- **`playbook.yml`**: Main Ansible playbook with four plays (see [Playbook Structure](#playbook-structure))
- **`profiles/`**: Profile configurations (nested up to 3 levels). See [profiles.md](profiles.md)
- **`ansible_plugins/`**: Custom Ansible plugins:
  - `inventory/dotfiles_profiles.py`: Dynamic inventory plugin for profile discovery
  - `lookup/aggregated_profile_var.py`: Aggregates variables from all profile hosts via hostvars
  - `filter/`: Custom Jinja2 filters
  - `action/`: Custom action plugins
- **`roles/`**: Modular Ansible roles (brew_packages, dotfiles, mas, pip, gem, composer, ssh_config, gitconfig, mcp_servers, etc.)
- **`docs/`**: Detailed documentation for profiles, testing, secrets, CLI, and tools

## Configuration Hierarchy

In order of precedence:

1. `config.yml`: Optional local overrides (git-ignored)
2. `profiles/{profile}/config.yml`: Profile-specific configuration
3. Built-in topical profiles: `shell` (CLI tools), `neovim` (editor), `development` (dev tools), `macos-desktop` (GUI apps)

## Playbook Structure

The main playbook runs four plays in sequence:

1. **Gather Facts** (`all` hosts): Collects minimal facts using `linear` strategy (bypasses Mitogen's slow fact gathering)
2. **Bootstrap** (`localhost`): One-time setup — macOS settings, Homebrew installation, brew_packages
3. **Setup dependencies per profile** (`all` hosts): Per-profile tasks — dotfiles, pipx, mcp_servers
4. **Finalize** (`localhost`): Aggregation + run-once — mas, ssh_config, gitconfig, pip, gem, composer, chsh, docker, gh_extensions, mise

### Role Patterns

The playbook uses three patterns:

1. **Bootstrap Pattern** (runs once before profiles): `localhost` in Bootstrap play
2. **Per-Profile Pattern** (runs once per profile): `hosts: all` in "Setup dependencies per profile" play
3. **Aggregation Pattern** (collects from all profiles, runs once): `localhost` in Finalize play

**Why localhost for aggregation?** Avoids double-counting when collecting data from `hostvars`. The aggregation pattern collects variables from all profile hosts via `lookup('aggregated_profile_var', 'varname')`, merges them, and executes once on localhost.

## Aggregation Pattern

The Finalize play uses the `aggregated_profile_var` lookup plugin to collect variables from all profile hosts:

```yaml
# Aggregates brew_packages from all profiles (shell, development, work, etc.)
brew_packages: "{{ lookup('aggregated_profile_var', 'brew_packages') | community.general.lists_mergeby('name') }}"
```

This pattern is used for: brew_packages, cask_packages, mas_packages, ssh_client_config, git config blocks, gh_extensions, pip_packages, gem_packages, composer_packages, gh_repos, and MCP servers.

## Dotfile Symlinking

The `dotfiles` role (`roles/dotfiles/tasks/main.yml`):

1. Cleans up dead symlinks in home directory, `~/.config/`, and `~/.local/bin/`
2. Symlinks files from profile's `files/dotfiles/` to `~/.{filename}` (excluding `config/`)
3. Symlinks files from profile's `files/dotfiles/config/` to `~/.config/{filename}`
4. Symlinks scripts from profile's `files/bin/` to `~/.local/bin/{filename}`
5. Copies (not symlinks) files from profile's `files/dotfiles-copy/` to `~/`

## Sudo Authentication

The Python CLI implements secure sudo authentication:

- Sudo tags (defined in `SUDO_TAGS`): `mas`, `chsh`
- For sudo tasks: prompts once, stores in environment variable, uses askpass script
- Bypasses Touch ID entirely, preventing multiple biometric prompts

## Shell Integration

After installation, `dotfiles` is symlinked to `~/.local/bin/dotfiles` for easy access. The wrapper script uses `mise x --` to execute commands within the project's mise environment.

## Profiles

The system uses profiles to manage different machine configurations:

- `shell` (priority 100): Core CLI tools — fish, zsh, bash, git, fzf, ripgrep, zellij, starship, mise
- `neovim` (priority 110): Editor — neovim, NvChad config, vim legacy, stylua, shfmt
- `development` (priority 120): Dev tools — IDEs, languages, DBs, cloud/infra, task runners, containers
- `macos-desktop` (priority 130): GUI — desktop apps, MAS, Alfred, fonts, terminal emulators
- `work`: Work-specific packages, SSH config, git settings
- `personal`: Personal packages and configurations
- Private profiles can be added to `profiles/private/` and are git-ignored by default

Profiles support up to three levels of nesting (e.g., `profiles/private/mycompany/work/` -> `private-mycompany-work`). A directory is only considered a profile if it contains `config.yml`.

See [profiles.md](profiles.md) for full documentation.
