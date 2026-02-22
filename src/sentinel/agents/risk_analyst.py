"""Risk Analyst agent -- augments a Forge model with Monte Carlo and sensitivity analysis."""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sentinel.llm import get_llm
from sentinel.tools.forge_mcp import get_forge_tools

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel
    from langchain_core.tools import BaseTool

    from sentinel.graph.state import SentinelState

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
MC_ITERATIONS = 10_000

RISK_AUGMENTATION_PROMPT = """\
You are a financial risk analyst.  Given the Forge YAML model below, add
monte_carlo and tornado sections for risk analysis.

EXISTING MODEL:
{model_yaml}

Add these sections to the YAML:

monte_carlo:
  iterations: {iterations}
  inputs:
    <for each input with a numeric value, add>:
      distribution: "normal"
      mean: <current value>
      std_dev: <10% of current value>

tornado:
  output: "outputs.operating_income"
  inputs:
    <for each input with a numeric value, add>:
      low: <90% of current value>
      high: <110% of current value>

Rules:
- Keep ALL existing content unchanged.
- Append monte_carlo and tornado sections at the end.
- Use raw numbers, not formatted strings.
- Return ONLY the YAML content, no markdown fences, no commentary.
"""

RISK_CORRECTION_PROMPT = """\
The augmented Forge model has validation errors:

{errors}

Here is the model:
{model_yaml}

Fix the errors and return the corrected YAML.  Return ONLY the YAML content,
no markdown fences, no commentary.
"""


def _text_from(result: list[dict[str, Any]]) -> str:
    """Extract text from MCP tool result content blocks."""
    return " ".join(block["text"] for block in result if block.get("type") == "text")


def _strip_fences(text: str) -> str:
    """Remove markdown code fences from YAML content."""
    lines = text.strip().splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines)


def _write_temp_yaml(content: str, prefix: str) -> Path:
    """Write YAML to a named temporary file and return the path."""
    fd, path = tempfile.mkstemp(suffix=".yaml", prefix=f"sentinel-risk-{prefix}-")
    with open(fd, "w") as fh:  # noqa: PTH123
        fh.write(content)
    return Path(path)


def _cleanup(path: Path) -> None:
    """Remove a temp YAML file and its Forge backup."""
    path.unlink(missing_ok=True)
    bak = path.with_suffix(".yaml.bak")
    bak.unlink(missing_ok=True)


