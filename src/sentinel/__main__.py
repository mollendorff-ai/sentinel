"""Sentinel CLI entry point — ``python -m sentinel [--quick] [--hitl] AAPL [MSFT ...]``."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import UTC, datetime

from sentinel.approval import prompt_approval, show_draft_summary
from sentinel.checkpointer import create_checkpointer
from sentinel.graph.pipeline import compile_graph
from sentinel.llm import PROVIDER_DEFAULTS
from sentinel.output import write_run_output
from sentinel.rag.store import create_store, ingest

VERSION = "0.7.0"

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
    quick: bool,
    hitl: bool,
    provider: str,
    model: str,
) -> None:
    """Run the pipeline for each ticker sequentially."""
    mode = "quick" if quick else "full"
    interrupt = ["synthesizer"] if hitl else None

    with create_checkpointer() as checkpointer:
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

            # Stream first pass (halts at interrupt if hitl=True)
            async for update in graph.astream(
                {"ticker": ticker, "quick": quick},
                config=config,
                stream_mode="updates",
            ):
                for node_name in update:
                    sys.stdout.write(
                        f"  [{_AGENT_LABELS.get(node_name, node_name)}]\n"
                    )

            # HITL approval gate
            if hitl:
                snapshot = graph.get_state(config)
                if snapshot.next and "synthesizer" in snapshot.next:
                    show_draft_summary(snapshot.values)
                    approved, feedback = prompt_approval()
                    if not approved and feedback:
                        await graph.aupdate_state(
                            config, {"analyst_feedback": feedback}
                        )
                    # Resume from interrupt
                    async for update in graph.astream(
                        None, config=config, stream_mode="updates"
                    ):
                        for node_name in update:
                            sys.stdout.write(
                                f"  [{_AGENT_LABELS.get(node_name, node_name)}]\n"
                            )

            result = dict(graph.get_state(config).values)

            run_dir = write_run_output(result)

            # Ingest current raw_data into Qdrant for future trend analysis
            raw_data = result.get("raw_data", {})
            if raw_data and "error" not in raw_data:
                try:
                    store = create_store()
                    ingest(store, raw_data)
                except Exception:
                    logging.getLogger(__name__).warning(
                        "Sentinel: Qdrant ingest failed for %s (non-fatal)", ticker
                    )

            brief = result.get("brief", "No brief generated.")
            sys.stdout.write(f"{brief}\n")
            sys.stdout.write(f"Output: {run_dir}\n\n")


def main() -> None:
    """Run the Sentinel earnings-analysis pipeline for one or more tickers."""
    args = sys.argv[1:]
    quick = "--quick" in args
    if quick:
        args.remove("--quick")
    hitl = "--hitl" in args
    if hitl:
        args.remove("--hitl")

    if not args:
        sys.stderr.write(
            "Usage: python -m sentinel [--quick] [--hitl] <TICKER> [TICKER ...]\n",
        )
        sys.stderr.write("  --quick    Skip risk analysis and scenario planning\n")
        sys.stderr.write("  --hitl     Pause before Synthesizer for analyst approval\n")
        sys.stderr.write("Example: python -m sentinel AAPL MSFT GOOG\n")
        sys.exit(1)

    tickers = [t.upper() for t in args]

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    provider = os.environ.get("SENTINEL_LLM_PROVIDER", "anthropic").lower()
    _, default_model = PROVIDER_DEFAULTS.get(provider, ("", "unknown"))
    model = os.environ.get("SENTINEL_LLM_MODEL", default_model)
    mode = "quick" if quick else "full"

    sys.stdout.write(
        f"Sentinel v{VERSION} — Analyzing {', '.join(tickers)} ({mode} mode, LLM: {model})\n\n",
    )

    asyncio.run(_run_all(tickers, quick=quick, hitl=hitl, provider=provider, model=model))


if __name__ == "__main__":
    main()
