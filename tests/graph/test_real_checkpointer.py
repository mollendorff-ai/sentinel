"""Run the compiled graph with the real async SQLite checkpointer (no mocks of persistence)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import patch

from sentinel.checkpointer import create_checkpointer
from sentinel.graph.pipeline import compile_graph

if TYPE_CHECKING:
    from pathlib import Path


def _stub(key: str, value: object):  # noqa: ANN202
    async def node(_state: dict[str, Any]) -> dict[str, Any]:
        return {key: value}

    return node


def _patched_nodes():  # noqa: ANN202
    return (
        patch("sentinel.graph.pipeline.research_node", _stub("raw_data", {"ticker": "AAPL"})),
        patch("sentinel.graph.pipeline.retriever_node", _stub("historical_context", [])),
        patch("sentinel.graph.pipeline.modeler_node", _stub("model_yaml", "m")),
        patch("sentinel.graph.pipeline.risk_analyst_node", _stub("risk_analysis", {})),
        patch("sentinel.graph.pipeline.scenario_planner_node", _stub("scenario_analysis", {})),
        patch("sentinel.graph.pipeline.synthesizer_node", _stub("brief", "BRIEF")),
    )


async def test_graph_runs_and_resumes_with_real_checkpointer(tmp_path: Path) -> None:
    """The pipeline must run, pause at the gate and resume with a real SQLite checkpointer."""
    patches = _patched_nodes()
    for p in patches:
        p.start()
    try:
        async with create_checkpointer(tmp_path / "ckpt.db") as saver:
            graph = compile_graph(checkpointer=saver, interrupt_before=["synthesizer"])
            config = {"configurable": {"thread_id": "t1"}}
            seen = [
                list(u)
                async for u in graph.astream(
                    {"ticker": "AAPL", "quick": False},
                    config=config,
                    stream_mode="updates",
                )
            ]
            assert ["synthesizer"] not in seen
            snapshot = await graph.aget_state(config)
            assert snapshot.next == ("synthesizer",)

            async for _ in graph.astream(None, config=config, stream_mode="updates"):
                pass
            final = await graph.aget_state(config)
            assert final.values["brief"] == "BRIEF"
    finally:
        for p in patches:
            p.stop()
