---
name: review
description: Review staged/unstaged changes for bugs, security issues, and improvements
allowed-tools:
  - Bash(git status:*)
  - Bash(git diff:*)
  - Bash(git log:*)
  - Read
  - Glob
  - Grep
---

# Code Review Skill

Review current changes (staged or unstaged) and provide actionable feedback.

## Context

- Current git status: !`git status`
- Staged changes: !`git diff --cached`
- Unstaged changes: !`git diff`

## Review Focus Areas

1. **Bugs & Logic Errors**
   - Off-by-one errors, null/undefined handling, edge cases
   - Incorrect conditionals or control flow
   - Race conditions or async issues

2. **Security Issues**
   - SQL injection, XSS, command injection
   - Hardcoded secrets or credentials
   - Insecure data handling

3. **Code Quality**
   - Code that's hard to understand or maintain
   - Missing error handling
   - Inefficient algorithms or unnecessary complexity

4. **Best Practices**
   - Violations of common patterns in the codebase
   - Missing input validation at boundaries
   - Potential breaking changes

## Output Format

Provide a summary with:
- **Critical Issues**: Must fix before committing
- **Warnings**: Should consider fixing
- **Suggestions**: Optional improvements

## Important Notes

- If the code looks good, say so briefly
- Don't nitpick style issues that linters would catch
- If you need more context about how existing code works, read the relevant files
