---
name: wiki
description: Work with team wiki (Confluence) - read/write documentation, create pages, maintain project docs. Use when user asks about team documentation, wiki pages, or needs to document something for the team. Requires Confluence MCP server.
---

# Work with Wiki Skill

Manage team documentation in Confluence wiki for shared knowledge and project documentation.

## Prerequisites

This skill requires a Confluence MCP server to be configured. If MCP tools are not available, inform the user they need to set up Confluence MCP integration.

Common Confluence MCP servers:
- `mcp-server-atlassian`
- `@anthropics/confluence-mcp`

## Reading Documentation

When user asks about existing documentation:

1. Search for relevant pages by title/content
2. Fetch page content
3. Present key information in a readable format
4. Include links to the original pages

## Creating Documentation

### Project Documentation
When documenting a new project:

1. **README/Overview page**:
   - Project purpose and goals
   - Key stakeholders
   - Links to related resources

2. **Architecture documentation**:
   - System design
   - Component diagrams
   - Data flow

3. **Setup/Onboarding guide**:
   - Prerequisites
   - Installation steps
   - Configuration

4. **API documentation** (if applicable):
   - Endpoints
   - Request/response formats
   - Authentication

### Decision Records
For architectural decisions (ADRs):

```markdown
# ADR-NNN: [Decision Title]

## Status
[Proposed | Accepted | Deprecated | Superseded]

## Context
[What is the issue we're addressing?]

## Decision
[What did we decide to do?]

## Consequences
[What are the results of this decision?]
```

### Meeting Notes
For team meetings:

```markdown
# [Meeting Type] - [Date]

## Attendees
- Person 1
- Person 2

## Agenda
1. Topic 1
2. Topic 2

## Discussion
[Key points discussed]

## Action Items
- [ ] Action 1 - @owner
- [ ] Action 2 - @owner

## Next Steps
[What happens next]
```

## Updating Documentation

When updating existing pages:
1. Fetch current content
2. Make targeted changes
3. Preserve existing structure
4. Update "last modified" metadata
5. Add to page history/changelog if significant

## Documentation Best Practices

### Structure
- Use clear hierarchies (space > parent page > child pages)
- Keep pages focused on single topics
- Use templates for consistency

### Content
- Write for your audience (new team members, future you)
- Include examples and code snippets
- Keep information current (schedule reviews)
- Link related pages

### Maintenance
- Review documentation during sprint retrospectives
- Archive outdated content rather than deleting
- Tag pages with relevant labels

## Common Operations

### Find documentation
"Where is the API documentation for service X?"

### Create new page
"Document the deployment process for project Y"

### Update existing
"Update the onboarding guide with the new setup steps"

### Generate from code
"Create API docs from this OpenAPI spec"

## Error Handling

If Confluence MCP is not available:
1. Inform user: "Confluence MCP server is not configured"
2. Suggest setup: "Add a Confluence MCP server to your Claude configuration"
3. Offer alternatives:
   - Write documentation in markdown for manual upload
   - Use local files as interim documentation
