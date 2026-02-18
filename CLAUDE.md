# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is an Ansible-based dotfiles management system for macOS that automates the setup of a development environment from scratch. The system uses a Python CLI wrapper (via UV and mise) to orchestrate Ansible playbooks that configure system settings, install packages, and manage dotfiles through symlinks.

## Architecture

See [docs/architecture.md](docs/architecture.md) for the full architecture documentation (playbook structure, role patterns, aggregation pattern, configuration hierarchy, etc.).

**Important:** When searching for configuration (MCP servers, packages, etc.), always search `profiles/private/` explicitly since it's gitignored and won't appear in normal grep/glob results. Use `Bash` with `grep -r` or specify the path directly.

## Common Development Commands

### Running the dotfiles CLI

```bash
./dotfiles install --all                    # Install all dotfiles and packages
./dotfiles install dotfiles brew            # Install specific tags
./dotfiles install --sync --all             # Sync before installing
./dotfiles edit                             # Edit dotfiles in $EDITOR
./dotfiles pull / push / sync               # Git operations
./dotfiles completion fish --install        # Install shell completions
./dotfiles profile list                     # List all profiles
./dotfiles profile bootstrap myco           # Create a new profile
./dotfiles config                           # Interactive profile/settings configuration
./dotfiles secret init                      # Initialize vault password
./dotfiles secret set -p shell key.path     # Set a secret (prompts for value)
```

### Working with Ansible directly

```bash
mise x -- ansible-playbook playbook.yml --tags dotfiles --limit shell,work
mise x -- ansible-playbook playbook.yml --list-tags
mise x -- ansible-playbook playbook.yml --syntax-check
mise x -- ansible-inventory --list                   # View dynamic inventory
```

### Testing

```bash
# Unit tests (CLI and packages)
mise x -- uv run pytest -v
mise x -- uv run pytest packages/dotfiles_cli/tests/test_app.py -v  # Specific test file

# Integration tests with Molecule
mise x -- molecule list                     # List scenarios
mise x -- molecule test -s default          # Project-level integration tests

# Individual role tests
cd roles/dotfiles && mise x -- molecule test
cd roles/ssh_config && mise x -- molecule test
```

### Linting and validation

```bash
mise x -- uv run pre-commit run --all-files
mise x -- uv run yamllint .
mise x -- uv run ansible-lint
mise x -- uv run ruff check .
mise x -- uv run ruff format .               # Format Python code
```

### Python environment management

```bash
mise x -- uv sync --managed-python --frozen   # Sync dependencies
mise x -- uv add <package-name>               # Add new dependency
mise x -- uv sync --upgrade                   # Upgrade dependencies
mise x -- uv run pytest                       # Run tests in UV environment
```

## Important Implementation Details

See [docs/architecture.md](docs/architecture.md) for details on dotfile symlinking, sudo authentication, shell integration, and the aggregation pattern.

## Adding New Components

### Adding a new Homebrew package

Edit the appropriate profile's `config.yml` (e.g., `profiles/shell/config.yml` for CLI tools, `profiles/development/config.yml` for dev tools) or `profiles/{profile}/config.yml`:
- `brew_packages`: for formulae
- `cask_packages`: for casks
- `brew_taps`: for taps
- `mas_packages`: for Mac App Store apps (with `name` and `id`)

Then run: `dotfiles install brew` (or `cask`, `mas`)

### Adding a new dotfile

1. Place source file in `profiles/shell/files/dotfiles/` (or `config/` for XDG config)
2. Run: `dotfiles install dotfiles`
3. Profile-specific dotfiles go in `profiles/{profile}/files/dotfiles/`

### Adding a new Ansible role

1. Create `roles/{rolename}/tasks/main.yml`
2. Optionally add `roles/{rolename}/defaults/main.yml` for default variables
3. Add the role to `playbook.yml` in the appropriate play (Bootstrap, Per-Profile, or Finalize)
4. Define variables in profile config files
5. Create `roles/{rolename}/README.md` documenting the role
6. Add `argument_specs` to `roles/{rolename}/meta/argument_specs.yml` for schema validation

**Tag Naming Convention:**
- Role names use underscores: `gh_repos`, `mcp_servers`
- Tags use kebab-case: `gh-repos`, `mcp-servers`

### Adding a new CLI command

1. Create `packages/dotfiles_cli/src/dotfiles_cli/commands/{command}.py`
2. Use Click decorators (`@click.command()`, `@click.option()`)
3. Import and add to `app.py`'s command group
4. Add unit tests in `packages/dotfiles_cli/tests/test_{command}.py`

### Documentation Maintenance

When modifying roles or profiles, update corresponding documentation:
- Role README files (`roles/{rolename}/README.md`)
- Profile README files (`profiles/{profile}/README.md`)
- Main README.md if user-facing commands change

### Ansible Code Style

Extract repeatable code into separate task files with `include_tasks` and loops:

```yaml
- name: Clean up dead symlinks in multiple directories
  ansible.builtin.include_tasks:
    file: delete_dead_symlinks.yml
  loop:
    - ~/.claude/commands
    - ~/.claude/agents
  loop_control:
    loop_var: symlink_dir
```

### Role Patterns

See [docs/architecture.md](docs/architecture.md#role-patterns) for the three playbook patterns (Bootstrap, Per-Profile, Aggregation).

## Detailed Documentation

| Topic | Documentation |
|-------|---------------|
| Profiles (nested profiles, git repos, custom tasks) | [docs/profiles.md](docs/profiles.md) |
| Secret management (Ansible Vault) | [docs/secrets.md](docs/secrets.md) |
| Testing (pytest, Molecule) | [docs/testing.md](docs/testing.md) |
| CLI package structure | [docs/cli.md](docs/cli.md) |
| Multi-agent workflow | [docs/agent-management.md](docs/agent-management.md) |
| Zellij configuration | [docs/zellij.md](docs/zellij.md) |
| Neovim keybindings | [docs/neovim-keybindings.md](docs/neovim-keybindings.md) |
| Lazygit usage | [docs/lazygit.md](docs/lazygit.md) |

## Neovim Configuration

Uses [NvChad](https://nvchad.com/) v2.5. Config at `profiles/neovim/files/dotfiles/config/nvim/`.
- Override default plugins: edit `lua/plugins/init.lua`
- Add new plugins: create new file in `lua/plugins/`
- First-time setup: Run `:MasonInstallAll` after launch

## Pre-commit Hooks

Uses yamllint, ansible-lint, shellcheck, ruff, and uv-lock/uv-sync. Hooks run on `pre-commit`, `post-checkout`, `post-merge`, and `post-rewrite`.

## Expected Warnings

These warnings can be safely ignored:
- **Mitogen strategy plugin deprecation**: Expected when using Mitogen for performance
- **Protomatter collection warning**: Internal Ansible issue
- **INJECT_FACTS_AS_VARS deprecation from external roles**: Third-party roles issue