async def _validate_loop(
    augmented_yaml: str,
    ticker: str,
    *,
    llm: BaseChatModel,
    validate: BaseTool,
) -> tuple[str, bool]:
    """Run the self-correction loop: validate -> fix -> retry.

    Returns the (possibly corrected) YAML and whether validation passed.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        model_path = _write_temp_yaml(augmented_yaml, ticker)
        try:
            try:
                val_result = await validate.ainvoke({"file_path": str(model_path)})
                val_text = _text_from(val_result)
            except Exception:
                logger.exception(
                    "Risk Analyst: forge_validate failed (attempt %d)",
                    attempt,
                )
                continue

            val_data = json.loads(val_text)
            if val_data.get("tables_valid") and val_data.get("scalars_valid"):
                logger.info("Risk Analyst: validation passed (attempt %d)", attempt)
                return augmented_yaml, True

            logger.warning(
                "Risk Analyst: validation failed (attempt %d): %s",
                attempt,
                val_text[:200],
            )

            if attempt < MAX_RETRIES:
                correction = RISK_CORRECTION_PROMPT.format(
                    errors=val_text,
                    model_yaml=augmented_yaml,
                )
                try:
                    response = await llm.ainvoke(correction)
                except Exception:
                    logger.exception(
                        "Risk Analyst: LLM correction failed (attempt %d)",
                        attempt,
                    )
                    continue
                augmented_yaml = (
                    response.content
                    if isinstance(response.content, str)
                    else str(response.content)
                )
                augmented_yaml = _strip_fences(augmented_yaml)
        finally:
            _cleanup(model_path)

    logger.error("Risk Analyst: validation failed after %d attempts", MAX_RETRIES)
    return augmented_yaml, False


async def _run_risk_tools(
    augmented_yaml: str,
    ticker: str,
    *,
    simulate: BaseTool,
    tornado: BaseTool,
    break_even: BaseTool,
) -> dict[str, Any]:
    """Run simulate, tornado, and break_even independently (partial results survive)."""
    model_path = _write_temp_yaml(augmented_yaml, ticker)
    try:
        try:
            sim_result = await simulate.ainvoke(
                {"file_path": str(model_path), "iterations": MC_ITERATIONS},
            )
            mc_data: dict[str, Any] = json.loads(_text_from(sim_result))
        except Exception:
            logger.exception("Risk Analyst: forge_simulate failed for %s", ticker)
            mc_data = {"error": "forge_simulate failed"}

        try:
            torn_result = await tornado.ainvoke({"file_path": str(model_path)})
            torn_data: dict[str, Any] = json.loads(_text_from(torn_result))
        except Exception:
            logger.exception("Risk Analyst: forge_tornado failed for %s", ticker)
            torn_data = {"error": "forge_tornado failed"}

        try:
            be_result = await break_even.ainvoke(
                {
                    "file_path": str(model_path),
                    "output": "outputs.operating_income",
                    "vary": "inputs.revenue",
                },
            )
            be_data: dict[str, Any] = json.loads(_text_from(be_result))
        except Exception:
            logger.exception("Risk Analyst: forge_break_even failed for %s", ticker)
            be_data = {"error": "forge_break_even failed"}

        logger.info("Risk Analyst: analysis complete for %s", ticker)
    finally:
        _cleanup(model_path)

    return {
        "monte_carlo": mc_data,
        "tornado": torn_data,
        "break_even": be_data,
        "risk_yaml": augmented_yaml,
    }


async def risk_analyst_node(state: SentinelState) -> dict[str, Any]:
    """Augment a Forge model with Monte Carlo, tornado, and break-even analysis.

    Includes a self-correction loop: if ``forge_validate`` returns errors,
    the augmented model is revised up to :data:`MAX_RETRIES` times.

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

    model_yaml = state.get("model_yaml", "")
    ticker = state.get("ticker", "UNKNOWN")

    logger.info("Risk Analyst: augmenting model for %s", ticker)

    llm = get_llm(max_tokens=4096)
    tools = await get_forge_tools()

    validate = next(t for t in tools if t.name == "forge_validate")
    simulate = next(t for t in tools if t.name == "forge_simulate")
    tornado_tool = next(t for t in tools if t.name == "forge_tornado")
    break_even = next(t for t in tools if t.name == "forge_break_even")

    # Generate augmented YAML with risk sections
    prompt = RISK_AUGMENTATION_PROMPT.format(
        model_yaml=model_yaml,
        iterations=MC_ITERATIONS,
    )
    try:
        response = await llm.ainvoke(prompt)
    except Exception:
        logger.exception("Risk Analyst: LLM augmentation failed for %s", ticker)
        return {"risk_analysis": {"error": f"LLM augmentation failed for {ticker}"}}
    augmented_yaml = (
        response.content if isinstance(response.content, str) else str(response.content)
    )
    augmented_yaml = _strip_fences(augmented_yaml)

    # Validate with self-correction
    augmented_yaml, passed = await _validate_loop(
        augmented_yaml,
        ticker,
        llm=llm,
        validate=validate,
    )
    if not passed:
        return {
            "risk_analysis": {"error": f"Validation failed after {MAX_RETRIES} attempts"},
        }

    # Run all three risk analyses
    risk_data = await _run_risk_tools(
        augmented_yaml,
        ticker,
        simulate=simulate,
        tornado=tornado_tool,
        break_even=break_even,
    )
    return {"risk_analysis": risk_data}
