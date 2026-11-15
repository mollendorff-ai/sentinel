"""Saved inputs: the documents a demo run reads, and the figures a person typed from them.

An input lives in ``inputs/<TICKER>/<PERIOD>/`` (ADR-012)::

    release.md      the document, as saved (an earnings release from SEC EDGAR)
    source.yaml     where it came from: url, filed, saved_on, saved_with
    expected.yaml   headline figures typed by a person from the document

A run fails when the figures the LLM extracts differ from ``expected.yaml``: Forge
checks the arithmetic, this checks the reading.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from sentinel.validation import validate_ticker

DEFAULT_INPUTS_DIR = Path("inputs")
DOCUMENT_FILE = "release.md"
SOURCE_FILE = "source.yaml"
EXPECTED_FILE = "expected.yaml"

_PERIOD = re.compile(r"[A-Za-z0-9][A-Za-z0-9.\-]{0,31}")


class InputError(ValueError):
    """A saved input is missing, incomplete or malformed."""


@dataclass(frozen=True)
class Expected:
    """Figures a person typed from the document, and whether they say they checked them."""

    figures: dict[str, float]
    tolerance: float
    checked: bool


@dataclass(frozen=True)
class SavedInput:
    """One saved input: the document text, its source and its expected figures."""

    ticker: str
    period: str
    path: Path
    document: str
    source: dict[str, Any]
    expected: Expected


def validate_period(raw: str) -> str:
    """Return *raw* if it is a safe folder name for a period (``FY2026-Q4``), else raise."""
    period = raw.strip()
    if not _PERIOD.fullmatch(period):
        msg = f"Invalid period {raw!r}: use letters, digits, '.' or '-' (e.g. FY2026-Q4)"
        raise InputError(msg)
    return period


def latest_period(ticker: str, *, inputs_dir: Path = DEFAULT_INPUTS_DIR) -> str:
    """Return the newest period folder saved for *ticker* (by name, so name them sortably)."""
    folder = inputs_dir / validate_ticker(ticker)
    periods = sorted(p.name for p in folder.iterdir() if p.is_dir()) if folder.is_dir() else []
    if not periods:
        msg = f"No saved input for {ticker} in {folder}/"
        raise InputError(msg)
    return periods[-1]


def load_input(
    ticker: str,
    period: str | None = None,
    *,
    inputs_dir: Path = DEFAULT_INPUTS_DIR,
) -> SavedInput:
    """Load the saved input for *ticker* (the newest period unless *period* is given)."""
    ticker = validate_ticker(ticker)
    period = validate_period(period) if period else latest_period(ticker, inputs_dir=inputs_dir)
    path = inputs_dir / ticker / period
    for name in (DOCUMENT_FILE, SOURCE_FILE, EXPECTED_FILE):
        if not (path / name).is_file():
            msg = f"Saved input {path}/ has no {name}"
            raise InputError(msg)
    return SavedInput(
        ticker=ticker,
        period=period,
        path=path,
        document=(path / DOCUMENT_FILE).read_text(encoding="utf-8"),
        source=_mapping(path / SOURCE_FILE),
        expected=_expected(path / EXPECTED_FILE),
    )


def _mapping(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        msg = f"{path} is not valid YAML: {exc}"
        raise InputError(msg) from exc
    if not isinstance(data, dict):
        msg = f"{path} is not a YAML mapping"
        raise InputError(msg)
    return data


def _expected(path: Path) -> Expected:
    data = _mapping(path)
    figures = data.get("figures")
    if not isinstance(figures, dict) or not figures:
        msg = f"{path} has no figures"
        raise InputError(msg)
    parsed: dict[str, float] = {}
    for name, value in figures.items():
        if not _is_number(value):
            msg = f"{path}: figure {name!r} is not a number: {value!r}"
            raise InputError(msg)
        parsed[str(name)] = float(value)
    tolerance = data.get("tolerance", 0.5)
    if not _is_number(tolerance) or tolerance < 0:
        msg = f"{path}: tolerance must be a number of 0 or more"
        raise InputError(msg)
    return Expected(
        figures=parsed, tolerance=float(tolerance), checked=data.get("checked") is True
    )


def _is_number(value: object) -> bool:
    return (
        isinstance(value, int | float)
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def compare_with_expected(raw_data: dict[str, Any], expected: Expected) -> list[str]:
    """Return one line per expected figure extracted wrong or not at all; empty if all match."""
    problems: list[str] = []
    for name, want in expected.figures.items():
        got = raw_data.get(name)
        if not _is_number(got):
            problems.append(f"{name}: expected {want:g}, extracted {got!r}")
        elif abs(float(got) - want) > expected.tolerance:
            problems.append(f"{name}: expected {want:g}, extracted {float(got):g}")
    return problems
