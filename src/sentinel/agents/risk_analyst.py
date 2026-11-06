"""Risk Analyst agent -- Monte Carlo, tornado and break-even analysis in Forge.

The risk sections are built in code (see :mod:`sentinel.tools.risk_models`),
not by an LLM: they are fixed percentage ranges around the reported figures.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sentinel.tools.forge_mcp import get_forge_tools
from sentinel.tools.forge_text import json_or_error, parse_json, text_from
from sentinel.tools.risk_models import (
    MC_ITERATIONS,
    OUTPUT_VARIABLE,
    ModelShapeError,
    add_tornado,
    monte_carlo_variant,
)

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool

    from sentinel.graph.state import SentinelState

logger = logging.getLogger(__name__)


def _write_temp_yaml(content: str, prefix: str) -> Path:
    """Write YAML to a named temporary file and return the path."""
    fd, path = tempfile.mkstemp(suffix=".yaml", prefix=f"sentinel-risk-{prefix}-")
    with open(fd, "w") as fh:  # noqa: PTH123
        fh.write(content)
    return Path(path)


def _cleanup(path: Path) -> None:
    """Remove a temp YAML file and its Forge backup."""
    path.unlink(missing_ok=True)
    path.with_suffix(".yaml.bak").unlink(missing_ok=True)


def summarise_monte_carlo(raw: dict[str, Any]) -> dict[str, Any]:
    """Flatten Forge's simulation result to ``p10/p50/p90`` plus the raw output."""
    if "error" in raw:
        return raw
    outputs = raw.get("monte_carlo_results", {}).get("outputs", {})
    stats = outputs.get(OUTPUT_VARIABLE)
    if not isinstance(stats, dict):
        return {"error": "forge_simulate returned no result for the operating income"}
    percentiles = stats.get("percentiles", {})
    return {
        "output": OUTPUT_VARIABLE,
        "iterations": raw.get("monte_carlo_results", {}).get("iterations"),
        "mean": stats.get("mean"),
        "std_dev": stats.get("std_dev"),
        "p10": percentiles.get("p10"),
        "p50": percentiles.get("p50"),
        "p90": percentiles.get("p90"),
    }


async def _call(tool: BaseTool, args: dict[str, Any], name: str) -> dict[str, Any]:
    """Invoke a Forge tool and return JSON, or ``{"error": ...}`` on any failure."""
    try:
        return json_or_error(text_from(await tool.ainvoke(args)), name)
    except Exception:
        logger.exception("Risk Analyst: %s failed", name)
        return {"error": f"{name} failed"}


async def risk_analyst_node(state: SentinelState) -> dict[str, Any]:
    """Run Monte Carlo, tornado and break-even analysis on the Forge model.

    Returns
    -------
    dict
        Partial state update with ``risk_analysis``.

    """
    forge_results = state.get("forge_results", {})
    if "error" in forge_results:
        logger.error(
            "Risk Analyst: skipping -- forge_results has error: %s",
            forge_results["error"],
        )
        return {"risk_analysis": {"error": forge_results["error"]}}

    ticker = state.get("ticker", "UNKNOWN")
    model_yaml = state.get("model_yaml", "")
    logger.info("Risk Analyst: analysing %s", ticker)

    try:
        tornado_yaml = add_tornado(model_yaml)
        mc_yaml = monte_carlo_variant(model_yaml)
    except ModelShapeError as exc:
        logger.exception("Risk Analyst: cannot build risk model for %s", ticker)
        return {"risk_analysis": {"error": f"Cannot build risk model: {exc}"}}

    tools = {t.name: t for t in await get_forge_tools()}
    tornado_path = _write_temp_yaml(tornado_yaml, ticker)
    mc_path = _write_temp_yaml(mc_yaml, f"{ticker}-mc")
    try:
        validation = parse_json(
            text_from(await tools["forge_validate"].ainvoke({"file_path": str(tornado_path)})),
        )
        if not (validation and validation.get("tables_valid") and validation.get("scalars_valid")):
            logger.error("Risk Analyst: Forge rejected the risk model for %s", ticker)
            return {"risk_analysis": {"error": "Forge rejected the risk model"}}

        simulation = await _call(
            tools["forge_simulate"],
            {"file_path": str(mc_path), "iterations": MC_ITERATIONS},
            "forge_simulate",
        )
        tornado = await _call(
            tools["forge_tornado"],
            {"file_path": str(tornado_path)},
            "forge_tornado",
        )
        break_even = await _call(
            tools["forge_break_even"],
            {
                "file_path": str(tornado_path),
                "output": OUTPUT_VARIABLE,
                "vary": "inputs.revenue",
            },
            "forge_break_even",
        )
    except Exception:
        logger.exception("Risk Analyst: Forge validation failed for %s", ticker)
        return {"risk_analysis": {"error": "forge_validate failed"}}
    finally:
        _cleanup(tornado_path)
        _cleanup(mc_path)

    logger.info("Risk Analyst: analysis complete for %s", ticker)
    return {
        "risk_analysis": {
            "monte_carlo": summarise_monte_carlo(simulation),
            "tornado": tornado,
            "break_even": break_even,
            "risk_yaml": tornado_yaml,
            "assumptions": "Each numeric input varied by 10% (tornado: low/high; "
            "Monte Carlo: normal with std dev 10% of the value, independent draws).",
        },
    }
