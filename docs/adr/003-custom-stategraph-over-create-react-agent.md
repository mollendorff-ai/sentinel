# ADR-003: Custom StateGraph over create_react_agent

**Status:** Accepted
**Date:** 2026-02-22

## Context

LangGraph provides two patterns for building agent workflows:

1. **`create_react_agent`** -- a high-level helper that wires an LLM to tools in a ReAct loop. The LLM decides which tool to call, observes the result, and repeats until done.
2. **Custom `StateGraph`** -- explicit graph definition with typed state, named nodes, and deterministic edges. Each node is an async function that receives state and returns partial updates.

As of LangGraph 1.0, `create_react_agent` is deprecated in the core package (moved to `langchain.agents`). Sentinel's installed version is LangGraph 1.0.9.

## Decision

Custom `StateGraph` with `TypedDict` state and async node functions. Each agent node calls `ChatAnthropic.ainvoke()` directly and invokes tools programmatically -- no LLM-driven tool-calling loop.

## Rationale

**Deprecation.** `create_react_agent` is no longer part of LangGraph core. Building on a deprecated API creates unnecessary migration risk.

**Programmatic tool control.** Sentinel agents need to decide *when* tools are called, not delegate that decision to the LLM. The Modeler agent runs a self-correction loop: generate YAML, call `forge_validate`, feed errors back to Claude, retry up to 3 times. This logic is explicit Python, not an emergent LLM behavior.

**Typed state contract.** `SentinelState(TypedDict, total=False)` defines a clear schema that all nodes share. Each node returns a partial dict -- the graph merges updates automatically. Type checkers catch mismatches at development time.

**Testability.** Each node is a standalone async function: `async def research_node(state: SentinelState) -> dict`. Tests mock Claude and Forge, call the node directly, and assert on the returned state. No graph machinery needed for unit tests.

**Deterministic flow.** The pipeline is linear (Research -> Modeler -> Synthesizer) with no LLM-driven routing decisions. Conditional edges (planned for v0.3.0's `--quick` flag) will be explicit Python functions, not LLM choices.

## Consequences

- More boilerplate than `create_react_agent` (explicit node functions, edge wiring)
- Full control over tool invocation order and retry logic
- No dependency on deprecated APIs
- Each node independently testable without graph compilation
- State schema serves as documentation of the inter-agent data contract
