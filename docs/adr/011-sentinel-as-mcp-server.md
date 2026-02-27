# ADR-011: Sentinel as MCP Server — Two-Tool Design

**Status:** Accepted
**Date:** 2026-02-26

## Context

Sentinel v0.7.0 introduced a human-in-the-loop approval gate via `interrupt_before` + SQLite
checkpointer (ADR-010). The pause/resume mechanism was explicitly designed to bridge to a future
MCP server surface. The Mollendorff ecosystem already follows the MCP pattern: Forge exposes a
20-tool financial engine, Ref provides headless-Chrome fetch — both over stdio. Exposing Sentinel
as an MCP server is the natural next step, allowing any MCP-capable client (Claude Desktop, other
LLM agents) to trigger and approve equity analysis runs.

## Decision

Expose Sentinel as a two-tool MCP server: `sentinel_analyze` and `sentinel_resume`.

### Tool 1: `sentinel_analyze`

Runs the full pipeline to the `interrupt_before=["synthesizer"]` point and returns:

- `thread_id` — the LangGraph checkpoint thread ID for resumption
- `draft` — the pre-synthesizer state snapshot (key financials, risk ranges, scenario outcomes)

The caller inspects the draft and decides whether to approve or reject.

### Tool 2: `sentinel_resume`

Accepts `thread_id`, `approved: bool`, and optional `feedback: str`. On approval, resumes the
graph via `astream(None, config)` and returns the final brief. On rejection, injects
`analyst_feedback` into state via `aupdate_state` before resuming, producing a revised brief
that incorporates the feedback.

### SDK

`mcp.server.fastmcp.FastMCP` from the `mcp` package (already a dependency at >=1.26.0). No new
runtime dependency is required.

### Transport

stdio — consistent with Forge and Ref. The server is invoked as:

```
python -m sentinel mcp
```

This adds a `mcp` subcommand to the existing CLI entry point in `__main__.py`.

## Alternatives Considered

### Single blocking tool

A single `sentinel_analyze` tool that runs the entire pipeline end-to-end would be simpler, but
eliminates the HITL gate entirely. The caller cannot inspect or reject the draft before the
Synthesizer runs. Long-running analysis also risks transport-level timeouts on slow tickers.

### `ctx.elicit()` (MCP elicitation)

The MCP spec's `elicit` mechanism allows a tool to pause and request structured input from the
client mid-execution. This was rejected for several reasons:

- **Client support:** Elicitation requires explicit client-side support; many MCP hosts do not
  implement it yet.
- **Timeout risk:** The tool blocks for the duration of the human review. Long deliberation
  windows risk transport-level timeouts.
- **Expressiveness:** The two-tool design gives the caller full programmatic control — it can
  inspect the draft, run additional analysis, or delegate the approval decision to another agent.
- **LangGraph showcase:** The two-tool split directly demonstrates LangGraph's checkpoint-based
  pause/resume, which is architecturally more interesting than hiding it behind an elicitation
  callback.

## Consequences

- Callers must manage a two-step flow: call `sentinel_analyze`, inspect the draft, then call
  `sentinel_resume` with the returned `thread_id`.
- `thread_id` is the sole handle linking the two calls; callers are responsible for passing it
  through.
- Both tools must use `interrupt_before=["synthesizer"]` on `compile_graph()` — the same
  parameter the CLI already passes in HITL mode.
- The SQLite checkpointer path must be consistent between the two tool invocations within a
  session. The server initialises the checkpointer once at startup and shares it across calls.
- The `mcp` subcommand reuses all existing pipeline, checkpointer, and streaming infrastructure.
  No graph or agent changes are required.
