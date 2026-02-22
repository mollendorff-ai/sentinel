"""Tests for the Modeler agent node."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from sentinel.agents.modeler import (
    _parse_calc_results,
    _strip_fences,
    _write_temp_yaml,
    modeler_node,
)

EXPECTED_MARGIN = 0.4
EXPECTED_REVENUE = 1_000_000.0
EXPECTED_GROSS_PROFIT = 52_800.0
EXPECTED_REVENUE_SMALL = 100.0
EXPECTED_VALIDATE_CALLS = 2


def test_strip_fences_removes_yaml_fences() -> None:
    """Verify markdown code fences are stripped from YAML."""
    fenced = "```yaml\n_forge_version: 5.0.0\n```"
    assert _strip_fences(fenced) == "_forge_version: 5.0.0"


def test_strip_fences_noop_on_clean_yaml() -> None:
    """Verify clean YAML passes through unchanged."""
    clean = "_forge_version: 5.0.0\ninputs:\n  revenue:\n    value: 100"
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


def test_parse_calc_results_extracts_scalars() -> None:
    """Verify calculation JSON is parsed into key-value pairs."""
    text = json.dumps(
        {
            "scalars": {"outputs.margin": 0.4, "inputs.revenue": 1000000},
            "tables": {},
        },
    )
    results = _parse_calc_results(text)
    assert results["outputs.margin"] == EXPECTED_MARGIN
    assert results["inputs.revenue"] == EXPECTED_REVENUE


def test_parse_calc_results_handles_empty_scalars() -> None:
    """Verify empty scalars returns empty dict."""
    text = json.dumps({"scalars": {}, "tables": {}})
    results = _parse_calc_results(text)
    assert results == {}


async def test_modeler_node_skips_on_research_error() -> None:
    """Verify modeler returns error when raw_data contains an error."""
    state: dict[str, Any] = {
        "ticker": "AAPL",
        "raw_data": {"error": "No data found"},
    }
    result = await modeler_node(state)
    assert result["model_yaml"] == ""
    assert "error" in result["forge_results"]


async def test_modeler_node_generates_and_calculates() -> None:
    """Verify modeler generates YAML, validates, and calculates."""
    state: dict[str, Any] = {
        "ticker": "AAPL",
        "raw_data": {
            "revenue": 94800,
            "cost_of_revenue": 42000,
            "operating_expenses": 14500,
        },
    }

    fake_yaml = (
        '_forge_version: "5.0.0"\ninputs:\n  revenue:\n    value: 94800\n    formula: null\n'
    )

    mock_llm_response = AsyncMock()
    mock_llm_response.content = fake_yaml

    mock_validate_result = [
        {
            "type": "text",
            "text": json.dumps({"tables_valid": True, "scalars_valid": True, "mismatches": []}),
        },
    ]
    mock_calc_result = [
        {
            "type": "text",
            "text": json.dumps(
                {
                    "scalars": {"outputs.gross_profit": 52800, "outputs.margin": 0.557},
                    "tables": {},
                },
            ),
        },
    ]

    mock_validate = MagicMock()
    mock_validate.name = "forge_validate"
    mock_validate.ainvoke = AsyncMock(return_value=mock_validate_result)

    mock_calculate = MagicMock()
    mock_calculate.name = "forge_calculate"
    mock_calculate.ainvoke = AsyncMock(return_value=mock_calc_result)

    with (
        patch(
            "sentinel.agents.modeler.get_llm",
            return_value=AsyncMock(ainvoke=AsyncMock(return_value=mock_llm_response)),
        ),
        patch(
            "sentinel.agents.modeler.get_forge_tools",
            new_callable=AsyncMock,
            return_value=[mock_validate, mock_calculate],
        ),
    ):
        result = await modeler_node(state)

    assert result["model_yaml"]
    assert result["forge_results"]["outputs.gross_profit"] == EXPECTED_GROSS_PROFIT


async def test_modeler_node_retries_on_validation_failure() -> None:
    """Verify modeler retries when validation fails, then succeeds."""
    state: dict[str, Any] = {
        "ticker": "AAPL",
        "raw_data": {"revenue": 100},
    }

    bad_yaml = "bad yaml"
    good_yaml = '_forge_version: "5.0.0"\ninputs:\n  revenue:\n    value: 100\n    formula: null'

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
                            "mismatches": [{"field": "x", "error": "invalid field"}],
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

    mock_calculate = MagicMock()
    mock_calculate.name = "forge_calculate"
    mock_calculate.ainvoke = AsyncMock(
        return_value=[
            {
                "type": "text",
                "text": json.dumps({"scalars": {"inputs.revenue": 100}, "tables": {}}),
            },
        ],
    )

    with (
        patch(
            "sentinel.agents.modeler.get_llm",
            return_value=mock_llm,
        ),
        patch(
            "sentinel.agents.modeler.get_forge_tools",
            new_callable=AsyncMock,
            return_value=[mock_validate, mock_calculate],
        ),
    ):
        result = await modeler_node(state)

    assert result["forge_results"]["inputs.revenue"] == EXPECTED_REVENUE_SMALL
    assert mock_validate.ainvoke.call_count == EXPECTED_VALIDATE_CALLS


async def test_modeler_node_exhausts_retries() -> None:
    """Verify modeler returns error after all validation retries fail."""
    state: dict[str, Any] = {
        "ticker": "AAPL",
        "raw_data": {"revenue": 100},
    }

    mock_response = AsyncMock()
    mock_response.content = "bad yaml"

    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    mock_validate = MagicMock()
    mock_validate.name = "forge_validate"
    mock_validate.ainvoke = AsyncMock(
        return_value=[
            {
                "type": "text",
                "text": json.dumps(
                    {
                        "tables_valid": False,
                        "scalars_valid": False,
                        "mismatches": [{"field": "x", "error": "always fails"}],
                    },
                ),
            },
        ],
    )

    mock_calculate = MagicMock()
    mock_calculate.name = "forge_calculate"

    with (
        patch("sentinel.agents.modeler.get_llm", return_value=mock_llm),
        patch(
            "sentinel.agents.modeler.get_forge_tools",
            new_callable=AsyncMock,
            return_value=[mock_validate, mock_calculate],
        ),
    ):
        result = await modeler_node(state)

    assert "error" in result["forge_results"]
    assert "failed after" in result["forge_results"]["error"].lower()
