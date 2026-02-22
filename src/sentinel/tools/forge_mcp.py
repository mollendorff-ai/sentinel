"""Forge MCP client — connects to Forge's 10 financial analysis tools via MCP."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools

logger = logging.getLogger(__name__)

FORGE_TOOL_NAMES = frozenset(
    {
        "forge_validate",
        "forge_calculate",
        "forge_audit",
        "forge_export",
        "forge_import",
        "forge_sensitivity",
        "forge_goal_seek",
        "forge_break_even",
        "forge_variance",
        "forge_compare",
    },
)
"""All 10 tools exposed by ``forge mcp``."""

FORGE_CONNECTION = {
    "forge": {
        "command": "forge",
        "args": ["mcp"],
        "transport": "stdio",
    },
}


async def get_forge_tools() -> list[BaseTool]:
    """Return Forge tools with a new MCP session per tool call.

    Simple interface — each tool invocation spawns a fresh ``forge mcp`` process.
    For multiple calls in sequence, prefer :func:`forge_session` instead.

    Returns
    -------
    list[BaseTool]
        LangChain-compatible tools auto-discovered from Forge MCP.

    """
    client = MultiServerMCPClient(FORGE_CONNECTION)
    tools = await client.get_tools()
    _log_discovered(tools)
    return tools


@asynccontextmanager
async def forge_session() -> AsyncIterator[list[BaseTool]]:
    """Open a persistent Forge MCP session for multiple tool calls.

    Usage::

        async with forge_session() as tools:
            validate = next(t for t in tools if t.name == "forge_validate")
            result = await validate.ainvoke({"file_path": "model.yaml"})

    Yields
    ------
    list[BaseTool]
        LangChain-compatible tools bound to the session.

    """
    client = MultiServerMCPClient(FORGE_CONNECTION)
    async with client.session("forge") as session:
        tools = await load_mcp_tools(session)
        _log_discovered(tools)
        yield tools


def _log_discovered(tools: list[BaseTool]) -> None:
    """Log discovered tool names and warn about any missing tools."""
    discovered = {t.name for t in tools}
    missing = FORGE_TOOL_NAMES - discovered
    if missing:
        logger.warning("Expected Forge tools not found: %s", missing)
    logger.info("Forge MCP: %d tools discovered", len(tools))
