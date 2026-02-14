# Agents Profile

A shareable profile that provides a complete AI coding agent development experience.

## What's Included

### AI Coding Agents
- **Claude Code** - Anthropic's Claude CLI (`claude`)
- **Cursor** - Cursor AI editor with CLI (`agent` command)
- **Copilot CLI** - GitHub Copilot CLI (`copilot`)
- **Codex** - OpenAI Codex CLI (`codex`)
- **Gemini** - Google Gemini CLI via npx wrapper (`gemini`)

### Hive CLI (Recommended)

The **`hive`** command is a Python CLI that provides a unified interface for agent and worktree management:

- `hive run` - Run AI agent with worktree selection, resume, and auto-restart support
- `hive zellij` - Open Zellij with agent layout
- `hive wt` - Manage git worktrees (create, delete, navigate, execute commands)
- `hive status` - Multi-agent status dashboard
- `hive diff` - Show changes across agent worktrees
- `hive task` - Manage agent task assignments
- `hive handoff` - Transfer work between agents
- `hive merge` - Preview and execute merges
- `hive rebase` - Check rebase status

The hive CLI is the recommended way to interact with agents and worktrees. It provides better error handling, shell completion, and a consistent interface.

### Zellij Integration
- Generic `agent.kdl` layout for multi-agent sessions
- `zc` - Auto-detect and open agent in Zellij (shell script, works in any shell)
- `zcc`, `zcu`, `zcp`, `zco`, `zcg` - Open specific agent in Zellij (fish functions)
- `ai-code` - Run agent directly without Zellij (shell script, works in any shell)
- `acc` - Fish abbreviation for `ai-code`

### Shell Scripts (Cross-Shell Compatible)

These are legacy scripts. **Prefer using `hive` commands instead** - they provide better UX, error handling, and shell completion.

- `zc` - Open Zellij with auto-detected agent layout → use `hive zellij`
- `ai-code` - Run AI agent directly → use `hive run`
- `cda` - Quick jump to worktree directory → use `hive wt cd`
- `ensure-agent-worktree` - Manage git worktrees → use `hive wt ensure`
- `agent-status` - Display status → use `hive status`
- `agent-diff` - Show git diff → use `hive diff`
- `agent-merge-preview` - Preview merge results → use `hive merge --preview`
- `agent-rebase-check` - Check for rebase issues → use `hive rebase --check`
- `agent-handoff` - Handoff between agents → use `hive handoff`
- `agent-task` - Manage agent tasks → use `hive task`
- `auto-restart` - Auto-restart commands → use `hive run --restart` or `hive wt exec --restart`
- `git-worktree-path` - Git worktree utilities → use `hive wt path`

### Claude Code Configuration
- Custom slash commands (`/pr`, `/changelog`, `/fixup`, `/explain`, `/review`, `/test`)
- Sub-agents (productivity-coach, staff-software-engineer, qa-automation-engineer)
- Skills (git-commit, personal-docs, wiki, jira, github, omnifocus)

**Skills and Agents**: Located in `files/skills/` and `files/agents/` (not under `dotfiles/claude/`) and symlinked to multiple agent destinations (Claude Code, Cursor) via `skill_folders` and `agent_folders` configuration in `config.yml`.

### MCP Servers
- **meta-mcp** - Meta MCP server that loads other servers from config
- User configures their own servers in `~/.meta-mcp/servers.json`

## Requirements

**Required:**
- Homebrew (for package installation)
- Git (for worktree scripts)

**Recommended (for full experience):**
- Fish shell (for agent functions and Gemini wrapper)
- Zellij (for layouts)
- Node.js (for Gemini via npx, MCP servers)

**Note:** Without Fish, the `gemini` command and `zcc`/`zcu`/`zc` functions won't be available. You can still use Claude, Cursor, Copilot, and Codex directly.

## Installation

### As Part of Your Dotfiles

```bash
# Clone this profile into your dotfiles profiles directory
git clone https://github.com/yourusername/dotfiles-agents profiles/agents

# Install agents profile only
./dotfiles install -p agents

# Or combine with other profiles
./dotfiles install -p common,agents
```

### Standalone Installation

If you have the parent dotfiles system set up:

```bash
./dotfiles install -p agents
```

## Configuration

### AI Agent Priority

Configure agent priority order in your profile's `config.yml` via `yaml_configs`:

```yaml
yaml_configs:
  - file: ~/.config/hive/hive.yml
    content:
      agents:
        order:
          - claude
          - cursor
          - gemini
          - codex
          - copilot
```

This writes to `~/.config/hive/hive.yml` which the hive CLI reads directly.

### MCP Servers

After installation, configure your MCP servers in `~/.meta-mcp/servers.json`:

