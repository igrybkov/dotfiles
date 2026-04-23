#!/usr/bin/env python3
"""MCP Hub server entry point.

Loads server configs, builds a dynamic instructions string that lists the
configured servers (so the LLM is aware of available capabilities without
having to call a discovery tool), and serves the hub's four tools over stdio.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from mcp_hub.config import load_servers
from mcp_hub.instructions import build_instructions
from mcp_hub.proxy import ProxyClient
from mcp_hub.tools import get_hub_tools, handle_tool

load_dotenv()

_log_file = os.getenv(
    "MCP_HUB_LOG_FILE", os.path.expanduser("~/Library/Logs/mcp-hub.log")
)
os.makedirs(os.path.dirname(_log_file), exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(_log_file), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


async def _main() -> None:
    servers = load_servers()
    logger.info("Loaded %d server(s)", len(servers))
    instructions = build_instructions(servers)

    app: Server = Server("mcp-hub", instructions=instructions)

    @app.list_tools()
    async def list_tools() -> list[Tool]:
        return get_hub_tools()

    async with ProxyClient(servers) as proxy:

        @app.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
            return await handle_tool(name, arguments or {}, servers, proxy)

        logger.info("Starting mcp-hub MCP server")
        async with stdio_server() as (read_stream, write_stream):
            await app.run(
                read_stream, write_stream, app.create_initialization_options()
            )


def run() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    run()
