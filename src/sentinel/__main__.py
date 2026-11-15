"""Sentinel CLI entry point — ``python -m sentinel [--quick] [--period P] AAPL``."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from typing import TYPE_CHECKING, Any

from dotenv import load_dotenv

from sentinel import __version__, handoff
from sentinel.graph.pipeline import compile_graph
from sentinel.handoff import CHAT_PROVIDER, QuietWhileWaiting
from sentinel.inputs import InputError, load_input, validate_period
from sentinel.llm import PROVIDER_DEFAULTS, missing_api_key
from sentinel.output import FAILED_OUTPUT_DIR, write_run_output
from sentinel.validation import validate_ticker

if TYPE_CHECKING:
    from sentinel.handoff import Exchange

VERSION = __version__
EXIT_WAITING = 3
"""Exit status while a prompt waits for the chat's answer (ADR-013)."""


def run_failed(result: dict[str, Any]) -> str:
    """Return why a finished run failed, or an empty string if it produced a brief."""
    for key in ("raw_data", "forge_results"):
        error = (result.get(key) or {}).get("error")
        if error:
            return f"{key}: {error}"
    brief = result.get("brief") or ""
    if not brief:
        return "no brief was written"
    if brief.startswith("Analysis incomplete"):
        return f"brief: {brief}"
    return ""


def _report_waiting(pending: list[Exchange]) -> None:
    """Tell the AI in the chat which prompts to answer before running again."""
    sys.stdout.write("WAITING for the chat to answer (SENTINEL_LLM_PROVIDER=chat):\n")
    for exchange in pending:
        sys.stdout.write(
            f"  {exchange.role}: read {exchange.prompt_path}\n"
            f"  {' ' * len(exchange.role)}  write the answer to {exchange.answer_path}\n",
        )
    sys.stdout.write("Then run the same command again.\n")


def _finish(result: dict[str, Any]) -> str:
    """Write and report one finished run; return ``ok``, ``failed`` or ``waiting``."""
    pending = list(handoff.store().pending)
    if pending:
        _report_waiting(pending)
        sys.stdout.write("\n")
        return "waiting"

    reason = run_failed(result)
    # A failed run is kept out of runs/, which is committed and read as history (ADR-012).
    run_dir = (
        write_run_output(result, output_dir=FAILED_OUTPUT_DIR)
        if reason
        else write_run_output(result)
    )
    handoff.store().keep(run_dir)
    sys.stdout.write(f"{result.get('brief', 'No brief generated.')}\n")
    sys.stdout.write(f"Output: {run_dir}\n")
    if reason:
        sys.stdout.write(f"FAILED: {reason}\n")
    sys.stdout.write("\n")
    return "failed" if reason else "ok"


_AGENT_LABELS: dict[str, str] = {
    "research": "Research",
    "retriever": "Retriever",
    "modeler": "Modeler",
    "risk_analyst": "Risk Analyst",
    "scenario_planner": "Scenario Planner",
    "synthesizer": "Synthesizer",
}


async def _run_all(
    tickers: list[str],
    *,
    period: str | None,
    quick: bool,
    provider: str,
    model: str,
) -> tuple[int, int]:
    """Run the pipeline for each ticker; return (runs failed, runs waiting for the chat)."""
    mode = "quick" if quick else "full"
    failures = 0
    waiting = 0
    graph = compile_graph()

    for ticker in tickers:
        config = {
            "run_name": f"sentinel-{ticker}-{mode}",
            "tags": [f"ticker:{ticker}", f"mode:{mode}", f"v{VERSION}"],
            "metadata": {
                "ticker": ticker,
                "mode": mode,
                "version": VERSION,
                "provider": provider,
                "model": model,
            },
        }

        sys.stdout.write(f"--- {ticker} ---\n")
        handoff.store().reset()
        result: dict[str, Any] = {}
        async for update in graph.astream(
            {"ticker": ticker, "quick": quick, "period": period or ""},
            config=config,
            stream_mode="updates",
        ):
            for node_name, values in update.items():
                sys.stdout.write(f"  [{_AGENT_LABELS.get(node_name, node_name)}]\n")
                result.update(values or {})

        outcome = _finish({"ticker": ticker, **result})
        failures += outcome == "failed"
        waiting += outcome == "waiting"

    return failures, waiting


