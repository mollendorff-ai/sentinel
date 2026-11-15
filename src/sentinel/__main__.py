"""Sentinel CLI entry point — ``python -m sentinel [--quick] [--hitl] [--period P] AAPL``.

Subcommands
-----------
``python -m sentinel mcp``  — start MCP server on stdio transport.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from dotenv import load_dotenv

from sentinel import __version__, handoff
from sentinel.approval import prompt_approval, show_draft_summary
from sentinel.checkpointer import create_checkpointer
from sentinel.graph.pipeline import compile_graph
from sentinel.handoff import CHAT_PROVIDER
from sentinel.inputs import validate_period
from sentinel.llm import PROVIDER_DEFAULTS
from sentinel.mcp import run_mcp_server
from sentinel.output import write_run_output
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

    run_dir = write_run_output(result)
    handoff.store().keep(run_dir)
    sys.stdout.write(f"{result.get('brief', 'No brief generated.')}\n")
    sys.stdout.write(f"Output: {run_dir}\n")
    reason = run_failed(result)
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


async def _run_all(  # noqa: PLR0913 - one keyword per CLI option
    tickers: list[str],
    *,
    period: str | None,
    quick: bool,
    hitl: bool,
    provider: str,
    model: str,
) -> tuple[int, int]:
    """Run the pipeline for each ticker; return (runs failed, runs waiting for the chat)."""
    mode = "quick" if quick else "full"
    interrupt = ["synthesizer"] if hitl else None
    failures = 0
    waiting = 0

    async with create_checkpointer() as checkpointer:
        graph = compile_graph(checkpointer=checkpointer, interrupt_before=interrupt)

        for ticker in tickers:
            timestamp = datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S")
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
                "configurable": {
                    "thread_id": f"{ticker}-{timestamp}",
                },
            }

            sys.stdout.write(f"--- {ticker} ---\n")
            handoff.store().reset()

            # Stream first pass (halts at interrupt if hitl=True)
            async for update in graph.astream(
                {"ticker": ticker, "quick": quick, "period": period or ""},
                config=config,
                stream_mode="updates",
            ):
                for node_name in update:
                    sys.stdout.write(f"  [{_AGENT_LABELS.get(node_name, node_name)}]\n")

            # HITL approval gate
            if hitl:
                snapshot = await graph.aget_state(config)
                if snapshot.next and "synthesizer" in snapshot.next:
                    show_draft_summary(snapshot.values)
                    approved, feedback = prompt_approval()
                    if not approved and feedback:
                        await graph.aupdate_state(config, {"analyst_feedback": feedback})
                    # Resume from interrupt
                    async for update in graph.astream(None, config=config, stream_mode="updates"):
                        for node_name in update:
                            sys.stdout.write(f"  [{_AGENT_LABELS.get(node_name, node_name)}]\n")

            outcome = _finish(dict((await graph.aget_state(config)).values))
            failures += outcome == "failed"
            waiting += outcome == "waiting"

    return failures, waiting


_USAGE = (
    "Usage: python -m sentinel [--quick] [--hitl] [--period PERIOD] <TICKER> [TICKER ...]\n"
    "  Reads the saved input in inputs/<TICKER>/<PERIOD>/ (the newest period by default)\n"
    "  and writes the run to runs/<TICKER>/<timestamp>/. Exits 1 if a run failed,\n"
    "  3 if it waits for the chat to answer a prompt (SENTINEL_LLM_PROVIDER=chat).\n"
    "  --quick      Skip risk analysis and scenario planning\n"
    "  --hitl       Pause before Synthesizer for analyst approval\n"
    "  --period P   Read inputs/<TICKER>/P/ instead of the newest period\n"
    "  --version    Print the version\n"
    "  --help       Show this help\n"
    "Example: python -m sentinel AAPL MSFT GOOG\n"
)
_FLAGS = {"--quick", "--hitl"}


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

    # MCP subcommand — dispatch before touching the other arguments
    if len(sys.argv) > 1 and sys.argv[1] == "mcp":
        run_mcp_server()
        sys.exit(0)

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
    hitl = "--hitl" in args
    names = [a for a in args if a not in _FLAGS]

    if not names:
        sys.stderr.write(_USAGE)
        sys.exit(1)

    try:
        tickers = [validate_ticker(t) for t in names]
    except ValueError as exc:
        sys.stderr.write(f"{exc}\n")
        sys.exit(2)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    provider = os.environ.get("SENTINEL_LLM_PROVIDER", "anthropic").lower()
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
        _run_all(tickers, period=period, quick=quick, hitl=hitl, provider=provider, model=model),
    )
    if failures:
        sys.exit(1)
    if waiting:
        sys.exit(EXIT_WAITING)


if __name__ == "__main__":
    main()
