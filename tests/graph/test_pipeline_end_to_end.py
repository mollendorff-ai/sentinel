"""The whole pipeline on the saved AAPL input, against the real pinned Forge.

The LLM is scripted (it answers what a correct LLM would), so this checks every
step that is not the LLM: reading the saved input, the expected-figure check, the
Forge model, Forge's numbers, risk and scenarios, history and the run folder.
It needs ``forge`` on PATH and no API key.  The real-LLM run is the demo workflow.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sentinel import handoff
from sentinel.__main__ import run_failed
from sentinel.graph.pipeline import compile_graph
from sentinel.output import write_run_output

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(shutil.which("forge") is None, reason="forge not on PATH"),
]

REPO = Path(__file__).resolve().parents[2]

# What the filing prints for the three months ended September 26, 2026 (millions).
EXTRACTION = {
    "company": "Apple Inc.",
    "period": "Q4 FY2026",
    "currency": "USD",
    "revenue": 114477,
    "cost_of_revenue": 59657,
    "gross_profit": 54820,
    "operating_expenses": 19189,
    "operating_income": 35631,
    "net_income": 30711,
    "eps": 2.10,
}
OPERATING_INCOME = 35631  # the filing's own figure, which Forge must reproduce

MODEL = """\
_forge_version: "5.1.0"
inputs:
  revenue: 114477
  cost_of_revenue: 59657
  operating_expenses: 19189
  net_income: 30711
outputs:
  gross_profit: {formula: "=inputs.revenue - inputs.cost_of_revenue"}
  operating_income: {formula: "=outputs.gross_profit - inputs.operating_expenses"}
  gross_margin: {formula: "=outputs.gross_profit / inputs.revenue"}
  operating_margin: {formula: "=outputs.operating_income / inputs.revenue"}
  net_margin: {formula: "=inputs.net_income / inputs.revenue"}
"""


def _scripted_llm(extraction: dict[str, Any], model: str = MODEL) -> MagicMock:
    """Return an LLM that answers each agent's prompt the way a correct model would."""

    async def answer(prompt: str) -> MagicMock:
        reply = MagicMock()
        if "financial data extraction specialist" in prompt:
            reply.content = json.dumps(extraction)
        elif "You are a financial modeler" in prompt:
            reply.content = model
        else:
            reply.content = "Brief: operating income came from Forge."
        return reply

    llm = MagicMock()
    llm.ainvoke = AsyncMock(side_effect=answer)
    return llm


@pytest.fixture
def repo_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Give a folder with the repository's saved inputs and no runs yet."""
    shutil.copytree(REPO / "inputs", tmp_path / "inputs")
    monkeypatch.chdir(tmp_path)
    return tmp_path


async def _run(extraction: dict[str, Any], model: str = MODEL) -> dict[str, Any]:
    llm = _scripted_llm(extraction, model)
    with (
        patch("sentinel.agents.research.get_llm", return_value=llm),
        patch("sentinel.agents.modeler.get_llm", return_value=llm),
        patch("sentinel.agents.synthesizer.get_llm", return_value=llm),
    ):
        return dict(await compile_graph().ainvoke({"ticker": "AAPL", "quick": False}))


@pytest.mark.usefixtures("repo_copy")
async def test_full_run_on_the_saved_input() -> None:
    """Every agent runs, Forge's operating income equals the filing's, and the run is written."""
    result = await _run(EXTRACTION)

    assert run_failed(result) == ""
    assert result["raw_data"]["input"]["expected_mismatches"] == []
    assert result["forge_results"]["outputs.operating_income"] == OPERATING_INCOME
    assert result["forge_results"]["filing_check"]["mismatches"] == []
    assert "error" not in result["risk_analysis"]
    assert "error" not in result["scenario_analysis"]
    assert result["historical_context"] == []

    run_dir = write_run_output(result)
    assert run_dir.parent == Path("runs/AAPL")
    assert {p.name for p in run_dir.iterdir()} >= {"brief.md", "model.yaml", "raw_data.json"}


@pytest.mark.usefixtures("repo_copy")
async def test_a_misread_figure_stops_the_run_before_forge() -> None:
    """An extraction that differs from expected.yaml fails, and no model is built."""
    result = await _run({**EXTRACTION, "net_income": 30117})

    assert run_failed(result).startswith("raw_data: Extracted figures differ")
    assert result["model_yaml"] == ""


@pytest.mark.usefixtures("repo_copy")
async def test_a_wrong_formula_stops_the_run_after_forge() -> None:
    """The evaluation's case, against the real Forge: a formula that adds operating expenses.

    Forge validates and calculates it (74,009); the filing prints 35,631, so the run fails
    and no brief is written from the wrong number.
    """
    wrong = MODEL.replace(
        "outputs.gross_profit - inputs.operating_expenses",
        "outputs.gross_profit + inputs.operating_expenses",
    )
    result = await _run(EXTRACTION, wrong)

    assert result["forge_results"]["outputs.operating_income"] == 74009  # noqa: PLR2004
    assert run_failed(result) == (
        "forge_results: Forge's results differ from the filing: "
        "outputs.operating_income: the filing prints 35631, Forge calculated 74009"
    )
    assert result["brief"].startswith("Analysis incomplete")


async def test_chat_mode_one_answer_per_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """With SENTINEL_LLM_PROVIDER=chat, each run stops at the next unanswered prompt.

    The test plays the AI in the chat: it answers each prompt Sentinel writes and
    runs again, as the prompt in the README asks.  Three runs wait (research,
    modeler, synthesizer); the fourth finishes with Forge's numbers.
    """
    shutil.copytree(REPO / "inputs", tmp_path / "inputs")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SENTINEL_LLM_PROVIDER", "chat")
    store = handoff.HandoffStore()
    monkeypatch.setattr(handoff, "_STORE", store)
    answers = {
        "research": json.dumps(EXTRACTION),
        "modeler": MODEL,
        "synthesizer": "Brief: written from Forge's results.",
    }

    roles_asked: list[str] = []
    for _ in range(5):
        store.reset()
        result = dict(await compile_graph().ainvoke({"ticker": "AAPL", "quick": False}))
        if not store.pending:
            break
        for exchange in store.pending:
            roles_asked.append(exchange.role)
            exchange.answer_path.write_text(answers[exchange.role])

    assert roles_asked == ["research", "modeler", "synthesizer"]
    assert run_failed(result) == ""
    assert result["forge_results"]["outputs.operating_income"] == OPERATING_INCOME
    run_dir = write_run_output(result)
    store.keep(run_dir)
    assert len(list((run_dir / "llm").iterdir())) == 6  # noqa: PLR2004
