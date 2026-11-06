"""Tests for reading Forge replies (JSON on success, plain text on failure)."""

from __future__ import annotations

from sentinel.tools.forge_text import json_or_error, parse_json, text_from


def test_text_from_joins_text_blocks() -> None:
    """Only text blocks are joined."""
    blocks = [{"type": "text", "text": "a"}, {"type": "image"}, {"type": "text", "text": "b"}]
    assert text_from(blocks) == "a b"


def test_text_from_accepts_plain_string() -> None:
    """A plain string passes through."""
    assert text_from("hello") == "hello"


def test_parse_json_returns_dict() -> None:
    """A JSON object parses."""
    assert parse_json('{"a": 1}') == {"a": 1}


def test_parse_json_returns_none_for_plain_text() -> None:
    """Forge's plain-text failures return None, not an exception."""
    assert parse_json("Validation failed: bad key") is None


def test_parse_json_returns_none_for_non_object() -> None:
    """A JSON list is not a Forge reply object."""
    assert parse_json("[1, 2]") is None


def test_json_or_error_keeps_forge_message() -> None:
    """The error dict carries Forge's own message, truncated."""
    result = json_or_error("Simulation failed: unknown field `inputs`", "forge_simulate")
    assert result["error"].startswith("forge_simulate failed: Simulation failed: unknown field")


def test_json_or_error_returns_json_when_valid() -> None:
    """Valid JSON is returned unchanged."""
    assert json_or_error('{"p50": 3}', "forge_simulate") == {"p50": 3}
