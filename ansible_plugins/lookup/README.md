# Lookup Plugins

Custom Ansible lookup plugins for the dotfiles system.

## aggregated_profile_var

Aggregates variables from all enabled profile hosts with automatic sorting by priority.

### Overview

This plugin simplifies the common pattern of collecting configuration from multiple profiles. It automatically:

1. Gets the list of enabled profiles from `active_profiles` (set by CLI)
2. Converts profile names to Ansible host names via groups lookup
3. Sorts hosts by `profile_priority` (ascending - lower number = higher priority)
4. Aggregates the requested variable using the specified merge strategy

### Basic Usage

```yaml
# In any role's tasks/main.yml
- name: Get aggregated packages
  ansible.builtin.set_fact:
    brew_packages: "{{ lookup('aggregated_profile_var', 'brew_packages') }}"
```

### Merge Strategies

| Strategy | Description | Use Case |
|----------|-------------|----------|
| `list` (default) | Flatten lists from all profiles | Package lists, extensions |
| `dict` | Merge dicts, later profiles override | Server configs, settings |
| `dict_recursive` | Deep merge dicts recursively | Nested configs with partial overrides |
| `first` | First defined value (lowest priority) | Defaults that can be overridden |
| `last` | Last defined value (highest priority) | Overrides from specific profiles |
| `any` | True if ANY profile has truthy value | Feature flags, optional upgrades |
| `all` | True only if ALL profiles have truthy value | Strict requirements |
| `none` | True only if NO profiles have truthy value | Inverse feature flags |

### Examples

#### List Aggregation (default)

Collects and flattens lists from all profiles in priority order.

```yaml
# Profile: common (priority 150)
brew_packages:
  - git
  - curl

# Profile: work (priority 200)
brew_packages:
  - slack
  - zoom

# Result: [git, curl, slack, zoom]
brew_packages: "{{ lookup('aggregated_profile_var', 'brew_packages') }}"
```

#### Dict Merge

Merges dictionaries, with later profiles (higher priority number) overriding earlier ones.

```yaml
# Profile: common (priority 150)
app_settings:
  theme: dark
  editor: vim

# Profile: work (priority 200)
app_settings:
  editor: code  # Override editor only

# Result: {theme: dark, editor: code}
app_settings: "{{ lookup('aggregated_profile_var', 'app_settings', merge='dict') }}"
```

#### Dict Recursive Merge

Deep merges nested dictionaries, useful for partial overrides.

```yaml
# Profile: common (priority 150)
mcp_secrets:
  openai:
    api_key: "common-key"
    org_id: "common-org"

# Profile: work (priority 200)
mcp_secrets:
  openai:
    org_id: "work-org"  # Only override org_id

# Result: {openai: {api_key: "common-key", org_id: "work-org"}}
mcp_secrets: "{{ lookup('aggregated_profile_var', 'mcp_secrets', merge='dict_recursive') }}"
```

#### First Defined Value

Returns the first defined value, from the lowest priority profile that defines it.
Useful for defaults that should come from base profiles.

```yaml
# Profile: common (priority 150)
base_theme: system

# Profile: work (priority 200)
# (not defined)

# Result: system
theme: "{{ lookup('aggregated_profile_var', 'base_theme', merge='first', default='dark') }}"
```

#### Last Defined Value

Returns the last defined value, from the highest priority profile that defines it.
Useful for overrides from specific profiles.

```yaml
# Profile: common (priority 150)
terminal_theme: dark

# Profile: work (priority 200)
terminal_theme: light

# Result: light (from highest priority profile)
theme: "{{ lookup('aggregated_profile_var', 'terminal_theme', merge='last', default='dark') }}"
```

#### Get Profile Hosts

Special `_hosts` term returns the sorted list of profile host names.

