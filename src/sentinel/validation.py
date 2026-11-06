"""Input validation shared by the CLI and the MCP server."""

from __future__ import annotations

import re

_TICKER = re.compile(r"[A-Z][A-Z0-9.\-]{0,9}")


def validate_ticker(raw: str) -> str:
    """Return *raw* upper-cased if it looks like a stock ticker, else raise ``ValueError``.

    Accepts 1 to 10 characters: a letter first, then letters, digits, ``.`` or ``-``
    (``AAPL``, ``BRK.B``, ``BF-B``). The ticker becomes a folder name and part of a
    thread id, so anything with a path separator or whitespace is refused.
    """
    ticker = raw.strip().upper()
    if not _TICKER.fullmatch(ticker):
        msg = (
            f"Invalid ticker {raw!r}: use 1-10 letters, digits, '.' or '-', starting with a letter"
        )
        raise ValueError(msg)
    return ticker
