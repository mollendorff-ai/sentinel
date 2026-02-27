"""FastMCP server -- ``sentinel_analyze`` and ``sentinel_resume`` tools.

Runs on stdio transport so any MCP-compatible client (Claude Desktop,
Cursor, etc.) can call the Sentinel earnings-analysis pipeline.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from sentinel.checkpointer import create_checkpointer
from sentinel.graph.pipeline import compile_graph
from sentinel.output import write_run_output
from sentinel.rag.store import create_store, ingest

logger = logging.getLogger(__name__)

mcp = FastMCP("sentinel")

_VERSION = "0.8.0"
_INTERRUPT_BEFORE = ["synthesizer"]


@mcp.tool()
async def sentinel_analyze(
    ticker: Annotated[str, Field(description="Stock ticker symbol (e.g. AAPL, MSFT)")],
    *,
    quick: Annotated[
        bool,
        Field(description="Skip risk/scenario analysis for faster results"),
    ] = False,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Run Sentinel earnings analysis pipeline to the analyst approval gate.

    Runs all agents (Research -> Retriever -> Modeler -> Risk Analyst -> Scenario
    Planner) and pauses before generating the final brief. Returns thread_id + draft
    state for analyst review. Call sentinel_resume to approve or reject and generate
    the brief.
    """
    ticker = ticker.upper()
    thread_id = f"{ticker}-{datetime.now(tz=UTC).strftime('%Y%m%d-%H%M%S')}"

    if ctx:
        await ctx.report_progress(0, 5)

    try:
        with create_checkpointer() as checkpointer:
            graph = compile_graph(
                checkpointer=checkpointer,
                interrupt_before=_INTERRUPT_BEFORE,
            )
            mode = "quick" if quick else "full"
            config: dict[str, Any] = {
                "run_name": f"sentinel-{ticker}-{mode}",
                "tags": [f"ticker:{ticker}", f"mode:{mode}", f"v{_VERSION}"],
                "metadata": {
                    "ticker": ticker,
                    "mode": mode,
                    "version": _VERSION,
                },
                "configurable": {"thread_id": thread_id},
            }

            step = 0
            total = 5
            async for update in graph.astream(
                {"ticker": ticker, "quick": quick},
                config=config,
                stream_mode="updates",
            ):
                for node_name in update:
                    step += 1
                    if ctx:
                        await ctx.info(f"  [{node_name}] complete")
                        await ctx.report_progress(step, total)

            snapshot = graph.get_state(config)

    except Exception as exc:
        logger.exception("sentinel_analyze failed for %s", ticker)
        return {
            "thread_id": thread_id,
            "status": "error",
            "error": str(exc),
            "ticker": ticker,
        }

    return {
        "thread_id": thread_id,
        "status": "awaiting_approval",
        "ticker": ticker,
        "quick": quick,
        "next_nodes": list(snapshot.next),
        "draft": {k: v for k, v in snapshot.values.items() if k != "model_yaml"},
    }


def _try_ingest(state: dict[str, Any], thread_id: str) -> None:
    """Non-fatal Qdrant ingest (same pattern as ``__main__.py``)."""
    raw_data = state.get("raw_data", {})
    if not raw_data or "error" in raw_data:
        return
    try:
        store = create_store()
        ingest(store, raw_data)
    except (OSError, RuntimeError):
        logger.warning("Qdrant ingest failed for thread %s (non-fatal)", thread_id)


@mcp.tool()
async def sentinel_resume(
    thread_id: Annotated[str, Field(description="Thread ID returned by sentinel_analyze")],
    decision: Annotated[
        Literal["approve", "reject"],
        Field(description="'approve' to generate brief, 'reject' to revise with feedback"),
    ],
    *,
    feedback: Annotated[
        str,
        Field(description="Analyst feedback for revision (required when decision='reject')"),
    ] = "",
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Resume a paused Sentinel analysis after analyst review.

    Pass decision='approve' to generate the executive brief, or decision='reject'
    with feedback to have the Synthesizer revise its analysis incorporating your notes.
    Returns the final brief text and output directory path.
    """
    if decision == "reject" and not feedback:
        msg = "feedback is required when decision='reject'"
        raise ValueError(msg)

    try:
        with create_checkpointer() as checkpointer:
            graph = compile_graph(
                checkpointer=checkpointer,
                interrupt_before=_INTERRUPT_BEFORE,
            )
            config: dict[str, Any] = {"configurable": {"thread_id": thread_id}}

            if decision == "reject":
                await graph.aupdate_state(config, {"analyst_feedback": feedback})

            if ctx:
                await ctx.info("Generating brief...")

            async for update in graph.astream(
                None,
                config=config,
                stream_mode="updates",
            ):
                for node_name in update:
                    if ctx:
                        await ctx.info(f"  [{node_name}] complete")

            snapshot = graph.get_state(config)
            state = dict(snapshot.values)

            output_dir = write_run_output(state)
            _try_ingest(state, thread_id)

    except ValueError:
        raise
    except Exception as exc:
        logger.exception("sentinel_resume failed for thread %s", thread_id)
        return {"thread_id": thread_id, "status": "error", "error": str(exc)}

    return {
        "thread_id": thread_id,
        "status": "complete",
        "brief": state.get("brief", ""),
        "output_directory": str(output_dir),
        "ticker": state.get("ticker", ""),
    }


def run_mcp_server() -> None:
    """Start Sentinel MCP server on stdio transport."""
    mcp.run(transport="stdio")
