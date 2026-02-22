"""Tests for the LangGraph pipeline wiring."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

from sentinel.graph.pipeline import build_graph, compile_graph

EXPECTED_REVENUE = 1000


def test_build_graph_has_expected_nodes() -> None:
    """Verify the graph contains all three agent nodes."""
    graph = build_graph()
    node_names = set(graph.nodes)
    assert "research" in node_names
    assert "modeler" in node_names
    assert "synthesizer" in node_names


def test_compile_graph_returns_runnable() -> None:
    """Verify compile_graph produces an invokable graph."""
    compiled = compile_graph()
    assert hasattr(compiled, "ainvoke")


async def test_pipeline_executes_all_nodes() -> None:
    """Verify the full pipeline calls research -> modeler -> synthesizer."""
    mock_research_result: dict[str, Any] = {
        "raw_data": {"ticker": "TEST", "revenue": 1000},
    }
    mock_modeler_result: dict[str, Any] = {
        "model_yaml": "test yaml",
        "forge_results": {"outputs.margin": 0.5},
    }
    mock_synth_result: dict[str, Any] = {
        "brief": "Test brief.",
    }

    # Patch at the import location in pipeline.py (not the definition module)
    with (
        patch(
            "sentinel.graph.pipeline.research_node",
            new_callable=AsyncMock,
            return_value=mock_research_result,
        ) as mock_research,
        patch(
            "sentinel.graph.pipeline.modeler_node",
            new_callable=AsyncMock,
            return_value=mock_modeler_result,
        ) as mock_modeler,
        patch(
            "sentinel.graph.pipeline.synthesizer_node",
            new_callable=AsyncMock,
            return_value=mock_synth_result,
        ) as mock_synth,
    ):
        compiled = compile_graph()
        result = await compiled.ainvoke({"ticker": "TEST"})

    mock_research.assert_called_once()
    mock_modeler.assert_called_once()
    mock_synth.assert_called_once()

    assert result["brief"] == "Test brief."
    assert result["raw_data"]["revenue"] == EXPECTED_REVENUE