```json
{
  "mcpServers": {
    "my-server": {
      "command": "npx",
      "args": ["-y", "my-mcp-server"],
      "env": {
        "API_KEY": "your-api-key"
      }
    }
  }
}
```

### Cursor CLI

Cursor CLI installation is enabled by default in this profile via `install_cursor_cli: true`.
To disable, set it to `false` in your local config override.

## Customization

### Removing Agents

Edit `config.yml` to remove agents you don't need:

```yaml
cask_packages:
  - name: claude-code
  # - name: copilot-cli  # Remove if not needed
  # - name: cursor       # Remove if not needed
  # - name: codex        # Remove if not needed
```

### Adding More Agents

Add new agents by updating `config.yml` with their brew/cask packages and creating
corresponding fish functions in `files/dotfiles/config/fish/conf.d/agents.fish`.

## Commands Reference

### Hive CLI Commands (Recommended)

The `hive` CLI is the recommended way to interact with agents and worktrees. Install shell completions for the best experience:

```bash
hive completion fish --install  # Fish shell
hive completion bash            # Bash (add to .bashrc)
```

#### `hive run` — Run AI Agent

**When to use:** You want to start an AI coding agent with full control over worktree selection, resume, and auto-restart.

```bash
# Basic usage
hive run                      # Auto-detect and run agent
hive run -a claude            # Use Claude specifically
hive run --resume             # Resume most recent conversation

# Worktree integration
hive run -w=-                 # Interactive worktree selection
hive run -w feature-123       # Run in specific worktree

# Auto-restart mode (great for long-running sessions)
hive run --restart            # Interactive selection + auto-restart on each iteration
hive run --restart -w feat    # Stay in same worktree, auto-restart
hive run --restart --restart-delay 2  # Add delay between restarts
```

**Key difference from `ai-code`:** The `hive run` command provides:
- Interactive worktree selection with fuzzy finder
- `--restart` mode that re-selects worktree on each restart (or stays in same one with `-w`)
- `--restart-delay` for configurable delay between restarts
- `--resume` for resuming conversations
- Better error messages and shell completion

---

#### `hive zellij` — Open Zellij with Agent Layout

**When to use:** You want a full development environment with multiple agent sessions in Zellij.

```bash
hive zellij                          # Auto-detect agent
hive zellij -a claude                # Use Claude specifically
hive zellij --restart                # Auto-restart after Zellij exits
hive zellij --restart --restart-delay 1  # With delay between restarts
```

**Key difference from `zc`:** The `hive zellij` command provides:
- `--restart` mode for auto-restarting Zellij sessions
- `--restart-delay` for configurable delay
- Better error messages when agents aren't installed

---

#### `hive wt` — Worktree Management

**When to use:** You need to manage git worktrees for multi-agent development.

```bash
# Navigation
hive wt                      # Interactive worktree selection
hive wt cd feature-auth      # Navigate to specific worktree
hive wt path feature-auth    # Get path for worktree
hive wt parent               # Get main repository path
hive wt list                 # List all worktrees

# Management
hive wt create feature-123   # Create new worktree
hive wt delete feature-123   # Delete worktree
hive wt exists feature-123   # Check if worktree exists (exit 0/1)

# Execution
hive wt exec -c 'npm test'              # Run command in git root
hive wt exec -c 'npm test' -w=-         # Interactive worktree selection
hive wt exec -c 'make watch' --restart  # Auto-restart command
```

**`hive wt exec` restart behavior:**
- `--restart` alone: Re-select worktree interactively on EACH restart
- `--restart -w feature-123`: Stay in that worktree, no re-selection
- `--restart --restart-delay 2`: Add 2 second delay between restarts

---

### Shell Script Commands (Legacy)

The shell scripts below are still available but **`hive` commands are recommended** for better UX.

#### `zc` — Open Zellij with AI Agent

**When to use:** You want a full development environment with multiple agent sessions, shell access, git operations, and test runners all in one terminal.

**What it does:** Opens Zellij terminal multiplexer with a pre-configured layout containing multiple AI agent panes. The layout includes agent sessions, shell tabs, git operations (lazygit), and test runners.

**How it works:**
1. Detects which AI agent you have installed (checks `agents.order` in hive config)
2. Changes to your repository's root directory
3. Creates/attaches to a Zellij session named `{repo}-{agent}`

```bash
# Auto-detect best available agent
zc

# Force a specific agent
HIVE_AGENT=claude zc
HIVE_AGENT=codex zc

# Customize detection order via config (~/.config/hive/hive.yml)
# or environment variable
export HIVE_AGENTS_ORDER="claude,gemini,codex,agent,copilot"
```

**Fish shortcuts:** `zcc` (Claude), `zcu` (Cursor), `zcp` (Copilot), `zco` (Codex), `zcg` (Gemini)

---

