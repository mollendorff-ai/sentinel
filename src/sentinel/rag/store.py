"""Qdrant store — historical earnings ingestion and retrieval by ticker.

History is looked up by an exact ``ticker`` payload filter, so no embedding model is
needed (``qdrant-client`` 1.20 removed the ``add``/``query`` helpers that used one).
"""

from __future__ import annotations

import logging
import os
import re
import uuid
from pathlib import Path
from typing import Any

from qdrant_client import QdrantClient, models

logger = logging.getLogger(__name__)

COLLECTION_NAME = "earnings"
DEFAULT_QDRANT_PATH = Path(".sentinel/qdrant")
TOP_K = 4
_SCAN_LIMIT = 1000
_VECTOR = [1.0]
"""Qdrant needs a vector per point; lookups use the payload filter, not similarity."""


def _qdrant_path() -> Path:
    """Return Qdrant persistence path from env or default."""
    raw = os.environ.get("SENTINEL_QDRANT_PATH")
    return Path(raw) if raw else DEFAULT_QDRANT_PATH


def create_store(path: Path | None = None) -> QdrantClient:
    """Create (or open) a local Qdrant store.

    Local Qdrant allows one open client per folder, so callers must ``close()``
    the client when they are done.

    Parameters
    ----------
    path
        Directory for Qdrant on-disk persistence.  When ``None``, uses
        :func:`_qdrant_path`.

    Returns
    -------
    QdrantClient
        A Qdrant client backed by local disk.

    """
    resolved = path if path is not None else _qdrant_path()
    resolved.mkdir(parents=True, exist_ok=True)
    logger.info("Qdrant store: opening at %s", resolved)
    return QdrantClient(path=str(resolved))


def _point_id(ticker: str, period: str) -> str:
    """Stable UUID5 from ticker:period for idempotent upsert."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{ticker}:{period}"))


def _period_key(period: str) -> tuple[int, int]:
    """Sort key (year, quarter) for labels like ``Q1 2026`` or ``FY 2025``; unknown → (0, 0)."""
    year = re.search(r"(19|20)\d{2}", period)
    quarter = re.search(r"Q([1-4])", period.upper())
    return (int(year.group()) if year else 0, int(quarter.group(1)) if quarter else 5)


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

    try:
        if not client.collection_exists(COLLECTION_NAME):
            client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=models.VectorParams(
                    size=len(_VECTOR),
                    distance=models.Distance.DOT,
                ),
            )
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=[
                models.PointStruct(
                    id=point_id,
                    vector=_VECTOR,
                    payload={**raw_data, "ticker": ticker, "period": period},
                ),
            ],
        )
        logger.info("Qdrant ingest: upserted %s %s (id=%s)", ticker, period, point_id)
    except (OSError, RuntimeError, ValueError):
        logger.exception("Qdrant ingest: failed for %s %s", ticker, period)
        return False
    else:
        return True


def retrieve(
    client: QdrantClient,
    ticker: str,
    current_period: str,
    *,
    top_k: int = TOP_K,
) -> list[dict[str, Any]]:
    """Return the most recent stored quarters for *ticker*, excluding the current one.

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
        Payloads for the latest stored periods of this ticker, newest first.
        Empty list on failure or no history.

    """
    try:
        if not client.collection_exists(COLLECTION_NAME):
            logger.info("Qdrant retrieve: no history for %s yet", ticker)
            return []
        points, _next = client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(key="ticker", match=models.MatchValue(value=ticker)),
                ],
            ),
            limit=_SCAN_LIMIT,
            with_payload=True,
            with_vectors=False,
        )
    except (OSError, RuntimeError, ValueError):
        logger.warning("Qdrant retrieve: lookup failed for %s", ticker)
        return []

    history = [dict(p.payload or {}) for p in points]
    history = [h for h in history if h.get("period") != current_period]
    history.sort(key=lambda h: _period_key(str(h.get("period", ""))), reverse=True)
    logger.info("Qdrant retrieve: %d records for %s", min(len(history), top_k), ticker)
    return history[:top_k]
