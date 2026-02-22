"""Tests for the Risk Analyst agent node."""

from __future__ import annotations

import json
import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sentinel.agents.risk_analyst import (
    _cleanup,
    _strip_fences,
    _text_from,
    _write_temp_yaml,
    risk_analyst_node,
)

EXPECTED_VALIDATE_CALLS = 2
EXPECTED_MC_MEAN = 38300
EXPECTED_MC_ITERATIONS = 10000


def _make_validate_pass() -> MagicMock:
    """Create a forge_validate mock that passes."""
    mock = MagicMock()
    mock.name = "forge_validate"
    mock.ainvoke = AsyncMock(
        return_value=[
            {
                "type": "text",
                "text": json.dumps(
                    {"tables_valid": True, "scalars_valid": True, "mismatches": []},
                ),
            },
        ],
    )
    return mock


def _make_validate_fail() -> MagicMock:
    """Create a forge_validate mock that always fails."""
    mock = MagicMock()
    mock.name = "forge_validate"
    mock.ainvoke = AsyncMock(
        return_value=[
            {
                "type": "text",
                "text": json.dumps(
                    {
                        "tables_valid": False,
                        "scalars_valid": False,
                        "mismatches": [{"field": "x", "error": "bad"}],
                    },
                ),
            },
        ],
    )
    return mock


def _make_simulate() -> MagicMock:
    """Create a forge_simulate mock with Monte Carlo results."""
    mock = MagicMock()
    mock.name = "forge_simulate"
    mock.ainvoke = AsyncMock(
        return_value=[
            {
                "type": "text",
                "text": json.dumps(
                    {
                        "monte_carlo_results": {
                            "iterations": EXPECTED_MC_ITERATIONS,
                            "outputs": {
                                "outputs.operating_income": {
                                    "statistics": {
                                        "mean": EXPECTED_MC_MEAN,
                                        "median": 38000,
                                        "std_dev": 5000,
                                        "percentiles": {
                                            "10": 31000,
                                            "50": 38000,
                                            "90": 45000,
                                        },
                                    },
                                    "threshold_probabilities": {"> 0": 0.99},
                                },
                            },
                        },
                    },
                ),
            },
        ],
    )
    return mock


def _make_tornado() -> MagicMock:
    """Create a forge_tornado mock with sensitivity results."""
    mock = MagicMock()
    mock.name = "forge_tornado"
    mock.ainvoke = AsyncMock(
        return_value=[
            {
                "type": "text",
                "text": json.dumps(
                    {
                        "tornado_results": {
                            "output": "outputs.operating_income",
                            "sensitivities": [
                                {
                                    "input": "inputs.revenue",
                                    "low_value": 85320,
                                    "high_value": 104280,
                                    "low_output": 33920,
                                    "high_output": 42680,
                                    "swing": 8760,
                                },
                            ],
                        },
                    },
                ),
            },
        ],
    )
    return mock


def _make_break_even() -> MagicMock:
    """Create a forge_break_even mock with convergence results."""
    mock = MagicMock()
    mock.name = "forge_break_even"
    mock.ainvoke = AsyncMock(
        return_value=[
            {
                "type": "text",
                "text": json.dumps(
                    {
                        "break_even_results": {
                            "output": "outputs.operating_income",
                            "vary": "inputs.revenue",
                            "break_even_value": 56500,
                            "converged": True,
                        },
                    },
                ),
            },
        ],
    )
    return mock


def _base_state() -> dict[str, Any]:
    """Create a valid state for risk analysis tests."""
    return {
        "ticker": "AAPL",
        "raw_data": {"revenue": 94800, "cost_of_revenue": 42000},
        "model_yaml": (
            '_forge_version: "5.0.0"\ninputs:\n  revenue:\n    value: 94800\n    formula: null\n'
        ),
        "forge_results": {
            "outputs.gross_profit": 52800,
            "outputs.margin": 0.557,
        },
    }


# --- Helper tests ---


def test_text_from_extracts_text_blocks() -> None:
    """Verify _text_from extracts text from MCP content blocks."""
    blocks: list[dict[str, Any]] = [
        {"type": "text", "text": "hello"},
        {"type": "image", "data": "..."},
        {"type": "text", "text": "world"},
    ]
    assert _text_from(blocks) == "hello world"


def test_strip_fences_removes_yaml_fences() -> None:
    """Verify markdown code fences are stripped from YAML."""
    fenced = "```yaml\n_forge_version: 5.0.0\n```"
    assert _strip_fences(fenced) == "_forge_version: 5.0.0"


