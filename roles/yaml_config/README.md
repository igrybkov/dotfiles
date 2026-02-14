# YAML Config Role

Manages YAML configuration files by merging settings using Ansible's `combine` filter with recursive merge.

## Variables

### `yaml_configs`

List of configuration items to apply. Each item supports:

| Key | Required | Default | Description |
|-----|----------|---------|-------------|
| `file` | Yes | - | Path to YAML file (supports `~` expansion) |
| `content` | Yes | - | Dictionary of settings to merge recursively |
| `create_file` | No | `false` | Create file with content if it doesn't exist |

## Examples

### Merge settings into existing file

```yaml
yaml_configs:
  - file: ~/.config/myapp/config.yml
    content:
      editor:
        vimMode: true
      telemetry:
        enabled: false
```

### Create file if missing

```yaml
yaml_configs:
  - file: ~/.config/myapp/settings.yaml
    create_file: true
    content:
      feature:
        enabled: true
      logging:
        level: info
```

### Multi-profile aggregation

When using with multiple profiles, entries for the same file are merged using `lists_mergeby`:

**Profile: common**
```yaml
yaml_configs:
  - file: ~/.config/myapp/config.yml
    content:
      editor:
        vimMode: true
```

**Profile: agents**
```yaml
yaml_configs:
  - file: ~/.config/myapp/config.yml
    content:
      plugins:
        autoUpdate: false
```

**Result after aggregation:**
```yaml
editor:
  vimMode: true
plugins:
  autoUpdate: false
```

## Behavior

- **File doesn't exist + `create_file: false`**: Config item is skipped (no directory created)
- **File doesn't exist + `create_file: true`**: Parent directory created, file created with content
- **File exists**: Content is recursively merged with existing settings, preserving unspecified keys

## Tags

- `yaml-config`

## Notes

- Settings are merged recursively - nested keys are preserved unless explicitly overwritten
- Output is formatted using `to_nice_yaml` for readability
- Content can be any YAML-compatible type: strings, numbers, booleans, arrays, objects
- No external dependencies
