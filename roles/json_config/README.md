# JSON Config Role

Manages JSON configuration files by merging settings using Ansible's `combine` filter with recursive merge.

## Variables

### `json_configs`

List of configuration items to apply. Each item supports:

| Key | Required | Default | Description |
|-----|----------|---------|-------------|
| `file` | Yes | - | Path to JSON file (supports `~` expansion) |
| `content` | Yes | - | Dictionary of settings to merge recursively |
| `create_file` | No | `false` | Create file with content if it doesn't exist |

## Examples

### Merge settings into existing file

```yaml
json_configs:
  - file: ~/.cursor/cli-config.json
    content:
      editor:
        vimMode: true
      telemetry:
        enableTelemetry: false
```

### Create file if missing

```yaml
json_configs:
  - file: ~/.claude/settings.json
    create_file: true
    content:
      planModeByDefault: true
      statusLine:
        type: command
        command: ~/.claude/statusline-command.py
```

### Multi-profile aggregation

When using with multiple profiles, entries for the same file are merged using `lists_mergeby`:

**Profile: common**
```yaml
json_configs:
  - file: ~/.cursor/cli-config.json
    content:
      editor:
        vimMode: true
```

**Profile: agents**
```yaml
json_configs:
  - file: ~/.cursor/cli-config.json
    content:
      attribution:
        attributeCommitsToAgent: false
```

**Result after aggregation:**
```json
{
  "editor": {
    "vimMode": true
  },
  "attribution": {
    "attributeCommitsToAgent": false
  }
}
```

## Behavior

- **File doesn't exist + `create_file: false`**: Config item is skipped (no directory created)
- **File doesn't exist + `create_file: true`**: Parent directory created, file created with content
- **File exists**: Content is recursively merged with existing settings, preserving unspecified keys

## Tags

- `json-config`
- `coding-agents` (when used for agent configuration)

## Notes

- Settings are merged recursively - nested keys are preserved unless explicitly overwritten
- Output is formatted using `to_nice_json` for readability
- Content can be any JSON-compatible type: strings, numbers, booleans, arrays, objects
- No external dependencies (previously required `jq`)
