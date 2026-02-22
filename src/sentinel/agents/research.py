"""Research agent -- fetches earnings data and extracts structured financials."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from sentinel.llm import get_llm
from sentinel.tools.ref_mcp import get_ref_tools

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


def _text_from(result: list[dict[str, Any]]) -> str:
    """Extract text from MCP tool result content blocks."""
    return " ".join(block["text"] for block in result if block.get("type") == "text")


def _extract_page_content(pages: list[dict[str, Any]]) -> tuple[list[str], str]:
    """Extract combined text content and source URL from fetched pages."""
    combined: list[str] = []
    source_url = ""
    for page in pages:
        if page.get("status") != "ok":
            logger.warning(
                "Research agent: failed to fetch %s: %s",
                page.get("url", "unknown"),
                page.get("error", "unknown"),
            )
            continue
        source_url = source_url or page.get("url", "")
        for section in page.get("sections", []):
            heading = section.get("heading", "")
            body = section.get("text", "")
            if heading:
                combined.append(f"## {heading}\n{body}")
            elif body:
                combined.append(body)
        logger.info(
            "Research agent: fetched %s (%d sections)",
            page.get("url", "unknown"),
            len(page.get("sections", [])),
        )
    return combined, source_url


def _parse_llm_response(response_text: str) -> dict[str, Any]:
    """Parse LLM response text into a structured dict, tolerating non-clean JSON."""
    try:
        return dict(json.loads(response_text))
    except json.JSONDecodeError:
        logger.warning("Research agent: Claude returned non-JSON, attempting extraction")
        start = response_text.find("{")
        end = response_text.rfind("}") + 1
        if start >= 0 and end > start:
            return dict(json.loads(response_text[start:end]))
        return {
            "error": "Failed to parse extraction response",
            "raw_response": response_text[:500],
        }


async def research_node(state: SentinelState) -> dict[str, Any]:
    """Fetch earnings data for *ticker* and extract structured financials.

    Returns
    -------
    dict
        Partial state update with ``raw_data`` populated.

    """
    ticker = state["ticker"]
    logger.info("Research agent: fetching earnings for %s", ticker)

    tools = await get_ref_tools()
    ref_fetch = next(t for t in tools if t.name == "ref_fetch")
    urls = _build_urls(ticker)

    # Batch all URLs in one MCP call
    try:
        mcp_result = await ref_fetch.ainvoke({"urls": urls, "timeout": 30000})
    except Exception:
        logger.exception("Research agent: ref_fetch failed for %s", ticker)
        return {"raw_data": {"error": f"ref_fetch failed for {ticker}", "ticker": ticker}}
    raw_text = _text_from(mcp_result)

    # Parse the JSON response -- single dict for 1 URL, array for multiple
    try:
        parsed = json.loads(raw_text)
    except (json.JSONDecodeError, TypeError):
        logger.exception("Research agent: failed to parse ref_fetch response for %s", ticker)
        return {"raw_data": {"error": f"No earnings data found for {ticker}", "ticker": ticker}}

    pages: list[dict[str, Any]] = parsed if isinstance(parsed, list) else [parsed]
    combined_content, source_url = _extract_page_content(pages)

    if not combined_content:
        logger.error("Research agent: no content retrieved for %s", ticker)
        return {"raw_data": {"error": f"No earnings data found for {ticker}", "ticker": ticker}}

    # Extract financials via LLM
    llm = get_llm()
    prompt = EXTRACTION_PROMPT.format(
        ticker=ticker,
        content="\n\n".join(combined_content)[:50000],
    )

    try:
        response = await llm.ainvoke(prompt)
    except Exception:
        logger.exception("Research agent: LLM extraction failed for %s", ticker)
        return {"raw_data": {"error": f"LLM extraction failed for {ticker}", "ticker": ticker}}
    response_text = (
        response.content if isinstance(response.content, str) else str(response.content)
    )

    raw_data = _parse_llm_response(response_text)
    raw_data["source_url"] = raw_data.get("source_url", source_url)
    logger.info(
        "Research agent: extracted data for %s (%s)",
        ticker,
        raw_data.get("period", "unknown period"),
    )
    return {"raw_data": raw_data}
