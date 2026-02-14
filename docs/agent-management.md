# Multi-Agent Coding Workflow

This guide covers the multi-agent development workflow using the `hive` CLI - a unified interface for managing AI coding agents, git worktrees, and parallel development workflows.

## Overview

The multi-agent system enables running multiple AI coding agents simultaneously on the same codebase without conflicts. It provides:

- **Isolation**: Each agent works in its own git worktree
- **Coordination**: Branch handoffs and shared notes for inter-agent communication
- **Management**: Unified CLI for all worktree and agent operations
- **Monitoring**: Live status dashboard and git analysis tools
- **GitHub Integration**: Direct issue fetching and branch creation from tickets

**Primary Interface:** The `hive` CLI is the modern, recommended tool for all multi-agent operations. It replaces legacy shell scripts with a unified, configurable interface.

## Quick Start

### 1. Install the hive CLI

If you've run the dotfiles installation:

```bash
./dotfiles install pipx
```

Or install directly via pipx:

```bash
pipx install -e /path/to/profiles/agents/packages/hive_cli
```

### 2. Run an AI agent

```bash
# Auto-detect and run available agent
hive run

# Resume most recent conversation
hive run --resume

# Interactive worktree selection, then run
hive run -w=-

# Auto-restart mode with worktree selection
hive run --restart
```

### 3. Manage worktrees

```bash
# Interactive selection and navigation
hive wt

# Create a new worktree
hive wt create feature-auth

# List all worktrees
hive wt list

# Delete a worktree
hive wt delete old-feature
```

### 4. Use handoffs for coordination

```bash
# Create a handoff note for current branch
hive handoff create

# Show all active handoffs
hive handoff

# Edit handoff in $EDITOR
hive handoff edit
```

## Core Commands

### hive run

Run an AI coding agent in the current directory or a selected worktree.

**Features:**
- Auto-detects available AI agent based on configuration priority
- Supports resume functionality for continuing conversations
- Worktree integration for isolated development
- Auto-restart mode for continuous workflows

**Usage:**

```bash
# Basic usage
hive run                      # Auto-detect and run agent
hive run -a claude            # Use Claude specifically
HIVE_AGENT=gemini hive run    # Use Gemini via env var

# Resume functionality
hive run --resume             # Resume most recent conversation
hive run -r                   # Short form

# Worktree integration
hive run -w=-                 # Interactive worktree selection
hive run -w feature-123       # Run in specific worktree

# Auto-restart mode
hive run --restart            # Interactive selection + auto-restart on exit
hive run --restart -w main    # Auto-restart in main repo (no re-selection)
hive run --restart -w feat    # Auto-restart in specific worktree
hive run --restart --restart-delay 2  # Add 2s delay between restarts
hive run -r --restart         # Resume with auto-restart
```

**Options:**

| Option | Description |
|--------|-------------|
| `-a, --agent TEXT` | Specific agent to use (overrides auto-detection) |
| `-w, --worktree TEXT` | Run in worktree. Use `-` for interactive selection, or specify branch |
| `-r, --resume` | Resume most recent conversation (falls back to new if none) |
| `--restart` | Auto-restart after exit. Implies `-w=-` for selection |
| `--restart-delay FLOAT` | Delay in seconds between restarts (default: 0) |
| `--auto-select BRANCH` | Auto-select branch after timeout. Use `-` for default branch |

### hive wt (Worktree Management)

Manage git worktrees for multi-agent development.

**Features:**
- Interactive fuzzy search through branches and worktrees
- GitHub issue integration for branch creation
- Automatic dependency installation
- Branch creation directly from the picker

**Usage:**

```bash
# Navigation
hive wt                  # Interactive selection (same as hive wt cd)
hive wt cd [BRANCH]      # Navigate to worktree (outputs path)
hive wt list             # List worktrees (branch:path format)
hive wt path BRANCH      # Get path for specific worktree

# Management
hive wt create BRANCH    # Create worktree for branch
hive wt delete BRANCH    # Delete worktree
hive wt exists BRANCH    # Check existence (exit 0/1)
hive wt ensure NUM       # Interactive agent workflow

# Utilities
hive wt parent           # Get main repository path
hive wt base             # Get base directory for worktrees
```

