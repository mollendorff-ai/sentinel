"""Tests for the Scenario Planner agent node."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sentinel.agents.scenario_planner import (
    _cleanup,
    _strip_fences,
    _text_from,
    _write_temp_yaml,
    scenario_planner_node,
)

EXPECTED_VALIDATE_CALLS = 2
EXPECTED_BULL_OI = 50000
EXPECTED_BASE_OI = 38300
EXPECTED_BEAR_OI = 20000
EXPECTED_EV_OI = 36650

VALID_YAML = (
    '_forge_version: "5.0.0"\n'
    "inputs:\n"
    "  revenue:\n"
    "    value: 94800\n"
    "    formula: null\n"
    "scenarios:\n"
    "  - name: Bull\n"
    "    probability: 0.25\n"
    "    scalars:\n"
    "      inputs.revenue: 108120\n"
)


def _make_valid_validation() -> list[dict[str, Any]]:
    return [
        {
            "type": "text",
            "text": json.dumps(
                {
                    "tables_valid": True,
                    "scalars_valid": True,
                    "mismatches": [],
                },
            ),
        },
    ]


def _make_invalid_validation() -> list[dict[str, Any]]:
    return [
        {
            "type": "text",
            "text": json.dumps(
                {
                    "tables_valid": False,
                    "scalars_valid": False,
                    "mismatches": [{"field": "scenarios", "error": "invalid format"}],
                },
            ),
        },
    ]


def _make_scenarios_result() -> list[dict[str, Any]]:
    return [
        {
            "type": "text",
            "text": json.dumps(
                {
                    "scenarios": [
                        {
                            "name": "Bull",
                            "probability": 0.25,
                            "outputs": {"outputs.operating_income": EXPECTED_BULL_OI},
                        },
                        {
                            "name": "Base",
                            "probability": 0.50,
                            "outputs": {"outputs.operating_income": EXPECTED_BASE_OI},
                        },
                        {
                            "name": "Bear",
                            "probability": 0.25,
                            "outputs": {"outputs.operating_income": EXPECTED_BEAR_OI},
                        },
                    ],
                    "expected_values": {"outputs.operating_income": EXPECTED_EV_OI},
                    "probability_positive": {"outputs.operating_income": 0.95},
                    "ranges": {"outputs.operating_income": [EXPECTED_BEAR_OI, EXPECTED_BULL_OI]},
                },
            ),
        },
    ]


def _make_compare_result() -> list[dict[str, Any]]:
    return [
        {
            "type": "text",
            "text": json.dumps(
                {
                    "scenarios": ["Bull", "Base", "Bear"],
                    "variables": ["outputs.operating_income"],
                    "values": {
                        "outputs.operating_income": {
                            "Bull": EXPECTED_BULL_OI,
                            "Base": EXPECTED_BASE_OI,
                            "Bear": EXPECTED_BEAR_OI,
                        },
                    },
                },
            ),
        },
    ]


def _make_break_even_result() -> list[dict[str, Any]]:
    return [
        {
            "type": "text",
            "text": json.dumps(
                {
                    "output": "outputs.operating_income",
                    "vary": "inputs.revenue",
                    "break_even_value": 56500,
                },
            ),
        },
    ]


def _make_mock_tools(
    *,
    validate_side_effect: list[list[dict[str, str]]] | None = None,
    validate_return: list[dict[str, str]] | None = None,
) -> list[MagicMock]:
    mock_validate = MagicMock()
    mock_validate.name = "forge_validate"
    if validate_side_effect is not None:
        mock_validate.ainvoke = AsyncMock(side_effect=validate_side_effect)
    else:
        mock_validate.ainvoke = AsyncMock(
            return_value=validate_return or _make_valid_validation(),
        )

    mock_scenarios = MagicMock()
    mock_scenarios.name = "forge_scenarios"
    mock_scenarios.ainvoke = AsyncMock(return_value=_make_scenarios_result())

    mock_compare = MagicMock()
    mock_compare.name = "forge_compare"
    mock_compare.ainvoke = AsyncMock(return_value=_make_compare_result())

    mock_break_even = MagicMock()
    mock_break_even.name = "forge_break_even"
    mock_break_even.ainvoke = AsyncMock(return_value=_make_break_even_result())

    return [mock_validate, mock_scenarios, mock_compare, mock_break_even]


def test_strip_fences_removes_yaml_fences() -> None:
    """Verify markdown code fences are stripped from YAML."""
    fenced = "```yaml\nscenarios:\n  - name: Bull\n```"
    assert _strip_fences(fenced) == "scenarios:\n  - name: Bull"


def test_strip_fences_noop_on_clean_yaml() -> None:
    """Verify clean YAML passes through unchanged."""
    clean = "scenarios:\n  - name: Bull\n    probability: 0.25"
    assert _strip_fences(clean) == clean


def test_text_from_extracts_text_blocks() -> None:
    """Verify text extraction from MCP content blocks."""
    result: list[dict[str, Any]] = [
        {"type": "text", "text": "hello"},
        {"type": "image", "data": "..."},
        {"type": "text", "text": "world"},
    ]
    assert _text_from(result) == "hello world"


def test_write_temp_yaml_creates_file() -> None:
    """Verify temp YAML file is written with correct content."""
    path = _write_temp_yaml("test content", "test")
    try:
        assert path.exists()
        assert path.read_text() == "test content"
        assert path.suffix == ".yaml"
    finally:
        path.unlink()


def test_cleanup_removes_file_and_backup() -> None:
    """Verify cleanup removes both YAML file and .bak backup."""
    path = _write_temp_yaml("content", "cleanup")
    bak = path.with_suffix(".yaml.bak")
    bak.write_text("backup")
    _cleanup(path)
    assert not path.exists()
    assert not bak.exists()


async def test_scenario_planner_node_skips_on_forge_error() -> None:
    """Verify scenario planner returns error when forge_results has error."""
    state: dict[str, Any] = {
        "ticker": "AAPL",
        "raw_data": {"revenue": 94800},
        "model_yaml": VALID_YAML,
        "forge_results": {"error": "Validation failed after 3 attempts"},
    }
    result = await scenario_planner_node(state)
    assert "error" in result["scenario_analysis"]


async def test_scenario_planner_node_runs_full_analysis() -> None:
    """Verify scenario planner generates scenarios and runs all tools."""
    state: dict[str, Any] = {
        "ticker": "AAPL",
        "raw_data": {"revenue": 94800, "cost_of_revenue": 42000},
        "model_yaml": VALID_YAML,
        "forge_results": {"outputs.gross_profit": 52800},
    }

    mock_llm_response = AsyncMock()
    mock_llm_response.content = VALID_YAML

    mock_tools = _make_mock_tools()

    with (
        patch(
            "sentinel.agents.scenario_planner.get_llm",
            return_value=AsyncMock(ainvoke=AsyncMock(return_value=mock_llm_response)),
        ),
        patch(
            "sentinel.agents.scenario_planner.get_forge_tools",
            new_callable=AsyncMock,
            return_value=mock_tools,
        ),
    ):
        result = await scenario_planner_node(state)

    sa = result["scenario_analysis"]
    assert "scenarios" in sa
    assert "expected_values" in sa
    assert "comparison" in sa
    assert "break_even_thresholds" in sa
    assert "scenario_yaml" in sa
    assert sa["expected_values"]["outputs.operating_income"] == EXPECTED_EV_OI


async def test_scenario_planner_node_retries_on_validation_failure() -> None:
    """Verify scenario planner retries when validation fails, then succeeds."""
    state: dict[str, Any] = {
        "ticker": "AAPL",
        "raw_data": {"revenue": 94800},
        "model_yaml": VALID_YAML,
        "forge_results": {"outputs.gross_profit": 52800},
    }

    bad_yaml = "bad yaml"
    mock_response_bad = AsyncMock()
    mock_response_bad.content = bad_yaml
    mock_response_good = AsyncMock()
    mock_response_good.content = VALID_YAML

    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(
        side_effect=[mock_response_bad, mock_response_good],
    )

    mock_tools = _make_mock_tools(
        validate_side_effect=[
            _make_invalid_validation(),
            _make_valid_validation(),
        ],
    )
    mock_validate = mock_tools[0]

    with (
        patch(
            "sentinel.agents.scenario_planner.get_llm",
            return_value=mock_llm,
        ),
        patch(
            "sentinel.agents.scenario_planner.get_forge_tools",
            new_callable=AsyncMock,
            return_value=mock_tools,
        ),
    ):
        result = await scenario_planner_node(state)

    assert "scenarios" in result["scenario_analysis"]
    assert mock_validate.ainvoke.call_count == EXPECTED_VALIDATE_CALLS


async def test_scenario_planner_node_exhausts_retries() -> None:
    """Verify scenario planner returns error after all retries fail."""
    state: dict[str, Any] = {
        "ticker": "AAPL",
        "raw_data": {"revenue": 94800},
        "model_yaml": VALID_YAML,
        "forge_results": {"outputs.gross_profit": 52800},
    }

    mock_response = AsyncMock()
    mock_response.content = "bad yaml"

    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    mock_tools = _make_mock_tools(validate_return=_make_invalid_validation())

    with (
        patch("sentinel.agents.scenario_planner.get_llm", return_value=mock_llm),
        patch(
            "sentinel.agents.scenario_planner.get_forge_tools",
            new_callable=AsyncMock,
            return_value=mock_tools,
        ),
    ):
        result = await scenario_planner_node(state)

    assert "error" in result["scenario_analysis"]
    assert "failed after" in result["scenario_analysis"]["error"].lower()


async def test_scenario_planner_uses_risk_yaml_when_available() -> None:
    """Verify scenario planner uses risk_yaml over model_yaml when present."""
    risk_yaml = VALID_YAML + "\nmonte_carlo:\n  iterations: 1000\n"

    state: dict[str, Any] = {
        "ticker": "AAPL",
        "raw_data": {"revenue": 94800},
        "model_yaml": VALID_YAML,
        "forge_results": {"outputs.gross_profit": 52800},
        "risk_analysis": {"risk_yaml": risk_yaml},
    }

    mock_llm_response = AsyncMock()
    mock_llm_response.content = risk_yaml

    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_llm_response)

    mock_tools = _make_mock_tools()

    with (
        patch(
            "sentinel.agents.scenario_planner.get_llm",
            return_value=mock_llm,
        ),
        patch(
            "sentinel.agents.scenario_planner.get_forge_tools",
            new_callable=AsyncMock,
            return_value=mock_tools,
        ),
    ):
        result = await scenario_planner_node(state)

    # Verify the LLM was called with risk_yaml (which contains monte_carlo)
    call_args = mock_llm.ainvoke.call_args_list[0]
    prompt_text = call_args[0][0]
    assert "monte_carlo" in prompt_text
    assert "scenarios" in result["scenario_analysis"]


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="Requires ANTHROPIC_API_KEY",
)
async def test_scenario_planner_with_real_forge() -> None:  # pragma: no cover
    """Integration test: run scenario planner with real Forge MCP.

    Requires ``forge`` binary on PATH.
    """
    fixture = Path(__file__).parent.parent / "fixtures" / "risk_model.yaml"
    model_yaml = fixture.read_text()

    state: dict[str, Any] = {
        "ticker": "TEST",
        "raw_data": {
            "revenue": 94800,
            "cost_of_revenue": 42000,
            "operating_expenses": 14500,
        },
        "model_yaml": model_yaml,
        "forge_results": {"outputs.gross_profit": 52800},
    }
    result = await scenario_planner_node(state)
    sa = result["scenario_analysis"]
    assert "scenarios" in sa or "error" in sa
