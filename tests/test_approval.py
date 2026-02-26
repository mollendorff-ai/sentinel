"""Tests for the HITL approval helpers."""

from __future__ import annotations

import io
from typing import Any
from unittest.mock import patch

from sentinel.approval import prompt_approval, show_draft_summary


def test_show_draft_summary_prints_header() -> None:
    """Verify header contains ticker and period."""
    state: dict[str, Any] = {
        "ticker": "AAPL",
        "raw_data": {"ticker": "AAPL", "period": "Q1 2026"},
    }
    out = io.StringIO()
    with patch("sys.stdout", out):
        show_draft_summary(state)
    output = out.getvalue()
    assert "DRAFT ANALYSIS" in output
    assert "AAPL" in output
    assert "Q1 2026" in output


def test_show_draft_summary_includes_revenue() -> None:
    """Verify revenue is printed when present."""
    state: dict[str, Any] = {
        "ticker": "AAPL",
        "raw_data": {"ticker": "AAPL", "period": "Q1 2026", "revenue": 94800},
    }
    out = io.StringIO()
    with patch("sys.stdout", out):
        show_draft_summary(state)
    assert "94,800" in out.getvalue()


def test_show_draft_summary_includes_margins() -> None:
    """Verify gross and operating margins are printed when present."""
    state: dict[str, Any] = {
        "ticker": "AAPL",
        "raw_data": {
            "ticker": "AAPL",
            "period": "Q1 2026",
            "gross_margin": 0.463,
            "operating_margin": 0.321,
        },
    }
    out = io.StringIO()
    with patch("sys.stdout", out):
        show_draft_summary(state)
    output = out.getvalue()
    assert "46.3%" in output
    assert "32.1%" in output


def test_show_draft_summary_includes_eps() -> None:
    """Verify EPS is printed when present."""
    state: dict[str, Any] = {
        "ticker": "AAPL",
        "raw_data": {"ticker": "AAPL", "period": "Q1 2026", "eps": 1.64},
    }
    out = io.StringIO()
    with patch("sys.stdout", out):
        show_draft_summary(state)
    assert "$1.64" in out.getvalue()


def test_show_draft_summary_includes_risk_p50() -> None:
    """Verify risk P50 (and P10/P90 range) is printed when monte_carlo data present."""
    state: dict[str, Any] = {
        "ticker": "AAPL",
        "raw_data": {"ticker": "AAPL", "period": "Q1 2026"},
        "risk_analysis": {
            "monte_carlo": {"p50": 94200, "p10": 88000, "p90": 101000},
        },
    }
    out = io.StringIO()
    with patch("sys.stdout", out):
        show_draft_summary(state)
    output = out.getvalue()
    assert "Risk P50" in output
    assert "94,200" in output
    assert "88,000" in output
    assert "101,000" in output


def test_show_draft_summary_skips_risk_with_error() -> None:
    """Verify risk section is absent when risk_analysis has error key."""
    state: dict[str, Any] = {
        "ticker": "AAPL",
        "raw_data": {"ticker": "AAPL", "period": "Q1 2026"},
        "risk_analysis": {"error": "validation failed"},
    }
    out = io.StringIO()
    with patch("sys.stdout", out):
        show_draft_summary(state)
    assert "Risk P50" not in out.getvalue()


def test_show_draft_summary_includes_scenarios() -> None:
    """Verify scenario one-liner is printed when scenarios data present."""
    state: dict[str, Any] = {
        "ticker": "AAPL",
        "raw_data": {"ticker": "AAPL", "period": "Q1 2026"},
        "scenario_analysis": {
            "scenarios": [
                {"name": "Bear", "revenue": 82000},
                {"name": "Base", "revenue": 94000},
                {"name": "Bull", "revenue": 108000},
            ],
        },
    }
    out = io.StringIO()
    with patch("sys.stdout", out):
        show_draft_summary(state)
    output = out.getvalue()
    assert "Scenario" in output
    assert "Bear" in output
    assert "Bull" in output


def test_show_draft_summary_skips_scenarios_with_error() -> None:
    """Verify scenario section is absent when scenario_analysis has error key."""
    state: dict[str, Any] = {
        "ticker": "AAPL",
        "raw_data": {"ticker": "AAPL", "period": "Q1 2026"},
        "scenario_analysis": {"error": "validation failed"},
    }
    out = io.StringIO()
    with patch("sys.stdout", out):
        show_draft_summary(state)
    assert "Scenario" not in out.getvalue()


def test_show_draft_summary_handles_minimal_state() -> None:
    """Verify show_draft_summary works with a minimal state (no optional fields)."""
    state: dict[str, Any] = {"ticker": "AAPL", "raw_data": {}}
    out = io.StringIO()
    with patch("sys.stdout", out):
        show_draft_summary(state)  # must not raise
    assert "AAPL" in out.getvalue()


def test_prompt_approval_empty_input_approves() -> None:
    """Verify empty Enter approves."""
    with patch("sys.stdin", io.StringIO("\n")):
        approved, feedback = prompt_approval()
    assert approved is True
    assert feedback == ""


def test_prompt_approval_a_approves() -> None:
    """Verify 'a' approves."""
    with patch("sys.stdin", io.StringIO("a\n")):
        approved, feedback = prompt_approval()
    assert approved is True
    assert feedback == ""


def test_prompt_approval_uppercase_a_approves() -> None:
    """Verify 'A' approves."""
    with patch("sys.stdin", io.StringIO("A\n")):
        approved, feedback = prompt_approval()
    assert approved is True
    assert feedback == ""


def test_prompt_approval_reject_returns_feedback() -> None:
    """Verify non-approve input rejects with feedback text."""
    with patch("sys.stdin", io.StringIO("emphasize margin compression\n")):
        approved, feedback = prompt_approval()
    assert approved is False
    assert feedback == "emphasize margin compression"


def test_prompt_approval_r_rejects() -> None:
    """Verify 'r' rejects with 'r' as feedback."""
    with patch("sys.stdin", io.StringIO("r\n")):
        approved, feedback = prompt_approval()
    assert approved is False
    assert feedback == "r"


def test_prompt_approval_prints_prompt() -> None:
    """Verify the prompt text is printed to stdout."""
    out = io.StringIO()
    with patch("sys.stdout", out), patch("sys.stdin", io.StringIO("a\n")):
        prompt_approval()
    assert "Generate brief?" in out.getvalue()
    assert "[A]pprove" in out.getvalue()
