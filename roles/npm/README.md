# npm

Ansible role to manage global NPM packages.

## Description

This role installs NPM packages globally using the `community.general.npm` module. It safely checks for npm availability first and skips gracefully if npm is not found.

## Requirements

- Node.js and NPM installed (via nvm, mise, Homebrew, or any other method)
- npm must be available in PATH

## Role Variables

### `npm_packages`

List of NPM packages to install globally.

```yaml
npm_packages:
  - prettier                             # Simple package name
  - name: eslint                         # With explicit name
  - name: typescript
    state: present                       # Install (default)
  - name: old-package
    state: absent                        # Uninstall
```

| Option  | Required | Default   | Description                     |
|---------|----------|-----------|---------------------------------|
| `name`  | Yes      | -         | NPM package name                |
| `state` | No       | `present` | `present` or `absent`           |

**Default**: `[]`

## Behavior

1. Aggregates `npm_packages` from all active profiles
2. Checks if npm is available in PATH
3. If npm is not found, outputs a debug message and skips installation
4. If npm is available, installs packages globally

## Dependencies

None. Node.js can be installed via:
- nvm (configured in fish shell)
- mise
- Homebrew (`node` formula)
- Any other method that puts npm in PATH

## Example Playbook

```yaml
- hosts: all
  roles:
    - role: npm
      vars:
        npm_packages:
          - prettier
          - eslint
          - name: typescript
```

## Tags

- `npm`

## Notes

- Packages are installed globally (`global: true`)
- The role runs in the Finalize play after mise install, ensuring npm is available
- If npm is not installed, the role skips gracefully without failing