#### `ai-code` — Run Agent Directly

**When to use:** You want to quickly start an AI agent in your current terminal without the full Zellij environment. Good for quick questions or when you're already in a terminal workflow.

**What it does:** Launches your preferred AI coding agent directly, passing through any arguments.

```bash
# Start agent interactively
ai-code

# Pass arguments to the agent
ai-code --help
ai-code "explain this codebase"

# Force a specific agent
AGENT=gemini ai-code
```

**Fish shortcut:** `acc` (abbreviation that expands to `ai-code`)

---

### Multi-Agent Worktree Workflow

These commands help you run multiple AI agents simultaneously, each working in isolated git worktrees to avoid conflicts.

#### `ensure-agent-worktree` — Select or Create a Worktree

**When to use:** You're starting a new agent session and need to decide where that agent should work. Essential when running multiple agents on the same codebase.

**What it does:**
1. Shows a fuzzy-searchable list of existing worktrees and branches
2. Lets you select an existing worktree to continue work
3. Or create a new worktree from any branch
4. Automatically installs dependencies (npm, pnpm, yarn, uv)
5. Sets up agent context files

**Why use worktrees:** Each AI agent gets its own copy of the codebase. Agent 1 can work on feature A while Agent 2 works on feature B without conflicts. Changes are isolated until you merge.

```bash
# Interactive selection (requires fzf)
ensure-agent-worktree 2

# Agent 1 always uses main repo
ensure-agent-worktree 1  # Returns main repo path

# Use in scripts
cd $(ensure-agent-worktree 2) && claude
```

**Typical workflow:**
1. Agent 1 works in main repo on `main` branch
2. Agent 2 runs `ensure-agent-worktree 2`, creates worktree for `feature-auth`
3. Agent 3 runs `ensure-agent-worktree 3`, creates worktree for `bugfix-123`
4. Each agent commits to their branch independently

---

#### `agent-status` — Dashboard of All Agent Worktrees

**When to use:** You have multiple agents running and want to see what each one is working on, whether they have uncommitted changes, and how far ahead/behind they are.

**What you get:**
- Branch name for each agent
- Dirty indicator (*) for uncommitted changes
- Commits ahead/behind the default branch
- Last commit message
- Current task (if assigned)

```bash
# One-time status check
agent-status

# Compact single-line format
agent-status --compact

# Live updating dashboard
agent-status --watch

# Compact live dashboard
agent-status --watch --compact
```

**Example output:**
```
Agent 1 (main)
  Branch: main
  Commit: abc1234 Add user authentication

Agent feature-auth *
  Branch: feature-auth
  Commit: def5678 WIP: OAuth integration
  Task:   Implement OAuth2 login flow
```

---

#### `agent-diff` — See What Each Agent Changed

**When to use:** Before merging agent work, you want to review what changes each agent made compared to main.

**What you get:** A unified diff view showing all changes across all agent worktrees, optionally with syntax highlighting (via delta).

```bash
# Full diff with syntax highlighting
agent-diff

# Just show file statistics
agent-diff --stat

# List only changed files
agent-diff --files
```

---

#### `agent-merge-preview` — Check for Merge Conflicts

**When to use:** Before merging an agent's work, you want to know if it will merge cleanly or cause conflicts.

**What you get:**
- **Without arguments:** Shows which files are being modified by multiple agents (potential conflict zones)
- **With agent number:** Simulates the merge and reports success or lists conflicting files

```bash
# See file overlap between all agents
agent-merge-preview

# Simulate merging agent-2's branch into main
agent-merge-preview 2
```

**Example output:**
```
Merge Preview: feature-auth → main

✓ Merge would succeed without conflicts

Files that would be changed:
  + src/auth/oauth.ts
  ~ src/config.ts
  ~ package.json
```

---

#### `agent-rebase-check` — Check if Agents Need Rebasing

**When to use:** Your agents have been working for a while and main has moved forward. Check if they need to rebase to avoid merge conflicts later.

**What you get:**
- Status for each worktree (up to date, X commits behind)
- Warning when rebase is recommended (>5 commits behind)
- List of files that might conflict

```bash
# Check all worktrees
agent-rebase-check

# Fetch from remote first
agent-rebase-check --fetch
```

**Example output:**
```
✓ Agent 1 (main) (main)
    up to date

! Agent feature-auth (feature-auth)
    3 commits behind
    Changed files that may conflict:
      - src/config.ts

✗ Agent old-feature (old-feature)
    12 commits behind - rebase recommended
```

---

#### `agent-handoff` — Transfer Work Between Agents

**When to use:** Agent 2 finished their part and Agent 3 needs to continue. Or you're switching from working on one machine to another.

**What it does:**
1. Optionally creates a WIP commit if there are uncommitted changes
2. Records a handoff note in shared notes file
3. Copies the task assignment to the new agent
4. Provides instructions for continuing

