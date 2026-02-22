"""Research agent -- fetches earnings data and extracts structured financials."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from sentinel.llm import get_llm
from sentinel.tools.ref_fetch import RefFetchTool

if TYPE_CHECKING:
    from sentinel.graph.state import SentinelState

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """\
You are a financial data extraction specialist.

Given the raw web content below, extract the most recent quarterly or annual
earnings data for **{ticker}**.  Return ONLY a valid JSON object (no markdown
fences, no commentary) with these fields:

{{
  "company": "<full company name>",
  "ticker": "{ticker}",
  "period": "<e.g. Q1 2026 or FY 2025>",
  "currency": "USD",
  "revenue": <number or null>,
  "cost_of_revenue": <number or null>,
  "gross_profit": <number or null>,
  "operating_expenses": <number or null>,
  "operating_income": <number or null>,
  "net_income": <number or null>,
  "eps": <number or null>,
  "revenue_growth_yoy": <decimal or null>,
  "gross_margin": <decimal or null>,
  "operating_margin": <decimal or null>,
  "guidance_revenue_low": <number or null>,
  "guidance_revenue_high": <number or null>,
  "source_url": "<URL where data was found>"
}}

Rules:
- All monetary values in millions (e.g. 94800 means $94.8B).
- Growth rates and margins as decimals (e.g. 0.12 = 12%).
- Use null for any field you cannot confidently extract.
- Do NOT invent or estimate numbers -- only use what is explicitly stated.

Web content:
{content}
"""

_EARNINGS_URLS = [
    "https://www.macrotrends.net/stocks/charts/{ticker_lower}/{slug}/revenue",
    "https://www.macrotrends.net/stocks/charts/{ticker_lower}/{slug}/income-statement",
]

_TICKER_SLUGS: dict[str, str] = {
    "AAPL": "apple",
    "MSFT": "microsoft",
    "GOOG": "alphabet",
    "GOOGL": "alphabet",
    "AMZN": "amazon",
    "META": "meta-platforms",
    "NVDA": "nvidia",
    "TSLA": "tesla",
}


def _build_urls(ticker: str) -> list[str]:
    """Build earnings research URLs for a given ticker."""
    slug = _TICKER_SLUGS.get(ticker.upper(), ticker.lower())
    return [url.format(ticker_lower=ticker.lower(), slug=slug) for url in _EARNINGS_URLS]


async def research_node(state: SentinelState) -> dict[str, Any]:
    """Fetch earnings data for *ticker* and extract structured financials.

    Returns
    -------
    dict
        Partial state update with ``raw_data`` populated.

    """
    ticker = state["ticker"]
    logger.info("Research agent: fetching earnings for %s", ticker)

    ref = RefFetchTool()
    urls = _build_urls(ticker)

    # Fetch pages and combine content
    combined_content: list[str] = []
    source_url = ""

    for url in urls:
        result = await ref._arun(url)  # noqa: SLF001
        if result.get("status") == "ok":
            source_url = source_url or url
            sections = result.get("sections", [])
            for section in sections:
                heading = section.get("heading", "")
                body = section.get("text", "")
                if heading:
                    combined_content.append(f"## {heading}\n{body}")
                elif body:
                    combined_content.append(body)
            logger.info(
                "Research agent: fetched %s (%d sections)",
                url,
                len(sections),
            )
        else:
            logger.warning(
                "Research agent: failed to fetch %s: %s",
                url,
                result.get("error", "unknown"),
            )

    if not combined_content:
        logger.error("Research agent: no content retrieved for %s", ticker)
        return {"raw_data": {"error": f"No earnings data found for {ticker}", "ticker": ticker}}

    # Extract financials via Claude
    llm = get_llm()
    prompt = EXTRACTION_PROMPT.format(
        ticker=ticker,
        content="\n\n".join(combined_content)[:50000],
    )

    response = await llm.ainvoke(prompt)
    raw_text = response.content if isinstance(response.content, str) else str(response.content)

    try:
        raw_data: dict[str, Any] = json.loads(raw_text)
    except json.JSONDecodeError:
        logger.warning("Research agent: Claude returned non-JSON, attempting extraction")
        start = raw_text.find("{")
        end = raw_text.rfind("}") + 1
        if start >= 0 and end > start:
            raw_data = json.loads(raw_text[start:end])
        else:
            raw_data = {
                "error": "Failed to parse extraction response",
                "raw_response": raw_text[:500],
            }

    raw_data["source_url"] = raw_data.get("source_url", source_url)
    logger.info(
        "Research agent: extracted data for %s (%s)",
        ticker,
        raw_data.get("period", "unknown period"),
    )
    return {"raw_data": raw_data}
