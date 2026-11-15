"""Modeler agent -- builds a Forge YAML model from extracted earnings data."""

from __future__ import annotations

import json
import logging
import re
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sentinel.inputs import InputError, compare_with_results, load_input
from sentinel.llm import get_llm
from sentinel.tools.forge_mcp import get_forge_tools
from sentinel.tools.forge_text import parse_json
from sentinel.tools.risk_models import ModelShapeError, load_model

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel
    from langchain_core.tools import BaseTool

    from sentinel.graph.state import SentinelState

logger = logging.getLogger(__name__)

MAX_RETRIES = 3

MODEL_FIGURES = (
    "company",
    "ticker",
    "period",
    "currency",
    "revenue",
    "cost_of_revenue",
    "operating_expenses",
    "net_income",
)
"""What the Modeler is shown of the extraction: the four inputs, not the printed subtotals."""

_NUMBER_IN_FORMULA = re.compile(r"(?<![A-Za-z_.\d])\d")

GENERATION_PROMPT = """\
You are a financial modeler.  Given the earnings data below, write a Forge model
(model format 5.1.0) that calculates the quarter's key metrics.  Forge does the
arithmetic: you write the formulas, never their results.

EARNINGS DATA:
{earnings_json}

The model has two groups.

`inputs` holds four figures, each a plain number copied from the data:
revenue, cost_of_revenue, operating_expenses, net_income.

`outputs` holds five results, each a formula over the inputs and other outputs:
- gross_profit: what the statements of operations call gross margin, in dollars
- operating_income: as the statements of operations define it
- gross_margin: gross profit as a share of revenue (0.25 means 25%)
- operating_margin: operating income as a share of revenue
- net_margin: net income as a share of revenue

Forge's format:
- The first line is `_forge_version: "5.1.0"`.
- An input is a plain number: `revenue: 94800`.  Use raw numbers, not "$94.8B".
- An output is `{{formula: "=<expression>"}}`, written like an Excel formula; never
  write its value.
- A formula names a field as `group.field`, for example `inputs.revenue`.
- Use only the four figures in the data; do NOT invent numbers.  If one is null or
  missing, leave it out, and leave out every output that needs it.
- Return ONLY the YAML content, no markdown fences, no commentary.

Sentinel compares two of Forge's results with the subtotals the filing prints, so
a wrong formula stops the run.
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

            val_data = parse_json(val_text)
            if val_data and val_data.get("tables_valid") and val_data.get("scalars_valid"):
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

    llm = get_llm(max_tokens=4096, role="modeler")
    tools = await get_forge_tools()

    validate = next(t for t in tools if t.name == "forge_validate")
    calculate = next(t for t in tools if t.name == "forge_calculate")

    # Generate initial YAML
    earnings = {key: raw_data[key] for key in MODEL_FIGURES if key in raw_data}
    prompt = GENERATION_PROMPT.format(earnings_json=json.dumps(earnings, indent=2))
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

    # Calculate, then check the formulas against the subtotals the filing prints
    forge_results = await _run_calculate(model_yaml, ticker, calculate=calculate)
    if "error" not in forge_results:
        typed = typed_results(model_yaml)
        if typed:
            forge_results["error"] = "A result is typed, not calculated: " + "; ".join(typed)
        else:
            _check_against_filing(forge_results, ticker, state.get("period") or None)
    return {"model_yaml": model_yaml, "forge_results": forge_results}


def typed_results(model_yaml: str) -> list[str]:
    """Return one line per output whose formula holds a number: a result typed in, not calculated.

    The five outputs are sums and ratios of the inputs, so none needs a number of its
    own; ``=54820`` would pass the filing check while calculating nothing.
    """
    try:
        outputs = load_model(model_yaml).get("outputs")
    except ModelShapeError as exc:
        return [str(exc)]
    if not isinstance(outputs, dict):
        return ["the model has no outputs"]
    problems: list[str] = []
    for name, field in outputs.items():
        formula = field.get("formula") if isinstance(field, dict) else field
        if not isinstance(formula, str) or _NUMBER_IN_FORMULA.search(formula):
            problems.append(f"outputs.{name} is {formula!r}")
    return problems


def _check_against_filing(forge_results: dict[str, Any], ticker: str, period: str | None) -> None:
    """Compare Forge's results with the filing's printed subtotals; set ``error`` on a difference.

    A model with a wrong formula validates and calculates; only the filing can say
    the formula is wrong (the evaluation of 2026-11-15 found this hole).
    """
    try:
        expected = load_input(ticker, period).expected
    except (InputError, ValueError, OSError) as exc:
        forge_results["error"] = f"Cannot check Forge's results against the filing: {exc}"
        return
    problems = compare_with_results(forge_results, expected)
    forge_results["filing_check"] = {"checked": sorted(expected.results), "mismatches": problems}
    if problems:
        logger.error("Modeler agent: Forge's results differ from the filing: %s", problems)
        forge_results["error"] = "Forge's results differ from the filing: " + "; ".join(problems)
    else:
        logger.info("Modeler agent: %d results equal the filing's", len(expected.results))


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
    data = parse_json(text)
    if data is None:
        return {"error": f"forge_calculate failed: {text.strip()[:400]}"}
    return dict(data.get("scalars", {}))
