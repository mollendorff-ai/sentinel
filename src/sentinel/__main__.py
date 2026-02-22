"""Sentinel CLI entry point — ``python -m sentinel [--quick] AAPL``."""

from __future__ import annotations

import asyncio
import logging
import os
import sys

from sentinel.graph.pipeline import compile_graph
from sentinel.llm import PROVIDER_DEFAULTS


def main() -> None:
    """Run the Sentinel earnings-analysis pipeline for a given ticker."""
    args = sys.argv[1:]
    quick = "--quick" in args
    if quick:
        args.remove("--quick")

    if not args:
        sys.stderr.write("Usage: python -m sentinel [--quick] <TICKER>\n")
        sys.stderr.write("  --quick    Skip risk analysis and scenario planning\n")
        sys.stderr.write("Example: python -m sentinel AAPL\n")
        sys.exit(1)

    ticker = args[0].upper()

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
        f"Sentinel v0.3.0 — Analyzing {ticker} ({mode} mode, LLM: {model})\n\n",
    )

    graph = compile_graph()
    result = asyncio.run(graph.ainvoke({"ticker": ticker, "quick": quick}))

    brief = result.get("brief", "No brief generated.")
    sys.stdout.write(f"{brief}\n")


if __name__ == "__main__":
    main()
