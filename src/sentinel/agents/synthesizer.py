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

Write a concise executive brief (300-500 words) with these sections:

1. **Overview** -- One sentence on the company and reporting period.
2. **Key Financials** -- Revenue, gross profit, operating income, margins.
   CRITICAL: Use ONLY numbers from the Forge calculation results above.
   Every number must trace back to a specific Forge output field.
3. **Margin Analysis** -- Gross margin, operating margin, trends if data allows.
4. **Assessment** -- Strengths, concerns, and a one-line outlook.

Rules:
- Do NOT invent, estimate, or hallucinate any numbers.
- If a metric is unavailable, say so -- do not fill in approximate figures.
- Format monetary values with $ and appropriate units (e.g. $94.8B, $1.2M).
- Format percentages with %% sign (e.g. 45.2%%).
- Be direct and factual -- this is for an investment professional.
"""


async def synthesizer_node(state: SentinelState) -> dict[str, Any]:
    """Produce an executive brief from earnings data and Forge results.

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

    # Remove raw_output from forge_results for the prompt (verbose)
    forge_clean = {k: v for k, v in forge_results.items() if k != "raw_output"}

    llm = get_llm()
    prompt = SYNTHESIS_PROMPT.format(
        ticker=ticker,
        period=raw_data.get("period", "Unknown"),
        raw_data_json=json.dumps(raw_data, indent=2),
        forge_results_json=json.dumps(forge_clean, indent=2),
    )

    response = await llm.ainvoke(prompt)
    brief = response.content if isinstance(response.content, str) else str(response.content)

    logger.info(
        "Synthesizer agent: brief complete for %s (%d chars)",
        ticker,
        len(brief),
    )
    return {"brief": brief}