def test_strip_fences_noop_on_clean_yaml() -> None:
    """Verify clean YAML passes through unchanged."""
    clean = "_forge_version: 5.0.0"
    assert _strip_fences(clean) == clean


def test_write_temp_yaml_creates_file() -> None:
    """Verify temp YAML file is written with correct content."""
    path = _write_temp_yaml("test content", "test")
    try:
        assert path.exists()
        assert path.read_text() == "test content"
        assert path.suffix == ".yaml"
    finally:
        path.unlink()


def test_cleanup_removes_file_and_bak() -> None:
    """Verify cleanup removes both the YAML and .bak files."""
    path = _write_temp_yaml("content", "cleanup")
    bak = path.with_suffix(".yaml.bak")
    bak.write_text("backup")

    _cleanup(path)

    assert not path.exists()
    assert not bak.exists()


def test_cleanup_tolerates_missing_files() -> None:
    """Verify cleanup does not raise when files are already gone."""
    path = _write_temp_yaml("content", "gone")
    path.unlink()
    _cleanup(path)  # should not raise


# --- Node tests ---


async def test_risk_analyst_node_skips_on_forge_error() -> None:
    """Verify risk analyst returns error when forge_results has error."""
    state: dict[str, Any] = {
        "ticker": "AAPL",
        "raw_data": {"revenue": 94800},
        "model_yaml": "",
        "forge_results": {"error": "Validation failed"},
    }
    result = await risk_analyst_node(state)
    assert "error" in result["risk_analysis"]
    assert "Validation failed" in result["risk_analysis"]["error"]


async def test_risk_analyst_node_runs_full_analysis() -> None:
    """Verify risk analyst augments model and runs all analyses."""
    state = _base_state()
    augmented_yaml = (
        '_forge_version: "5.0.0"\ninputs:\n  revenue:\n'
        "    value: 94800\n    formula: null\n"
        "monte_carlo:\n  iterations: 10000\n"
    )

    mock_llm_response = AsyncMock()
    mock_llm_response.content = augmented_yaml

    mock_validate = _make_validate_pass()
    mock_simulate = _make_simulate()
    mock_tornado = _make_tornado()
    mock_break_even = _make_break_even()

    with (
        patch(
            "sentinel.agents.risk_analyst.get_llm",
            return_value=AsyncMock(ainvoke=AsyncMock(return_value=mock_llm_response)),
        ),
        patch(
            "sentinel.agents.risk_analyst.get_forge_tools",
            new_callable=AsyncMock,
            return_value=[mock_validate, mock_simulate, mock_tornado, mock_break_even],
        ),
    ):
        result = await risk_analyst_node(state)

    ra = result["risk_analysis"]
    assert "monte_carlo" in ra
    assert "tornado" in ra
    assert "break_even" in ra
    assert "risk_yaml" in ra
    assert ra["monte_carlo"]["monte_carlo_results"]["iterations"] == EXPECTED_MC_ITERATIONS


async def test_risk_analyst_node_retries_on_validation_failure() -> None:
    """Verify risk analyst retries when validation fails then succeeds."""
    state = _base_state()

    bad_yaml = "bad yaml"
    good_yaml = (
        '_forge_version: "5.0.0"\ninputs:\n  revenue:\n    value: 94800\n    formula: null\n'
    )

    mock_response_bad = AsyncMock()
    mock_response_bad.content = bad_yaml
    mock_response_good = AsyncMock()
    mock_response_good.content = good_yaml

    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(
        side_effect=[mock_response_bad, mock_response_good],
    )

    mock_validate = MagicMock()
    mock_validate.name = "forge_validate"
    mock_validate.ainvoke = AsyncMock(
        side_effect=[
            [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "tables_valid": False,
                            "scalars_valid": False,
                            "mismatches": [{"field": "mc", "error": "missing"}],
                        },
                    ),
                },
            ],
            [
                {
                    "type": "text",
                    "text": json.dumps(
                        {"tables_valid": True, "scalars_valid": True, "mismatches": []},
                    ),
                },
            ],
        ],
    )

    mock_simulate = _make_simulate()
    mock_tornado = _make_tornado()
    mock_break_even = _make_break_even()

    with (
        patch(
            "sentinel.agents.risk_analyst.get_llm",
            return_value=mock_llm,
        ),
        patch(
            "sentinel.agents.risk_analyst.get_forge_tools",
            new_callable=AsyncMock,
            return_value=[mock_validate, mock_simulate, mock_tornado, mock_break_even],
        ),
    ):
        result = await risk_analyst_node(state)

    assert "monte_carlo" in result["risk_analysis"]
    assert mock_validate.ainvoke.call_count == EXPECTED_VALIDATE_CALLS


