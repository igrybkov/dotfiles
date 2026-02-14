# mas

Ansible role to manage Mac App Store applications.

## Description

This role installs, uninstalls, and upgrades applications from the Mac App Store using the `mas` CLI tool.

## Requirements

- macOS
- `mas` CLI tool installed (via Homebrew)
- Signed in to the Mac App Store

## Role Variables

### `mas_packages`

List of Mac App Store applications to manage.

```yaml
mas_packages:
  - name: Xcode
    id: 497799835
  - name: Things 3
    id: 904280696
    state: absent                        # Uninstall
  - name: Amphetamine
    id: 937984704
    state: present                       # Install (default)
```

| Option  | Required | Default   | Description                     |
|---------|----------|-----------|---------------------------------|
| `name`  | Yes      | -         | Application name (for display)  |
| `id`    | Yes      | -         | Mac App Store application ID    |
| `state` | No       | `present` | `present` or `absent`           |

### `mas_upgrade_all`

Whether to upgrade all installed Mac App Store applications. This is aggregated from all profiles using "any" logic - if ANY profile sets this to `true`, upgrades will run.

**Default**: `false`

## Finding App IDs

You can find the App ID in the Mac App Store URL:
```
https://apps.apple.com/app/xcode/id497799835
                                  ^^^^^^^^^ App ID
```

Or use `mas search`:
```bash
mas search Xcode
```

## Dependencies

- `mas` CLI tool (install via `brew install mas`)

## Example Playbook

```yaml
- hosts: all
  roles:
    - role: mas
      vars:
        mas_upgrade_all: true
        mas_packages:
          - name: Xcode
            id: 497799835
          - name: Keynote
            id: 409183694
```

## Tags

- `mas`

## Notes

- You must be signed in to the Mac App Store before running this role
- Uninstalling apps requires `become: true` (sudo)
- The `name` field is only for documentation; the `id` is used for installation
- When uninstalling, the role also removes the `.app` file from `/Applications`
