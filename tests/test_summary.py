"""Tests for the run summary shown in the demo pull request."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from sentinel.summary import main, summarize

if TYPE_CHECKING:
    from pathlib import Path


def _run(tmp_path: Path, raw: dict, results: dict, brief: str | None = "The brief.") -> Path:
    run = tmp_path / "20261115-120000"
    run.mkdir()
    (run / "raw_data.json").write_text(json.dumps(raw))
    (run / "forge_results.json").write_text(json.dumps(results))
    if brief is not None:
        (run / "brief.md").write_text(brief + "\n")
    return run


def test_summary_of_a_good_run(tmp_path: Path) -> None:
    """Input, extracted figures, Forge's results and the brief, in that order."""
    raw = {
        "revenue": 114477,
        "net_income": 30711.5,
        "input": {
            "path": "inputs/AAPL/FY2026-Q4",
            "source_url": "https://www.sec.gov/x.htm",
            "expected_checked_by_person": True,
            "expected_mismatches": [],
        },
    }
    results = {
        "outputs.operating_income": 35631,
        "outputs.gross_margin": 0.47887,
        "filing_check": {"checked": ["outputs.operating_income"], "mismatches": []},
    }
    text = summarize(_run(tmp_path, raw, results))

    assert "`inputs/AAPL/FY2026-Q4` (https://www.sec.gov/x.htm)" in text
    assert "checked by a person:** yes" in text
    assert "| revenue | 114,477 |" in text
    assert "| net_income | 30,711.50 |" in text
    assert "| cost_of_revenue | — |" in text
    assert "| outputs.operating_income | 35,631 |" in text
    assert "| outputs.gross_margin | 0.4789 |" in text
    assert "All match expected.yaml." in text
    assert (
        "Forge's `outputs.operating_income` equal the figures the filing prints "
        "(the margins are not compared)." in text
    )
    assert text.index("Forge's results") < text.index("The brief.")


def test_summary_of_a_failed_run(tmp_path: Path) -> None:
    """A failed run shows the reason and the differences; missing files do not crash it."""
    raw = {
        "error": "Extracted figures differ",
        "revenue": True,
        "input": {"expected_mismatches": ["revenue: expected 1, extracted 2"]},
    }
    run = _run(tmp_path, raw, {}, brief=None)
    (run / "forge_results.json").write_text("[1, 2]")
    text = summarize(run)

    assert "**Failed:** Extracted figures differ" in text
    assert "checked by a person:** no" in text
    assert "Differences: revenue: expected 1, extracted 2" in text
    assert "| revenue | — |" in text
    assert "(no brief)" in text
    assert "were not compared with the filing (a run before 0.9.0)" in text


def test_summary_of_a_wrong_formula(tmp_path: Path) -> None:
    """Forge's results that differ from the filing are listed."""
    results = {
        "error": "Forge's results differ from the filing",
        "filing_check": {
            "checked": ["outputs.operating_income"],
            "mismatches": [
                "outputs.operating_income: the filing prints 35631, Forge calculated 74009"
            ],
        },
    }
    text = summarize(_run(tmp_path, {"input": {}}, results))
    assert (
        "Differences from the filing: outputs.operating_income: "
        "the filing prints 35631, Forge calculated 74009" in text
    )


def test_summary_of_an_empty_folder(tmp_path: Path) -> None:
    """A folder with nothing in it still gives a summary."""
    assert "`?` (no source url)" in summarize(tmp_path)


def test_main_prints_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The module prints the summary of the folder it is given."""
    run = _run(tmp_path, {}, {})
    monkeypatch.setattr("sys.argv", ["summary", str(run)])
    main()
    assert "## Sentinel run `20261115-120000`" in capsys.readouterr().out


def test_main_needs_one_folder(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Without exactly one argument it prints the usage and exits 2."""
    monkeypatch.setattr("sys.argv", ["summary"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2  # noqa: PLR2004
    assert "Usage" in capsys.readouterr().err
