"""Tests for the Research agent node."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, patch

from sentinel.agents.research import _build_urls, research_node

EXPECTED_REVENUE = 100_000
EXPECTED_REVENUE_PARTIAL = 50_000
EXPECTED_URL_COUNT = 2


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
    """Verify research_node calls ref_fetch and extracts financial data via Claude."""
    fake_ref_result: dict[str, Any] = {
        "status": "ok",
        "url": "https://example.com",
        "sections": [
            {"heading": "Revenue", "text": "Revenue was $100B in Q1 2026."},
            {"heading": "Margins", "text": "Gross margin was 45%."},
        ],
    }

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
            "sentinel.agents.research.RefFetchTool._arun",
            new_callable=AsyncMock,
            return_value=fake_ref_result,
        ),
        patch(
            "sentinel.agents.research.ChatAnthropic",
            return_value=AsyncMock(ainvoke=AsyncMock(return_value=mock_llm_response)),
        ),
    ):
        result = await research_node({"ticker": "AAPL"})

    assert "raw_data" in result
    assert result["raw_data"]["ticker"] == "AAPL"
    assert result["raw_data"]["revenue"] == EXPECTED_REVENUE


async def test_research_node_handles_no_content() -> None:
    """Verify research_node returns error when ref_fetch fails for all URLs."""
    fail_result: dict[str, Any] = {"status": "error", "error": "timeout"}

    with patch(
        "sentinel.agents.research.RefFetchTool._arun",
        new_callable=AsyncMock,
        return_value=fail_result,
    ):
        result = await research_node({"ticker": "AAPL"})

    assert "error" in result["raw_data"]


async def test_research_node_handles_non_json_response() -> None:
    """Verify research_node extracts JSON from non-clean Claude response."""
    fake_ref_result: dict[str, Any] = {
        "status": "ok",
        "url": "https://example.com",
        "sections": [{"heading": "Data", "text": "Some earnings data."}],
    }

    mock_llm_response = AsyncMock()
    mock_llm_response.content = 'Here is the data: {"ticker": "AAPL", "revenue": 50000}'

    with (
        patch(
            "sentinel.agents.research.RefFetchTool._arun",
            new_callable=AsyncMock,
            return_value=fake_ref_result,
        ),
        patch(
            "sentinel.agents.research.ChatAnthropic",
            return_value=AsyncMock(ainvoke=AsyncMock(return_value=mock_llm_response)),
        ),
    ):
        result = await research_node({"ticker": "AAPL"})

    assert result["raw_data"]["revenue"] == EXPECTED_REVENUE_PARTIAL


async def test_research_node_includes_headingless_sections() -> None:
    """Verify sections without headings are included by body text."""
    fake_ref_result: dict[str, Any] = {
        "status": "ok",
        "url": "https://example.com",
        "sections": [
            {"heading": "", "text": "Body-only section content."},
        ],
    }

    mock_llm_response = AsyncMock()
    mock_llm_response.content = json.dumps({"ticker": "AAPL", "revenue": 1})

    with (
        patch(
            "sentinel.agents.research.RefFetchTool._arun",
            new_callable=AsyncMock,
            return_value=fake_ref_result,
        ),
        patch(
            "sentinel.agents.research.ChatAnthropic",
            return_value=AsyncMock(ainvoke=AsyncMock(return_value=mock_llm_response)),
        ),
    ):
        result = await research_node({"ticker": "AAPL"})

    assert result["raw_data"]["ticker"] == "AAPL"


async def test_research_node_handles_unparseable_response() -> None:
    """Verify research_node returns error when Claude output has no JSON."""
    fake_ref_result: dict[str, Any] = {
        "status": "ok",
        "url": "https://example.com",
        "sections": [{"heading": "Data", "text": "Some content."}],
    }

    mock_llm_response = AsyncMock()
    mock_llm_response.content = "I cannot extract any data from this page."

    with (
        patch(
            "sentinel.agents.research.RefFetchTool._arun",
            new_callable=AsyncMock,
            return_value=fake_ref_result,
        ),
        patch(
            "sentinel.agents.research.ChatAnthropic",
            return_value=AsyncMock(ainvoke=AsyncMock(return_value=mock_llm_response)),
        ),
    ):
        result = await research_node({"ticker": "AAPL"})

    assert "error" in result["raw_data"]
