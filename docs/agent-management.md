# Multi-Agent Coding Workflow

This guide covers the multi-agent development workflow, which enables running multiple AI coding agents (Claude, Cursor, Copilot, etc.) simultaneously on the same codebase without conflicts.

## Overview

The multi-agent system provides:

- **Isolation**: Each agent works in its own git worktree
- **Coordination**: Shared notes and task management for inter-agent communication
- **Monitoring**: Live status dashboard showing all agents
- **Workflow Tools**: Diff, merge preview, and rebase checking across agents

## Architecture

```
my-project/                    # Main repository (Agent 1)
├── .worktrees/
│   ├── agent-2/              # Agent 2 worktree
│   ├── agent-3/              # Agent 3 worktree
│   └── agent-4/              # Agent 4 worktree
└── .claude/
    └── local-agents/         # Coordination files (git-ignored)
        ├── shared-notes.md   # Inter-agent communication
        └── tasks/
            ├── agent-1.md    # Task for agent 1
            ├── agent-2.md    # Task for agent 2
            └── ...
```

## Getting Started

### 1. Start a Zellij Session

The `agent.kdl` Zellij layout provides a complete multi-agent environment:

```bash
# Using the zc function (auto-detects available AI tool)
zc

# Or explicitly with claude
zcc
```

### 2. Zellij Layout Tabs

| Tab | Purpose |
|-----|---------|
| **Agent 1+2** | Main development with two agents + live status board |
| **Agent 3+4** | Additional agent sessions |
| **Shell+Logs** | General shell and log viewing |
| **Git** | Lazygit + git shell |
| **Tests** | Test runner |
| **Workflow** | Multi-agent tools (diff, merge preview, tasks) |
| **Neovim** | Editor |

### 3. Creating Agent Worktrees

When you start Agent 2+ in Zellij, `ensure-agent-worktree` runs automatically and prompts:

```
┌─────────────────────────────────────────────────────────
│ Agent 2 - No worktree exists yet
│ Main repo: main
└─────────────────────────────────────────────────────────

[C]reate worktree, or use [M]ain repo?
```

For existing worktrees:

```
┌─────────────────────────────────────────────────────────
│ Agent 2 worktree exists
│ Worktree: feature-branch (dirty)
│ Main repo: main
└─────────────────────────────────────────────────────────

[C]ontinue, [S]tart fresh, or use [M]ain repo?
```

### 4. Branch Selection (Start Fresh)

When starting fresh, you have multiple options:

```
[S]earch, [N]ew, [A]gent-2, [D]etached, [B]ack?
```

| Option | Description |
|--------|-------------|
| **S** | Fuzzy search existing branches with fzf |
| **N** | Create a new custom-named branch |
| **A** | Quick create `agent-N` branch from main |
| **D** | Detached HEAD from main (no branch) |
| **B** | Go back to previous menu |

---

## CLI Commands

### agent-status

Live dashboard showing all agent worktrees.

```bash
agent-status           # Show status once
agent-status --watch   # Live updating (every 2s)
```

**Output includes:**
- Current branch for each agent
- Dirty indicator (`*`) for uncommitted changes
- Ahead/behind counts vs remote
- Last commit message
- Assigned task (if any)
- Shared notes summary

### agent-diff

View combined diff of all agent worktrees against the main branch.

```bash
agent-diff           # Full diff (uses delta if available)
agent-diff --stat    # Show diffstat only
agent-diff --files   # Show only changed file names
```

### agent-rebase-check

Check if agent worktrees need rebasing against the main branch.

```bash
agent-rebase-check          # Check current state
agent-rebase-check --fetch  # Fetch from remote first
```

**Output shows:**
- ✓ Up to date
- ! N commits behind (warning)
- ✗ N commits behind - rebase recommended (error)
- Files that may conflict

### agent-merge-preview

Preview potential merge conflicts.

