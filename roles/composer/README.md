# composer

Ansible role to manage global PHP Composer packages.

## Description

This role installs PHP packages globally using Composer's `require` command.

## Requirements

- PHP installed
- Composer installed (typically via Homebrew)

## Role Variables

### `composer_packages`

List of Composer packages to install globally.

```yaml
composer_packages:
  - laravel/installer                    # Simple package name
  - name: phpunit/phpunit                # With explicit name
  - name: custom/package
    global_command: true                 # Install globally (default)
    working_dir: /path/to/project        # Custom working directory
```

| Option           | Required | Default | Description                           |
|------------------|----------|---------|---------------------------------------|
| `name`           | Yes      | -       | Package name (vendor/package format)  |
| `global_command` | No       | `true`  | Install as global package             |
| `working_dir`    | No       | -       | Working directory for installation    |

## Dependencies

- PHP and Composer must be installed

## Example Playbook

```yaml
- hosts: all
  roles:
    - role: composer
      vars:
        composer_packages:
          - laravel/installer
          - name: phpunit/phpunit
```

## Tags

- `composer`

## Notes

- Packages are installed using `composer global require`
- The role uses the `community.general.composer` module
