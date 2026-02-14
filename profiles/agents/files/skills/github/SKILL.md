---
name: github
description: Work with GitHub using gh CLI - create/update PRs, manage workflows, issues, and releases. Handles multiple authenticated profiles.
allowed-tools:
  - Bash(gh:*)
  - Bash(git status:*)
  - Bash(git diff:*)
  - Bash(git log:*)
  - Bash(git branch:*)
  - Bash(git push:*)
  - Read
---

# GitHub Skill

Work with GitHub repositories using the `gh` CLI for all GitHub operations.

## Using the gh CLI

Always use the `gh` CLI for GitHub interactions instead of direct API calls or web URLs:

### Pull Requests

```bash
# Create PR
gh pr create --title "Title" --body "Description"

# List PRs
gh pr list

# View PR details
gh pr view 123

# Check out a PR locally
gh pr checkout 123

# Merge PR
gh pr merge 123 --squash

# Review PR
gh pr review 123 --approve
gh pr review 123 --request-changes --body "Please fix..."
```

### Issues

```bash
# Create issue
gh issue create --title "Title" --body "Description"

# List issues
gh issue list

# View issue
gh issue view 123

# Close issue
gh issue close 123
```

### Workflows (GitHub Actions)

```bash
# List workflows
gh workflow list

# View workflow runs
gh run list

# View specific run
gh run view 123456

# Watch a running workflow
gh run watch 123456

# Trigger workflow manually
gh workflow run workflow-name.yml

# Download artifacts
gh run download 123456
```

### Releases

```bash
# Create release
gh release create v1.0.0 --title "Release v1.0.0" --notes "Release notes"

# List releases
gh release list

# Download release assets
gh release download v1.0.0
```

### Repository Operations

```bash
# Clone repository
gh repo clone owner/repo

# Fork repository
gh repo fork owner/repo

# View repository
gh repo view owner/repo
```

## Multiple GitHub Profiles

The user may have multiple GitHub accounts authenticated (e.g., personal and work accounts).

### Handling 404 Errors

If a `gh` command fails with a **404 error**, it likely means you're authenticated as the wrong account for that repository.

**To diagnose:**

```bash
# List all authenticated profiles
gh auth status -h github.com
```

This shows all authenticated accounts and which one is currently active.

**To fix:**

```bash
# Switch to a different profile
gh auth switch -h github.com -u <username>
```

Replace `<username>` with the appropriate GitHub username for the repository you're trying to access.

### Example Workflow

```bash
# Command fails with 404
gh pr list
# error: Could not resolve to a Repository...

# Check which account is active
gh auth status -h github.com
# github.com
#   ✓ Logged in to github.com account personal-user (keyring)
#   - Active account: true
#   ✓ Logged in to github.com account work-user (keyring)
#   - Active account: false

# Switch to work account
gh auth switch -h github.com -u work-user

# Retry the command
gh pr list
# Now it works!
```

### Proactive Approach

When working with a repository, if you're unsure which account has access:

1. Check the repository's organization/owner
2. Run `gh auth status -h github.com` to see available accounts
3. Switch to the appropriate account before running commands

## Common Patterns

### Create PR with Labels and Reviewers

```bash
gh pr create \
  --title "feat: add new feature" \
  --body "Description of changes" \
  --label "enhancement" \
  --reviewer username1,username2
```

### View PR Comments

```bash
gh api repos/{owner}/{repo}/pulls/{pr_number}/comments
```

### Check CI Status

```bash
gh pr checks 123
```

### Search Issues

```bash
gh issue list --search "bug in:title"
```
