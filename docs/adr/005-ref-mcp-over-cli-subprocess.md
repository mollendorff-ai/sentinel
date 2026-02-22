# ADR-005: Ref MCP over CLI subprocess for web data ingestion

**Status:** Accepted
**Date:** 2026-02-22

## Context

Sentinel agents need to call Ref for web data ingestion (fetching earnings releases, PDFs, link checking, etc.). Ref offers two integration paths:

1. **MCP server** — `ref mcp` runs a JSON-RPC server over stdio, exposing 6 tools with auto-discoverable schemas.
2. **CLI subprocess** — invoke `ref fetch URL`, `ref pdf URL`, etc. as individual shell commands, parsing stdout.

## Decision

MCP as the primary integration method, consistent with Forge (ADR-002).

## Rationale

**Persistent browser pool.** MCP maintains a long-lived Ref process with a warm headless Chrome pool. CLI subprocess spawns a new browser per call — unnecessary overhead when the Research agent may fetch dozens of URLs per analysis.

**Batch fetching.** The MCP client can issue multiple `ref_fetch` calls concurrently over the same connection. CLI subprocess requires sequential spawning or manual parallelism.

**Schema auto-discovery.** `langchain-mcp-adapters` connects to `ref mcp` via `MultiServerMCPClient` (stdio transport) and auto-discovers all 6 tools as LangChain `BaseTool` instances. If Ref adds or changes tools, the MCP client picks them up automatically. CLI subprocess wrappers require manual updates.

**Consistency.** Forge already uses MCP (ADR-002). Using the same integration pattern for both tools simplifies the codebase — one `MultiServerMCPClient` session manages both Forge and Ref connections.

## MCP tools (6)

`ref_fetch`, `ref_pdf`, `ref_check_links`, `ref_scan`, `ref_verify_refs`, `ref_refresh_data`

## Consequences

- Primary dependency: `langchain-mcp-adapters` (stdio transport, shared with Forge)
- Minimum Ref version: v1.5.0+ (MCP server support)
- 6 tools via MCP, no CLI subprocess fallback needed
- Removes `sentinel.tools.ref_fetch` CLI wrapper from v0.1.0
