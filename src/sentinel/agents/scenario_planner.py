"""Scenario Planner agent -- bull / base / bear scenarios run in Forge.

The scenarios are built in code (see :mod:`sentinel.tools.risk_models`): revenue
moves by +/-10%, cost of revenue and net income move with it, operating expenses
stay fixed.  They are an illustration of operating leverage, not a forecast.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sentinel.tools.forge_mcp import get_forge_tools
from sentinel.tools.forge_text import json_or_error, parse_json, text_from
from sentinel.tools.risk_models import (
    OUTPUT_VARIABLE,
    SCENARIO_NAMES,
    ModelShapeError,
    add_scenarios,
)

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool

    from sentinel.graph.state import SentinelState

logger = logging.getLogger(__name__)

_ASSUMPTIONS = (
    "Revenue +10% (bull) / -10% (bear); cost of revenue and net income move with "
    "revenue; operating expenses fixed. Probabilities 25/50/25 are illustrative."
)


def _write_temp_yaml(content: str, prefix: str) -> Path:
    """Write YAML to a named temporary file and return the path."""
    fd, path = tempfile.mkstemp(suffix=".yaml", prefix=f"sentinel-{prefix}-")
    with open(fd, "w") as fh:  # noqa: PTH123
        fh.write(content)
    return Path(path)


def _cleanup(path: Path) -> None:
    """Remove a temp YAML file and its Forge backup."""
    path.unlink(missing_ok=True)
    path.with_suffix(".yaml.bak").unlink(missing_ok=True)


async def _call(tool: BaseTool, args: dict[str, Any], name: str) -> dict[str, Any]:
    """Invoke a Forge tool and return JSON, or ``{"error": ...}`` on any failure."""
    try:
        return json_or_error(text_from(await tool.ainvoke(args)), name)
    except Exception:
        logger.exception("Scenario Planner: %s failed", name)
        return {"error": f"{name} failed"}


def _flatten(scenarios: object) -> list[dict[str, Any]]:
    """Add top-level ``revenue`` and ``operating_income`` to each scenario."""
    if not isinstance(scenarios, list):
        return []
    flat: list[dict[str, Any]] = []
    for item in scenarios:
        if not isinstance(item, dict):
            continue
        scalars = item.get("scalars", {})
        flat.append(
            {
                "name": item.get("name"),
                "probability": item.get("probability"),
                "revenue": scalars.get("inputs.revenue"),
                "operating_income": scalars.get(OUTPUT_VARIABLE),
                "scalars": scalars,
            },
        )
    return flat


def _expected_value(flat: list[dict[str, Any]]) -> dict[str, float]:
    """Probability-weighted operating income, when every scenario has both parts."""
    parts = [(s["probability"], s["operating_income"]) for s in flat]
    if not parts or any(p is None or v is None for p, v in parts):
        return {}
    return {OUTPUT_VARIABLE: sum(p * v for p, v in parts)}


async def scenario_planner_node(state: SentinelState) -> dict[str, Any]:
    """Build bull / base / bear scenarios and run Forge's scenario tools.

    Returns
    -------
    dict
        Partial state update with ``scenario_analysis``.

    """
    forge_results = state.get("forge_results", {})
    if isinstance(forge_results, dict) and "error" in forge_results:
        logger.error(
            "Scenario Planner: skipping -- upstream error: %s",
            forge_results["error"],
        )
        return {"scenario_analysis": {"error": forge_results["error"]}}

    ticker = state["ticker"]
    base_yaml = state.get("risk_analysis", {}).get("risk_yaml") or state["model_yaml"]
    logger.info("Scenario Planner: building scenarios for %s", ticker)

    try:
        scenario_yaml = add_scenarios(base_yaml)
    except ModelShapeError as exc:
        logger.exception("Scenario Planner: cannot build scenarios for %s", ticker)
        return {"scenario_analysis": {"error": f"Cannot build scenarios: {exc}"}}

    tools = {t.name: t for t in await get_forge_tools()}
    path = _write_temp_yaml(scenario_yaml, f"{ticker}-scenario")
    try:
        validation = parse_json(
            text_from(await tools["forge_validate"].ainvoke({"file_path": str(path)})),
        )
        if not (validation and validation.get("tables_valid") and validation.get("scalars_valid")):
            logger.error("Scenario Planner: Forge rejected the scenarios for %s", ticker)
            return {"scenario_analysis": {"error": "Forge rejected the scenario model"}}

        scenarios = await _call(
            tools["forge_scenarios"],
            {"file_path": str(path)},
            "forge_scenarios",
        )
        comparison = await _call(
            tools["forge_compare"],
            {"file_path": str(path), "scenarios": list(SCENARIO_NAMES)},
            "forge_compare",
        )
        break_even = await _call(
            tools["forge_break_even"],
            {"file_path": str(path), "output": OUTPUT_VARIABLE, "vary": "inputs.revenue"},
            "forge_break_even",
        )
    except Exception:
        logger.exception("Scenario Planner: Forge validation failed for %s", ticker)
        return {"scenario_analysis": {"error": "forge_validate failed"}}
    finally:
        _cleanup(path)

    flat = _flatten(scenarios.get("scenarios"))
    logger.info("Scenario Planner: analysis complete for %s", ticker)
    return {
        "scenario_analysis": {
            "scenarios": flat,
            "expected_values": _expected_value(flat),
            "comparison": comparison,
            "break_even_thresholds": break_even,
            "scenario_yaml": scenario_yaml,
            "assumptions": _ASSUMPTIONS,
        },
    }
