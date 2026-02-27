"""Tests for Sentinel CLI entry point."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

import pytest

from sentinel.__main__ import VERSION, main


def _mock_graph(result: dict, *, next_nodes: tuple[str, ...] = ()) -> MagicMock:
    """Create a mock compiled graph that returns the given result via astream + get_state."""
    mock = MagicMock()

    async def _astream(*_args: object, **_kwargs: object) -> AsyncIterator[dict[str, dict]]:
        for key in result:
            yield {key: {}}

    mock.astream = MagicMock(side_effect=_astream)

    state_snap = MagicMock()
    state_snap.values = result
    state_snap.next = next_nodes
    mock.get_state = MagicMock(return_value=state_snap)
    mock.aupdate_state = AsyncMock()
    return mock


def _patch_cli(mock_graph: MagicMock, run_dir: Path | None = None) -> tuple:
    """Context manager that patches checkpointer, compile_graph, output, and rag."""
    mock_checkpointer = MagicMock()
    mock_checkpointer.__enter__ = MagicMock(return_value=mock_checkpointer)
    mock_checkpointer.__exit__ = MagicMock(return_value=False)

    return (
        patch("sentinel.__main__.create_checkpointer", return_value=mock_checkpointer),
        patch("sentinel.__main__.compile_graph", return_value=mock_graph),
        patch(
            "sentinel.__main__.write_run_output",
            return_value=run_dir or Path("output/AAPL/20260222-120000"),
        ),
        patch("sentinel.__main__.create_store"),
        patch("sentinel.__main__.ingest"),
    )


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
    assert "--quick" in err
    assert "TICKER" in err


def test_main_shows_multi_ticker_usage(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify usage message shows multi-ticker example."""
    monkeypatch.setattr("sys.argv", ["sentinel"])
    with pytest.raises(SystemExit):
        main()
    err = capsys.readouterr().err
    assert "AAPL MSFT GOOG" in err


