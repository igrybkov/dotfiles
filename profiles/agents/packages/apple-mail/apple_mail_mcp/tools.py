#!/usr/bin/env python3
"""Tool definitions for the Apple Mail MCP server."""

from __future__ import annotations

import json
import logging
from typing import Any

from mcp.types import TextContent, Tool

from apple_mail_mcp.client import MailClient

logger = logging.getLogger(__name__)

_ACCOUNT_PROP = {
    "account": {
        "type": "string",
        "description": (
            "Mail account name to scope this call to. "
            "Use mail_get_accounts to list available names. "
            "Optional when APPLE_MAIL_ACCOUNT is set or only one account exists."
        ),
    }
}


def get_outlook_tools() -> list[Tool]:
    return [
        Tool(
            name="mail_get_accounts",
            description=(
                "List all Mail.app account names on this machine. "
                "Only needed before write operations (mail_create_draft, mail_delete_draft) "
                "when you need to specify an account. Read and search tools work across "
                "all accounts by default without calling this first."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="mail_list_mailboxes",
            description=(
                "List all mailboxes (folders) for a Mail account with their message counts. "
                "Use this to discover canonical mailbox names before calling other tools — "
                "names may include emoji/Unicode. "
                "When no account is given, returns mailboxes across all accounts."
            ),
            inputSchema={
                "type": "object",
                "properties": {**_ACCOUNT_PROP},
            },
        ),
        Tool(
            name="mail_list_messages",
            description=(
                "List messages in a mailbox, most-recent first. Returns a positional "
                "`index` per message that can be passed to mail_read_message for "
                "fast fetch. Also returns stable `message_id` (RFC Message-ID header). "
                "When no account is given, searches across all accounts."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "mailbox": {
                        "type": "string",
                        "description": "Mailbox name (use mail_list_mailboxes to discover).",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max messages to return (default 20).",
                        "default": 20,
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Skip this many messages from the start (default 0).",
                        "default": 0,
                    },
                    **_ACCOUNT_PROP,
                },
                "required": ["mailbox"],
            },
        ),
        Tool(
            name="mail_read_message",
            description=(
                "Fetch full message content (body, to/cc, date). Prefer `index` (fast) "
                "returned by a recent mail_list_messages or mail_search_subject. "
                "`message_id` is a slow fallback that scans the mailbox. "
                "When no account is given, searches across all accounts."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "mailbox": {
                        "type": "string",
                        "description": "Mailbox containing the message.",
                    },
                    "index": {
                        "type": "integer",
                        "description": "Positional index from a recent list/search (preferred).",
                    },
                    "message_id": {
                        "type": "string",
                        "description": "Stable RFC Message-ID (slow fallback).",
                    },
                    **_ACCOUNT_PROP,
                },
                "required": ["mailbox"],
            },
        ),
        Tool(
            name="mail_search_subject",
            description=(
                "Search a mailbox for messages whose subject contains a substring "
                "(case-insensitive). Subject-only — body search is not supported here "
                "because scanning bodies across large folders is prohibitively slow. "
                "When no account is given, searches across all accounts."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "mailbox": {"type": "string", "description": "Mailbox to search."},
                    "query": {
                        "type": "string",
                        "description": "Substring to match in the subject.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max hits to return (default 20).",
                        "default": 20,
                    },
                    **_ACCOUNT_PROP,
                },
                "required": ["mailbox", "query"],
            },
        ),
        Tool(
            name="mail_create_draft",
            description=(
                "Create a draft email in the Drafts folder. Does NOT send. Returns the "
                "resulting draft's stable message_id which can be passed to "
                "mail_delete_draft to discard. "
                "When multiple Mail accounts exist, `account` is required unless the "
                "client supports elicitation (in which case you will be prompted). "
                "Use mail_get_accounts to discover available account names."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "Recipient addresses, comma-separated.",
                    },
                    "subject": {"type": "string", "description": "Email subject."},
                    "body": {"type": "string", "description": "Plain-text body."},
                    "cc": {
                        "type": "string",
                        "description": "CC addresses, comma-separated (optional).",
                    },
                    **_ACCOUNT_PROP,
                },
                "required": ["to", "subject", "body"],
            },
        ),
        Tool(
            name="mail_delete_draft",
            description=(
                "Delete a draft from the Drafts folder by its RFC Message-ID. "
                "When multiple Mail accounts exist, `account` is required unless the "
                "client supports elicitation. "
                "Use mail_get_accounts to discover available account names."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "Message-ID returned by mail_create_draft.",
                    },
                    **_ACCOUNT_PROP,
                },
                "required": ["message_id"],
            },
        ),
        Tool(
            name="mail_edit_draft",
            description=(
                "Edit an existing draft in the Drafts folder by its RFC Message-ID. "
                "Only the fields you supply are changed; omitted fields keep their current values. "
                "Returns the new message_id (the old one is invalidated). "
                "When multiple Mail accounts exist, `account` is required unless the "
                "client supports elicitation. "
                "Use mail_get_accounts to discover available account names."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "Message-ID of the draft to edit (from mail_create_draft).",
                    },
                    "to": {
                        "type": "string",
                        "description": "New recipient addresses, comma-separated (optional).",
                    },
                    "subject": {
                        "type": "string",
                        "description": "New subject line (optional).",
                    },
                    "body": {
                        "type": "string",
                        "description": "New plain-text body (optional).",
                    },
                    "cc": {
                        "type": "string",
                        "description": "New CC addresses, comma-separated (optional).",
                    },
                    **_ACCOUNT_PROP,
                },
                "required": ["message_id"],
            },
        ),
    ]


async def handle_outlook_tool(
    name: str, arguments: dict[str, Any], client: MailClient
) -> list[TextContent]:
    try:
        account = arguments.get("account")
        if name == "mail_get_accounts":
            result = await client.get_accounts()
        elif name == "mail_list_mailboxes":
            result = await client.list_mailboxes(account=account)
        elif name == "mail_list_messages":
            result = await client.list_messages(
                mailbox=arguments["mailbox"],
                limit=arguments.get("limit", 20),
                offset=arguments.get("offset", 0),
                account=account,
            )
        elif name == "mail_read_message":
            result = await client.read_message(
                mailbox=arguments["mailbox"],
                index=arguments.get("index"),
                message_id=arguments.get("message_id"),
                account=account,
            )
        elif name == "mail_search_subject":
            result = await client.search_subject(
                mailbox=arguments["mailbox"],
                query=arguments["query"],
                limit=arguments.get("limit", 20),
                account=account,
            )
        elif name == "mail_create_draft":
            result = await client.create_draft(
                to=arguments["to"],
                subject=arguments["subject"],
                body=arguments["body"],
                cc=arguments.get("cc"),
                account=account,
            )
        elif name == "mail_delete_draft":
            result = await client.delete_draft(
                message_id=arguments["message_id"],
                account=account,
            )
        elif name == "mail_edit_draft":
            result = await client.edit_draft(
                message_id=arguments["message_id"],
                to=arguments.get("to"),
                subject=arguments.get("subject"),
                body=arguments.get("body"),
                cc=arguments.get("cc"),
                account=account,
            )
        else:
            raise ValueError(f"Unknown tool: {name}")
        return [
            TextContent(type="text", text=json.dumps(result, indent=2, default=str))
        ]
    except Exception as e:
        logger.exception("Error in tool %s", name)
        return [TextContent(type="text", text=f"Error: {e}")]
