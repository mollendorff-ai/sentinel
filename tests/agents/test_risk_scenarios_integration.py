"""Risk and scenario nodes against the real, pinned Forge binary (needs ``forge`` on PATH)."""

from __future__ import annotations

import shutil

import pytest

from sentinel.agents.risk_analyst import risk_analyst_node
from sentinel.agents.scenario_planner import scenario_planner_node

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(shutil.which("forge") is None, reason="forge not on PATH"),
]

MODEL_5_0 = """\
_forge_version: "5.0.0"
inputs:
  revenue:
    value: 94800
    formula: null
  cost_of_revenue:
    value: 42000
    formula: null
  operating_expenses:
    value: 14500
    formula: null
  net_income:
    value: 24000
    formula: null
outputs:
  gross_profit:
    value: null
    formula: "=inputs.revenue - inputs.cost_of_revenue"
  operating_income:
    value: null
    formula: "=outputs.gross_profit - inputs.operating_expenses"
  operating_margin:
    value: null
    formula: "=outputs.operating_income / inputs.revenue"
"""

MODEL_5_1 = """\
_forge_version: "5.1.0"
inputs:
  revenue: 94800
  cost_of_revenue: 42000
  operating_expenses: 14500
  net_income: 24000
outputs:
  gross_profit: {formula: "=inputs.revenue - inputs.cost_of_revenue"}
  operating_income: {formula: "=outputs.gross_profit - inputs.operating_expenses"}
  operating_margin: {formula: "=outputs.operating_income / inputs.revenue"}
"""

both_formats = pytest.mark.parametrize("model", [MODEL_5_1, MODEL_5_0], ids=["5.1.0", "5.0.0"])

BASE_OPERATING_INCOME = 38300
REVENUE_SWING = 18960
BEAR_OPERATING_INCOME = 33020
BULL_OPERATING_INCOME = 43580


@both_formats
async def test_risk_analyst_with_real_forge(model: str) -> None:
    """Monte Carlo, tornado and break-even all return real numbers."""
    state = {"ticker": "TEST", "model_yaml": model, "forge_results": {}}
    out = (await risk_analyst_node(state))["risk_analysis"]  # type: ignore[arg-type]
    assert "error" not in out["monte_carlo"]
    assert out["monte_carlo"]["p10"] < out["monte_carlo"]["p50"] < out["monte_carlo"]["p90"]
    assert out["tornado"]["base_value"] == BASE_OPERATING_INCOME
    assert out["tornado"]["bars"][0]["abs_swing"] == REVENUE_SWING
    assert out["break_even"]["converged"] is True


@both_formats
async def test_scenario_planner_with_real_forge(model: str) -> None:
    """Bull / base / bear come back with the expected operating income."""
    state = {"ticker": "TEST", "model_yaml": model, "forge_results": {}}
    out = (await scenario_planner_node(state))["scenario_analysis"]  # type: ignore[arg-type]
    by_name = {s["name"]: s["operating_income"] for s in out["scenarios"]}
    assert by_name == {
        "bull": BULL_OPERATING_INCOME,
        "base": BASE_OPERATING_INCOME,
        "bear": BEAR_OPERATING_INCOME,
    }
    assert "error" not in out["comparison"]