```yaml
# Get hosts for iteration
- name: Get profile hosts
  ansible.builtin.set_fact:
    profile_hosts: "{{ lookup('aggregated_profile_var', '_hosts') }}"

# Result: ['common-profile', 'work-profile'] (sorted by priority)

# Use for iteration when you need to process each profile
- name: Process each profile
  ansible.builtin.include_tasks: process_profile.yml
  loop: "{{ lookup('aggregated_profile_var', '_hosts') }}"
  loop_control:
    loop_var: profile_host
```

#### Boolean Aggregation - Any

Returns `true` if ANY profile has the variable set to a truthy value.
Useful for feature flags that any profile can enable.

```yaml
# Profile: common (priority 150)
brew_upgrade_all: true

# Profile: work (priority 200)
# (not defined)

# Result: true (because common has it set to true)
brew_upgrade_all: "{{ lookup('aggregated_profile_var', 'brew_upgrade_all', merge='any', default=false) }}"
```

#### Boolean Aggregation - All

Returns `true` only if ALL profiles that define the variable have it set to a truthy value.
Useful for strict requirements that all profiles must agree on.

```yaml
# Profile: common (priority 150)
strict_mode: true

# Profile: work (priority 200)
strict_mode: true

# Result: true (all profiles agree)
strict_mode: "{{ lookup('aggregated_profile_var', 'strict_mode', merge='all', default=false) }}"
```

#### Boolean Aggregation - None

Returns `true` only if NO profiles have the variable set to a truthy value.
Useful for inverse feature flags.

```yaml
# Profile: common (priority 150)
verbose_output: false

# Profile: work (priority 200)
# (not defined)

# Result: true (no profile has it set to true)
quiet_mode: "{{ lookup('aggregated_profile_var', 'verbose_output', merge='none', default=true) }}"
```

### Direct Usage in Loops

You can use the lookup directly in loops without setting a variable first:

```yaml
- name: Install gem packages
  community.general.gem:
    name: "{{ item }}"
    state: present
  loop: "{{ lookup('aggregated_profile_var', 'gem_packages') }}"
  when: lookup('aggregated_profile_var', 'gem_packages') | length > 0
```

### Profile Priority

Profiles are sorted by `profile_priority` variable (set by inventory plugin):

| Profile | Default Priority |
|---------|-----------------|
| default | 100 |
| common | 150 |
| work | 200 |
| personal | 200 |
| (others) | 1000 |

Lower number = processed first = lower priority in merge operations.

For `merge='dict'` and `merge='dict_recursive'`, later profiles (higher priority number) override earlier ones.

### How It Works

1. **CLI passes `--limit`**: The `dotfiles install` command passes `--limit common,work,localhost` to Ansible

2. **Plugin parses `ansible_limit`**: Extracts profile names, filtering out `localhost`

3. **Profile names → Host names**: Each profile name (e.g., `common`) maps to a group containing a host (e.g., `common-profile`)

4. **Sort by priority**: Hosts are sorted by their `profile_priority` variable

5. **Aggregate**: The variable is collected from each host's `hostvars` and merged according to the strategy

### Fallback Behavior

If no `--limit` is set (e.g., running playbook directly), the plugin uses all hosts in the `all` group.

### Error Handling

- Invalid merge strategy raises `AnsibleError` with valid options listed
- Missing variables return empty list/dict or the specified `default` value
- Non-existent profiles are silently skipped

### Comparison with Manual Aggregation

**Before (manual aggregation):**
```yaml
- name: Get all hosts
  set_fact:
    _all_hosts: "{{ groups['all'] | list }}"

- name: Sort by priority
  set_fact:
    _sorted_hosts: >-
      {{ _all_hosts
         | map('extract', hostvars, ['profile_priority'])
         | zip(_all_hosts)
         | sort(attribute='0')
         | map(attribute='1')
         | list }}

- name: Aggregate packages
  set_fact:
    brew_packages: >-
      {{ _sorted_hosts
         | map('extract', hostvars, ['brew_packages'])
         | map('default', [])
         | flatten
         | list }}
```

**After (with lookup plugin):**
```yaml
- name: Aggregate packages
  set_fact:
    brew_packages: "{{ lookup('aggregated_profile_var', 'brew_packages') }}"
```
