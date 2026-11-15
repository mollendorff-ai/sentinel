"""Tests for the Research agent node: saved input in, checked figures out."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

import pytest

from sentinel.agents.research import _parse_llm_response, research_node

if TYPE_CHECKING:
    from pathlib import Path

REVENUE = 100_000
FIGURES = {"revenue": REVENUE, "cost_of_revenue": 60_000, "net_income": 25_000}


def _save_input(root: Path, *, checked: bool = True, period: str = "FY2026-Q4") -> Path:
    folder = root / "inputs" / "AAPL" / period
    folder.mkdir(parents=True)
    (folder / "release.md").write_text("# Apple reports\nTotal net sales 100,000\n")
    (folder / "source.yaml").write_text("url: https://www.sec.gov/example.htm\n")
    lines = "\n".join(f"  {k}: {v}" for k, v in FIGURES.items())
    (folder / "expected.yaml").write_text(f"checked: {str(checked).lower()}\nfigures:\n{lines}\n")
    return folder


def _llm(content: str | Exception) -> Any:  # noqa: ANN401
    if isinstance(content, Exception):
        return AsyncMock(ainvoke=AsyncMock(side_effect=content))
    response = AsyncMock()
    response.content = content
    return AsyncMock(ainvoke=AsyncMock(return_value=response))


@pytest.fixture
def in_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Run the test from a folder that holds one saved AAPL input."""
    _save_input(tmp_path)
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.mark.usefixtures("in_repo")
async def test_research_node_extracts_and_checks() -> None:
    """Figures that match expected.yaml pass, with the input recorded beside them."""
    extracted = {"period": "Q4 FY2026", **FIGURES, "eps": 2.1}
    llm = _llm(json.dumps(extracted))
    with patch("sentinel.agents.research.get_llm", return_value=llm):
        result = await research_node({"ticker": "AAPL"})

    raw = result["raw_data"]
    assert "error" not in raw
    assert raw["revenue"] == REVENUE
    assert raw["ticker"] == "AAPL"
    assert raw["input"] == {
        "path": "inputs/AAPL/FY2026-Q4",
        "period": "FY2026-Q4",
        "source_url": "https://www.sec.gov/example.htm",
        "expected_checked_by_person": True,
        "expected_mismatches": [],
    }
    prompt = llm.ainvoke.call_args[0][0]
    assert "Total net sales 100,000" in prompt
    assert "<<<DOCUMENT" in prompt


@pytest.mark.usefixtures("in_repo")
async def test_research_node_fails_when_figures_differ() -> None:
    """A figure the LLM misread stops the run with the figure named."""
    extracted = {**FIGURES, "revenue": 99_000}
    with patch("sentinel.agents.research.get_llm", return_value=_llm(json.dumps(extracted))):
        result = await research_node({"ticker": "AAPL"})

    raw = result["raw_data"]
    assert raw["error"].startswith("Extracted figures differ from expected.yaml")
    assert raw["input"]["expected_mismatches"] == ["revenue: expected 100000, extracted 99000"]


async def test_research_node_reads_the_period_asked_for(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """state['period'] picks an older input over the newest one."""
    _save_input(tmp_path, period="FY2026-Q3")
    _save_input(tmp_path, period="FY2026-Q4")
    monkeypatch.chdir(tmp_path)
    with patch("sentinel.agents.research.get_llm", return_value=_llm(json.dumps(FIGURES))):
        result = await research_node({"ticker": "AAPL", "period": "FY2026-Q3"})

    assert result["raw_data"]["input"]["period"] == "FY2026-Q3"


async def test_research_node_records_an_unchecked_expected_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An expected.yaml nobody has checked still compares, and says it was not checked."""
    _save_input(tmp_path, checked=False)
    monkeypatch.chdir(tmp_path)
    with patch("sentinel.agents.research.get_llm", return_value=_llm(json.dumps(FIGURES))):
        result = await research_node({"ticker": "AAPL"})

    assert result["raw_data"]["input"]["expected_checked_by_person"] is False


async def test_research_node_without_saved_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No input folder for the ticker is an error, before any LLM call."""
    monkeypatch.chdir(tmp_path)
    llm = _llm("{}")
    with patch("sentinel.agents.research.get_llm", return_value=llm):
        result = await research_node({"ticker": "MSFT"})

    assert "No saved input for MSFT" in result["raw_data"]["error"]
    llm.ainvoke.assert_not_called()


@pytest.mark.usefixtures("in_repo")
async def test_research_node_handles_llm_exception() -> None:
    """An LLM failure is an error for the ticker, not a crash."""
    with patch("sentinel.agents.research.get_llm", return_value=_llm(RuntimeError("boom"))):
        result = await research_node({"ticker": "AAPL"})

    assert result["raw_data"]["error"] == "LLM extraction failed for AAPL"


@pytest.mark.usefixtures("in_repo")
async def test_research_node_handles_unparseable_response() -> None:
    """An answer with no JSON is an error, and keeps the input it came from."""
    llm = _llm("I cannot extract any data from this document.")
    with patch("sentinel.agents.research.get_llm", return_value=llm):
        result = await research_node({"ticker": "AAPL"})

    raw = result["raw_data"]
    assert raw["error"] == "Failed to parse extraction response"
    assert raw["input"]["period"] == "FY2026-Q4"


@pytest.mark.usefixtures("in_repo")
async def test_research_node_accepts_non_string_content() -> None:
    """A provider that returns content blocks instead of a string is read as text."""
    response = AsyncMock()
    response.content = [{"type": "text", "text": "no json"}]
    llm = AsyncMock(ainvoke=AsyncMock(return_value=response))
    with patch("sentinel.agents.research.get_llm", return_value=llm):
        result = await research_node({"ticker": "AAPL"})

    assert "error" in result["raw_data"]


def test_parse_llm_response_finds_json_in_text() -> None:
    """JSON wrapped in prose is still read."""
    assert _parse_llm_response('Here: {"revenue": 5} done')["revenue"] == 5  # noqa: PLR2004


def test_parse_llm_response_handles_broken_json_inside_braces() -> None:
    """Text with braces that is still not JSON returns the error dict instead of raising."""
    result = _parse_llm_response("Here you go: {not valid json} thanks")
    assert result["error"] == "Failed to parse extraction response"
