"""LangGraph pipeline — wires the 5-agent earnings-analysis graph."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from sentinel.agents.modeler import modeler_node
from sentinel.agents.research import research_node
from sentinel.agents.risk_analyst import risk_analyst_node
from sentinel.agents.scenario_planner import scenario_planner_node
from sentinel.agents.synthesizer import synthesizer_node
from sentinel.graph.state import SentinelState


def _route_after_modeler(state: dict[str, Any]) -> str:
    """Route to Risk Analyst or skip to Synthesizer based on quick flag."""
    if state.get("quick", False):
        return "synthesizer"
    return "risk_analyst"


def build_graph() -> StateGraph:
    """Construct the Sentinel earnings-analysis graph (uncompiled).

    Graph topology::

        START → research → modeler ──┬──→ risk_analyst → scenario_planner ──┬──→ synthesizer → END
                                     └─── (quick=True) ────────────────────┘

    Returns
    -------
    StateGraph
        The graph builder, ready to be compiled.

    """
    graph = StateGraph(SentinelState)

    graph.add_node("research", research_node)
    graph.add_node("modeler", modeler_node)
    graph.add_node("risk_analyst", risk_analyst_node)
    graph.add_node("scenario_planner", scenario_planner_node)
    graph.add_node("synthesizer", synthesizer_node)

    graph.add_edge(START, "research")
    graph.add_edge("research", "modeler")
    graph.add_conditional_edges(
        "modeler",
        _route_after_modeler,
        {"risk_analyst": "risk_analyst", "synthesizer": "synthesizer"},
    )
    graph.add_edge("risk_analyst", "scenario_planner")
    graph.add_edge("scenario_planner", "synthesizer")
    graph.add_edge("synthesizer", END)

    return graph


def compile_graph() -> StateGraph:
    """Build and compile the pipeline, ready to invoke.

    Returns
    -------
    CompiledStateGraph
        Executable graph supporting ``invoke`` / ``ainvoke``.

    """
    return build_graph().compile()
