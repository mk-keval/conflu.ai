"""Parity tests: backend bands evaluator vs shared fixture.

CONTRACT: frontend/src/content/__tests__/evaluateBands.test.ts consumes the
SAME fixture (frontend/src/content/__fixtures__/bands-cases.json). Any
divergence between TS and Python evaluators fails one of these suites.
"""

import json
from pathlib import Path

import pytest

from backend.app.infrastructure.professional.education_bands import (
    evaluate_bands,
    evaluate_condition,
)

FIXTURE_PATH = (
    Path(__file__).parent.parent.parent
    / "frontend" / "src" / "content" / "__fixtures__" / "bands-cases.json"
)


@pytest.fixture(scope="module")
def cases():
    with open(FIXTURE_PATH, encoding="utf-8") as f:
        data = json.load(f)
    assert "$comment" in data and len(data["cases"]) >= 15
    return data["cases"]


def test_fixture_path_exists():
    assert FIXTURE_PATH.exists(), f"shared fixture missing at {FIXTURE_PATH}"


@pytest.mark.parametrize(
    "condition,value,expected",
    [
        ("value > 10", "15", True),
        ("value >= 10", "10", True),
        ("value > 10", "9.99", False),
        ("value == 'bullish'", "Bullish", True),
        ("value != 'bearish'", "neutral", True),
        ("value < 0", "-1", True),
        ("garbage", "5", False),
        ("value == 'x", "x", False),  # unterminated quote
        ("", "anything", True),  # fallback band is unconditional
    ],
)
def test_evaluate_condition(condition, value, expected):
    assert evaluate_condition(condition, value) is expected


def test_shared_fixture_parity(cases):
    for c in cases:
        got = evaluate_bands(c["interpretation"], c["value"])
        assert got == c["expected"], (
            f"PARITY FAILURE on '{c['name']}': python={got!r} "
            f"expected={c['expected']!r}"
        )


def test_no_match_returns_empty(cases):
    interp = {"type": "bands", "transform": None, "bands": [{"if": "value > 1000", "text": "X"}]}
    assert evaluate_bands(interp, "5") == ""
