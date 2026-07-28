"""MCP servers deploy — write per-server entries into MCP config files.

Mirrors ``roles/mcp_servers/tasks/`` (``main.yml`` + ``config_file.yml`` +
``git_repos.yml`` + ``remove_absent.yml``) and ports the cross-profile merge
from ``ansible_plugins/filter/merge_mcp_servers.py``.

This deploy runs against ``merged_all`` (every enabled profile), because writing
the ``mcpServers`` block of a shared config file is destructive: a server that
only one profile declares must still survive a run that selected a different
profile, and absent servers must be removed regardless of selection.

Pipeline (matching the Ansible role's ordering):

  1. Flatten the per-profile nested lists into a single list of entries, then
     collapse same-name contributors into their owners via
     :func:`_merge_mcp_servers` (a faithful port of the filter plugin).
  2. Clone/update ``git_repo`` servers — a real pyinfra ``git.repo`` operation,
     not build-time work, so the clone *executes* on the host.
  3. For each target config file: read the current JSON at build time, drop
     absent servers, add available present servers (rewriting ``secret_env``
     servers to go through ``bin/run-with-secrets.sh``), and write the merged
     result back.

Two simplifications versus the Ansible role, both deliberate:

  * Command availability is checked at build time (``shutil.which`` /
    ``os.path.isfile``). Brew already ran earlier in the same pyinfra run, so
    PATH-installed commands resolve. A server whose ``command`` is a binary
    produced by its own ``git_repo`` clone will not exist on the first run and
    is skipped — same first-run limitation the role tolerates via its
    availability check, just evaluated earlier.
  * Plain ``env``/``headers`` values are written verbatim — inline Jinja
    ``{{ lookup('vault_secret', …) }}`` expressions are NOT rendered (the old
    role's Jinja filters have no pyinfra equivalent). Secrets belong in
    ``secret_env`` (resolved at spawn time by the wrapper) or, for URL servers,
    ``secret_headers`` (resolved at build time via sops and merged into
    ``headers``; the plaintext lands in the rendered config file, same as the
    old install-time lookup behavior).

Caller contract: ``merged["mcp_servers"]`` is what ``merge_var(..., "list")``
produces — a list of per-profile sub-lists. Each entry carries a ``_profile``
key (the owning profile name, injected by ``deploy/inventory.py``) so the
merge can route contributor secrets and the wrapper can target the right
vault.
"""

from __future__ import annotations

import copy
import io
import json
import os
import shutil
from pathlib import Path
from typing import Any

from pyinfra import logger
from pyinfra.operations import files, git

from dotfiles_pyinfra.secrets import decrypt_key

# Fields a *contribution* entry may carry. Anything else makes the entry a
# standalone record (owner, pruning entry, top-level absent) — see the filter
# plugin docstring.
_CONTRIB_ALLOWED_FIELDS = frozenset(
    {"name", "secret_env", "env", "secret_headers", "_profile"}
)

# Default config files when a server does not declare its own ``config_files``.
# Mirrors ``mcp_default_config_files`` in roles/mcp_servers/defaults/main.yml;
# overridable via ``merged["mcp_default_config_files"]``.
_DEFAULT_CONFIG_FILES: list[dict[str, Any]] = [
    {"path": "~/.mcp.json"},
    {
        "path": "~/Library/Application Support/Claude/claude_desktop_config.json",
        "optional": True,
    },
]


