"""
Dynamic inventory plugin that discovers profiles from profiles/ directory.

Each profile creates:
- A group named {profile_name} (with hyphens replaced by underscores)
- A host named {profile_name}-profile (or custom host from config.yml)
- Variables loaded from profiles/{name}/config.yml (if exists)
- Auto-discovered variables:
    - profile_name: Name of the profile (from profile.name or directory name)
    - profile_dir: Path to profile directory
    - dotfiles_dir: Path to profile's dotfiles directory
    - dotfiles_copy_dir: Path to profile's dotfiles-copy directory
    - bin_dir: Path to profile's bin directory (scripts symlinked to ~/.local/bin)
    - skills_dir: Path to profile's skills directory (for AI agent skills)
    - agents_dir: Path to profile's agents directory (for AI agent definitions)
    - packages_dir: Path to profile's packages directory (pipx local packages)
    - profile_tasks_file: Path to profile's tasks/main.yml (for custom tasks)
    - profile_roles_dir: Path to profile's roles/ directory (for custom roles)
    - profile_requirements_file: Path to profile's requirements.yml (for Galaxy deps)
    - profile_priority: Profile priority for sorting (used in aggregation tasks)

Supports up to three levels of profile nesting:
- profiles/{profile}/config.yml (level 1, name is profile)
- profiles/{repo}/{profile}/config.yml (level 2, name becomes repo-profile)
- profiles/{dir}/{repo}/{profile}/config.yml (level 3, name becomes dir-repo-profile)

Usage: Create a profiles.yml file at repo root:
    plugin: dotfiles_profiles

Profile configuration in config.yml:
    profile:
      name: <profile-name>  # Optional: custom name (default: directory name or path-based)
      host: <hostname>      # Optional: Ansible host name (default: {name}-profile)
      priority: <int>       # Optional: execution order (default varies by name)

Priority: Profiles sorted by profile.priority (default varies by name), then alphabetically

Special default priorities:
    - "default" profile: priority 100
    - "common" profile: priority 150
    - "work" / "personal" profiles: priority 200 (built-in workstation types)
    - All others: priority 1000
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

# Add the shared package to Python path for Ansible plugin usage
# (Ansible plugins can't use pip dependencies directly)
_packages_dir = Path(__file__).parent.parent.parent / "packages"
_discovery_pkg = _packages_dir / "dotfiles_profile_discovery" / "src"
if str(_discovery_pkg) not in sys.path:
    sys.path.insert(0, str(_discovery_pkg))

from ansible.errors import AnsibleParserError  # noqa: E402
from ansible.plugins.inventory import BaseInventoryPlugin  # noqa: E402
from dotfiles_profile_discovery import discover_profiles  # noqa: E402

DOCUMENTATION = """
    name: dotfiles_profiles
    plugin_type: inventory
    short_description: Dynamic inventory from profiles directory
    description:
        - Scans profiles/ directory for profile configurations
        - Each profile creates a group and host automatically
        - Supports up to 3 levels of nesting (profiles/{a}/, profiles/{a}/{b}/, profiles/{a}/{b}/{c}/)
        - Requires config.yml for a directory to be considered a profile
        - Auto-discovers paths like dotfiles_dir, dotfiles_copy_dir, skills_dir, agents_dir
    options:
        profiles_dir:
            description: Path to profiles directory (relative to inventory file or absolute)
            default: profiles
            type: string
