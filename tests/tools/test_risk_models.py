"""Tests for the deterministic risk and scenario model builders."""

from __future__ import annotations

import pytest
import yaml

from sentinel.tools.risk_models import (
    MC_ITERATIONS,
    ModelShapeError,
    add_scenarios,
    add_tornado,
    monte_carlo_variant,
    numeric_inputs,
)

MODEL = """\
_forge_version: "5.0.0"
inputs:
  revenue:
    value: 1000
    formula: null
  cost_of_revenue:
    value: 400
    formula: null
  operating_expenses:
    value: 200
    formula: null
  net_income:
    value: 300
    formula: null
  note:
    value: null
    formula: null
outputs:
  gross_profit:
    value: null
    formula: "=inputs.revenue - inputs.cost_of_revenue"
  operating_income:
    value: null
    formula: "=outputs.gross_profit - inputs.operating_expenses"
"""

PROBS = 1.0
BULL_REVENUE = 1100
BEAR_REVENUE = 900
BULL_COST = 440
MC_STD = 100


def test_numeric_inputs_skips_null_zero_bool_and_formulas() -> None:
    """Numeric inputs skips null zero bool and formulas."""
    model = {
        "inputs": {
            "a": {"value": 5, "formula": None},
            "b": {"value": None, "formula": None},
            "c": {"value": 0, "formula": None},
            "d": {"value": True, "formula": None},
            "e": {"value": 7, "formula": "=a"},
            "f": 3,
        },
    }
    assert numeric_inputs(model) == {"a": 5.0}


def test_numeric_inputs_without_inputs_section() -> None:
    """Numeric inputs without inputs section."""
    assert numeric_inputs({"inputs": []}) == {}


def test_add_tornado_ranges() -> None:
    """Add tornado ranges."""
    model = yaml.safe_load(add_tornado(MODEL))
    assert model["tornado"]["output"] == "outputs.operating_income"
    rev = next(i for i in model["tornado"]["inputs"] if i["name"] == "inputs.revenue")
    assert (rev["low"], rev["high"]) == (900, 1100)
    assert len(model["tornado"]["inputs"]) == len(["revenue", "cost", "opex", "net"])


def test_monte_carlo_variant_uses_mc_formulas() -> None:
    """Monte carlo variant uses mc formulas."""
    model = yaml.safe_load(monte_carlo_variant(MODEL))
    assert model["inputs"]["revenue"] == {
        "value": None,
        "formula": f"=MC.Normal(1000.0, {float(MC_STD)})",
    }
    assert model["monte_carlo"]["iterations"] == MC_ITERATIONS
    assert model["monte_carlo"]["outputs"][0]["variable"] == "outputs.operating_income"
    assert model["inputs"]["note"] == {"value": None, "formula": None}


def test_add_scenarios_scales_with_revenue_and_keeps_opex() -> None:
    """Add scenarios scales with revenue and keeps opex."""
    sc = yaml.safe_load(add_scenarios(MODEL))["scenarios"]
    assert set(sc) == {"bull", "base", "bear"}
    assert sc["bull"]["scalars"]["revenue"] == BULL_REVENUE
    assert sc["bear"]["scalars"]["revenue"] == BEAR_REVENUE
    assert sc["bull"]["scalars"]["cost_of_revenue"] == BULL_COST
    assert sc["bull"]["scalars"]["operating_expenses"] == 200  # noqa: PLR2004
    assert sum(s["probability"] for s in sc.values()) == PROBS
    assert sc["base"]["scalars"]["revenue"] == 1000  # noqa: PLR2004


@pytest.mark.parametrize("builder", [add_tornado, monte_carlo_variant, add_scenarios])
@pytest.mark.parametrize(
    "bad",
    [
        "not: [valid",
        "- a list",
        "inputs: {}\noutputs: {operating_income: {value: null, formula: '=1'}}",
        "inputs:\n  x: {value: 1, formula: null}\noutputs: {}",
    ],
)
def test_builders_reject_unusable_models(builder: object, bad: str) -> None:
    """Builders reject unusable models."""
    with pytest.raises(ModelShapeError):
        builder(bad)  # type: ignore[operator]
