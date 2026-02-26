"""Tests for the Retriever agent node."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from sentinel.agents.retriever import retriever_node


async def test_retriever_node_returns_history() -> None:
    """Verify retriever_node returns historical_context from Qdrant."""
    history = [
        {"ticker": "AAPL", "period": "Q4 2025", "revenue": 90000},
        {"ticker": "AAPL", "period": "Q3 2025", "revenue": 85000},
    ]
    state: dict[str, Any] = {
        "ticker": "AAPL",
        "raw_data": {"ticker": "AAPL", "period": "Q1 2026"},
    }
    mock_client = MagicMock()
    mock_create = MagicMock(return_value=mock_client)
    mock_retrieve = MagicMock(return_value=history)

    with (
        patch("sentinel.agents.retriever.create_store", mock_create),
        patch("sentinel.agents.retriever.retrieve", mock_retrieve),
    ):
        result = await retriever_node(state)

    assert result["historical_context"] == history
    mock_create.assert_called_once()
    mock_retrieve.assert_called_once_with(mock_client, "AAPL", "Q1 2026")


async def test_retriever_node_returns_empty_on_first_run() -> None:
    """Verify retriever_node returns [] when Qdrant has no history."""
    state: dict[str, Any] = {
        "ticker": "AAPL",
        "raw_data": {"ticker": "AAPL", "period": "Q1 2026"},
    }
    mock_client = MagicMock()
    mock_create = MagicMock(return_value=mock_client)
    mock_retrieve = MagicMock(return_value=[])

    with (
        patch("sentinel.agents.retriever.create_store", mock_create),
        patch("sentinel.agents.retriever.retrieve", mock_retrieve),
    ):
        result = await retriever_node(state)

    assert result["historical_context"] == []


async def test_retriever_node_skips_on_research_error() -> None:
    """Verify retriever skips Qdrant when research returned an error."""
    state: dict[str, Any] = {
        "ticker": "AAPL",
        "raw_data": {"error": "ref_fetch failed for AAPL", "ticker": "AAPL"},
    }
    mock_create = MagicMock()

    with patch("sentinel.agents.retriever.create_store", mock_create):
        result = await retriever_node(state)

    assert result["historical_context"] == []
    mock_create.assert_not_called()


async def test_retriever_node_graceful_on_qdrant_exception() -> None:
    """Verify retriever returns [] when create_store raises."""
    state: dict[str, Any] = {
        "ticker": "AAPL",
        "raw_data": {"ticker": "AAPL", "period": "Q1 2026"},
    }

    with patch(
        "sentinel.agents.retriever.create_store",
        side_effect=RuntimeError("Qdrant init failed"),
    ):
        result = await retriever_node(state)

    assert result["historical_context"] == []


async def test_retriever_node_uses_ticker_from_raw_data() -> None:
    """Verify retriever prefers ticker from raw_data over state ticker."""
    state: dict[str, Any] = {
        "ticker": "AAPL",
        "raw_data": {"ticker": "MSFT", "period": "Q2 2025"},
    }
    mock_client = MagicMock()
    mock_create = MagicMock(return_value=mock_client)
    mock_retrieve = MagicMock(return_value=[])

    with (
        patch("sentinel.agents.retriever.create_store", mock_create),
        patch("sentinel.agents.retriever.retrieve", mock_retrieve),
    ):
        await retriever_node(state)

    mock_retrieve.assert_called_once_with(mock_client, "MSFT", "Q2 2025")


async def test_retriever_node_falls_back_to_state_ticker() -> None:
    """Verify retriever falls back to state ticker when raw_data has none."""
    state: dict[str, Any] = {
        "ticker": "NVDA",
        "raw_data": {"period": "Q3 2025"},
    }
    mock_client = MagicMock()
    mock_create = MagicMock(return_value=mock_client)
    mock_retrieve = MagicMock(return_value=[])

    with (
        patch("sentinel.agents.retriever.create_store", mock_create),
        patch("sentinel.agents.retriever.retrieve", mock_retrieve),
    ):
        await retriever_node(state)

    call_args = mock_retrieve.call_args[0]
    assert call_args[1] == "NVDA"