"""


class InventoryModule(BaseInventoryPlugin):
    """Dynamic inventory plugin for dotfiles profiles."""

    NAME = "dotfiles_profiles"

    def verify_file(self, path: str) -> bool:
        """Verify this is a valid config file for this plugin.

        Returns True for any .yml/.yaml file.
        """
        valid = False
        if super().verify_file(path):
            if path.endswith((".yml", ".yaml")):
                valid = True
        return valid

    def parse(self, inventory, loader, path, cache=True):
        """Parse profiles directory and populate inventory."""
        super().parse(inventory, loader, path, cache)

        # Read plugin configuration
        self._read_config_data(path)

        # Get profiles directory path
        profiles_dir_setting = self.get_option("profiles_dir") or "profiles"
        config_path = Path(path)

        # Resolve profiles directory - try relative to config file, then repo root
        if Path(profiles_dir_setting).is_absolute():
            profiles_dir = Path(profiles_dir_setting)
        else:
            # First try relative to config file location
            profiles_dir = (config_path.parent / profiles_dir_setting).resolve()
            if not profiles_dir.exists():
                # Try relative to repo root (parent of inventory file location)
                profiles_dir = (
                    config_path.parent.parent / profiles_dir_setting
                ).resolve()

        if not profiles_dir.exists():
            # No profiles directory - nothing to do (not an error)
            return

        # Use shared discovery logic
        profiles = discover_profiles(profiles_dir)

        # Validate uniqueness of profile names and host names
        seen_names: dict[str, Path] = {}  # profile_name -> path
        seen_hosts: dict[str, Path] = {}  # host_name -> path

        for p in profiles:
            if p.name in seen_names:
                raise AnsibleParserError(
                    f"Duplicate profile name '{p.name}': found in both "
                    f"'{seen_names[p.name]}' and '{p.path}'. "
                    f"Profile names must be unique across all profiles."
                )
            seen_names[p.name] = p.path

            if p.host_name in seen_hosts:
                raise AnsibleParserError(
                    f"Duplicate host name '{p.host_name}': found in both "
                    f"'{seen_hosts[p.host_name]}' and '{p.path}'. "
                    f"Host names must be unique across all profiles."
                )
            seen_hosts[p.host_name] = p.path

        # Sort profiles by priority (ascending), then by name (alphabetical)
        profiles.sort(key=lambda x: (x.priority, x.name))

        # Create inventory entries for each profile
        for profile in profiles:
            # Create group for this profile (sanitize name: replace hyphens with underscores)
            group_name = profile.name.replace("-", "_")
            self.inventory.add_group(group_name)

            # Add host to group
            self.inventory.add_host(profile.host_name, group=group_name)

            # Set connection type
            self.inventory.set_variable(
                profile.host_name, "ansible_connection", profile.connection
            )

            # Set auto-discovered variables using absolute paths
            profile_abs_path = str(profile.path)
            self.inventory.set_variable(profile.host_name, "profile_name", profile.name)
            self.inventory.set_variable(
                profile.host_name, "profile_dir", profile_abs_path
            )
            # Profile dotfiles paths (auto-discovered from standard locations)
            self.inventory.set_variable(
                profile.host_name,
                "dotfiles_dir",
                f"{profile_abs_path}/files/dotfiles",
            )
            self.inventory.set_variable(
                profile.host_name,
                "dotfiles_copy_dir",
                f"{profile_abs_path}/files/dotfiles-copy",
            )
            self.inventory.set_variable(
                profile.host_name,
                "bin_dir",
                f"{profile_abs_path}/files/bin",
            )
            # Profile skills and agents paths (for AI agent configuration)
            self.inventory.set_variable(
                profile.host_name,
                "skills_dir",
                f"{profile_abs_path}/files/skills",
            )
            self.inventory.set_variable(
                profile.host_name,
                "agents_dir",
                f"{profile_abs_path}/files/agents",
            )
            # Profile packages path (for pipx local packages)
            self.inventory.set_variable(
                profile.host_name,
                "packages_dir",
                f"{profile_abs_path}/packages",
            )
            # Profile tasks, roles, and requirements paths (for custom support)
            self.inventory.set_variable(
                profile.host_name,
                "profile_tasks_file",
                f"{profile_abs_path}/tasks/main.yml",
            )
            self.inventory.set_variable(
                profile.host_name,
                "profile_roles_dir",
                f"{profile_abs_path}/roles",
            )
            self.inventory.set_variable(
                profile.host_name,
                "profile_requirements_file",
                f"{profile_abs_path}/requirements.yml",
            )
            # Profile priority (for sorting in aggregation tasks)
            self.inventory.set_variable(
                profile.host_name, "profile_priority", profile.priority
            )

            # Set user-defined variables from config.yml
            for key, value in profile.config.items():
                self.inventory.set_variable(profile.host_name, key, value)

        # Only profiles with non-empty tasks/main.yml run in per-profile play
        self.inventory.add_group("profiles_with_tasks")
        for profile in profiles:
            tasks_file = profile.path / "tasks" / "main.yml"
            if tasks_file.exists():
                try:
                    with open(tasks_file) as f:
                        content = yaml.safe_load(f)
                    if isinstance(content, list) and len(content) > 0:
                        self.inventory.add_host(
                            profile.host_name, group="profiles_with_tasks"
                        )
                except yaml.YAMLError:
                    pass
