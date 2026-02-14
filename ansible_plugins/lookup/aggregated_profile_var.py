"""Lookup plugin to aggregate variables from enabled profile hosts.

See README.md in this directory for detailed documentation.
"""

from __future__ import annotations

from ansible.errors import AnsibleError
from ansible.plugins.lookup import LookupBase

DOCUMENTATION = r"""
name: aggregated_profile_var
author: dotfiles
version_added: "1.0.0"
short_description: Aggregate variables from enabled profile hosts
description:
  - Aggregates a variable from all enabled profile hosts.
  - Automatically accesses hostvars, groups, and active_profiles from context.
  - Supports multiple merge strategies for lists, dicts, and scalar values.
  - Profiles are sorted by priority before aggregation.
options:
  _terms:
    description: Variable name(s) to aggregate. Use '_hosts' to get the sorted list of profile host names.
    required: true
    type: list
    elements: str
  merge:
    description: "Merge strategy: list (default), dict, dict_recursive, first, last, any, all, or none."
    type: str
    default: list
    choices:
      - list
      - dict
      - dict_recursive
      - first
      - last
      - any
      - all
      - none
  default:
    description: Default value if variable not found in any profile. Used with first, last, and boolean strategies.
    type: raw
    default: null
notes:
  - Parses ansible_limit to get active profiles (e.g., --limit common,work,localhost).
  - Falls back to all hosts in all group if no limit is set.
  - Profiles are sorted by profile_priority variable (ascending).
"""

EXAMPLES = """
# Aggregate list variable (default strategy)
- name: Get all brew packages from enabled profiles
  set_fact:
    brew_packages: "{{ lookup('aggregated_profile_var', 'brew_packages') }}"

# Aggregate dict variable (later profiles override)
- name: Get app settings configuration
  set_fact:
    app_settings: "{{ lookup('aggregated_profile_var', 'app_settings', merge='dict') }}"

# Aggregate dict with recursive merge
- name: Get MCP secrets with deep merge
  set_fact:
    mcp_secrets: "{{ lookup('aggregated_profile_var', 'mcp_secrets', merge='dict_recursive') }}"

# Get first defined value (from lowest priority profile)
- name: Get base theme from first profile that defines it
  set_fact:
    base_theme: "{{ lookup('aggregated_profile_var', 'base_theme', merge='first', default='system') }}"

# Get last defined value (from highest priority profile)
- name: Get theme from highest priority profile
  set_fact:
    theme: "{{ lookup('aggregated_profile_var', 'terminal_theme', merge='last', default='dark') }}"

# Get sorted list of profile host names
- name: Get profile hosts for iteration
  set_fact:
    profile_hosts: "{{ lookup('aggregated_profile_var', '_hosts') }}"

# Use directly in a loop
- name: Install gem packages
  community.general.gem:
    name: "{{ item }}"
  loop: "{{ lookup('aggregated_profile_var', 'gem_packages') }}"

# Boolean aggregation - any (true if ANY profile has true)
- name: Check if any profile wants to upgrade all brew packages
  set_fact:
    brew_upgrade_all: "{{ lookup('aggregated_profile_var', 'brew_upgrade_all', merge='any', default=false) }}"

# Boolean aggregation - all (true only if ALL profiles have true)
- name: Check if all profiles require strict mode
  set_fact:
    strict_mode: "{{ lookup('aggregated_profile_var', 'strict_mode', merge='all', default=false) }}"

# Boolean aggregation - none (true only if NO profiles have true)
- name: Check if no profiles want verbose output
  set_fact:
    quiet_mode: "{{ lookup('aggregated_profile_var', 'verbose_output', merge='none', default=true) }}"
"""

RETURN = """
_raw:
    description:
        - Aggregated value(s) from profile hosts
        - Type depends on merge strategy and source variable type
    type: any
"""


