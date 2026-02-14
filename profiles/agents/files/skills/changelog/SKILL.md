---
name: changelog
description: Generate changelog entry from recent commits
allowed-tools:
  - Bash(git log:*)
  - Bash(git tag:*)
  - Bash(git diff:*)
  - Bash(git describe:*)
  - Read
  - Glob
  - Edit
  - Write
---

# Changelog Generation Skill

Generate a changelog entry from recent commits following Keep a Changelog format.

## Context

- Recent commits: !`git log --oneline -20`

## Workflow

1. **Determine scope**
   - If there's a recent tag, include commits since that tag
   - Otherwise, ask the user how far back to go or use a reasonable default

2. **Analyze commits**
   - Group commits by type (features, fixes, breaking changes, etc.)
   - Identify the most significant changes
   - Note any breaking changes prominently

3. **Generate changelog entry**

   Use this format:
   ```markdown
   ## [Version or Unreleased] - YYYY-MM-DD

   ### Added
   - New feature descriptions

   ### Changed
   - Changes to existing functionality

   ### Fixed
   - Bug fixes

   ### Breaking Changes
   - Any breaking changes (if applicable)
   ```

4. **Check for existing changelog**
   - Look for CHANGELOG.md, HISTORY.md, or similar
   - If found, prepend the new entry (after any header)
   - If not found, ask if the user wants to create one

5. **Output options**
   - Show the generated entry
   - Ask if the user wants to write it to a file

## Important Notes

- Keep entries concise and user-focused (what changed from user perspective, not implementation details)
- Follow Keep a Changelog conventions
