"""Helpers for reading Forge MCP replies, which are JSON on success and plain text on failure."""

from __future__ import annotations

import json
from typing import Any

_MAX_ERROR_CHARS = 400


def text_from(result: Any) -> str:  # noqa: ANN401
    """Join the text blocks of an MCP tool result."""
    if isinstance(result, str):
        return result
    return " ".join(
        block["text"]
        for block in result
        if isinstance(block, dict) and block.get("type") == "text"
    )


def parse_json(text: str) -> dict[str, Any] | None:
    """Return *text* as a JSON object, or ``None`` when Forge replied with plain text."""
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def json_or_error(text: str, tool_name: str) -> dict[str, Any]:
    """Return Forge's JSON reply, or an error dict that keeps Forge's own message."""
    data = parse_json(text)
    if data is not None:
        return data
    return {"error": f"{tool_name} failed: {text.strip()[:_MAX_ERROR_CHARS]}"}