def deploy(merged: dict[str, Any], dotfiles_dir: Path) -> None:
    """Configure MCP servers across their target config files.

    Args:
        merged: Merged profile data (use ``merged_all`` — destructive writes).
        dotfiles_dir: Root of the dotfiles repository; locates the
            ``bin/run-with-secrets.sh`` wrapper baked into ``secret_env``
            server commands.
    """
    raw = merged.get("mcp_servers", []) or []

    # merge_var(..., "list") yields per-profile sub-lists; older/normalized
    # callers may pass a flat list. Accept both.
    flat: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, list):
            flat.extend(item)
        else:
            flat.append(item)

    if not flat:
        return

    servers = _merge_mcp_servers(flat)

    default_config_files = (
        merged.get("mcp_default_config_files") or _DEFAULT_CONFIG_FILES
    )

    # 1. Git-backed servers: clone/update as a real operation (not build-time).
    _git_repos(servers, merged)

    # 2. Group every server by each config-file path it targets, then write each
    #    file once. Absent servers force their targets to be treated as optional
    #    (we only prune; never create a file just to delete an entry).
    files_map: dict[str, list[dict[str, Any]]] = {}
    optional_map: dict[str, bool] = {}

    for srv in servers:
        server_absent = srv.get("state") == "absent"
        for cf in _normalize_config_files(srv, default_config_files):
            path = cf["path"]
            # Effective per-file state: a present server may still be absent
            # from individual files via `config_files: [{path, state: absent}]`
            # (mirrors the role's `item.1.state | default('present')`).
            entry_absent = server_absent or cf["state"] == "absent"
            optional = bool(cf.get("optional", False)) or entry_absent
            files_map.setdefault(path, []).append(
                {**srv, "state": "absent"} if entry_absent else srv
            )
            # A path is optional only if *every* entry targeting it is optional.
            optional_map[path] = optional_map.get(path, True) and optional

    run_with_secrets = str(dotfiles_dir / "bin" / "run-with-secrets.sh")

    for raw_path, srvs in files_map.items():
        _configure_file(
            raw_path=raw_path,
            servers=srvs,
            optional=optional_map[raw_path],
            run_with_secrets=run_with_secrets,
            dotfiles_dir=dotfiles_dir,
        )


# ---------------------------------------------------------------------------
# Cross-profile merge — faithful port of merge_mcp_servers.py
# ---------------------------------------------------------------------------


class MergeMcpServersError(ValueError):
    """Raised when cross-profile mcp_servers entries conflict."""


