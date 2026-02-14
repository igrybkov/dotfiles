# ssh_config

Ansible role to manage SSH client configuration.

## Description

This role manages the SSH client configuration file (`~/.ssh/config`). It aggregates configuration from all profiles and writes them to a single file. Features:

- **Aggregates config from all profiles** sorted by priority (lower priority = processed first)
- Adding SSH host configurations via `community.general.ssh_config`
- Inserting custom config blocks at the top or bottom of the file
- Preserves manual entries in the middle section between managed blocks

## Requirements

- SSH installed (comes with macOS/Linux)

## Role Variables

### `ssh_config_file`

Path to the SSH config file.

**Default**: `~/.ssh/config`

### `ssh_client_config`

List of SSH host configurations using the `community.general.ssh_config` module format.

```yaml
ssh_client_config:
  - host: github.com
    hostname: github.com
    identity_file: ~/.ssh/id_ed25519
    user: git
  - host: myserver
    hostname: 192.168.1.100
    user: admin
    port: 2222
```

See [community.general.ssh_config](https://docs.ansible.com/ansible/latest/collections/community/general/ssh_config_module.html) for all available options.

### `ssh_client_config_block`

List of raw text blocks to insert into the SSH config. Useful for options not supported by the `ssh_config` module.

```yaml
ssh_client_config_block:
  - content: |
      Include ~/.ssh/1Password/config
    position: top                        # Insert at beginning
  - content: |
      Host *
          IdentityAgent "~/Library/Group Containers/2BUA8C4S2C.com.1password/t/agent.sock"
    position: bottom                     # Insert at end
```

| Option     | Required | Default | Description                        |
|------------|----------|---------|------------------------------------|
| `content`  | Yes      | -       | Raw SSH config text                |
| `position` | Yes      | -       | `top` or `bottom`                  |

## Dependencies

- `ordered_blockinfile` role (internal dependency for config blocks)
- `community.general.ssh_config` module (for host entries)

## Example Playbook

The role aggregates config from all profiles, so it should run on a single host:

```yaml
# In playbook.yml - run on common host to aggregate config from all profiles
- hosts: common
  roles:
    - role: ssh_config
```

Each profile defines its own configuration in `profiles/{profile}/config.yml`:

```yaml
# profiles/work/config.yml
ssh_client_config:
  - host: github.com
    identity_file: ~/.ssh/id_ed25519
    user: git
  - host: "*.corp.example.com"
    user: jdoe
    proxycommand: "ssh -W %h:%p bastion.example.com"

ssh_client_config_block:
  - content: |
      Include ~/.ssh/config.d/*
    position: top
```

## Tags

- `ssh`

## Profile Priority

When aggregating config from multiple profiles, the role sorts by `profile_priority` (ascending). Lower values are processed first:

| Profile | Default Priority |
|---------|------------------|
| default | 100 |
| common | 150 |
| work, personal | 200 |
| others | 1000 |

This means `common` profile's config appears before `work` profile's config in the final file.

## Block Markers

The role uses the `ordered_blockinfile` role internally with global markers (shared across all profiles):
- `##### BEGIN SSH CONFIG TOP #####`
- `##### END SSH CONFIG TOP #####`
- `##### BEGIN SSH CONFIG BOTTOM #####`
- `##### END SSH CONFIG BOTTOM #####`

**Note**: Previous versions used per-profile markers (e.g., `##### BEGIN SSH CONFIG TOP for common-profile #####`). The role automatically removes these legacy markers during migration.

## Notes

- This role should run on a single host (e.g., `common`) to aggregate config from all profiles
- Profiles are sorted by `profile_priority` (lower value = processed first) when aggregating
- The role ensures blocks are always in the correct position (top/bottom)
- Uses `throttle: 1` to prevent race conditions when adding host entries
- Custom blocks are useful for 1Password SSH agent integration
- Host entries added via `community.general.ssh_config` are normalized (lowercase directives, 4-space indent)
