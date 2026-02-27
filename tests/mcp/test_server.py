"""Tests for Sentinel MCP server tools."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sentinel.mcp.server import (
    mcp,
    run_mcp_server,
    sentinel_analyze,
    sentinel_resume,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


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


def _mock_ctx() -> MagicMock:
    """Create a mock MCP Context with async methods."""
    ctx = MagicMock()
    ctx.info = AsyncMock()
    ctx.warning = AsyncMock()
    ctx.report_progress = AsyncMock()
    return ctx


# ---------------------------------------------------------------------------
# sentinel_analyze
# ---------------------------------------------------------------------------


class TestSentinelAnalyze:
    """Tests for the sentinel_analyze tool."""

    async def test_returns_thread_id(self) -> None:
        """Verify sentinel_analyze returns a thread_id and awaiting_approval status."""
        state: dict[str, Any] = {"ticker": "AAPL", "brief": "Draft brief."}
        mock_graph = _mock_graph(state)

        with (
            patch(
                "sentinel.mcp.server.create_checkpointer",
                return_value=_mock_checkpointer(),
            ),
            patch("sentinel.mcp.server.compile_graph", return_value=mock_graph),
        ):
            result = await sentinel_analyze(ticker="AAPL")

        assert "thread_id" in result
        assert result["thread_id"].startswith("AAPL-")
        assert result["status"] == "awaiting_approval"

    async def test_uppercases_ticker(self) -> None:
        """Verify lowercase ticker is uppercased in the result."""
        state: dict[str, Any] = {"ticker": "AAPL", "brief": "Draft."}
        mock_graph = _mock_graph(state)

        with (
            patch(
                "sentinel.mcp.server.create_checkpointer",
                return_value=_mock_checkpointer(),
            ),
            patch("sentinel.mcp.server.compile_graph", return_value=mock_graph),
        ):
            result = await sentinel_analyze(ticker="aapl")

        assert result["ticker"] == "AAPL"

    async def test_with_quick_flag(self) -> None:
        """Verify quick=True is passed through to the graph input."""
        state: dict[str, Any] = {"ticker": "MSFT", "brief": "Quick."}
        mock_graph = _mock_graph(state)

        with (
            patch(
                "sentinel.mcp.server.create_checkpointer",
                return_value=_mock_checkpointer(),
            ),
            patch("sentinel.mcp.server.compile_graph", return_value=mock_graph),
        ):
            result = await sentinel_analyze(ticker="MSFT", quick=True)

        astream_call = mock_graph.astream.call_args
        assert astream_call[0][0]["quick"] is True
        assert result["quick"] is True

    async def test_omits_model_yaml_from_draft(self) -> None:
        """Verify model_yaml is excluded from the draft dict."""
        state: dict[str, Any] = {
            "ticker": "AAPL",
            "brief": "Draft.",
            "model_yaml": "big-yaml-string",
        }
        mock_graph = _mock_graph(state)

        with (
            patch(
                "sentinel.mcp.server.create_checkpointer",
                return_value=_mock_checkpointer(),
            ),
            patch("sentinel.mcp.server.compile_graph", return_value=mock_graph),
        ):
            result = await sentinel_analyze(ticker="AAPL")

        assert "model_yaml" not in result["draft"]
        assert "ticker" in result["draft"]

    async def test_with_ctx_reports_progress(self) -> None:
        """Verify ctx.report_progress and ctx.info are called when ctx is provided."""
        state: dict[str, Any] = {"research": {}, "ticker": "AAPL"}
        mock_graph = _mock_graph(state)
        ctx = _mock_ctx()

        with (
            patch(
                "sentinel.mcp.server.create_checkpointer",
                return_value=_mock_checkpointer(),
            ),
            patch("sentinel.mcp.server.compile_graph", return_value=mock_graph),
        ):
            await sentinel_analyze(ticker="AAPL", ctx=ctx)

        ctx.report_progress.assert_called()
        ctx.info.assert_called()

    async def test_without_ctx_no_error(self) -> None:
        """Verify sentinel_analyze runs cleanly when ctx is None."""
        state: dict[str, Any] = {"ticker": "GOOG", "brief": "Brief."}
        mock_graph = _mock_graph(state)

        with (
            patch(
                "sentinel.mcp.server.create_checkpointer",
                return_value=_mock_checkpointer(),
            ),
            patch("sentinel.mcp.server.compile_graph", return_value=mock_graph),
        ):
            result = await sentinel_analyze(ticker="GOOG", ctx=None)

        assert result["status"] == "awaiting_approval"

    async def test_on_exception_returns_error_status(self) -> None:
        """Verify sentinel_analyze returns error status when graph.astream raises."""
        mock_graph = MagicMock()

        async def _boom(
            _first_arg: dict[str, object] | None = None,
            **_kwargs: object,
        ) -> AsyncIterator[dict[str, dict[str, object]]]:
            msg = "boom"
            raise RuntimeError(msg)
            yield  # pragma: no cover

        mock_graph.astream = MagicMock(side_effect=_boom)

        with (
            patch(
                "sentinel.mcp.server.create_checkpointer",
                return_value=_mock_checkpointer(),
            ),
            patch("sentinel.mcp.server.compile_graph", return_value=mock_graph),
        ):
            result = await sentinel_analyze(ticker="FAIL")

        assert result["status"] == "error"
        assert "boom" in result["error"]
        assert result["ticker"] == "FAIL"


# ---------------------------------------------------------------------------
# sentinel_resume
# ---------------------------------------------------------------------------


class TestSentinelResume:
    """Tests for the sentinel_resume tool."""

    async def test_approve_does_not_inject_feedback(self) -> None:
        """Verify decision='approve' does NOT call aupdate_state."""
        state: dict[str, Any] = {"ticker": "AAPL", "brief": "Final brief."}
        mock_graph = _mock_graph(state, next_nodes=())

        with (
            patch(
                "sentinel.mcp.server.create_checkpointer",
                return_value=_mock_checkpointer(),
            ),
            patch("sentinel.mcp.server.compile_graph", return_value=mock_graph),
            patch(
                "sentinel.mcp.server.write_run_output",
                return_value=Path("output/AAPL/20260226"),
            ),
            patch("sentinel.mcp.server.create_store"),
            patch("sentinel.mcp.server.ingest"),
        ):
            await sentinel_resume(
                thread_id="AAPL-20260226-120000",
                decision="approve",
            )

        mock_graph.aupdate_state.assert_not_called()

    async def test_approve_calls_astream_none(self) -> None:
        """Verify astream is called with None as first argument to resume."""
        state: dict[str, Any] = {"ticker": "AAPL", "brief": "Brief."}
        mock_graph = _mock_graph(state, next_nodes=())

        with (
            patch(
                "sentinel.mcp.server.create_checkpointer",
                return_value=_mock_checkpointer(),
            ),
            patch("sentinel.mcp.server.compile_graph", return_value=mock_graph),
            patch(
                "sentinel.mcp.server.write_run_output",
                return_value=Path("output/AAPL/20260226"),
            ),
            patch("sentinel.mcp.server.create_store"),
            patch("sentinel.mcp.server.ingest"),
        ):
            await sentinel_resume(
                thread_id="AAPL-20260226-120000",
                decision="approve",
            )

        astream_call = mock_graph.astream.call_args
        assert astream_call[0][0] is None

    async def test_reject_injects_feedback(self) -> None:
        """Verify decision='reject' calls aupdate_state with analyst_feedback."""
        state: dict[str, Any] = {"ticker": "AAPL", "brief": "Revised."}
        mock_graph = _mock_graph(state, next_nodes=())

        with (
            patch(
                "sentinel.mcp.server.create_checkpointer",
                return_value=_mock_checkpointer(),
            ),
            patch("sentinel.mcp.server.compile_graph", return_value=mock_graph),
            patch(
                "sentinel.mcp.server.write_run_output",
                return_value=Path("output/AAPL/20260226"),
            ),
            patch("sentinel.mcp.server.create_store"),
            patch("sentinel.mcp.server.ingest"),
        ):
            await sentinel_resume(
                thread_id="AAPL-20260226-120000",
                decision="reject",
                feedback="focus on margins",
            )

        mock_graph.aupdate_state.assert_called_once()
        update_args = mock_graph.aupdate_state.call_args[0]
        assert update_args[1] == {"analyst_feedback": "focus on margins"}

    async def test_reject_without_feedback_raises(self) -> None:
        """Verify decision='reject' with empty feedback raises ValueError."""
        with pytest.raises(ValueError, match="feedback is required"):
            await sentinel_resume(
                thread_id="AAPL-20260226-120000",
                decision="reject",
                feedback="",
            )

    async def test_returns_brief(self) -> None:
        """Verify the result contains the brief from the final state."""
        state: dict[str, Any] = {"ticker": "AAPL", "brief": "Executive summary here."}
        mock_graph = _mock_graph(state, next_nodes=())

        with (
            patch(
                "sentinel.mcp.server.create_checkpointer",
                return_value=_mock_checkpointer(),
            ),
            patch("sentinel.mcp.server.compile_graph", return_value=mock_graph),
            patch(
                "sentinel.mcp.server.write_run_output",
                return_value=Path("output/AAPL/20260226"),
            ),
            patch("sentinel.mcp.server.create_store"),
            patch("sentinel.mcp.server.ingest"),
        ):
            result = await sentinel_resume(
                thread_id="AAPL-20260226-120000",
                decision="approve",
            )

        assert result["brief"] == "Executive summary here."
        assert result["status"] == "complete"

    async def test_writes_output(self) -> None:
        """Verify write_run_output is called with the final state."""
        state: dict[str, Any] = {"ticker": "AAPL", "brief": "Brief."}
        mock_graph = _mock_graph(state, next_nodes=())
        mock_write = MagicMock(return_value=Path("output/AAPL/20260226"))

        with (
            patch(
                "sentinel.mcp.server.create_checkpointer",
                return_value=_mock_checkpointer(),
            ),
            patch("sentinel.mcp.server.compile_graph", return_value=mock_graph),
            patch("sentinel.mcp.server.write_run_output", mock_write),
            patch("sentinel.mcp.server.create_store"),
            patch("sentinel.mcp.server.ingest"),
        ):
            await sentinel_resume(
                thread_id="AAPL-20260226-120000",
                decision="approve",
            )

        mock_write.assert_called_once_with(state)

    async def test_ingests_to_qdrant(self) -> None:
        """Verify ingest is called when raw_data is present and has no error."""
        raw_data: dict[str, Any] = {
            "ticker": "AAPL",
            "period": "Q1 2026",
            "revenue": 94800,
        }
        state: dict[str, Any] = {"ticker": "AAPL", "brief": "B.", "raw_data": raw_data}
        mock_graph = _mock_graph(state, next_nodes=())
        mock_store = MagicMock()
        mock_ingest = MagicMock()

        with (
            patch(
                "sentinel.mcp.server.create_checkpointer",
                return_value=_mock_checkpointer(),
            ),
            patch("sentinel.mcp.server.compile_graph", return_value=mock_graph),
            patch(
                "sentinel.mcp.server.write_run_output",
                return_value=Path("output/AAPL/20260226"),
            ),
            patch("sentinel.mcp.server.create_store", return_value=mock_store),
            patch("sentinel.mcp.server.ingest", mock_ingest),
        ):
            await sentinel_resume(
                thread_id="AAPL-20260226-120000",
                decision="approve",
            )

        mock_ingest.assert_called_once_with(mock_store, raw_data)

    async def test_skips_ingest_on_error_data(self) -> None:
        """Verify ingest is NOT called when raw_data contains an error key."""
        state: dict[str, Any] = {
            "ticker": "AAPL",
            "brief": "B.",
            "raw_data": {"error": "ref_fetch failed"},
        }
        mock_graph = _mock_graph(state, next_nodes=())
        mock_ingest = MagicMock()

        with (
            patch(
                "sentinel.mcp.server.create_checkpointer",
                return_value=_mock_checkpointer(),
            ),
            patch("sentinel.mcp.server.compile_graph", return_value=mock_graph),
            patch(
                "sentinel.mcp.server.write_run_output",
                return_value=Path("output/AAPL/20260226"),
            ),
            patch("sentinel.mcp.server.create_store"),
            patch("sentinel.mcp.server.ingest", mock_ingest),
        ):
            await sentinel_resume(
                thread_id="AAPL-20260226-120000",
                decision="approve",
            )

        mock_ingest.assert_not_called()

    async def test_ingest_failure_nonfatal(self) -> None:
        """Verify result is still returned when ingest raises an exception."""
        raw_data: dict[str, Any] = {"ticker": "AAPL", "period": "Q1 2026"}
        state: dict[str, Any] = {"ticker": "AAPL", "brief": "B.", "raw_data": raw_data}
        mock_graph = _mock_graph(state, next_nodes=())

        with (
            patch(
                "sentinel.mcp.server.create_checkpointer",
                return_value=_mock_checkpointer(),
            ),
            patch("sentinel.mcp.server.compile_graph", return_value=mock_graph),
            patch(
                "sentinel.mcp.server.write_run_output",
                return_value=Path("output/AAPL/20260226"),
            ),
            patch(
                "sentinel.mcp.server.create_store",
                side_effect=RuntimeError("qdrant down"),
            ),
        ):
            result = await sentinel_resume(
                thread_id="AAPL-20260226-120000",
                decision="approve",
            )

        assert result["status"] == "complete"
        assert result["brief"] == "B."

    async def test_with_ctx_logs_info(self) -> None:
        """Verify ctx.info is called when ctx is provided."""
        state: dict[str, Any] = {"ticker": "AAPL", "brief": "Brief."}
        mock_graph = _mock_graph(state, next_nodes=())
        ctx = _mock_ctx()

        with (
            patch(
                "sentinel.mcp.server.create_checkpointer",
                return_value=_mock_checkpointer(),
            ),
            patch("sentinel.mcp.server.compile_graph", return_value=mock_graph),
            patch(
                "sentinel.mcp.server.write_run_output",
                return_value=Path("output/AAPL/20260226"),
            ),
            patch("sentinel.mcp.server.create_store"),
            patch("sentinel.mcp.server.ingest"),
        ):
            await sentinel_resume(
                thread_id="AAPL-20260226-120000",
                decision="approve",
                ctx=ctx,
            )

        ctx.info.assert_called()

    async def test_without_ctx_no_error(self) -> None:
        """Verify sentinel_resume runs cleanly when ctx is None."""
        state: dict[str, Any] = {"ticker": "AAPL", "brief": "Brief."}
        mock_graph = _mock_graph(state, next_nodes=())

        with (
            patch(
                "sentinel.mcp.server.create_checkpointer",
                return_value=_mock_checkpointer(),
            ),
            patch("sentinel.mcp.server.compile_graph", return_value=mock_graph),
            patch(
                "sentinel.mcp.server.write_run_output",
                return_value=Path("output/AAPL/20260226"),
            ),
            patch("sentinel.mcp.server.create_store"),
            patch("sentinel.mcp.server.ingest"),
        ):
            result = await sentinel_resume(
                thread_id="AAPL-20260226-120000",
                decision="approve",
                ctx=None,
            )

        assert result["status"] == "complete"

    async def test_value_error_inside_try_reraises(self) -> None:
        """Verify ValueError raised inside try block is not swallowed."""
        state: dict[str, Any] = {"ticker": "AAPL", "brief": "Brief."}
        mock_graph = _mock_graph(state, next_nodes=())

        with (
            patch(
                "sentinel.mcp.server.create_checkpointer",
                return_value=_mock_checkpointer(),
            ),
            patch("sentinel.mcp.server.compile_graph", return_value=mock_graph),
            patch(
                "sentinel.mcp.server.write_run_output",
                side_effect=ValueError("bad state"),
            ),
            pytest.raises(ValueError, match="bad state"),
        ):
            await sentinel_resume(
                thread_id="AAPL-20260226-120000",
                decision="approve",
            )

    async def test_on_exception_returns_error_status(self) -> None:
        """Verify sentinel_resume returns error status when astream raises."""
        mock_graph = MagicMock()

        async def _boom(
            _first_arg: dict[str, object] | None = None,
            **_kwargs: object,
        ) -> AsyncIterator[dict[str, dict[str, object]]]:
            msg = "resume failed"
            raise RuntimeError(msg)
            yield  # pragma: no cover

        mock_graph.astream = MagicMock(side_effect=_boom)
        mock_graph.aupdate_state = AsyncMock()

        with (
            patch(
                "sentinel.mcp.server.create_checkpointer",
                return_value=_mock_checkpointer(),
            ),
            patch("sentinel.mcp.server.compile_graph", return_value=mock_graph),
        ):
            result = await sentinel_resume(
                thread_id="AAPL-20260226-120000",
                decision="approve",
            )

        assert result["status"] == "error"
        assert "resume failed" in result["error"]


# ---------------------------------------------------------------------------
# run_mcp_server / tool registration
# ---------------------------------------------------------------------------


class TestMcpServer:
    """Tests for run_mcp_server and tool registration."""

    def test_run_mcp_server_calls_mcp_run(self) -> None:
        """Verify run_mcp_server calls mcp.run with stdio transport."""
        with patch("sentinel.mcp.server.mcp") as mock_mcp:
            run_mcp_server()

        mock_mcp.run.assert_called_once_with(transport="stdio")

    async def test_mcp_server_has_two_tools(self) -> None:
        """Verify exactly sentinel_analyze and sentinel_resume are registered."""
        tools = await mcp.list_tools()
        tool_names = {t.name for t in tools}
        assert tool_names == {"sentinel_analyze", "sentinel_resume"}
