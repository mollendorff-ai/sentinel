"""Tests for the Research agent node."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from sentinel.agents.research import _build_urls, research_node

EXPECTED_REVENUE = 100_000
EXPECTED_REVENUE_PARTIAL = 50_000
EXPECTED_URL_COUNT = 2


def _mock_ref_tools(mcp_response: list[dict[str, Any]]) -> AsyncMock:
    """Build a mock get_ref_tools that returns a ref_fetch tool with the given response."""
    ref_fetch_tool = MagicMock()
    ref_fetch_tool.name = "ref_fetch"
    ref_fetch_tool.ainvoke = AsyncMock(return_value=mcp_response)
    return AsyncMock(return_value=[ref_fetch_tool])


def _mcp_content(data: dict[str, Any] | list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Wrap data as MCP content blocks."""
    return [{"type": "text", "text": json.dumps(data)}]


def test_build_urls_known_ticker() -> None:
    """Verify URL construction for a known ticker slug."""
    urls = _build_urls("AAPL")
    assert len(urls) == EXPECTED_URL_COUNT
    assert "apple" in urls[0]
    assert "apple" in urls[1]


def test_build_urls_unknown_ticker() -> None:
    """Verify URL construction falls back to lowercase ticker."""
    urls = _build_urls("XYZ")
    assert "xyz" in urls[0]


async def test_research_node_extracts_data() -> None:
    """Verify research_node calls ref_fetch via MCP and extracts financial data."""
    pages = [
        {
            "status": "ok",
            "url": "https://example.com",
            "sections": [
                {"heading": "Revenue", "text": "Revenue was $100B in Q1 2026."},
                {"heading": "Margins", "text": "Gross margin was 45%."},
            ],
        },
    ]

    extracted = {
        "company": "Apple Inc.",
        "ticker": "AAPL",
        "period": "Q1 2026",
        "revenue": 100000,
        "gross_margin": 0.45,
    }

    mock_llm_response = AsyncMock()
    mock_llm_response.content = json.dumps(extracted)

    with (
        patch(
            "sentinel.agents.research.get_ref_tools",
            _mock_ref_tools(_mcp_content(pages)),
        ),
        patch(
            "sentinel.agents.research.get_llm",
            return_value=AsyncMock(ainvoke=AsyncMock(return_value=mock_llm_response)),
        ),
    ):
        result = await research_node({"ticker": "AAPL"})

    assert "raw_data" in result
    assert result["raw_data"]["ticker"] == "AAPL"
    assert result["raw_data"]["revenue"] == EXPECTED_REVENUE


async def test_research_node_handles_no_content() -> None:
    """Verify research_node returns error when ref_fetch fails for all URLs."""
    pages = [
        {"status": "error", "url": "https://fail.example", "error": "timeout"},
        {"status": "error", "url": "https://fail2.example", "error": "timeout"},
    ]

    with patch(
        "sentinel.agents.research.get_ref_tools",
        _mock_ref_tools(_mcp_content(pages)),
    ):
        result = await research_node({"ticker": "AAPL"})

    assert "error" in result["raw_data"]


async def test_research_node_handles_non_json_response() -> None:
    """Verify research_node extracts JSON from non-clean Claude response."""
    pages = [
        {
            "status": "ok",
            "url": "https://example.com",
            "sections": [{"heading": "Data", "text": "Some earnings data."}],
        },
    ]

    mock_llm_response = AsyncMock()
    mock_llm_response.content = 'Here is the data: {"ticker": "AAPL", "revenue": 50000}'

    with (
        patch(
            "sentinel.agents.research.get_ref_tools",
            _mock_ref_tools(_mcp_content(pages)),
        ),
        patch(
            "sentinel.agents.research.get_llm",
            return_value=AsyncMock(ainvoke=AsyncMock(return_value=mock_llm_response)),
        ),
    ):
        result = await research_node({"ticker": "AAPL"})

    assert result["raw_data"]["revenue"] == EXPECTED_REVENUE_PARTIAL


async def test_research_node_includes_headingless_sections() -> None:
    """Verify sections without headings are included by body text."""
    pages = [
        {
            "status": "ok",
            "url": "https://example.com",
            "sections": [
                {"heading": "", "text": "Body-only section content."},
            ],
        },
    ]

    mock_llm_response = AsyncMock()
    mock_llm_response.content = json.dumps({"ticker": "AAPL", "revenue": 1})

    with (
        patch(
            "sentinel.agents.research.get_ref_tools",
            _mock_ref_tools(_mcp_content(pages)),
        ),
        patch(
            "sentinel.agents.research.get_llm",
            return_value=AsyncMock(ainvoke=AsyncMock(return_value=mock_llm_response)),
        ),
    ):
        result = await research_node({"ticker": "AAPL"})

    assert result["raw_data"]["ticker"] == "AAPL"


async def test_research_node_handles_unparseable_response() -> None:
    """Verify research_node returns error when Claude output has no JSON."""
    pages = [
        {
            "status": "ok",
            "url": "https://example.com",
            "sections": [{"heading": "Data", "text": "Some content."}],
        },
    ]

    mock_llm_response = AsyncMock()
    mock_llm_response.content = "I cannot extract any data from this page."

    with (
        patch(
            "sentinel.agents.research.get_ref_tools",
            _mock_ref_tools(_mcp_content(pages)),
        ),
        patch(
            "sentinel.agents.research.get_llm",
            return_value=AsyncMock(ainvoke=AsyncMock(return_value=mock_llm_response)),
        ),
    ):
        result = await research_node({"ticker": "AAPL"})

    assert "error" in result["raw_data"]


async def test_research_node_handles_mcp_parse_failure() -> None:
    """Verify research_node returns error when MCP response is not parseable JSON."""
    bad_content = [{"type": "text", "text": "not valid json"}]

    with patch(
        "sentinel.agents.research.get_ref_tools",
        _mock_ref_tools(bad_content),
    ):
        result = await research_node({"ticker": "AAPL"})

    assert "error" in result["raw_data"]


async def test_research_node_single_page_response() -> None:
    """Verify research_node handles single dict (not array) from ref_fetch."""
    single_page = {
        "status": "ok",
        "url": "https://example.com",
        "sections": [{"heading": "Revenue", "text": "Revenue was $100B."}],
    }

    mock_llm_response = AsyncMock()
    mock_llm_response.content = json.dumps({"ticker": "AAPL", "revenue": 100000})

    with (
        patch(
            "sentinel.agents.research.get_ref_tools",
            _mock_ref_tools(_mcp_content(single_page)),
        ),
        patch(
            "sentinel.agents.research.get_llm",
            return_value=AsyncMock(ainvoke=AsyncMock(return_value=mock_llm_response)),
        ),
    ):
        result = await research_node({"ticker": "AAPL"})

    assert result["raw_data"]["revenue"] == EXPECTED_REVENUE
