"""Tests for Ref CLI wrapper."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from sentinel.tools.ref_fetch import RefFetchTool


@pytest.fixture
def ref_tool() -> RefFetchTool:
    """Create a RefFetchTool instance for testing."""
    return RefFetchTool()


# ---------------------------------------------------------------------------
# Unit tests (no external binaries)
# ---------------------------------------------------------------------------


async def test_ref_fetch_happy_path_mocked(ref_tool: RefFetchTool) -> None:
    """Verify successful fetch with mocked subprocess returning valid JSON."""
    payload = {"url": "https://example.com", "status": "ok", "title": "Example", "sections": []}
    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate.return_value = (json.dumps(payload).encode(), b"")

    with patch("sentinel.tools.ref_fetch.asyncio.create_subprocess_exec", return_value=mock_proc):
        result = await ref_tool._arun("https://example.com")  # noqa: SLF001

    assert result["status"] == "ok"
    assert result["title"] == "Example"


def test_ref_fetch_sync_run_mocked(ref_tool: RefFetchTool) -> None:
    """Verify synchronous _run delegates to _arun (mocked)."""
    payload = {"url": "https://example.com", "status": "ok", "title": "Test", "sections": []}

    with patch.object(ref_tool, "_arun", return_value=payload):
        result = ref_tool._run("https://example.com")  # noqa: SLF001

    assert result["status"] == "ok"


async def test_ref_fetch_nonzero_exit_code(ref_tool: RefFetchTool) -> None:
    """Verify non-zero exit code returns error with stderr message."""
    mock_proc = AsyncMock()
    mock_proc.returncode = 1
    mock_proc.communicate.return_value = (b"", b"connection refused")

    with patch("sentinel.tools.ref_fetch.asyncio.create_subprocess_exec", return_value=mock_proc):
        result = await ref_tool._arun("https://fail.example")  # noqa: SLF001

    assert result["status"] == "error"
    assert "connection refused" in result["error"]


async def test_ref_fetch_binary_not_found(ref_tool: RefFetchTool) -> None:
    """Verify FileNotFoundError when ref CLI is not installed."""
    with patch(
        "sentinel.tools.ref_fetch.asyncio.create_subprocess_exec",
        side_effect=FileNotFoundError,
    ):
        result = await ref_tool._arun("https://example.com")  # noqa: SLF001

    assert result["status"] == "error"
    assert "not found" in result["error"]


async def test_ref_fetch_timeout(ref_tool: RefFetchTool) -> None:
    """Verify TimeoutError returns timeout message."""
    with patch(
        "sentinel.tools.ref_fetch.asyncio.create_subprocess_exec",
        side_effect=TimeoutError,
    ):
        result = await ref_tool._arun("https://slow.example")  # noqa: SLF001

    assert result["status"] == "error"
    assert "Timeout" in result["error"]


async def test_ref_fetch_invalid_json(ref_tool: RefFetchTool) -> None:
    """Verify malformed JSON from ref returns error."""
    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate.return_value = (b"not json", b"")

    with patch("sentinel.tools.ref_fetch.asyncio.create_subprocess_exec", return_value=mock_proc):
        result = await ref_tool._arun("https://example.com")  # noqa: SLF001

    assert result["status"] == "error"
    assert "Invalid JSON" in result["error"]


# ---------------------------------------------------------------------------
# Integration tests (require real `ref` binary)
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_ref_fetch_returns_structured_json(ref_tool: RefFetchTool) -> None:
    """Fetch a known static page and verify JSON structure."""
    result = await ref_tool.ainvoke("https://example.com")

    assert result["status"] == "ok"
    assert result["url"] == "https://example.com"
    assert "title" in result
    assert "sections" in result


@pytest.mark.integration
async def test_ref_fetch_invalid_url(ref_tool: RefFetchTool) -> None:
    """Verify invalid URL returns non-ok status."""
    result = await ref_tool.ainvoke("not-a-url")

    assert result["status"] != "ok"


@pytest.mark.integration
def test_ref_fetch_sync_run(ref_tool: RefFetchTool) -> None:
    """Verify synchronous _run delegates to _arun."""
    result = ref_tool._run("https://example.com")  # noqa: SLF001

    assert result["status"] == "ok"
    assert result["url"] == "https://example.com"
