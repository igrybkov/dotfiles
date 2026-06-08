#!/usr/bin/env python3
"""mcp-hub CLI — scriptable access to configured MCP servers.

Uses the same config loading as the server, so CONFIG_FILE points at the same
sources. Each subcommand spawns the needed child server on demand and prints
JSON to stdout.

Examples:
    mcp-hub list
    mcp-hub list --filter monitoring
    mcp-hub tools github --summary
    mcp-hub tools github --tool createIssue
    mcp-hub search "deploy"
    mcp-hub call github listIssues --args '{"repo": "my/repo"}'
    mcp-hub call github listIssues --args-file ./args.json
"""

from __future__ import annotations

import asyncio
import getpass
import json
import logging
import sys
from pathlib import Path
from typing import Any

import click
from dotenv import load_dotenv

from mcp_hub.config import load_servers
from mcp_hub.proxy import ProxyClient
from mcp_hub.search import search as do_search

load_dotenv()

logger = logging.getLogger("mcp-hub.cli")


def _print(payload: Any) -> None:
    click.echo(json.dumps(payload, indent=2, default=str))


def _die(msg: str, code: int = 1) -> None:
    click.echo(f"error: {msg}", err=True)
    sys.exit(code)


def _run_async(coro, *, server: str | None = None) -> Any:
    """Run a coroutine, converting unhandled exceptions to clean CLI errors.

    Re-raises SystemExit (from _die calls inside the coroutine) unchanged.
    Converts ExceptionGroups (anyio task-group failures) to a one-line error
    that points the user at the server's own stderr output.
    """
    try:
        return asyncio.run(coro)
    except SystemExit:
        raise
    except BaseException as exc:
        prefix = f"server '{server}': " if server else ""
        if hasattr(exc, "exceptions"):  # BaseExceptionGroup / ExceptionGroup
            _die(f"{prefix}failed to connect — see server output above")
        _die(f"{prefix}{exc}")


