"""Tests for the Retriever agent: history from earlier runs' files."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

from sentinel.agents.retriever import earlier_runs, retriever_node

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _run(root: Path, name: str, raw: dict[str, Any] | str, ticker: str = "AAPL") -> None:
    folder = root / ticker / name
    folder.mkdir(parents=True)
    text = raw if isinstance(raw, str) else json.dumps(raw)
    (folder / "raw_data.json").write_text(text)


def _raw(period: str, revenue: int) -> dict[str, Any]:
    return {"period": f"label {period}", "revenue": revenue, "input": {"period": period}}


def test_earlier_runs_newest_good_run_per_period(tmp_path: Path) -> None:
    """One entry per earlier period, from its newest good run, newest first."""
    _run(tmp_path, "20260801-000000", _raw("FY2026-Q3", 1))
    _run(tmp_path, "20260802-000000", _raw("FY2026-Q3", 2))
    _run(tmp_path, "20260803-000000", {"error": "differs", "input": {"period": "FY2026-Q2"}})
    _run(tmp_path, "20260804-000000", "not json")
    _run(tmp_path, "20260805-000000", ["a", "list"])  # type: ignore[arg-type]
    _run(tmp_path, "20260806-000000", _raw("FY2026-Q4", 9))
    _run(tmp_path, "20260701-000000", {"period": "Q2 FY2026", "revenue": 5})
    _run(tmp_path, "20260601-000000", {"revenue": 4})
    (tmp_path / "AAPL" / "notes.txt").write_text("not a run")

    history = earlier_runs("AAPL", "FY2026-Q4", runs_dir=tmp_path)

    assert [(h["period"], h["revenue"], h["run"]) for h in history] == [
        ("label FY2026-Q3", 2, "20260802-000000"),
        ("Q2 FY2026", 5, "20260701-000000"),
    ]


def test_earlier_runs_stops_at_top_k(tmp_path: Path) -> None:
    """At most top_k periods are returned."""
    for day in range(1, 6):
        _run(tmp_path, f"2026080{day}-000000", _raw(f"P{day}", day))
    history = earlier_runs("AAPL", "NOW", runs_dir=tmp_path, top_k=2)
    assert [h["revenue"] for h in history] == [5, 4]


def test_earlier_runs_without_folder(tmp_path: Path) -> None:
    """A ticker that has never run has no history."""
    assert earlier_runs("MSFT", "FY2026-Q4", runs_dir=tmp_path) == []


async def test_retriever_node_reads_runs_folder(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The node reads runs/ in the current folder and excludes the current period."""
    _run(tmp_path / "runs", "20260801-000000", _raw("FY2026-Q3", 1))
    _run(tmp_path / "runs", "20260802-000000", _raw("FY2026-Q4", 2))
    monkeypatch.chdir(tmp_path)

    state: dict[str, Any] = {"ticker": "AAPL", "raw_data": _raw("FY2026-Q4", 2)}
    result = await retriever_node(state)

    assert [h["revenue"] for h in result["historical_context"]] == [1]


async def test_retriever_node_uses_extracted_period_without_input() -> None:
    """Without an input record, the extracted period label is the current period."""
    with patch("sentinel.agents.retriever.earlier_runs", return_value=[]) as mock_runs:
        await retriever_node({"ticker": "AAPL", "raw_data": {"period": "Q4 FY2026"}})
    mock_runs.assert_called_once_with("AAPL", "Q4 FY2026")


async def test_retriever_node_skips_on_research_error() -> None:
    """No history is read when Research failed."""
    with patch("sentinel.agents.retriever.earlier_runs") as mock_runs:
        result = await retriever_node({"ticker": "AAPL", "raw_data": {"error": "x"}})
    assert result == {"historical_context": []}
    mock_runs.assert_not_called()


async def test_retriever_node_graceful_on_unreadable_runs() -> None:
    """A failure reading runs/ gives no history instead of stopping the run."""
    with patch("sentinel.agents.retriever.earlier_runs", side_effect=OSError("denied")):
        result = await retriever_node({"ticker": "AAPL", "raw_data": {"period": "P"}})
    assert result == {"historical_context": []}
