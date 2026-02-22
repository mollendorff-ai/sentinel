"""Output writer -- persists pipeline results to structured directory."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_DIR = Path("output")


def write_run_output(
    state: dict[str, Any],
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> Path:
    """Write all pipeline artifacts to a timestamped directory.

    Creates::

        output/{TICKER}/{YYYYMMDD-HHMMSS}/
            brief.md
            raw_data.json
            model.yaml
            forge_results.json
            risk_analysis.json      (full mode only)
            scenario_analysis.json  (full mode only)

    Returns the run directory path.
    """
    ticker = state.get("ticker", "UNKNOWN")
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S")
    run_dir = output_dir / ticker / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)

    # Always write core files
    _write_text(run_dir / "brief.md", state.get("brief", ""))
    _write_json(run_dir / "raw_data.json", state.get("raw_data", {}))
    _write_text(run_dir / "model.yaml", state.get("model_yaml", ""))
    _write_json(run_dir / "forge_results.json", state.get("forge_results", {}))

    # Conditionally write risk analysis
    risk = state.get("risk_analysis")
    if risk and "error" not in risk:
        _write_json(run_dir / "risk_analysis.json", risk)

    # Conditionally write scenario analysis
    scenario = state.get("scenario_analysis")
    if scenario and "error" not in scenario:
        _write_json(run_dir / "scenario_analysis.json", scenario)

    logger.info("Output written to %s", run_dir)
    return run_dir


def _write_json(path: Path, data: dict[str, Any]) -> None:
    """Write pretty-printed JSON."""
    path.write_text(json.dumps(data, indent=2, default=str) + "\n")


def _write_text(path: Path, content: str) -> None:
    """Write text, ensuring trailing newline."""
    if content and not content.endswith("\n"):
        content += "\n"
    path.write_text(content)
