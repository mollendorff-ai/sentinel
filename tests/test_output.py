"""Tests for the output writer module."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sentinel.output import _write_json, _write_text, write_run_output

EXPECTED_REVENUE = 100_000
EXPECTED_NET_INCOME = 25_000
EXPECTED_MONTE_CARLO_P50 = 1.5
EXPECTED_BULL_UPSIDE = 0.2


def _full_state() -> dict[str, Any]:
    """Return a complete state dict for testing."""
    return {
        "ticker": "AAPL",
        "brief": "Apple looks strong.",
        "raw_data": {"revenue": EXPECTED_REVENUE},
        "model_yaml": "_forge_version: 5.0.0\n",
        "forge_results": {"net_income": EXPECTED_NET_INCOME},
        "risk_analysis": {"monte_carlo": {"p50": EXPECTED_MONTE_CARLO_P50}},
        "scenario_analysis": {"bull": {"upside": EXPECTED_BULL_UPSIDE}},
    }


def test_write_run_output_creates_directory(tmp_path: Path) -> None:
    """Verify output/{TICKER}/{TIMESTAMP}/ structure is created."""
    run_dir = write_run_output(_full_state(), output_dir=tmp_path)
    assert run_dir.exists()
    assert run_dir.parent.name == "AAPL"
    assert run_dir.parent.parent == tmp_path


def test_write_run_output_writes_brief(tmp_path: Path) -> None:
    """Verify brief.md is written with correct content."""
    run_dir = write_run_output(_full_state(), output_dir=tmp_path)
    brief = (run_dir / "brief.md").read_text()
    assert "Apple looks strong." in brief


def test_write_run_output_writes_raw_data(tmp_path: Path) -> None:
    """Verify raw_data.json is valid JSON with expected content."""
    run_dir = write_run_output(_full_state(), output_dir=tmp_path)
    data = json.loads((run_dir / "raw_data.json").read_text())
    assert data["revenue"] == EXPECTED_REVENUE


def test_write_run_output_writes_model_yaml(tmp_path: Path) -> None:
    """Verify model.yaml is written with correct content."""
    run_dir = write_run_output(_full_state(), output_dir=tmp_path)
    yaml_content = (run_dir / "model.yaml").read_text()
    assert "_forge_version: 5.0.0" in yaml_content


def test_write_run_output_writes_forge_results(tmp_path: Path) -> None:
    """Verify forge_results.json is valid JSON with expected content."""
    run_dir = write_run_output(_full_state(), output_dir=tmp_path)
    data = json.loads((run_dir / "forge_results.json").read_text())
    assert data["net_income"] == EXPECTED_NET_INCOME


def test_write_run_output_includes_risk_when_present(tmp_path: Path) -> None:
    """Verify risk_analysis.json is written when risk data exists."""
    run_dir = write_run_output(_full_state(), output_dir=tmp_path)
    data = json.loads((run_dir / "risk_analysis.json").read_text())
    assert data["monte_carlo"]["p50"] == EXPECTED_MONTE_CARLO_P50


def test_write_run_output_includes_scenario_when_present(tmp_path: Path) -> None:
    """Verify scenario_analysis.json is written when scenario data exists."""
    run_dir = write_run_output(_full_state(), output_dir=tmp_path)
    data = json.loads((run_dir / "scenario_analysis.json").read_text())
    assert data["bull"]["upside"] == EXPECTED_BULL_UPSIDE


def test_write_run_output_skips_risk_with_error(tmp_path: Path) -> None:
    """Verify risk_analysis.json is not written when risk contains an error."""
    state = _full_state()
    state["risk_analysis"] = {"error": "LLM failed"}
    run_dir = write_run_output(state, output_dir=tmp_path)
    assert not (run_dir / "risk_analysis.json").exists()


def test_write_run_output_skips_scenario_with_error(tmp_path: Path) -> None:
    """Verify scenario_analysis.json is not written when scenario has an error."""
    state = _full_state()
    state["scenario_analysis"] = {"error": "LLM failed"}
    run_dir = write_run_output(state, output_dir=tmp_path)
    assert not (run_dir / "scenario_analysis.json").exists()


def test_write_run_output_handles_missing_fields(tmp_path: Path) -> None:
    """Verify empty state doesn't crash and creates directory."""
    run_dir = write_run_output({}, output_dir=tmp_path)
    assert run_dir.exists()
    assert (run_dir / "brief.md").exists()
    assert (run_dir / "raw_data.json").exists()


def test_write_run_output_returns_run_dir(tmp_path: Path) -> None:
    """Verify the function returns the run directory Path."""
    run_dir = write_run_output(_full_state(), output_dir=tmp_path)
    assert isinstance(run_dir, Path)
    assert run_dir.is_dir()


def test_write_json_formats_with_indent(tmp_path: Path) -> None:
    """Verify JSON is written with indent=2 formatting."""
    path = tmp_path / "test.json"
    _write_json(path, {"key": "value"})
    content = path.read_text()
    assert '  "key": "value"' in content
    assert content.endswith("\n")


def test_write_text_adds_trailing_newline(tmp_path: Path) -> None:
    """Verify trailing newline is added to text without one."""
    path = tmp_path / "test.txt"
    _write_text(path, "hello")
    assert path.read_text() == "hello\n"


def test_write_text_preserves_existing_newline(tmp_path: Path) -> None:
    """Verify no double newline when text already ends with one."""
    path = tmp_path / "test.txt"
    _write_text(path, "hello\n")
    assert path.read_text() == "hello\n"