_USAGE = (
    "Usage: python -m sentinel [--quick] [--period PERIOD] <TICKER> [TICKER ...]\n"
    "  Reads the saved input in inputs/<TICKER>/<PERIOD>/ (the newest period by default)\n"
    "  and writes the run to runs/<TICKER>/<timestamp>/, or a failed run to\n"
    "  .sentinel/failed/<TICKER>/<timestamp>/. Exits 1 if a run failed,\n"
    "  3 if it waits for the chat to answer a prompt (SENTINEL_LLM_PROVIDER=chat).\n"
    "  --quick      Skip risk analysis and scenario planning\n"
    "  --period P   Read inputs/<TICKER>/P/ instead of the newest period\n"
    "  --allow-unchecked  Run even if expected.yaml is not checked by a person\n"
    "  --version    Print the version\n"
    "  --help       Show this help\n"
    "Example: python -m sentinel AAPL MSFT GOOG\n"
)
_FLAGS = {"--quick", "--allow-unchecked"}


def _check_inputs(tickers: list[str], period: str | None, *, allow_unchecked: bool) -> None:
    """Exit 2 unless every ticker has a saved input whose expected.yaml a person checked."""
    for ticker in tickers:
        try:
            saved = load_input(ticker, period)
        except InputError as exc:
            sys.stderr.write(f"{exc}\n")
            sys.exit(2)
        if not saved.expected.checked and not allow_unchecked:
            sys.stderr.write(
                f"{saved.path}/expected.yaml is not checked by a person (checked: false).\n"
                "Check its figures against the filing and set checked: true, or pass\n"
                "--allow-unchecked for a test run (its summary will say it was not checked).\n",
            )
            sys.exit(2)


def _take_period(args: list[str]) -> tuple[list[str], str | None]:
    """Remove ``--period P`` from *args*; exit with a message if it is malformed."""
    if "--period" not in args:
        return args, None
    at = args.index("--period")
    if at + 1 >= len(args) or args[at + 1].startswith("-"):
        sys.stderr.write(f"--period needs a value\n{_USAGE}")
        sys.exit(2)
    try:
        period = validate_period(args[at + 1])
    except ValueError as exc:
        sys.stderr.write(f"{exc}\n")
        sys.exit(2)
    return args[:at] + args[at + 2 :], period


def main() -> None:
    """Run the Sentinel earnings-analysis pipeline for one or more tickers."""
    load_dotenv()  # reads .env from the current folder; real environment variables win

    args = sys.argv[1:]
    if "--help" in args or "-h" in args:
        sys.stdout.write(_USAGE)
        sys.exit(0)
    if "--version" in args:
        sys.stdout.write(f"sentinel {VERSION}\n")
        sys.exit(0)

    args, period = _take_period(args)

    unknown = [a for a in args if a.startswith("-") and a not in _FLAGS]
    if unknown:
        sys.stderr.write(f"Unknown option: {unknown[0]}\n{_USAGE}")
        sys.exit(2)

    quick = "--quick" in args
    names = [a for a in args if a not in _FLAGS]

    if not names:
        sys.stderr.write(_USAGE)
        sys.exit(1)

    try:
        tickers = [validate_ticker(t) for t in names]
    except ValueError as exc:
        sys.stderr.write(f"{exc}\n")
        sys.exit(2)
    _check_inputs(tickers, period, allow_unchecked="--allow-unchecked" in args)

    provider = os.environ.get("SENTINEL_LLM_PROVIDER", "anthropic").lower()
    key_problem = missing_api_key(provider)
    if key_problem:
        sys.stderr.write(f"{key_problem}\n")
        sys.exit(2)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # While a prompt waits for the chat, the agents after it fail on purpose; say only WAITING.
    for log_handler in logging.getLogger().handlers:
        log_handler.addFilter(QuietWhileWaiting())
    chat_label = (CHAT_PROVIDER, "the AI in this chat")
    _, default_model = PROVIDER_DEFAULTS.get(
        provider, chat_label if provider == CHAT_PROVIDER else ("", "unknown")
    )
    model = os.environ.get("SENTINEL_LLM_MODEL", default_model)
    mode = "quick" if quick else "full"

    sys.stdout.write(
        f"Sentinel v{VERSION} — Analyzing {', '.join(tickers)} ({mode} mode, LLM: {model})\n\n",
    )

    failures, waiting = asyncio.run(
        _run_all(tickers, period=period, quick=quick, provider=provider, model=model),
    )
    if failures:
        sys.exit(1)
    if waiting:
        sys.exit(EXIT_WAITING)


if __name__ == "__main__":
    main()
