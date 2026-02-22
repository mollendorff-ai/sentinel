"""Tests for Ref MCP client."""

import logging
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sentinel.tools.ref_mcp import (
    REF_TOOL_NAMES,
    _log_discovered,
    get_ref_tools,
    ref_session,
)

EXPECTED_TOOL_COUNT = 6


def _fake_tools() -> list[MagicMock]:
    """Build a list of mock tools matching all Ref tool names."""
    tools = []
    for name in REF_TOOL_NAMES:
        tool = MagicMock()
        tool.name = name
        tools.append(tool)
    return tools


# ---------------------------------------------------------------------------
# Unit tests (no external binaries)
# ---------------------------------------------------------------------------


async def test_get_ref_tools_mocked() -> None:
    """Verify get_ref_tools() connects and returns tools (mocked MCP)."""
    fake = _fake_tools()
    mock_client = MagicMock()
    mock_client.get_tools = AsyncMock(return_value=fake)

    with patch("sentinel.tools.ref_mcp.MultiServerMCPClient", return_value=mock_client):
        tools = await get_ref_tools()

    assert {t.name for t in tools} == REF_TOOL_NAMES
    assert len(tools) == EXPECTED_TOOL_COUNT


async def test_ref_session_mocked() -> None:
    """Verify ref_session() yields tools via async context manager (mocked MCP)."""
    fake = _fake_tools()

    @asynccontextmanager
    async def _fake_session(_name: str):  # noqa: ANN202
        yield MagicMock()

    mock_client = MagicMock()
    mock_client.session = _fake_session

    with (
        patch("sentinel.tools.ref_mcp.MultiServerMCPClient", return_value=mock_client),
        patch("sentinel.tools.ref_mcp.load_mcp_tools", AsyncMock(return_value=fake)),
    ):
        async with ref_session() as tools:
            assert {t.name for t in tools} == REF_TOOL_NAMES


def test_log_discovered_warns_on_missing_tools(caplog: pytest.LogCaptureFixture) -> None:
    """Verify _log_discovered warns when expected tools are missing."""
    partial_tool = MagicMock()
    partial_tool.name = "ref_fetch"

    with caplog.at_level(logging.WARNING, logger="sentinel.tools.ref_mcp"):
        _log_discovered([partial_tool])

    assert "Expected Ref tools not found" in caplog.text


# ---------------------------------------------------------------------------
# Integration tests (require real `ref` binary)
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_get_ref_tools_discovers_all() -> None:
    """Verify get_ref_tools() returns all 6 Ref tools."""
    tools = await get_ref_tools()
    discovered = {t.name for t in tools}
    assert discovered == REF_TOOL_NAMES


@pytest.mark.integration
async def test_ref_session_discovers_all_tools() -> None:
    """Verify ref_session() context manager returns all 6 tools."""
    async with ref_session() as tools:
        discovered = {t.name for t in tools}
        assert discovered == REF_TOOL_NAMES
