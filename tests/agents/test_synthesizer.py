"""Tests for the Synthesizer agent node."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

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
        "sentinel.agents.synthesizer.get_llm",
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
        "sentinel.agents.synthesizer.get_llm",
        return_value=mock_llm,
    ):
        await synthesizer_node(state)

    call_args = mock_llm.ainvoke.call_args[0][0]
    assert "should not appear in prompt" not in call_args


async def test_synthesizer_includes_risk_data_in_prompt() -> None:
    """Verify risk analysis data is injected into the prompt."""
    state: dict[str, Any] = {
        "ticker": "AAPL",
        "raw_data": {"period": "Q1 2026"},
        "forge_results": {"outputs.margin": 0.5},
        "risk_analysis": {
            "monte_carlo": {"iterations": 10000},
            "tornado": {"bars": []},
            "break_even": {"converged": True},
            "risk_yaml": "should not appear",
        },
    }

    mock_response = AsyncMock()
    mock_response.content = "Brief with risk."

    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    with patch("sentinel.agents.synthesizer.get_llm", return_value=mock_llm):
        await synthesizer_node(state)

    prompt = mock_llm.ainvoke.call_args[0][0]
    assert "RISK ANALYSIS" in prompt
    assert "monte_carlo" in prompt


async def test_synthesizer_includes_scenario_data_in_prompt() -> None:
    """Verify scenario analysis data is injected into the prompt."""
    state: dict[str, Any] = {
        "ticker": "AAPL",
        "raw_data": {"period": "Q1 2026"},
        "forge_results": {"outputs.margin": 0.5},
        "scenario_analysis": {
            "scenarios": [{"name": "Bull"}],
            "expected_values": {},
            "scenario_yaml": "should not appear",
        },
    }

    mock_response = AsyncMock()
    mock_response.content = "Brief with scenarios."

    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    with patch("sentinel.agents.synthesizer.get_llm", return_value=mock_llm):
        await synthesizer_node(state)

    prompt = mock_llm.ainvoke.call_args[0][0]
    assert "SCENARIO ANALYSIS" in prompt
    assert "Bull" in prompt


async def test_synthesizer_excludes_risk_yaml_from_prompt() -> None:
    """Verify risk_yaml is stripped before injection."""
    state: dict[str, Any] = {
        "ticker": "AAPL",
        "raw_data": {"period": "Q1 2026"},
        "forge_results": {"outputs.margin": 0.5},
        "risk_analysis": {
            "monte_carlo": {},
            "risk_yaml": "secret risk yaml content",
        },
    }

    mock_response = AsyncMock()
    mock_response.content = "Brief."

    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    with patch("sentinel.agents.synthesizer.get_llm", return_value=mock_llm):
        await synthesizer_node(state)

    prompt = mock_llm.ainvoke.call_args[0][0]
    assert "secret risk yaml content" not in prompt


async def test_synthesizer_excludes_scenario_yaml_from_prompt() -> None:
    """Verify scenario_yaml is stripped before injection."""
    state: dict[str, Any] = {
        "ticker": "AAPL",
        "raw_data": {"period": "Q1 2026"},
        "forge_results": {"outputs.margin": 0.5},
        "scenario_analysis": {
            "scenarios": [],
            "scenario_yaml": "secret scenario yaml content",
        },
    }

    mock_response = AsyncMock()
    mock_response.content = "Brief."

    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    with patch("sentinel.agents.synthesizer.get_llm", return_value=mock_llm):
        await synthesizer_node(state)

    prompt = mock_llm.ainvoke.call_args[0][0]
    assert "secret scenario yaml content" not in prompt


async def test_synthesizer_skips_risk_with_error() -> None:
    """Verify risk data is not injected when it contains an error."""
    state: dict[str, Any] = {
        "ticker": "AAPL",
        "raw_data": {"period": "Q1 2026"},
        "forge_results": {"outputs.margin": 0.5},
        "risk_analysis": {"error": "Validation failed after 3 attempts"},
    }

    mock_response = AsyncMock()
    mock_response.content = "Brief without risk."

    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    with patch("sentinel.agents.synthesizer.get_llm", return_value=mock_llm):
        await synthesizer_node(state)

    prompt = mock_llm.ainvoke.call_args[0][0]
    assert "RISK ANALYSIS" not in prompt


async def test_synthesizer_skips_scenario_with_error() -> None:
    """Verify scenario data is not injected when it contains an error."""
    state: dict[str, Any] = {
        "ticker": "AAPL",
        "raw_data": {"period": "Q1 2026"},
        "forge_results": {"outputs.margin": 0.5},
        "scenario_analysis": {"error": "Validation failed after 3 attempts"},
    }

    mock_response = AsyncMock()
    mock_response.content = "Brief without scenarios."

    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    with patch("sentinel.agents.synthesizer.get_llm", return_value=mock_llm):
        await synthesizer_node(state)

    prompt = mock_llm.ainvoke.call_args[0][0]
    assert "SCENARIO ANALYSIS" not in prompt


async def test_synthesizer_uses_short_word_range_without_extras() -> None:
    """Verify 300-500 word range when no risk or scenario data."""
    state: dict[str, Any] = {
        "ticker": "AAPL",
        "raw_data": {"period": "Q1 2026"},
        "forge_results": {"outputs.margin": 0.5},
    }

    mock_response = AsyncMock()
    mock_response.content = "Brief."

    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    with patch("sentinel.agents.synthesizer.get_llm", return_value=mock_llm):
        await synthesizer_node(state)

    prompt = mock_llm.ainvoke.call_args[0][0]
    assert "300-500" in prompt


async def test_synthesizer_uses_long_word_range_with_risk() -> None:
    """Verify 400-700 word range when risk data is present."""
    state: dict[str, Any] = {
        "ticker": "AAPL",
        "raw_data": {"period": "Q1 2026"},
        "forge_results": {"outputs.margin": 0.5},
        "risk_analysis": {"monte_carlo": {}, "tornado": {}},
    }

    mock_response = AsyncMock()
    mock_response.content = "Longer brief."

    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    with patch("sentinel.agents.synthesizer.get_llm", return_value=mock_llm):
        await synthesizer_node(state)

    prompt = mock_llm.ainvoke.call_args[0][0]
    assert "400-700" in prompt


async def test_synthesizer_node_handles_llm_exception() -> None:
    """Verify synthesizer returns fallback brief when LLM call raises."""
    state: dict[str, Any] = {
        "ticker": "AAPL",
        "raw_data": {"period": "Q1 2026"},
        "forge_results": {"outputs.margin": 0.5},
    }

    with patch(
        "sentinel.agents.synthesizer.get_llm",
        return_value=AsyncMock(ainvoke=AsyncMock(side_effect=RuntimeError("boom"))),
    ):
        result = await synthesizer_node(state)

    assert "Analysis incomplete for AAPL" in result["brief"]
    assert "LLM call failed" in result["brief"]


async def test_synthesizer_includes_history_in_prompt() -> None:
    """Verify historical context is injected into the prompt when present."""
    state: dict[str, Any] = {
        "ticker": "AAPL",
        "raw_data": {"period": "Q1 2026"},
        "forge_results": {"outputs.margin": 0.5},
        "historical_context": [
            {"ticker": "AAPL", "period": "Q4 2025", "revenue": 90000},
        ],
    }
    mock_response = MagicMock()
    mock_response.content = "Brief with history."
    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)
    with patch("sentinel.agents.synthesizer.get_llm", return_value=mock_llm):
        await synthesizer_node(state)
    prompt = mock_llm.ainvoke.call_args[0][0]
    assert "HISTORICAL EARNINGS" in prompt
    assert "Q4 2025" in prompt


async def test_synthesizer_omits_history_section_when_empty() -> None:
    """Verify historical section is absent when historical_context is empty."""
    state: dict[str, Any] = {
        "ticker": "AAPL",
        "raw_data": {"period": "Q1 2026"},
        "forge_results": {"outputs.margin": 0.5},
        "historical_context": [],
    }
    mock_response = MagicMock()
    mock_response.content = "Brief without history."
    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)
    with patch("sentinel.agents.synthesizer.get_llm", return_value=mock_llm):
        await synthesizer_node(state)
    prompt = mock_llm.ainvoke.call_args[0][0]
    assert "HISTORICAL EARNINGS" not in prompt


async def test_synthesizer_uses_long_word_range_with_history() -> None:
    """Verify 400-700 word range when historical_context is non-empty."""
    state: dict[str, Any] = {
        "ticker": "AAPL",
        "raw_data": {"period": "Q1 2026"},
        "forge_results": {"outputs.margin": 0.5},
        "historical_context": [{"ticker": "AAPL", "period": "Q4 2025"}],
    }
    mock_response = MagicMock()
    mock_response.content = "Longer brief."
    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)
    with patch("sentinel.agents.synthesizer.get_llm", return_value=mock_llm):
        await synthesizer_node(state)
    prompt = mock_llm.ainvoke.call_args[0][0]
    assert "400-700" in prompt


async def test_synthesizer_incorporates_analyst_feedback() -> None:
    """Verify analyst_feedback is injected into the prompt when set."""
    state: dict[str, Any] = {
        "ticker": "AAPL",
        "raw_data": {"period": "Q1 2026"},
        "forge_results": {"outputs.margin": 0.5},
        "analyst_feedback": "Emphasize margin compression.",
    }
    mock_response = MagicMock()
    mock_response.content = "Brief with feedback."
    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)
    with patch("sentinel.agents.synthesizer.get_llm", return_value=mock_llm):
        await synthesizer_node(state)
    prompt = mock_llm.ainvoke.call_args[0][0]
    assert "ANALYST FEEDBACK" in prompt
    assert "Emphasize margin compression." in prompt


async def test_synthesizer_omits_feedback_section_when_empty() -> None:
    """Verify ANALYST FEEDBACK section is absent when analyst_feedback is empty/missing."""
    state: dict[str, Any] = {
        "ticker": "AAPL",
        "raw_data": {"period": "Q1 2026"},
        "forge_results": {"outputs.margin": 0.5},
    }
    mock_response = MagicMock()
    mock_response.content = "Brief without feedback."
    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)
    with patch("sentinel.agents.synthesizer.get_llm", return_value=mock_llm):
        await synthesizer_node(state)
    prompt = mock_llm.ainvoke.call_args[0][0]
    assert "ANALYST FEEDBACK" not in prompt
