"""Tests for saved inputs and the expected-figures check."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from sentinel.inputs import (
    Expected,
    InputError,
    compare_with_expected,
    compare_with_results,
    latest_period,
    load_input,
    validate_period,
)

if TYPE_CHECKING:
    from pathlib import Path


RESULTS = "results:\n  outputs.gross_profit: 4\n"


def _write(folder: Path, *, expected: str = "figures:\n  revenue: 10\n" + RESULTS) -> None:
    folder.mkdir(parents=True)
    (folder / "release.md").write_text("doc")
    (folder / "source.yaml").write_text("url: https://example.com\n")
    (folder / "expected.yaml").write_text(expected)


def test_load_input_reads_all_three_files(tmp_path: Path) -> None:
    """The newest period is loaded with its document, source and expected figures."""
    _write(tmp_path / "AAPL" / "FY2026-Q3")
    _write(
        tmp_path / "AAPL" / "FY2026-Q4",
        expected="checked: true\nfigures:\n  revenue: 12\n" + RESULTS,
    )

    saved = load_input("aapl", inputs_dir=tmp_path)

    assert saved.ticker == "AAPL"
    assert saved.period == "FY2026-Q4"
    assert saved.document == "doc"
    assert saved.source == {"url": "https://example.com"}
    assert saved.expected == Expected(
        figures={"revenue": 12.0},
        tolerance=0.5,
        checked=True,
        results={"outputs.gross_profit": 4.0},
    )


def test_load_input_named_period(tmp_path: Path) -> None:
    """A period given by name is loaded even if it is not the newest."""
    _write(tmp_path / "AAPL" / "FY2026-Q3")
    _write(tmp_path / "AAPL" / "FY2026-Q4")
    assert load_input("AAPL", "FY2026-Q3", inputs_dir=tmp_path).period == "FY2026-Q3"


def test_checked_must_be_true_exactly(tmp_path: Path) -> None:
    """Only `checked: true` counts as checked by a person; a string does not."""
    _write(tmp_path / "AAPL" / "P1", expected='checked: "yes"\nfigures:\n  revenue: 1\n' + RESULTS)
    assert load_input("AAPL", inputs_dir=tmp_path).expected.checked is False


@pytest.mark.parametrize(
    ("expected", "message"),
    [
        ("- a list\n", "is not a YAML mapping"),
        ("figures: [\n", "is not valid YAML"),
        ("checked: true\n" + RESULTS, "has no figures"),
        ("figures:\n  revenue: lots\n" + RESULTS, "figures 'revenue' is not a number"),
        ("figures:\n  revenue: true\n" + RESULTS, "figures 'revenue' is not a number"),
        ("figures:\n  revenue: .nan\n" + RESULTS, "figures 'revenue' is not a number"),
        ("figures:\n  revenue: 1\n", "has no results"),
        ("figures:\n  revenue: 1\nresults:\n  x: big\n", "results 'x' is not a number"),
        ("tolerance: -1\nfigures:\n  revenue: 1\n" + RESULTS, "tolerance must be a number"),
    ],
)
def test_malformed_expected_file(tmp_path: Path, expected: str, message: str) -> None:
    """A malformed expected.yaml is refused with the reason."""
    _write(tmp_path / "AAPL" / "P1", expected=expected)
    with pytest.raises(InputError, match=message):
        load_input("AAPL", inputs_dir=tmp_path)


@pytest.mark.parametrize("missing", ["release.md", "source.yaml", "expected.yaml"])
def test_missing_file(tmp_path: Path, missing: str) -> None:
    """An input without one of its three files is refused, naming the file."""
    folder = tmp_path / "AAPL" / "P1"
    _write(folder)
    (folder / missing).unlink()
    with pytest.raises(InputError, match=f"has no {missing}"):
        load_input("AAPL", inputs_dir=tmp_path)


def test_no_input_for_ticker(tmp_path: Path) -> None:
    """A ticker with no folder, or an empty one, has no latest period."""
    with pytest.raises(InputError, match="No saved input for MSFT"):
        latest_period("MSFT", inputs_dir=tmp_path)
    (tmp_path / "MSFT").mkdir()
    with pytest.raises(InputError, match="No saved input for MSFT"):
        latest_period("MSFT", inputs_dir=tmp_path)


@pytest.mark.parametrize("bad", ["../x", "a/b", "", " ", "-x", "x" * 40])
def test_validate_period_refuses_unsafe_names(bad: str) -> None:
    """A period becomes a folder name, so path separators and odd names are refused."""
    with pytest.raises(InputError, match="Invalid period"):
        validate_period(bad)


def test_compare_with_expected() -> None:
    """Matches within the tolerance pass; differences and missing figures are listed."""
    expected = Expected(
        figures={"a": 10.0, "b": 20.0, "c": 30.0}, tolerance=0.5, checked=True, results={}
    )
    problems = compare_with_expected({"a": 10.4, "b": 21, "c": None}, expected)
    assert problems == ["b: expected 20, extracted 21", "c: expected 30, extracted None"]


def test_compare_with_results() -> None:
    """A Forge result equal to the filing passes; a wrong or missing one is listed."""
    expected = Expected(
        figures={},
        tolerance=0.5,
        checked=True,
        results={"outputs.gross_profit": 54820.0, "outputs.operating_income": 35631.0},
    )
    assert (
        compare_with_results(
            {"outputs.gross_profit": 54820.0, "outputs.operating_income": 35631.4}, expected
        )
        == []
    )
    assert compare_with_results(
        {"outputs.gross_profit": 54820.0, "outputs.operating_income": 74009.0}, expected
    ) == ["outputs.operating_income: the filing prints 35631, Forge calculated 74009"]
    assert compare_with_results({"outputs.gross_profit": 54820.0}, expected) == [
        "outputs.operating_income: the filing prints 35631, Forge calculated None"
    ]
