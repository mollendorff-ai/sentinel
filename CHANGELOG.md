# Changelog

All notable changes to Sentinel are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/).

## [0.8.0] - 2026-02-27

Sentinel as MCP server: `sentinel_analyze` + `sentinel_resume` tools.

### Added

- **MCP server** (`sentinel.mcp.server`): `FastMCP("sentinel")` on stdio transport; launch with `sentinel mcp` or `python -m sentinel mcp`
- **`sentinel_analyze` tool**: runs the full pipeline (Research → Retriever → Modeler → [Risk → Scenario] → interrupt) with `interrupt_before=["synthesizer"]`; returns `thread_id`, `ticker`, `period`, `draft` (condensed financials snapshot), and `status`
- **`sentinel_resume` tool**: reloads the SQLite checkpoint by `thread_id`; injects analyst feedback on `reject`; resumes the graph to produce the final brief; calls `write_run_output()` and Qdrant ingest; returns `brief`, `status`, `run_dir`
- **ADR-011:** Sentinel as MCP server — two-tool split design (`sentinel_analyze` + `sentinel_resume`); `ctx.elicit()` considered and rejected (client support gaps, timeout risk, weaker LangGraph showcase); stdio transport; `mcp.server.fastmcp.FastMCP`
- **`sentinel` script entry point** in `pyproject.toml` (`[project.scripts]`): `sentinel = "sentinel.__main__:main"`
- `mcp>=1.26` runtime dependency

### Changed

- **CLI** (`sentinel.__main__`): `mcp` subcommand dispatched before argparse; `_maybe_ingest()` helper extracted from `_run_all()` to reduce complexity (C901); VERSION = "0.8.0"
- **README**: MCP Server section with tool table, quick-start JSON config, and 3-step usage guide; C4 diagram updated — Sentinel shown as both MCP consumer and server, new MCP Clients system added
- **Unit tests:** 207 tests at 100% coverage (was 181); 10 integration tests (was 8)

## [0.7.0] - 2026-02-26

Human-in-the-loop approval gate + real-time streaming.

### Added

- **HITL approval gate** (`--hitl` flag): `interrupt_before=["synthesizer"]` pauses the pipeline before the Synthesizer; analyst reviews computed financials, risk ranges, and scenario outcomes before the brief is generated
- **Approval module** (`sentinel.approval`): `show_draft_summary()` prints a condensed analysis (revenue, margins, EPS, risk P50, scenario one-liner) to the terminal; `prompt_approval()` reads analyst decision — empty/`a`/`A` approves, anything else rejects with feedback text
- **Rejection loop**: analyst feedback injected into `SentinelState.analyst_feedback`; `graph.aupdate_state()` writes it before resuming; Synthesizer prompt includes an "ANALYST FEEDBACK" section when set
- **Real-time streaming**: CLI migrated from `ainvoke` to `astream(stream_mode="updates")`; each completed agent node prints `  [Agent Name]` to the terminal as it finishes
- **`_AGENT_LABELS`** map in CLI: human-readable labels for all 6 node names
- **ADR-010:** HITL design — `interrupt_before` + SQLite checkpointer as MCP-compatible pause/resume (accepted); documents Option A two-tool MCP bridge for future implementation
- `analyst_feedback: str` field added to `SentinelState`

### Changed

- **`compile_graph()`**: new keyword-only parameter `interrupt_before: list[str] | None = None`; passed through to `build_graph().compile()`
- **Synthesizer agent**: reads `analyst_feedback` from state; injects "ANALYST FEEDBACK" section into `SYNTHESIS_PROMPT` when non-empty
- **CLI** (`sentinel.__main__`): `--hitl` flag parsing; `astream` + `get_state` replaces `ainvoke`; VERSION = "0.7.0"
- **Unit tests:** 181 tests at 100% coverage (was 156)

## [0.6.0] - 2026-02-25

RAG with Qdrant — historical earnings for trend analysis.

### Added

- **Qdrant RAG layer** (`sentinel.rag.store`): `create_store()` factory opens local on-disk Qdrant at `.sentinel/qdrant/`; `ingest()` upserts a quarter's earnings using stable `uuid5(ticker:period)` point IDs (idempotent); `retrieve()` queries the top-4 most relevant past quarters via fastembed semantic search, excluding the current period
- **Retriever agent** (`sentinel.agents.retriever`): new LangGraph node between Research and Modeler; queries Qdrant for historical quarters; graceful degradation — returns `{"historical_context": []}` on first run or Qdrant error, never blocks the pipeline
- **Historical Trend Analysis section** in Synthesizer brief: when `historical_context` is non-empty the Synthesizer prompt includes past quarters' financials and produces a trend section covering revenue trajectory, margin expansion/compression, and EPS progression
- **Post-run ingest** in CLI (`__main__.py`): after each successful pipeline run, `raw_data` is ingested into Qdrant so subsequent runs for the same ticker accumulate historical context
- **ADR-009:** Qdrant RAG over local fastembed for zero-config historical earnings retrieval (accepted)
- **`SENTINEL_QDRANT_PATH`** env var: configures Qdrant persistence path (default: `.sentinel/qdrant/`)
- `qdrant-client[fastembed]>=1.9` runtime dependency (embedding model downloaded once on first use)