**Interactive Picker Controls:**

| Key | Action |
|-----|--------|
| **↑↓** | Navigate items |
| **Enter** | Open selected worktree/branch |
| **Ctrl+O** | Open in editor (nvim/cursor/code) |
| **Ctrl+D** | Delete worktree |
| **Ctrl+A** | Change agent |
| **Esc** | Create new branch |
| **Ctrl+C** | Quit |

**GitHub Issue Integration:**

When GitHub integration is enabled (default), the picker shows open issues assigned to you. Selecting an issue prompts for a branch name with `gh-{number}-` prefix and creates `.claude/task.local.md` with issue details.

### hive wt exec

Execute arbitrary commands in worktrees with optional restart loop.

**Usage:**

```bash
# Execute in git root
hive wt exec -c 'ls -la'

# Interactive worktree selection
hive wt exec -c 'npm test' -w=-

# Specific worktree
hive wt exec -c 'npm test' -w feature-123

# Auto-restart mode
hive wt exec -c 'make watch' --restart        # Re-select each time
hive wt exec -c 'make watch' --restart -w feat # Restart in specific worktree
hive wt exec -c 'date' --restart --restart-delay 1
```

**Options:**

| Option | Description |
|--------|-------------|
| `-c, --command TEXT` | Command to execute (shell string) [required] |
| `-w, --worktree TEXT` | Run in worktree. Use `-` for selection, or specify branch |
| `--restart` | Auto-restart after exit. Implies `-w=-` for selection |
| `--restart-delay FLOAT` | Delay in seconds between restarts (default: 0) |

**Restart Behavior:**
- `--restart` (no `-w`): Interactive selection on EACH restart
- `--restart -w feature-123`: Stay in that worktree, no re-selection
- `--restart -w=-`: Explicit interactive selection on EACH restart

### hive handoff

Manage branch handoff notes for preserving context between sessions.

**Features:**
- Template-based handoff creation
- Central storage in `.claude/handoffs/{branch}.md`
- Automatic symlinking into worktrees
- Rich markdown formatting

**Usage:**

```bash
# Show all active handoffs
hive handoff

# Manage current branch
hive handoff show         # Show handoff for current branch
hive handoff create       # Create handoff for current branch
hive handoff edit         # Edit handoff in $EDITOR
hive handoff clear        # Clear handoff for current branch

# Manage specific branch
hive handoff show feature-123
hive handoff create feature-123 "Completed auth UI"
hive handoff edit feature-123

# Utilities
hive handoff list         # List all handoff files
hive handoff list -a      # Include empty handoffs
hive handoff clean        # Remove orphaned handoffs
hive handoff clean -n     # Preview what would be removed
hive handoff path         # Get path to handoff file
```

**Handoff Template Structure:**

When you create a handoff, it follows this template:

```markdown
# Handoff: {branch}

**Created:** 2025-01-15 14:30
**Last Commit:** abc123f Fix authentication bug
**Status:** In Progress

## Summary
[Brief description of work on this branch]

## Accomplished
- [What was completed]
- [Key changes made]

## Remaining Work
1. [Next step]
2. [Following step]

## Key Files
- `path/to/file` - [what it does]

## Context & Gotchas
- [Important context]
- [Gotchas or tricky parts]

## How to Continue
```bash
cd /path/to/worktree
git status
```
```

### hive status

Live dashboard showing all agent worktrees (legacy, use multi-agent git tools instead).

### hive diff / merge-preview / rebase-check

Git analysis tools for multi-agent workflows (legacy shell scripts - see Legacy section).

### hive zellij

Open Zellij with an AI agent layout.

**Usage:**

```bash
# Auto-detect agent
hive zellij

# Use specific agent
hive zellij -a claude

# Auto-restart after Zellij exits
hive zellij --restart
hive zellij --restart --restart-delay 1

# Use environment variable
HIVE_AGENT=gemini hive zellij
```

