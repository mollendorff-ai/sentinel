"""Tests for Forge MCP client."""

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sentinel.tools.forge_mcp import (
    FORGE_TOOL_NAMES,
    _log_discovered,
    forge_session,
    get_forge_tools,
)

FIXTURES = Path(__file__).parent.parent / "fixtures"
SIMPLE_MODEL = FIXTURES / "simple_model.yaml"

EXPECTED_TOOL_COUNT = 20


def _text_from(result: list[dict[str, Any]]) -> str:
    """Extract text from MCP tool result content blocks."""
    return " ".join(block["text"] for block in result if block.get("type") == "text")


def _fake_tools() -> list[MagicMock]:
    """Build a list of mock tools matching all Forge tool names."""
    tools = []
    for name in FORGE_TOOL_NAMES:
        tool = MagicMock()
        tool.name = name
        tools.append(tool)
    return tools


# ---------------------------------------------------------------------------
# Unit tests (no external binaries)
# ---------------------------------------------------------------------------


async def test_get_forge_tools_mocked() -> None:
    """Verify get_forge_tools() connects and returns tools (mocked MCP)."""
    fake = _fake_tools()
    mock_client = MagicMock()
    mock_client.get_tools = AsyncMock(return_value=fake)

    with patch("sentinel.tools.forge_mcp.MultiServerMCPClient", return_value=mock_client):
        tools = await get_forge_tools()

    assert {t.name for t in tools} == FORGE_TOOL_NAMES
    assert len(tools) == EXPECTED_TOOL_COUNT


async def test_forge_session_mocked() -> None:
    """Verify forge_session() yields tools via async context manager (mocked MCP)."""
    fake = _fake_tools()

    @asynccontextmanager
    async def _fake_session(_name: str):  # noqa: ANN202
        yield MagicMock()

    mock_client = MagicMock()
    mock_client.session = _fake_session

    with (
        patch("sentinel.tools.forge_mcp.MultiServerMCPClient", return_value=mock_client),
        patch("sentinel.tools.forge_mcp.load_mcp_tools", AsyncMock(return_value=fake)),
    ):
        async with forge_session() as tools:
            assert {t.name for t in tools} == FORGE_TOOL_NAMES


def test_log_discovered_warns_on_missing_tools(caplog: pytest.LogCaptureFixture) -> None:
    """Verify _log_discovered warns when expected tools are missing."""
    partial_tool = MagicMock()
    partial_tool.name = "forge_validate"

    with caplog.at_level(logging.WARNING, logger="sentinel.tools.forge_mcp"):
        _log_discovered([partial_tool])

    assert "Expected Forge tools not found" in caplog.text


# ---------------------------------------------------------------------------
# Integration tests (require real `forge` binary)
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_get_forge_tools_discovers_all() -> None:
    """Verify get_forge_tools() returns all 20 Forge tools."""
    tools = await get_forge_tools()
    discovered = {t.name for t in tools}
    assert discovered == FORGE_TOOL_NAMES


@pytest.mark.integration
async def test_forge_session_discovers_all_tools() -> None:
    """Verify forge_session() context manager returns all 20 tools."""
    async with forge_session() as tools:
        discovered = {t.name for t in tools}
        assert discovered == FORGE_TOOL_NAMES


@pytest.mark.integration
async def test_forge_validate_accepts_valid_model() -> None:
    """Call forge_validate on a known-good model."""
    tools = await get_forge_tools()
    validate = next(t for t in tools if t.name == "forge_validate")
    result = await validate.ainvoke({"file_path": str(SIMPLE_MODEL)})
    parsed = json.loads(_text_from(result))
    assert parsed["tables_valid"] is True
    assert parsed["scalars_valid"] is True


@pytest.mark.integration
async def test_forge_calculate_dry_run() -> None:
    """Call forge_calculate (dry run) and verify it completes."""
    tools = await get_forge_tools()
    calculate = next(t for t in tools if t.name == "forge_calculate")
    result = await calculate.ainvoke(
        {
            "file_path": str(SIMPLE_MODEL),
            "dry_run": True,
        },
    )
    parsed = json.loads(_text_from(result))
    assert parsed["dry_run"] is True
    assert "scalars" in parsed