def _merge_mcp_servers(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse same-name contributor entries into their owner.

    Port of ``ansible_plugins/filter/merge_mcp_servers.py``. An *owner* sets
    ``command`` or ``url`` (at most one per name). A *contribution* carries only
    ``{name, secret_env, env, _profile}`` plus at least one ``secret_env``/``env``
    pair; its values are folded into the owner, with secret paths suffixed
    ``@<contributor>`` unless the contributor *is* the owner's profile. Every
    other entry passes through verbatim.
    """
    entries = [copy.deepcopy(e) for e in entries]

    for e in entries:
        if not e.get("name"):
            raise MergeMcpServersError("merge_mcp_servers: entry missing 'name' field")

    def is_contribution(e: dict[str, Any]) -> bool:
        if set(e) - _CONTRIB_ALLOWED_FIELDS:
            return False
        return bool(e.get("secret_env") or e.get("env") or e.get("secret_headers"))

    # Owners: non-contribution entries that set command or url. At most one
    # per name.
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
            raise MergeMcpServersError(
                f"merge_mcp_servers: server {name!r} declared with "
                f"'command'/'url' by two profiles ({prev!r} and "
                f"{cur!r}); exactly one profile may own each server"
            )
        owners[name] = e

    # Track source of each env/secret_env/header var for conflict error
    # messages. Headers share one namespace: plain ``headers`` and
    # ``secret_headers`` both land in the rendered ``headers`` block.
    secret_sources: dict[tuple[str, str], str] = {}
    env_sources: dict[tuple[str, str], str] = {}
    header_sources: dict[tuple[str, str], str] = {}
    for name, owner in owners.items():
        owner_profile = owner.get("_profile", "<unknown>")
        for var in owner.get("secret_env") or {}:
            secret_sources[(name, var)] = owner_profile
        for var in owner.get("env") or {}:
            env_sources[(name, var)] = owner_profile
        for var in owner.get("headers") or {}:
            header_sources[(name, var)] = owner_profile
        for var in owner.get("secret_headers") or {}:
            if (name, var) in header_sources:
                raise MergeMcpServersError(
                    f"merge_mcp_servers: header {var!r} on server {name!r} is "
                    f"declared in both 'headers' and 'secret_headers'"
                )
            header_sources[(name, var)] = owner_profile

    result: list[dict[str, Any]] = []
    for e in entries:
        if not is_contribution(e):
            result.append(e)
            continue

        name = e["name"]
        contributor = e.get("_profile", "<unknown>")
        if name not in owners:
            raise MergeMcpServersError(
                f"merge_mcp_servers: server {name!r} has contribution from "
                f"profile {contributor!r} but no profile declares it with "
                f"'command' or 'url'"
            )

        owner = owners[name]
        owner_profile = owner.get("_profile", "<unknown>")
        suffix = "" if contributor == owner_profile else f"@{contributor}"

        secret_contribution = e.get("secret_env") or {}
        if not isinstance(secret_contribution, dict):
            raise MergeMcpServersError(
                f"merge_mcp_servers: non-mapping 'secret_env' in contribution "
                f"to {name!r} from {contributor!r}"
            )
        for var, path in secret_contribution.items():
            if not isinstance(path, str):
                raise MergeMcpServersError(
                    f"merge_mcp_servers: non-string secret_env value for "
                    f"{var!r} on {name!r} from profile {contributor!r}"
                )
            key = (name, var)
            if key in secret_sources:
                raise MergeMcpServersError(
                    f"merge_mcp_servers: secret_env var {var!r} on server "
                    f"{name!r} is declared by both {secret_sources[key]!r} "
                    f"and {contributor!r}"
                )
            if owner.get("secret_env") is None:
                owner["secret_env"] = {}
            owner["secret_env"][var] = f"{path}{suffix}"
            secret_sources[key] = contributor

        header_contribution = e.get("secret_headers") or {}
        if not isinstance(header_contribution, dict):
            raise MergeMcpServersError(
                f"merge_mcp_servers: non-mapping 'secret_headers' in "
                f"contribution to {name!r} from {contributor!r}"
            )
        for var, path in header_contribution.items():
            if not isinstance(path, str):
                raise MergeMcpServersError(
                    f"merge_mcp_servers: non-string secret_headers value for "
                    f"{var!r} on {name!r} from profile {contributor!r}"
                )
            key = (name, var)
            if key in header_sources:
                raise MergeMcpServersError(
                    f"merge_mcp_servers: header {var!r} on server {name!r} is "
                    f"declared by both {header_sources[key]!r} and "
                    f"{contributor!r}"
                )
            if owner.get("secret_headers") is None:
                owner["secret_headers"] = {}
            owner["secret_headers"][var] = f"{path}{suffix}"
            header_sources[key] = contributor

        env_contribution = e.get("env") or {}
        if not isinstance(env_contribution, dict):
            raise MergeMcpServersError(
                f"merge_mcp_servers: non-mapping 'env' in contribution to "
                f"{name!r} from {contributor!r}"
            )
        for var, value in env_contribution.items():
            key = (name, var)
            if key in env_sources:
                raise MergeMcpServersError(
                    f"merge_mcp_servers: env var {var!r} on server {name!r} is "
                    f"declared by both {env_sources[key]!r} and {contributor!r}"
                )
            if owner.get("env") is None:
                owner["env"] = {}
            owner["env"][var] = value
            env_sources[key] = contributor

    return result


# ---------------------------------------------------------------------------
# Git repositories
# ---------------------------------------------------------------------------


def _git_repos(servers: list[dict[str, Any]], merged: dict[str, Any]) -> None:
    """Clone/update git-backed MCP servers (present state only).

    Deduplicated by destination so monorepo servers sharing a ``git_dest`` are
    cloned once. This is a real pyinfra operation: the clone executes on the
    host, so a command living inside the clone can resolve on subsequent runs.
    """
    base = str(
        Path(
            merged.get("mcp_servers_git_base", "~/.local/share/mcp-servers")
        ).expanduser()
    )

    seen: dict[str, dict[str, Any]] = {}
    for srv in servers:
        if "git_repo" not in srv:
            continue
        if srv.get("state", "present") != "present":
            continue
        name = srv["name"]
        dest = str(Path(srv.get("git_dest", f"{base}/{name}")).expanduser())
        if dest in seen:
            continue
        seen[dest] = {
            "git_repo": srv["git_repo"],
            "git_version": srv.get("git_version", "HEAD"),
            "git_force": bool(srv.get("git_force", False)),
            "name": name,
        }

    for dest, repo in seen.items():
        # "HEAD" means "the remote's default branch" (Ansible git's default);
        # pyinfra clones the default branch when branch is None, whereas
        # branch="HEAD" would emit an invalid `git clone --branch HEAD`.
        version = repo["git_version"]
        branch = None if version == "HEAD" else version
        git.repo(
            name=f"Clone/update MCP server repo {repo['name']}",
            src=repo["git_repo"],
            dest=dest,
            branch=branch,
            pull=True,
            rebase=False,
        )


# ---------------------------------------------------------------------------
# Config file assembly + write
# ---------------------------------------------------------------------------


def _normalize_config_files(
    server: dict[str, Any], defaults: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Return a server's target config files as ``{path, optional, state}`` dicts.

    Items may be plain path strings or ``{path, optional, state}`` mappings.
    When the server declares no ``config_files`` the role defaults apply.
    """
    raw = server.get("config_files")
    source = raw if raw is not None else defaults

    normalized: list[dict[str, Any]] = []
    for cf in source:
        if isinstance(cf, str):
            normalized.append({"path": cf, "optional": False, "state": "present"})
        elif isinstance(cf, dict):
            normalized.append(
                {
                    "path": cf["path"],
                    "optional": bool(cf.get("optional", False)),
                    "state": cf.get("state", "present"),
                }
            )
        else:
            raise MergeMcpServersError(
                f"mcp_servers: invalid config_files entry {cf!r} on "
                f"server {server.get('name')!r}"
            )
    return normalized


def _configure_file(
    *,
    raw_path: str,
    servers: list[dict[str, Any]],
    optional: bool,
    run_with_secrets: str,
    dotfiles_dir: Path,
) -> None:
    """Build and write one MCP config file's ``mcpServers`` block."""
    path = Path(raw_path).expanduser()
    parent = path.parent

    if not parent.exists():
        if optional:
            logger.debug(
                f"mcp_servers: skipping optional {path} — parent dir "
                f"{parent} does not exist"
            )
            return
        files.directory(
            name=f"Ensure parent dir for {path}",
            path=str(parent),
            present=True,
            mode="755",
        )

    # Read existing config at build time (correct here: we need current state to
    # compute the merge, and nothing this op depends on mutates the file first).
    existing: dict[str, Any] = {}
    if path.exists():
        text = path.read_text()
        if text.strip():
            try:
                existing = json.loads(text)
            except json.JSONDecodeError as exc:
                logger.warning(f"Ignoring invalid JSON in {path}: {exc}")
                existing = {}

    existing_servers: dict[str, Any] = dict(existing.get("mcpServers", {}))

    has_secrets = False
    for srv in servers:
        name = srv["name"]

        if srv.get("state") == "absent":
            existing_servers.pop(name, None)
            continue

        # URL servers pass through; command servers must be available.
        if "url" not in srv:
            if not _command_available(srv.get("command", "")):
                logger.warning(
                    f"mcp_servers: skipping {name!r} — command "
                    f"{srv.get('command')!r} not found"
                )
                continue
        elif srv.get("secret_headers"):
            headers = _resolve_secret_headers(srv, dotfiles_dir)
            if headers is None:
                logger.warning(
                    f"mcp_servers: skipping {name!r} — could not resolve "
                    f"secret_headers (see warnings above)"
                )
                continue
            srv = {**srv, "headers": headers}

        built = _build_server(srv, run_with_secrets)
        if _server_has_secrets(srv):
            has_secrets = True
        existing_servers[name] = built

    config = {**existing, "mcpServers": existing_servers}
    mode = "600" if has_secrets else "644"
    payload = json.dumps(config, indent=2, sort_keys=True).encode() + b"\n"

    try:
        path_label = "~/" + str(path.relative_to(Path.home()))
    except ValueError:
        path_label = str(path)
    files.put(
        name=f"Configure MCP servers in {path_label}",
        src=io.BytesIO(payload),
        dest=str(path),
        mode=mode,
    )


def _command_available(command: str) -> bool:
    """True if a command-based server's command resolves at build time.

    A path-like command (containing ``/``) is checked as a file; a bare name is
    resolved on PATH. Brew already ran earlier in the pyinfra run, so
    PATH-installed tools are present.
    """
    if not command:
        return False
    expanded = os.path.expanduser(command)
    if "/" in expanded:
        return os.path.isfile(expanded)
    return shutil.which(expanded) is not None


def _resolve_secret_headers(
    server: dict[str, Any], dotfiles_dir: Path
) -> dict[str, str] | None:
    """Resolve a URL server's ``secret_headers`` into a full headers dict.

    Values are ``key.path`` (resolved against the server's owning profile) or
    ``key.path@profile``. Returns plain ``headers`` merged with the resolved
    secrets, or ``None`` when any value fails to resolve — the caller skips
    the server rather than writing a broken config.
    """
    headers: dict[str, str] = dict(server.get("headers") or {})
    for header, spec in (server.get("secret_headers") or {}).items():
        key_path, _, profile = spec.rpartition("@")
        if not key_path:  # no '@' — whole spec is the key path
            key_path, profile = spec, server.get("_profile", "")
        value = decrypt_key(profile, key_path, dotfiles_dir)
        if value is None:
            return None
        headers[header] = value
    return headers


def _server_has_secrets(server: dict[str, Any]) -> bool:
    """True if this server contributes secret material to the file's mode."""
    if server.get("secret_env"):
        return True
    if "url" in server and server.get("secret_headers"):
        return True
    if server.get("env"):  # any non-empty env mapping
        return True
    return bool("url" in server and server.get("headers"))


def _build_server(server: dict[str, Any], run_with_secrets: str) -> dict[str, Any]:
    """Render one server's config dict (command/url shape).

    Mirrors the ``mcp_updated_servers`` block in config_file.yml: URL servers
    emit ``type``/``url``/``transport``/``headers``; command servers emit
    ``command``/``args`` (rewritten through ``run-with-secrets.sh`` when
    ``secret_env`` is set), plus ``env`` with ``~`` expanded. ``description``,
    ``tags`` and ``auth`` are copied through when present.
    """
    config: dict[str, Any] = {}

    if "url" in server:
        if "type" in server:
            config["type"] = server["type"]
        config["url"] = server["url"]
        if "transport" in server:
            config["transport"] = server["transport"]
        if server.get("headers"):
            config["headers"] = server["headers"]
    else:
        command = os.path.expanduser(server["command"])
        args = [_expand_arg(a) for a in server.get("args", []) or []]
        secret_env = server.get("secret_env") or {}

        if server.get("auth"):
            # Auth handled by mcp-hub keychain — command used directly.
            config["command"] = command
            if args:
                config["args"] = args
        elif secret_env:
            # Secrets resolved at spawn time by the wrapper — rewrite command.
            profile = server.get("_profile", "")
            wrapped = ["-p", profile]
            wrapped += [f"{var}={path}" for var, path in secret_env.items()]
            wrapped.append("--")
            wrapped.append(command)
            wrapped += args
            config["command"] = run_with_secrets
            config["args"] = wrapped
        else:
            config["command"] = command
            if args:
                config["args"] = args

        if "env" in server and server["env"] is not None:
            config["env"] = {k: _expand_value(v) for k, v in server["env"].items()}

    if server.get("auth"):
        config["auth"] = server["auth"]
    if server.get("description"):
        config["description"] = server["description"]
    if server.get("tags"):
        config["tags"] = list(server["tags"])

    return config


def _expand_arg(arg: Any) -> Any:
    """Expand a leading ``~`` in string args; pass through non-strings."""
    if isinstance(arg, str) and arg.startswith("~"):
        return os.path.expanduser(arg)
    return arg


def _expand_value(value: Any) -> Any:
    """Expand a leading ``~`` in string env values; pass through non-strings."""
    if isinstance(value, str) and value.startswith("~"):
        return os.path.expanduser(value)
    return value
