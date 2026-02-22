# ADR-007: SQLite Checkpointer for Pipeline Persistence

**Status:** Accepted
**Date:** 2026-02-22

## Context

The Sentinel CLI tool runs multi-step pipelines that can take significant time. If a run is interrupted (network timeout, user cancellation, process crash), all progress is lost because the default LangGraph in-memory saver does not persist state to disk. MemorySaver is unsuitable for a CLI tool where each invocation is a fresh process.

## Decision

Use `langgraph-checkpoint-sqlite` to persist pipeline state to a local SQLite database at `.sentinel/checkpoints.db`. A factory function `create_checkpointer()` returns a `SqliteSaver` context manager that the CLI entry point wraps around graph compilation. Each ticker analysis uses a unique `thread_id` so runs are isolated.

## Consequences

- `.sentinel/` directory is created automatically; should be git-ignored
- `SqliteSaver.from_conn_string` returns a context manager — callers must use `with`
- `compile_graph()` accepts an optional `checkpointer` parameter (defaults to `None` for backward compatibility and testing)
- `thread_id` scoped per ticker enables resumption and history
- Adds `langgraph-checkpoint-sqlite>=2.0` as a runtime dependency
