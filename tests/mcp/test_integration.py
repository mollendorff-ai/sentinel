"""Integration tests for Sentinel MCP server."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sentinel.mcp.server import mcp, sentinel_analyze, sentinel_resume

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

_TOOLS_LIST_REQUEST_ID = 2
_PROJECT_ROOT = str(Path(__file__).resolve().parents[2])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_graph(
    state: dict[str, Any],
    *,
    next_nodes: tuple[str, ...] = ("synthesizer",),
) -> MagicMock:
    """Create a mock compiled graph returning *state* via astream + get_state."""
    mock = MagicMock()

    async def _astream(
        _first_arg: dict[str, object] | None = None,
        **_kwargs: object,
    ) -> AsyncIterator[dict[str, dict[str, object]]]:
        for key in state:
            yield {key: {}}

    mock.astream = MagicMock(side_effect=_astream)

    snapshot = MagicMock()
    snapshot.values = state
    snapshot.next = next_nodes
    mock.get_state = MagicMock(return_value=snapshot)
    mock.aupdate_state = AsyncMock()
    return mock


def _mock_checkpointer() -> MagicMock:
    """Create a mock checkpointer context manager."""
    ckpt = MagicMock()
    ckpt.__enter__ = MagicMock(return_value=ckpt)
    ckpt.__exit__ = MagicMock(return_value=False)
    return ckpt


# ---------------------------------------------------------------------------
# Tool registry (non-integration — run in CI)
# ---------------------------------------------------------------------------


class TestToolRegistry:
    """Verify MCP server tool registration metadata."""

    async def test_sentinel_analyze_tool_is_registered(self) -> None:
        """Verify sentinel_analyze is registered with correct schema fields."""
        tools = await mcp.list_tools()
        by_name = {t.name: t for t in tools}

        assert "sentinel_analyze" in by_name
        tool = by_name["sentinel_analyze"]
        schema_props = tool.inputSchema.get("properties", {})
        assert "ticker" in schema_props
        assert "quick" in schema_props

    async def test_sentinel_resume_tool_is_registered(self) -> None:
        """Verify sentinel_resume is registered with correct schema fields."""
        tools = await mcp.list_tools()
        by_name = {t.name: t for t in tools}

        assert "sentinel_resume" in by_name
        tool = by_name["sentinel_resume"]
        schema_props = tool.inputSchema.get("properties", {})
        assert "thread_id" in schema_props
        assert "decision" in schema_props
        assert "feedback" in schema_props


# ---------------------------------------------------------------------------
# Full flow (integration — skipped in CI)
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_mcp_stdio_protocol_tool_discovery() -> None:
    """Verify MCP server responds to tools/list over stdio JSON-RPC."""
    init_msg = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "0.1.0"},
            },
        },
    )
    list_msg = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": _TOOLS_LIST_REQUEST_ID,
            "method": "tools/list",
            "params": {},
        },
    )

    stdin_data = f"{init_msg}\n{list_msg}\n".encode()

    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "sentinel",
        "mcp",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=_PROJECT_ROOT,
    )
    stdout, _stderr = await asyncio.wait_for(proc.communicate(stdin_data), timeout=30)

    # Parse JSON-RPC responses from stdout (one per line)
    responses = [json.loads(raw) for raw in stdout.decode().strip().splitlines() if raw.strip()]

    # Find the tools/list response
    tools_resp = next(
        (r for r in responses if r.get("id") == _TOOLS_LIST_REQUEST_ID),
        None,
    )
    assert tools_resp is not None, f"No tools/list response found in: {responses}"

    tool_names = {t["name"] for t in tools_resp["result"]["tools"]}
    assert "sentinel_analyze" in tool_names
    assert "sentinel_resume" in tool_names


@pytest.mark.integration
async def test_sentinel_analyze_resume_full_flow_mocked() -> None:
    """Full analyze -> resume flow using mocked graph (no real LLM)."""
    analyze_state: dict[str, Any] = {
        "ticker": "AAPL",
        "brief": "Draft brief for AAPL.",
        "raw_data": {"ticker": "AAPL", "period": "Q1 2026", "revenue": 94800},
    }
    resume_state: dict[str, Any] = {
        "ticker": "AAPL",
        "brief": "Final executive brief for AAPL.",
        "raw_data": {"ticker": "AAPL", "period": "Q1 2026", "revenue": 94800},
    }

    analyze_graph = _mock_graph(analyze_state, next_nodes=("synthesizer",))
    resume_graph = _mock_graph(resume_state, next_nodes=())

    mock_compile = MagicMock(side_effect=[analyze_graph, resume_graph])
    mock_write = MagicMock(return_value=Path("output/AAPL/20260226"))

    with (
        patch(
            "sentinel.mcp.server.create_checkpointer",
            return_value=_mock_checkpointer(),
        ),
        patch("sentinel.mcp.server.compile_graph", mock_compile),
        patch("sentinel.mcp.server.write_run_output", mock_write),
        patch("sentinel.mcp.server.create_store"),
        patch("sentinel.mcp.server.ingest"),
    ):
        # Step 1: analyze
        analyze_result = await sentinel_analyze(ticker="AAPL")

        assert analyze_result["status"] == "awaiting_approval"
        assert analyze_result["thread_id"].startswith("AAPL-")
        assert "synthesizer" in analyze_result["next_nodes"]

        thread_id = analyze_result["thread_id"]

        # Step 2: resume with approval
        resume_result = await sentinel_resume(
            thread_id=thread_id,
            decision="approve",
        )

    assert resume_result["status"] == "complete"
    assert resume_result["brief"] == "Final executive brief for AAPL."
    assert resume_result["ticker"] == "AAPL"
    mock_write.assert_called_once()