async def test_risk_analyst_node_exhausts_retries() -> None:
    """Verify risk analyst returns error after all retries fail."""
    state = _base_state()

    mock_response = AsyncMock()
    mock_response.content = "bad yaml"

    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    mock_validate = _make_validate_fail()
    mock_simulate = _make_simulate()
    mock_tornado = _make_tornado()
    mock_break_even = _make_break_even()

    with (
        patch("sentinel.agents.risk_analyst.get_llm", return_value=mock_llm),
        patch(
            "sentinel.agents.risk_analyst.get_forge_tools",
            new_callable=AsyncMock,
            return_value=[mock_validate, mock_simulate, mock_tornado, mock_break_even],
        ),
    ):
        result = await risk_analyst_node(state)

    assert "error" in result["risk_analysis"]
    assert "failed after" in result["risk_analysis"]["error"].lower()


async def test_risk_analyst_node_handles_validate_exception_in_loop() -> None:
    """Verify risk analyst exhausts retries when validate raises in loop."""
    state = _base_state()
    augmented_yaml = '_forge_version: "5.0.0"\ninputs:\n  revenue:\n    value: 94800'

    mock_llm_response = AsyncMock()
    mock_llm_response.content = augmented_yaml

    mock_validate = MagicMock()
    mock_validate.name = "forge_validate"
    mock_validate.ainvoke = AsyncMock(side_effect=RuntimeError("boom"))

    mock_simulate = _make_simulate()
    mock_tornado = _make_tornado()
    mock_break_even = _make_break_even()

    with (
        patch(
            "sentinel.agents.risk_analyst.get_llm",
            return_value=AsyncMock(ainvoke=AsyncMock(return_value=mock_llm_response)),
        ),
        patch(
            "sentinel.agents.risk_analyst.get_forge_tools",
            new_callable=AsyncMock,
            return_value=[mock_validate, mock_simulate, mock_tornado, mock_break_even],
        ),
    ):
        result = await risk_analyst_node(state)

    assert "error" in result["risk_analysis"]
    assert "failed after" in result["risk_analysis"]["error"].lower()


async def test_risk_analyst_node_handles_llm_correction_exception_in_loop() -> None:
    """Verify risk analyst exhausts retries when LLM correction raises in loop."""
    state = _base_state()
    augmented_yaml = '_forge_version: "5.0.0"\ninputs:\n  revenue:\n    value: 94800'

    mock_initial_response = AsyncMock()
    mock_initial_response.content = augmented_yaml

    # First LLM call succeeds (generation), subsequent correction calls throw
    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(
        side_effect=[mock_initial_response, RuntimeError("correction boom")],
    )

    mock_validate = _make_validate_fail()
    mock_simulate = _make_simulate()
    mock_tornado = _make_tornado()
    mock_break_even = _make_break_even()

    with (
        patch("sentinel.agents.risk_analyst.get_llm", return_value=mock_llm),
        patch(
            "sentinel.agents.risk_analyst.get_forge_tools",
            new_callable=AsyncMock,
            return_value=[mock_validate, mock_simulate, mock_tornado, mock_break_even],
        ),
    ):
        result = await risk_analyst_node(state)

    assert "error" in result["risk_analysis"]


async def test_risk_analyst_node_handles_llm_exception() -> None:
    """Verify risk analyst returns error when initial LLM call raises."""
    state = _base_state()

    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(side_effect=RuntimeError("boom"))

    mock_validate = _make_validate_pass()
    mock_simulate = _make_simulate()
    mock_tornado = _make_tornado()
    mock_break_even = _make_break_even()

    with (
        patch("sentinel.agents.risk_analyst.get_llm", return_value=mock_llm),
        patch(
            "sentinel.agents.risk_analyst.get_forge_tools",
            new_callable=AsyncMock,
            return_value=[mock_validate, mock_simulate, mock_tornado, mock_break_even],
        ),
    ):
        result = await risk_analyst_node(state)

    assert "error" in result["risk_analysis"]
    assert "LLM augmentation failed" in result["risk_analysis"]["error"]


