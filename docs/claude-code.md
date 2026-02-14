# Claude Code Configuration Guide

This guide documents the Claude Code configuration managed by this dotfiles repository.

## Overview

Claude Code configuration is managed in two parts:

1. **Files** (commands, agents, skills, hooks, etc.) - managed via the `dotfiles` role
2. **Settings** (`~/.claude.json`, `~/.claude/settings.json`) - managed via the `coding_agents` role

### Directory Mapping

| Source Directory | Destination |
|-----------------|-------------|
| `profiles/{profile}/files/dotfiles/claude/commands/` | `~/.claude/commands/` |
| `profiles/{profile}/files/agents/` | `~/.claude/agents/`, `~/.cursor/agents/` (configurable) |
| `profiles/{profile}/files/skills/` | `~/.claude/skills/`, `~/.cursor/skills/` (configurable) |
| `profiles/{profile}/files/dotfiles/claude/hooks/` | `~/.claude/hooks/` |
| `profiles/{profile}/files/dotfiles/claude/output-styles/` | `~/.claude/output-styles/` |
| `profiles/{profile}/files/dotfiles/claude/CLAUDE.md` | `~/.claude/CLAUDE.md` |
| `profiles/{profile}/files/dotfiles/claude/statusline-command.py` | `~/.claude/statusline-command.py` |

Files from multiple profiles are merged (symlinked) into the destination.

