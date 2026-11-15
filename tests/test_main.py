"""Tests for Sentinel CLI entry point."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

import pytest

from sentinel import handoff
from sentinel.__main__ import EXIT_WAITING, VERSION, main


def _mock_graph(result: dict, *, next_nodes: tuple[str, ...] = ()) -> MagicMock:
    """Create a mock compiled graph that returns the given result via astream + aget_state."""
    mock = MagicMock()

    async def _astream(*_args: object, **_kwargs: object) -> AsyncIterator[dict[str, dict]]:
        for key in result:
            yield {key: {}}

    mock.astream = MagicMock(side_effect=_astream)

    state_snap = MagicMock()
    state_snap.values = result
    state_snap.next = next_nodes
    mock.aget_state = AsyncMock(return_value=state_snap)
    mock.aupdate_state = AsyncMock()
    return mock


def _patch_cli(mock_graph: MagicMock, run_dir: Path | None = None) -> tuple:
    """Patches for the checkpointer, compile_graph and the output writer."""
    mock_checkpointer = MagicMock()
    mock_checkpointer.__aenter__ = AsyncMock(return_value=mock_checkpointer)
    mock_checkpointer.__aexit__ = AsyncMock(return_value=False)

    return (
        patch("sentinel.__main__.create_checkpointer", return_value=mock_checkpointer),
        patch("sentinel.__main__.compile_graph", return_value=mock_graph),
        patch(
            "sentinel.__main__.write_run_output",
            return_value=run_dir or Path("runs/AAPL/20260222-120000"),
        ),
        patch("sentinel.__main__._check_inputs"),
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

    p_ckpt, p_graph, p_output, p_inputs = _patch_cli(mock_graph)
    with p_ckpt, p_graph, p_output, p_inputs:
        main()

    out = capsys.readouterr().out
    assert f"v{VERSION}" in out
    assert "full mode" in out
    assert "AAPL" in out
    assert "Apple is doing great." in out
    assert "Output:" in out

    call_args = mock_graph.astream.call_args
    assert call_args[0][0] == {"ticker": "AAPL", "quick": False, "period": ""}
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

    p_ckpt, p_graph, p_output, p_inputs = _patch_cli(mock_graph)
    with p_ckpt, p_graph, p_output, p_inputs:
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

    p_ckpt, p_graph, p_output, p_inputs = _patch_cli(mock_graph)
    with p_ckpt, p_graph, p_output, p_inputs:
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

    p_ckpt, p_graph, p_output, p_inputs = _patch_cli(mock_graph)
    with p_ckpt, p_graph, p_output, p_inputs:
        main()

    call_args = mock_graph.astream.call_args
    assert call_args[0][0] == {"ticker": "MSFT", "quick": True, "period": ""}


def test_main_tickers_uppercased(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify lowercase tickers are uppercased."""
    monkeypatch.setattr("sys.argv", ["sentinel", "aapl"])
    mock_graph = _mock_graph({"ticker": "AAPL", "brief": "Brief."})

    p_ckpt, p_graph, p_output, p_inputs = _patch_cli(mock_graph)
    with p_ckpt, p_graph, p_output, p_inputs:
        main()

    call_args = mock_graph.astream.call_args
    assert call_args[0][0]["ticker"] == "AAPL"