def _parse_args(args: str | None, args_file: str | None) -> dict[str, Any]:
    if args and args_file:
        _die("use either --args or --args-file, not both")
    if args_file:
        raw = Path(args_file).read_text()
    elif args:
        raw = args
    else:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        _die(f"invalid JSON: {e}")
    if not isinstance(parsed, dict):
        _die("arguments must be a JSON object")
    return parsed  # type: ignore[return-value]


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("-v", "--verbose", is_flag=True, help="Enable debug logging to stderr.")
def main(verbose: bool) -> None:
    """MCP Hub CLI — invoke configured MCP servers from the shell."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )


@main.command("list")
@click.option(
    "-f", "--filter", "needle", help="Substring filter on name/description/tags."
)
@click.option(
    "--names-only", is_flag=True, help="Print server names only, one per line."
)
def cmd_list(needle: str | None, names_only: bool) -> None:
    """List configured MCP servers."""
    servers = load_servers()
    rows = []
    for name in sorted(servers):
        s = servers[name]
        if needle:
            hay = " ".join([s.name, s.description or "", " ".join(s.tags)]).lower()
            if needle.lower() not in hay:
                continue
        rows.append(s)
    if names_only:
        for s in rows:
            click.echo(s.name)
        return
    _print(
        {
            "count": len(rows),
            "servers": [
                {
                    "name": s.name,
                    "transport": s.transport,
                    "description": s.description,
                    "tags": s.tags,
                }
                for s in rows
            ],
        }
    )


@main.command("tools")
@click.argument("server")
@click.option("--summary", is_flag=True, help="Return only names and descriptions.")
@click.option(
    "--tool",
    "tool_names",
    multiple=True,
    help="Return full schemas for named tools only.",
)
def cmd_tools(server: str, summary: bool, tool_names: tuple[str, ...]) -> None:
    """List tools for SERVER (spawns the server if needed)."""

    async def _run() -> dict[str, Any]:
        servers = load_servers()
        if server not in servers:
            _die(f"unknown server: {server}")
        async with ProxyClient(servers) as proxy:
            tools = await proxy.list_tools(server)
        if tool_names:
            wanted = set(tool_names)
            tools = [t for t in tools if t.name in wanted]
            return {
                "server": server,
                "tools": [
                    {
                        "name": t.name,
                        "description": t.description or "",
                        "inputSchema": t.inputSchema,
                    }
                    for t in tools
                ],
            }
        if summary:
            return {
                "server": server,
                "tools": [
                    {"name": t.name, "description": t.description or ""} for t in tools
                ],
            }
        return {
            "server": server,
            "tools": [
                {
                    "name": t.name,
                    "description": t.description or "",
                    "inputSchema": t.inputSchema,
                }
                for t in tools
            ],
        }

    _print(_run_async(_run(), server=server))


@main.command("call")
@click.argument("server")
@click.argument("tool")
@click.option("--args", "args_json", help="Tool arguments as JSON object.")
@click.option("--args-file", help="Read tool arguments from a JSON file.")
def cmd_call(
    server: str, tool: str, args_json: str | None, args_file: str | None
) -> None:
    """Call TOOL on SERVER with optional JSON ARGS."""
    args = _parse_args(args_json, args_file)

    async def _run() -> dict[str, Any]:
        servers = load_servers()
        if server not in servers:
            _die(f"unknown server: {server}")
        async with ProxyClient(servers) as proxy:
            result = await proxy.call_tool(server, tool, args)
        content = []
        for block in result.content:
            if getattr(block, "type", None) == "text":
                content.append({"type": "text", "text": block.text})
            else:
                content.append(
                    {"type": getattr(block, "type", "?"), "repr": str(block)}
                )
        return {
            "server": server,
            "tool": tool,
            "isError": bool(result.isError),
            "content": content,
        }

    _print(_run_async(_run(), server=server))


@main.command("search")
@click.argument("query")
@click.option("--limit", default=20, show_default=True, type=int)
@click.option(
    "--load",
    is_flag=True,
    help="Load tool schemas for ALL servers before searching (slow; spawns every server).",
)
def cmd_search(query: str, limit: int, load: bool) -> None:
    """Search server metadata (and optionally tools) for QUERY."""

    async def _run() -> dict[str, Any]:
        servers = load_servers()
        tools_by_server: dict[str, Any] = {}
        if load:
            async with ProxyClient(servers) as proxy:
                for name in servers:
                    try:
                        tools_by_server[name] = await proxy.list_tools(name)
                    except Exception as e:
                        logger.warning("skipping %s: %s", name, e)
        hits = do_search(query, servers, tools_by_server, limit=limit)
        return {"count": len(hits), "hits": [h.to_dict() for h in hits]}

    _print(asyncio.run(_run()))


@main.group("auth")
def cmd_auth() -> None:
    """Manage keychain secrets for MCP servers."""


@cmd_auth.command("status")
@click.option("--server", default=None, help="Show status for a specific server only.")
def cmd_auth_status(server: str | None) -> None:
    """Show auth status for all servers with auth schemas."""
    from mcp_hub.auth import resolve_auth, auth_status as get_auth_status

    servers = load_servers()
    rows = []
    check = {server: servers[server]} if server and server in servers else servers
    if server and server not in servers:
        _die(f"unknown server: {server}")
    for name in sorted(check):
        spec = check[name]
        auth = resolve_auth(name, spec.auth)
        if auth is None:
            continue
        status = get_auth_status(name, auth)
        for s in status["secrets"]:
            rows.append(
                (
                    name,
                    s["env_var"],
                    s["label"],
                    "✓" if s["stored"] else "✗",
                    status["status"],
                )
            )
    if not rows:
        click.echo("No servers with auth schemas found.")
        return
    click.echo(f"{'SERVER':<25} {'ENV_VAR':<40} {'LABEL':<35} {'STORED':<8} {'STATUS'}")
    click.echo("-" * 115)
    for name, env_var, label, stored, status_val in rows:
        click.echo(f"{name:<25} {env_var:<40} {label:<35} {stored:<8} {status_val}")


@cmd_auth.command("provision")
@click.argument("server", required=False)
@click.option(
    "--all",
    "all_servers",
    is_flag=True,
    help="Provision all servers with auth schemas.",
)
def cmd_auth_provision(server: str | None, all_servers: bool) -> None:
    """Collect and store secrets for SERVER (or all servers with --all)."""
    from mcp_hub.auth import resolve_auth, get_secret, set_secret

    servers = load_servers()
    targets: list[str] = []

    if all_servers:
        targets = sorted(
            name
            for name, spec in servers.items()
            if resolve_auth(name, spec.auth) is not None
        )
        if not targets:
            click.echo("No servers with auth schemas found.")
            return
    elif server:
        if server not in servers:
            _die(f"unknown server: {server}")
        auth = resolve_auth(server, servers[server].auth)
        if auth is None:
            _die(f"server '{server}' has no auth schema")
        targets = [server]
    else:
        click.echo("Specify a server name or use --all")
        raise SystemExit(1)

    for name in targets:
        spec = servers[name]
        auth = resolve_auth(name, spec.auth)
        if auth is None:
            continue
        present = [s for s in auth.secrets if s.state == "present"]
        if not present:
            continue
        click.echo(f"\n--- {name} ---")
        for secret in present:
            existing = get_secret(name, secret.env_var)
            if existing is not None:
                click.echo(
                    f"  {secret.label} ({secret.env_var}): already stored [skip]"
                )
                continue
            if secret.create_url:
                click.echo(f"  {secret.label} ({secret.env_var})")
                click.echo(f"    Create one at: {secret.create_url}")
            if secret.sensitive:
                value = getpass.getpass(f"  Enter {secret.label}: ")
            else:
                value = click.prompt(f"  Enter {secret.label}")
            if value:
                set_secret(name, secret.env_var, value)
                click.echo("  Stored ✓")
            else:
                click.echo("  Skipped (empty input)")

    click.echo(
        "\nDone. If mcp-hub is running, call the 'reload' tool or restart to pick up changes."
    )


@cmd_auth.command("rm")
@click.argument("server")
@click.argument("env_var", required=False)
def cmd_auth_rm(server: str, env_var: str | None) -> None:
    """Delete stored secret(s) for SERVER. If ENV_VAR given, remove only that secret."""
    from mcp_hub.auth import get_secret, delete_secret, delete_learned

    servers = load_servers()
    if server not in servers:
        _die(f"unknown server: {server}")

    if env_var:
        if get_secret(server, env_var) is None:
            click.echo(f"No secret stored for {server}/{env_var}")
        else:
            delete_secret(server, env_var)
            click.echo(f"Deleted {server}/{env_var} from keychain")
        delete_learned(server, env_var)
    else:
        from mcp_hub.auth import resolve_auth

        auth = resolve_auth(server, servers[server].auth)
        if auth is None:
            click.echo(f"No auth schema for server '{server}'")
            return
        removed = 0
        for s in auth.secrets:
            if get_secret(server, s.env_var) is not None:
                delete_secret(server, s.env_var)
                click.echo(f"Deleted {server}/{s.env_var}")
                removed += 1
        delete_learned(server)
        if removed == 0:
            click.echo(f"No secrets stored for '{server}'")


@cmd_auth.command("promote")
@click.argument("server")
def cmd_auth_promote(server: str) -> None:
    """Print YAML auth.secrets block for a learned schema (to paste into profile config)."""
    from mcp_hub.auth import load_learned

    learned = load_learned()
    if server not in learned:
        _die(f"no learned schema for server '{server}'")
    auth = learned[server]
    click.echo(f"# Add to your profile config under mcp_servers entry for '{server}':")
    click.echo("auth:")
    click.echo("  secrets:")
    for s in auth.secrets:
        click.echo(f"    - env_var: {s.env_var}")
        click.echo(f"      label: {s.label}")
        if s.create_url:
            click.echo(f"      create_url: {s.create_url}")
        if not s.sensitive:
            click.echo("      sensitive: false")


if __name__ == "__main__":
    main()
