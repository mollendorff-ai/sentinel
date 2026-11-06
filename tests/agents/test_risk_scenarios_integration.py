"""Risk and scenario nodes against the real Forge binary (needs ``forge`` on PATH)."""

from __future__ import annotations

import shutil

import pytest

from sentinel.agents.risk_analyst import risk_analyst_node
from sentinel.agents.scenario_planner import scenario_planner_node

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(shutil.which("forge") is None, reason="forge not on PATH"),
]

MODEL = """\
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

BASE_OPERATING_INCOME = 38300
REVENUE_SWING = 18960
BEAR_OPERATING_INCOME = 33020
BULL_OPERATING_INCOME = 43580


async def test_risk_analyst_with_real_forge() -> None:
    """Monte Carlo, tornado and break-even all return real numbers."""
    state = {"ticker": "TEST", "model_yaml": MODEL, "forge_results": {}}
    out = (await risk_analyst_node(state))["risk_analysis"]  # type: ignore[arg-type]
    assert "error" not in out["monte_carlo"]
    assert out["monte_carlo"]["p10"] < out["monte_carlo"]["p50"] < out["monte_carlo"]["p90"]
    assert out["tornado"]["base_value"] == BASE_OPERATING_INCOME
    assert out["tornado"]["bars"][0]["abs_swing"] == REVENUE_SWING
    assert out["break_even"]["converged"] is True


async def test_scenario_planner_with_real_forge() -> None:
    """Bull / base / bear come back with the expected operating income."""
    state = {"ticker": "TEST", "model_yaml": MODEL, "forge_results": {}}
    out = (await scenario_planner_node(state))["scenario_analysis"]  # type: ignore[arg-type]
    by_name = {s["name"]: s["operating_income"] for s in out["scenarios"]}
    assert by_name == {
        "bull": BULL_OPERATING_INCOME,
        "base": BASE_OPERATING_INCOME,
        "bear": BEAR_OPERATING_INCOME,
    }
    assert "error" not in out["comparison"]
