# ADR-009: Qdrant RAG for Historical Earnings Trend Analysis

**Status:** Accepted
**Date:** 2026-02-25

## Context

The Sentinel pipeline analyses a single quarter's earnings in isolation. An analyst reviewing
Apple Q1 2026 results wants to know whether revenue growth is accelerating or decelerating, whether
margins are expanding, and how the current EPS compares to the year-ago period. Without historical
context, the Synthesizer produces a snapshot brief with no trend dimension.

## Decision

Use `qdrant-client[fastembed]` with on-disk local persistence at `.sentinel/qdrant/`. The
high-level fastembed API (`client.add()` for ingest, `client.query()` for retrieval) eliminates
the need for a separate embedding API key: the `BAAI/bge-small-en-v1.5` model (384-dimension,
33 M parameters) is downloaded once from HuggingFace on first use and cached locally.

A new `retriever` graph node is inserted between `research` and `modeler`. It queries Qdrant
for the top 4 most relevant past quarters (excluding the current period) and writes
`historical_context: list[dict]` to the pipeline state. The `synthesizer` node reads this field
and injects a **Historical Trend Analysis** section into the brief when `historical_context` is
non-empty.

After each successful pipeline run, `__main__.py` ingests the current quarter's `raw_data` into
Qdrant so it is available for future runs.

## New Graph Topology

```
START → research → retriever → modeler ──┬──→ risk_analyst → scenario_planner ──┬──→ synthesizer → END
                                          └─── (quick=True) ────────────────────┘
```

## Deduplication

Point IDs are stable `uuid.uuid5(uuid.NAMESPACE_DNS, f"{ticker}:{period}")` values. Re-running
the pipeline for the same ticker and period is idempotent: Qdrant's `add()` with the same ID
overwrites the existing point.

## Graceful Degradation

- **First run:** Qdrant store is empty; `retrieve()` returns `[]`; `historical_context` is `[]`;
  the Synthesizer omits the trend section. The pipeline completes normally.
- **Qdrant unavailable:** `retriever_node` catches all exceptions and returns
  `{"historical_context": []}`. The pipeline never fails due to RAG.
- **Ingest failure at CLI level:** caught with a warning log; brief and output files still written.

## Persistence Path

Local persistence at `.sentinel/qdrant/` is configurable via `SENTINEL_QDRANT_PATH` env var.
The `.sentinel/` directory is already in `.gitignore` from ADR-007.

## Collection Auto-Creation

The Qdrant collection `"earnings"` is created automatically on the first `client.add()` call.
Fastembed manages vector dimensions internally for the configured model. We do **not** call
`client.create_collection()` manually, as this would conflict with fastembed's internal naming.

## Consequences

- Adds `qdrant-client[fastembed]>=1.9` as a runtime dependency (~130 MB for the embedding model
  on first download, cached in `~/.cache/fastembed/` thereafter)
- The `retriever` node increases the pipeline from 5 to 6 nodes; `quick=True` still routes
  through `retriever` since it precedes the Modeler routing decision
- Historical value builds over time: the first run of any ticker produces no trend section;
  subsequent runs enrich the brief progressively
- `SENTINEL_QDRANT_PATH` follows the `SENTINEL_LLM_PROVIDER` / `SENTINEL_LLM_MODEL` env var
  naming convention
- No external API key required; fully local embedding
