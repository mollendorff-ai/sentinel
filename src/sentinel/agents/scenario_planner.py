"""Scenario Planner agent -- generates Bull/Base/Bear scenarios from a Forge model."""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sentinel.llm import get_llm
from sentinel.tools.forge_mcp import get_forge_tools

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool

    from sentinel.graph.state import SentinelState

logger = logging.getLogger(__name__)

MAX_RETRIES = 3

SCENARIO_AUGMENTATION_PROMPT = """\
You are a financial scenario analyst.  Given the Forge v5.0.0 YAML model below,
augment it with a ``scenarios:`` section containing Bull, Base, and Bear cases.

CURRENT MODEL:
{model_yaml}

EARNINGS DATA:
{earnings_json}

Add a ``scenarios:`` section with this structure:

```yaml
scenarios:
  - name: Bull
    probability: 0.25
    scalars:
      inputs.revenue: <+10-15% from base>
      inputs.cost_of_revenue: <adjust proportionally>
      inputs.operating_expenses: <same or slightly lower>
  - name: Base
    probability: 0.50
    scalars:
      inputs.revenue: <current value>
      inputs.cost_of_revenue: <current value>
      inputs.operating_expenses: <current value>
  - name: Bear
    probability: 0.25
    scalars:
      inputs.revenue: <-10-15% from base>
      inputs.cost_of_revenue: <adjust proportionally>
      inputs.operating_expenses: <same or slightly higher>
```

Rules:
- Probabilities MUST sum to 1.0.
- Bull case: revenue +10-15%, cost adjusts proportionally, opex flat or lower.
- Base case: current values from the model inputs.
- Bear case: revenue -10-15%, cost adjusts proportionally, opex flat or higher.
- Calibrate from management guidance in the earnings data if available.
- Only use scalar keys that exist in the model ``inputs:`` section.
- Preserve ALL existing sections (inputs, outputs, monte_carlo, tornado, etc.).
- Return ONLY the complete YAML content, no markdown fences, no commentary.
"""

CORRECTION_PROMPT = """\
The augmented Forge model has validation errors:

{errors}

Here is the model you generated:
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
    fd, path = tempfile.mkstemp(suffix=".yaml", prefix=f"sentinel-{prefix}-")
    with open(fd, "w") as fh:  # noqa: PTH123
        fh.write(content)
    return Path(path)


def _cleanup(path: Path) -> None:
    """Remove a temp YAML file and its Forge backup."""
    path.unlink(missing_ok=True)
    bak = path.with_suffix(".yaml.bak")
    bak.unlink(missing_ok=True)


async def scenario_planner_node(state: SentinelState) -> dict[str, Any]:
    """Generate Bull/Base/Bear scenarios and run scenario analysis.

    Augments an existing Forge YAML model with a ``scenarios:`` section,
    then runs ``forge_scenarios``, ``forge_compare``, and ``forge_break_even``.
    Includes a self-correction loop: if ``forge_validate`` returns errors,
    the model is revised up to :data:`MAX_RETRIES` times.

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
    logger.info("Scenario Planner: generating scenarios for %s", ticker)

    llm = get_llm(max_tokens=4096)
    tools = await get_forge_tools()

    forge_validate = next(t for t in tools if t.name == "forge_validate")
    forge_scenarios = next(t for t in tools if t.name == "forge_scenarios")
    forge_compare = next(t for t in tools if t.name == "forge_compare")
    forge_break_even = next(t for t in tools if t.name == "forge_break_even")

    # Use risk-augmented YAML if available, otherwise fall back to model_yaml
    risk_analysis = state.get("risk_analysis", {})
    base_yaml = risk_analysis.get("risk_yaml", state["model_yaml"])

    raw_data = state.get("raw_data", {})

    # LLM generates augmented YAML with scenarios section
    prompt = SCENARIO_AUGMENTATION_PROMPT.format(
        model_yaml=base_yaml,
        earnings_json=json.dumps(raw_data, indent=2),
    )
    response = await llm.ainvoke(prompt)
    augmented_yaml = (
        response.content if isinstance(response.content, str) else str(response.content)
    )
    augmented_yaml = _strip_fences(augmented_yaml)

    # Self-correction loop: validate -> fix -> retry
    for attempt in range(1, MAX_RETRIES + 1):
        model_path = _write_temp_yaml(augmented_yaml, f"{ticker}-scenario")
        try:
            val_result = await forge_validate.ainvoke({"file_path": str(model_path)})
            val_text = _text_from(val_result)

            val_data = json.loads(val_text)
            if val_data.get("tables_valid") and val_data.get("scalars_valid"):
                logger.info(
                    "Scenario Planner: validation passed (attempt %d)",
                    attempt,
                )
                break

            logger.warning(
                "Scenario Planner: validation failed (attempt %d): %s",
                attempt,
                val_text[:200],
            )

            if attempt < MAX_RETRIES:
                correction = CORRECTION_PROMPT.format(
                    errors=val_text,
                    model_yaml=augmented_yaml,
                )
                response = await llm.ainvoke(correction)
                augmented_yaml = (
                    response.content
                    if isinstance(response.content, str)
                    else str(response.content)
                )
                augmented_yaml = _strip_fences(augmented_yaml)
        finally:
            _cleanup(model_path)
    else:
        logger.error(
            "Scenario Planner: validation failed after %d attempts",
            MAX_RETRIES,
        )
        return {
            "scenario_analysis": {
                "error": f"Validation failed after {MAX_RETRIES} attempts",
            },
        }

    return await _run_scenario_tools(
        augmented_yaml,
        ticker,
        forge_scenarios=forge_scenarios,
        forge_compare=forge_compare,
        forge_break_even=forge_break_even,
    )


async def _run_scenario_tools(
    augmented_yaml: str,
    ticker: str,
    *,
    forge_scenarios: BaseTool,
    forge_compare: BaseTool,
    forge_break_even: BaseTool,
) -> dict[str, Any]:
    """Run forge_scenarios, forge_compare, and forge_break_even on augmented YAML."""
    model_path = _write_temp_yaml(augmented_yaml, f"{ticker}-scenario")
    try:
        scenarios_result = await forge_scenarios.ainvoke({"file_path": str(model_path)})
        scenarios_data = json.loads(_text_from(scenarios_result))

        compare_result = await forge_compare.ainvoke(
            {
                "file_path": str(model_path),
                "scenarios": ["Bull", "Base", "Bear"],
            },
        )
        compare_data = json.loads(_text_from(compare_result))

        break_even_result = await forge_break_even.ainvoke(
            {
                "file_path": str(model_path),
                "output": "outputs.operating_income",
                "vary": "inputs.revenue",
            },
        )
        break_even_data = json.loads(_text_from(break_even_result))

        logger.info("Scenario Planner: analysis complete for %s", ticker)
    finally:
        _cleanup(model_path)

    return {
        "scenario_analysis": {
            "scenarios": scenarios_data.get("scenarios", []),
            "expected_values": scenarios_data.get("expected_values", {}),
            "comparison": compare_data,
            "break_even_thresholds": break_even_data,
            "scenario_yaml": augmented_yaml,
        },
    }
