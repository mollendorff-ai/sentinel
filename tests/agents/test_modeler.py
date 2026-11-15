"""Tests for the Modeler agent node."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sentinel.agents.modeler import (
    _parse_calc_results,
    _strip_fences,
    _write_temp_yaml,
    modeler_node,
    typed_results,
)

if TYPE_CHECKING:
    from pathlib import Path

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


async def test_modeler_node_handles_llm_generation_exception() -> None:
    """Verify modeler returns error when initial LLM call raises."""
    state: dict[str, Any] = {
        "ticker": "AAPL",
        "raw_data": {"revenue": 100},
    }

    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(side_effect=RuntimeError("boom"))

    mock_validate = MagicMock()
    mock_validate.name = "forge_validate"
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

    assert result["model_yaml"] == ""
    assert "LLM generation failed" in result["forge_results"]["error"]


async def test_modeler_node_handles_validate_exception_in_loop() -> None:
    """Verify modeler treats validate exception as failure and exhausts retries."""
    state: dict[str, Any] = {
        "ticker": "AAPL",
        "raw_data": {"revenue": 100},
    }

    mock_response = AsyncMock()
    mock_response.content = "some yaml"

    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    mock_validate = MagicMock()
    mock_validate.name = "forge_validate"
    mock_validate.ainvoke = AsyncMock(side_effect=RuntimeError("boom"))

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


async def test_modeler_node_handles_calculate_exception() -> None:
    """Verify modeler returns error when forge_calculate raises."""
    state: dict[str, Any] = {
        "ticker": "AAPL",
        "raw_data": {"revenue": 100},
    }

    mock_response = AsyncMock()
    mock_response.content = '_forge_version: "5.0.0"\ninputs:\n  revenue:\n    value: 100'

    mock_validate = MagicMock()
    mock_validate.name = "forge_validate"
    mock_validate.ainvoke = AsyncMock(
        return_value=[
            {
                "type": "text",
                "text": json.dumps(
                    {"tables_valid": True, "scalars_valid": True, "mismatches": []},
                ),
            },
        ],
    )

    mock_calculate = MagicMock()
    mock_calculate.name = "forge_calculate"
    mock_calculate.ainvoke = AsyncMock(side_effect=RuntimeError("boom"))

    with (
        patch(
            "sentinel.agents.modeler.get_llm",
            return_value=AsyncMock(ainvoke=AsyncMock(return_value=mock_response)),
        ),
        patch(
            "sentinel.agents.modeler.get_forge_tools",
            new_callable=AsyncMock,
            return_value=[mock_validate, mock_calculate],
        ),
    ):
        result = await modeler_node(state)

    assert "forge_calculate failed" in result["forge_results"]["error"]
    assert result["model_yaml"]


async def test_modeler_node_handles_llm_correction_exception_in_loop() -> None:
    """Verify modeler exhausts retries when LLM correction raises inside loop."""
    state: dict[str, Any] = {
        "ticker": "AAPL",
        "raw_data": {"revenue": 100},
    }

    mock_initial_response = AsyncMock()
    mock_initial_response.content = "initial yaml"

    # First LLM call succeeds (initial generation), subsequent calls throw
    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(
        side_effect=[mock_initial_response, RuntimeError("correction boom")],
    )

    # Validation always fails to trigger correction
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
                        "mismatches": [{"field": "x", "error": "bad"}],
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


def _text(payload: str) -> list[dict[str, str]]:
    return [{"type": "text", "text": payload}]


async def test_modeler_survives_plain_text_validation_failure() -> None:
    """Forge answers a failed validation with plain text; the loop must correct, not crash."""
    state: dict[str, Any] = {"ticker": "AAPL", "raw_data": {"revenue": 100}}
    first = AsyncMock()
    first.content = "bad yaml"
    second = AsyncMock()
    second.content = "good yaml"
    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(side_effect=[first, second])

    mock_validate = MagicMock()
    mock_validate.name = "forge_validate"
    mock_validate.ainvoke = AsyncMock(
        side_effect=[
            _text("Validation failed: unknown field `inputs`"),
            _text(json.dumps({"tables_valid": True, "scalars_valid": True})),
        ],
    )
    mock_calculate = MagicMock()
    mock_calculate.name = "forge_calculate"
    mock_calculate.ainvoke = AsyncMock(
        return_value=_text(json.dumps({"scalars": {"inputs.revenue": 100}})),
    )

    with (
        patch("sentinel.agents.modeler.get_llm", return_value=mock_llm),
        patch(
            "sentinel.agents.modeler.get_forge_tools",
            new_callable=AsyncMock,
            return_value=[mock_validate, mock_calculate],
        ),
    ):
        result = await modeler_node(state)

    correction_prompt = mock_llm.ainvoke.call_args_list[1].args[0]
    assert "unknown field `inputs`" in correction_prompt
    assert result["forge_results"]["inputs.revenue"] == EXPECTED_REVENUE_SMALL


def test_parse_calc_results_reports_plain_text_failure() -> None:
    """A plain-text calculate failure becomes an error dict, not an exception."""
    results = _parse_calc_results("Calculation failed: bad formula")
    assert results["error"].startswith("forge_calculate failed: Calculation failed")


GOOD_MODEL = """\
_forge_version: "5.1.0"
inputs:
  revenue: 114477
  cost_of_revenue: 59657
  operating_expenses: 19189
  net_income: 30711
