"""Sentinel CLI entry point — ``python -m sentinel AAPL``."""

from __future__ import annotations

import asyncio
import logging
import os
import sys

from sentinel.graph.pipeline import compile_graph
from sentinel.llm import PROVIDER_DEFAULTS


def main() -> None:
    """Run the Sentinel earnings-analysis pipeline for a given ticker."""
    if len(sys.argv) < 2:  # noqa: PLR2004
        sys.stderr.write("Usage: python -m sentinel <TICKER>\n")
        sys.stderr.write("Example: python -m sentinel AAPL\n")
        sys.exit(1)

    ticker = sys.argv[1].upper()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    provider = os.environ.get("SENTINEL_LLM_PROVIDER", "anthropic").lower()
    _, default_model = PROVIDER_DEFAULTS.get(provider, ("", "unknown"))
    model = os.environ.get("SENTINEL_LLM_MODEL", default_model)
    sys.stdout.write(f"Sentinel v0.2.1 — Analyzing {ticker} (LLM: {model})\n\n")

    graph = compile_graph()
    result = asyncio.run(graph.ainvoke({"ticker": ticker}))

    brief = result.get("brief", "No brief generated.")
    sys.stdout.write(f"{brief}\n")


if __name__ == "__main__":
    main()
