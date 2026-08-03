# Global Claude Code Instructions

## Writing Style

Avoid overly technical jargon and long-winded breakdowns. Explain things knowing I'm an experienced software engineer with a tired brain who needs low cognitive load. Use ASC-STE100 Simplified Technical English as a style model: short sentences, one idea per sentence, plain verbs.

Avoid these AI writing tics: antithesis, corrective negation, paragraph pinning, parataxis, summary beats, rhetorical crutches, negative parallelisms, negative anaphoras, contrasting pairs, rule of three, em dashes, throat-clearing openers, landing sentences, setup/payoff constructions, parallel sentence structures within a paragraph, stacked noun phrases, filler intensifiers (genuinely, really, truly, actually), corporate-register verbs (leverage, underscore, reflect), nominalization, hedging qualifiers, performed enthusiasm. Vary sentence length unpredictably. Write for the spoken voice.

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

When working with MCP servers through `mcp-hub`, always verify tool schemas before making calls. Do not guess parameter names based on conventions.

### Required Workflow

1. **Discover servers**: Use `list_servers` to browse the catalog (or check the hub's startup `instructions` — it already lists configured servers)
2. **Find capabilities**: Use `search` to match a task to tools/servers by keyword
3. **Discover tools**: Use `get_server_tools` with `summary_only: true` for lightweight discovery
4. **Get full schema**: Use `get_server_tools` with specific tool names to fetch full parameter schemas
5. **Call the tool**: Use `call_tool` with the correct parameters from the schema

For shell scripting (including calling MCP tools from Bash), use the `mcp-hub` CLI:

```bash
mcp-hub list --filter monitoring
mcp-hub tools github --summary
mcp-hub call github listIssues --args '{"repo": "my/repo"}'
```

## MCP Server Secrets

When adding a new stdio MCP server that needs secrets (tokens, API keys), use `secret_env:` rather than `env:` with `vault_secret` lookups. The former resolves secrets at spawn time so the rendered config is commit-safe; the latter bakes plaintext secrets into `~/.config/mcp-hub/servers.json` and similar files.

```yaml
mcp_servers:
  - name: my-server
    command: my-server-bin
    env:
      LOG_LEVEL: info                                # non-secret, stays as-is
    secret_env:
      API_TOKEN: mcp_secrets.myservice.token       # vault key path, resolved at spawn
```

URL-based servers have no spawn-time hook to wrap (HTTP headers are just static values in the rendered config, unlike a stdio command), so header secrets are always resolved at install time and written into the file — prefer `secret_headers:` over hand-writing a `{{ lookup('vault_secret', ...) }}` expression directly in `headers:`; both resolve the same way, but `secret_headers:` uses the same bare key-path syntax as `secret_env:` and is validated (a header name can't appear in both `headers:` and `secret_headers:`). The rendered config file is still written mode `0600` since it carries a resolved value.

```yaml
mcp_servers:
  - name: my-remote-server
    type: http
    url: "https://example.com/api/mcp"
    secret_headers:
      Authorization: mcp_secrets.myservice.bearer    # resolved at install time
```

The secret must hold the complete header value (store `Bearer <token>`, not just the token).

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