def test_main_single_ticker(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify main() runs pipeline for a single ticker in full mode."""
    monkeypatch.setattr("sys.argv", ["sentinel", "AAPL"])
    result = {"ticker": "AAPL", "brief": "Apple is doing great."}
    mock_graph = _mock_graph(result)

    p_ckpt, p_graph, p_output, p_store, p_ingest = _patch_cli(mock_graph)
    with p_ckpt, p_graph, p_output, p_store, p_ingest:
        main()

    out = capsys.readouterr().out
    assert f"v{VERSION}" in out
    assert "full mode" in out
    assert "AAPL" in out
    assert "Apple is doing great." in out
    assert "Output:" in out

    call_args = mock_graph.astream.call_args
    assert call_args[0][0] == {"ticker": "AAPL", "quick": False}
    config = call_args[1]["config"]
    assert config["run_name"] == "sentinel-AAPL-full"
    assert "ticker:AAPL" in config["tags"]
    assert "mode:full" in config["tags"]
    assert config["metadata"]["ticker"] == "AAPL"


def test_main_multi_ticker(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify main() runs pipeline for multiple tickers sequentially."""
    monkeypatch.setattr("sys.argv", ["sentinel", "AAPL", "MSFT"])
    mock_graph = _mock_graph({"ticker": "X", "brief": "Brief."})

    p_ckpt, p_graph, p_output, p_store, p_ingest = _patch_cli(mock_graph)
    with p_ckpt, p_graph, p_output, p_store, p_ingest:
        main()

    assert mock_graph.astream.call_count == 2  # noqa: PLR2004
    out = capsys.readouterr().out
    assert "--- AAPL ---" in out
    assert "--- MSFT ---" in out


def test_main_quick_flag(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify --quick flag is parsed and passed to graph."""
    monkeypatch.setattr("sys.argv", ["sentinel", "--quick", "AAPL"])
    mock_graph = _mock_graph({"ticker": "AAPL", "brief": "Quick."})

    p_ckpt, p_graph, p_output, p_store, p_ingest = _patch_cli(mock_graph)
    with p_ckpt, p_graph, p_output, p_store, p_ingest:
        main()

    out = capsys.readouterr().out
    assert "quick mode" in out
    call_args = mock_graph.astream.call_args
    assert call_args[0][0]["quick"] is True
    assert "mode:quick" in call_args[1]["config"]["tags"]


def test_main_quick_flag_after_ticker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify --quick works when placed after the ticker."""
    monkeypatch.setattr("sys.argv", ["sentinel", "MSFT", "--quick"])
    mock_graph = _mock_graph({"ticker": "MSFT", "brief": "Quick MSFT."})

    p_ckpt, p_graph, p_output, p_store, p_ingest = _patch_cli(mock_graph)
    with p_ckpt, p_graph, p_output, p_store, p_ingest:
        main()

    call_args = mock_graph.astream.call_args
    assert call_args[0][0] == {"ticker": "MSFT", "quick": True}


def test_main_tickers_uppercased(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify lowercase tickers are uppercased."""
    monkeypatch.setattr("sys.argv", ["sentinel", "aapl"])
    mock_graph = _mock_graph({"ticker": "AAPL", "brief": "Brief."})

    p_ckpt, p_graph, p_output, p_store, p_ingest = _patch_cli(mock_graph)
    with p_ckpt, p_graph, p_output, p_store, p_ingest:
        main()

    call_args = mock_graph.astream.call_args
    assert call_args[0][0]["ticker"] == "AAPL"


def test_main_langsmith_config_structure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify LangSmith config has required fields."""
    monkeypatch.setattr("sys.argv", ["sentinel", "GOOG"])
    mock_graph = _mock_graph({"ticker": "GOOG", "brief": "Brief."})

    p_ckpt, p_graph, p_output, p_store, p_ingest = _patch_cli(mock_graph)
    with p_ckpt, p_graph, p_output, p_store, p_ingest:
        main()

    config = mock_graph.astream.call_args[1]["config"]
    assert "run_name" in config
    assert "tags" in config
    assert "metadata" in config
    assert "configurable" in config
    assert "thread_id" in config["configurable"]
    assert config["metadata"]["version"] == VERSION
    assert f"v{VERSION}" in config["tags"]


def test_main_calls_write_run_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify main() calls write_run_output with the result."""
    monkeypatch.setattr("sys.argv", ["sentinel", "AAPL"])
    result = {"ticker": "AAPL", "brief": "Brief."}
    mock_graph = _mock_graph(result)

    mock_checkpointer = MagicMock()
    mock_checkpointer.__enter__ = MagicMock(return_value=mock_checkpointer)
    mock_checkpointer.__exit__ = MagicMock(return_value=False)

    mock_write = MagicMock(return_value=Path("output/AAPL/20260222"))

    with (
        patch("sentinel.__main__.create_checkpointer", return_value=mock_checkpointer),
        patch("sentinel.__main__.compile_graph", return_value=mock_graph),
        patch("sentinel.__main__.write_run_output", mock_write),
        patch("sentinel.__main__.create_store"),
        patch("sentinel.__main__.ingest"),
    ):
        main()

    mock_write.assert_called_once_with(result)


def test_main_ingests_after_successful_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify main() calls ingest with raw_data after a successful pipeline run."""
    monkeypatch.setattr("sys.argv", ["sentinel", "AAPL"])
    raw_data = {"ticker": "AAPL", "period": "Q1 2026", "revenue": 94800}
    result = {"ticker": "AAPL", "brief": "Brief.", "raw_data": raw_data}
    mock_graph = _mock_graph(result)
    mock_store = MagicMock()
    mock_create_store = MagicMock(return_value=mock_store)
    mock_ingest = MagicMock()

    p_ckpt, p_graph, p_output, _, _ = _patch_cli(mock_graph)
    with (
        p_ckpt,
        p_graph,
        p_output,
        patch("sentinel.__main__.create_store", mock_create_store),
        patch("sentinel.__main__.ingest", mock_ingest),
    ):
        main()

    mock_ingest.assert_called_once_with(mock_store, raw_data)


def test_main_skips_ingest_on_error_raw_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify main() skips ingest when raw_data contains an error key."""
    monkeypatch.setattr("sys.argv", ["sentinel", "AAPL"])
    result = {
        "ticker": "AAPL",
        "brief": "Brief.",
        "raw_data": {"error": "ref_fetch failed"},
    }
    mock_graph = _mock_graph(result)
    mock_ingest = MagicMock()

    p_ckpt, p_graph, p_output, _, _ = _patch_cli(mock_graph)
    with (
        p_ckpt,
        p_graph,
        p_output,
        patch("sentinel.__main__.create_store"),
        patch("sentinel.__main__.ingest", mock_ingest),
    ):
        main()

    mock_ingest.assert_not_called()


def test_main_ingest_exception_is_non_fatal(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify main() continues when Qdrant ingest raises."""
    monkeypatch.setattr("sys.argv", ["sentinel", "AAPL"])
    result = {
        "ticker": "AAPL",
        "brief": "Brief.",
        "raw_data": {"ticker": "AAPL", "period": "Q1 2026"},
    }
    mock_graph = _mock_graph(result)

    p_ckpt, p_graph, p_output, _, _ = _patch_cli(mock_graph)
    with (
        p_ckpt,
        p_graph,
        p_output,
        patch("sentinel.__main__.create_store", side_effect=RuntimeError("boom")),
    ):
        main()  # must not raise

    out = capsys.readouterr().out
    assert "Brief." in out  # pipeline completed normally


def test_main_hitl_flag_parses(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify --hitl flag is parsed and main() runs without error."""
    monkeypatch.setattr("sys.argv", ["sentinel", "--hitl", "AAPL"])
    result = {"ticker": "AAPL", "brief": "Brief."}
    # next_nodes=() means no interrupt triggered (graph ran to completion)
    mock_graph = _mock_graph(result, next_nodes=())

    p_ckpt, p_graph, p_output, p_store, p_ingest = _patch_cli(mock_graph)
    with p_ckpt, p_graph, p_output, p_store, p_ingest:
        main()

    out = capsys.readouterr().out
    assert "AAPL" in out
    assert "Brief." in out


def test_main_hitl_approves_and_resumes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify --hitl: show_draft_summary called, approval triggers resume astream."""
    monkeypatch.setattr("sys.argv", ["sentinel", "--hitl", "AAPL"])
    result = {"ticker": "AAPL", "brief": "Brief."}
    # next_nodes=("synthesizer",) triggers the HITL gate
    mock_graph = _mock_graph(result, next_nodes=("synthesizer",))

    p_ckpt, p_graph, p_output, p_store, p_ingest = _patch_cli(mock_graph)
    with (
        p_ckpt,
        p_graph,
        p_output,
        p_store,
        p_ingest,
        patch("sentinel.__main__.show_draft_summary") as mock_show,
        patch("sentinel.__main__.prompt_approval", return_value=(True, "")),
    ):
        main()

    mock_show.assert_called_once()
    # First pass + resume = 2 astream calls
    assert mock_graph.astream.call_count == 2  # noqa: PLR2004
    mock_graph.aupdate_state.assert_not_called()


def test_main_hitl_rejects_and_injects_feedback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify --hitl rejection injects analyst_feedback via aupdate_state."""
    monkeypatch.setattr("sys.argv", ["sentinel", "--hitl", "AAPL"])
    result = {"ticker": "AAPL", "brief": "Brief."}
    mock_graph = _mock_graph(result, next_nodes=("synthesizer",))

    p_ckpt, p_graph, p_output, p_store, p_ingest = _patch_cli(mock_graph)
    with (
        p_ckpt,
        p_graph,
        p_output,
        p_store,
        p_ingest,
        patch("sentinel.__main__.show_draft_summary"),
        patch(
            "sentinel.__main__.prompt_approval",
            return_value=(False, "emphasize margin compression"),
        ),
    ):
        main()

    # aupdate_state called with the feedback
    mock_graph.aupdate_state.assert_called_once()
    update_kwargs = mock_graph.aupdate_state.call_args[0][1]
    assert update_kwargs == {"analyst_feedback": "emphasize margin compression"}
    # Resume astream also called
    assert mock_graph.astream.call_count == 2  # noqa: PLR2004


def test_main_hitl_skipped_when_no_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify HITL gate is not triggered when --hitl flag is absent."""
    monkeypatch.setattr("sys.argv", ["sentinel", "AAPL"])
    result = {"ticker": "AAPL", "brief": "Brief."}
    mock_graph = _mock_graph(result)

    p_ckpt, p_graph, p_output, p_store, p_ingest = _patch_cli(mock_graph)
    mock_show = MagicMock()
    mock_prompt = MagicMock()
    with (
        p_ckpt,
        p_graph,
        p_output,
        p_store,
        p_ingest,
        patch("sentinel.__main__.show_draft_summary", mock_show),
        patch("sentinel.__main__.prompt_approval", mock_prompt),
    ):
        main()

    mock_show.assert_not_called()
    mock_prompt.assert_not_called()
    assert mock_graph.astream.call_count == 1


def test_main_mcp_subcommand_dispatches_to_run_mcp_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify 'sentinel mcp' dispatches to run_mcp_server and exits cleanly."""
    monkeypatch.setattr("sys.argv", ["sentinel", "mcp"])
    mock_run = MagicMock()
    with (
        patch("sentinel.__main__.run_mcp_server", mock_run),
        pytest.raises(SystemExit, match="0"),
    ):
        main()

    mock_run.assert_called_once()


def test_main_mcp_subcommand_does_not_run_pipeline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify 'sentinel mcp' exits before the pipeline is compiled."""
    monkeypatch.setattr("sys.argv", ["sentinel", "mcp"])
    mock_run = MagicMock()
    mock_compile = MagicMock()
    with (
        patch("sentinel.__main__.run_mcp_server", mock_run),
        patch("sentinel.__main__.compile_graph", mock_compile),
        pytest.raises(SystemExit),
    ):
        main()

    mock_compile.assert_not_called()


def test_main_streaming_progress_printed(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify agent progress labels are printed to stdout during streaming."""
    monkeypatch.setattr("sys.argv", ["sentinel", "AAPL"])
    # Include node names as keys so _astream yields them and labels get printed
    result = {
        "research": {},
        "modeler": {},
        "ticker": "AAPL",
        "brief": "Brief.",
    }
    mock_graph = _mock_graph(result)

    p_ckpt, p_graph, p_output, p_store, p_ingest = _patch_cli(mock_graph)
    with p_ckpt, p_graph, p_output, p_store, p_ingest:
        main()

    out = capsys.readouterr().out
    assert "  [Research]" in out
    assert "  [Modeler]" in out
