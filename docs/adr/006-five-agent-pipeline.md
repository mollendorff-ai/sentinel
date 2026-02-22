# ADR-006: Five-Agent Pipeline with Conditional Routing

**Status:** Accepted
**Date:** 2026-02-22

## Context

The v0.2.x pipeline is a linear 3-agent chain: Research -> Modeler -> Synthesizer. For v0.3.0, two new agents are required: Risk Analyst (Monte Carlo, tornado sensitivity) and Scenario Planner (Bull/Base/Bear scenarios). A `--quick` mode should skip these agents for fast deterministic-only analysis.

## Decision

Linear chain with one conditional edge after the Modeler node. The full pipeline is Research -> Modeler -> Risk Analyst -> Scenario Planner -> Synthesizer. In `--quick` mode, the Modeler routes directly to the Synthesizer, bypassing Risk Analyst and Scenario Planner.

Risk Analyst augments the Modeler YAML with `monte_carlo:` and `tornado:` sections. Scenario Planner builds on Risk Analyst output (or falls back to Modeler YAML) and adds a `scenarios:` section with Bull/Base/Bear cases. Both agents use the proven validate-fix-retry self-correction loop from the Modeler.

LLM generates augmented YAML because financial heuristics (distribution shapes, scenario ranges, sensitivity parameters) vary by company and sector. Static rules would not generalize.

## Routing

`add_conditional_edges` on the Modeler node checks `state["quick"]`:

- `True` -> Synthesizer (deterministic only)
- `False` -> Risk Analyst -> Scenario Planner -> Synthesizer (full analysis)

## Consequences

- Pipeline grows from 3 to 5 nodes; each agent is independently testable
- `--quick` provides a fast path for deterministic-only analysis
- YAML augmentation uses the validate-fix-retry loop (proven pattern from Modeler)
- State schema adds `risk_analysis`, `scenario_analysis`, and `quick` fields
- Synthesizer must incorporate risk and scenario data when present
