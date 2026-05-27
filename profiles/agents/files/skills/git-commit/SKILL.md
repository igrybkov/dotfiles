---
name: git-commit
description: Create well-organized git commits with automatic task ID detection. Defaults to a single commit; only splits when changes are genuinely unrelated. Use when user asks to commit changes or create commits.
allowed-tools:
  - Bash(git status:*)
  - Bash(git diff:*)
  - Bash(git log:*)
  - Bash(git branch:*)
  - Bash(git add:*)
  - Bash(git commit:*)
  - Bash(git -C:*)
  - Bash(~/.claude/skills/git-commit/git-task-id:*)
  - Bash(~/.cursor/skills/git-commit/git-task-id:*)
  - Bash(find:*)
  - Read
  - Glob
---

# Commit Code Skill

Create well-organized git commits with automatic task ID prefixing. **Default to a single commit.** Only split into multiple commits when changes are genuinely unrelated.

## Workflow

1. **Gather metadata (parallel)** - Run all these commands in a single message with parallel tool calls:
   - `${CLAUDE_SKILL_DIR}/git-task-id -v` - Detect probable task ID from `.claude/task.local.md`, branch name, and recent commits. See [Task ID Detection](#task-id-detection).
   - `git status` - List all modified, staged, and untracked files
   - Nested-repo scan (see [Nested Repositories](#nested-repositories))
2. **Inspect changes selectively** - Based on file list from status:
   - For small/focused changes: read diff for specific files with `git diff -- <file>`
   - For config/simple changes: may not need diff at all
   - Avoid running `git diff` without file paths on large changesets
3. **Decide whether to split** - Default is a single commit. Only split if changes are genuinely unrelated (see Grouping Strategy)
4. **Create commit(s)** - Stage and commit, preferring one commit unless splitting is clearly warranted
5. **Handle nested repos** - If the scan found nested repos with changes, ask the user whether to commit those too (see [Nested Repositories](#nested-repositories))

## Task ID Detection

Use the `git-task-id` helper bundled with this skill (at `${CLAUDE_SKILL_DIR}/git-task-id`). It scans, in priority order:

1. `.claude/task.local.md` (per-worktree task note written when the worktree was created)
2. Current branch name (e.g. `feature/AB-123-description` → `AB-123`)
3. Recent commit subjects not yet on the base branch (`main` or `master`)

Diff hunks are deliberately not scanned — TODO comments and in-source ticket references describe other work, not the current change.

```bash
${CLAUDE_SKILL_DIR}/git-task-id              # prints the detected ID, or exits 1
${CLAUDE_SKILL_DIR}/git-task-id -v           # also prints the source on stderr
${CLAUDE_SKILL_DIR}/git-task-id --all -v     # all ranked candidates per source (use when sources disagree)
```

The default regex is `[A-Z][A-Z0-9]+-[0-9]+` (Jira-style); override with `GIT_TASK_ID_REGEX`.

If exit status is 1, no ID was found — proceed without a prefix and mention it to the user.

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

**One commit is the default.** Most changesets belong in a single commit. Do not look for ways to split — only split when you have a clear reason.

### When NOT to split (keep in one commit)

- **Tests and the code they test** - ALWAYS commit tests together with the implementation they cover. Never use the `test` type for tests that accompany a feature or fix — use `feat` or `fix` and include the tests in the same commit.
- A feature and its associated config/type/schema changes
- A refactor that touches multiple files for the same reason
- Tightly coupled changes that would break if separated
- Any single logical change that spans multiple files

### When to split (multiple commits)

Only split when ALL of these are true:
- Changes serve **completely different purposes** (e.g., an unrelated bug fix + a new feature)
- Each commit could be **independently reverted** without breaking the other
- A reviewer would naturally **review them as separate units**

If in doubt, use a single commit.

## Nested Repositories

The current working tree may contain independent nested git repos (e.g., gitignored subdirectories that are separately versioned — see `profiles/private/*` in this dotfiles repo). Their changes do **not** show up in the parent repo's `git status`, so they're easy to miss.

### Scan

Run as part of the parallel metadata gathering in step 1. Lists each nested repo that has uncommitted or untracked changes, with a short status:

```bash
find . -mindepth 2 -name .git -type d -prune -execdir sh -c '
  changes=$(git status --porcelain)
  if [ -n "$changes" ]; then
    printf "==> %s\n%s\n" "$PWD" "$changes"
  fi
' \;
```

Notes on the command:
- `-mindepth 2` skips the current repo's own `.git`.
- `-prune` prevents `find` from recursing into `.git` internals.
- `-execdir` runs the shell snippet from the parent of `.git` (i.e., the nested repo's root).
- Only repos with changes are printed — silent output means nothing to commit.

### Prompt

If the scan output is non-empty, after handling the main repo present a prompt to the user listing the nested repos with changes, e.g.:

> Found nested repos with uncommitted changes:
> - `profiles/private/work` (3 modified, 1 untracked)
> - `profiles/private/personal` (1 modified)
>
> Commit these as well? [all / pick / no]

If the main repo has **no** changes but nested repos do, skip the main-repo commit and go straight to this prompt.

### Recurse

For each repo the user picks, re-run the full skill workflow scoped to that repo using `git -C <path>` (or `cd <path> && git ...`):
- Re-detect task ID from that repo's branch + recent commits — task IDs are per-repo, do not reuse the parent's.
- Apply the same grouping strategy (default to one commit per repo).
- Show the planned commit(s) for each repo before executing.

Do **not** auto-push any of the nested repo commits. Pushing follows the same "only when explicitly asked" rule as the main repo.

## Example Workflow

### Typical case: single commit

```bash
# 1. Gather metadata (run these in PARALLEL - single message, multiple tool calls)
${CLAUDE_SKILL_DIR}/git-task-id -v                      # → PROJ-123 (source=branch:feature/PROJ-123-user-auth)
git status                          # → lists modified files

# 2. Inspect specific files as needed (based on status output)
git diff -- src/auth/service.ts
git diff -- src/auth/service.test.ts

# 3. All changes are part of the same feature → single commit (tests included!)
git add src/auth/service.ts src/auth/service.test.ts src/auth/types.ts
git commit -m "PROJ-123: feat(auth): implement user authentication service"
```

### Rare case: multiple commits (genuinely unrelated changes)

```bash
# Only split when changes are truly independent — e.g., a bug fix AND an unrelated feature
git add src/billing/invoice.ts
git commit -m "PROJ-456: fix(billing): correct tax calculation rounding"

git add src/auth/service.ts src/auth/service.test.ts
git commit -m "PROJ-123: feat(auth): implement user authentication service"
```

## Important Notes

- Always show the user what commits will be created before executing
- Use `git add -p` for partial file staging when needed
- Never force push or amend pushed commits without explicit permission
- Never push the branch unless explicitly asked
- When in doubt, prefer fewer commits over more — a single well-described commit is almost always better than over-split small ones
