"""
Ansible filter plugin for recursively evaluating Jinja2 templates in data structures.

Usage in playbooks:
    {{ mcp_servers | resolve_templates(vars) }}
    {{ some_config | resolve_templates(hostvars[inventory_hostname]) }}

The filter recursively finds all string values containing '{{' and evaluates them
using Ansible's Templar with the provided variables context.

This is useful when config files contain Jinja2 expressions (like lookups) that
need to be evaluated at runtime rather than treated as literal strings.

Example:
    # Input (from config.yml loaded as data, not as Ansible variables)
    mcp_servers:
      - name: my-server
        env:
          API_KEY: "{{ lookup('vault_secret', 'mcp_secrets.api_key') }}"
          PLAIN: "plain-value"

    # After | resolve_templates(vars)
    mcp_servers:
      - name: my-server
        env:
          API_KEY: "actual-secret-value"
          PLAIN: "plain-value"
"""

from __future__ import annotations

import copy
import re
from typing import Any

from ansible.errors import AnsibleFilterError
from ansible.parsing.dataloader import DataLoader
from ansible.plugins.loader import lookup_loader
from ansible.template import Templar


class FilterModule:
    """Ansible filter plugin for recursive Jinja2 template evaluation."""

    def filters(self) -> dict[str, Any]:
        return {
            "resolve_templates": self.resolve_templates,
        }

    def resolve_templates(
        self,
        data: Any,
        variables: dict[str, Any] | None = None,
        extra_vars: dict[str, Any] | None = None,
    ) -> Any:
        """
        Recursively evaluate Jinja2 templates in a data structure.

        Args:
            data: Any data structure (dict, list, or scalar)
            variables: Variables dict to use for template evaluation.
                       Pass `vars` or `hostvars[inventory_hostname]` from playbook.
            extra_vars: Additional variables to merge into the context.
                        Use this instead of `| combine()` to avoid Ansible
                        proxy object issues with HostVarsVars.

        Returns:
            A deep copy of the data with all Jinja2 expressions evaluated.

        Raises:
            AnsibleFilterError: If template evaluation fails.
        """
        import os

        if variables is None:
            variables = {}

        if extra_vars:
            variables = {**variables, **extra_vars}

        # Check if there are any templates to resolve
        if not self._has_templates(data):
            return data

        # Get playbook_dir for configuring loader and vault
        playbook_dir = variables.get("playbook_dir", os.getcwd())

        # Create a DataLoader and set its basedir so it can find lookup plugins
        loader = DataLoader()
        loader.set_basedir(playbook_dir)

        # Try to set up vault secrets if available in variables
        # This allows vault_secret lookups to work
        self._setup_vault_secrets(loader, variables, playbook_dir)

        templar = Templar(loader=loader, variables=variables)

        # Recursively resolve templates
        return self._resolve(data, templar, variables, loader)

    def _has_templates(self, data: Any) -> bool:
        """Check if data contains any Jinja2 templates."""
        if isinstance(data, str):
            return "{{" in data or "{%" in data
        elif isinstance(data, dict):
            return any(self._has_templates(v) for v in data.values())
        elif isinstance(data, list):
            return any(self._has_templates(item) for item in data)
        return False

    def _resolve(
        self,
        data: Any,
        templar: Templar,
        variables: dict[str, Any],
        loader: DataLoader,
    ) -> Any:
        """Recursively resolve Jinja2 templates in a data structure."""
        if isinstance(data, str):
            if "{{" in data or "{%" in data:
                try:
                    # First try standard templar
                    result = templar.template(data)
                    # If result still contains unresolved lookups, try direct invocation
                    if isinstance(result, str) and "lookup(" in data:
                        result = self._resolve_lookups(data, variables, loader)
                    return result
                except Exception as e:
                    # Try direct lookup invocation as fallback
                    if "lookup(" in data:
                        try:
                            return self._resolve_lookups(data, variables, loader)
                        except Exception:
                            pass
                    raise AnsibleFilterError(
                        f"Failed to evaluate template: {data}\nError: {e}"
                    )
            return data
        elif isinstance(data, dict):
            return {
                key: self._resolve(value, templar, variables, loader)
                for key, value in data.items()
            }
        elif isinstance(data, list):
            return [self._resolve(item, templar, variables, loader) for item in data]
        return copy.deepcopy(data) if hasattr(data, "__dict__") else data

    def _resolve_lookups(
        self, template_str: str, variables: dict[str, Any], loader: DataLoader
    ) -> str:
        """
        Directly resolve lookup() calls in a template string.

        This bypasses the Templar and directly invokes lookup plugins,
        which is necessary when the Templar doesn't have the right context.
        """
        # Pattern to match {{ lookup('plugin_name', 'arg1', ...) }}
        lookup_pattern = re.compile(
            r"\{\{\s*lookup\(\s*['\"](\w+)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)\s*\}\}"
        )

        def replace_lookup(match: re.Match) -> str:
            plugin_name = match.group(1)
            lookup_arg = match.group(2)

            # Get the lookup plugin
            lookup_plugin = lookup_loader.get(plugin_name, loader=loader)
            if lookup_plugin is None:
                raise AnsibleFilterError(f"Lookup plugin not found: {plugin_name}")

            try:
                # Run the lookup with the variables context
                result = lookup_plugin.run([lookup_arg], variables=variables)
                if result and len(result) == 1:
                    return str(result[0])
                elif result:
                    return str(result)
                return ""
            except Exception as e:
                raise AnsibleFilterError(
                    f"Lookup '{plugin_name}' failed for '{lookup_arg}': {e}"
                )

        return lookup_pattern.sub(replace_lookup, template_str)

    def _setup_vault_secrets(
        self, loader: DataLoader, variables: dict[str, Any], playbook_dir: str
    ) -> None:
        """Set up vault secrets on the loader if vault password is available."""
        import os
        from pathlib import Path

        from ansible.parsing.vault import VaultSecret

        # Check for .vault_password file
        vault_pass_file = Path(playbook_dir) / ".vault_password"
        if vault_pass_file.exists():
            try:
                vault_password = vault_pass_file.read_text().strip().encode()
                loader.set_vault_secrets([(None, VaultSecret(vault_password))])
                return
            except (OSError, IOError):
                pass

        # Try environment variable
        env_password = os.environ.get("ANSIBLE_VAULT_PASSWORD")
        if env_password:
            loader.set_vault_secrets([(None, VaultSecret(env_password.encode()))])
