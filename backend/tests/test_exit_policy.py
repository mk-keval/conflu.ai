"""Bundle A exit policy (D-77) — target selection + multi-leg simulation.

Pure unit tests. No network, no DB. These lock the frozen v0.2 geometry:
nearest-first structural targets, family bands, tranches, breakeven, trail,
time stop, gap/ambiguity conventions and weighted accounting.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from backend.app.domain.workflow import exit_policy as ep
from backend.app.domain.workflow import pnl


def _bar(date: str, o: float, h: float, lo: float, c: float) -> dict[str, Any]:
    return {"date": date, "open": o, "high": h, "low": lo, "close": c}


ENTRY_BAR = _bar("2026-01-02", 100, 101, 99, 100)


# ── Family mapping ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("screen", "family"),
    [
        ("Trend Follower", "trend"),
        ("Trend Follower v2", "trend"),
        ("trend-follower-v2", "trend"),
        ("Institutional Accumulation", "trend"),
        ("Quality Trend + Fundamentals", "trend"),
        ("52-Week Breakout", "breakout"),
        ("VCP Breakout", "breakout"),
        ("Low-Vol Setup", "breakout"),
        ("Statistical Mean Reversion", "mean_reversion"),
        ("Sector Rotation: XLK", "rotation"),
        ("Sector Rotation Holdings", "rotation"),
        ("Distribution", "unknown"),
        ("", "unknown"),
        (None, "unknown"),
    ],
)
def test_family_for_screen(screen: str | None, family: str) -> None:
    assert ep.family_for_screen(screen) == family


def test_normalize_family_rejects_unknown() -> None:
    assert ep.normalize_family("Mean-Reversion") == "mean_reversion"
    assert ep.normalize_family("nonsense") is None
    assert ep.policy_for("nonsense").family == "unknown"


# ── Candidate collection ────────────────────────────────────────────────


def test_collect_candidates_above_price_within_cap_and_deduped() -> None:
    levels = ep.collect_candidates(
        price=100,
        key_resistance=[90, 105, 105, 160],
        swing_highs=[110],
        swing_lows=[80],
    )
    # 90 is below price; 160 is beyond 1.5x; 105 deduped; measured move
    # 100 + (110 - 80) = 130 is also inside the cap.
    assert levels == [105.0, 110.0, 130.0]


def test_collect_candidates_has_no_percentage_fallback() -> None:
    assert ep.collect_candidates(price=100) == []


# ── Target selection ────────────────────────────────────────────────────


def test_select_targets_nearest_first_inside_band() -> None:
    # entry 95, stop 90 -> 1R = 5. Levels at 2R, 3R, 5R.
    selection = ep.select_targets(
        entry_low=95, stop_loss=90, family="trend",
        candidates=[105, 110, 120],
    )
    assert selection.ok
    assert selection.targets == (105.0, 110.0, 120.0)
    assert selection.t1_r == 2.0
    assert selection.stretch_r == 5.0


def test_select_targets_skips_sub_floor_levels() -> None:
    # 100 is only 1R; 110 is 3R; 115 is 4R.
    selection = ep.select_targets(
        entry_low=95, stop_loss=90, family="trend",
        candidates=[100, 110, 115],
    )
    assert selection.targets == (110.0, 115.0)
    assert selection.t1_r == 3.0


def test_select_targets_half_size_floor_is_reachable() -> None:
    # 2.2R is inside the CONDITIONAL tier (2.0-2.5R), so it must be selectable.
    selection = ep.select_targets(
        entry_low=95, stop_loss=90, family="trend",
        candidates=[106],
    )
    assert selection.ok
    assert selection.t1_r == 2.2


def test_select_targets_too_close() -> None:
    selection = ep.select_targets(
        entry_low=95, stop_loss=90, family="trend",
        candidates=[100, 101],
    )
    assert not selection.ok
    assert selection.rejection == ep.REJECT_TOO_CLOSE
    assert "floor" in selection.detail


def test_select_targets_too_far() -> None:
    selection = ep.select_targets(
        entry_low=95, stop_loss=90, family="trend",
        candidates=[125],
    )
    assert not selection.ok
    assert selection.rejection == ep.REJECT_TOO_FAR


def test_select_targets_too_far_wins_over_too_close_when_both_exist() -> None:
    # 100 is 1R (below floor) and 125 is 6R (above cap). There is no band
    # candidate; the frozen rule reports the cap violation, not "too close".
    selection = ep.select_targets(
        entry_low=95, stop_loss=90, family="trend",
        candidates=[100, 125],
    )
    assert selection.rejection == ep.REJECT_TOO_FAR


def test_select_targets_no_objective() -> None:
    selection = ep.select_targets(
        entry_low=95, stop_loss=90, family="trend", candidates=[],
    )
    assert selection.rejection == ep.REJECT_NO_OBJECTIVE


def test_select_targets_family_max_differs() -> None:
    # 4.5R is inside breakout's 5R cap but outside trend's 4R cap.
    breakout = ep.select_targets(
        entry_low=95, stop_loss=90, family="breakout", candidates=[117.5],
    )
    trend = ep.select_targets(
        entry_low=95, stop_loss=90, family="trend", candidates=[117.5],
    )
    assert breakout.ok and breakout.t1_r == 4.5
    assert trend.rejection == ep.REJECT_TOO_FAR


def test_select_targets_invalid_geometry() -> None:
    selection = ep.select_targets(
        entry_low=90, stop_loss=95, family="trend", candidates=[100],
    )
    assert selection.rejection == ep.REJECT_INVALID_GEOMETRY


# ── Simulation ──────────────────────────────────────────────────────────


def _trend_bars() -> list[dict[str, Any]]:
    return [
        ENTRY_BAR,
        _bar("2026-01-05", 101, 110, 100, 109),
        _bar("2026-01-06", 109, 115, 108, 114),
        _bar("2026-01-07", 114, 116, 111, 113),
        _bar("2026-01-08", 113, 114, 110, 111),
    ]


def test_trend_t1_t2_runner_trail_and_weighted_accounting() -> None:
    sim = ep.simulate_exit(
        _trend_bars(), entry=100, stop=95, targets=[110, 115, 120],
        family="trend", shares=100, atr=1.0, entry_date="2026-01-02",
    )
    assert sim.exit_reason == ep.EXIT_SCALE_OUT
    assert [leg.reason for leg in sim.legs] == [
        "target_1", "target_2", ep.EXIT_TRAIL,
    ]
    assert [round(leg.price, 2) for leg in sim.legs] == [110.0, 115.0, 112.0]
    assert sum(leg.size_pct for leg in sim.legs) == pytest.approx(100.0)
    assert sim.plan_adherence == 0.5

    columns = sim.as_exit_columns(entry=100, stop=95, shares=100)
    vwap = (110 + 115 + 112) / 3
    assert columns["exit_price"] == round(vwap, 2)
    assert columns["realized_r"] == round((vwap - 100) / 5, 2)
    assert columns["exit_reason"] == ep.EXIT_SCALE_OUT
    assert columns["plan_adherence"] == 0.5

    legs = json.loads(columns["exit_legs"])
    weighted_price = sum(leg["price"] * leg["size_pct"] for leg in legs) / 100
    weighted_r = sum(leg["r"] * leg["size_pct"] for leg in legs) / 100
    assert weighted_price == pytest.approx(vwap, abs=1e-3)
    assert weighted_r == pytest.approx((vwap - 100) / 5, abs=1e-3)

    money = pnl.dollar_pnl(100, vwap, 100)
    assert columns["pnl_usd"] == money["pnl_usd"]
    leg_sum = sum(
        pnl.dollar_pnl(100, leg["price"], 100 * leg["size_pct"] / 100)["pnl_usd"]
        for leg in legs
    )
    assert leg_sum == pytest.approx(columns["pnl_usd"], abs=0.02)


def test_trend_missing_t2_joins_runner() -> None:
    bars = [
        ENTRY_BAR,
        _bar("2026-01-05", 101, 110, 100, 109),
        _bar("2026-01-06", 109, 118, 108, 117),
    ]
    sim = ep.simulate_exit(
        bars, entry=100, stop=95, targets=[110], family="trend",
        shares=100, atr=1.0, entry_date="2026-01-02",
    )
    # T1 is 1/3; the missing T2 third joins the runner, so 2/3 remains open.
    assert [leg.reason for leg in sim.legs] == ["target_1"]
    assert sim.exit_price is None
    assert sim.remaining_fraction == pytest.approx(2 / 3)


def test_breakout_half_at_t1_then_trail() -> None:
    bars = [
        ENTRY_BAR,
        _bar("2026-01-05", 101, 110, 100, 109),
        _bar("2026-01-06", 109, 113, 108, 112),
        _bar("2026-01-07", 112, 113, 108, 109),
    ]
    sim = ep.simulate_exit(
        bars, entry=100, stop=95, targets=[110, 115], family="breakout",
        shares=100, atr=1.0, entry_date="2026-01-02",
    )
    assert [leg.reason for leg in sim.legs] == ["target_1", ep.EXIT_TRAIL]
    assert [round(leg.price, 2) for leg in sim.legs] == [110.0, 109.5]
    assert sum(leg.size_pct for leg in sim.legs) == pytest.approx(100.0)
    assert sim.plan_adherence == 0.5


def test_mean_reversion_full_exit_at_t1() -> None:
    bars = [
        ENTRY_BAR,
        _bar("2026-01-05", 101, 104, 100, 103),
    ]
    sim = ep.simulate_exit(
        bars, entry=100, stop=95, targets=[104, 110], family="mean_reversion",
        shares=100, entry_date="2026-01-02",
    )
    assert len(sim.legs) == 1
    assert sim.legs[0].price == 104
    assert sim.legs[0].size_pct == 100
    assert sim.exit_reason == "target_1"
    assert sim.plan_adherence == 1.0


def test_breakeven_arms_at_close_and_is_live_next_bar() -> None:
    bars = [
        ENTRY_BAR,
        _bar("2026-01-05", 101, 106, 100, 105),  # high >= +1R -> BE at close
        _bar("2026-01-06", 104, 105, 98, 99),    # next bar trades through entry
    ]
    sim = ep.simulate_exit(
        bars, entry=100, stop=95, targets=[120], family="unknown",
        shares=100, entry_date="2026-01-02",
    )
    assert sim.exit_reason == "stop"
    assert sim.exit_price == 100
    assert sim.plan_adherence == 0.0


def test_gap_through_stop_fills_at_open() -> None:
    bars = [
        ENTRY_BAR,
        _bar("2026-01-05", 92, 93, 91, 92),
    ]
    sim = ep.simulate_exit(
        bars, entry=100, stop=95, targets=[110], family="trend",
        shares=100, entry_date="2026-01-02",
    )
    assert sim.exit_reason == "stop"
    assert sim.exit_price == 92
    assert sim.plan_adherence == 0.0


def test_stop_wins_same_bar_tie_and_flags_ambiguity() -> None:
    bars = [
        ENTRY_BAR,
        _bar("2026-01-05", 100, 111, 94, 100),
    ]
    sim = ep.simulate_exit(
        bars, entry=100, stop=95, targets=[110], family="trend",
        shares=100, entry_date="2026-01-02",
    )
    assert sim.ambiguous is True
    assert sim.exit_reason == "stop"
    assert sim.exit_price == 95
    # MAE records the bar's low (v0.1 convention), not the stop fill.
    assert sim.mae_r == pytest.approx(-1.2)


def test_entry_bar_is_excluded() -> None:
    bars = [
        _bar("2026-01-02", 100, 130, 99, 100),
        _bar("2026-01-05", 100, 101, 99, 100),
    ]
    sim = ep.simulate_exit(
        bars, entry=100, stop=95, targets=[110], family="trend",
        shares=100, entry_date="2026-01-02",
    )
    assert sim.legs == []
    assert sim.exit_price is None


def test_time_stop_exits_remainder_at_close() -> None:
    bars = [
        ENTRY_BAR,
        _bar("2026-01-13", 101, 103, 100, 102),  # first session >= 10d cutoff
    ]
    sim = ep.simulate_exit(
        bars, entry=100, stop=95, targets=[120], family="mean_reversion",
        shares=100, entry_date="2026-01-02",
    )
    assert sim.exit_reason == "time_stop"
    assert sim.exit_date == "2026-01-13"
    assert sim.exit_price == 102
    assert sim.plan_adherence == 0.5


def test_atr_missing_uses_two_risk_trail() -> None:
    bars = [
        ENTRY_BAR,
        _bar("2026-01-05", 101, 110, 100, 109),  # T1 fills; close 109
        _bar("2026-01-06", 109, 118, 108, 117),  # close 117
        _bar("2026-01-07", 117, 118, 99, 100),   # low through both stops
    ]
    with_atr = ep.simulate_exit(
        bars, entry=100, stop=95, targets=[110], family="trend",
        shares=100, atr=1.0, entry_date="2026-01-02",
    )
    without_atr = ep.simulate_exit(
        bars, entry=100, stop=95, targets=[110], family="trend",
        shares=100, atr=None, entry_date="2026-01-02",
    )
    # 2x1 ATR trail is 115; the 2xrisk fallback is 107 (max with entry 100).
    assert with_atr.legs[-1].reason == ep.EXIT_TRAIL
    assert with_atr.legs[-1].price == 115
    assert without_atr.legs[-1].reason == ep.EXIT_TRAIL
    assert without_atr.legs[-1].price == 107


def test_no_exit_returns_empty_columns() -> None:
    bars = [ENTRY_BAR, _bar("2026-01-05", 100, 101, 99, 100)]
    sim = ep.simulate_exit(
        bars, entry=100, stop=95, targets=[130], family="trend",
        shares=100, entry_date="2026-01-02",
    )
    assert sim.exit_price is None
    assert sim.as_exit_columns(entry=100, stop=95, shares=100) == {}


def test_invalid_geometry_returns_empty_simulation() -> None:
    sim = ep.simulate_exit(
        [ENTRY_BAR], entry=90, stop=95, targets=[100], family="trend",
    )
    assert sim.exit_price is None
    assert sim.legs == []
