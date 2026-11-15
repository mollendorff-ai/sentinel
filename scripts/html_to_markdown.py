"""Turn an SEC filing's HTML into the Markdown a demo run reads (ADR-012).

Usage: python scripts/html_to_markdown.py release.htm > release.md

Paragraphs become lines and each table becomes a pipe table.  The spacer cells
EDGAR uses for alignment are dropped, and a ``$`` or ``%`` printed in a cell of its
own is joined to its number, so a row reads ``Total net sales | $ 114,512 | ...``.
Nothing is reworded or recalculated.  Needs beautifulsoup4 and lxml.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, Tag

_SPACE = re.compile(r"\s+")


def _clean(text: str) -> str:
    return _SPACE.sub(" ", text.replace("\xa0", " ")).strip()


def _row(tr: Tag) -> list[str]:
    cells = [_clean(td.get_text(" ")) for td in tr.find_all(["td", "th"])]
    merged: list[str] = []
    for cell in cells:
        if not cell:
            continue
        if merged and cell in {"%", ")", "%)"}:
            merged[-1] += cell
        elif merged and merged[-1] in {"$", "("}:
            merged[-1] = f"{merged[-1]} {cell}" if merged[-1] == "$" else merged[-1] + cell
        else:
            merged.append(cell)
    return merged


def _table(table: Tag) -> list[str]:
    rows = [r for r in (_row(tr) for tr in table.find_all("tr")) if r]
    if not rows:
        return []
    width = max(len(r) for r in rows)
    lines = ["| " + " | ".join(r + [""] * (width - len(r))) + " |" for r in rows]
    lines.insert(1, "|" + " --- |" * width)
    return lines


def convert(html: str) -> str:
    """Return the Markdown text of *html*: paragraphs and pipe tables, in document order."""
    soup = BeautifulSoup(html, "lxml")
    body = soup.body or soup
    out: list[str] = []
    for node in body.find_all(["table", "p", "div"]):
        if node.find_parent("table") is not None:
            continue
        if node.name == "table":
            out += ["", *_table(node), ""]
        elif node.find(["p", "div", "table"]) is None:
            text = _clean(node.get_text(" "))
            if text:
                out.append(text)
    return "\n".join(out).strip() + "\n"


if __name__ == "__main__":
    sys.stdout.write(convert(Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")))
