"""Synthesizer agent -- produces an executive brief from Forge results."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from sentinel.llm import get_llm

if TYPE_CHECKING:
    from sentinel.graph.state import SentinelState

logger = logging.getLogger(__name__)

SYNTHESIS_PROMPT = """\
You are an investment analyst writing an executive brief.

COMPANY: {ticker}
PERIOD: {period}

EXTRACTED DATA (from public filings):
{raw_data_json}

FORGE CALCULATION RESULTS (deterministic -- these are the authoritative numbers):
{forge_results_json}
{risk_section}\
{scenario_section}\
{history_section}\

Write a concise executive brief ({word_range} words) with these sections:

1. **Overview** -- One sentence on the company and reporting period.
2. **Key Financials** -- Revenue, gross profit, operating income, margins.
   CRITICAL: Use ONLY numbers from the Forge calculation results above.
   Every number must trace back to a specific Forge output field.
3. **Margin Analysis** -- Gross margin, operating margin, trends if data allows.
{extra_sections}\
4. **Assessment** -- Strengths, concerns, and a one-line outlook.

Rules:
- Do NOT invent, estimate, or hallucinate any numbers.
- If a metric is unavailable, say so -- do not fill in approximate figures.
- Format monetary values with $ and appropriate units (e.g. $94.8B, $1.2M).
- Format percentages with %% sign (e.g. 45.2%%).
- Be direct and factual -- this is for an investment professional.
"""

_RISK_DATA = """
RISK ANALYSIS (Monte Carlo + Sensitivity):
{risk_json}
"""

_RISK_SECTIONS = """\
5. **Risk Profile** -- P10/P50/P90 ranges for key metrics from Monte Carlo. \
Top risk drivers from sensitivity (tornado) analysis. Margin of safety.
"""

_SCENARIO_DATA = """
SCENARIO ANALYSIS (Bull / Base / Bear):
{scenario_json}
"""

_SCENARIO_SECTIONS = """\
6. **Scenario Comparison** -- Bull/base/bear outcomes with probabilities. \
Expected value across scenarios. Key break-even thresholds.
"""

_HISTORY_DATA = """
HISTORICAL EARNINGS (past quarters from RAG store, most relevant first):
{history_json}
"""

_HISTORY_SECTIONS = """\
{section_num}. **Historical Trend Analysis** -- Revenue trajectory over prior quarters. \
Margin expansion or compression trend. EPS progression. Year-over-year comparison \
with current quarter vs. prior year same period if available.
"""


def _clean_risk(risk_analysis: dict[str, Any]) -> dict[str, Any]:
    """Remove risk_yaml from risk_analysis before injecting into prompt."""
    return {k: v for k, v in risk_analysis.items() if k != "risk_yaml"}


def _clean_scenario(scenario_analysis: dict[str, Any]) -> dict[str, Any]:
    """Remove scenario_yaml from scenario_analysis before injecting into prompt."""
    return {k: v for k, v in scenario_analysis.items() if k != "scenario_yaml"}


async def synthesizer_node(state: SentinelState) -> dict[str, Any]:
    """Produce an executive brief from earnings data and Forge results.

    When risk and/or scenario analysis data is available, the brief
    includes additional sections and uses a wider word range.

    Returns
    -------
    dict
        Partial state update with ``brief`` populated.

    """
    ticker = state["ticker"]
    raw_data = state.get("raw_data", {})
    forge_results = state.get("forge_results", {})

    if "error" in forge_results:
        logger.error(
            "Synthesizer agent: skipping -- forge returned error: %s",
            forge_results["error"],
        )
        return {
            "brief": f"Analysis incomplete for {ticker}: {forge_results['error']}",
        }

    logger.info("Synthesizer agent: generating brief for %s", ticker)

    risk_analysis = state.get("risk_analysis", {})
    scenario_analysis = state.get("scenario_analysis", {})

    has_risk = bool(risk_analysis) and "error" not in risk_analysis
    has_scenarios = bool(scenario_analysis) and "error" not in scenario_analysis

    risk_section = ""
    scenario_section = ""
    extra_sections = ""

    if has_risk:
        risk_section = _RISK_DATA.format(
            risk_json=json.dumps(_clean_risk(risk_analysis), indent=2),
        )
        extra_sections += _RISK_SECTIONS

    if has_scenarios:
        scenario_section = _SCENARIO_DATA.format(
            scenario_json=json.dumps(_clean_scenario(scenario_analysis), indent=2),
        )
        extra_sections += _SCENARIO_SECTIONS

    historical_context = state.get("historical_context", [])
    has_history = bool(historical_context)

    history_section = ""
    if has_history:
        history_section = _HISTORY_DATA.format(
            history_json=json.dumps(historical_context, indent=2),
        )
        section_num = 4 + int(has_risk) + int(has_scenarios)
        extra_sections += _HISTORY_SECTIONS.format(section_num=section_num)

    word_range = "400-700" if (has_risk or has_scenarios or has_history) else "300-500"

    # Remove raw_output from forge_results for the prompt (verbose)
    forge_clean = {k: v for k, v in forge_results.items() if k != "raw_output"}

    llm = get_llm()
    prompt = SYNTHESIS_PROMPT.format(
        ticker=ticker,
        period=raw_data.get("period", "Unknown"),
        raw_data_json=json.dumps(raw_data, indent=2),
        forge_results_json=json.dumps(forge_clean, indent=2),
        risk_section=risk_section,
        scenario_section=scenario_section,
        history_section=history_section,
        extra_sections=extra_sections,
        word_range=word_range,
    )

    try:
        response = await llm.ainvoke(prompt)
    except Exception:
        logger.exception("Synthesizer agent: LLM call failed for %s", ticker)
        return {"brief": f"Analysis incomplete for {ticker}: LLM call failed"}
    brief = response.content if isinstance(response.content, str) else str(response.content)

    logger.info(
        "Synthesizer agent: brief complete for %s (%d chars)",
        ticker,
        len(brief),
    )
    return {"brief": brief}
