"""Retriever agent — queries Qdrant for historical earnings context."""

from __future__ import annotations

import logging
from typing import Any

from sentinel.graph.state import SentinelState
from sentinel.rag.store import create_store, retrieve

logger = logging.getLogger(__name__)


async def retriever_node(state: SentinelState) -> dict[str, Any]:
    """Query Qdrant for historical earnings data matching the current ticker.

    Reads ``raw_data`` from state (populated by the Research agent) and
    returns up to 4 historical quarters as ``historical_context``.

    Graceful degradation: any failure (first run, Qdrant unavailable,
    no history yet) returns ``{"historical_context": []}`` rather than
    raising an exception.

    Parameters
    ----------
    state
        Current pipeline state.  Must contain ``raw_data`` (from Research)
        and ``ticker``.

    Returns
    -------
    dict
        Partial state update with ``historical_context`` populated.

    """
    raw_data = state.get("raw_data", {})
    ticker = raw_data.get("ticker") or state.get("ticker", "")
    period = raw_data.get("period", "")

    if "error" in raw_data:
        logger.warning(
            "Retriever agent: skipping — research returned error for %s", ticker
        )
        return {"historical_context": []}

    logger.info(
        "Retriever agent: querying history for %s (current: %s)", ticker, period
    )

    try:
        client = create_store()
        history = retrieve(client, ticker, period)
    except Exception:
        logger.exception("Retriever agent: Qdrant unavailable for %s", ticker)
        return {"historical_context": []}

    return {"historical_context": history}