```bash
# Basic handoff
agent-handoff 2 3

# With a message
agent-handoff 2 3 "Completed auth UI, backend integration remaining"
```

**The handoff note is saved to `.claude/local-agents/shared-notes.md` so agents can see the history of work.**

---

#### `agent-task` — Assign and Track Agent Tasks

**When to use:** You want to give each agent a specific assignment and track what they're working on.

**What it does:** Manages markdown task files for each agent in `.claude/local-agents/tasks/`.

```bash
# Show all agent tasks
agent-task

# Show task for specific agent
agent-task 2

# Assign a task
agent-task 2 "Implement OAuth2 login with Google provider"

# Edit task in your editor
agent-task 2 -e

# Clear a task
agent-task 2 -c
```

---

#### `cda` — Quick Jump to Worktree

**When to use:** You're working with multiple worktrees and want to quickly switch between them without typing full paths.

**What it does:** Fuzzy-searches your worktrees and changes to the selected one. In fish shell, completions show available worktrees.

```bash
# Fuzzy search all worktrees (requires fzf)
cda

# Jump to main repo
cda main
cda 1

# Jump to specific worktree by branch name
cda feature-auth

# Legacy agent numbering (if worktree named agent-2 exists)
cda 2
```

**Shell compatibility:**
- **Fish:** Just type `cda` — the wrapper function handles cd and provides completions
- **Bash/Zsh:** Use `cd $(cda)` or `cd $(cda feature-auth)` since scripts can't change parent shell directory

---

### Utility Commands

#### `auto-restart` — Keep Commands Running

**When to use:** In Zellij panes where you want a command to automatically restart when it exits. Useful for agent sessions that might crash or for watch commands.

**What it does:** Wraps any command and restarts it when it exits. Detects crash loops (too many failures in a short time) and pauses.

```bash
# Keep claude running
auto-restart claude

# In Zellij layout configs
auto-restart $AGENT
```

**Configuration (environment variables):**
- `AUTO_RESTART_MAX_FAILURES=5` — Stop after this many failures
- `AUTO_RESTART_WINDOW_SECS=60` — Time window for counting failures
- `AUTO_RESTART_DELAY_SECS=1` — Delay before restart

---

#### `git-worktree-path` — Resolve Worktree Paths

**When to use:** In scripts that need to find where worktrees are stored. Used internally by other agent commands.

**What it does:** Provides a consistent way to get worktree paths, supporting both local (`.worktrees/`) and home directory (`~/.git-worktrees/`) storage modes.

```bash
# Get path for a branch
git-worktree-path feature-auth
# → /path/to/repo/.worktrees/feature-auth

# List all worktrees
git-worktree-path --list
# → main:/path/to/repo
# → feature-auth:/path/to/repo/.worktrees/feature-auth

# Check if worktree exists
git-worktree-path --exists feature-auth && echo "exists"

# Get base directory
git-worktree-path --base
# → /path/to/repo/.worktrees
```

**Centralized mode:** Set `GIT_WORKTREES_HOME=true` to store all worktrees in `~/.git-worktrees/` instead of per-repo.

---

## File Structure

```
profiles/agents/
├── config.yml                      # Package declarations & settings
├── README.md
├── packages/
│   └── hive_cli/                   # Hive CLI Python package
│       ├── pyproject.toml
│       ├── README.md
│       └── src/hive_cli/
│           ├── app.py              # CLI entry point
│           ├── config.py           # Agent configurations
│           ├── agents/             # Agent detection
│           ├── git/                # Git/worktree operations
│           ├── utils/              # Terminal, fuzzy finder
│           └── commands/           # CLI commands
│               ├── run.py          # hive run
│               ├── zellij.py       # hive zellij
│               ├── wt.py           # hive wt
│               ├── exec_runner.py  # Worktree execution logic
│               └── ...
└── files/
    ├── bin/                        # Shell scripts (→ ~/.local/bin/)
    │   ├── zc                      # Zellij agent launcher (cross-shell)
    │   ├── ai-code                 # Direct agent launcher (cross-shell)
    │   ├── cda                     # Quick jump to worktree (cross-shell)
    │   ├── agent-status, agent-diff, ...
    │   └── ensure-agent-worktree, ...
    ├── claude/                     # Claude Code config (→ ~/.claude/)
    │   ├── CLAUDE.md
    │   ├── commands/
    │   ├── agents/
    │   ├── skills/
    │   └── hooks/
    ├── dotfiles/config/
    │   ├── fish/conf.d/agents.fish # Fish-specific functions & abbreviations
    │   └── zellij/layouts/agent.kdl
    └── dotfiles-copy/.meta-mcp/
        └── servers.json            # MCP servers template
```
