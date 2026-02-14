# Cursor CLI Role

Installs and updates the Cursor CLI (`agent` command) for the Cursor AI code editor.

## Tags

- `cursor-cli` - Cursor CLI operations

## Input Variables

None. The role operates automatically based on system state.

## Output Variables

### `cursor_cli_check`

Register containing the result of checking if Cursor CLI is installed.

### `cursor_upgrade_result`

Register containing the result of the upgrade operation.

## Side Effects

- Downloads and executes Cursor install script from `https://cursor.com/install`
- Installs the `agent` command to the system PATH
- Upgrades existing installation if already present

## Dependencies

- macOS only (`ansible_facts["distribution"] == 'MacOSX'`)
- Must be in the `work` group (only runs for work profile)
- Requires `curl` for installation

## Conditions

This role only runs when:
1. Running on macOS
2. The host is in the `work` group

## Example Usage

This role typically requires no configuration. It's included in the playbook and runs automatically for work profiles:

```yaml
# In playbook.yml
- name: Install Cursor CLI
  ansible.builtin.include_role:
    name: cursor_cli
  tags: [cursor-cli]
```

## Behavior

1. **Check**: Verifies if `agent` command exists in PATH
2. **Install**: If not present, downloads and runs Cursor install script
3. **Upgrade**: If present, runs `agent upgrade` to update to latest version

## Notes

- The Cursor CLI is named `agent`, not `cursor`
- Installation script is fetched from Cursor's official website
- Upgrade is only attempted if CLI is already installed
- Only installed on work machines (work profile)
