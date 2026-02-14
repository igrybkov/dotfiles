---
name: git-commit
description: Create git commits split by feature/logical unit with automatic task ID detection from branch names. Use when user asks to commit changes, create commits, or split changes into multiple commits.
allowed-tools:
  - Bash(git status:*)
  - Bash(git diff:*)
  - Bash(git log:*)
  - Bash(git branch:*)
  - Bash(git add:*)
  - Bash(git commit:*)
  - Read
  - Glob
---

# Commit Code Skill

Create well-organized git commits split by logical units with automatic task ID prefixing.

## Workflow

1. **Gather metadata (parallel)** - Run all these commands in a single message with parallel tool calls:
   - `git branch --show-current` - Get current branch for task ID extraction
   - `git log main..HEAD --oneline --max-count=10` - Recent commits for task ID pattern
   - `git status` - List all modified, staged, and untracked files
2. **Extract task ID** - Parse branch name or recent commits for task ID pattern
3. **Inspect changes selectively** - Based on file list from status:
   - For small/focused changes: read diff for specific files with `git diff -- <file>`
   - For config/simple changes: may not need diff at all
   - Avoid running `git diff` without file paths on large changesets
4. **Group changes** - Organize files by logical feature/purpose
5. **Create commits** - Make separate commits for each logical unit

## Task ID Detection

Check these sources in order:

1. **Branch name patterns**:
   - `feature/AB-123-description` → `AB-123`
   - `AB-123/description` → `AB-123`
   - `fix/AB-123` → `AB-123`
   - Pattern: uppercase letters + hyphen + numbers (e.g., `PROJ-1234`, `AB-1`)

2. **Recent commits on branch** (not yet in main):
   ```bash
   git log main..HEAD --oneline
   ```
   Look for existing task ID prefixes in commit messages.

3. **If no task ID found**: Proceed without prefix, but mention this to the user.

## Commit Message Format

Use conventional commit format:

```
<TASK-ID>: <type>(<scope>): <description>

<optional body>
```

- **With task ID**: `AB-123: feat(auth): add login form validation`
- **Without task ID**: `feat(auth): add login form validation`

**Types** (required):
- `feat` - New feature
- `fix` - Bug fix
- `docs` - Documentation only
- `style` - Formatting, no code change
- `refactor` - Code change that neither fixes a bug nor adds a feature
- `test` - Adding or updating tests
- `chore` - Maintenance tasks, dependencies
- `perf` - Performance improvement
- `ci` - CI/CD changes
- `build` - Build system changes

**Scope** (optional): Component or area affected, e.g., `auth`, `api`, `ui`

## Grouping Strategy

Split commits by:
- **Feature boundaries** - Related functionality together
- **Layer boundaries** - Frontend/backend separately when logical
- **File type** - Config changes, dependencies, code changes

Do NOT split:
- Tightly coupled changes that would break if separated
- Single logical change across multiple files
- **Tests and the code they test** - Always commit tests together with the implementation they cover (e.g., `auth.py` and `test_auth.py` in one commit)

## Example Workflow

```bash
# 1. Gather metadata (run these in PARALLEL - single message, multiple tool calls)
git branch --show-current           # → feature/PROJ-123-user-auth
git log main..HEAD --oneline --max-count=10
git status                          # → lists modified files

# 2. Inspect specific files as needed (based on status output)
git diff -- src/auth/service.ts     # Only diff files you need to understand
git diff --staged -- src/auth/types.ts

# 3. Stage and commit logically grouped changes
git add src/auth/*.ts
git commit -m "PROJ-123: feat(auth): implement user authentication service"

git add src/components/LoginForm.tsx
git commit -m "PROJ-123: feat(ui): add login form component"
```

## Important Notes

- Always show the user what commits will be created before executing
- Use `git add -p` for partial file staging when needed
- Never force push or amend pushed commits without explicit permission
- Never push the branch unless explicitly asked
- If changes are too intertwined to split, create a single well-described commit
