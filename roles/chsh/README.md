# chsh

Ansible role to change the default user shell on macOS.

## Description

This role changes the default shell for the current user. It prioritizes Fish shell, falling back to Zsh if Fish is not available.

## Requirements

- macOS
- Fish or Zsh shell installed (typically via Homebrew)

## Role Variables

This role has no configurable variables. It automatically:

1. Searches for Fish shell in standard paths
2. Falls back to Zsh if Fish is not found
3. Updates `/etc/shells` to include the shell
4. Changes the user's default shell

## Search Paths

The role searches for shells in:
- `/usr/bin`
- `/usr/local/bin`
- `/opt/homebrew/bin`

## Dependencies

- `brew` role (to install Fish/Zsh)

## Example Playbook

```yaml
- hosts: all
  roles:
    - role: chsh
```

## Tags

- `chsh` - Run shell change tasks
- `brew` - Also triggered by brew tag

## Notes

- Requires `become: true` (sudo) to modify `/etc/shells` and change the shell
- Fish shell takes priority over Zsh
- The role is idempotent - it won't change anything if the shell is already set correctly