### Changed

- **Graph topology**: 5-node pipeline extended to 6 nodes — `research → retriever → modeler → [risk_analyst → scenario_planner] → synthesizer`
- **`SentinelState`**: added `historical_context: list[dict[str, Any]]` field
- **Synthesizer word range**: expands to 400–700 words when historical context is present (alongside existing risk/scenario expansion)
- **Version**: bumped to 0.6.0

## [0.5.0] - 2026-02-22

Showcase: C4 architecture diagram, dynamic badges, README rewrite.

### Added

- **C4 Level 2 container diagram** (Mermaid `C4Container`): 5 agents, Forge/Ref MCP servers, LLM provider, LangSmith, SQLite checkpointer; renders natively on GitHub
- **Dynamic CI badges**: coverage percentage and test count updated on every push to main via `schneegans/dynamic-badges-action` + GitHub Gist
- **Ecosystem section** in README: Sentinel, Forge, and Ref framed as a unified MCP-connected platform
- **Roadmap table** in README: version history with planned v0.6.0 (RAG/Qdrant) and v0.7.0 (human-in-the-loop)

### Changed

- **README** rewritten: C4 diagram replaces flow chart, ecosystem section, roadmap table, Forge/Ref described as "our MCP servers", stack table updated
- **CI workflow** (`.github/workflows/ci.yml`): added `coverage` job (metrics extraction) and `badges` job (gist update, main push only)
- **GitHub org profile** (`mollendorff-ai/.github`): Sentinel/Forge/Ref descriptions updated to highlight MCP ecosystem

## [0.4.0] - 2026-02-22

Persistence + observability + developer experience.

### Added

- **SQLite checkpointer** (`sentinel.checkpointer`): `create_checkpointer()` factory returns `SqliteSaver` context manager; persists pipeline state to `.sentinel/checkpoints.db`; enables resumable runs via `thread_id`
- **Structured output** (`sentinel.output`): `write_run_output()` saves all pipeline artifacts to `output/{TICKER}/{YYYYMMDD-HHMMSS}/` — brief.md, raw_data.json, model.yaml, forge_results.json, risk/scenario JSON (full mode)
- **LangSmith traces**: per-ticker `RunnableConfig` with `run_name`, `tags` (ticker, mode, version), and `metadata` (provider, model); traces filterable in LangSmith UI
- **Multi-ticker batch mode**: `python -m sentinel AAPL MSFT GOOG` runs sequential analysis with per-ticker output and checkpointing
- **Makefile**: setup, lint, test, check, demo, demo-quick, clean, help targets
- **ADR-007:** SQLite checkpointer over MemorySaver for persistence (accepted)
- **ADR-008:** Structured output directory design (accepted)

### Changed

- **Error handling**: all `await tool.ainvoke()` and `await llm.ainvoke()` calls wrapped in try/except across all 5 agents; MCP tool failures and LLM errors return graceful error dicts instead of crashing the graph; risk/scenario tools wrapped independently for partial results
- **Pipeline** (`sentinel.graph.pipeline`): `compile_graph()` accepts optional `checkpointer` parameter
- **CLI** (`sentinel.__main__`): multi-ticker support, checkpointer integration, LangSmith config, output writing, version v0.4.0
- **Unit tests:** 126 tests at 100% coverage (was 77)

## [0.3.0] - 2026-02-22

Risk + scenarios: full 5-agent pipeline with conditional routing.

### Added

- **Risk Analyst agent** (`sentinel.agents.risk_analyst`): augments Forge YAML with `monte_carlo` + `tornado` sections via Claude; runs `forge_simulate` (Monte Carlo P10/P50/P90), `forge_tornado` (sensitivity), `forge_break_even`; self-correction loop for validation
- **Scenario Planner agent** (`sentinel.agents.scenario_planner`): augments YAML with `scenarios` section (Bull/Base/Bear); runs `forge_scenarios`, `forge_compare`, `forge_break_even`; builds on Risk Analyst's augmented YAML when available
- **Conditional routing**: `--quick` CLI flag skips Risk Analyst + Scenario Planner via LangGraph `add_conditional_edges`
- **ADR-006:** Five-Agent Pipeline with Conditional Routing (accepted)
- **Test fixture:** `risk_model.yaml` — Forge v5.0.0 model with monte_carlo, tornado, and scenarios sections

### Changed

- **Pipeline** (`sentinel.graph.pipeline`): 5 nodes with conditional edge after Modeler; `_route_after_modeler` checks `quick` flag
- **State schema** (`sentinel.graph.state`): added `quick`, `risk_analysis`, `scenario_analysis` fields
- **Synthesizer agent** (`sentinel.agents.synthesizer`): conditionally injects risk + scenario data; adds Risk Profile and Scenario Comparison sections; word range 400-700 in full mode
- **CLI** (`sentinel.__main__`): `--quick` flag, mode display (full/quick), version v0.3.0
- **LLM default** (`sentinel.llm`): Anthropic default model switched from `claude-sonnet-4-20250514` to `claude-opus-4-6`
- **Unit tests:** 77 tests at 100% coverage (was 48)

