"""Sentinel CLI entry point — ``python -m sentinel AAPL``."""

from __future__ import annotations

import asyncio
import logging
import sys

from sentinel.graph.pipeline import compile_graph


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

    sys.stdout.write(f"Sentinel v0.2.0 — Analyzing {ticker}\n\n")

    graph = compile_graph()
    result = asyncio.run(graph.ainvoke({"ticker": ticker}))

    brief = result.get("brief", "No brief generated.")
    sys.stdout.write(f"{brief}\n")


if __name__ == "__main__":
    main()
