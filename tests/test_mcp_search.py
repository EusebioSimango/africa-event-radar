import asyncio
import json
from types import SimpleNamespace

import pytest
from mcp.types import CallToolResult

from eventradar.mcp_search import McpSearchBackend, SearchFailed, parse_tool_result

PAYLOAD = {"events_results": [{"title": "PyCon Example"}]}


def wire_result(text, *, is_error=False, structured=True):
    """A CallToolResult as the MCP server sends it over the wire."""
    data = {"content": [{"type": "text", "text": text}], "isError": is_error}
    if structured:
        data["structuredContent"] = {"result": text}
    return CallToolResult.model_validate(data)


def test_reads_json_from_structured_content():
    assert parse_tool_result(wire_result(json.dumps(PAYLOAD))) == PAYLOAD


def test_falls_back_to_the_text_block():
    assert parse_tool_result(wire_result(json.dumps(PAYLOAD), structured=False)) == PAYLOAD


def test_tool_errors_become_safe_messages():
    result = wire_result("Invalid API key: SECRET123", is_error=True)

    with pytest.raises(SearchFailed) as failure:
        parse_tool_result(result, secret="SECRET123")

    assert "SECRET123" not in str(failure.value)
    assert "Invalid API key" in str(failure.value)


def test_non_json_answers_are_reported():
    with pytest.raises(SearchFailed, match="Unexpected response"):
        parse_tool_result(SimpleNamespace(content=[], structured_content=None, is_error=False))


def test_connection_failures_never_show_the_key():
    async def run():
        async with McpSearchBackend("SECRET123", url="http://127.0.0.1:9/mcp", timeout=2) as mcp:
            await mcp.search({"engine": "google_light", "q": "python"})

    with pytest.raises(SearchFailed) as failure:
        asyncio.run(run())

    assert "SECRET123" not in str(failure.value)
    assert str(failure.value).startswith("Could not connect to SerpApi's MCP server")


def test_search_needs_an_open_session():
    with pytest.raises(SearchFailed, match="not open"):
        asyncio.run(McpSearchBackend("key").search({"engine": "google_light", "q": "python"}))