```bash
agent-merge-preview      # Show file overlap between all agents
agent-merge-preview 2    # Simulate merging agent-2 into main
```

**File overlap analysis** identifies files modified by multiple agents that could cause merge conflicts.

### agent-task

Manage task assignments for agents.

```bash
agent-task                    # Show all agent tasks
agent-task 2                  # Show task for agent 2
agent-task 2 "Build auth UI"  # Set task for agent 2
agent-task 2 -e               # Edit task in $EDITOR
agent-task 2 -c               # Clear task
```

Tasks are stored in `.claude/local-agents/tasks/agent-N.md`.

### agent-handoff

Hand off work from one agent to another.

```bash
agent-handoff 2 3                           # Hand off from agent 2 to 3
agent-handoff 2 3 "Completed UI, need API"  # With message
```

**Handoff process:**
1. Prompts to create WIP commit if uncommitted changes exist
2. Adds handoff entry to shared notes
3. Copies task file to new agent
4. Provides instructions for continuing

### ensure-agent-worktree

Create or manage agent worktrees (usually called automatically by Zellij).

```bash
ensure-agent-worktree 2    # Ensure agent-2 worktree exists
ensure-agent-worktree 3    # Ensure agent-3 worktree exists
```

**Features:**
- Interactive prompts for worktree creation
- Branch selection with fuzzy search
- Automatic dependency installation (npm, yarn, pnpm, uv)
- Creates `.claude/worktree-context.md` for agent context

---

## Fish Functions

### cda

Quick navigation to agent worktrees.

```bash
cda      # Go to main repo (agent 1)
cda 1    # Go to main repo
cda 2    # Go to agent-2 worktree
cda 3    # Go to agent-3 worktree
```

### cdwt

Alternative worktree navigation (also works for non-agent worktrees).

```bash
cdwt           # Interactive selection with fzf
cdwt 2         # Go to agent-2 worktree
cdwt feature   # Go to worktree matching "feature"
```

---

## Coordination & Communication

### Shared Notes

Agents can communicate via `.claude/local-agents/shared-notes.md`:

```markdown
## [Agent 2] 2025-01-12 14:30 - Found authentication bug

The OAuth token refresh logic has a race condition in `src/auth/token.ts:45`.
Need to add mutex lock before proceeding with the fix.

---

## [Agent 3] 2025-01-12 14:45 - API endpoints complete

Finished implementing all REST endpoints. Agent 2 can now integrate
the auth UI with the backend.

---
```

**Best practices:**
- Check shared notes before starting work
- Document important discoveries
- Note files you're actively modifying
- Add handoff context when switching agents

### File Locking Convention

To prevent conflicts on specific files:

```markdown
## [Agent 2] LOCK: src/components/Auth.tsx
Working on authentication refactor. Expected completion: ~30 min
```

Remove lock entries when done.

### Global Claude Instructions

The global `~/.claude/CLAUDE.md` provides instructions to Claude about multi-agent collaboration. It's automatically symlinked from `profiles/{profile}/files/dotfiles/claude/CLAUDE.md`.

---

## Workflow Examples

### Example 1: Parallel Feature Development

```bash
# Agent 1: Working on backend API
# Agent 2: Working on frontend UI

# Check for conflicts before merging
agent-merge-preview

# If no conflicts, merge agent-2's branch
git checkout main
git merge agent-2-feature
```

### Example 2: Handoff Between Agents

```bash
# Agent 2 finished initial work, handing off to Agent 3
agent-handoff 2 3 "Completed auth UI components. Need to:
- Add form validation
- Connect to API endpoints
- Add error handling"

# Agent 3 picks up the work
cda 3
# Review shared notes and task
agent-task 3
```

### Example 3: Investigating a Bug with Multiple Agents

