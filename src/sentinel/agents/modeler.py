"""Modeler agent -- builds a Forge YAML model from extracted earnings data."""

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

GENERATION_PROMPT = """\
You are a financial modeler.  Given the earnings data below, generate a
Forge v5.0.0 YAML model that calculates key financial metrics.

EARNINGS DATA:
{earnings_json}

Generate a YAML model with this structure:

```yaml
_forge_version: "5.0.0"

inputs:
  revenue:
    value: <from data>
    formula: null
  cost_of_revenue:
    value: <from data>
    formula: null
  operating_expenses:
    value: <from data>
    formula: null
  net_income:
    value: <from data or null>
    formula: null
  shares_outstanding:
    value: <from data or null>
    formula: null

outputs:
  gross_profit:
    value: null
    formula: "=inputs.revenue - inputs.cost_of_revenue"
  operating_income:
    value: null
    formula: "=outputs.gross_profit - inputs.operating_expenses"
  gross_margin:
    value: null
    formula: "=outputs.gross_profit / inputs.revenue"
  operating_margin:
    value: null
    formula: "=outputs.operating_income / inputs.revenue"
  net_margin:
    value: null
    formula: "=inputs.net_income / inputs.revenue"
```

Rules:
- Use `_forge_version: "5.0.0"`.
- Every field MUST have both `value` and `formula` keys.
- Input fields: `formula: null`, `value: <number>`.
- Output fields: `value: null`, `formula: "=<expression>"`.
- Formulas reference other fields with `group.field` syntax.
- Only use data provided -- do NOT invent numbers.
- Use raw numbers (not formatted): 94800 not "$94.8B".
- If a value is null/missing, omit that input and any outputs depending on it.
- Return ONLY the YAML content, no markdown fences, no commentary.
"""

CORRECTION_PROMPT = """\
The Forge model you generated has validation errors:

{errors}

Here is the model you generated:
{model_yaml}

Fix the errors and return the corrected YAML.  Return ONLY the YAML content,
no markdown fences, no commentary.
"""


def _text_from(result: list[dict[str, Any]]) -> str:
    """Extract text from MCP tool result content blocks."""
    return " ".join(block["text"] for block in result if block.get("type") == "text")


async def _validate_loop(
    model_yaml: str,
    ticker: str,
    *,
    llm: BaseChatModel,
    validate: BaseTool,
) -> tuple[str, bool]:
    """Run the self-correction loop: validate -> fix -> retry.

    Returns the (possibly corrected) YAML and whether validation passed.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        model_path = _write_temp_yaml(model_yaml, ticker)
        try:
            try:
                val_result = await validate.ainvoke({"file_path": str(model_path)})
                val_text = _text_from(val_result)
            except Exception:
                logger.exception(
                    "Modeler agent: forge_validate failed (attempt %d)",
                    attempt,
                )
                continue

            val_data = json.loads(val_text)
            if val_data.get("tables_valid") and val_data.get("scalars_valid"):
                logger.info("Modeler agent: validation passed (attempt %d)", attempt)
                return model_yaml, True

            logger.warning(
                "Modeler agent: validation failed (attempt %d): %s",
                attempt,
                val_text[:200],
            )

            if attempt < MAX_RETRIES:
                correction = CORRECTION_PROMPT.format(
                    errors=val_text,
                    model_yaml=model_yaml,
                )
                try:
                    response = await llm.ainvoke(correction)
                except Exception:
                    logger.exception(
                        "Modeler agent: LLM correction failed (attempt %d)",
                        attempt,
                    )
                    continue
                model_yaml = (
                    response.content
                    if isinstance(response.content, str)
                    else str(response.content)
                )
                model_yaml = _strip_fences(model_yaml)
        finally:
            _cleanup(model_path)

    logger.error("Modeler agent: validation failed after %d attempts", MAX_RETRIES)
    return model_yaml, False


async def _run_calculate(
    model_yaml: str,
    ticker: str,
    *,
    calculate: BaseTool,
) -> dict[str, Any]:
    """Run forge_calculate and return the results dict."""
    model_path = _write_temp_yaml(model_yaml, ticker)
    try:
        try:
            calc_result = await calculate.ainvoke({"file_path": str(model_path)})
        except Exception:
            logger.exception("Modeler agent: forge_calculate failed for %s", ticker)
            return {"error": f"forge_calculate failed for {ticker}"}
        calc_text = _text_from(calc_result)
        logger.info("Modeler agent: calculation complete for %s", ticker)
        forge_results = _parse_calc_results(calc_text)
        forge_results["raw_output"] = calc_text
    finally:
        _cleanup(model_path)
    return forge_results


async def modeler_node(state: SentinelState) -> dict[str, Any]:
    """Generate, validate, and calculate a Forge model from earnings data.

    Includes a self-correction loop: if ``forge_validate`` returns errors,
    the model is revised up to :data:`MAX_RETRIES` times.

    Returns
    -------
    dict
        Partial state update with ``model_yaml`` and ``forge_results``.

    """
    raw_data = state["raw_data"]
    ticker = state["ticker"]

    if "error" in raw_data:
        logger.error(
            "Modeler agent: skipping -- research returned error: %s",
            raw_data["error"],
        )
        return {"model_yaml": "", "forge_results": {"error": raw_data["error"]}}

    logger.info("Modeler agent: generating Forge model for %s", ticker)

    llm = get_llm(max_tokens=4096)
    tools = await get_forge_tools()

    validate = next(t for t in tools if t.name == "forge_validate")
    calculate = next(t for t in tools if t.name == "forge_calculate")

    # Generate initial YAML
    prompt = GENERATION_PROMPT.format(earnings_json=json.dumps(raw_data, indent=2))
    try:
        response = await llm.ainvoke(prompt)
    except Exception:
        logger.exception("Modeler agent: LLM generation failed for %s", ticker)
        return {
            "model_yaml": "",
            "forge_results": {"error": f"LLM generation failed for {ticker}"},
        }
    model_yaml = response.content if isinstance(response.content, str) else str(response.content)
    model_yaml = _strip_fences(model_yaml)

    # Validate with self-correction
    model_yaml, passed = await _validate_loop(
        model_yaml,
        ticker,
        llm=llm,
        validate=validate,
    )
    if not passed:
        return {
            "model_yaml": model_yaml,
            "forge_results": {"error": f"Validation failed after {MAX_RETRIES} attempts"},
        }

    # Calculate
    forge_results = await _run_calculate(model_yaml, ticker, calculate=calculate)
    return {"model_yaml": model_yaml, "forge_results": forge_results}


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
    fd, path = tempfile.mkstemp(suffix=".yaml", prefix=f"sentinel-{prefix}-")
    with open(fd, "w") as fh:  # noqa: PTH123
        fh.write(content)
    return Path(path)


def _cleanup(path: Path) -> None:
    """Remove a temp YAML file and its Forge backup."""
    path.unlink(missing_ok=True)
    bak = path.with_suffix(".yaml.bak")
    bak.unlink(missing_ok=True)


def _parse_calc_results(text: str) -> dict[str, Any]:
    """Parse Forge calculation output into a structured dict.

    Forge MCP returns JSON with ``scalars`` and ``tables`` keys.
    """
    data = json.loads(text)
    return dict(data.get("scalars", {}))