class LookupModule(LookupBase):
    """Lookup plugin for aggregating variables from profile hosts."""

    def run(self, terms, variables=None, **kwargs):
        if variables is None:
            raise AnsibleError(
                "aggregated_profile_var lookup requires access to variables"
            )

        # Get Ansible context variables
        hostvars = variables.get("hostvars", {})
        groups = variables.get("groups", {})

        # Get active profiles from --limit (e.g., "common,work,localhost")
        active_profiles = None
        ansible_limit = variables.get("ansible_limit")
        if ansible_limit:
            # Split by comma, filter out localhost and empty strings
            active_profiles = [
                p.strip()
                for p in ansible_limit.split(",")
                if p.strip() and p.strip() != "localhost"
            ]

        # Get options
        merge_strategy = kwargs.get("merge", "list")
        default_value = kwargs.get("default")

        # Validate merge strategy
        valid_strategies = (
            "list",
            "dict",
            "dict_recursive",
            "first",
            "last",
            "any",
            "all",
            "none",
        )
        if merge_strategy not in valid_strategies:
            raise AnsibleError(
                f"Invalid merge strategy '{merge_strategy}'. "
                f"Valid options: {', '.join(valid_strategies)}"
            )

        # Build sorted host list from active profiles
        hosts = self._get_profile_hosts(active_profiles, groups, hostvars)

        results = []
        for term in terms:
            if term == "_hosts":
                # Special case: return the host list itself
                results.append(hosts)
            elif merge_strategy == "first":
                results.append(
                    self._aggregate_first(term, hosts, hostvars, default_value)
                )
            elif merge_strategy == "last":
                results.append(
                    self._aggregate_last(term, hosts, hostvars, default_value)
                )
            elif merge_strategy in ("dict", "dict_recursive"):
                results.append(
                    self._aggregate_dict(term, hosts, hostvars, merge_strategy)
                )
            elif merge_strategy in ("any", "all", "none"):
                results.append(
                    self._aggregate_bool(
                        term, hosts, hostvars, merge_strategy, default_value
                    )
                )
            else:  # list (default)
                results.append(self._aggregate_list(term, hosts, hostvars))

        return results

    def _get_profile_hosts(
        self,
        active_profiles: list[str] | None,
        groups: dict,
        hostvars: dict,
    ) -> list[str]:
        """Convert active profile names to sorted host names."""
        if not active_profiles:
            # Fallback to all hosts if no active_profiles specified
            hosts = list(groups.get("all", []))
        else:
            # Convert profile names to host names via groups lookup
            hosts = []
            for profile in active_profiles:
                profile_hosts = groups.get(profile, [])
                hosts.extend(profile_hosts)

        # Sort by profile_priority (ascending - lower priority number = earlier)
        def get_priority(host: str) -> int:
            return hostvars.get(host, {}).get("profile_priority", 1000)

        return sorted(hosts, key=get_priority)

    def _aggregate_list(self, var_name: str, hosts: list[str], hostvars: dict) -> list:
        """Aggregate list variable from all hosts."""
        result = []
        for host in hosts:
            value = hostvars.get(host, {}).get(var_name, [])
            if isinstance(value, list):
                result.extend(value)
            elif value:
                result.append(value)
        return result

    def _aggregate_dict(
        self, var_name: str, hosts: list[str], hostvars: dict, strategy: str
    ) -> dict:
        """Aggregate dict variable from all hosts."""
        result = {}
        for host in hosts:
            value = hostvars.get(host, {}).get(var_name, {})
            if isinstance(value, dict):
                if strategy == "dict_recursive":
                    result = self._deep_merge(result, value)
                else:
                    result.update(value)
        return result

    def _aggregate_first(
        self, var_name: str, hosts: list[str], hostvars: dict, default
    ):
        """Get first defined value from hosts (lowest priority profile)."""
        for host in hosts:
            value = hostvars.get(host, {}).get(var_name)
            if value is not None:
                return value
        return default

    def _aggregate_last(self, var_name: str, hosts: list[str], hostvars: dict, default):
        """Get last defined value from hosts (highest priority profile)."""
        for host in reversed(hosts):
            value = hostvars.get(host, {}).get(var_name)
            if value is not None:
                return value
        return default

    def _aggregate_bool(
        self,
        var_name: str,
        hosts: list[str],
        hostvars: dict,
        strategy: str,
        default,
    ) -> bool:
        """Aggregate boolean values from hosts using any/all/none logic.

        Args:
            var_name: The variable name to aggregate
            hosts: List of host names to check
            hostvars: Dictionary of host variables
            strategy: One of 'any', 'all', or 'none'
            default: Default value if no hosts define the variable

        Returns:
            - any: True if ANY host has a truthy value
            - all: True if ALL hosts with the variable defined have truthy values
            - none: True if NO hosts have a truthy value
        """
        values = []
        for host in hosts:
            host_vars = hostvars.get(host, {})
            if var_name in host_vars:
                values.append(bool(host_vars[var_name]))

        if not values:
            # No hosts define the variable, return default
            return bool(default) if default is not None else False

        if strategy == "any":
            return any(values)
        elif strategy == "all":
            return all(values)
        else:  # none
            return not any(values)

    def _deep_merge(self, base: dict, override: dict) -> dict:
        """Recursively merge override into base dict."""
        result = base.copy()
        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result