outputs:
  gross_profit: {formula: "=inputs.revenue - inputs.cost_of_revenue"}
  operating_income: {formula: "=outputs.gross_profit - inputs.operating_expenses"}
  gross_margin: {formula: "=outputs.gross_profit / inputs.revenue"}
"""


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        (GOOD_MODEL, []),
        (
            GOOD_MODEL.replace('"=outputs.gross_profit - inputs', '"=35631 + 0 * inputs'),
            ["outputs.operating_income is '=35631 + 0 * inputs.operating_expenses'"],
        ),
        ("outputs:\n  gross_profit: 54820\n", ["outputs.gross_profit is 54820"]),
        ("inputs: {}\n", ["the model has no outputs"]),
        ("- not a mapping\n", ["model is not a YAML mapping"]),
    ],
)
def test_typed_results(model: str, expected: list[str]) -> None:
    """An output whose formula holds a number, or a plain value, is typed, not calculated."""
    assert typed_results(model) == expected


def _filing(root: Path) -> None:
    folder = root / "inputs" / "AAPL" / "FY2026-Q4"
    folder.mkdir(parents=True)
    (folder / "release.md").write_text("doc")
    (folder / "source.yaml").write_text("url: https://www.sec.gov/x.htm\n")
    (folder / "expected.yaml").write_text(
        "checked: true\nfigures:\n  revenue: 114477\n"
        "results:\n  outputs.gross_profit: 54820\n  outputs.operating_income: 35631\n"
    )


def _tools(scalars: dict[str, float]) -> list[MagicMock]:
    validate = MagicMock()
    validate.name = "forge_validate"
    validate.ainvoke = AsyncMock(
        return_value=_text(json.dumps({"tables_valid": True, "scalars_valid": True}))
    )
    calculate = MagicMock()
    calculate.name = "forge_calculate"
    calculate.ainvoke = AsyncMock(
        return_value=_text(json.dumps({"scalars": scalars, "tables": {}}))
    )
    return [validate, calculate]


async def _run_modeler(answer: str, scalars: dict[str, float]) -> tuple[dict[str, Any], str]:
    llm = AsyncMock(ainvoke=AsyncMock(return_value=AsyncMock(content=answer)))
    raw_data = {
        "ticker": "AAPL",
        "revenue": 114477,
        "cost_of_revenue": 59657,
        "operating_expenses": 19189,
        "net_income": 30711,
        "gross_profit": 54820,
        "operating_income": 35631,
        "input": {"path": "inputs/AAPL/FY2026-Q4"},
    }
    with (
        patch("sentinel.agents.modeler.get_llm", return_value=llm),
        patch(
            "sentinel.agents.modeler.get_forge_tools",
            new_callable=AsyncMock,
            return_value=_tools(scalars),
        ),
    ):
        result = await modeler_node({"ticker": "AAPL", "raw_data": raw_data})
    return result["forge_results"], llm.ainvoke.call_args[0][0]


async def test_modeler_passes_when_forge_equals_the_filing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Forge's subtotals equal the filing's: no error, and the check is recorded."""
    _filing(tmp_path)
    monkeypatch.chdir(tmp_path)
    results, prompt = await _run_modeler(
        GOOD_MODEL, {"outputs.gross_profit": 54820, "outputs.operating_income": 35631}
    )
    assert "error" not in results
    assert results["filing_check"] == {
        "checked": ["outputs.gross_profit", "outputs.operating_income"],
        "mismatches": [],
    }
    # The Modeler sees the four inputs, not the subtotals, and is given no formula.
    assert '"revenue": 114477' in prompt
    assert '"gross_profit": 54820' not in prompt
    assert "inputs.revenue -" not in prompt
    assert "/home" not in prompt


async def test_modeler_fails_a_wrong_formula(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The evaluation's case: operating income that adds expenses fails the run."""
    _filing(tmp_path)
    monkeypatch.chdir(tmp_path)
    wrong = GOOD_MODEL.replace(
        "outputs.gross_profit - inputs.operating_expenses",
        "outputs.gross_profit + inputs.operating_expenses",
    )
    results, _ = await _run_modeler(
        wrong, {"outputs.gross_profit": 54820, "outputs.operating_income": 74009}
    )
    assert results["error"] == (
        "Forge's results differ from the filing: "
        "outputs.operating_income: the filing prints 35631, Forge calculated 74009"
    )


async def test_modeler_fails_a_typed_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A result typed into a formula fails, even when it equals the filing."""
    _filing(tmp_path)
    monkeypatch.chdir(tmp_path)
    typed = GOOD_MODEL.replace('"=outputs.gross_profit - inputs.operating_expenses"', '"=35631"')
    results, _ = await _run_modeler(
        typed, {"outputs.gross_profit": 54820, "outputs.operating_income": 35631}
    )
    assert (
        results["error"]
        == "A result is typed, not calculated: outputs.operating_income is '=35631'"
    )


async def test_modeler_fails_without_a_saved_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no saved input to check against, the run fails rather than pass unchecked."""
    monkeypatch.chdir(tmp_path)
    results, _ = await _run_modeler(GOOD_MODEL, {"outputs.gross_profit": 54820})
    assert results["error"].startswith("Cannot check Forge's results against the filing: ")