**Options:**

| Option | Description |
|--------|-------------|
| `-a, --agent TEXT` | Specific agent to use (overrides auto-detection) |
| `--restart` | Auto-restart Zellij after it exits |
| `--restart-delay FLOAT` | Delay in seconds between restarts (default: 0) |

### hive completion

Generate shell completion scripts.

**Usage:**

```bash
# Print completion script
hive completion fish
hive completion bash

# Install completion (fish)
hive completion fish --install
```

## Configuration

Hive supports flexible configuration through YAML files with a clear precedence hierarchy.

### Configuration Files

- **`.hive.yml`** - Version-controlled project configuration
- **`.hive.local.yml`** - Local overrides (add to `.gitignore`)
- **`$XDG_CONFIG_HOME/hive/hive.yml`** - Global user configuration (defaults to `~/.config/hive/hive.yml`)

### Configuration Precedence

Settings are merged in order (highest to lowest priority):

1. **Environment variables** (`HIVE_*` prefix)
2. **`.hive.local.yml`** (local overrides)
3. **`.hive.yml`** (project config)
4. **`$XDG_CONFIG_HOME/hive/hive.yml`** (global config)
5. **Built-in defaults**

### Configuration Options

#### Agent Configuration

**`agents.order`**
- **Type:** `list[string]`
- **Default:** `["claude", "gemini", "codex", "agent", "copilot"]`
- **Description:** Priority order for agent auto-detection. First available agent wins.

**`agents.configs.<name>.resume_args`**
- **Type:** `list[string]`
- **Default:** Varies by agent (see table below)
- **Description:** Arguments to prepend when using `--resume`. Set to `[]` to disable resume for an agent.

**Built-in resume defaults:**

| Agent | Resume Args |
|-------|-------------|
| `claude` | `["--continue"]` |
| `copilot` | `["--continue"]` |
| `codex` | `["resume", "--last"]` |
| `gemini` | `["--resume", "latest"]` |
| `agent` | `["resume"]` |
| `cursor-agent` | `["resume"]` |

#### Resume Behavior

**`resume.enabled`**
- **Type:** `boolean`
- **Default:** `false`
- **Description:** Default value for `--resume` flag when not explicitly specified.

#### Worktree Configuration

**`worktrees.enabled`**
- **Type:** `boolean`
- **Default:** `true`
- **Description:** Enable/disable worktree features. When `false`, `hive wt` commands error.

**`worktrees.parent_dir`**
- **Type:** `string`
- **Default:** `".worktrees"`
- **Description:** Directory for worktrees. Can be relative (to git root), absolute, or use `~`.

**`worktrees.use_home`**
- **Type:** `boolean`
- **Default:** `false`
- **Description:** Use `~/.git-worktrees/{repo}-{branch}` instead of `parent_dir`.

**`worktrees.resume`**
- **Type:** `boolean`
- **Default:** `false`
- **Description:** Default `--resume` flag for worktree sessions (separate from `resume.enabled`).

**`worktrees.auto_select.enabled`**
- **Type:** `boolean`
- **Default:** `false`
- **Description:** Enable auto-selection of a branch in worktree picker after timeout.

**`worktrees.auto_select.branch`**
- **Type:** `string`
- **Default:** `"-"`
- **Description:** Branch to auto-select. Use `"-"` for repo's default branch (main/master).

**`worktrees.auto_select.timeout`**
- **Type:** `float`
- **Default:** `3.0`
- **Description:** Seconds before auto-selection (0 for instant).

**`worktrees.post_create`**
- **Type:** `list[object]`
- **Default:** See example below
- **Description:** Commands to run after creating a worktree.

Each item can be:
- A string: `"npm install"` (always runs)
- An object with conditions:
  ```yaml
  - command: "pnpm install"
    if_exists: "pnpm-lock.yaml"
  ```

**`worktrees.copy_files`**
- **Type:** `list[string]`
- **Default:** `[]`
- **Description:** Files to copy from main repo to new worktrees.

