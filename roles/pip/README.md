# pip

Ansible role to manage Python packages using pip.

## Description

This role installs Python packages using pip. It automatically detects the correct pip executable from multiple possible locations.

## Requirements

- Python 3 installed

## Role Variables

### `pip_packages`

List of Python packages to install.

```yaml
pip_packages:
  - requests                             # Simple package name
  - name: flask                          # With explicit name
  - name: django
    state: present                       # Install specific version
  - name: numpy
    state: latest                        # Keep updated (default)
  - name: git+https://github.com/user/repo  # Install from git
```

| Option  | Required | Default  | Description                      |
|---------|----------|----------|----------------------------------|
| `name`  | Yes      | -        | Package name or git URL          |
| `state` | No       | `latest` | `present`, `latest`, or `absent` |

**Default**: `[]`

### `pip_system_pip_path`

Path to the system pip executable.

**Default**: `/usr/local/bin/pip3`

### `pip_miniconda_path`

Path to Miniconda installation (for Miniconda pip).

**Default**: `/opt/homebrew/Caskroom/miniconda/base`

## Pip Executable Detection

The role searches for pip in this order:
1. `pip_system_pip_path` (`/usr/local/bin/pip3`)
2. Miniconda pip (`{pip_miniconda_path}/bin/pip`)
3. macOS system pip (`/usr/bin/pip3`)

## Dependencies

- Python 3 must be installed

## Example Playbook

```yaml
- hosts: all
  roles:
    - role: pip
      vars:
        pip_packages:
          - requests
          - name: flask
            state: present
```

## Tags

- `pip`
- `python`

## Notes

- Pip itself is upgraded to the latest version before installing packages
- Packages default to `state: latest` (unlike some other roles)
- Supports installing from git repositories
- The role asserts that a pip executable is found before proceeding
