"""Sentinel CLI entry point — ``python -m sentinel [--quick] AAPL [MSFT ...]``."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import UTC, datetime

from sentinel.checkpointer import create_checkpointer
from sentinel.graph.pipeline import compile_graph
from sentinel.llm import PROVIDER_DEFAULTS
from sentinel.output import write_run_output

VERSION = "0.4.0"


async def _run_all(
    tickers: list[str],
    *,
    quick: bool,
    provider: str,
    model: str,
) -> None:
    """Run the pipeline for each ticker sequentially."""
    mode = "quick" if quick else "full"

    with create_checkpointer() as checkpointer:
        graph = compile_graph(checkpointer=checkpointer)

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
            result = await graph.ainvoke(
                {"ticker": ticker, "quick": quick},
                config=config,
            )

            run_dir = write_run_output(result)
            brief = result.get("brief", "No brief generated.")
            sys.stdout.write(f"{brief}\n")
            sys.stdout.write(f"Output: {run_dir}\n\n")


def main() -> None:
    """Run the Sentinel earnings-analysis pipeline for one or more tickers."""
    args = sys.argv[1:]
    quick = "--quick" in args
    if quick:
        args.remove("--quick")

    if not args:
        sys.stderr.write(
            "Usage: python -m sentinel [--quick] <TICKER> [TICKER ...]\n",
        )
        sys.stderr.write("  --quick    Skip risk analysis and scenario planning\n")
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

    asyncio.run(_run_all(tickers, quick=quick, provider=provider, model=model))


if __name__ == "__main__":
    main()
