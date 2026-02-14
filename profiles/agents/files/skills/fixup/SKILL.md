---
name: fixup
description: Create a fixup commit and squash it into the last commit
allowed-tools:
  - Bash(git status:*)
  - Bash(git diff:*)
  - Bash(git log:*)
  - Bash(git add:*)
  - Bash(git commit:*)
  - Bash(git rebase:*)
---

# Fixup Commit Skill

Create a fixup for the last commit (small correction that should be part of the previous commit).

## Context

- Current git status: !`git status`
- Staged changes: !`git diff --cached`
- Unstaged changes: !`git diff`
- Last commit: !`git log -1 --oneline`

## Workflow

1. **Safety checks**
   - Verify the last commit has NOT been pushed to remote
   - If the branch shows "ahead of origin", it's safe to proceed
   - If already pushed, STOP and warn the user (amending would require force push)

2. **Stage changes**
   - If nothing is staged, stage all changes
   - If changes are staged, use those

3. **Create fixup commit and squash**

   Option A - Using git commit --amend (simpler):
   ```bash
   git add -A  # if needed
   git commit --amend --no-edit
   ```

   Option B - Using fixup workflow (if you want to review):
   ```bash
   git add -A  # if needed
   git commit --fixup HEAD
   git rebase -i --autosquash HEAD~2
   ```

4. **Verify success**
   - Run git log to show the amended commit
   - Run git status to confirm clean state

## Important Notes

- Do NOT use this if the last commit has been pushed
- Do NOT add any new commit message content
- Do NOT push to remote
