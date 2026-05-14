#!/usr/bin/env python3
"""Apple Mail MCP server. Stdio transport."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from mcp.server import Server
from mcp.server.elicitation import AcceptedElicitation, elicit_with_validation
from mcp.server.stdio import stdio_server
from mcp.types import ClientCapabilities, ElicitationCapability, TextContent
from pydantic import BaseModel

from apple_mail_mcp.client import MailClient
from apple_mail_mcp.tools import get_outlook_tools, handle_outlook_tool

log_file = os.getenv(
    "APPLE_MAIL_LOG_FILE", os.path.expanduser("~/Library/Logs/apple-mail-mcp.log")
)
os.makedirs(os.path.dirname(log_file), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(log_file), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

app = Server("apple-mail-mcp")
_client: MailClient | None = None

_DRAFT_TOOLS = {"mail_create_draft", "mail_delete_draft", "mail_edit_draft"}


class _AccountChoice(BaseModel):
    account: str


@app.list_tools()
async def list_tools() -> list:
    return get_outlook_tools()


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    global _client
    if _client is None:
        _client = MailClient()
        logger.info("MailClient initialized with account=%s", _client.account)

    # Draft tools require a known account — no sensible multi-account scatter exists.
    if (
        name in _DRAFT_TOOLS
        and _client.account is None
        and not arguments.get("account")
    ):
        accounts = await _client.get_accounts()
        if len(accounts) > 1:
            session = app.request_context.session
            supports_elicitation = session.check_client_capability(
                ClientCapabilities(elicitation=ElicitationCapability())
            )
            if supports_elicitation:
                account_list = ", ".join(f"'{a}'" for a in accounts)
                elicit_result = await elicit_with_validation(
                    session=session,
                    message=(
                        f"Which Mail account should be used for this draft operation? "
                        f"Available accounts: {account_list}"
                    ),
                    schema=_AccountChoice,
                )
                if isinstance(elicit_result, AcceptedElicitation):
                    arguments = {**arguments, "account": elicit_result.data.account}
                    logger.info(
                        "Elicited account for %s: %s", name, elicit_result.data.account
                    )
                else:
                    return [TextContent(type="text", text="Draft operation cancelled.")]
            else:
                names = ", ".join(f"'{a}'" for a in accounts)
                return [
                    TextContent(
                        type="text",
                        text=f"Error: multiple Mail accounts exist ({names}). "
                        f"Pass 'account' to specify which one to use, "
                        f"or set APPLE_MAIL_ACCOUNT to pin a default.",
                    )
                ]

    return await handle_outlook_tool(name, arguments, _client)


async def _main() -> None:
    logger.info("Starting Apple Mail MCP server")
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


def run() -> None:
    asyncio.run(_main())
