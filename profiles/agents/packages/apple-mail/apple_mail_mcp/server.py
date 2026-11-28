#!/usr/bin/env python3
"""Apple Mail MCP server. Stdio transport."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from mcp.server import Server, ServerRequestContext
from mcp.server.elicitation import (
    AcceptedElicitation,
    elicit_with_validation,
    render_elicitation_schema,
)
from mcp.server.stdio import stdio_server
from mcp.shared.exceptions import NoBackChannelError
from mcp.types import (
    CallToolRequestParams,
    CallToolResult,
    ClientCapabilities,
    ElicitationCapability,
    ElicitRequest,
    ElicitRequestFormParams,
    ElicitResult,
    InputRequiredResult,
    ListToolsResult,
    PaginatedRequestParams,
    TextContent,
)
from pydantic import BaseModel, ValidationError

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

_client: MailClient | None = None

_DRAFT_TOOLS = {"mail_create_draft", "mail_delete_draft", "mail_edit_draft"}


_ACCOUNT_INPUT_KEY = "account"


class _AccountChoice(BaseModel):
    account: str


def _text(text: str, *, is_error: bool = False) -> CallToolResult:
    return CallToolResult(
        content=[TextContent(type="text", text=text)], is_error=is_error
    )


def _multiple_accounts_error(accounts: list[str]) -> CallToolResult:
    names = ", ".join(f"'{a}'" for a in accounts)
    return _text(
        f"Error: multiple Mail accounts exist ({names}). "
        f"Pass 'account' to specify which one to use, "
        f"or set APPLE_MAIL_ACCOUNT to pin a default.",
        is_error=True,
    )


async def list_tools(
    ctx: ServerRequestContext, params: PaginatedRequestParams | None
) -> ListToolsResult:
    return ListToolsResult(tools=get_outlook_tools())


def _account_prompt(accounts: list[str]) -> str:
    account_list = ", ".join(f"'{a}'" for a in accounts)
    return (
        f"Which Mail account should be used for this draft operation? "
        f"Available accounts: {account_list}"
    )


def _account_from_input_responses(params: CallToolRequestParams) -> str | None | bool:
    """Read the account answer from a 2026-07-28 retry.

    Returns the account name, False if the user declined or cancelled,
    or None if this call carries no answer.
    """
    response = (params.input_responses or {}).get(_ACCOUNT_INPUT_KEY)
    if not isinstance(response, ElicitResult):
        return None
    if response.action != "accept" or response.content is None:
        return False
    try:
        return _AccountChoice.model_validate(response.content).account
    except ValidationError:
        logger.warning("Ignoring malformed account answer: %r", response.content)
        return False


async def _elicit_account(
    ctx: ServerRequestContext, accounts: list[str]
) -> str | bool | InputRequiredResult:
    """Ask the user which account to use.

    Handshake-era clients get a server-initiated elicitation request.
    On 2026-07-28 there is no back-channel, so return InputRequiredResult;
    the client asks the user and retries the call with input_responses.
    """
    try:
        result = await elicit_with_validation(
            session=ctx.session,
            message=_account_prompt(accounts),
            schema=_AccountChoice,
            related_request_id=ctx.request_id,
        )
    except NoBackChannelError:
        return InputRequiredResult(
            input_requests={
                _ACCOUNT_INPUT_KEY: ElicitRequest(
                    params=ElicitRequestFormParams(
                        message=_account_prompt(accounts),
                        requested_schema=render_elicitation_schema(_AccountChoice),
                    )
                )
            }
        )
    except ValueError:
        # Client accepted but sent content that doesn't match the schema.
        logger.warning("Ignoring malformed account answer", exc_info=True)
        return False
    if isinstance(result, AcceptedElicitation):
        return result.data.account
    return False


async def call_tool(
    ctx: ServerRequestContext, params: CallToolRequestParams
) -> CallToolResult | InputRequiredResult:
    global _client
    if _client is None:
        _client = MailClient()
        logger.info("MailClient initialized with account=%s", _client.account)

    name = params.name
    arguments: dict[str, Any] = dict(params.arguments or {})

    # Draft tools require a known account — no sensible multi-account scatter exists.
    if (
        name in _DRAFT_TOOLS
        and _client.account is None
        and not arguments.get("account")
    ):
        answer = _account_from_input_responses(params)
        if answer is None:
            accounts = await _client.get_accounts()
            if len(accounts) > 1:
                supports_elicitation = ctx.session.check_client_capability(
                    ClientCapabilities(elicitation=ElicitationCapability())
                )
                if not supports_elicitation:
                    return _multiple_accounts_error(accounts)
                answer = await _elicit_account(ctx, accounts)
                if isinstance(answer, InputRequiredResult):
                    return answer
        if answer is False:
            return _text("Draft operation cancelled.")
        if answer:
            arguments["account"] = answer
            logger.info("Elicited account for %s: %s", name, answer)

    return await handle_outlook_tool(name, arguments, _client)


app = Server("apple-mail-mcp", on_list_tools=list_tools, on_call_tool=call_tool)


async def _main() -> None:
    logger.info("Starting Apple Mail MCP server")
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


def run() -> None:
    asyncio.run(_main())