async def test_risk_analyst_node_handles_simulate_exception() -> None:
    """Verify partial results when forge_simulate raises but others succeed."""
    state = _base_state()
    augmented_yaml = '_forge_version: "5.0.0"\ninputs:\n  revenue:\n    value: 94800'

    mock_llm_response = AsyncMock()
    mock_llm_response.content = augmented_yaml

    mock_validate = _make_validate_pass()

    mock_simulate = MagicMock()
    mock_simulate.name = "forge_simulate"
    mock_simulate.ainvoke = AsyncMock(side_effect=RuntimeError("boom"))

    mock_tornado = _make_tornado()
    mock_break_even = _make_break_even()

    with (
        patch(
            "sentinel.agents.risk_analyst.get_llm",
            return_value=AsyncMock(ainvoke=AsyncMock(return_value=mock_llm_response)),
        ),
        patch(
            "sentinel.agents.risk_analyst.get_forge_tools",
            new_callable=AsyncMock,
            return_value=[mock_validate, mock_simulate, mock_tornado, mock_break_even],
        ),
    ):
        result = await risk_analyst_node(state)

    ra = result["risk_analysis"]
    assert "error" in ra["monte_carlo"]
    assert "tornado" in ra
    assert "error" not in ra["tornado"]
    assert "break_even" in ra
    assert "error" not in ra["break_even"]


async def test_risk_analyst_node_handles_tornado_exception() -> None:
    """Verify partial results when forge_tornado raises but others succeed."""
    state = _base_state()
    augmented_yaml = '_forge_version: "5.0.0"\ninputs:\n  revenue:\n    value: 94800'

    mock_llm_response = AsyncMock()
    mock_llm_response.content = augmented_yaml

    mock_validate = _make_validate_pass()
    mock_simulate = _make_simulate()

    mock_tornado = MagicMock()
    mock_tornado.name = "forge_tornado"
    mock_tornado.ainvoke = AsyncMock(side_effect=RuntimeError("boom"))

    mock_break_even = _make_break_even()

    with (
        patch(
            "sentinel.agents.risk_analyst.get_llm",
            return_value=AsyncMock(ainvoke=AsyncMock(return_value=mock_llm_response)),
        ),
        patch(
            "sentinel.agents.risk_analyst.get_forge_tools",
            new_callable=AsyncMock,
            return_value=[mock_validate, mock_simulate, mock_tornado, mock_break_even],
        ),
    ):
        result = await risk_analyst_node(state)

    ra = result["risk_analysis"]
    assert "error" not in ra["monte_carlo"]
    assert "error" in ra["tornado"]
    assert "error" not in ra["break_even"]


async def test_risk_analyst_node_handles_break_even_exception() -> None:
    """Verify partial results when forge_break_even raises but others succeed."""
    state = _base_state()
    augmented_yaml = '_forge_version: "5.0.0"\ninputs:\n  revenue:\n    value: 94800'

    mock_llm_response = AsyncMock()
    mock_llm_response.content = augmented_yaml

    mock_validate = _make_validate_pass()
    mock_simulate = _make_simulate()
    mock_tornado = _make_tornado()

    mock_break_even = MagicMock()
    mock_break_even.name = "forge_break_even"
    mock_break_even.ainvoke = AsyncMock(side_effect=RuntimeError("boom"))

    with (
        patch(
            "sentinel.agents.risk_analyst.get_llm",
            return_value=AsyncMock(ainvoke=AsyncMock(return_value=mock_llm_response)),
        ),
        patch(
            "sentinel.agents.risk_analyst.get_forge_tools",
            new_callable=AsyncMock,
            return_value=[mock_validate, mock_simulate, mock_tornado, mock_break_even],
        ),
    ):
        result = await risk_analyst_node(state)

    ra = result["risk_analysis"]
    assert "error" not in ra["monte_carlo"]
    assert "error" not in ra["tornado"]
    assert "error" in ra["break_even"]


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="Requires ANTHROPIC_API_KEY",
)
async def test_risk_analyst_with_real_forge() -> None:  # pragma: no cover
    """Integration test: risk analyst with real Forge MCP tools."""
    state: dict[str, Any] = {
        "ticker": "AAPL",
        "raw_data": {"revenue": 94800, "cost_of_revenue": 42000},
        "model_yaml": (
            '_forge_version: "5.0.0"\ninputs:\n  revenue:\n'
            "    value: 94800\n    formula: null\n"
            "  cost_of_revenue:\n    value: 42000\n    formula: null\n"
            "  operating_expenses:\n    value: 14500\n    formula: null\n"
            "outputs:\n  gross_profit:\n    value: null\n"
            '    formula: "=inputs.revenue - inputs.cost_of_revenue"\n'
            "  operating_income:\n    value: null\n"
            '    formula: "=outputs.gross_profit - inputs.operating_expenses"\n'
        ),
        "forge_results": {"outputs.gross_profit": 52800},
    }
    result = await risk_analyst_node(state)
    ra = result["risk_analysis"]
    assert "monte_carlo" in ra or "error" in ra
