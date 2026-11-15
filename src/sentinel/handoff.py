"""The chat hand-off: the AI in a chat answers Sentinel's LLM prompts (ADR-013).

With ``SENTINEL_LLM_PROVIDER=chat`` no API is called.  Each LLM call writes its
prompt to ``.sentinel/chat/<role>-<hash>.prompt.md`` and, until the file beside it,
``<role>-<hash>.answer.md``, holds an answer, the run stops and says which file to
write.  The AI in the chat reads the prompt, writes the answer and runs Sentinel
again; answers already written are reused, so each run gets one step further.

A prompt is named by a hash of its text, so an answer is reused only for exactly
the prompt it answered: when Forge's results change, the brief is asked for again.
"""

from __future__ import annotations

import hashlib
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

CHAT_PROVIDER = "chat"
DEFAULT_CHAT_DIR = Path(".sentinel/chat")


class AnswerNeededError(RuntimeError):
    """A prompt has no answer yet; the agent that asked treats it as a failed call."""


@dataclass(frozen=True)
class Exchange:
    """One prompt and the file its answer goes in."""

    role: str
    prompt_path: Path
    answer_path: Path


@dataclass
class HandoffStore:
    """The prompts and answers of the current run, kept as files in *folder*."""

    folder: Path = DEFAULT_CHAT_DIR
    pending: list[Exchange] = field(default_factory=list)
    used: list[Exchange] = field(default_factory=list)

    def answer(self, role: str, prompt: str) -> str:
        """Return the written answer to *prompt*, or record it as pending and raise."""
        key = f"{role}-{hashlib.sha256(prompt.encode()).hexdigest()[:12]}"
        exchange = Exchange(
            role=role,
            prompt_path=self.folder / f"{key}.prompt.md",
            answer_path=self.folder / f"{key}.answer.md",
        )
        self.folder.mkdir(parents=True, exist_ok=True)
        exchange.prompt_path.write_text(prompt, encoding="utf-8")
        answer = (
            exchange.answer_path.read_text(encoding="utf-8").strip()
            if exchange.answer_path.is_file()
            else ""
        )
        if answer:
            if exchange not in self.used:
                self.used.append(exchange)
            return answer
        if exchange not in self.pending:
            self.pending.append(exchange)
        msg = f"No answer yet: write {exchange.answer_path}"
        raise AnswerNeededError(msg)

    def reset(self) -> None:
        """Forget the exchanges of the previous run (the files stay)."""
        self.pending.clear()
        self.used.clear()

    def keep(self, run_dir: Path) -> None:
        """Copy this run's prompts and answers into ``run_dir/llm/``, the record of the LLM."""
        if not self.used:
            return
        target = run_dir / "llm"
        target.mkdir(parents=True, exist_ok=True)
        for exchange in self.used:
            shutil.copyfile(exchange.prompt_path, target / exchange.prompt_path.name)
            shutil.copyfile(exchange.answer_path, target / exchange.answer_path.name)


_STORE = HandoffStore()


def store() -> HandoffStore:
    """Return the hand-off store of this process."""
    return _STORE


class HandoffLLM:
    """A stand-in for a chat model: ``ainvoke`` returns the answer written for the prompt."""

    def __init__(self, role: str) -> None:
        """Answer prompts for the agent named *role*."""
        self.role = role

    async def ainvoke(self, prompt: object) -> SimpleNamespace:
        """Return ``.content`` = the answer written for *prompt*; raise if there is none yet."""
        return SimpleNamespace(content=store().answer(self.role, str(prompt)))


class QuietWhileWaiting(logging.Filter):
    """Drop Sentinel's warnings and errors while a prompt waits for the chat's answer.

    A prompt with no answer yet is the normal state of a chat-mode run: the agent
    that asked stops, and the agents after it skip on its error.  Their warnings,
    and the traceback of :class:`AnswerNeededError`, would read as a failure, so
    while anything is pending only the WAITING block says what happened.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Return False for a Sentinel warning or error logged while a prompt is pending."""
        if record.exc_info and isinstance(record.exc_info[1], AnswerNeededError):
            return False
        return not (
            store().pending
            and record.levelno >= logging.WARNING
            and record.name.startswith("sentinel")
        )
