---
name: pr
description: Create a pull request with auto-generated title and description
allowed-tools:
  - Bash(git status:*)
  - Bash(git diff:*)
  - Bash(git log:*)
  - Bash(git branch:*)
  - Bash(git push:*)
  - Bash(git rev-parse:*)
  - Bash(gh pr:*)
  - Bash(gh api:*)
---

# Create Pull Request Skill

Create a pull request for the current branch with auto-generated title and description.

## Context

- Current branch: !`git branch --show-current`
- Recent commits: !`git log --oneline -10`
- Current git status: !`git status`

## Workflow

1. **Check for uncommitted changes**
   - If there are uncommitted changes, ask if I should commit them first or proceed without them

2. **Analyze the commits**
   - Review all commits that will be included in the PR
   - Understand the overall purpose and scope of changes

3. **Generate PR title**
   - Create a concise, descriptive title
   - Use conventional commit style if appropriate (feat:, fix:, refactor:, etc.)

4. **Generate PR description**
   - Write a summary section (2-4 bullet points of key changes)
   - Add a test plan section with checkboxes for testing steps
   - Do NOT add AI attribution or signatures

5. **Push and create PR**
   - Push the branch to origin if not already pushed: `git push -u origin <branch>`
   - Create the PR using gh CLI:

```bash
gh pr create --title "Title here" --body "$(cat <<'EOF'
## Summary
- Key change 1
- Key change 2

## Test plan
- [ ] Test step 1
- [ ] Test step 2
EOF
)"
```

6. **Return the PR URL** so it can be opened in a browser

## Important Notes

- Do NOT force push or modify git history
- Always verify the branch is ready before creating PR
