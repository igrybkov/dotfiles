# gh_extensions

Ansible role to manage GitHub CLI extensions.

## Description

This role installs, upgrades, and removes GitHub CLI (`gh`) extensions. Extensions extend the functionality of the `gh` command with additional features.

## Requirements

- GitHub CLI (`gh`) must be installed (typically via Homebrew)
- User must be authenticated with `gh auth login`
- Requires `community.general` Ansible collection

## Tags

- `gh-extensions` - GitHub CLI extension operations

## Role Variables

### `gh_extensions`

List of GitHub CLI extensions to manage.

```yaml
gh_extensions:
  - name: seachicken/gh-poi         # Extension name (required)
    state: present                   # present, latest, or absent
```

**Default:** `[]` (empty list)

**State behavior:**
- `present` - Install if not present, don't upgrade (default)
- `latest` - Install or upgrade to latest version (uses `--force` flag)
- `absent` - Remove the extension

## Dependencies

None.

## Example Usage

```yaml
# In profiles/common/config.yml or profiles/{profile}/config.yml
gh_extensions:
  - name: seachicken/gh-poi
    state: present
  - name: github/gh-copilot
    state: latest
  - name: dlvhdr/gh-dash
  - name: some/old-extension
    state: absent
```

## Side Effects

- Installs extensions to `~/.local/share/gh/extensions/`
- Extensions may add new `gh` subcommands
- `latest` state forces reinstall even if already installed

## Behavior

1. Checks if `gh` CLI is installed
2. Lists currently installed extensions
3. Removes extensions marked as `absent`
4. Installs missing extensions with `present` state
5. Force-installs extensions with `latest` state (upgrades if exists)

## Notes

- Extension names are in the format `owner/repo` (GitHub repository)
- The role gracefully handles missing `gh` CLI (skips all tasks)
- Failed operations don't halt the playbook (uses `failed_when: false`)
