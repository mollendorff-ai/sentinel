"""Tests for sentinel.rag.store — all Qdrant interactions are mocked."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from sentinel.rag.store import (
    COLLECTION_NAME,
    DEFAULT_QDRANT_PATH,
    _point_id,
    _to_text,
    create_store,
    ingest,
    retrieve,
)


# ── _point_id ────────────────────────────────────────────────────────────────


class TestPointId:
    def test_point_id_is_stable(self):
        assert _point_id("AAPL", "Q1-2025") == _point_id("AAPL", "Q1-2025")

    def test_point_id_differs_by_period(self):
        assert _point_id("AAPL", "Q1-2025") != _point_id("AAPL", "Q2-2025")

    def test_point_id_differs_by_ticker(self):
        assert _point_id("AAPL", "Q1-2025") != _point_id("MSFT", "Q1-2025")

    def test_point_id_is_uuid5(self):
        result = _point_id("AAPL", "Q1-2025")
        assert uuid.UUID(result).version == 5


# ── _to_text ─────────────────────────────────────────────────────────────────


class TestToText:
    def test_to_text_includes_ticker_and_period(self):
        data = {"ticker": "AAPL", "period": "Q1-2025", "company": "Apple"}
        text = _to_text(data)
        assert "ticker=AAPL" in text
        assert "period=Q1-2025" in text
        assert "company=Apple" in text

    def test_to_text_includes_numeric_fields(self):
        data = {
            "ticker": "AAPL",
            "period": "Q1-2025",
            "company": "Apple",
            "revenue": 100_000,
            "eps": 1.52,
            "gross_margin": 0.45,
        }
        text = _to_text(data)
        assert "revenue=100000" in text
        assert "eps=1.52" in text
        assert "gross_margin=0.45" in text

    def test_to_text_omits_none_fields(self):
        data = {
            "ticker": "AAPL",
            "period": "Q1-2025",
            "company": "Apple",
            "revenue": None,
            "eps": 1.52,
        }
        text = _to_text(data)
        assert "revenue=" not in text
        assert "eps=1.52" in text


# ── create_store ─────────────────────────────────────────────────────────────


class TestCreateStore:
    def test_create_store_creates_parent_dirs(self, tmp_path):
        deep = tmp_path / "deep" / "nested" / "qdrant"
        with patch("sentinel.rag.store.QdrantClient") as mock_cls:
            mock_cls.return_value = MagicMock()
            create_store(path=deep)
        assert deep.exists()

    def test_create_store_uses_env_var(self, tmp_path):
        env_path = str(tmp_path / "env_qdrant")
        with (
            patch.dict("os.environ", {"SENTINEL_QDRANT_PATH": env_path}),
            patch("sentinel.rag.store.QdrantClient") as mock_cls,
        ):
            mock_cls.return_value = MagicMock()
            create_store()
        mock_cls.assert_called_once_with(path=env_path)

    def test_create_store_uses_default_when_no_env(self):
        with (
            patch.dict("os.environ", {}, clear=True),
            patch("sentinel.rag.store._qdrant_path") as mock_path_fn,
            patch("sentinel.rag.store.QdrantClient") as mock_cls,
        ):
            fake_path = MagicMock()
            mock_path_fn.return_value = fake_path
            mock_cls.return_value = MagicMock()
            create_store()
        mock_cls.assert_called_once_with(path=str(fake_path))

    def test_create_store_returns_client(self, tmp_path):
        with patch("sentinel.rag.store.QdrantClient") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            result = create_store(path=tmp_path)
        assert result is mock_client


# ── ingest ───────────────────────────────────────────────────────────────────


class TestIngest:
    @pytest.fixture()
    def client(self):
        return MagicMock()

    @pytest.fixture()
    def sample_data(self):
        return {
            "ticker": "AAPL",
            "period": "Q1-2025",
            "company": "Apple",
            "revenue": 100_000,
        }

    def test_ingest_calls_add_with_correct_args(self, client, sample_data):
        ingest(client, sample_data)
        client.add.assert_called_once()
        call_kwargs = client.add.call_args[1]
        assert call_kwargs["collection_name"] == COLLECTION_NAME
        assert "AAPL" in call_kwargs["documents"][0]
        assert call_kwargs["ids"] == [_point_id("AAPL", "Q1-2025")]

    def test_ingest_is_idempotent_for_same_period(self, client, sample_data):
        ingest(client, sample_data)
        first_id = client.add.call_args[1]["ids"][0]
        ingest(client, sample_data)
        second_id = client.add.call_args[1]["ids"][0]
        assert first_id == second_id

    def test_ingest_returns_true_on_success(self, client, sample_data):
        assert ingest(client, sample_data) is True

    def test_ingest_returns_false_when_add_raises(self, client, sample_data):
        client.add.side_effect = RuntimeError("boom")
        assert ingest(client, sample_data) is False

    def test_ingest_returns_false_for_missing_ticker(self, client):
        assert ingest(client, {"period": "Q1-2025"}) is False

    def test_ingest_returns_false_for_missing_period(self, client):
        assert ingest(client, {"ticker": "AAPL"}) is False


# ── retrieve ─────────────────────────────────────────────────────────────────


class TestRetrieve:
    @pytest.fixture()
    def client(self):
        return MagicMock()

    def _make_hit(self, metadata: dict) -> MagicMock:
        hit = MagicMock()
        hit.metadata = metadata
        return hit

    def test_retrieve_returns_historical_records_excluding_current(self, client):
        client.query.return_value = [
            self._make_hit({"ticker": "AAPL", "period": "Q4-2024"}),
            self._make_hit({"ticker": "AAPL", "period": "Q1-2025"}),
            self._make_hit({"ticker": "AAPL", "period": "Q3-2024"}),
        ]
        results = retrieve(client, "AAPL", "Q1-2025")
        periods = [r["period"] for r in results]
        assert "Q1-2025" not in periods
        assert "Q4-2024" in periods
        assert "Q3-2024" in periods

    def test_retrieve_respects_top_k(self, client):
        client.query.return_value = [
            self._make_hit({"ticker": "AAPL", "period": f"Q{i}-2024"})
            for i in range(1, 6)
        ]
        results = retrieve(client, "AAPL", "Q1-2025", top_k=2)
        assert len(results) <= 2

    def test_retrieve_returns_empty_on_query_exception(self, client):
        client.query.side_effect = RuntimeError("no collection")
        results = retrieve(client, "AAPL", "Q1-2025")
        assert results == []

    def test_retrieve_calls_query_with_collection_name(self, client):
        client.query.return_value = []
        retrieve(client, "AAPL", "Q1-2025")
        call_kwargs = client.query.call_args[1]
        assert call_kwargs["collection_name"] == COLLECTION_NAME

    def test_retrieve_returns_empty_when_no_history(self, client):
        client.query.return_value = []
        results = retrieve(client, "AAPL", "Q1-2025")
        assert results == []

    def test_retrieve_handles_hit_without_metadata_attr(self, client):
        hit = MagicMock(spec=[])  # no attributes at all
        client.query.return_value = [hit]
        results = retrieve(client, "AAPL", "Q1-2025")
        assert results == [{}]
