"""Build the dynamic MCP server `instructions` string so the LLM sees the
catalog of proxied servers without needing any discovery call.
"""

from __future__ import annotations

from mcp_hub.config import ServerSpec


def build_instructions(servers: dict[str, ServerSpec]) -> str:
    """Describe the hub so the LLM knows capabilities are available."""
    if not servers:
        return (
            "MCP Hub — aggregator for child MCP servers. No servers are currently "
            "configured. Set CONFIG_FILE to point at a JSON or YAML config."
        )

    lines = [
        "MCP Hub — proxies lazy-loaded MCP servers. Child servers are spawned on "
        "first use, so calling a tool is the only way to trigger a connection.",
        "",
        f"Configured servers ({len(servers)}):",
    ]
    for name in sorted(servers):
        lines.append(f"  • {name}")

    lines.extend(
        [
            "",
            "Workflow:",
            "  1. `list_servers(filter?)` — browse or filter the catalog",
            "  2. `search(query)` — find tools by keyword across all servers",
            "  3. `get_server_tools(server, summary_only=true)` — cheap tool listing",
            "  4. `get_server_tools(server, tools=[names])` — full schemas for specific tools",
            "  5. `call_tool(server, tool, arguments)` — invoke a tool",
            "",
            "For shell scripting use the `mcp-hub` CLI:",
            "  mcp-hub list [--filter X]",
            "  mcp-hub tools <server> [--summary]",
            "  mcp-hub call <server> <tool> --args '<json>'",
            "  mcp-hub search <query>",
        ]
    )
    return "\n".join(lines)
