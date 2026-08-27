"""Bands DSL evaluator — backend half of the parity contract with
``frontend/src/content/evaluateBands.ts``.

Grammar (must stay identical on both sides)::

    condition := "value" <op> <rhs>
    op        := ">=" | "<=" | "==" | "!=" | ">" | "<"
    rhs       := single-quoted string | number
    band      := {"if": condition, "text": str}   # evaluated in order

``${value}`` inside band text is replaced by the transformed value.
An empty/whitespace condition is an unconditional FALLBACK band (last).

Canonical rendering rules (locked by shared fixture bands-cases.json):
- ``plain`` transform or no transform: floats with >2 decimals render as
  exactly 2 decimals (mirrors narration._fmt); strings/short decimals
  pass through verbatim.
- ``percent`` appends ``%``; ``ratio`` renders 2-decimal + ``x``;
  ``compactNumber`` abbreviates K/M/B (1 decimal); ``money`` renders
  ``$`` + thousands separators + 2 decimals.
"""

from __future__ import annotations

import math
import re
from typing import Any

_CONDITION_RE = re.compile(
    r"^\s*value\s*(>=|<=|==|!=|>|<)\s*(?:'([^']*)'|(-?\d+(?:\.\d+)?))\s*$"
)
_EPSILON = 1e-9


def apply_transform(raw: str, transform: str | None) -> str:
    """Render a raw value string per the band transform. Mirrors TS exactly."""
    num = 0.0
    finite = False
    try:
        num = float(raw)
        finite = math.isfinite(num)
    except (TypeError, ValueError):
        pass

    if transform == "percent":
        return f"{raw}%"
    if transform == "ratio":
        return f"{num:.2f}x" if finite else f"{raw}x"
    if transform == "money":
        if not finite:
            return f"${raw}"
        return f"${num:,.2f}"
    if transform == "compactNumber":
        if not finite:
            return raw
        absn = abs(num)
        if absn >= 1e9:
            return f"{num / 1e9:.1f}B"
        if absn >= 1e6:
            return f"{num / 1e6:.1f}M"
        if absn >= 1e3:
            return f"{num / 1e3:.1f}K"
        return str(num)

    # plain / None — default rendering
    if not finite:
        return raw
    if "." in raw and len(raw.split(".")[1]) > 2:
        return f"{num:.2f}"
    return raw


def evaluate_condition(condition: str, value: str) -> bool:
    """Evaluate one condition against a value. Mirrors TS implementation.

    Empty/whitespace condition = unconditional (fallback band, must be last).
    """
    if not condition or not condition.strip():
        return True

    match = _CONDITION_RE.match(condition)
    if not match:
        return False

    op = match.group(1)
    str_rhs = match.group(2)
    num_rhs = match.group(3)

    if str_rhs is not None:
        lhs = value.strip().lower()
        rhs = str_rhs.strip().lower()
        if op == "==":
            return lhs == rhs
        if op == "!=":
            return lhs != rhs
        return False

    try:
        num = float(value)
    except (TypeError, ValueError):
        return False
    rhs_num = float(num_rhs)

    if op == ">":
        return num > rhs_num
    if op == "<":
        return num < rhs_num
    if op == ">=":
        return num >= rhs_num
    if op == "<=":
        return num <= rhs_num
    if op == "==":
        return abs(num - rhs_num) < _EPSILON
    if op == "!=":
        return abs(num - rhs_num) >= _EPSILON
    return False


def evaluate_bands(interp: dict[str, Any], value: str) -> str:
    """Render the first matching band's text. Mirrors TS evaluateBands."""
    for band in interp.get("bands") or []:
        if evaluate_condition(band.get("if", ""), value):
            rendered = apply_transform(value, interp.get("transform"))
            return band["text"].replace("${value}", rendered)
    return ""
