#!/usr/bin/env python3
"""
Apple Mail client for the Outlook MCP server.

Drives Mail.app via JXA (JavaScript for Automation) over osascript. Works with
any IMAP/Exchange account added to Mail.app.

Set APPLE_MAIL_ACCOUNT to scope all operations to a single named account.
When unset, operations fan out across all accounts in parallel.

Surface:
  - list_accounts()
  - list_mailboxes()
  - list_messages(mailbox, limit, offset)
  - read_message(mailbox, message_id)
  - search_subject(mailbox, query, limit)
  - create_draft(to, subject, body, cc)
  - delete_draft(message_id)

Message IDs returned are the RFC Message-ID headers (stable across restarts),
not Mail.app's local integer ids.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess

logger = logging.getLogger(__name__)

ACCOUNT = os.getenv("APPLE_MAIL_ACCOUNT") or None
DEFAULT_TIMEOUT = 60


class AppleScriptError(RuntimeError):
    pass


def _run_jxa(script: str, args: dict, timeout: int) -> str:
    """Run a JXA script and pass `args` as a JSON string on argv.

    The script is wrapped with a run() entry point that parses argv[0] as JSON,
    calls `main(args)`, and prints the return value as JSON. This keeps argument
    passing safe regardless of user input.
    """
    wrapped = (
        script + "\nfunction run(argv) {\n"
        "  const args = JSON.parse(argv[0]);\n"
        "  const out = main(args);\n"
        "  return JSON.stringify(out);\n"
        "}\n"
    )
    proc = subprocess.run(
        ["osascript", "-l", "JavaScript", "-", json.dumps(args)],
        input=wrapped,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        raise AppleScriptError(
            proc.stderr.strip() or f"osascript exit {proc.returncode}"
        )
    return proc.stdout.strip()


# --- JXA scripts — each operates on exactly one named account ---

JXA_LIST_ACCOUNTS = r"""
function main(args) {
  const Mail = Application("Mail");
  return Mail.accounts().map(a => a.name());
}
"""

JXA_LIST_MAILBOXES = r"""
function main(args) {
  const Mail = Application("Mail");
  Mail.includeStandardAdditions = true;
  const acct = Mail.accounts.byName(args.account);
  const boxes = acct.mailboxes();
  const out = [];
  for (const mb of boxes) {
    let c = 0;
    try { c = mb.messages.length; } catch (e) { c = -1; }
    out.push({ name: mb.name(), count: c, account: args.account });
  }
  return out;
}
"""

JXA_LIST_MESSAGES = r"""
function main(args) {
  const Mail = Application("Mail");
  const acct = Mail.accounts.byName(args.account);
  const mb = acct.mailboxes.byName(args.mailbox);
  const start = Math.max(0, args.offset);
  const end = start + args.limit;
  const out = [];
  for (let i = start; i < end; i++) {
    try {
      const m = mb.messages[i];
      // Probe a cheap property first so we detect the end-of-range without
      // forcing a full collection-length evaluation up front.
      const mid = m.messageId();
      out.push({
        index: i,
        message_id: mid,
        subject: m.subject(),
        from: m.sender(),
        date: m.dateReceived().toISOString(),
        read: m.readStatus(),
      });
    } catch (e) { break; }
  }
  return { messages: out };
}
"""

JXA_READ_MESSAGE = r"""
function main(args) {
  const Mail = Application("Mail");
  const acct = Mail.accounts.byName(args.account);
  const mb = acct.mailboxes.byName(args.mailbox);
  let m;
  if (typeof args.index === "number") {
    m = mb.messages[args.index];
  } else if (args.message_id) {
    const hits = mb.messages.whose({ messageId: args.message_id })();
    if (!hits || hits.length === 0) return { error: "message not found" };
    m = hits[0];
  } else {
    return { error: "must provide index or message_id" };
  }
  const tos = [];
  try { for (const r of m.toRecipients()) tos.push(r.address()); } catch (e) {}
  const ccs = [];
  try { for (const r of m.ccRecipients()) ccs.push(r.address()); } catch (e) {}
  let body = "";
  try { body = m.content(); } catch (e) { body = ""; }
  return {
    message_id: m.messageId(),
    subject: m.subject(),
    from: m.sender(),
    to: tos,
    cc: ccs,
    date: m.dateReceived().toISOString(),
    body: body,
  };
}
"""

JXA_SEARCH_SUBJECT = r"""
function main(args) {
  const Mail = Application("Mail");
  const acct = Mail.accounts.byName(args.account);
  const mb = acct.mailboxes.byName(args.mailbox);
  const hits = mb.messages.whose({ subject: { _contains: args.query } })();
  const total = hits.length;
  const cap = Math.min(total, args.limit);
  const out = [];
  for (let i = 0; i < cap; i++) {
    try {
      const m = hits[i];
      out.push({
        message_id: m.messageId(),
        subject: m.subject(),
        from: m.sender(),
        date: m.dateReceived().toISOString(),
      });
    } catch (e) {}
  }
  return { total: total, messages: out };
}
"""

JXA_CREATE_DRAFT = r"""
function main(args) {
  const Mail = Application("Mail");
  const d = Mail.OutgoingMessage({
    subject: args.subject,
    content: args.body,
    visible: false,
  });
  Mail.outgoingMessages.push(d);
  for (const addr of args.to) {
    d.toRecipients.push(Mail.Recipient({ address: addr }));
  }
  for (const addr of args.cc || []) {
    d.ccRecipients.push(Mail.Recipient({ address: addr }));
  }
  d.save();
  delay(1);
  try {
    const acct = Mail.accounts.byName(args.account);
    const drafts = acct.mailboxes.byName("Drafts");
    const cands = drafts.messages.whose({ subject: args.subject })();
    if (cands && cands.length > 0) {
      const m = cands[0];
      return { message_id: m.messageId(), subject: m.subject(), mailbox: "Drafts" };
    }
  } catch(e) {}
  return { message_id: "", warning: "created but not found in Drafts yet" };
}
"""

JXA_DELETE_DRAFT = r"""
function main(args) {
  const Mail = Application("Mail");
  const acct = Mail.accounts.byName(args.account);
  let n = 0;
  try {
    const drafts = acct.mailboxes.byName("Drafts");
    const hits = drafts.messages.whose({ messageId: args.message_id })();
    if (hits) {
      const msgs = [];
      for (const m of hits) msgs.push(m);
      for (let i = msgs.length - 1; i >= 0; i--) {
        try { Mail.delete(msgs[i]); n++; } catch (e) {}
      }
    }
  } catch(e) {}
  return { deleted: n };
}
"""


class MailClient:
    def __init__(self, account: str | None = None) -> None:
        self.account = account if account is not None else ACCOUNT

    async def _run(
        self, script: str, args: dict, timeout: int = DEFAULT_TIMEOUT
    ) -> object:
        out = await asyncio.to_thread(_run_jxa, script, args, timeout)
        return json.loads(out) if out else None

    async def get_accounts(self) -> list[str]:
        result = await self._run(JXA_LIST_ACCOUNTS, {})
        return result or []

    async def list_mailboxes(self, account: str | None = None) -> list[dict]:
        resolved = account or self.account
        if resolved:
            return await self._run(JXA_LIST_MAILBOXES, {"account": resolved})
        accounts = await self.get_accounts()
        results = await asyncio.gather(
            *[self._run(JXA_LIST_MAILBOXES, {"account": a}) for a in accounts],
            return_exceptions=True,
        )
        return [mb for r in results if not isinstance(r, Exception) and r for mb in r]

    async def list_messages(
        self, mailbox: str, limit: int = 20, offset: int = 0, account: str | None = None
    ) -> dict:
        resolved = account or self.account
        args = {"mailbox": mailbox, "limit": limit, "offset": offset}
        if resolved:
            return await self._run(JXA_LIST_MESSAGES, {"account": resolved, **args})
        accounts = await self.get_accounts()
        results = await asyncio.gather(
            *[self._run(JXA_LIST_MESSAGES, {"account": a, **args}) for a in accounts],
            return_exceptions=True,
        )
        for r in results:
            if not isinstance(r, Exception) and r is not None:
                return r
        return {"messages": []}

    async def read_message(
        self,
        mailbox: str,
        index: int | None = None,
        message_id: str | None = None,
        account: str | None = None,
    ) -> dict:
        resolved = account or self.account
        args: dict = {"mailbox": mailbox}
        if index is not None:
            args["index"] = int(index)
        if message_id is not None:
            args["message_id"] = message_id
        if resolved:
            return await self._run(
                JXA_READ_MESSAGE, {"account": resolved, **args}, timeout=120
            )
        accounts = await self.get_accounts()
        results = await asyncio.gather(
            *[
                self._run(JXA_READ_MESSAGE, {"account": a, **args}, timeout=120)
                for a in accounts
            ],
            return_exceptions=True,
        )
        for r in results:
            if not isinstance(r, Exception) and r is not None and "error" not in r:
                return r
        return {"error": "message not found"}

    async def search_subject(
        self, mailbox: str, query: str, limit: int = 20, account: str | None = None
    ) -> dict:
        resolved = account or self.account
        args = {"mailbox": mailbox, "query": query, "limit": limit}
        if resolved:
            return await self._run(
                JXA_SEARCH_SUBJECT, {"account": resolved, **args}, timeout=180
            )
        accounts = await self.get_accounts()
        results = await asyncio.gather(
            *[
                self._run(JXA_SEARCH_SUBJECT, {"account": a, **args}, timeout=180)
                for a in accounts
            ],
            return_exceptions=True,
        )
        for r in results:
            if not isinstance(r, Exception) and r is not None:
                return r
        return {"total": 0, "messages": []}

    async def create_draft(
        self,
        to: str | list[str],
        subject: str,
        body: str,
        cc: str | list[str] | None = None,
        account: str | None = None,
    ) -> dict:
        def _split(v):
            if v is None:
                return []
            if isinstance(v, list):
                return [a.strip() for a in v if a and a.strip()]
            return [a.strip() for a in str(v).split(",") if a.strip()]

        resolved_account = account or self.account
        if not resolved_account:
            raise ValueError(
                "account is required for create_draft when multiple Mail accounts exist"
            )
        args = {"to": _split(to), "cc": _split(cc), "subject": subject, "body": body}
        return await self._run(
            JXA_CREATE_DRAFT, {"account": resolved_account, **args}
        ) or {"message_id": "", "warning": "created but not found in Drafts yet"}

    async def delete_draft(self, message_id: str, account: str | None = None) -> dict:
        resolved_account = account or self.account
        if not resolved_account:
            raise ValueError(
                "account is required for delete_draft when multiple Mail accounts exist"
            )
        result = await self._run(
            JXA_DELETE_DRAFT, {"account": resolved_account, "message_id": message_id}
        )
        return result or {"deleted": 0}
