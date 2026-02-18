# dotfiles

Ansible-based macOS environment setup with profile-based configuration management.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![macOS](https://img.shields.io/badge/macOS-Ventura%2B-black?logo=apple)](https://www.apple.com/macos/)
[![Ansible](https://img.shields.io/badge/Ansible-2.17%2B-red?logo=ansible)](https://www.ansible.com/)

<p align="center">
  <img src="docs/assets/demo.gif" alt="dotfiles demo" width="800">
</p>

## Overview

Automated macOS development environment setup powered by Ansible. One command installs Homebrew packages, symlinks dotfiles, configures SSH and Git per profile, manages secrets with Ansible Vault, and applies macOS system settings. The profile system lets you separate work, personal, and private configurations — and keep private profiles in their own git repos.

This repo ships with an opinionated set of packages and tools across four topical profiles (`shell`, `neovim`, `development`, `macos-desktop`). **Fork it and make it yours** — swap in your own packages, dotfiles, and profiles.

## Features

- **Profile-based configuration** — work, personal, private profiles that combine freely
- **Homebrew, Cask, and Mac App Store** automation
- **Dotfile symlinking** with XDG config directory support
- **Per-profile SSH and Git** configuration
- **Secret management** with Ansible Vault
- **Private profiles as separate git repos** — keep sensitive configs out of your public dotfiles
- **CLI with shell completions** for fish, bash, and zsh
- **18 modular Ansible roles** — use what you need, ignore the rest
- **macOS system settings** automation
- **Auto-bootstrapping** — installs Homebrew, mise, uv, and Ansible on first run

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Customization](#customization)
- [CLI Commands](#cli-commands)
- [Profiles](#profiles)
- [Available Tags](#available-tags)
- [Secret Management](#secret-management)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [Acknowledgments](#acknowledgments)
- [License](#license)

## Prerequisites

- **macOS Ventura (13)** or later
- **Xcode Command Line Tools**: `xcode-select --install`

Everything else — Homebrew, Python, Ansible, mise, uv — is installed automatically on first run.

## Quick Start

1. **Fork and clone:**

   ```bash
   git clone https://github.com/<your-username>/dotfiles.git ~/.dotfiles
   cd ~/.dotfiles
   ```

2. **Configure profiles and settings:**

   ```bash
   ./dotfiles config
   ```

3. **Install everything:**

   ```bash
   ./dotfiles install --all
   ```

After installation, `dotfiles` is available globally from any directory.

<details>
<summary><strong>What just happened?</strong></summary>

- Homebrew formulae and casks were installed
- Dotfiles were symlinked to your home directory and `~/.config/`
- SSH config was generated from your profile settings
- Git config blocks were written per profile
- macOS system preferences were applied
- Shell was set (if configured)
- Mac App Store apps were installed (if `mas` tag was included)
- The `dotfiles` CLI was linked to `~/.local/bin/dotfiles` for global access

</details>

## Customization

This repo is designed to be forked and customized. The built-in profiles (`shell`, `neovim`, `development`, `macos-desktop`) contain the author's preferred tools — replace them with your own.

### Adding packages

Edit the appropriate profile's `config.yml` — e.g., `profiles/shell/config.yml` for CLI tools, `profiles/development/config.yml` for dev tools, or `profiles/{profile}/config.yml` for profile-specific packages:

```yaml
brew_packages:
  - name: ripgrep
  - name: fd

cask_packages:
  - name: visual-studio-code
  - name: firefox

mas_packages:
  - name: Magnet
    id: 441258766
```

Then run: `dotfiles install brew cask mas`

### Adding dotfiles

Place files in the appropriate profile directory:

| Source | Destination | Method |
|--------|-------------|--------|
| `files/dotfiles/{file}` | `~/.{file}` | Symlink |
| `files/dotfiles/config/{dir}` | `~/.config/{dir}` | Symlink |
| `files/dotfiles-copy/{file}` | `~/{file}` | Copy |
| `files/bin/{script}` | `~/.local/bin/{script}` | Symlink |

All paths are relative to `profiles/{profile}/`. Then run: `dotfiles install dotfiles`

### Local overrides

Create `config.yml` in the repository root to override any profile variables. This file is git-ignored, so your local tweaks won't affect version control.

## CLI Commands

| Command | Description |
|---------|-------------|
| `dotfiles install [TAGS]` | Install packages and configure system |
| `dotfiles config` | Interactive profile and settings configuration |
| `dotfiles sync` | Pull, upgrade dependencies, push |
| `dotfiles upgrade` | Upgrade mise, Ansible Galaxy, Python packages |
| `dotfiles pull` / `push` | Git operations (main repo + profile repos) |
| `dotfiles edit` | Open dotfiles in `$EDITOR` |
| `dotfiles secret <cmd>` | Manage Ansible Vault secrets |
| `dotfiles completion <shell>` | Generate or install shell completions |
| `dotfiles profile list` | List all profiles with status and priority |
| `dotfiles profile bootstrap <name>` | Create a new profile |

### Install examples

```bash
dotfiles install --all                       # Everything
dotfiles install dotfiles brew               # Specific tags
dotfiles install --profile shell,work brew    # Specific profiles + tags
dotfiles install --sync --all                # Sync before installing
dotfiles install -v                          # Verbose (-vv, -vvv for more)
dotfiles install --dry-run                   # Preview changes without applying
```

Run `dotfiles <command> --help` for full options on any command.

## Profiles

### Why Profiles?

- **Privacy**: Keep work configs (corporate GitHub orgs, internal tools) in private repos
- **Modularity**: Separate concerns between different environments
- **Portability**: Share your main dotfiles publicly while keeping sensitive configs private

### Profile structure

```
profiles/
├── shell/                     # Core CLI tools (priority 100)
│   ├── config.yml
│   └── files/dotfiles/
├── neovim/                    # Editor configuration (priority 110)
│   ├── config.yml
│   └── files/dotfiles/
├── development/               # Dev tools (priority 120)
│   ├── config.yml
│   └── files/bin/
├── macos-desktop/             # GUI apps, fonts (priority 130)
│   ├── config.yml
│   └── files/dotfiles/
├── work/                      # Work-specific configuration
│   └── config.yml
├── personal/                  # Personal configuration
│   └── config.yml
└── private/                   # Private profiles (git-ignored)
    └── mycompany/             # Separate git repo per company/context
        ├── config.yml
        ├── files/dotfiles/    # Profile dotfiles to symlink
        ├── files/bin/         # Profile scripts
        ├── tasks/main.yml     # Custom Ansible tasks
        ├── roles/             # Custom Ansible roles
        ├── secrets/           # Vault-encrypted secrets
        └── .git/              # Managed as a separate git repo
```

### Configuration example

```yaml
# profiles/private/mycompany/config.yml
---
host:
  name: mycompany-profile
  priority: 200

brew_packages:
  - name: internal-tool

ssh_client_config:
  - host: "*.internal.company.com"
    identity_file: ~/.ssh/company_key
    remote_user: myuser

```

### Creating a profile

```bash
dotfiles profile bootstrap private/mycompany          # Creates private profile with git repo
dotfiles profile bootstrap private/mycompany --no-git  # Without git initialization
dotfiles profile bootstrap mycompany                   # Creates shared (public) profile
```

### Private profile git repos

Private profiles live in `profiles/private/` (git-ignored) and can be managed as separate git repositories:

```bash
cd profiles/private/mycompany
git remote add origin git@github.com:you/dotfiles-mycompany.git
git push -u origin main
```

The `pull`, `push`, and `sync` commands automatically discover and sync profile git repos.

See [docs/profiles.md](docs/profiles.md) for nested profiles, custom tasks, and advanced configuration.

## Available Tags

Run specific parts of the setup using tags:

| Tag | Description |
|-----|-------------|
| `all` | Run everything |
| `brew` | Install Homebrew formulae |
| `brew-packages` | Install Homebrew formulae (alias for `brew`) |
| `cask` | Install Homebrew casks |
| `taps` | Configure Homebrew taps |
| `mas` | Install Mac App Store apps |
| `dotfiles` | Symlink dotfiles to home directory |
| `gitconfig` | Configure git (profile blocks) |
| `ssh` | Configure SSH |
| `python` | Python environment setup |
| `pip` | Install Python packages |
| `pipx` | Install pipx packages |
| `gem` | Install Ruby gems |
| `npm` | Install npm global packages |
| `composer` | Install PHP Composer packages |
| `docker` | Docker configuration |
| `mise` | Install mise-managed tools |
| `fonts` | Install fonts |
| `chsh` | Change default shell |
| `gh-extensions` | Install GitHub CLI extensions |
| `gh-repos` | Clone GitHub repositories |
| `mcp-servers` | Configure MCP servers for Claude |
| `coding-agents` | Configure coding agent tools |
| `cursor-cli` | Install Cursor CLI |
| `json-config` | Manage JSON configuration files |
| `yaml-config` | Manage YAML configuration files |

## Secret Management

```bash
dotfiles secret init                          # Create global vault password
dotfiles secret init -p shell                 # Create profile-specific vault password
dotfiles secret set -p shell mcp.api_key      # Set a secret (prompts for value)
dotfiles secret get -p shell mcp.api_key      # Retrieve a secret
```

Secrets are encrypted with Ansible Vault. Each profile can have its own secrets file and vault password.

See [docs/secrets.md](docs/secrets.md) for the full reference including profile secrets, editing, rekeying, and more.

## Architecture

The system runs a four-play Ansible playbook:

1. **Gather Facts** — collect system information (all hosts, linear strategy)
2. **Bootstrap** — one-time setup: macOS settings, Homebrew installation (`localhost`)
3. **Per-Profile Setup** — profile-specific tasks: dotfiles, pipx, MCP servers (all profile hosts)
4. **Finalize** — aggregation across profiles: brew packages, SSH config, git config, etc. (`localhost`)

Key design choices:
- **Dynamic inventory** — profiles are discovered automatically via a custom inventory plugin
- **Aggregation pattern** — the Finalize play collects variables from all profiles and merges them before executing once
- **Mitogen** — used as the connection strategy for faster execution

See [docs/architecture.md](docs/architecture.md) for detailed architecture documentation.

## Project Structure

```
├── dotfiles                  # CLI wrapper script (entry point)
├── playbook.yml              # Main Ansible playbook
├── packages/                 # Python packages (UV workspace)
│   ├── dotfiles_cli/         # Main CLI (Click-based)
│   ├── dotfiles_profile_discovery/  # Shared profile discovery
│   └── symlink_dotfiles/     # Dotfile symlinking logic
├── ansible_plugins/          # Custom Ansible plugins
│   ├── inventory/            # Dynamic profile inventory
│   ├── lookup/               # Aggregation lookup
│   ├── filter/               # Custom Jinja2 filters
│   └── action/               # Custom action plugins
├── profiles/                 # Profile configurations
│   ├── shell/                # Core CLI tools (priority 100)
│   ├── neovim/               # Editor configuration (priority 110)
│   ├── development/          # Dev tools (priority 120)
│   ├── macos-desktop/        # GUI apps, fonts (priority 130)
│   ├── work/                 # Work-specific configuration
│   ├── personal/             # Personal configuration
│   └── private/              # Private profiles (git-ignored, nested repos)
├── roles/                    # Ansible roles (18 modular roles)
├── schemas/                  # JSON schemas for config validation
├── molecule/                 # Integration tests
├── docs/                     # Documentation
└── config.yml                # Local overrides (git-ignored)
```

## Troubleshooting

**First run is slow**

The initial run bootstraps all dependencies (Homebrew, mise, uv, Ansible, Python). Subsequent runs are much faster.

**Homebrew permission issues**

Run `sudo chown -R $(whoami) /usr/local/` (Intel) or ensure `/opt/homebrew/` is owned by your user (Apple Silicon).

**How do I remove a package?**

Set `state: absent` in your profile's `config.yml` and run the relevant install tag. Ansible will uninstall it for you.

**How do I skip certain tags?**

Use Ansible's skip-tags directly: `mise x -- ansible-playbook playbook.yml --skip-tags mas,docker`

**How do I use this with an existing Homebrew setup?**

It works out of the box. The installer only adds packages listed in your profiles — it won't modify or remove existing packages.

**Dotfile conflicts**

If a target file already exists and isn't a symlink, the dotfiles role will skip it. Back up or remove the existing file to allow symlinking.

## Contributing

Contributions are welcome. Please follow [Conventional Commits](https://www.conventionalcommits.org/) for commit messages and run `mise x -- uv run pre-commit run --all-files` before submitting.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide.

## Acknowledgments

- [Jonas Friedmann](https://github.com/frdmn) — original fork source
- [Ansible](https://www.ansible.com/), [Homebrew](https://brew.sh/), [mise](https://mise.jdx.dev/), [uv](https://docs.astral.sh/uv/) — the tools that make this work

## License

[MIT](LICENSE)
