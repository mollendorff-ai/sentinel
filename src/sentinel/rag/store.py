"""Qdrant vector store — historical earnings ingestion and retrieval."""

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path
from typing import Any

from qdrant_client import QdrantClient

logger = logging.getLogger(__name__)

COLLECTION_NAME = "earnings"
DEFAULT_QDRANT_PATH = Path(".sentinel/qdrant")
TOP_K = 4


def _qdrant_path() -> Path:
    """Return Qdrant persistence path from env or default."""
    raw = os.environ.get("SENTINEL_QDRANT_PATH")
    return Path(raw) if raw else DEFAULT_QDRANT_PATH


def create_store(path: Path | None = None) -> QdrantClient:
    """Create (or open) a local Qdrant store.

    Parameters
    ----------
    path
        Directory for Qdrant on-disk persistence.  When ``None``, uses
        :func:`_qdrant_path`.

    Returns
    -------
    QdrantClient
        A Qdrant client backed by local disk.  The collection is created
        automatically on first :func:`ingest` call (fastembed owns dimensions).

    """
    resolved = path if path is not None else _qdrant_path()
    resolved.mkdir(parents=True, exist_ok=True)
    logger.info("Qdrant store: opening at %s", resolved)
    return QdrantClient(path=str(resolved))


def _point_id(ticker: str, period: str) -> str:
    """Stable UUID5 from ticker:period for idempotent upsert."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{ticker}:{period}"))


def _to_text(raw_data: dict[str, Any]) -> str:
    """Serialise raw_data to a flat text representation for embedding."""
    numeric_fields = [
        "revenue",
        "cost_of_revenue",
        "gross_profit",
        "operating_expenses",
        "operating_income",
        "net_income",
        "eps",
        "revenue_growth_yoy",
        "gross_margin",
        "operating_margin",
    ]
    parts = [
        f"ticker={raw_data.get('ticker', '')}",
        f"period={raw_data.get('period', '')}",
        f"company={raw_data.get('company', '')}",
    ]
    for field in numeric_fields:
        val = raw_data.get(field)
        if val is not None:
            parts.append(f"{field}={val}")
    return " ".join(parts)


def ingest(client: QdrantClient, raw_data: dict[str, Any]) -> bool:
    """Upsert one earnings record into Qdrant.

    Uses a stable UUID5 point ID derived from ``ticker:period`` so
    repeated ingestion of the same quarter is idempotent.

    Parameters
    ----------
    client
        An open :class:`QdrantClient` instance.
    raw_data
        The structured earnings dict from the Research agent.

    Returns
    -------
    bool
        ``True`` on success, ``False`` on any exception (graceful degradation).

    """
    ticker = raw_data.get("ticker", "")
    period = raw_data.get("period", "")

    if not ticker or not period:
        logger.warning("Qdrant ingest: skipping — missing ticker or period")
        return False

    point_id = _point_id(ticker, period)
    text = _to_text(raw_data)

    try:
        client.add(
            collection_name=COLLECTION_NAME,
            documents=[text],
            metadata=[{"ticker": ticker, "period": period, **raw_data}],
            ids=[point_id],
        )
        logger.info("Qdrant ingest: upserted %s %s (id=%s)", ticker, period, point_id)
        return True
    except Exception:
        logger.exception("Qdrant ingest: failed for %s %s", ticker, period)
        return False


def retrieve(
    client: QdrantClient,
    ticker: str,
    current_period: str,
    *,
    top_k: int = TOP_K,
) -> list[dict[str, Any]]:
    """Query Qdrant for the most relevant historical quarters.

    Parameters
    ----------
    client
        An open :class:`QdrantClient` instance.
    ticker
        The company ticker symbol (e.g. ``"AAPL"``).
    current_period
        The current reporting period to *exclude* from results.
    top_k
        Maximum number of historical records to return.

    Returns
    -------
    list[dict[str, Any]]
        Payloads for the top-k nearest historical records, ordered by
        similarity.  Empty list on failure or no history.

    """
    query_text = f"ticker={ticker} period={current_period}"

    try:
        hits = client.query(
            collection_name=COLLECTION_NAME,
            query_text=query_text,
            limit=top_k + 1,
        )
    except Exception:
        logger.warning(
            "Qdrant retrieve: no history for %s (collection may not exist yet)", ticker
        )
        return []

    results = []
    for hit in hits:
        payload = hit.metadata if hasattr(hit, "metadata") else {}
        if payload.get("period") == current_period:
            continue
        results.append(payload)
        if len(results) >= top_k:
            break

    logger.info("Qdrant retrieve: %d records for %s", len(results), ticker)
    return results
