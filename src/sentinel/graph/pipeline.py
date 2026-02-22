"""LangGraph pipeline — wires Research → Modeler → Synthesizer."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from sentinel.agents.modeler import modeler_node
from sentinel.agents.research import research_node
from sentinel.agents.synthesizer import synthesizer_node
from sentinel.graph.state import SentinelState


def build_graph() -> StateGraph:
    """Construct the Sentinel earnings-analysis graph (uncompiled).

    Returns
    -------
    StateGraph
        The graph builder, ready to be compiled.

    """
    graph = StateGraph(SentinelState)

    graph.add_node("research", research_node)
    graph.add_node("modeler", modeler_node)
    graph.add_node("synthesizer", synthesizer_node)

    graph.add_edge(START, "research")
    graph.add_edge("research", "modeler")
    graph.add_edge("modeler", "synthesizer")
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
