---
name: personal-docs
description: Work with personal notes and documentation in Obsidian vault - drafts, personal notes, ideas not yet ready for team sharing. Use when user asks about personal notes, drafts, or private documentation. Requires Obsidian MCP server (obsidian-digital-garden or similar).
---

# Personal Docs Skill

Manage personal documentation and notes in Obsidian vault for private knowledge management.

## Prerequisites

**Required**: Obsidian MCP server must be configured.

Available Obsidian MCP tools:
- `mcp__obsidian-digital-garden__get_vault_file` - Read a file
- `mcp__obsidian-digital-garden__create_vault_file` - Create/update a file
- `mcp__obsidian-digital-garden__append_to_vault_file` - Append to a file
- `mcp__obsidian-digital-garden__search_vault_simple` - Text search
- `mcp__obsidian-digital-garden__search_vault_smart` - Semantic search
- `mcp__obsidian-digital-garden__list_vault_files` - List files in directory
- `mcp__obsidian-digital-garden__get_active_file` - Get currently open file
- `mcp__obsidian-digital-garden__show_file_in_obsidian` - Open file in Obsidian

If MCP is not available, inform user: "Obsidian MCP server required. Configure `obsidian-digital-garden` or similar MCP server."

## Personal vs Team Documentation

This skill is for **personal** notes:
- Work-in-progress drafts
- Personal learning notes
- Ideas and brainstorms
- Meeting prep and private notes
- Research before sharing

For **team** documentation, use the `wiki` skill (Confluence).

## Common Operations

### Quick Capture
When user wants to save a quick note:
```
create_vault_file(
  filename="inbox/YYYY-MM-DD-quick-note.md",
  content="# Quick Note\n\n[content]"
)
```

### Daily Notes
For daily journaling or logging:
```
create_vault_file(
  filename="daily/YYYY-MM-DD.md",
  content="# YYYY-MM-DD\n\n## Tasks\n\n## Notes\n\n## Log"
)
```

### Search Notes
Find relevant notes:
```
search_vault_simple(query="search term")
# or for semantic search:
search_vault_smart(query="concept to find")
```

### Read and Summarize
When user asks about their notes:
```
get_vault_file(filename="path/to/note.md")
```

## Note Templates

### Meeting Prep
```markdown
# Meeting: [Topic]
Date: YYYY-MM-DD

## My Goals
- What do I want to achieve?

## Questions to Ask
1.
2.

## Background
[Context I need to remember]

## Post-Meeting Notes
[Fill in after]
```

### Learning Note
```markdown
# [Topic]
Tags: #learning #[subject]

## Summary
[One paragraph explanation]

## Key Concepts
- Concept 1
- Concept 2

## Examples
[Code or examples]

## Questions
- Things I don't understand yet

## Resources
- Links and references
```

### Project Idea
```markdown
# Idea: [Name]
Status: #idea
Created: YYYY-MM-DD

## Problem
[What problem does this solve?]

## Solution
[High-level approach]

## Next Steps
- [ ] Research X
- [ ] Prototype Y

## Notes
[Additional thoughts]
```

### Decision Draft
```markdown
# Decision: [Topic]
Status: #draft
Created: YYYY-MM-DD

## Context
[Background information]

## Options Considered
1. Option A
   - Pros:
   - Cons:
2. Option B
   - Pros:
   - Cons:

## Recommendation
[My current thinking]

## Open Questions
- Questions before deciding

---
*Move to team wiki when ready to share*
```

## Organization Patterns

### Suggested Folder Structure
```
vault/
├── inbox/          # Quick captures, unsorted
├── daily/          # Daily notes
├── projects/       # Project-specific notes
├── learning/       # Study notes
├── meetings/       # Meeting prep and notes
├── ideas/          # Ideas and brainstorms
└── archive/        # Old/completed items
```

### Tagging Conventions
- `#draft` - Work in progress
- `#idea` - Idea to explore
- `#learning` - Learning notes
- `#decision` - Decision being made
- `#ready-to-share` - Ready for team wiki

## Workflow: Draft to Team Docs

1. Create draft in Obsidian with `#draft` tag
2. Iterate and refine privately
3. When ready, tag with `#ready-to-share`
4. Use `work-with-wiki` skill to publish to Confluence
5. Archive or link the Obsidian note to published version
