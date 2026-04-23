"""Lazy proxy client — maintains ClientSession per child server.

Connections are opened on first use and cached for the lifetime of the ProxyClient.
Use as an async context manager so the underlying AsyncExitStack tears everything
down cleanly.
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client

from mcp_hub.config import ServerSpec

logger = logging.getLogger(__name__)


class ProxyClient:
    """Manages lazy-connected ClientSessions for a set of configured servers."""

    def __init__(self, servers: dict[str, ServerSpec]) -> None:
        self._servers = servers
        self._sessions: dict[str, ClientSession] = {}
        self._tool_cache: dict[str, list[types.Tool]] = {}
        self._stack = AsyncExitStack()
        self._locks: dict[str, asyncio.Lock] = {}

    # --- lifecycle ---

    async def __aenter__(self) -> ProxyClient:
        await self._stack.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self._stack.__aexit__(exc_type, exc, tb)

    # --- connection management ---

    def _lock_for(self, name: str) -> asyncio.Lock:
        lock = self._locks.get(name)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[name] = lock
        return lock

    async def _connect(self, spec: ServerSpec) -> ClientSession:
        if spec.transport == "stdio":
            if not spec.command:
                raise ValueError(f"server {spec.name!r} missing 'command'")
            params = StdioServerParameters(
                command=spec.command,
                args=list(spec.args),
                env={**os.environ, **spec.env} if spec.env else None,
            )
            read, write = await self._stack.enter_async_context(stdio_client(params))
        elif spec.transport == "streamable-http":
            if not spec.url:
                raise ValueError(f"server {spec.name!r} missing 'url'")
            read, write, _ = await self._stack.enter_async_context(
                streamablehttp_client(spec.url, headers=spec.headers or None)
            )
        elif spec.transport == "sse":
            if not spec.url:
                raise ValueError(f"server {spec.name!r} missing 'url'")
            read, write = await self._stack.enter_async_context(
                sse_client(spec.url, headers=spec.headers or None)
            )
        else:
            raise ValueError(f"unsupported transport: {spec.transport}")

        session = await self._stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        return session

    async def session(self, name: str) -> ClientSession:
        """Return a live session for `name`, connecting on first call."""
        spec = self._servers.get(name)
        if spec is None:
            raise KeyError(f"unknown server: {name!r}")
        async with self._lock_for(name):
            cached = self._sessions.get(name)
            if cached is not None:
                return cached
            logger.info("Connecting to server %r (%s)", name, spec.transport)
            session = await self._connect(spec)
            self._sessions[name] = session
            return session

    # --- public API ---

    async def list_tools(self, name: str) -> list[types.Tool]:
        cached = self._tool_cache.get(name)
        if cached is not None:
            return cached
        session = await self.session(name)
        result = await session.list_tools()
        self._tool_cache[name] = list(result.tools)
        return self._tool_cache[name]

    async def call_tool(
        self, name: str, tool: str, arguments: dict[str, Any]
    ) -> types.CallToolResult:
        session = await self.session(name)
        return await session.call_tool(tool, arguments=arguments)