**Note**: Skills and agents are now located in generic `files/skills/` and `files/agents/` directories (not under `dotfiles/claude/`) and can be symlinked to multiple agent destinations (Claude, Cursor, etc.) via configuration. See the [Skills and Agents](#skills-and-agents) section below.

---

## Slash Commands

Slash commands are user-defined prompts that can be invoked with `/command-name` in Claude Code.

### Directory Structure

```
profiles/{profile}/files/dotfiles/claude/commands/
└── commit.md              # Invoked with /commit
```

### Creating a Command

Create a markdown file with frontmatter and instructions:

```markdown
---
description: Short description shown in command list
allowed-tools: Bash(git status:*), Bash(git diff:*), Read, Edit
---

## Context

- Current status: !`git status`
- File content: !`cat package.json`

## Instructions

Your prompt instructions here. The context section uses !`command`
syntax to inject command output into the prompt.
```

### Frontmatter Options

| Field | Description |
|-------|-------------|
| `description` | Short description shown when listing commands |
| `allowed-tools` | Tools the command can use without permission prompts |

### Dynamic Context

Use backtick syntax to inject command output:
- `!`git status`` - Injects git status output
- `!`cat file.txt`` - Injects file contents

**Official docs:** https://docs.anthropic.com/en/docs/claude-code/slash-commands

---

## Skills and Agents

Skills and agents are now stored in generic locations and can be shared across multiple AI coding agents (Claude Code, Cursor, etc.).

### Directory Structure

```
profiles/{profile}/files/
├── skills/                # Skills directory (shared across agents)
│   └── git-commit/
│       └── SKILL.md
└── agents/                 # Agents directory (shared across agents)
    └── productivity-coach.md
```

### Configuration

Configure which agent destinations should receive skills and agents in your profile's `config.yml`:

```yaml
skill_folders:
  - ~/.claude/skills
  - ~/.cursor/skills

agent_folders:
  - ~/.claude/agents
  - ~/.cursor/agents
```

Skills and agents from all profiles are merged into each configured destination, allowing you to share the same skills and agents across multiple AI coding tools.

---

## Sub-Agents

Sub-agents are specialized agents that can be spawned using the `Task` tool. They run autonomously and return results.

### Directory Structure

```
profiles/{profile}/files/agents/
└── code-reviewer.md       # Referenced as subagent_type="code-reviewer"
```

### Creating a Sub-Agent

Create a markdown file defining the agent's behavior:

```markdown
---
description: Reviews code for best practices and potential issues
tools: Read, Grep, Glob
---

You are a code review agent. When given code to review:

1. Check for common issues (security, performance, readability)
2. Verify adherence to project conventions
3. Suggest improvements with specific code examples

Return a structured review with:
- Summary of findings
- Critical issues (if any)
- Suggestions for improvement
```

### Frontmatter Options

| Field | Description |
|-------|-------------|
| `description` | Description shown in agent selection and helps Claude choose when to use it |
| `tools` | Comma-separated list of tools available to the agent |

### Using Sub-Agents

Sub-agents are invoked via the `Task` tool:

```
Task(subagent_type="code-reviewer", prompt="Review the changes in src/auth.ts")
```

Claude Code will automatically use appropriate sub-agents when they match the task at hand.

### Built-in Agent Types

Claude Code includes these built-in agent types:

| Type | Purpose |
|------|---------|
| `general-purpose` | Multi-step tasks, code search |
| `Explore` | Codebase exploration (quick/medium/very thorough) |
| `Plan` | Implementation planning and architecture |
| `claude-code-guide` | Questions about Claude Code itself |

**Official docs:** https://docs.anthropic.com/en/docs/claude-code/sub-agents

---

## Hooks

Hooks are scripts that run in response to Claude Code events (Stop, PreToolUse, etc.).

### Directory Structure

```
profiles/{profile}/files/dotfiles/claude/hooks/
└── auto-rename-session.py   # Stop hook example
```

### Creating a Hook

Create an executable script (Python, Bash, etc.):

```python
#!/usr/bin/env python3
"""Example Stop hook that runs when Claude finishes responding."""
import json
import sys

# Read hook input from stdin
input_data = json.load(sys.stdin)
session_id = input_data.get("session_id", "")
transcript_path = input_data.get("transcript_path", "")
stop_hook_active = input_data.get("stop_hook_active", False)

# Prevent infinite loops
if stop_hook_active:
    print(json.dumps({"decision": None}))
    sys.exit(0)

# Your hook logic here...

# Return decision
print(json.dumps({"decision": None}))  # None = allow stop, "block" = prevent stop
sys.exit(0)
```

### Registering Hooks

Configure hooks in your profile's `config.yml`:

```yaml
claude_settings_json:
  hooks:
    Stop:
      - hooks:
          - type: command
            command: ~/.claude/hooks/auto-rename-session.py
```

### Available Hook Events

| Event | Description |
|-------|-------------|
| `Stop` | When Claude finishes responding |
| `PreToolUse` | Before a tool is executed |
| `PostToolUse` | After a tool completes |
| `SessionStart` | When a session starts |
| `UserPromptSubmit` | Before Claude processes user prompt |

**Official docs:** https://docs.anthropic.com/en/docs/claude-code/hooks

---

## Settings Management

The `coding_agents` role manages two settings files:

### ~/.claude.json

Application-level settings:

```yaml
# In profile config.yml
claude_json_settings:
  hasCompletedOnboarding: true
  autoUpdaterStatus: disabled
  projects:
    default:
      allowedTools:
        - Bash(git:*)
        - Read
        - Edit
```

### ~/.claude/settings.json

UI and behavior settings:

```yaml
# In profile config.yml
claude_settings_json:
  statusLine:
    type: command
    command: ~/.claude/statusline-command.py
  attribution:
    commit: ""
    pr: ""
  hooks:
    Stop:
      - hooks:
          - type: command
            command: ~/.claude/hooks/my-hook.py
```

Settings are recursively merged with existing content.

### Common Settings

| Setting | File | Description |
|---------|------|-------------|
| `hasCompletedOnboarding` | `.claude.json` | Skip onboarding prompts |
| `autoUpdaterStatus` | `.claude.json` | `enabled`, `disabled`, or `check_only` |
| `projects.default.allowedTools` | `.claude.json` | Tools allowed without prompts |
| `statusLine` | `settings.json` | Custom status line command |
| `hooks` | `settings.json` | Hook configurations |

**Official docs:** https://docs.anthropic.com/en/docs/claude-code/settings

---

## Installation

Run the dotfiles installer:

```bash
./dotfiles install dotfiles claude-code
```

The `dotfiles` tag symlinks the files, and `claude-code` manages the settings.

---

## File Locations

| What | Source | Destination |
|------|--------|-------------|
| Commands | `profiles/*/files/dotfiles/claude/commands/*.md` | `~/.claude/commands/` |
| Agents | `profiles/*/files/agents/*.md` | `~/.claude/agents/`, `~/.cursor/agents/` (configurable) |
| Skills | `profiles/*/files/skills/*/` | `~/.claude/skills/`, `~/.cursor/skills/` (configurable) |
| Hooks | `profiles/*/files/dotfiles/claude/hooks/*` | `~/.claude/hooks/` |
| Output styles | `profiles/*/files/dotfiles/claude/output-styles/*.md` | `~/.claude/output-styles/` |
| CLAUDE.md | `profiles/*/files/dotfiles/claude/CLAUDE.md` | `~/.claude/CLAUDE.md` |
| App settings | Ansible variables | `~/.claude.json` |
| UI settings | Ansible variables | `~/.claude/settings.json` |

---

## Examples

### Example: Git Commit Command

`profiles/{profile}/files/dotfiles/claude/commands/commit.md`:

```markdown
---
description: Create a git commit with conventional message
allowed-tools: Bash(git status:*), Bash(git diff:*), Bash(git log:*), Bash(git add:*), Bash(git commit:*)
---

## Context

- Current git status: !`git status`
- Staged changes: !`git diff --cached`
- Recent commits: !`git log --oneline -5`

## Instructions

Create a git commit following conventional commit format...
```

### Example: Code Review Agent

`profiles/{profile}/files/agents/code-reviewer.md`:

```markdown
---
description: Reviews code changes for issues and improvements
tools: Read, Grep, Glob, Bash(git diff:*)
---

You are a thorough code reviewer. Analyze the provided code for:

1. **Correctness**: Logic errors, edge cases, potential bugs
2. **Security**: Input validation, injection risks, auth issues
3. **Performance**: Inefficient algorithms, unnecessary operations
4. **Maintainability**: Code clarity, naming, documentation

Provide actionable feedback with specific line references.
```

---

## Official Documentation

- **Claude Code Overview:** https://docs.anthropic.com/en/docs/claude-code/overview
- **Slash Commands:** https://docs.anthropic.com/en/docs/claude-code/slash-commands
- **Sub-Agents:** https://docs.anthropic.com/en/docs/claude-code/sub-agents
- **Settings:** https://docs.anthropic.com/en/docs/claude-code/settings
- **CLAUDE.md Files:** https://docs.anthropic.com/en/docs/claude-code/memory
- **Hooks:** https://docs.anthropic.com/en/docs/claude-code/hooks
- **MCP Servers:** https://docs.anthropic.com/en/docs/claude-code/mcp-servers
