"""Tests for the LangGraph pipeline wiring."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from langgraph.checkpoint.base import BaseCheckpointSaver

from sentinel.graph.pipeline import _route_after_modeler, build_graph, compile_graph

EXPECTED_REVENUE = 1000
EXPECTED_NODE_COUNT = 6


def test_build_graph_has_expected_nodes() -> None:
    """Verify the graph contains all six agent nodes."""
    graph = build_graph()
    node_names = set(graph.nodes)
    assert "research" in node_names
    assert "retriever" in node_names
    assert "modeler" in node_names
    assert "risk_analyst" in node_names
    assert "scenario_planner" in node_names
    assert "synthesizer" in node_names
    assert len(node_names) == EXPECTED_NODE_COUNT


def test_compile_graph_returns_runnable() -> None:
    """Verify compile_graph produces an invokable graph."""
    compiled = compile_graph()
    assert hasattr(compiled, "ainvoke")


def test_route_after_modeler_defaults_to_risk_analyst() -> None:
    """Verify routing goes to risk_analyst when quick is not set."""
    assert _route_after_modeler({}) == "risk_analyst"


def test_route_after_modeler_returns_risk_analyst_when_not_quick() -> None:
    """Verify routing goes to risk_analyst when quick is False."""
    assert _route_after_modeler({"quick": False}) == "risk_analyst"


def test_route_after_modeler_returns_synthesizer_when_quick() -> None:
    """Verify routing skips to synthesizer when quick is True."""
    assert _route_after_modeler({"quick": True}) == "synthesizer"


async def test_pipeline_executes_all_nodes_full_mode() -> None:
    """Verify the full pipeline calls all 6 nodes when quick=False."""
    mock_research_result: dict[str, Any] = {
        "raw_data": {"ticker": "TEST", "revenue": 1000},
    }
    mock_modeler_result: dict[str, Any] = {
        "model_yaml": "test yaml",
        "forge_results": {"outputs.margin": 0.5},
    }
    mock_risk_result: dict[str, Any] = {
        "risk_analysis": {"monte_carlo": {}, "tornado": {}, "break_even": {}},
    }
    mock_scenario_result: dict[str, Any] = {
        "scenario_analysis": {"scenarios": [], "expected_values": {}},
    }
    mock_synth_result: dict[str, Any] = {
        "brief": "Test brief.",
    }

    mock_retriever_result: dict[str, Any] = {
        "historical_context": [],
    }

    with (
        patch(
            "sentinel.graph.pipeline.research_node",
            new_callable=AsyncMock,
            return_value=mock_research_result,
        ) as mock_research,
        patch(
            "sentinel.graph.pipeline.retriever_node",
            new_callable=AsyncMock,
            return_value=mock_retriever_result,
        ) as mock_retriever,
        patch(
            "sentinel.graph.pipeline.modeler_node",
            new_callable=AsyncMock,
            return_value=mock_modeler_result,
        ) as mock_modeler,
        patch(
            "sentinel.graph.pipeline.risk_analyst_node",
            new_callable=AsyncMock,
            return_value=mock_risk_result,
        ) as mock_risk,
        patch(
            "sentinel.graph.pipeline.scenario_planner_node",
            new_callable=AsyncMock,
            return_value=mock_scenario_result,
        ) as mock_scenario,
        patch(
            "sentinel.graph.pipeline.synthesizer_node",
            new_callable=AsyncMock,
            return_value=mock_synth_result,
        ) as mock_synth,
    ):
        compiled = compile_graph()
        result = await compiled.ainvoke({"ticker": "TEST"})

    mock_research.assert_called_once()
    mock_retriever.assert_called_once()
    mock_modeler.assert_called_once()
    mock_risk.assert_called_once()
    mock_scenario.assert_called_once()
    mock_synth.assert_called_once()

    assert result["brief"] == "Test brief."
    assert result["raw_data"]["revenue"] == EXPECTED_REVENUE


async def test_pipeline_skips_risk_and_scenario_in_quick_mode() -> None:
    """Verify quick=True skips risk_analyst and scenario_planner."""
    mock_research_result: dict[str, Any] = {
        "raw_data": {"ticker": "TEST", "revenue": 1000},
    }
    mock_modeler_result: dict[str, Any] = {
        "model_yaml": "test yaml",
        "forge_results": {"outputs.margin": 0.5},
    }
    mock_synth_result: dict[str, Any] = {
        "brief": "Quick brief.",
    }

    with (
        patch(
            "sentinel.graph.pipeline.research_node",
            new_callable=AsyncMock,
            return_value=mock_research_result,
        ),
        patch(
            "sentinel.graph.pipeline.retriever_node",
            new_callable=AsyncMock,
            return_value={"historical_context": []},
        ),
        patch(
            "sentinel.graph.pipeline.modeler_node",
            new_callable=AsyncMock,
            return_value=mock_modeler_result,
        ),
        patch(
            "sentinel.graph.pipeline.risk_analyst_node",
            new_callable=AsyncMock,
            return_value={},
        ) as mock_risk,
        patch(
            "sentinel.graph.pipeline.scenario_planner_node",
            new_callable=AsyncMock,
            return_value={},
        ) as mock_scenario,
        patch(
            "sentinel.graph.pipeline.synthesizer_node",
            new_callable=AsyncMock,
            return_value=mock_synth_result,
        ),
    ):
        compiled = compile_graph()
        result = await compiled.ainvoke({"ticker": "TEST", "quick": True})

    mock_risk.assert_not_called()
    mock_scenario.assert_not_called()
    assert result["brief"] == "Quick brief."


def test_compile_graph_accepts_checkpointer() -> None:
    """Verify compile_graph accepts a checkpointer argument."""
    mock_checkpointer = MagicMock(spec=BaseCheckpointSaver)
    compiled = compile_graph(checkpointer=mock_checkpointer)
    assert hasattr(compiled, "ainvoke")


def test_compile_graph_defaults_to_no_checkpointer() -> None:
    """Verify compile_graph works without a checkpointer (default None)."""
    compiled = compile_graph()
    assert hasattr(compiled, "ainvoke")
