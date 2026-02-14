# brew_packages

Ansible role to manage Homebrew packages, casks, and taps on macOS.

## Description

This role manages the installation and removal of:
- Homebrew formulae (packages)
- Homebrew casks (GUI applications)
- Homebrew taps (third-party repositories)

It supports batch operations for efficiency and handles packages with custom versions or specific states.

Input validation is handled via `meta/argument_specs.yml`.

## Requirements

- macOS
- Homebrew (installed via `geerlingguy.mac.homebrew` role)

## Role Variables

### `brew_taps`

List of Homebrew taps to manage. Each item must be a dict with a `name` key.

```yaml
brew_taps:
  - name: homebrew/services
  - name: homebrew/cask-fonts
    state: absent                        # Remove this tap
```

| Option  | Required | Default   | Description                     |
|---------|----------|-----------|---------------------------------|
| `name`  | Yes      | -         | Tap name                        |
| `state` | No       | `present` | `present` or `absent`           |

### `brew_packages`

List of Homebrew formulae to install. Each item must be a dict with a `name` key.

```yaml
brew_packages:
  - name: git                            # Install if not present
  - name: node
    state: present                       # Only install if not present
  - name: python
    state: latest                        # Keep updated
  - name: go
    version: "1.21"                      # Specific version
  - name: old-package
    state: absent                        # Uninstall
```

| Option    | Required | Default   | Description                      |
|-----------|----------|-----------|----------------------------------|
| `name`    | Yes      | -         | Package name                     |
| `state`   | No       | `present` | `present`, `latest`, or `absent` |
| `version` | No       | -         | Specific version to install      |

### `cask_packages`

List of Homebrew casks to install. Each item must be a dict with a `name` key.

```yaml
cask_packages:
  - name: visual-studio-code
  - name: docker-desktop
    state: present
  - name: old-app
    state: absent
```

| Option    | Required | Default   | Description                      |
|-----------|----------|-----------|----------------------------------|
| `name`    | Yes      | -         | Cask name                        |
| `state`   | No       | `present` | `present`, `latest`, or `absent` |
| `version` | No       | -         | Specific version to install      |

### `brew_upgrade_all`

Whether to upgrade all installed packages.

**Default**: `false`

## Dependencies

- `geerlingguy.mac.homebrew` (for Homebrew installation)

## Example Playbook

```yaml
- hosts: localhost
  roles:
    - role: brew_packages
      vars:
        brew_taps:
          - name: homebrew/services
        brew_packages:
          - name: git
          - name: node
            state: present
        cask_packages:
          - name: firefox
          - name: visual-studio-code
```

## Tags

- `brew` - Run all brew tasks
- `brew-packages` - Run all brew tasks
- `taps` - Only manage taps
- `cask` - Only manage casks

## Notes

- All list items must be dicts with a `name` key (string format not supported)
- Packages without explicit `state` default to `present`
- Use `state: latest` for packages you want to keep updated
- Casks are installed with `accept_external_apps: true` flag
