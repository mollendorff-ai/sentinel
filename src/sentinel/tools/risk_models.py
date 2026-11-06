"""Build the risk and scenario sections of a Forge model without an LLM.

The sections are mechanical (fixed percentage ranges around the reported
figures), so they are written in code and checked by tests rather than asked
of a language model.  The shapes follow Forge 10.0.0-beta.11.
"""

from __future__ import annotations

from typing import Any

import yaml

SPREAD = 0.10
"""Relative range used for Monte Carlo spread, tornado low/high and scenarios."""

MC_ITERATIONS = 10_000
MC_SEED = 42
OUTPUT_VARIABLE = "outputs.operating_income"
SCENARIO_NAMES = ("bull", "base", "bear")

_PROBABILITIES = {"bull": 0.25, "base": 0.5, "bear": 0.25}
_SCENARIO_FACTOR = {"bull": 1 + SPREAD, "base": 1.0, "bear": 1 - SPREAD}
_SCALED_WITH_REVENUE = ("revenue", "cost_of_revenue", "net_income")


class ModelShapeError(ValueError):
    """The model has no usable ``inputs`` or ``outputs`` section."""


def _load(model_yaml: str) -> dict[str, Any]:
    try:
        model = yaml.safe_load(model_yaml)
    except yaml.YAMLError as exc:
        msg = f"model is not valid YAML: {exc}"
        raise ModelShapeError(msg) from exc
    if not isinstance(model, dict):
        msg = "model is not a YAML mapping"
        raise ModelShapeError(msg)
    return model


def numeric_inputs(model: dict[str, Any]) -> dict[str, float]:
    """Return ``{name: value}`` for inputs that hold a plain, non-zero number."""
    found: dict[str, float] = {}
    section = model.get("inputs")
    if not isinstance(section, dict):
        return found
    for name, field in section.items():
        if not isinstance(field, dict):
            continue
        value = field.get("value")
        if field.get("formula") is None and _is_number(value) and value != 0:
            found[str(name)] = float(value)
    return found


def _is_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _require(model: dict[str, Any]) -> dict[str, float]:
    inputs = numeric_inputs(model)
    outputs = model.get("outputs")
    if not inputs:
        msg = "model has no numeric inputs"
        raise ModelShapeError(msg)
    if not isinstance(outputs, dict) or "operating_income" not in outputs:
        msg = "model has no outputs.operating_income"
        raise ModelShapeError(msg)
    return inputs


def _dump(model: dict[str, Any]) -> str:
    return yaml.safe_dump(model, sort_keys=False, default_flow_style=False)


def add_tornado(model_yaml: str) -> str:
    """Return the model with a ``tornado`` section (each input at -10% / +10%)."""
    model = _load(model_yaml)
    inputs = _require(model)
    model["tornado"] = {
        "output": OUTPUT_VARIABLE,
        "inputs": [
            {
                "name": f"inputs.{name}",
                "low": round(value * (1 - SPREAD), 6),
                "high": round(value * (1 + SPREAD), 6),
            }
            for name, value in inputs.items()
        ],
    }
    return _dump(model)


def monte_carlo_variant(model_yaml: str) -> str:
    """Return a model whose numeric inputs are normal draws (std dev 10% of value).

    Forge's ``validate`` rejects ``MC.*`` formulas, so this variant is only for
    ``forge_simulate``.  Inputs are drawn independently of each other.
    """
    model = _load(model_yaml)
    inputs = _require(model)
    for name, value in inputs.items():
        model["inputs"][name] = {
            "value": None,
            "formula": f"=MC.Normal({value}, {round(abs(value) * SPREAD, 6)})",
        }
    model["monte_carlo"] = {
        "iterations": MC_ITERATIONS,
        "sampling": "latin_hypercube",
        "seed": MC_SEED,
        "outputs": [{"variable": OUTPUT_VARIABLE, "percentiles": [10, 50, 90]}],
    }
    return _dump(model)


def add_scenarios(model_yaml: str) -> str:
    """Return the model with bull / base / bear scenarios.

    Revenue moves by +/-10%.  Cost of revenue and net income move with it
    (margins held), operating expenses stay fixed, so operating margin changes
    through operating leverage.
    """
    model = _load(model_yaml)
    inputs = _require(model)
    model["scenarios"] = {
        name: {
            "probability": _PROBABILITIES[name],
            "description": name.capitalize(),
            "scalars": {
                key: round(value * _SCENARIO_FACTOR[name], 6)
                if key in _SCALED_WITH_REVENUE
                else value
                for key, value in inputs.items()
            },
        }
        for name in SCENARIO_NAMES
    }
    return _dump(model)
