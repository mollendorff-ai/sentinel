# Changelog

All notable changes to Sentinel are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/).

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
