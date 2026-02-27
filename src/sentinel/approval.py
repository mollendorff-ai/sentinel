"""Approval helpers for the HITL gate -- show draft summary and prompt analyst."""

from __future__ import annotations

import sys
from typing import Any

_SEPARATOR = "━" * 40
_INDENT = " "


def _write_financials(raw_data: dict[str, Any]) -> None:
    """Write key financial metrics from raw_data to stdout."""
    revenue = raw_data.get("revenue")
    if revenue is not None:
        sys.stdout.write(f"{_INDENT}Revenue:          ${revenue:,.0f}M\n")

    gross_margin = raw_data.get("gross_margin")
    if gross_margin is not None:
        sys.stdout.write(f"{_INDENT}Gross Margin:     {gross_margin:.1%}\n")

    operating_margin = raw_data.get("operating_margin")
    if operating_margin is not None:
        sys.stdout.write(f"{_INDENT}Operating Margin: {operating_margin:.1%}\n")

    eps = raw_data.get("eps")
    if eps is not None:
        sys.stdout.write(f"{_INDENT}EPS:              ${eps:.2f}\n")


def _write_risk(risk_analysis: dict[str, Any]) -> None:
    """Write Monte Carlo P10/P50/P90 risk line to stdout."""
    mc = risk_analysis.get("monte_carlo", {})
    p50 = mc.get("p50") or mc.get("P50")
    p10 = mc.get("p10") or mc.get("P10")
    p90 = mc.get("p90") or mc.get("P90")
    if p50 is not None:
        p10_str = f"P10 ${p10:,.0f}M" if p10 is not None else ""
        p90_str = f"P90 ${p90:,.0f}M" if p90 is not None else ""
        range_str = " / ".join(filter(None, [p10_str, p90_str]))
        line = f"{_INDENT}Risk P50:         ${p50:,.0f}M"
        if range_str:
            line += f"  ({range_str})"
        sys.stdout.write(f"{line}\n")


def _write_scenarios(scenario_analysis: dict[str, Any]) -> None:
    """Write bear/base/bull scenario one-liner to stdout."""
    scenarios = scenario_analysis.get("scenarios", [])
    if scenarios:
        parts = []
        for s in scenarios:
            name = s.get("name", "")
            rev = s.get("revenue")
            if name and rev is not None:
                parts.append(f"{name} ${rev:,.0f}M")
        if parts:
            sys.stdout.write(f"{_INDENT}Scenario:         {' · '.join(parts)}\n")


def show_draft_summary(state: dict[str, Any]) -> None:
    """Print a condensed analysis summary to stdout for analyst review.

    Reads key financials from ``raw_data``, and optionally includes
    P10/P50/P90 from ``risk_analysis`` and a bull/base/bear one-liner
    from ``scenario_analysis``.

    Parameters
    ----------
    state
        Current pipeline state values from ``graph.get_state(config).values``.

    """
    raw_data = state.get("raw_data", {})
    ticker = state.get("ticker", raw_data.get("ticker", ""))
    period = raw_data.get("period", "")

    header = f" DRAFT ANALYSIS — {ticker}"
    if period:
        header += f"  ({period})"

    sys.stdout.write(f"\n{_SEPARATOR}\n{header}\n{_SEPARATOR}\n")

    _write_financials(raw_data)

    risk_analysis = state.get("risk_analysis", {})
    if risk_analysis and "error" not in risk_analysis:
        _write_risk(risk_analysis)

    scenario_analysis = state.get("scenario_analysis", {})
    if scenario_analysis and "error" not in scenario_analysis:
        _write_scenarios(scenario_analysis)

    sys.stdout.write(f"{_SEPARATOR}\n")


def prompt_approval() -> tuple[bool, str]:
    """Prompt the analyst to approve or reject the draft analysis.

    Prints ``Generate brief? [A]pprove / [R]eject + feedback: `` and reads
    a line from stdin.

    Returns
    -------
    tuple[bool, str]
        ``(True, "")`` if approved; ``(False, feedback_text)`` if rejected.
        Approval: empty input, "a", or "A".
        Rejection: any other input — that text becomes the feedback.

    """
    sys.stdout.write("Generate brief? [A]pprove / [R]eject + feedback: ")
    sys.stdout.flush()
    response = sys.stdin.readline().rstrip("\n")
    if response.lower() in ("", "a"):
        return True, ""
    return False, response
