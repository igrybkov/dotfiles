# Global Claude Code Instructions

## Task Context

When starting work in a worktree, check if `.claude/task.local.md` exists. This file contains the GitHub issue details (title, link, description) that this branch is meant to address. Read it first to understand the task context.

## Multi-Agent Collaboration

When working in a multi-agent environment (multiple Claude instances in separate worktrees), use the handoff system for preserving context between sessions.

### Branch Handoffs

Each branch has its own handoff file that preserves context for whoever continues the work. Handoffs are stored centrally in the main repo at `.claude/handoffs/{branch}.md` and symlinked into worktrees at `.claude/HANDOFF.md`.

**When starting work on a branch:**
1. Check if `.claude/HANDOFF.md` exists and has content
2. Read the handoff to understand prior context
3. Consider clearing it after reading: `hive handoff clear`

**When stopping work or handing off:**
1. Use the `/handoff` skill to save your work state
2. Or run `hive handoff create` from the command line
3. The handoff file captures: what was done, what remains, key files, and gotchas

**Handoff commands:**
```bash
hive handoff              # Show all active handoffs
hive handoff show         # Show handoff for current branch
hive handoff create       # Create handoff for current branch
hive handoff edit         # Edit handoff in $EDITOR
hive handoff clear        # Clear handoff for current branch
hive handoff list         # List all handoff files
hive handoff clean        # Remove orphaned handoffs
```

### Shared Notes (Optional)

For cross-branch coordination (file locking, architectural decisions affecting multiple branches), use the shared notes file at `.claude/local-agents/shared-notes.md` in the main repository.

**When to use shared notes:**
- Note files you're actively modifying to avoid conflicts across branches
- Record blockers or questions that need human intervention
- Share architectural decisions affecting multiple branches

**Format for entries:**
```markdown
## [Branch: feature-auth] YYYY-MM-DD HH:MM - Brief Title

Your notes here. Be concise but informative.

- Key finding 1
- Key finding 2
```

### File Locking Convention

If you need exclusive access to a file across branches, create a lock entry in shared notes:
```markdown
## LOCK: src/components/Auth.tsx
**Branch:** feature-auth
Working on authentication refactor. Expected completion: ~30 min
```

Remove the lock entry when done.

## MCP Server Usage

When working with MCP servers through `meta-mcp`, always verify tool schemas before making calls. Do not guess parameter names based on conventions.

### Required Workflow

1. **Discover servers**: Use `list_servers` to find available MCP servers
2. **Discover tools**: Use `get_server_tools` with `summary_only: true` for lightweight discovery
3. **Get full schema**: Use `get_server_tools` with specific tool names to fetch full parameter schemas
4. **Call the tool**: Use `call_tool` with the correct parameters from the schema

### Example

```
# Wrong - guessing parameter names
call_tool(server: "apple-calendar", tool: "list_events", arguments: {start: "...", end: "..."})

# Right - verify schema first
get_server_tools(server: "apple-calendar", tools: ["list_events"])
# Schema shows: start_date, end_date, calendar_name
call_tool(server: "apple-calendar", tool: "list_events", arguments: {start_date: "...", end_date: "..."})
```

### Why This Matters

- Parameter names vary between tools (`start` vs `start_date`, `query` vs `search_term`)
- Some parameters are required, others optional
- Schema reveals expected formats and constraints
- Guessing leads to cryptic errors or silent failures
