"""
Ansible filter plugin for resolving 1Password (op://) references in data structures.

Usage in templates:
    {{ mcp_servers | resolve_op_secrets }}
    {{ some_config | resolve_op_secrets }}

The filter recursively finds all string values starting with 'op://' and resolves
them using the 1Password CLI (op read).

Requirements:
    - 1Password CLI must be installed: brew install 1password-cli
    - User must be signed in: op signin

Examples:
    # Input
    mcp_servers:
      - name: my-server
        env:
          API_KEY: "op://Vault/Item/password"
          OTHER: "plain-value"

    # Output (after | resolve_op_secrets)
    mcp_servers:
      - name: my-server
        env:
          API_KEY: "actual-secret-value"
          OTHER: "plain-value"
"""

from __future__ import annotations

import copy
import shutil
import subprocess
from functools import lru_cache
from typing import Any

from ansible.errors import AnsibleFilterError


class FilterModule:
    """Ansible filter plugin for 1Password secret resolution."""

    def filters(self) -> dict[str, Any]:
        return {
            "resolve_op_secrets": self.resolve_op_secrets,
        }

    def resolve_op_secrets(self, data: Any) -> Any:
        """
        Resolve all op:// references in a data structure.

        Args:
            data: Any data structure (dict, list, or scalar)

        Returns:
            A deep copy of the data with all op:// references resolved

        Raises:
            AnsibleFilterError: If 1Password CLI is not available or user not signed in
        """
        # Collect all op:// references first
        refs = self._collect_op_refs(data)

        if not refs:
            # No op:// references, return data unchanged
            return data

        # Check if op CLI is available
        if not shutil.which("op"):
            raise AnsibleFilterError(
                "1Password CLI (op) is required but not available.\n\n"
                f"Some values have op:// references that need resolution:\n"
                f"  {', '.join(sorted(refs)[:5])}"
                + (f"\n  ... and {len(refs) - 5} more" if len(refs) > 5 else "")
                + "\n\n"
                "To fix this:\n"
                "  1. Install 1Password CLI: brew install 1password-cli\n"
                "  2. Sign in: op signin\n"
                "  3. Re-run this playbook\n\n"
                "Alternatively, use Ansible vault secrets instead of op:// references."
            )

        # Check if signed in
        if not self._is_signed_in():
            raise AnsibleFilterError(
                "1Password CLI is installed but you are not signed in.\n\n"
                "To sign in, run:\n"
                "  op signin\n\n"
                "Or use biometric unlock:\n"
                "  op signin --account <your-account>"
            )

        # Resolve all references
        secrets = {}
        for ref in refs:
            secrets[ref] = self._read_secret(ref)

        # Apply resolved secrets to a deep copy of the data
        return self._apply_secrets(copy.deepcopy(data), secrets)

    def _collect_op_refs(self, data: Any, refs: set[str] | None = None) -> set[str]:
        """Recursively collect all op:// references from a data structure."""
        if refs is None:
            refs = set()

        if isinstance(data, str):
            if data.startswith("op://"):
                refs.add(data)
        elif isinstance(data, dict):
            for value in data.values():
                self._collect_op_refs(value, refs)
        elif isinstance(data, list):
            for item in data:
                self._collect_op_refs(item, refs)

        return refs

    def _apply_secrets(self, data: Any, secrets: dict[str, str]) -> Any:
        """Recursively apply resolved secrets to a data structure."""
        if isinstance(data, str):
            return secrets.get(data, data)
        elif isinstance(data, dict):
            return {
                key: self._apply_secrets(value, secrets) for key, value in data.items()
            }
        elif isinstance(data, list):
            return [self._apply_secrets(item, secrets) for item in data]
        return data

    def _is_signed_in(self) -> bool:
        """Check if user is signed in to 1Password."""
        try:
            result = subprocess.run(
                ["op", "account", "list"],
                capture_output=True,
                timeout=10,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            return False

    @lru_cache(maxsize=128)
    def _read_secret(self, ref: str) -> str:
        """Read a secret from 1Password. Results are cached."""
        try:
            result = subprocess.run(
                ["op", "read", ref],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                raise AnsibleFilterError(
                    f"Failed to read 1Password secret: {ref}\n"
                    f"Error: {result.stderr.strip()}"
                )
            return result.stdout.rstrip("\n")
        except subprocess.TimeoutExpired:
            raise AnsibleFilterError(
                f"Timeout reading 1Password secret: {ref}\n"
                "This might indicate a network issue or 1Password is unresponsive."
            )
        except OSError as e:
            raise AnsibleFilterError(f"Error running 'op read': {e}")
