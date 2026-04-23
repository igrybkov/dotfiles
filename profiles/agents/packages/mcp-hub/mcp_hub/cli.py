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
def cmd_list(needle: str | None) -> None:
    """List configured MCP servers."""
    servers = load_servers()
    rows = []
    for name in sorted(servers):
        s = servers[name]
        if needle:
            hay = " ".join([s.name, s.description or "", " ".join(s.tags)]).lower()
            if needle.lower() not in hay:
                continue
        rows.append(
            {
                "name": s.name,
                "transport": s.transport,
                "description": s.description,
                "tags": s.tags,
            }
        )
    _print({"count": len(rows), "servers": rows})


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

    _print(asyncio.run(_run()))


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

    _print(asyncio.run(_run()))


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


if __name__ == "__main__":
    main()