```bash
# Assign tasks to different agents
agent-task 1 "Reproduce bug and write failing test"
agent-task 2 "Investigate auth token handling"
agent-task 3 "Check database query performance"

# Monitor progress
agent-status --watch

# Check findings in shared notes
cat .claude/local-agents/shared-notes.md
```

### Example 4: Rebase Before Merging

```bash
# Check if agents need to rebase
agent-rebase-check --fetch

# If agent-2 is behind, rebase it
cda 2
git rebase origin/main

# Return to main
cda 1
```

---

## Tips & Best Practices

1. **Use Agent 1 for coordination** - Keep main repo clean, use it for reviewing and merging

2. **Commit frequently** - Agents should commit often to preserve work and enable handoffs

3. **Check overlap before deep work** - Run `agent-merge-preview` to see if you're about to conflict

4. **Use detached HEAD for exploration** - When just exploring/researching, use detached mode to avoid branch clutter

5. **Name branches descriptively** - Instead of `agent-2`, use `agent-2-auth-refactor` for clarity

6. **Clean up old worktrees** - Remove worktrees when done:
   ```bash
   git worktree remove .worktrees/agent-2
   ```

7. **Use shared notes liberally** - Better to over-communicate than have agents duplicate work

---

## Troubleshooting

### Worktree shows "dirty" but I committed everything

Check for untracked files:
```bash
git -C .worktrees/agent-2 status
```

### Agent can't find commands

The `agent-*` scripts need to be in PATH. Run the dotfiles playbook:
```bash
./dotfiles install dotfiles
```

Or manually symlink:
```bash
ln -s ~/path/to/dotfiles/files/bin/agent-* ~/.local/bin/
```

### Merge preview fails

Ensure you have enough disk space for the temporary clone. The merge preview creates a temporary directory to safely test merges.

### fzf not working in branch selection

Install fzf:
```bash
brew install fzf
```

---

# Adding a New AI Coding Agent

The dotfiles system integrates multiple AI coding agents (Claude Code, Cursor, Gemini, Codex, Copilot) with Zellij layouts.

## Installation Methods

### Via Homebrew (preferred)

Add to `profiles/common/config.yml` or profile-specific files:
```yaml
brew_packages:
  - {agent-name}
# OR
cask_packages:
  - name: {agent-name}
```

Most agents (claude-code, copilot-cli, codex) are installed this way.

### Via npx (if no brew package exists)

Create a wrapper function in `profiles/common/files/dotfiles/config/fish/functions/{agent}.fish`:
```fish
function {agent}
    npx @package/agent-cli -- $argv
end
```
Example: Gemini uses `npx @google/gemini-cli`

### Via install script

Create an Ansible role similar to `roles/cursor_cli/` that installs the agent.

## Integration Steps

1. **Create the Zellij layout** (`profiles/common/files/dotfiles/config/zellij/layouts/{agent}.kdl`):
   - Copy an existing layout (e.g., `copilot.kdl`) as a template
   - Replace agent command references
   - Follow the standard tab structure (Agent sessions, Shell+Logs, Git, Tests, Neovim)

2. **Add Zellij profile function** (`profiles/common/files/dotfiles/config/fish/conf.d/zellij.fish`):
   ```fish
   function zx{letter} --description 'Open zellij with {agent} layout'
       zellij --layout {agent} attach --create (__zellij_get_session_name)-{agent}
   end
   ```

3. **Update the auto-detect function** in the same file:
   - Add the agent to the `zc` function's priority chain
   - Priority order: `claude > cursor > gemini > codex > copilot`

4. **Test**: Run the agent command, `zx{letter}`, and `zc` to verify

## Current Agents

| Agent | Function | Installation | Command |
|-------|----------|--------------|---------|
| Claude Code | `zcc` | brew cask | `claude` |
| Cursor | `zcu` | Ansible role | `agent` |
| Gemini | `zxg` | npx wrapper | `gemini` |
| Codex | `zco` | brew | `codex` |
| Copilot | `zcp` | brew | `copilot` |
