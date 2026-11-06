"""Tests for the Risk Analyst agent node."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from sentinel.agents.risk_analyst import risk_analyst_node, summarise_monte_carlo

MODEL = Path("tests/fixtures/risk_model.yaml")
P10, P50, P90 = 24854.0, 38208.0, 51694.0

VALID = {"tables_valid": True, "scalars_valid": True, "mismatches": []}
SIMULATION = {
    "monte_carlo_results": {
        "iterations": 10000,
        "outputs": {
            "outputs.operating_income": {
                "mean": 38299.0,
                "std_dev": 10394.0,
                "percentiles": {"p10": P10, "p50": P50, "p90": P90},
            },
        },
    },
}
TORNADO = {"bars": [{"input_name": "inputs.revenue", "swing": 18960.0}]}
BREAK_EVEN = {"solution": 56500.0, "converged": True}

SOURCE = """\
_forge_version: "5.0.0"
inputs:
  revenue:
    value: 94800
    formula: null
  cost_of_revenue:
    value: 42000
    formula: null
outputs:
  gross_profit:
    value: null
    formula: "=inputs.revenue - inputs.cost_of_revenue"
  operating_income:
    value: null
    formula: "=outputs.gross_profit"
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
        "forge_simulate": SIMULATION,
        "forge_tornado": TORNADO,
        "forge_break_even": BREAK_EVEN,
    }
    payloads.update(overrides)
    return [_tool(n, p) for n, p in payloads.items()]


def _state(**extra: Any) -> dict[str, Any]:  # noqa: ANN401
    return {"ticker": "AAPL", "model_yaml": SOURCE, "forge_results": {}, **extra}


async def _run(tools: list[MagicMock], state: dict[str, Any]) -> dict[str, Any]:
    with patch("sentinel.agents.risk_analyst.get_forge_tools", AsyncMock(return_value=tools)):
        result = await risk_analyst_node(state)  # type: ignore[arg-type]
    return result["risk_analysis"]


async def test_full_analysis() -> None:
    """Full analysis."""
    tools = _tools()
    out = await _run(tools, _state())
    assert out["monte_carlo"]["p50"] == P50
    assert out["tornado"] == TORNADO
    assert out["break_even"] == BREAK_EVEN
    assert "tornado:" in out["risk_yaml"]
    assert "10%" in out["assumptions"]
    sim = next(t for t in tools if t.name == "forge_simulate")
    path = Path(sim.ainvoke.call_args.args[0]["file_path"])
    assert not path.exists()  # noqa: ASYNC240


async def test_skips_when_upstream_error() -> None:
    """Skips when upstream error."""
    out = await _run(_tools(), _state(forge_results={"error": "boom"}))
    assert out == {"error": "boom"}


async def test_unusable_model() -> None:
    """Unusable model."""
    out = await _run(_tools(), _state(model_yaml="- not a model"))
    assert "Cannot build risk model" in out["error"]


async def test_forge_rejects_model() -> None:
    """Forge rejects model."""
    bad = {"tables_valid": False, "scalars_valid": False}
    out = await _run(_tools(forge_validate=bad), _state())
    assert out == {"error": "Forge rejected the risk model"}


async def test_forge_validate_plain_text_is_rejection() -> None:
    """Forge validate plain text is rejection."""
    out = await _run(_tools(forge_validate="Validation failed: nope"), _state())
    assert out == {"error": "Forge rejected the risk model"}


async def test_validate_exception() -> None:
    """Validate exception."""
    tools = _tools()
    tools[0].ainvoke = AsyncMock(side_effect=RuntimeError("down"))
    out = await _run(tools, _state())
    assert out == {"error": "forge_validate failed"}


async def test_partial_results_survive_tool_failures() -> None:
    """Partial results survive tool failures."""
    tools = _tools(forge_simulate="Simulation failed: monte_carlo config error")
    tornado = next(t for t in tools if t.name == "forge_tornado")
    tornado.ainvoke = AsyncMock(side_effect=RuntimeError("crash"))
    out = await _run(tools, _state())
    assert "forge_simulate failed" in out["monte_carlo"]["error"]
    assert out["tornado"] == {"error": "forge_tornado failed"}
    assert out["break_even"] == BREAK_EVEN


def test_summarise_monte_carlo_without_result() -> None:
    """Summarise monte carlo without result."""
    assert "error" in summarise_monte_carlo({"monte_carlo_results": {"outputs": {}}})
    assert summarise_monte_carlo({"error": "x"}) == {"error": "x"}
