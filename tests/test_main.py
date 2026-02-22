"""Tests for Sentinel CLI entry point."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from sentinel.__main__ import main


def test_main_requires_ticker(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify main() exits with usage message when no ticker is provided."""
    monkeypatch.setattr("sys.argv", ["sentinel"])
    with pytest.raises(SystemExit, match="1"):
        main()
    err = capsys.readouterr().err
    assert "Usage" in err


def test_main_runs_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify main() invokes the graph and prints the brief."""
    monkeypatch.setattr("sys.argv", ["sentinel", "AAPL"])

    mock_result = {
        "ticker": "AAPL",
        "brief": "Apple is doing great.",
    }

    mock_graph = AsyncMock()
    mock_graph.ainvoke = AsyncMock(return_value=mock_result)

    with patch(
        "sentinel.__main__.compile_graph",
        return_value=mock_graph,
    ):
        main()

    out = capsys.readouterr().out
    assert "Sentinel v0.2.0" in out
    assert "Apple is doing great." in out
