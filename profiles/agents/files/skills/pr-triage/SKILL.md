---
name: pr-triage
description: Triage PR review comments into actionable issues, false positives, and items needing clarification. Use when you need to systematically address PR feedback.
allowed-tools:
  - Bash(gh:*)
  - Bash(git status:*)
  - Bash(git diff:*)
  - Bash(git log:*)
  - Bash(git branch:*)
  - Read
  - Glob
  - Grep
  - EnterPlanMode
  - AskUserQuestion
---

# PR Feedback Triage Skill

Systematically read, analyze, and triage all review comments on a pull request, then build a plan to address them.

## Input

The user provides a PR reference. This can be:
- A PR URL: `https://github.com/owner/repo/pull/123`
- A PR number: `123` (uses current repo)
- No argument: uses the PR for the current branch

## Workflow

### 1. Fetch All PR Comments

Retrieve all review comments, issue comments, and review threads:

```bash
# Get PR details and review comments
gh pr view <number> --json title,body,reviews,comments,url

# Get review comments (inline code comments)
gh api repos/{owner}/{repo}/pulls/{number}/comments

# Get issue-level comments
gh api repos/{owner}/{repo}/issues/{number}/comments

# Get reviews with their state
gh api repos/{owner}/{repo}/pulls/{number}/reviews
```

### 2. Analyze and Group Comments

Read through every comment thread and classify each into one of three categories:

#### Category A: Real Issues (Fix Required)
Comments that identify genuine bugs, logic errors, security issues, or valid improvements. These need code changes.

Criteria:
- The commenter identified an actual bug or correctness issue
- The suggestion improves security, performance, or maintainability
- The feedback aligns with project conventions or best practices
- You can verify the issue exists by reading the relevant code

#### Category B: False Positives (No Action Needed)
Comments where the reviewer misunderstood the code, context, or intent. No changes required.

Criteria:
- The code already handles the concern raised
- The reviewer misread or misunderstood the implementation
- The suggestion contradicts project conventions or requirements
- The concern is addressed elsewhere in the codebase

**Important**: When you suspect a comment is a false positive, verify by reading the actual code before concluding. Don't dismiss feedback without evidence.

#### Category C: Needs Clarification
Comments where the right course of action is unclear, the fix approach has multiple valid options, or you need the user's input to proceed.

Criteria:
- The comment raises a valid point but the fix approach isn't obvious
- There are multiple valid ways to address the feedback
- The comment touches on product/design decisions you can't make alone
- You need more context about intent or requirements

### 3. Present the Triage

Show the user the grouped results with a brief summary for each comment:

```
## PR #123: Title

### A. Real Issues (X comments) — will fix
1. **file.ts:42** - [reviewer]: Missing null check on `user.email`
   → The variable is used without validation; will add null check

2. **api.ts:15** - [reviewer]: SQL injection risk in query builder
   → Confirmed: user input not sanitized; will use parameterized query

### B. False Positives (X comments) — no action needed
1. **utils.ts:88** - [reviewer]: This function is never called
   → Actually imported in `handler.ts:12`; used in the error path

### C. Needs Your Input (X comments)
1. **config.ts:30** - [reviewer]: Should this default to `true` or `false`?
   → Both are valid; depends on desired UX for new users
```

### 4. Ask Questions About Category C

Use `AskUserQuestion` to get the user's decision on each item in Category C. Ask concise, specific questions with clear options when possible.

### 5. Build a Plan

Once all items are resolved, enter plan mode and build a comprehensive fix plan covering all Category A items and the now-resolved Category C items. The plan should:

- Group related fixes together
- Order changes logically (dependencies first)
- Note which files will be modified
- Describe the fix approach for each item

Present the plan for user approval before making any code changes.

### 6. Reply to False Positives (Optional)

After the user approves the plan, ask if they'd like you to draft replies to the false positive comments explaining why no change is needed. Keep replies professional and concise.

## Important Notes

- **Read the code**: Always verify comments against actual code before classifying
- **Don't dismiss hastily**: When in doubt, classify as Category C rather than B
- **Respect reviewers**: Even false positives deserve respectful consideration
- **Be thorough**: Don't skip comments — every thread must be classified
- **Handle 404s**: If the gh command fails, check `gh auth status` and switch accounts if needed (see `/github` skill)
