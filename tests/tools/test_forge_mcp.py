"""Smoke tests for Forge MCP client."""

import logging
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from sentinel.tools.forge_mcp import (
    FORGE_TOOL_NAMES,
    _log_discovered,
    forge_session,
    get_forge_tools,
)

FIXTURES = Path(__file__).parent.parent / "fixtures"
SIMPLE_MODEL = FIXTURES / "simple_model.yaml"


def _text_from(result: list[dict[str, Any]]) -> str:
    """Extract text from MCP tool result content blocks."""
    return " ".join(block["text"] for block in result if block.get("type") == "text")


async def test_get_forge_tools_discovers_all() -> None:
    """Verify get_forge_tools() returns all 10 Forge tools."""
    tools = await get_forge_tools()
    discovered = {t.name for t in tools}
    assert discovered == FORGE_TOOL_NAMES


async def test_forge_session_discovers_all_tools() -> None:
    """Verify forge_session() context manager returns all 10 tools."""
    async with forge_session() as tools:
        discovered = {t.name for t in tools}
        assert discovered == FORGE_TOOL_NAMES


async def test_forge_validate_accepts_valid_model() -> None:
    """Call forge_validate on a known-good model."""
    tools = await get_forge_tools()
    validate = next(t for t in tools if t.name == "forge_validate")
    result = await validate.ainvoke({"file_path": str(SIMPLE_MODEL)})
    assert "successful" in _text_from(result).lower()


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
    assert "completed" in _text_from(result).lower()


def test_log_discovered_warns_on_missing_tools(caplog: pytest.LogCaptureFixture) -> None:
    """Verify _log_discovered warns when expected tools are missing."""
    partial_tool = MagicMock()
    partial_tool.name = "forge_validate"

    with caplog.at_level(logging.WARNING, logger="sentinel.tools.forge_mcp"):
        _log_discovered([partial_tool])

    assert "Expected Forge tools not found" in caplog.text
