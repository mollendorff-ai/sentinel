"""Tests for the Scenario Planner agent node."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from sentinel.agents.scenario_planner import scenario_planner_node

VALID = {"tables_valid": True, "scalars_valid": True, "mismatches": []}
OPERATING = "outputs.operating_income"
SCENARIOS = {
    "scenarios": [
        {
            "name": "bull",
            "probability": 0.25,
            "scalars": {"inputs.revenue": 110.0, OPERATING: 60.0},
        },
        {
            "name": "base",
            "probability": 0.5,
            "scalars": {"inputs.revenue": 100.0, OPERATING: 50.0},
        },
        {
            "name": "bear",
            "probability": 0.25,
            "scalars": {"inputs.revenue": 90.0, OPERATING: 40.0},
        },
    ],
}
COMPARE = {"scenarios": ["bull", "base", "bear"], "values": {}}
BREAK_EVEN = {"solution": 56.0, "converged": True}
EXPECTED_VALUE = 50.0

SOURCE = """\
inputs:
  revenue:
    value: 100
    formula: null
  cost_of_revenue:
    value: 50
    formula: null
outputs:
  operating_income:
    value: null
    formula: "=inputs.revenue - inputs.cost_of_revenue"
"""


def _tool(name: str, payload: object) -> MagicMock:
    tool = MagicMock()
    tool.name = name
    text = payload if isinstance(payload, str) else json.dumps(payload)
    tool.ainvoke = AsyncMock(return_value=[{"type": "text", "text": text}])
    return tool


def _tools(**overrides: object) -> list[MagicMock]:
    payloads: dict[str, object] = {
        "forge_validate": VALID,
        "forge_scenarios": SCENARIOS,
        "forge_compare": COMPARE,
        "forge_break_even": BREAK_EVEN,
    }
    payloads.update(overrides)
    return [_tool(n, p) for n, p in payloads.items()]


def _state(**extra: Any) -> dict[str, Any]:  # noqa: ANN401
    return {"ticker": "AAPL", "model_yaml": SOURCE, "forge_results": {}, **extra}


async def _run(tools: list[MagicMock], state: dict[str, Any]) -> dict[str, Any]:
    with patch("sentinel.agents.scenario_planner.get_forge_tools", AsyncMock(return_value=tools)):
        result = await scenario_planner_node(state)  # type: ignore[arg-type]
    return result["scenario_analysis"]


async def test_full_analysis() -> None:
    """Full analysis."""
    tools = _tools()
    out = await _run(tools, _state())
    assert [s["name"] for s in out["scenarios"]] == ["bull", "base", "bear"]
    assert out["scenarios"][0]["revenue"] == 110.0  # noqa: PLR2004
    assert out["expected_values"] == {OPERATING: EXPECTED_VALUE}
    assert out["comparison"] == COMPARE
    assert out["break_even_thresholds"] == BREAK_EVEN
    assert "scenarios:" in out["scenario_yaml"]
    assert "Revenue +10%" in out["assumptions"]
    compare = next(t for t in tools if t.name == "forge_compare")
    assert compare.ainvoke.call_args.args[0]["scenarios"] == ["bull", "base", "bear"]
    path = Path(compare.ainvoke.call_args.args[0]["file_path"])
    assert not path.exists()  # noqa: ASYNC240


async def test_builds_on_risk_yaml_when_present() -> None:
    """Builds on risk yaml when present."""
    risk = SOURCE + "tornado:\n  output: outputs.operating_income\n  inputs: []\n"
    out = await _run(_tools(), _state(risk_analysis={"risk_yaml": risk}))
    assert "tornado:" in out["scenario_yaml"]


async def test_skips_when_upstream_error() -> None:
    """Skips when upstream error."""
    out = await _run(_tools(), _state(forge_results={"error": "boom"}))
    assert out == {"error": "boom"}


async def test_unusable_model() -> None:
    """Unusable model."""
    out = await _run(_tools(), _state(model_yaml="- nope"))
    assert "Cannot build scenarios" in out["error"]


async def test_forge_rejects_scenarios() -> None:
    """Forge rejects scenarios."""
    out = await _run(_tools(forge_validate={"tables_valid": False}), _state())
    assert out == {"error": "Forge rejected the scenario model"}


async def test_validate_exception() -> None:
    """Validate exception."""
    tools = _tools()
    tools[0].ainvoke = AsyncMock(side_effect=RuntimeError("down"))
    assert await _run(tools, _state()) == {"error": "forge_validate failed"}


async def test_tool_failures_become_errors() -> None:
    """Tool failures become errors."""
    tools = _tools(forge_scenarios="Scenario analysis failed: bad", forge_compare="x")
    next(t for t in tools if t.name == "forge_compare").ainvoke = AsyncMock(
        side_effect=RuntimeError("crash"),
    )
    out = await _run(tools, _state())
    assert out["scenarios"] == []
    assert out["expected_values"] == {}
    assert out["comparison"] == {"error": "forge_compare failed"}
    assert out["break_even_thresholds"] == BREAK_EVEN


async def test_malformed_scenario_entries() -> None:
    """Malformed scenario entries."""
    odd = {"scenarios": ["junk", {"name": "bull", "probability": 1.0, "scalars": {}}]}
    out = await _run(_tools(forge_scenarios=odd), _state())
    assert len(out["scenarios"]) == 1
    assert out["expected_values"] == {}
