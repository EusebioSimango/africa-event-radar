"""Call the ``search`` tool on SerpApi's hosted MCP server and return the JSON results."""

from __future__ import annotations

import contextlib
import json
from contextlib import AsyncExitStack
from typing import Any, Protocol

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

MCP_URL = "https://mcp.serpapi.com/mcp"
SEARCH_TOOL = "search"

# SerpApi reports an empty result page through the "error" field with this wording.
NO_RESULTS_MARKER = "hasn't returned any results"


class SearchFailed(RuntimeError):
    """A search could not run; the message is safe to show and never contains the API key."""


class SearchBackend(Protocol):
    async def search(self, params: dict[str, Any]) -> dict[str, Any]: ...


class McpSearchBackend:
    """One MCP session to mcp.serpapi.com, shared by every search in a run.

    Use it as ``async with``: the session must be opened and closed in the same task, because
    the MCP SDK runs on anyio task groups. Connecting costs no credits.

    The key travels in the ``Authorization`` header: SerpApi notes that a key in the URL path
    can end up in request logs.
    """

    def __init__(self, api_key: str, *, url: str = MCP_URL, timeout: float = 60.0) -> None:
        self._api_key = api_key
        self._url = url
        self._timeout = timeout
        self._stack = AsyncExitStack()
        self._client: Client | None = None

    async def __aenter__(self) -> McpSearchBackend:
        try:
            http = await self._stack.enter_async_context(
                httpx2.AsyncClient(
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    timeout=httpx2.Timeout(30.0, read=self._timeout),
                )
            )
            transport = streamable_http_client(self._url, http_client=http)
            self._client = await self._stack.enter_async_context(Client(transport))
        except Exception as exc:
            await self._close()
            raise SearchFailed(
                f"Could not connect to SerpApi's MCP server ({type(exc).__name__})."
            ) from exc
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self._close()

    async def search(self, params: dict[str, Any]) -> dict[str, Any]:
        if self._client is None:
            raise SearchFailed("The MCP session is not open; use `async with McpSearchBackend`.")
        try:
            result = await self._client.call_tool(
                SEARCH_TOOL, {"params": params, "mode": "compact"}
            )
        except Exception as exc:
            raise SearchFailed(f"SerpApi MCP request failed ({type(exc).__name__}).") from exc
        return parse_tool_result(result, secret=self._api_key)

    async def _close(self) -> None:
        # The results are already in hand; a failure while hanging up should not lose them.
        with contextlib.suppress(Exception):
            await self._stack.aclose()
        self._client = None


def parse_tool_result(result: Any, *, secret: str = "") -> dict[str, Any]:
    """Read the JSON text of a ``CallToolResult``, from ``structured_content`` or a text block."""
    text = _result_text(result)
    if getattr(result, "is_error", False):
        raise SearchFailed(_without_secret(text or "SerpApi MCP search failed.", secret))
    try:
        payload = json.loads(text)
    except ValueError:
        raise SearchFailed("Unexpected response from the SerpApi MCP server.") from None
    if not isinstance(payload, dict):
        raise SearchFailed("Unexpected response from the SerpApi MCP server.")
    return payload


def _result_text(result: Any) -> str:
    structured = getattr(result, "structured_content", None)
    if isinstance(structured, dict) and isinstance(structured.get("result"), str):
        return structured["result"]
    for block in getattr(result, "content", None) or []:
        text = getattr(block, "text", None)
        if isinstance(text, str):
            return text
    return ""


def _without_secret(message: str, secret: str) -> str:
    return message.replace(secret, "***") if secret else message
