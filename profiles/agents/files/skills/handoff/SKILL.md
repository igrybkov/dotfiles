---
name: handoff
description: Save work state and context for handoff to another session. Use when stopping work, completing a unit of work, or handing off to another agent/session.
allowed-tools:
  - Bash(git status:*)
  - Bash(git diff:*)
  - Bash(git log:*)
  - Bash(git branch:*)
  - Bash(git add:*)
  - Bash(git commit:*)
  - Bash(git rev-parse:*)
  - Read
  - Write
  - Glob
---

# Handoff Skill

Save your current work state and context so another session (or your future self) can continue seamlessly.

## When to Use

- Completing a unit of work before moving on
- Stopping work mid-task (end of day, switching context)
- Explicitly asked to hand off work
- Before a long-running operation where you might lose context

## Workflow

### 1. Gather Context

```bash
# Get current branch name
git branch --show-current

# Check for uncommitted changes
git status --short

# Get recent commits on this branch (not in main)
git log main..HEAD --oneline --max-count=10

# Get diff summary
git diff --stat
git diff --staged --stat
```

### 2. Determine Handoff File Location

The handoff file lives in the **main repository** (not the worktree):

```
{main_repo}/.claude/handoffs/{branch-name}.md
```

To find the main repo from a worktree:
```bash
# This returns the main repo path even from a worktree
git rev-parse --path-format=absolute --git-common-dir | sed 's|/.git$||'
```

If you're in the main repo (not a worktree), use `.claude/handoffs/main.md`.

### 3. Commit Changes (if any)

If there are uncommitted changes, commit them with a descriptive message:

```bash
git add -A
git commit -m "WIP: [describe current state]

Handoff: [brief summary of what's being handed off]"
```

Use conventional commit format when appropriate. Include "WIP:" prefix if work is incomplete.

### 4. Create/Update Handoff File

Write to `{main_repo}/.claude/handoffs/{branch}.md` with this structure:

```markdown
# Handoff: {Branch Name}

**Created:** YYYY-MM-DD HH:MM
**Last Commit:** {hash} {message}
**Status:** [In Progress | Ready for Review | Blocked | Complete]

## Summary
[1-2 sentence overview of the work on this branch]

## Accomplished
- [What was completed]
- [Key changes made]
- [Problems solved]

## Remaining Work
1. [Next step]
2. [Following step]
3. [etc.]

## Current State
- [ ] Tests passing
- [ ] Build succeeds
- [ ] Linting clean
- [x] Code compiles

## Key Files
- `path/to/file.ts` - [what it does/why it matters]
- `path/to/other.ts` - [context]

## Context & Gotchas
- [Important context the next person needs]
- [Gotchas or tricky parts]
- [Dependencies or blockers]
- [Decisions made and why]

## How to Continue
```bash
# Navigate to worktree
cd {worktree_path}

# Or create worktree if needed
hive wt create {branch}

# Check current state
git status
npm test  # or equivalent

# Continue from here...
```
```

### 5. Confirm to User

After creating the handoff:

1. Show the path to the handoff file
2. Summarize what was saved
3. Remind about `hive handoff show` to view it later

## Important Notes

- **Do NOT push** unless explicitly asked - handoffs are local artifacts
- **Always commit first** - uncommitted changes can be lost
- **Be specific** in "Remaining Work" - vague items are unhelpful
- **Include the "why"** - context about decisions is invaluable
- **Update, don't recreate** - if handoff exists, update relevant sections
- The handoff file is gitignored and stays local to the machine

## Example Interaction

User: "I need to stop for today, please hand off"

Agent:
1. Runs `git status` and `git diff --stat`
2. Commits any uncommitted changes with descriptive message
3. Runs `git log main..HEAD --oneline` to see branch history
4. Creates/updates `.claude/handoffs/{branch}.md` in main repo
5. Responds with summary:

> Handoff saved to `.claude/handoffs/feature-auth.md`
>
> **Committed:** "WIP: auth service with token refresh"
>
> **Summary:** Implemented OAuth2 login flow, form validation complete. Need to add database migrations and integration tests.
>
> View with: `hive handoff show feature-auth`
