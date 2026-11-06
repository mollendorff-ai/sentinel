"""Tests for sentinel.rag.store, run against a real on-disk Qdrant (no mocks of Qdrant)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

from sentinel.rag.store import (
    COLLECTION_NAME,
    _period_key,
    _point_id,
    create_store,
    ingest,
    retrieve,
)

if TYPE_CHECKING:
    from pathlib import Path

_UUID_V5_VERSION = 5


def _quarter(ticker: str, period: str, revenue: int = 1) -> dict[str, Any]:
    return {"ticker": ticker, "period": period, "company": ticker, "revenue": revenue}


class TestPointId:
    """Tests for the ``_point_id`` helper."""

    def test_point_id_is_stable_and_unique(self) -> None:
        """Same ticker+period is stable; different ones differ."""
        assert _point_id("AAPL", "Q1 2025") == _point_id("AAPL", "Q1 2025")
        assert _point_id("AAPL", "Q1 2025") != _point_id("AAPL", "Q2 2025")
        assert _point_id("AAPL", "Q1 2025") != _point_id("MSFT", "Q1 2025")

    def test_point_id_is_uuid5(self) -> None:
        """The returned string is a valid UUID version 5."""
        assert uuid.UUID(_point_id("AAPL", "Q1 2025")).version == _UUID_V5_VERSION


class TestPeriodKey:
    """Tests for the period sort key."""

    def test_orders_by_year_then_quarter(self) -> None:
        """Newer years and later quarters sort higher."""
        assert _period_key("Q1 2026") > _period_key("Q4 2025")
        assert _period_key("Q3 2025") > _period_key("Q2 2025")

    def test_full_year_sorts_after_its_quarters(self) -> None:
        """A fiscal-year label sorts after the quarters of the same year."""
        assert _period_key("FY 2025") > _period_key("Q4 2025")

    def test_unknown_label_sorts_last(self) -> None:
        """A label with no year sorts below any dated period."""
        assert _period_key("latest") < _period_key("Q1 2000")


class TestCreateStore:
    """Tests for ``create_store``."""

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        """Parent directories are created when they do not exist."""
        deep = tmp_path / "deep" / "nested" / "qdrant"
        create_store(path=deep).close()
        assert deep.exists()

    def test_uses_env_var(self, tmp_path: Path) -> None:
        """SENTINEL_QDRANT_PATH overrides the default path."""
        env_path = str(tmp_path / "env_qdrant")
        with patch.dict("os.environ", {"SENTINEL_QDRANT_PATH": env_path}):
            create_store().close()
        assert (tmp_path / "env_qdrant").exists()

    def test_uses_default_when_no_env(self, tmp_path: Path) -> None:
        """Without the env var, the default path function is used."""
        with (
            patch.dict("os.environ", {}, clear=True),
            patch("sentinel.rag.store._qdrant_path", return_value=tmp_path / "default"),
        ):
            create_store().close()
        assert (tmp_path / "default").exists()


class TestIngestAndRetrieve:
    """Round trips through a real local Qdrant."""

    def test_round_trip_newest_first(self, tmp_path: Path) -> None:
        """Stored quarters come back newest first, without the current period."""
        client = create_store(tmp_path)
        for period in ("Q2 2025", "Q4 2025", "Q3 2025", "Q1 2026"):
            assert ingest(client, _quarter("AAPL", period)) is True
        history = retrieve(client, "AAPL", "Q1 2026")
        client.close()
        assert [h["period"] for h in history] == ["Q4 2025", "Q3 2025", "Q2 2025"]

    def test_only_returns_the_requested_ticker(self, tmp_path: Path) -> None:
        """Other companies' quarters are never returned."""
        client = create_store(tmp_path)
        ingest(client, _quarter("AAPL", "Q4 2025"))
        ingest(client, _quarter("MSFT", "Q4 2025"))
        history = retrieve(client, "AAPL", "Q1 2026")
        client.close()
        assert [h["ticker"] for h in history] == ["AAPL"]

    def test_ingest_is_idempotent(self, tmp_path: Path) -> None:
        """Ingesting the same quarter twice keeps one record, with the latest values."""
        client = create_store(tmp_path)
        ingest(client, _quarter("AAPL", "Q4 2025", revenue=1))
        ingest(client, _quarter("AAPL", "Q4 2025", revenue=2))
        history = retrieve(client, "AAPL", "Q1 2026")
        client.close()
        assert len(history) == 1
        assert history[0]["revenue"] == 2  # noqa: PLR2004

    def test_top_k_limits_results(self, tmp_path: Path) -> None:
        """No more than top_k records are returned."""
        client = create_store(tmp_path)
        for period in ("Q1 2025", "Q2 2025", "Q3 2025", "Q4 2025"):
            ingest(client, _quarter("AAPL", period))
        history = retrieve(client, "AAPL", "Q1 2026", top_k=2)
        client.close()
        assert [h["period"] for h in history] == ["Q4 2025", "Q3 2025"]

    def test_retrieve_before_any_ingest_is_empty(self, tmp_path: Path) -> None:
        """A store with no collection yet returns no history."""
        client = create_store(tmp_path)
        assert retrieve(client, "AAPL", "Q1 2026") == []
        client.close()

    def test_store_survives_reopen(self, tmp_path: Path) -> None:
        """History written by one client is read by the next, as across two runs."""
        first = create_store(tmp_path)
        ingest(first, _quarter("AAPL", "Q4 2025"))
        first.close()
        second = create_store(tmp_path)
        history = retrieve(second, "AAPL", "Q1 2026")
        second.close()
        assert len(history) == 1

    @pytest.mark.parametrize("data", [{"ticker": "AAPL"}, {"period": "Q1 2026"}, {}])
    def test_ingest_skips_missing_ticker_or_period(
        self,
        tmp_path: Path,
        data: dict[str, Any],
    ) -> None:
        """A record without ticker or period is skipped."""
        client = create_store(tmp_path)
        assert ingest(client, data) is False
        client.close()

    def test_ingest_returns_false_when_qdrant_raises(self) -> None:
        """Ingest degrades to False instead of raising."""
        client = MagicMock()
        client.collection_exists.side_effect = RuntimeError("boom")
        assert ingest(client, _quarter("AAPL", "Q1 2026")) is False

    def test_retrieve_returns_empty_when_qdrant_raises(self) -> None:
        """Retrieve degrades to an empty list instead of raising."""
        client = MagicMock()
        client.collection_exists.side_effect = RuntimeError("boom")
        assert retrieve(client, "AAPL", "Q1 2026") == []

    def test_collection_name_is_stable(self) -> None:
        """The collection name is part of the on-disk format."""
        assert COLLECTION_NAME == "earnings"
