"""Tests for ticker validation."""

from __future__ import annotations

import pytest

from sentinel.validation import validate_ticker


@pytest.mark.parametrize("raw", ["AAPL", "aapl", " msft ", "BRK.B", "BF-B", "A"])
def test_valid_tickers_are_normalised(raw: str) -> None:
    """Real tickers pass and are upper-cased."""
    assert validate_ticker(raw) == raw.strip().upper()


@pytest.mark.parametrize(
    "raw",
    ["", "../../ESCAPED", "AAPL/..", "A B", "1ABC", "TOOLONGTICKER", "AAPL;rm", "..", "-X"],
)
def test_invalid_tickers_are_refused(raw: str) -> None:
    """Anything that could escape a folder or is not ticker-shaped is refused."""
    with pytest.raises(ValueError, match="Invalid ticker"):
        validate_ticker(raw)
