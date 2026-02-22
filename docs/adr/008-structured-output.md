# ADR-008: Structured Output Directory

**Status:** Accepted
**Date:** 2026-02-22

## Context

Pipeline results are printed to stdout and discarded after each run. Analysts need persistent artifacts for review, comparison across runs, and audit trails. A structured, predictable layout makes it easy to script post-processing and diff successive analyses for the same ticker.

## Decision

Each pipeline run writes its artifacts to a per-ticker, timestamped directory under `output/`:

```text
output/{TICKER}/{YYYYMMDD-HHMMSS}/
    brief.md
    raw_data.json
    model.yaml
    forge_results.json
    risk_analysis.json      (full mode only)
    scenario_analysis.json  (full mode only)
```

Core files (brief, raw data, model YAML, forge results) are always written. Risk and scenario analysis files are written only when the pipeline runs in full mode and the agents succeed without errors.

Timestamps use UTC to avoid timezone ambiguity across environments.

## Consequences

- `output/` is added to `.gitignore` so run artifacts stay local
- Each run is preserved independently; no overwriting of previous results
- The writer accepts a plain `dict[str, Any]` to avoid tight coupling to `SentinelState`
- Callers can override the output directory for testing or custom workflows