def test_main_langsmith_config_structure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify LangSmith config has required fields."""
    monkeypatch.setattr("sys.argv", ["sentinel", "GOOG"])
    mock_graph = _mock_graph({"ticker": "GOOG", "brief": "Brief."})

    p_ckpt, p_graph, p_output, p_inputs = _patch_cli(mock_graph)
    with p_ckpt, p_graph, p_output, p_inputs:
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
    mock_checkpointer.__aenter__ = AsyncMock(return_value=mock_checkpointer)
    mock_checkpointer.__aexit__ = AsyncMock(return_value=False)

    mock_write = MagicMock(return_value=Path("runs/AAPL/20260222"))

    with (
        patch("sentinel.__main__.create_checkpointer", return_value=mock_checkpointer),
        patch("sentinel.__main__.compile_graph", return_value=mock_graph),
        patch("sentinel.__main__.write_run_output", mock_write),
        patch("sentinel.__main__._check_inputs"),
    ):
        main()

    mock_write.assert_called_once_with(result)


def test_main_hitl_flag_parses(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify --hitl flag is parsed and main() runs without error."""
    monkeypatch.setattr("sys.argv", ["sentinel", "--hitl", "AAPL"])
    result = {"ticker": "AAPL", "brief": "Brief."}
    # next_nodes=() means no interrupt triggered (graph ran to completion)
    mock_graph = _mock_graph(result, next_nodes=())

    p_ckpt, p_graph, p_output, p_inputs = _patch_cli(mock_graph)
    with p_ckpt, p_graph, p_output, p_inputs:
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

    p_ckpt, p_graph, p_output, p_inputs = _patch_cli(mock_graph)
    with (
        p_ckpt,
        p_graph,
        p_output,
        p_inputs,
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

    p_ckpt, p_graph, p_output, p_inputs = _patch_cli(mock_graph)
    with (
        p_ckpt,
        p_graph,
        p_output,
        p_inputs,
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

    p_ckpt, p_graph, p_output, p_inputs = _patch_cli(mock_graph)
    mock_show = MagicMock()
    mock_prompt = MagicMock()
    with (
        p_ckpt,
        p_graph,
        p_output,
        p_inputs,
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

    p_ckpt, p_graph, p_output, p_inputs = _patch_cli(mock_graph)
    with p_ckpt, p_graph, p_output, p_inputs:
        main()

    out = capsys.readouterr().out
    assert "  [Research]" in out
    assert "  [Modeler]" in out


def test_main_help_prints_usage(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--help prints the usage on stdout and exits 0."""
    monkeypatch.setattr("sys.argv", ["sentinel", "--help"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0
    assert "Usage" in capsys.readouterr().out


def test_main_version_prints_version(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--version prints the version and exits 0."""
    monkeypatch.setattr("sys.argv", ["sentinel", "--version"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0
    assert VERSION in capsys.readouterr().out


def test_main_rejects_unknown_option(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An unknown flag is an error, not a ticker."""
    monkeypatch.setattr("sys.argv", ["sentinel", "--fast", "AAPL"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2  # noqa: PLR2004
    assert "Unknown option: --fast" in capsys.readouterr().err


def test_main_rejects_invalid_ticker(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A ticker that could escape the output folder is refused before any work starts."""
    monkeypatch.setattr("sys.argv", ["sentinel", "../../ESCAPED"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2  # noqa: PLR2004
    assert "Invalid ticker" in capsys.readouterr().err


def test_main_period_passed_to_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--period P selects inputs/<TICKER>/P/ and reaches the graph."""
    monkeypatch.setattr("sys.argv", ["sentinel", "--period", "FY2026-Q4", "AAPL"])
    mock_graph = _mock_graph({"ticker": "AAPL", "brief": "Brief."})

    p_ckpt, p_graph, p_output, p_inputs = _patch_cli(mock_graph)
    with p_ckpt, p_graph, p_output, p_inputs:
        main()

    assert mock_graph.astream.call_args[0][0]["period"] == "FY2026-Q4"


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["sentinel", "AAPL", "--period"], "--period needs a value"),
        (["sentinel", "--period", "--quick", "AAPL"], "--period needs a value"),
        (["sentinel", "--period", "../x", "AAPL"], "Invalid period"),
    ],
)
def test_main_rejects_bad_period(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    argv: list[str],
    message: str,
) -> None:
    """A missing or unsafe period is refused before any work starts."""
    monkeypatch.setattr("sys.argv", argv)
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2  # noqa: PLR2004
    assert message in capsys.readouterr().err


@pytest.mark.parametrize(
    ("result", "reason"),
    [
        (
            {"ticker": "AAPL", "brief": "B.", "raw_data": {"error": "figures differ"}},
            "raw_data: figures differ",
        ),
        (
            {"ticker": "AAPL", "brief": "B.", "forge_results": {"error": "invalid"}},
            "forge_results: invalid",
        ),
        ({"ticker": "AAPL", "brief": ""}, "no brief was written"),
    ],
)
def test_main_exits_1_when_a_run_fails(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    result: dict,
    reason: str,
) -> None:
    """A failed run is written out, reported, and makes the command exit 1."""
    monkeypatch.setattr("sys.argv", ["sentinel", "AAPL"])
    mock_graph = _mock_graph(result)

    p_ckpt, p_graph, p_output, p_inputs = _patch_cli(mock_graph)
    with p_ckpt, p_graph, p_output as mock_write, p_inputs, pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 1
    mock_write.assert_called_once()
    assert f"FAILED: {reason}" in capsys.readouterr().out


def test_main_waits_for_the_chat_and_exits_3(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """A prompt without an answer: no run folder, the files named, exit 3."""
    monkeypatch.setattr("sys.argv", ["sentinel", "AAPL"])
    monkeypatch.setenv("SENTINEL_LLM_PROVIDER", "chat")
    store = handoff.HandoffStore(folder=tmp_path)
    monkeypatch.setattr(handoff, "_STORE", store)

    mock_graph = _mock_graph({"ticker": "AAPL", "raw_data": {"error": "No answer yet"}})

    async def _astream(*_args: object, **_kwargs: object) -> AsyncIterator[dict[str, dict]]:
        with pytest.raises(handoff.AnswerNeededError):
            store.answer("research", "Read the filing.")
        yield {"research": {}}

    mock_graph.astream = MagicMock(side_effect=_astream)

    p_ckpt, p_graph, p_output, p_inputs = _patch_cli(mock_graph)
    with p_ckpt, p_graph, p_output as mock_write, p_inputs, pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == EXIT_WAITING
    mock_write.assert_not_called()
    out = capsys.readouterr().out
    assert "LLM: the AI in this chat" in out
    assert "WAITING for the chat to answer" in out
    assert "research: read " in out
    assert ".answer.md" in out
    assert "Then run the same command again." in out


def test_main_keeps_the_chat_transcript(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A finished chat run copies its prompts and answers into the run folder."""
    monkeypatch.setattr("sys.argv", ["sentinel", "AAPL"])
    store = MagicMock(pending=[])
    monkeypatch.setattr(handoff, "_STORE", store)
    mock_graph = _mock_graph({"ticker": "AAPL", "brief": "Brief."})

    p_ckpt, p_graph, _, p_inputs = _patch_cli(mock_graph)
    with (
        p_ckpt,
        p_graph,
        p_inputs,
        patch("sentinel.__main__.write_run_output", return_value=tmp_path),
    ):
        main()

    store.keep.assert_called_once_with(tmp_path)


def test_main_fails_on_an_incomplete_brief(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A brief the Synthesizer could not write counts as a failed run."""
    monkeypatch.setattr("sys.argv", ["sentinel", "AAPL"])
    result = {"ticker": "AAPL", "brief": "Analysis incomplete for AAPL: LLM call failed"}
    mock_graph = _mock_graph(result)

    p_ckpt, p_graph, p_output, p_inputs = _patch_cli(mock_graph)
    with p_ckpt, p_graph, p_output, p_inputs, pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 1
    assert "FAILED: brief: Analysis incomplete" in capsys.readouterr().out


def _saved(tmp_path: Path, *, checked: bool) -> None:
    folder = tmp_path / "inputs" / "AAPL" / "FY2026-Q4"
    folder.mkdir(parents=True)
    (folder / "release.md").write_text("doc")
    (folder / "source.yaml").write_text("url: x\n")
    (folder / "expected.yaml").write_text(f"checked: {str(checked).lower()}\nfigures:\n  a: 1\n")


@pytest.mark.parametrize(
    ("argv", "checked", "message"),
    [
        (["sentinel", "AAPL"], False, "is not checked by a person"),
        (["sentinel", "MSFT"], True, "No saved input for MSFT"),
    ],
)
def test_main_refuses_an_unchecked_or_missing_input(  # noqa: PLR0913
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    argv: list[str],
    *,
    checked: bool,
    message: str,
) -> None:
    """No run starts on an input nobody checked, or on a ticker with no input."""
    _saved(tmp_path, checked=checked)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", argv)
    with (
        patch("sentinel.__main__.compile_graph") as mock_compile,
        pytest.raises(SystemExit) as exc,
    ):
        main()
    assert exc.value.code == 2  # noqa: PLR2004
    assert message in capsys.readouterr().err
    mock_compile.assert_not_called()


@pytest.mark.parametrize(
    ("argv", "checked"),
    [(["sentinel", "--allow-unchecked", "AAPL"], False), (["sentinel", "AAPL"], True)],
)
def test_main_runs_a_checked_input_or_with_allow_unchecked(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    argv: list[str],
    *,
    checked: bool,
) -> None:
    """A checked input runs; an unchecked one runs only with --allow-unchecked."""
    _saved(tmp_path, checked=checked)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", argv)
    mock_graph = _mock_graph({"ticker": "AAPL", "brief": "Brief."})
    p_ckpt, p_graph, p_output, _ = _patch_cli(mock_graph)
    with p_ckpt, p_graph, p_output:
        main()
    assert mock_graph.astream.call_count == 1
