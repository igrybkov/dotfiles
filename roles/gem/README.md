# gem

Ansible role to manage Ruby gems.

## Description

This role installs Ruby gems using the system gem command.

## Requirements

- Ruby installed (typically via Homebrew or system Ruby)

## Role Variables

### `gem_packages`

List of Ruby gems to install.

```yaml
gem_packages:
  - bundler
  - rake
  - nokogiri
```

## Dependencies

- Ruby must be installed

## Example Playbook

```yaml
- hosts: all
  roles:
    - role: gem
      vars:
        gem_packages:
          - bundler
          - rake
```

## Tags

- `gem`

## Notes

- Gems are installed with `state: present` (won't upgrade existing gems)
- Uses the `community.general.gem` module