## [0.2.2] - 2026-02-22

Forge MCP tool list updated from 10 to 20. No more CLI subprocess fallback.

### Changed

- **Forge MCP client** (`sentinel.tools.forge_mcp`): FORGE_TOOL_NAMES expanded from 10 to 20 tools; 7 new analysis engines (simulate, scenarios, decision_tree, real_options, tornado, bootstrap, bayesian) and 3 discovery tools (schema, functions, examples)
- **Modeler agent** (`sentinel.agents.modeler`): validation and calculation result parsing updated for Forge structured JSON responses (`tables_valid`/`scalars_valid` for validation, `scalars` dict for calculation)
- **ADR-002** updated: CLI subprocess fallback removed — all Forge tools now available via MCP
- **Roadmap** updated: v0.3.0 Risk Analyst and Scenario Planner agents will use forge_simulate, forge_tornado, forge_scenarios via MCP directly

## [0.2.1] - 2026-02-22

Ref MCP migration: subprocess CLI wrapper replaced with native MCP client.

### Added

- **ADR-005:** Ref MCP over CLI subprocess for web data ingestion (accepted)

### Changed

- **Ref MCP client** (`sentinel.tools.ref_mcp`): connects to `ref mcp` via langchain-mcp-adapters (stdio transport); auto-discovers all 6 tools (fetch, pdf, check_links, scan, verify_refs, refresh_data)
- **Research agent** batches URLs via MCP connection instead of sequential subprocess calls

### Removed

- **Ref CLI wrapper** (`sentinel.tools.ref_fetch`): replaced by Ref MCP client

## [0.2.0] - 2026-02-22

Core 3-agent LangGraph pipeline: one ticker in, one executive brief out.

### Added

- **LangGraph pipeline** (`sentinel.graph`): StateGraph wiring Research -> Modeler -> Synthesizer; typed state schema (`SentinelState`); compiled graph with `ainvoke` support
- **Research agent** (`sentinel.agents.research`): fetches earnings data via `ref fetch`, extracts structured financials (revenue, margins, growth) via Claude; handles multiple URL sources and non-JSON Claude responses
- **Modeler agent** (`sentinel.agents.modeler`): generates Forge v5.0.0 YAML models from extracted data; self-correction loop (validate -> fix -> retry up to 3 times); calculates via `forge_calculate`
- **Synthesizer agent** (`sentinel.agents.synthesizer`): produces 300-500 word executive briefs from Forge calculation results; every number traces to deterministic Forge output
- **CLI entry point:** `python -m sentinel AAPL` runs the full pipeline and prints the brief
- **GitHub Actions CI:** lint (ruff format + check ALL), test matrix (Python 3.11/3.12), markdownlint; integration tests marked and skipped in CI
- **Multi-provider LLM** (`sentinel.llm`): factory function `get_llm()` configurable via `SENTINEL_LLM_PROVIDER` and `SENTINEL_LLM_MODEL` env vars; supports Anthropic (default), OpenAI, Google Gemini, Groq; optional extras in pyproject.toml (`pip install sentinel[google]`)
- **ADR-003:** Custom StateGraph over deprecated `create_react_agent` (accepted)
- **ADR-004:** Multi-provider LLM support via env-var factory (accepted)
- **README:** badges (CI, coverage, Python, license) and status section
- **Unit tests:** 51 tests at 100% coverage; integration tests marked separately for CI

## [0.1.0] - 2026-02-22

Project scaffold, Forge MCP integration, and Ref CLI wrapper.

### Added

- **Project scaffold:** pyproject.toml with langgraph, langchain-anthropic, langchain-mcp-adapters, langsmith dependencies; Python 3.11+ editable install via uv/pip
- **LangSmith tracing:** .env.example with LANGCHAIN_TRACING_V2, LANGSMITH_API_KEY, LANGSMITH_PROJECT
- **Forge MCP client** (`sentinel.tools.forge_mcp`): connects to `forge mcp` via langchain-mcp-adapters (stdio transport); auto-discovers all 10 tools (validate, calculate, audit, export, import, sensitivity, goal_seek, break_even, variance, compare); provides both ephemeral (`get_forge_tools()`) and persistent (`forge_session()`) session APIs
- **Ref CLI wrapper** (`sentinel.tools.ref_fetch`): LangChain BaseTool wrapping `ref fetch` via async subprocess; returns structured JSON (title, sections, links)
- **Smoke tests:** 6 passing — Forge tool discovery (both APIs), validate, calculate (dry run), Ref fetch (structured JSON, error handling)
- **ADR-001:** Python over TypeScript for LangGraph orchestration (accepted)
- **ADR-002:** Forge MCP over CLI subprocess for core tools (accepted)
- **Test fixture:** simple_model.yaml — minimal Forge v5.0.0 model for smoke tests
