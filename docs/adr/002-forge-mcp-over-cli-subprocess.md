# ADR-002: Forge MCP over CLI subprocess for core tools

**Status:** Accepted
**Date:** 2026-02-22

## Context

Sentinel agents need to call Forge for financial calculations (validate, calculate, sensitivity, etc.). Forge offers two integration paths:

1. **MCP server** — `forge mcp` runs a JSON-RPC server over stdio, exposing 20 tools with auto-discoverable schemas.
2. **CLI subprocess** — invoke `forge calculate model.yaml`, `forge validate model.yaml`, etc. as individual shell commands, parsing stdout.

## Decision

MCP as the integration method for all Forge tools.

## Rationale

**Native LangChain integration.** `langchain-mcp-adapters` connects to `forge mcp` via `MultiServerMCPClient` (stdio transport) and auto-discovers all 20 tools as LangChain `BaseTool` instances. Agents call Forge tools directly — no manual schema definitions, no stdout parsing.

**Single persistent connection.** MCP maintains one long-lived process. CLI subprocess spawns a new process per call — unnecessary overhead when an agent may invoke dozens of Forge calls per analysis.

**Schema auto-discovery.** If Forge adds or changes tools, the MCP client picks them up automatically. CLI subprocess wrappers require manual updates.

**Structured I/O.** MCP communicates via JSON-RPC with typed input schemas and structured responses. CLI output is human-readable text that requires parsing.

## MCP tools (20)

`forge_validate`, `forge_calculate`, `forge_audit`, `forge_export`, `forge_import`, `forge_sensitivity`, `forge_goal_seek`, `forge_break_even`, `forge_variance`, `forge_compare`, `forge_simulate`, `forge_scenarios`, `forge_decision_tree`, `forge_real_options`, `forge_tornado`, `forge_bootstrap`, `forge_bayesian`, `forge_schema`, `forge_functions`, `forge_examples`

All tools operate on **file paths**, not inline YAML content. Agents must write model YAML to disk before calling Forge.

## Consequences

- Primary dependency: `langchain-mcp-adapters` (stdio transport)
- Minimum Forge version: v0.3.0+ (MCP server support)
- All 20 tools via MCP; no CLI subprocess needed
- All model YAML is written to disk; Forge reads/writes files directly
