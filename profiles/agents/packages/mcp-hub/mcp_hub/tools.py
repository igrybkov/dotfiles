"""MCP tool definitions and dispatch for mcp-hub."""

from __future__ import annotations

import json
import logging
from typing import Any

from mcp import types

from mcp_hub.config import ServerSpec
from mcp_hub.proxy import ProxyClient
from mcp_hub.search import search as do_search

logger = logging.getLogger(__name__)


def get_hub_tools() -> list[types.Tool]:
    """Return the mcp-hub tool definitions."""
    return [
        types.Tool(
            name="list_servers",
            description=(
                "List configured MCP servers with their descriptions and tags. "
                "Optionally filter by substring match on name/description/tags."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "filter": {
                        "type": "string",
                        "description": "Optional substring to filter on name, description, or tags.",
                    }
                },
            },
        ),
        types.Tool(
            name="get_server_tools",
            description=(
                "Get tools from a specific server. Lazily connects if not already "
                "connected. Use summary_only=true for cheap discovery (~100 tokens), "
                "then fetch full schemas for specific tools you plan to call."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "server": {"type": "string", "description": "Server name"},
                    "summary_only": {
                        "type": "boolean",
                        "description": "If true, return only tool names and descriptions (no input schemas).",
                        "default": False,
                    },
                    "tools": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "If set, return full schemas only for the named tools.",
                    },
                },
                "required": ["server"],
            },
        ),
        types.Tool(
            name="call_tool",
            description=(
                "Call a tool on a specific server. The server is spawned on first call. "
                "The tool must exist on the server — use get_server_tools to discover first."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "server": {"type": "string", "description": "Server name"},
                    "tool": {"type": "string", "description": "Tool name"},
                    "arguments": {
                        "type": "object",
                        "description": "Tool arguments as a JSON object.",
                        "additionalProperties": True,
                    },
                },
                "required": ["server", "tool"],
            },
        ),
        types.Tool(
            name="search",
            description=(
                "Search all configured servers and their known tools for a keyword. "
                "Returns ranked hits across server metadata and tool descriptions. "
                "Only searches servers whose tools have been loaded via get_server_tools "
                "or call_tool — server-level metadata is always searched."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Keywords (space-separated).",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default 20).",
                        "default": 20,
                    },
                },
                "required": ["query"],
            },
        ),
    ]


# --- dispatch ---


def _filter_match(spec: ServerSpec, needle: str) -> bool:
    needle = needle.lower()
    fields = [spec.name, spec.description or "", " ".join(spec.tags)]
    return any(needle in f.lower() for f in fields)


def _server_summary(spec: ServerSpec) -> dict[str, Any]:
    return {
        "name": spec.name,
        "description": spec.description,
        "tags": spec.tags,
        "transport": spec.transport,
    }


def _tool_summary(tool: types.Tool) -> dict[str, Any]:
    return {"name": tool.name, "description": tool.description or ""}


def _tool_full(tool: types.Tool) -> dict[str, Any]:
    return {
        "name": tool.name,
        "description": tool.description or "",
        "inputSchema": tool.inputSchema,
    }


def _text(payload: Any) -> list[types.TextContent]:
    if isinstance(payload, str):
        return [types.TextContent(type="text", text=payload)]
    return [
        types.TextContent(type="text", text=json.dumps(payload, indent=2, default=str))
    ]


async def handle_tool(
    name: str,
    arguments: dict[str, Any],
    servers: dict[str, ServerSpec],
    proxy: ProxyClient,
) -> list[types.TextContent]:
    if name == "list_servers":
        needle = (arguments or {}).get("filter")
        matches = [
            _server_summary(s)
            for s in servers.values()
            if not needle or _filter_match(s, needle)
        ]
        matches.sort(key=lambda x: x["name"])
        return _text({"count": len(matches), "servers": matches})

    if name == "get_server_tools":
        server = arguments["server"]
        if server not in servers:
            return _text({"error": f"unknown server: {server}"})
        summary_only = bool(arguments.get("summary_only", False))
        filter_names = arguments.get("tools")
        try:
            tools = await proxy.list_tools(server)
        except Exception as e:
            logger.exception("list_tools failed for %s", server)
            return _text({"error": f"list_tools failed: {e}"})
        if filter_names:
            wanted = set(filter_names)
            tools = [t for t in tools if t.name in wanted]
            return _text({"server": server, "tools": [_tool_full(t) for t in tools]})
        if summary_only:
            return _text({"server": server, "tools": [_tool_summary(t) for t in tools]})
        return _text({"server": server, "tools": [_tool_full(t) for t in tools]})

    if name == "call_tool":
        server = arguments["server"]
        tool = arguments["tool"]
        tool_args = arguments.get("arguments") or {}
        if server not in servers:
            return _text({"error": f"unknown server: {server}"})
        try:
            result = await proxy.call_tool(server, tool, tool_args)
        except Exception as e:
            logger.exception("call_tool failed for %s/%s", server, tool)
            return _text({"error": f"call_tool failed: {e}"})
        # Pass through the underlying tool result content (text blocks primarily).
        passthrough: list[types.TextContent] = []
        for block in result.content:
            if isinstance(block, types.TextContent):
                passthrough.append(block)
            else:
                passthrough.append(types.TextContent(type="text", text=str(block)))
        if result.isError:
            passthrough.insert(
                0, types.TextContent(type="text", text="[tool reported error]")
            )
        return passthrough

    if name == "search":
        query = arguments["query"]
        limit = int(arguments.get("limit", 20))
        # Use already-loaded tool cache — don't force eager connections
        hits = do_search(query, servers, proxy._tool_cache, limit=limit)
        return _text({"count": len(hits), "hits": [h.to_dict() for h in hits]})

    return _text({"error": f"unknown tool: {name}"})
