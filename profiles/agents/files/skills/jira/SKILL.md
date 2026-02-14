---
name: jira
description: Work with Jira issues - fetch details, create/update tickets, link commits to issues. Use when user mentions Jira tickets, asks about issues, or needs to update project tracking. Requires Jira MCP server.
---

# Work with Jira Skill

Interact with Jira for issue tracking, project management, and commit linking.

## Prerequisites

This skill requires a Jira MCP server to be configured. If MCP tools are not available, inform the user they need to set up Jira MCP integration.

Common Jira MCP servers:
- `@anthropics/jira-mcp` (official)
- `mcp-server-atlassian`

## Fetching Issue Details

When user asks about a Jira ticket (e.g., "What's PROJ-123 about?"):

1. Use Jira MCP to fetch issue details
2. Present key information:
   - Summary and description
   - Status and assignee
   - Priority and labels
   - Recent comments
   - Linked issues

## Creating Issues

When user asks to create a ticket:

1. Gather required information:
   - Project key (e.g., PROJ)
   - Issue type (Bug, Story, Task, Epic)
   - Summary (title)
   - Description

2. Optional fields to ask about:
   - Priority
   - Assignee
   - Labels
   - Sprint
   - Story points

3. Create via MCP and return the issue key

## Updating Issues

Common update operations:
- Change status (transitions)
- Update description
- Add comments
- Change assignee
- Update labels

## Linking Commits to Issues

### From Branch Name
Extract issue key from branch patterns:
- `feature/PROJ-123-description`
- `PROJ-123/feature-name`
- `fix/PROJ-123`

### In Commit Messages
Ensure commits reference issues:
```
PROJ-123: feat(auth): implement login flow

This implements the authentication flow as described in PROJ-123.
```

### Smart Commit Syntax
If Jira Smart Commits are enabled:
```
PROJ-123 #comment Fixed the login bug #time 2h
PROJ-123 #done
PROJ-123 #in-progress
```

## Workflow Integration

### Before Starting Work
1. Fetch issue details to understand requirements
2. Check acceptance criteria
3. Review linked issues and dependencies

### During Development
1. Reference issue key in branch name
2. Include issue key in commit messages
3. Add comments for significant progress

### When Completing Work
1. Update issue status
2. Add final comment with PR link
3. Verify all acceptance criteria met

## Common Queries

### My assigned issues
"Show me my open issues in PROJ"

### Sprint work
"What's in the current sprint?"

### Issue status
"What's the status of PROJ-123?"

### Blockers
"Are there any blocked issues in PROJ?"

## Error Handling

If Jira MCP is not available:
1. Inform user: "Jira MCP server is not configured"
2. Suggest setup: "Add a Jira MCP server to your Claude configuration"
3. Provide manual fallback: "You can view the issue at: https://your-jira.atlassian.net/browse/PROJ-123"
