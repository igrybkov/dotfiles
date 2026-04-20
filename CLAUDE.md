# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is an Ansible-based dotfiles management system for macOS that automates the setup of a development environment from scratch. The system uses a Python CLI wrapper (via UV and mise) to orchestrate Ansible playbooks that configure system settings, install packages, and manage dotfiles through symlinks.

## Architecture

See [docs/architecture.md](docs/architecture.md) for the full architecture documentation (playbook structure, role patterns, aggregation pattern, configuration hierarchy, etc.).

**Important:** When searching for configuration (MCP servers, packages, etc.), always search `profiles/private/` explicitly since it's gitignored and won't appear in normal grep/glob results. Use `Bash` with `grep -r` or specify the path directly.

**Private profiles are git repos:** Each directory under `profiles/private/` is its own git repository. When modifying files there, treat them as separate repos — stage, commit, and push changes independently from the main dotfiles repo.

**Before committing or pushing**, run `./dotfiles sync --status` to see which repos have uncommitted/unpushed changes. This checks the main repo and all profile repos in parallel and shows branch, ahead/behind, staged/modified/untracked counts.

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

### Ansible Facts in Per-Profile Tasks

Facts are gathered **only on `localhost`** (first play). Per-profile tasks run on profile hosts (e.g., `agents-profile`), so Ansible facts like `ansible_system`, `ansible_architecture`, `ansible_env` are **not directly available**. To access them, reference localhost's facts:

```yaml
# Wrong — will fail with "undefined" error
"{{ ansible_architecture }}"

# Correct — reference localhost's gathered facts
"{{ hostvars['localhost']['ansible_facts']['architecture'] }}"
```

For `HOME` paths, prefer `~` which Ansible modules expand natively, instead of `ansible_env.HOME`.

## Adding New Components

### Adding a new Homebrew package

Edit the appropriate profile's `config.yml` (e.g., `profiles/shell/config.yml` for CLI tools, `profiles/development/config.yml` for dev tools) or `profiles/{profile}/config.yml`:
- `brew_packages`: for formulas
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

