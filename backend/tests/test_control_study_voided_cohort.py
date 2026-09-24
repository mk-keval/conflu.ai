"""Tests for Phase 0A-i control-study pure logic (manufacture detector, R25).

The control-study script replays the voided bypass cohort through the
manufacture detector (offline) and the Sec.2E exit inferencer (network).
These tests cover the offline half: replay_rr, mechanical_1r,
heuristic_pair and detect_manufacture classification, plus the cohort
statistics helper.

The detector must reproduce R25's audit finding on the archived rows:
only the R20 mechanical signature (``target_1 == entry + risk·1.0``) is
*proof*, and it appeared on exactly 4/30 rows (PAGP, LNG, CVX×2).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make backend.scripts importable (mirror of the script's own bootstrap).
SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from control_study_voided_cohort import (  # noqa: E402
    CLASS_INDETERMINATE,
    CLASS_MANUFACTURED,
    CLASS_STRUCTURAL,
    RR_TOLERANCE,
    cohort_stats,
    detect_manufacture,
    heuristic_pair,
    mechanical_1r,
    replay_rr,
    sizing_ok,
    stop_distance_pct,
)


# ── replay_rr ──────────────────────────────────────────────────────────────


def test_replay_rr_mechanical_1r_row():
    """R20 fingerprint row: t1 = entry + 1.0*risk → rr_1 exactly 1.0."""
    row = {"entry_price": "27.68", "stop_loss": "26.62",
           "target_1": "28.74", "target_2": "30.01"}
    rr1, rr2 = replay_rr(row)
    assert rr1 is not None and rr2 is not None
    assert abs(rr1 - 1.0) <= RR_TOLERANCE
    assert 2.0 < rr2 < 2.5  # t2 manufactured to ~2.2R heuristic


def test_replay_rr_degenerate_geometry_returns_none():
    """No stop / stop above entry → (None, None), never raises."""
    assert replay_rr({"entry_price": "10", "stop_loss": ""}) == (None, None)
    assert replay_rr({"entry_price": "10", "stop_loss": "15"}) == (None, None)
    assert replay_rr({"entry_price": "", "stop_loss": "5"}) == (None, None)


def test_replay_rr_missing_targets():
    """Missing target_2 yields rr_2 None without raising."""
    rr1, rr2 = replay_rr({"entry_price": "10", "stop_loss": "9",
                          "target_1": "12"})
    assert rr1 == pytest.approx(2.0)
    assert rr2 is None


# ── fingerprint helpers ────────────────────────────────────────────────────


def test_mechanical_1r_detects_r20():
    row = {"entry_price": "211.32", "stop_loss": "203.46",
           "target_1": "219.18", "target_2": "228.61"}
    assert mechanical_1r(row) is True
    # t2=~2.2R is OFF the round grid (base 1.5 +0.5 strong +0.2 vol — a
    # non-round heuristic result), so the pair is not *provable* from the
    # tuple alone; R20's 1.0R signature is the proof that fires here.
    assert heuristic_pair(row) is False


def test_mechanical_1r_false_for_structural_shape():
    """A genuinely chart-derived target (e.g. 3.99R) is NOT the fingerprint."""
    row = {"entry_price": "8.94", "stop_loss": "6.90",
           "target_1": "17.08", "target_2": "18.32"}
    assert mechanical_1r(row) is False
    assert heuristic_pair(row) is False  # 3.99 / 4.60 — not on the rr grid


def test_heuristic_pair_requires_both_targets():
    row = {"entry_price": "80", "stop_loss": "60",
           "target_1": "100", "target_2": ""}
    assert mechanical_1r(row) is True
    assert heuristic_pair(row) is False  # rr_2 missing


# ── detect_manufacture (R25 classification) ────────────────────────────────


def test_manufactured_class_requires_proof_fingerprint():
    row = {"entry_price": "27.68", "stop_loss": "26.62",
           "target_1": "28.74", "target_2": "30.01"}
    klass, ev = detect_manufacture(row)
    assert klass == CLASS_MANUFACTURED
    assert ev["mechanical_1r"] is True
    assert ev["rr_1"] == 1.0


def test_indeterminate_for_non_fingerprint_row():
    """Per R25: a 3.99R target carries no mechanical signature → indeterminate."""
    row = {"entry_price": "8.94", "stop_loss": "6.90",
           "target_1": "17.08", "target_2": "18.32"}
    klass, ev = detect_manufacture(row)
    assert klass == CLASS_INDETERMINATE
    assert ev["mechanical_1r"] is False
    assert ev["stop_distance_pct"] == pytest.approx(22.82, abs=0.01)


def test_structural_never_assignable_from_schema():
    """R25: the 12-column schema cannot prove a chart-derived target."""
    for row in (
        {"entry_price": "8.94", "stop_loss": "6.90",
         "target_1": "17.08", "target_2": "18.32"},
        {"entry_price": "27.68", "stop_loss": "26.62",
         "target_1": "28.74", "target_2": "30.01"},
    ):
        klass, _ = detect_manufacture(row)
        assert klass != CLASS_STRUCTURAL


def test_no_geometry_classified_indeterminate():
    klass, ev = detect_manufacture({"entry_price": "10", "stop_loss": ""})
    assert klass == CLASS_INDETERMINATE
    assert ev["risk"] is None


# ── cohort statistics ──────────────────────────────────────────────────────


def test_cohort_stats_distribution_and_sizing():
    rows = [
        ("a.csv", {"symbol": "A", "entry_price": "100", "stop_loss": "95",
                   "position_size_pct": "3.0"}),
        ("a.csv", {"symbol": "B", "entry_price": "100", "stop_loss": "80",
                   "position_size_pct": "10.0"}),        # 20% stop, > cap
        ("a.csv", {"symbol": "C", "entry_price": "100", "stop_loss": "",  # no stop
                   "position_size_pct": "30.0"}),
    ]
    stats = cohort_stats(rows)
    assert stats["n"] == 2
    assert stats["no_stop"] == 1
    assert stats["max"] == 20.0
    assert len(stats["over_10"]) == 1  # B only
    assert stats["over_5"][0]["symbol"] == "B"
    assert len(stats["over_25"]) == 0  # C has no stop → excluded from sizing
    assert stats["mean"] == 12.5


def test_stop_distance_pct_helper():
    assert stop_distance_pct({"entry_price": "100", "stop_loss": "90"}) == 10.0
    assert stop_distance_pct({"entry_price": "100", "stop_loss": ""}) is None
    assert stop_distance_pct({"entry_price": "10", "stop_loss": "15"}) is None


def test_sizing_ok_blueprint_cap():
    assert sizing_ok({"position_size_pct": "4.9"}) == (True, 4.9)
    assert sizing_ok({"position_size_pct": "5.0"}) == (True, 5.0)
    assert sizing_ok({"position_size_pct": "5.1"}) == (False, 5.1)
    assert sizing_ok({"position_size_pct": ""}) == (True, None)