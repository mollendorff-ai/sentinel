"""Tests for the Synthesizer agent node."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

from sentinel.agents.synthesizer import synthesizer_node


async def test_synthesizer_node_produces_brief() -> None:
    """Verify synthesizer generates a brief from raw_data and forge_results."""
    state: dict[str, Any] = {
        "ticker": "AAPL",
        "raw_data": {"period": "Q1 2026", "revenue": 94800},
        "forge_results": {
            "outputs.gross_profit": 52800.0,
            "outputs.margin": 0.557,
            "raw_output": "verbose output...",
        },
    }

    mock_response = AsyncMock()
    mock_response.content = "# Executive Brief\n\nApple reported strong Q1 results."

    with patch(
        "sentinel.agents.synthesizer.ChatAnthropic",
        return_value=AsyncMock(ainvoke=AsyncMock(return_value=mock_response)),
    ):
        result = await synthesizer_node(state)

    assert "brief" in result
    assert "Executive Brief" in result["brief"]


async def test_synthesizer_node_handles_forge_error() -> None:
    """Verify synthesizer returns error message when forge_results has error."""
    state: dict[str, Any] = {
        "ticker": "AAPL",
        "raw_data": {},
        "forge_results": {"error": "Validation failed"},
    }

    result = await synthesizer_node(state)

    assert "incomplete" in result["brief"].lower()
    assert "Validation failed" in result["brief"]


async def test_synthesizer_node_excludes_raw_output_from_prompt() -> None:
    """Verify raw_output is stripped from forge_results before sending to Claude."""
    state: dict[str, Any] = {
        "ticker": "AAPL",
        "raw_data": {"period": "Q1 2026"},
        "forge_results": {
            "outputs.margin": 0.5,
            "raw_output": "should not appear in prompt",
        },
    }

    mock_response = AsyncMock()
    mock_response.content = "Brief content."

    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    with patch(
        "sentinel.agents.synthesizer.ChatAnthropic",
        return_value=mock_llm,
    ):
        await synthesizer_node(state)

    # Check the prompt passed to Claude does not contain raw_output
    call_args = mock_llm.ainvoke.call_args[0][0]
    assert "should not appear in prompt" not in call_args
