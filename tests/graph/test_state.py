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
