# Changelog

All notable changes to Sentinel are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/).

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
