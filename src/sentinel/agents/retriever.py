"""Retriever agent -- reads earlier runs for the ticker from the repository.

Each run is a folder ``runs/<TICKER>/<timestamp>/`` committed to git (ADR-012), so
history is the ``raw_data.json`` of earlier runs, not a vector store.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from sentinel.output import DEFAULT_OUTPUT_DIR
from sentinel.validation import validate_ticker

if TYPE_CHECKING:
    from pathlib import Path

    from sentinel.graph.state import SentinelState

logger = logging.getLogger(__name__)

TOP_K = 4
"""At most this many earlier periods are passed to the Synthesizer."""

_HISTORY_FIELDS = (
    "period",
    "revenue",
    "cost_of_revenue",
    "gross_profit",
    "operating_expenses",
    "operating_income",
    "net_income",
    "eps",
)


def earlier_runs(
    ticker: str,
    current_period: str,
    *,
    runs_dir: Path = DEFAULT_OUTPUT_DIR,
    top_k: int = TOP_K,
) -> list[dict[str, Any]]:
    """Return the newest good run of each earlier period for *ticker*, newest first.

    A run counts when its ``raw_data.json`` parses, has no ``error`` and is for a
    period other than *current_period*.  Unreadable runs are skipped, never fatal.
    """
    folder = runs_dir / validate_ticker(ticker)
    if not folder.is_dir():
        return []
    seen: set[str] = set()
    history: list[dict[str, Any]] = []
    for run in sorted((p for p in folder.iterdir() if p.is_dir()), reverse=True):
        data = _read(run / "raw_data.json")
        period = str((data.get("input") or {}).get("period") or data.get("period") or "")
        if not data or "error" in data or not period or period == current_period:
            continue
        if period in seen:
            continue
        seen.add(period)
        history.append({key: data.get(key) for key in _HISTORY_FIELDS} | {"run": run.name})
        if len(history) == top_k:
            break
    return history


def _read(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


async def retriever_node(state: SentinelState) -> dict[str, Any]:
    """Return earlier periods of this ticker as ``historical_context``.

    Any failure, or no earlier run, gives ``{"historical_context": []}``.
    """
    raw_data = state.get("raw_data", {})
    ticker = state.get("ticker", "")
    if "error" in raw_data:
        logger.warning("Retriever agent: skipping -- research returned error for %s", ticker)
        return {"historical_context": []}

    current = str((raw_data.get("input") or {}).get("period") or raw_data.get("period") or "")
    try:
        history = earlier_runs(ticker, current)
    except (OSError, ValueError):
        logger.exception("Retriever agent: could not read earlier runs for %s", ticker)
        return {"historical_context": []}
    logger.info("Retriever agent: %d earlier period(s) for %s", len(history), ticker)
    return {"historical_context": history}
