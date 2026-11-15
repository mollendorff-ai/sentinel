# ADR-014: Check Forge's results against the filing, and keep only what the demo uses

**Status:** Accepted
**Date:** 2026-11-15
**Amends:** [ADR-012](012-sentinel-as-forge-demo.md), the sentence that kept `--hitl` and the MCP server, and [ADR-013](013-run-in-a-chat.md), decision 2
**Supersedes:** [ADR-007](007-sqlite-checkpointer.md), [ADR-010](010-hitl-interrupt-before-synthesizer.md), [ADR-011](011-sentinel-as-mcp-server.md)

## Context

An independent evaluation on 2026-11-15 (grade B-) found that a model with a wrong formula passed every check. With `operating_income = gross_profit + operating_expenses`, Forge validated and calculated the model (74,009), the run exited 0, and the summary said "All match expected.yaml", though the filing prints 35,631. Two checks existed and neither looked at the formulas: `expected.yaml` checks what the LLM read, and Forge checks that each result comes from a formula it calculated. Forge cannot know whether the formula is the right one. ADR-013's claim that "the expected-figure check and Forge still catch a misread or a wrong sum" was true of a misread and false of a wrong sum.

The evaluation also found that the Modeler's prompt contained the finished model, every formula included, so "the AI writes the Forge model" meant "the AI copies a template"; that features the demo does not use (the `--hitl` gate, the MCP server, the SQLite checkpointer) were kept against the repository's own rule that "a feature that does not [serve the demonstration] is removed"; and that a failed run was written into `runs/`, which is committed and read as history.

## Decision

1. **A third check: Forge's results against the filing.** `expected.yaml` gains `results:`, the subtotals the filing prints that Forge must calculate (for Apple, gross profit 54,820 and operating income 35,631). After Forge calculates, the Modeler compares them, and a difference fails the run before any brief is written. An input without `results:` is refused. A model whose output formula holds a number (`=35631`) also fails, so a result cannot be typed in to pass the check.
2. **The Modeler writes the formulas.** Its prompt names the four inputs and the five outputs and what each output means, gives Forge's format rules, and gives no formula. It sees the four input figures, not the subtotals the LLM extracted.
3. **What the demo does not use is removed:** the `--hitl` approval gate (ADR-010), the MCP server (ADR-011) and the SQLite checkpointer (ADR-007). A chat-mode run starts again from the beginning each time an answer is written, so checkpoints between runs serve nothing. Multi-provider support stays: it is how a run uses an API instead of a chat.
4. **A failed run is written to `.sentinel/failed/`**, which git ignores, so `runs/` holds only runs that passed every check.

## Consequences

- Three checks, three questions: `expected.yaml`'s figures check the reading, Forge checks the arithmetic, and the filing's subtotals check the formulas. The margins are ratios of checked figures and are not compared with the filing.
- The check is only as good as `results:`: a person confirms those figures, as for `figures:`.
- A run made before 0.9.0 has no `filing_check` in `forge_results.json`; its summary says so.
- Prompts changed, so answers saved for the Modeler's old prompt are not reused (prompt files are named by a hash of their text, ADR-013).
- About 1,000 lines of code and tests are gone, and two dependencies (`langgraph-checkpoint-sqlite`, and `mcp` as a direct dependency; `langchain-mcp-adapters` still brings it for the Forge client).
