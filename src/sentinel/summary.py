"""A run's summary in Markdown: what the demo pull request shows its reviewer (ADR-012).

``python -m sentinel.summary runs/AAPL/<timestamp>`` prints it.  It reads only the
files the run wrote, so the review is of what is committed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_FIGURES = ("revenue", "cost_of_revenue", "operating_expenses", "net_income")
_RESULTS = (
    "outputs.gross_profit",
    "outputs.operating_income",
    "outputs.gross_margin",
    "outputs.operating_margin",
    "outputs.net_margin",
)


def _json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _number(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return "—"
    if abs(value) < 1:
        return f"{value:.4f}"
    return f"{value:,.0f}" if float(value).is_integer() else f"{value:,.2f}"


def summarize(run_dir: Path) -> str:
    """Return the Markdown summary of the run in *run_dir*."""
    raw = _json(run_dir / "raw_data.json")
    results = _json(run_dir / "forge_results.json")
    source = raw.get("input") or {}
    checked = source.get("expected_checked_by_person")
    mismatches = source.get("expected_mismatches") or []

    lines = [
        f"## Sentinel run `{run_dir.name}`",
        "",
        f"- **Input:** `{source.get('path', '?')}` ({source.get('source_url', 'no source url')})",
        f"- **expected.yaml checked by a person:** {'yes' if checked else 'no'}",
    ]
    if raw.get("error"):
        lines.append(f"- **Failed:** {raw['error']}")
    lines += [
        "",
        "### Figures the LLM read, checked against expected.yaml (millions)",
        "",
        "| Figure | Extracted |",
        "| --- | ---: |",
        *(f"| {name} | {_number(raw.get(name))} |" for name in _FIGURES),
        "",
        "All match expected.yaml." if not mismatches else "Differences: " + "; ".join(mismatches),
        "",
        "### Forge's results",
        "",
        "| Result | Forge |",
        "| --- | ---: |",
        *(f"| {name} | {_number(results.get(name))} |" for name in _RESULTS),
        "",
        "Each result in this table is Forge's; the brief below was written by the LLM from them.",
        "",
        "### Brief",
        "",
    ]
    brief = run_dir / "brief.md"
    lines.append(brief.read_text(encoding="utf-8").strip() if brief.is_file() else "(no brief)")
    return "\n".join(lines) + "\n"


def main() -> None:
    """Print the summary of the run folder given on the command line."""
    if len(sys.argv) != 2:  # noqa: PLR2004
        sys.stderr.write("Usage: python -m sentinel.summary runs/<TICKER>/<timestamp>\n")
        sys.exit(2)
    sys.stdout.write(summarize(Path(sys.argv[1])))


if __name__ == "__main__":
    main()
