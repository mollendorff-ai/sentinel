# ADR-010: HITL Design — interrupt_before + Checkpointer as MCP-Compatible Pause/Resume

**Status:** Accepted
**Date:** 2026-02-25

## Context

v0.7.0 adds a human approval gate before the Synthesizer. The analyst reviews computed
financials, risk ranges, and scenario outcomes before the brief is generated. Rejection
injects feedback into state; the Synthesizer reruns with that context.

The mechanism must work for the CLI today and for a future MCP server surface (Option A:
two-tool split) without requiring a refactor.

## Decision

`interrupt_before=["synthesizer"]` on `compile_graph()` + SQLite checkpointer pauses the
graph before the Synthesizer node, persists the full pipeline state to disk, and allows
resumption via a second `astream(None, config=same_config)` call.

This is opt-in via the `--hitl` CLI flag. Default behavior is unchanged.

### Approval flow

1. CLI runs `graph.astream(input, config, stream_mode="updates")` — graph halts at the
   interrupt.
2. `graph.get_state(config)` returns a `StateSnapshot`; `.next` contains `"synthesizer"`.
3. `show_draft_summary(snapshot.values)` prints key financials to the terminal.
4. `prompt_approval()` prompts: `Generate brief? [A]pprove / [R]eject + feedback: `
   - Empty / "a" / "A" → approve; resume immediately.
   - Anything else → that text becomes `analyst_feedback`; injected via `aupdate_state`
     before resuming.
5. `graph.astream(None, config=same_config)` resumes from the interrupt point.

### Analyst feedback

Rejection with non-empty input injects `analyst_feedback: str` into state via
`graph.aupdate_state(config, {"analyst_feedback": feedback})`. The Synthesizer prompt
includes an "ANALYST FEEDBACK" section when this field is non-empty.

### MCP bridge (Option A, future)

A future `sentinel_analyze` MCP tool runs the graph to the interrupt point and returns
the draft state dict + `thread_id`. `sentinel_resume(thread_id, approved, feedback)` calls
`aupdate_state` if feedback present, then resumes with `astream(None, config)`. The CLI
approval loop is the exact same mechanism — no refactoring required.

## Consequences

- HITL is opt-in (`--hitl` flag). Default pipeline behavior is unchanged.
- `interrupt_before` requires a checkpointer — SQLite checkpointer (ADR-007) is already
  required for HITL mode; without one, `interrupt_before` is silently ignored.
- `compile_graph()` gains `interrupt_before: list[str] | None = None` keyword parameter.
- `SentinelState` gains `analyst_feedback: str` field.
- The CLI migrates from `ainvoke` to `astream` + `get_state` to support streaming and
  HITL in a unified code path.
- Real-time agent progress (streaming) is a free by-product of the `astream` migration.