**Tag propagation with `include_role`:** When using `include_role` in a `tasks:` block, you must set both `tags:` on the task (so it gets selected by `--tags`) and `apply: tags:` (so the included role's internal tasks inherit those tags). Without `apply:`, the role's tasks run untagged and get skipped.

```yaml
- name: Install npm packages
  tags: [npm]
  ansible.builtin.include_role:
    name: npm
    apply:
      tags: [npm]
```

### Role Patterns

See [docs/architecture.md](docs/architecture.md#role-patterns) for the three playbook patterns (Bootstrap, Per-Profile, Aggregation).

## Profile Capabilities

This section documents what the repo already provides and how to extend each capability type. When looking for existing configuration, always check `profiles/private/` explicitly (it's gitignored — use `grep -r` or direct paths).

### Profiles Overview

| Profile | Priority | Purpose |
|---------|----------|---------|
| `macos` | 50 | macOS system-level settings |
| `shell` | 100 | Core CLI tools (fish, zsh, git, fzf, ripgrep, zellij, tmux, mise, direnv) |
| `neovim` | 110 | Neovim + NvChad configuration |
| `development` | 120 | Dev tooling (terraform, docker, k9s, jupyter, uv, poetry, ruff) |
| `macos-desktop` | 130 | GUI apps (Alfred, Obsidian, 1Password, browsers, fonts) |
| `agents` | 300 | AI coding agent framework (see below) |
| `private/*` | varies | Private profiles (work, personal, etc.) — gitignored, each is its own git repo |

Private profiles are not listed here since they vary per machine. Run `./dotfiles profile list` to see all profiles available in the current environment.

### Agentic Capabilities (agents profile)

The `agents` profile is the primary extension point for AI coding setup. It manages:

#### Skills
Claude Code slash commands. Each skill lives at `profiles/agents/files/skills/{name}/SKILL.md`.

**To add a skill:** Create `profiles/agents/files/skills/{name}/SKILL.md` with:
```yaml
---
name: skill-name
description: One line description shown in the skill picker.
allowed-tools:
  - Bash(git status:*)
  - Read
  - Glob
---

# Skill Name

Workflow, usage patterns, examples...
```
Skills are symlinked to both `~/.claude/skills/` and `~/.cursor/skills/` (configured via `skill_folders` in `profiles/agents/config.yml`).

**Existing skills (17):** agent-team, changelog, claude-api, claude-for-chrome, explain, fixup, git-commit, github, handoff, jira, omnifocus, personal-docs, pr, pr-triage, review, test, verify, wiki

#### Sub-agents
Specialized agents invoked by Claude Code's `Agent` tool. Each agent lives at `profiles/agents/files/agents/{name}.md`.

**To add a sub-agent:** Create `profiles/agents/files/agents/{name}.md` with:
```yaml
---
name: agent-name
description: "Multi-line description with use cases and examples for when to invoke this agent."
model: opus  # or sonnet, haiku
color: green  # semantic color label
---

## Your Core Philosophy
...
```
Agents are symlinked to both `~/.claude/agents/` and `~/.cursor/agents/`.

**Existing agents (3):** `staff-software-engineer` (Opus/green), `qa-automation-engineer` (Sonnet/pink), `productivity-coach` (Opus/cyan)

#### Global Agent Instructions
The global `~/.claude/CLAUDE.md` is assembled from Markdown fragments in `profiles/agents/files/AGENT.md/` (and equivalent in other profiles). Fragments are named `{NN}-{section}.md` and concatenated in order.

**To add instructions:** Create a new numbered fragment in `profiles/agents/files/AGENT.md/` or add a `AGENT.md/` directory to another profile.

#### MCP Servers
MCP servers are configured via `mcp_servers:` in a profile's `config.yml`. The `agents` profile provides two servers by default:
- **meta-mcp** — loads additional servers from `~/.meta-mcp/servers.json` (used by private profiles to inject work/personal servers without modifying shared config)
- **mcp-exec** — executes code via MCP tools

**To add an MCP server:**
```yaml
# In profiles/{profile}/config.yml
mcp_servers:
  - name: my-server
    command: uvx
    args: ["my-mcp-package"]
    env:
      API_KEY: "{{ lookup('vault_secret', 'mcp_secrets.my_server.api_key') }}"
```
Private profile MCP servers (adobe, productivity, home-network) use Ansible Vault for secrets — see [docs/secrets.md](docs/secrets.md).

### Global Gitignore

Each profile can contribute patterns to the **global** git ignore list (i.e., `~/.config/git/ignore`, applied to all repos on the machine) via `profiles/{profile}/files/gitconfig/gitignore`. These are merged by the `gitconfig` role.

When asked to "add X to the agent's gitignore", this almost always means adding X to `profiles/agents/files/gitconfig/gitignore` — **not** to `profiles/agents/.gitignore` (which controls what git ignores inside the dotfiles repo itself).

The `agents` profile currently ignores: `.hive.local.yml`, `.hive.local.yaml`, `.cursor/mcp.json`, `.cursor/plans/`, `.claude/plans/`.

**To add patterns:** Edit `profiles/agents/files/gitconfig/gitignore` (or create the file in any other profile).

### Package Management

Packages are declared in `config.yml` per profile. Available package managers:

| Key | Manager | Example use |
|-----|---------|-------------|
| `brew_packages` | Homebrew formulas | CLI tools |
| `cask_packages` | Homebrew casks | GUI apps |
| `brew_taps` | Homebrew taps | Third-party repos |
| `mas_packages` | Mac App Store (name + id) | App Store apps |
| `npm` | npm global packages | JS/Node tools |
| `pipx_packages` | pipx isolated envs | Python CLI tools |
| `gem` | Ruby gems | Ruby tools |
| `gh_extensions` | GitHub CLI extensions | gh subcommands |

All keys accept a `state: absent` field to uninstall.

### Configuration Merging

Two roles allow profiles to contribute partial configuration to shared files:

- **`json_configs`** — deep-merges JSON fragments into a target file (e.g., `~/.claude/settings.json`, `~/.cursor/cli-config.json`)
- **`yaml_configs`** — merges YAML fragments into a target file (e.g., `~/.config/hive/hive.yml`, `~/.config/mise/config.toml`)

This lets multiple profiles contribute to the same config file without overwriting each other.

### Secret Management (Vault)

Private profile secrets are encrypted with Ansible Vault in `profiles/private/{profile}/secrets.yml`. Reference them in config:
```yaml
env:
  MY_TOKEN: "{{ lookup('vault_secret', 'mcp_secrets.service.token') }}"
```
See [docs/secrets.md](docs/secrets.md) for vault setup and usage.

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
