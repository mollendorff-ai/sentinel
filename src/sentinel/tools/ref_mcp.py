"""Ref MCP client — connects to Ref's 6 web-fetching tools via MCP."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools

logger = logging.getLogger(__name__)

REF_TOOL_NAMES = frozenset(
    {
        "ref_fetch",
        "ref_pdf",
        "ref_check_links",
        "ref_scan",
        "ref_verify_refs",
        "ref_refresh_data",
    },
)
"""All 6 tools exposed by ``ref mcp``."""

REF_CONNECTION = {
    "ref": {
        "command": "ref",
        "args": ["mcp"],
        "transport": "stdio",
    },
}


async def get_ref_tools() -> list[BaseTool]:
    """Return Ref tools with a new MCP session per tool call.

    Simple interface — each tool invocation spawns a fresh ``ref mcp`` process.
    For multiple calls in sequence, prefer :func:`ref_session` instead.

    Returns
    -------
    list[BaseTool]
        LangChain-compatible tools auto-discovered from Ref MCP.

    """
    client = MultiServerMCPClient(REF_CONNECTION)
    tools = await client.get_tools()
    _log_discovered(tools)
    return tools


@asynccontextmanager
async def ref_session() -> AsyncIterator[list[BaseTool]]:
    """Open a persistent Ref MCP session for multiple tool calls.

    Usage::

        async with ref_session() as tools:
            fetch = next(t for t in tools if t.name == "ref_fetch")
            result = await fetch.ainvoke({"urls": ["https://example.com"]})

    Yields
    ------
    list[BaseTool]
        LangChain-compatible tools bound to the session.

    """
    client = MultiServerMCPClient(REF_CONNECTION)
    async with client.session("ref") as session:
        tools = await load_mcp_tools(session)
        _log_discovered(tools)
        yield tools


def _log_discovered(tools: list[BaseTool]) -> None:
    """Log discovered tool names and warn about any missing tools."""
    discovered = {t.name for t in tools}
    missing = REF_TOOL_NAMES - discovered
    if missing:
        logger.warning("Expected Ref tools not found: %s", missing)
    logger.info("Ref MCP: %d tools discovered", len(tools))
