---
name: omnifocus
description: Manage tasks and projects in OmniFocus - daily planning, weekly reviews, task creation/updates. Use when user asks about tasks, planning their day, reviewing work, or managing OmniFocus.
---

# OmniFocus Skill

Integrate with OmniFocus for task management, daily planning, and weekly reviews.

## Available MCP Tools

Use these OmniFocus MCP tools:
- `mcp__omnifocus__query_omnifocus` - Query tasks, projects, folders with filters
- `mcp__omnifocus__add_omnifocus_task` - Add new tasks
- `mcp__omnifocus__add_project` - Add new projects
- `mcp__omnifocus__edit_item` - Edit tasks or projects
- `mcp__omnifocus__remove_item` - Remove tasks or projects
- `mcp__omnifocus__batch_add_items` - Add multiple items at once
- `mcp__omnifocus__dump_database` - Get full database state
- `mcp__omnifocus__list_perspectives` - List available perspectives
- `mcp__omnifocus__get_perspective_view` - Get items from a perspective

## Quick Task Operations

### Add a task
```
add_omnifocus_task(
  name="Task description",
  projectName="Project Name",  # Optional, goes to inbox if omitted
  dueDate="2024-01-15",        # Optional, ISO format
  flagged=true,                # Optional
  tags=["tag1", "tag2"]        # Optional
)
```

### Query tasks by project
```
query_omnifocus(
  entity="tasks",
  filters={projectName: "Project Name", status: ["Available", "Next"]}
)
```

### Mark task complete
```
edit_item(
  itemType="task",
  name="Task name",
  newStatus="completed"
)
```

### Get tasks from a perspective
```
# First, list available perspectives
list_perspectives()
# Returns: Inbox, Projects, Tags, Forecast, Flagged, Review, + custom perspectives

# Get tasks from a built-in perspective
get_perspective_view(
  perspectiveName="Flagged",
  fields=["id", "name", "note", "dueDate", "projectName", "tagNames"],
  limit=20
)

# Get tasks from a custom perspective
get_perspective_view(
  perspectiveName="Today",
  fields=["id", "name", "note", "dueDate", "projectName", "tagNames", "estimatedMinutes"],
  includeMetadata=true,
  limit=50
)
```

## Best Practices

- Use perspectives for common views (Forecast, Flagged, etc.)
- Today = committed to do today/soon
- Due dates = hard deadlines only
- Defer dates = when task becomes relevant
- Keep inbox at zero during weekly review
