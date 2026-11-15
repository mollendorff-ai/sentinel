"""Tests for the chat hand-off (ADR-013)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from sentinel import handoff
from sentinel.handoff import AnswerNeededError, HandoffLLM, HandoffStore

if TYPE_CHECKING:
    from pathlib import Path


def test_a_prompt_without_answer_is_written_and_pending(tmp_path: Path) -> None:
    """The prompt goes to a file, the call raises, and the exchange is pending once."""
    store = HandoffStore(folder=tmp_path / "chat")
    for _ in range(2):
        with pytest.raises(AnswerNeededError, match=r"write .*research-[0-9a-f]{12}\.answer\.md"):
            store.answer("research", "Read this filing.")

    (exchange,) = store.pending
    assert exchange.role == "research"
    assert exchange.prompt_path.read_text() == "Read this filing."
    assert not exchange.answer_path.exists()
    assert store.used == []


def test_an_answer_is_returned_and_recorded(tmp_path: Path) -> None:
    """A written answer is returned, stripped, and recorded as used once."""
    store = HandoffStore(folder=tmp_path)
    with pytest.raises(AnswerNeededError):
        store.answer("modeler", "Write the model.")
    store.pending[0].answer_path.write_text("  model: yaml\n\n")
    store.reset()

    assert store.answer("modeler", "Write the model.") == "model: yaml"
    assert store.answer("modeler", "Write the model.") == "model: yaml"
    assert len(store.used) == 1
    assert store.pending == []


def test_an_empty_answer_file_is_not_an_answer(tmp_path: Path) -> None:
    """An answer file with only whitespace still waits."""
    store = HandoffStore(folder=tmp_path)
    with pytest.raises(AnswerNeededError):
        store.answer("synthesizer", "Write the brief.")
    store.pending[0].answer_path.write_text("\n")
    with pytest.raises(AnswerNeededError):
        store.answer("synthesizer", "Write the brief.")


def test_a_changed_prompt_needs_a_new_answer(tmp_path: Path) -> None:
    """An answer is reused only for exactly the prompt it answered."""
    store = HandoffStore(folder=tmp_path)
    with pytest.raises(AnswerNeededError):
        store.answer("synthesizer", "Forge says 1.")
    store.pending[0].answer_path.write_text("Brief for 1.")
    with pytest.raises(AnswerNeededError):
        store.answer("synthesizer", "Forge says 2.")
    assert store.pending[1].prompt_path != store.pending[0].prompt_path


def test_keep_copies_the_transcript(tmp_path: Path) -> None:
    """keep() copies used prompts and answers into run_dir/llm/; nothing used, no folder."""
    store = HandoffStore(folder=tmp_path / "chat")
    run_dir = tmp_path / "run"
    store.keep(run_dir)
    assert not (run_dir / "llm").exists()

    with pytest.raises(AnswerNeededError):
        store.answer("research", "P")
    store.pending[0].answer_path.write_text("A")
    store.answer("research", "P")
    store.keep(run_dir)

    names = sorted(p.name for p in (run_dir / "llm").iterdir())
    assert len(names) == 2  # noqa: PLR2004
    assert names[0].endswith(".answer.md")
    assert names[1].endswith(".prompt.md")


async def test_handoff_llm_uses_the_process_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HandoffLLM answers through store(), with .content like a chat model's reply."""
    monkeypatch.setattr(handoff, "_STORE", HandoffStore(folder=tmp_path))
    llm = HandoffLLM("research")
    with pytest.raises(AnswerNeededError):
        await llm.ainvoke("P")
    handoff.store().pending[0].answer_path.write_text('{"revenue": 1}')
    assert (await llm.ainvoke("P")).content == '{"revenue": 1}'
