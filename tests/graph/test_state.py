"""Tests for the pipeline state schema."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sentinel.graph.state import SentinelState


def test_state_accepts_partial_updates() -> None:
    """Verify SentinelState allows partial dict creation (total=False)."""
    partial: SentinelState = {"ticker": "AAPL"}
    assert partial["ticker"] == "AAPL"


def test_state_accepts_full_population() -> None:
    """Verify SentinelState accepts all fields populated."""
    full: SentinelState = {
        "ticker": "MSFT",
        "raw_data": {"revenue": 100},
        "model_yaml": "_forge_version: 5.0.0",
        "forge_results": {"outputs.margin": 0.5},
        "brief": "Executive brief.",
    }
    assert full["ticker"] == "MSFT"
    assert full["brief"] == "Executive brief."


def test_state_accepts_v030_fields() -> None:
    """Verify SentinelState accepts v0.3.0 fields (quick, risk, scenario)."""
    full: SentinelState = {
        "ticker": "NVDA",
        "raw_data": {"revenue": 26000},
        "model_yaml": "_forge_version: 5.0.0",
        "forge_results": {"outputs.margin": 0.65},
        "brief": "Strong quarter.",
        "quick": False,
        "risk_analysis": {
            "monte_carlo": {"mean": 38000},
            "tornado": {"top_driver": "revenue"},
            "break_even": {"threshold": 20000},
        },
        "scenario_analysis": {
            "bull": {"revenue_growth": 0.15},
            "base": {"revenue_growth": 0.08},
            "bear": {"revenue_growth": -0.05},
        },
    }
    assert full["ticker"] == "NVDA"
    assert full["quick"] is False
    assert "monte_carlo" in full["risk_analysis"]
    assert "bull" in full["scenario_analysis"]
