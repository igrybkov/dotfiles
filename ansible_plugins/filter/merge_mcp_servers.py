"""Ansible filter plugin that collapses cross-profile mcp_servers entries.

Multiple profiles may each declare an entry in `mcp_servers:` with the same
`name:`. Exactly one of those entries is the *owner* — it sets `command:` or
`url:` and carries the rest of the server's shape. The others are
*contributors*: partial entries that add extra `secret_env:` / `env:` pairs to
the shared server.

Each entry reaches this filter tagged with `_profile` (injected by the
playbook's aggregation step). Contributor `secret_env:` values get
`@<contributor>` auto-appended so `run-with-secrets.sh` routes them to the
contributing profile's vault.

Example::

    # productivity/config.yml — owner
    mcp_servers:
      - name: obsidian
        command: obsidian-mcp-server
        secret_env:
          OBSIDIAN_API_KEY_GARDEN: mcp_secrets.obsidian.digital_garden.api_key

    # adobe/config.yml — contributor
    mcp_servers:
      - name: obsidian
        secret_env:
          OBSIDIAN_API_KEY_ADOBE: mcp_secrets.obsidian_adobe.api_key

After merge: one `obsidian` entry whose `secret_env` contains both keys, with
the Adobe value rewritten to `mcp_secrets.obsidian_adobe.api_key@private-adobe`.

Rules:

1. **Owner** = entry with `command:` or `url:`. At most one owner per name.
   Zero owners when contributions exist → error.
2. **Contributor fields** are restricted to `name`, `secret_env`, `env`, plus
   the auto-injected `_profile`. Anything else → error.
3. **Contributions from the owner's own profile** stay bare (no suffix).
4. **`env:` contributions** are unioned verbatim (no suffix — not a vault path).
5. **Conflicts** (same var declared twice across owner + contributors) abort
   with both source profiles in the error.
6. **Non-contribution shapes pass through.** An entry that has fields other
   than `{name, secret_env, env, _profile}` is not a contribution — it's a
   standalone record (owner, pruning entry like `name + config_files`, or
   top-level `state: absent`). It appears verbatim in the result and never
   merges with anything else.
"""

from __future__ import annotations

import copy
from typing import Any

from ansible.errors import AnsibleFilterError

_CONTRIB_ALLOWED_FIELDS = frozenset({"name", "secret_env", "env", "_profile"})


class FilterModule:
    """Ansible filter plugin: merge_mcp_servers."""

    def filters(self) -> dict[str, Any]:
        return {"merge_mcp_servers": self.merge_mcp_servers}

    def merge_mcp_servers(self, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Collapse same-name entries into owners; see module docstring."""
        entries = [copy.deepcopy(e) for e in entries]

        # Validate names upfront so every downstream branch can assume truthy.
        for e in entries:
            if not e.get("name"):
                raise AnsibleFilterError(
                    "merge_mcp_servers: entry missing 'name' field"
                )

        # An entry is a *contribution* iff it only carries contribution-shape
        # fields and declares at least one secret_env/env pair. Anything else
        # (owners, pruning entries like `name + config_files`, top-level
        # `state: absent`) passes through unchanged.
        def is_contribution(e: dict[str, Any]) -> bool:
            if set(e) - _CONTRIB_ALLOWED_FIELDS:
                return False
            return bool(e.get("secret_env") or e.get("env"))

        # Owners: non-contribution entries that set command or url. At most
        # one per name.
        owners: dict[str, dict[str, Any]] = {}
        for e in entries:
            if is_contribution(e):
                continue
            if not (e.get("command") or e.get("url")):
                continue
            name = e["name"]
            if name in owners:
                prev = owners[name].get("_profile", "<unknown>")
                cur = e.get("_profile", "<unknown>")
                raise AnsibleFilterError(
                    f"merge_mcp_servers: server {name!r} declared with "
                    f"'command'/'url' by two profiles ({prev!r} and "
                    f"{cur!r}); exactly one profile may own each server"
                )
            owners[name] = e

        # Track source of each env/secret_env var for conflict error messages.
        secret_sources: dict[tuple[str, str], str] = {}
        env_sources: dict[tuple[str, str], str] = {}
        for name, owner in owners.items():
            owner_profile = owner.get("_profile", "<unknown>")
            for var in owner.get("secret_env") or {}:
                secret_sources[(name, var)] = owner_profile
            for var in owner.get("env") or {}:
                env_sources[(name, var)] = owner_profile

        result: list[dict[str, Any]] = []
        for e in entries:
            if not is_contribution(e):
                result.append(e)
                continue

            name = e["name"]
            contributor = e.get("_profile", "<unknown>")
            if name not in owners:
                raise AnsibleFilterError(
                    f"merge_mcp_servers: server {name!r} has contribution "
                    f"from profile {contributor!r} but no profile declares "
                    f"it with 'command' or 'url'"
                )

            owner = owners[name]
            owner_profile = owner.get("_profile", "<unknown>")
            suffix = "" if contributor == owner_profile else f"@{contributor}"

            secret_contribution = e.get("secret_env") or {}
            if not isinstance(secret_contribution, dict):
                raise AnsibleFilterError(
                    f"merge_mcp_servers: non-mapping 'secret_env' in "
                    f"contribution to {name!r} from {contributor!r}"
                )
            for var, path in secret_contribution.items():
                if not isinstance(path, str):
                    raise AnsibleFilterError(
                        f"merge_mcp_servers: non-string secret_env value "
                        f"for {var!r} on {name!r} from profile "
                        f"{contributor!r}"
                    )
                key = (name, var)
                if key in secret_sources:
                    raise AnsibleFilterError(
                        f"merge_mcp_servers: secret_env var {var!r} on "
                        f"server {name!r} is declared by both "
                        f"{secret_sources[key]!r} and {contributor!r}"
                    )
                owner.setdefault("secret_env", {})
                if owner["secret_env"] is None:
                    owner["secret_env"] = {}
                owner["secret_env"][var] = f"{path}{suffix}"
                secret_sources[key] = contributor

            env_contribution = e.get("env") or {}
            if not isinstance(env_contribution, dict):
                raise AnsibleFilterError(
                    f"merge_mcp_servers: non-mapping 'env' in contribution "
                    f"to {name!r} from {contributor!r}"
                )
            for var, value in env_contribution.items():
                key = (name, var)
                if key in env_sources:
                    raise AnsibleFilterError(
                        f"merge_mcp_servers: env var {var!r} on server "
                        f"{name!r} is declared by both "
                        f"{env_sources[key]!r} and {contributor!r}"
                    )
                owner.setdefault("env", {})
                if owner["env"] is None:
                    owner["env"] = {}
                owner["env"][var] = value
                env_sources[key] = contributor

        return result