**`worktrees.symlink_files`**
- **Type:** `list[string]`
- **Default:** `[]`
- **Description:** Files to symlink from main repo to new worktrees.

#### Zellij Configuration

**`zellij.layout`**
- **Type:** `string` (optional)
- **Default:** `null` (uses Zellij's default layout)
- **Description:** Zellij layout name to use. Must exist in Zellij config if specified.

**`zellij.session_name`**
- **Type:** `string`
- **Default:** `"{repo}-{agent}"`
- **Description:** Session name template. Supports `{repo}` (repository name) and `{agent}` (agent name) placeholders.

#### GitHub Integration

**`github.fetch_issues`**
- **Type:** `boolean`
- **Default:** `true`
- **Description:** Fetch GitHub issues in worktree picker for branch suggestions.

**`github.issue_limit`**
- **Type:** `integer`
- **Default:** `20`
- **Description:** Maximum number of issues to fetch.

### Environment Variables

Environment variables use the `HIVE_` prefix and take precedence over config files:

| Variable | Type | Description |
|----------|------|-------------|
| `HIVE_AGENTS_ORDER` | CSV | Agent priority order, e.g., `claude,gemini` |
| `HIVE_RESUME_ENABLED` | boolean | Enable resume by default |
| `HIVE_WORKTREES_ENABLED` | boolean | Enable worktrees feature |
| `HIVE_WORKTREES_PARENT_DIR` | string | Directory for worktrees |
| `HIVE_WORKTREES_USE_HOME` | boolean | Use `~/.git-worktrees/` instead |
| `HIVE_WORKTREES_RESUME` | boolean | Default resume for worktree sessions |
| `HIVE_ZELLIJ_LAYOUT` | string | Zellij layout name |
| `HIVE_ZELLIJ_SESSION_NAME` | string | Session name template |
| `HIVE_GITHUB_FETCH_ISSUES` | boolean | Fetch GitHub issues |
| `HIVE_GITHUB_ISSUE_LIMIT` | integer | Max issues to fetch |

**Legacy variables** (still supported, lower precedence than `HIVE_*`):

- `AGENT`: Override agent selection for current command
- `GIT_WORKTREES_HOME`: Set to `true` for home-based worktrees (equivalent to `worktrees.use_home: true`)

### Example Configurations

**Minimal project config:**

```yaml
# .hive.yml
agents:
  order: [claude, gemini]
```

**TypeScript project:**

```yaml
# .hive.yml
worktrees:
  post_create:
    - command: "pnpm install --frozen-lockfile"
      if_exists: "pnpm-lock.yaml"
  copy_files:
    - ".env.local"
```

**Python project with uv:**

```yaml
# .hive.yml
worktrees:
  post_create:
    - command: "mise trust"
      if_exists: ".mise.toml"
    - command: "uv sync"
      if_exists: "pyproject.toml"
```

**Personal overrides (git-ignored):**

```yaml
# .hive.local.yml
resume:
  enabled: true  # Always resume by default

github:
  fetch_issues: false  # Don't fetch issues (faster)

worktrees:
  auto_select:
    enabled: true
    branch: "main"
    timeout: 5.0
```

**Complete configuration reference:**

```yaml
# .hive.yml - Example configuration with all options

# Agent detection and configuration
agents:
  # Priority order for auto-detection (first available wins)
  order:
    - claude
    - gemini
    - codex
    - agent      # Cursor agent CLI
    - copilot

  # Per-agent resume behavior configuration
  configs:
    claude:
      resume_args: ["--continue"]
    codex:
      resume_args: ["resume", "--last"]
    gemini:
      resume_args: ["--resume", "latest"]
    agent:
      resume_args: ["resume"]

# Resume behavior defaults
resume:
  enabled: false

# Git worktree configuration
worktrees:
  enabled: true
  parent_dir: ".worktrees"
  use_home: false
  resume: false

  # Auto-select configuration
  auto_select:
    enabled: false
    branch: "-"      # Use "-" for default branch
    timeout: 3.0

  # Commands to run after creating a worktree
  post_create:
    - command: "mise trust"
      if_exists: ".mise.toml"
    - command: "pnpm install --frozen-lockfile"
      if_exists: "pnpm-lock.yaml"
    - command: "yarn install --frozen-lockfile"
      if_exists: "yarn.lock"
    - command: "npm ci"
      if_exists: "package-lock.json"
    - command: "uv sync"
      if_exists: "pyproject.toml"

  # Files to copy from main repo to new worktrees
  copy_files:
    - ".env.local"

  # Files to symlink from main repo to new worktrees
  symlink_files:
    - ".env"

# Zellij terminal multiplexer configuration
zellij:
  # Layout name (optional, must exist in zellij config if specified)
  # layout: "agent"

  # Session name template
  session_name: "{repo}-{agent}"

# GitHub integration
github:
  fetch_issues: true
  issue_limit: 20
```

## Advanced Features

### Handoff System Deep Dive

The handoff system preserves context when stopping work or switching between sessions.

**Architecture:**

- **Central Storage:** Handoffs are stored in `.claude/handoffs/{branch}.md` in the main repository
- **Worktree Access:** Symlinked to `.claude/HANDOFF.md` in each worktree for easy access
- **Template-Based:** Consistent structure ensures completeness
- **Branch-Specific:** Each branch has its own independent handoff file

**Workflow Pattern:**

1. **Starting work on a branch:**
   ```bash
   # Check if handoff exists
   hive handoff show

   # Read it, then clear after understanding context
   hive handoff clear
   ```

2. **Stopping work or handing off:**
   ```bash
   # Create handoff with summary
   hive handoff create "Completed auth UI, need API integration"

   # Or edit template in $EDITOR
   hive handoff edit
   ```

3. **Resuming work:**
   ```bash
   # Navigate to worktree
   hive wt cd feature-auth

   # Check handoff
   cat .claude/HANDOFF.md

   # Continue work...

   # Clear when done
   hive handoff clear
   ```

**Handoff Lifecycle:**

```
Create → Edit (refine) → Clear (when done)
   ↓
Share across sessions via central storage
   ↓
Symlink ensures easy access in worktrees
```

### GitHub Issue Integration

Direct integration with GitHub Issues for streamlined workflow.

**Features:**
- Automatic issue fetching for assigned tickets
- Issue cache for fast picker loading
- Branch name generation with `gh-{number}-` prefix
- Automatic `.claude/task.local.md` creation with issue details

**Setup:**

Requires `gh` CLI installed and authenticated:

```bash
brew install gh
gh auth login
```

**Configuration:**

```yaml
# .hive.yml
github:
  fetch_issues: true    # Enable issue fetching
  issue_limit: 20       # Max issues to show
```

**Workflow:**

1. Run `hive run -w=-` or `hive wt` to open the picker
2. Issues appear with 🎫 emoji prefix
3. Select an issue
4. Enter branch name (pre-filled with `gh-{number}-`)
5. Worktree is created with `.claude/task.local.md` containing:
   - Issue title and number
   - Issue URL
   - Full issue description

**Branch Naming Convention:**

- Pattern: `gh-{number}-{description}`
- Examples:
  - `gh-123-fix-auth-bug`
  - `gh-456-add-dark-mode`
  - `gh-789-refactor-api`

**Issue Cache:**

- Location: `~/.cache/hive/gh-{org}--{repo}-issues.json`
- Updated on each fetch (background thread)
- Fast initial picker load from cache
- Stale issues removed on successful fetch

**`.claude/task.local.md` Format:**

```markdown
# Task: Fix authentication redirect bug

**Issue:** [#123](https://github.com/org/repo/issues/123)

## Description

Users are getting redirected to the wrong page after login...
```

### Shared Notes System

For cross-branch coordination and communication.

**File:** `.claude/local-agents/shared-notes.md` (in main repository)

**When to Use:**

| Use Case | Tool |
|----------|------|
| Branch-specific work state | **Handoffs** (`.claude/handoffs/{branch}.md`) |
| Cross-branch coordination | **Shared Notes** |
| File locking across branches | **Shared Notes** |
| Blockers/questions for humans | **Shared Notes** |
| Architectural decisions | **Shared Notes** |

**Format:**

```markdown
## [Branch: feature-auth] 2025-01-15 14:30 - Found authentication bug

The OAuth token refresh logic has a race condition in `src/auth/token.ts:45`.
Need to add mutex lock before proceeding.

- Affects: feature-auth, feature-user-profile
- Status: Blocked pending architecture review

---

## LOCK: src/components/Auth.tsx

**Branch:** feature-auth
**Reason:** Refactoring authentication flow
**Expected completion:** ~30 min
**Contact:** Remove lock when done

---
```

**Best Practices:**

- Add timestamps and branch names to all entries
- Be concise but informative
- Remove entries when resolved
- Use LOCK prefix for file locks
- Check before starting work on shared files

### Zellij Integration

The Zellij layout provides a complete multi-agent environment.

**Layout Structure:**

The `agent.kdl` layout includes these tabs:

| Tab | Purpose | Panes |
|-----|---------|-------|
| **Agent 1+2** | Main development | Two agents + live status board |
| **Agent 3+4** | Additional agents | Two more agent sessions |
| **Shell+Logs** | General tasks | Shell and log viewing |
| **Git** | Version control | Lazygit + git shell |
| **Tests** | Test runner | Test execution |
| **Workflow** | Multi-agent tools | diff, merge preview, tasks |
| **Neovim** | Editor | Neovim |

**Usage:**

```bash
# Auto-detect agent and open Zellij
hive zellij

# Use specific agent
hive zellij -a claude

# Fish functions (configured via dotfiles)
zcc   # Zellij with Claude
zcu   # Zellij with Cursor
zxg   # Zellij with Gemini
zco   # Zellij with Codex
zcp   # Zellij with Copilot
zc    # Auto-detect agent
```

**Configuration:**

```yaml
# .hive.yml
zellij:
  layout: "agent"              # Use custom layout
  session_name: "{repo}-{agent}"  # Template for session name
```

**Session Management:**

Sessions are named using the `session_name` template:
- `{repo}`: Repository name (from git remote or directory name)
- `{agent}`: Agent name (claude, gemini, etc.)

Example: `dotfiles-claude`

## Legacy Shell Scripts (Compatibility)

The following shell scripts are legacy tools that have been replaced by `hive` CLI. They're maintained for compatibility but new workflows should use `hive`.

### Legacy Commands

**agent-status**

Live dashboard showing all agent worktrees.

```bash
agent-status           # Show status once
agent-status --watch   # Live updating (every 2s)
```

**agent-diff**

View combined diff of all agent worktrees against the main branch.

```bash
agent-diff           # Full diff (uses delta if available)
agent-diff --stat    # Show diffstat only
agent-diff --files   # Show only changed file names
```

**agent-rebase-check**

Check if agent worktrees need rebasing against the main branch.

```bash
agent-rebase-check          # Check current state
agent-rebase-check --fetch  # Fetch from remote first
```

**agent-merge-preview**

Preview potential merge conflicts.

```bash
agent-merge-preview      # Show file overlap between all agents
agent-merge-preview 2    # Simulate merging agent-2 into main
```

**agent-task**

Manage task assignments for agents.

```bash
agent-task                    # Show all agent tasks
agent-task 2                  # Show task for agent 2
agent-task 2 "Build auth UI"  # Set task for agent 2
agent-task 2 -e               # Edit task in $EDITOR
agent-task 2 -c               # Clear task
```

**ensure-agent-worktree**

Create or manage agent worktrees (usually called automatically by Zellij).

```bash
ensure-agent-worktree 2    # Ensure agent-2 worktree exists
```

### Fish Functions

**cda**

Quick navigation to agent worktrees (uses `hive wt` under the hood).

```bash
cda      # Go to main repo (agent 1)
cda 1    # Go to main repo
cda 2    # Go to agent-2 worktree
cda 3    # Go to agent-3 worktree
```

**cdwt**

Alternative worktree navigation.

```bash
cdwt           # Interactive selection with fzf
cdwt 2         # Go to agent-2 worktree
cdwt feature   # Go to worktree matching "feature"
```

### When to Use Legacy Scripts

Use legacy scripts when:
- Working with existing automation that hasn't been updated
- Integrating with tools that expect the old interface
- Debugging issues with the modern CLI

For all new workflows, use `hive` CLI commands instead.

## Workflow Examples

### Example 1: Parallel Feature Development

```bash
# Agent 1: Working on backend API (main repo)
hive run

# Agent 2: Working on frontend UI (separate worktree)
hive run -w=-   # Select feature-ui branch

# Check for conflicts before merging
hive merge-preview

# If no conflicts, merge in main repo
git checkout main
git merge feature-ui
```

### Example 2: Handoff Between Sessions

```bash
# Session 1: Agent working on auth
hive run -w feature-auth

# ... do some work ...

# Create handoff before stopping
hive handoff create "Completed auth UI components. Need to:
- Add form validation
- Connect to API endpoints
- Add error handling"

# Exit agent

# ----

# Session 2: Resume the work
hive run -w feature-auth --resume

# Read handoff
cat .claude/HANDOFF.md

# Continue work, then clear handoff when done
hive handoff clear
```

### Example 3: GitHub Issue Workflow

```bash
# Start agent with worktree picker
hive run -w=-

# Picker shows issues:
# 🎫 #123: Fix authentication redirect bug
# 🎫 #456: Add dark mode support
# main [repo]
# feature-auth
# ...

# Select issue #123
# Prompted: Branch: gh-123-
# Enter: gh-123-fix-auth-redirect

# Worktree created with task file
# Agent starts, can reference .claude/task.local.md for context
```

### Example 4: Debugging with Multiple Agents

```bash
# Terminal 1: Reproduce bug and write test
hive run -w reproduce-bug

# Terminal 2: Investigate auth token handling
hive run -w investigate-auth

# Terminal 3: Check database query performance
hive run -w check-db-perf

# Monitor all agents
hive status --watch

# Coordinate via shared notes
echo "## [reproduce-bug] Found race condition in token refresh" >> .claude/local-agents/shared-notes.md
```

### Example 5: Rebase Before Merging

```bash
# Check if worktrees need rebasing
hive rebase-check --fetch

# Output shows:
# ✓ feature-ui: Up to date
# ! feature-auth: 3 commits behind - rebase recommended

# Navigate to worktree and rebase
hive wt cd feature-auth
git rebase origin/main

# Return to main
hive wt cd main
```

## Tips & Best Practices

### Worktree Management

1. **Use Agent 1 for coordination** - Keep main repo clean, use it for reviewing and merging

2. **Name branches descriptively** - Instead of `agent-2`, use `feature-auth-refactor` for clarity

3. **Clean up old worktrees** - Remove when done:
   ```bash
   hive wt delete old-feature
   ```

4. **Use detached HEAD for exploration** - When just exploring/researching, avoid branch clutter

### Handoffs

5. **Create handoffs when stopping work** - Even if you plan to resume soon, preserve context:
   ```bash
   hive handoff create
   ```

6. **Clear handoffs when resuming** - After reading, clear to avoid confusion:
   ```bash
   hive handoff clear
   ```

7. **Edit handoffs for complex state** - Use `$EDITOR` for detailed context:
   ```bash
   hive handoff edit
   ```

### Coordination

8. **Check overlap before deep work** - Run `hive merge-preview` to see if you're about to conflict

9. **Use shared notes liberally** - Better to over-communicate than have agents duplicate work

10. **Commit frequently** - Agents should commit often to preserve work and enable handoffs

11. **Lock files being refactored** - Add LOCK entries to shared notes for files under heavy modification

### Configuration

12. **Use `.hive.local.yml` for personal preferences** - Don't commit personal settings like `resume.enabled`

13. **Configure post_create for dependencies** - Automatically install dependencies when creating worktrees

14. **Disable GitHub issues if not needed** - Faster picker startup:
    ```yaml
    github:
      fetch_issues: false
    ```

### Performance

15. **Use auto-select for repetitive workflows** - Skip picker when you always use the same branch:
    ```yaml
    worktrees:
      auto_select:
        enabled: true
        branch: "main"
        timeout: 3.0
    ```

16. **Use resume by default** - Continue conversations automatically:
    ```yaml
    resume:
      enabled: true
    ```

## Troubleshooting

### Worktree shows "dirty" but I committed everything

Check for untracked files:
```bash
git status
```

### Agent can't find commands

Ensure `hive` CLI is installed:
```bash
pipx list | grep hive
```

If not found:
```bash
./dotfiles install pipx
```

### GitHub issues not showing in picker

Check if `gh` CLI is installed and authenticated:
```bash
gh auth status
```

If not authenticated:
```bash
gh auth login
```

Verify configuration:
```bash
cat .hive.yml | grep -A2 github
```

### Merge preview fails

Ensure you have enough disk space. The merge preview creates a temporary directory to test merges.

### Worktree creation fails

Check if branch already has a worktree:
```bash
hive wt list
```

Verify git repository is clean:
```bash
git status
```

### Handoff file not showing in worktree

Check if symlink exists:
```bash
ls -la .claude/HANDOFF.md
```

Verify handoff exists in main repo:
```bash
hive handoff list
```

### Resume not working

Check agent configuration:
```bash
# View config
cat .hive.yml

# Test resume directly
claude --continue  # Or your agent's resume command
```

Verify agent has resume_args configured:
```yaml
agents:
  configs:
    claude:
      resume_args: ["--continue"]
```

### Interactive picker crashes

Ensure terminal supports required features:
- 256 colors
- Unicode support
- ANSI escape sequences

Test with:
```bash
echo $TERM
```

Should be `xterm-256color` or similar.

---

## Adding a New AI Coding Agent

The dotfiles system integrates multiple AI coding agents with `hive` and Zellij layouts.

### Installation Methods

**Via Homebrew (preferred)**

Add to `profiles/common/config.yml`:
```yaml
brew_packages:
  - {agent-name}
# OR
cask_packages:
  - name: {agent-name}
```

**Via npx**

Create wrapper in `profiles/common/files/dotfiles/config/fish/functions/{agent}.fish`:
```fish
function {agent}
    npx @package/agent-cli -- $argv
end
```

**Via install script**

Create an Ansible role similar to `roles/cursor_cli/`.

### Integration Steps

1. **Add to hive configuration** (project or global `.hive.yml`):
   ```yaml
   agents:
     order:
       - {agent-name}
       - claude
       - gemini
     configs:
       {agent-name}:
         resume_args: ["--continue"]  # Or agent-specific args
   ```

2. **Create Zellij layout** (`profiles/common/files/dotfiles/config/zellij/layouts/{agent}.kdl`):
   - Copy existing layout (e.g., `copilot.kdl`)
   - Replace agent command references
   - Follow standard tab structure

3. **Add Zellij profile function** (`profiles/common/files/dotfiles/config/fish/conf.d/zellij.fish`):
   ```fish
   function zx{letter} --description 'Open zellij with {agent} layout'
       zellij --layout {agent} attach --create (__zellij_get_session_name)-{agent}
   end
   ```

4. **Update auto-detect function** in same file:
   - Add agent to `zc` function's priority chain

5. **Test**: Run `{agent}`, `zx{letter}`, and `hive run` to verify

### Current Agents

| Agent | Function | Installation | Command |
|-------|----------|--------------|---------|
| Claude Code | `zcc` | brew cask | `claude` |
| Cursor | `zcu` | Ansible role | `agent` |
| Gemini | `zxg` | npx wrapper | `gemini` |
| Codex | `zco` | brew | `codex` |
| Copilot | `zcp` | brew | `copilot` |
