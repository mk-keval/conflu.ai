"""H-09 replay rules (D-78) — pure unit + production-parity tests.

Network and database are never touched. The parity tests are the guard rail:
if ``synthesis``, ``gate``, ``exits`` or ``exit_policy`` change, these fail
instead of silently moving the v0.1/v0.2 comparison.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backend.app.domain.ticker_analysis import synthesis
from backend.app.domain.ticker_analysis.models import TechnicalAnalysis
from backend.app.domain.workflow import exits as exits_mod
from backend.app.domain.workflow import pending as pending_mod
from backend.app.infrastructure.backtest import replay_rules as rules


# ── Helpers ─────────────────────────────────────────────────────────────────


def _frame(closes: list[float], end: str = "2026-10-16") -> pd.DataFrame:
    idx = pd.bdate_range(end=end, periods=len(closes))
    close = pd.Series(closes, index=idx, dtype=float)
    prev = close.shift(1).fillna(close.iloc[0])
    return pd.DataFrame(
        {
            "Open": prev,
            "High": np.maximum(prev, close) + 0.7,
            "Low": np.minimum(prev, close) - 0.7,
            "Close": close,
            "Volume": 1_000_000.0,
        },
        index=idx,
    )


def _bar(day: str, o: float, h: float, low: float, c: float) -> dict:
    return {"date": day, "open": o, "high": h, "low": low, "close": c}


def _geometry() -> rules.PlanGeometry:
    geometry = rules.build_geometry(100.0, 2.0)
    assert geometry is not None
    return geometry


def _fill(day: str = "2026-10-02", price: float = 98.5) -> pending_mod.FillDecision:
    return pending_mod.FillDecision(
        pending_mod.FILLED,
        fill_date=day,
        fill_price=price,
        reason="limit touched",
        bar=_bar(day, 100.0, 101.0, 98.4, 100.0),
    )


# ── Geometry ────────────────────────────────────────────────────────────────


def test_build_geometry_uses_the_15pct_floor() -> None:
    geometry = _geometry()
    # 0.5 × 2 / 100 = 1% < 1.5% floor.
    assert geometry.width_pct == pytest.approx(0.015)
    assert geometry.entry_low == 98.5
    assert geometry.entry_high == 100.75
    assert geometry.stop_loss == 96.0
    assert geometry.risk_per_share == pytest.approx(2.5)


def test_build_geometry_uses_half_atr_when_wider() -> None:
    geometry = rules.build_geometry(100.0, 5.0)
    assert geometry is not None
    assert geometry.width_pct == pytest.approx(0.025)
    assert geometry.entry_low == 97.5
    assert geometry.entry_high == 101.25
    assert geometry.stop_loss == 90.0


@pytest.mark.parametrize(
    ("close", "atr"),
    [(0.0, 2.0), (100.0, 0.0), (100.0, None), (None, 2.0), (100.0, -1.0)],
)
def test_build_geometry_rejects_bad_inputs(close, atr) -> None:
    assert rules.build_geometry(close, atr) is None


def test_build_geometry_rejects_stop_above_limit() -> None:
    # A sub-1% ATR makes the 2×ATR stop sit above the 1.5%-wide limit.
    assert rules.build_geometry(100.0, 0.5) is None


def test_atr_at_uses_only_bars_through_the_signal() -> None:
    frame = _frame([100.0] * 40)
    value = rules.atr_at(frame, frame.index[-1].date().isoformat())
    assert value == pytest.approx(1.4, abs=0.05)

    # Truncating at an earlier date cannot see later bars.
    early = frame.index[25].date().isoformat()
    assert rules.atr_at(frame, early) == pytest.approx(
        rules.atr_at(frame.loc[:early], early)
    )


# ── Structural levels / v0.1 targets ────────────────────────────────────────


def test_structural_levels_have_no_look_ahead() -> None:
    frame = _frame([100 + (i % 7) for i in range(80)])
    cutoff = frame.index[60]
    levels = rules.structural_levels(
        frame.loc[:cutoff], close=float(frame.loc[cutoff, "Close"]), atr=2.0
    )
    assert all(level > 0 for level in levels.key_resistance)
    assert all(level > 0 for level in levels.swing_highs)


def test_v01_targets_keep_the_highest_three() -> None:
    levels = rules.StructureLevels(
        key_resistance=(104.0, 112.0, 118.0),
        swing_highs=(106.0, 120.0, 130.0),
        swing_lows=(90.0,),
    )
    targets = rules.v01_targets(100.0, 2.0, levels)
    # Measured move 100 + (130 - 90) = 140 also qualifies; highest three win.
    assert targets == [120.0, 130.0, 140.0]


def test_v01_targets_fall_back_to_atr_when_no_structure() -> None:
    targets = rules.v01_targets(100.0, 10.0, rules.StructureLevels())
    assert targets == [120.0, 130.0, 140.0]


def test_v01_targets_fall_back_to_fixed_percent_without_atr() -> None:
    targets = rules.v01_targets(100.0, None, rules.StructureLevels())
    assert targets == [108.0, 115.0, 125.0]


def test_v01_targets_parity_with_synthesis() -> None:
    technical = TechnicalAnalysis(
        score=0.5,
        ma_alignment="bullish",
        rsi_regime="neutral",
        adx_verdict="strong",
        volatility_regime="normal",
        findings=[],
        key_resistance=[104.0, 112.0, 118.0],
        swing_highs=[106.0, 120.0, 130.0],
        swing_lows=[90.0, 95.0],
    )
    expected = synthesis._get_structural_targets_long(  # noqa: SLF001
        technical, None, 100.0, [], atr=2.0
    )
    levels = rules.StructureLevels(
        key_resistance=tuple(technical.key_resistance or ()),
        swing_highs=tuple(technical.swing_highs or ()),
        swing_lows=tuple(technical.swing_lows or ()),
    )
    assert rules.v01_targets(100.0, 2.0, levels) == expected


# ── Gate ────────────────────────────────────────────────────────────────────


def test_v01_gate_reproduces_the_midpoint_vs_entry_low_quirk() -> None:
    decision = rules.v01_plan(
        _geometry(),
        rules.StructureLevels(key_resistance=(110.0, 120.0, 130.0)),
    )
    assert decision.plan_rr == pytest.approx(8.38, abs=0.01)
    # 5c compares the midpoint RR to the entry-low geometry, exactly as live.
    assert decision.gate_verdict == "CONDITIONAL"
    assert "disagrees" in (decision.gate_note or "")


def test_v01_gate_fails_below_the_legacy_floor() -> None:
    decision = rules.v01_plan(
        _geometry(),
        rules.StructureLevels(key_resistance=(100.4,)),
    )
    assert decision.gate_verdict == "FAIL"


def test_v02_gate_passes_above_the_family_full_floor() -> None:
    decision = rules.v02_plan(
        _geometry(), rules.StructureLevels(key_resistance=(104.5,)), "mean_reversion"
    )
    # (104.5 - 98.5) / 2.5 = 2.4R → above the 1.5R full floor, inside the 2.5R cap.
    assert decision.has_plan
    assert decision.plan_rr == pytest.approx(2.4)
    assert decision.gate_verdict == "PASS"


def test_v02_gate_is_conditional_in_the_half_size_tier() -> None:
    # Trend: 2.0R half floor, 2.5R full floor. 104 → 2.2R.
    decision = rules.v02_plan(
        _geometry(), rules.StructureLevels(key_resistance=(104.0,)), "trend"
    )
    assert decision.plan_rr == pytest.approx(2.2)
    assert decision.gate_verdict == "CONDITIONAL"


def test_v02_rejects_target_too_close() -> None:
    decision = rules.v02_plan(
        _geometry(), rules.StructureLevels(key_resistance=(101.0,)), "mean_reversion"
    )
    assert not decision.has_plan
    assert decision.rejection == "target too close"


def test_v02_rejects_target_too_far() -> None:
    decision = rules.v02_plan(
        _geometry(), rules.StructureLevels(key_resistance=(120.0,)), "mean_reversion"
    )
    assert not decision.has_plan
    assert decision.rejection == "target too far"


def test_v02_rejects_no_structural_objective() -> None:
    decision = rules.v02_plan(_geometry(), rules.StructureLevels(), "trend")
    assert not decision.has_plan
    assert decision.rejection == "no structural objective"


def test_family_map_matches_the_live_display_names() -> None:
    from backend.app.domain.workflow import exit_policy

    assert exit_policy.family_for_screen("Mean Reversion") == "mean_reversion"
    assert exit_policy.family_for_screen("52-Week Breakout") == "breakout"
    assert exit_policy.family_for_screen("trend-follower-v2") == "trend"
    # Live display names that do not normalize to the family sets (G11).
    assert exit_policy.family_for_screen(
        "Institutional Trend Follower (Multi-Timeframe)"
    ) == "unknown"
    assert exit_policy.family_for_screen("Low-Vol Setup Simple") == "unknown"


# ── Fills ───────────────────────────────────────────────────────────────────


def test_fill_never_happens_on_the_signal_bar() -> None:
    bars = [
        _bar("2026-10-01", 100.0, 101.0, 97.0, 99.0),   # signal bar touches limit
        _bar("2026-10-02", 99.0, 100.0, 98.4, 99.5),
    ]
    decision = rules.evaluate_fill(_geometry(), "2026-10-01", bars)
    assert decision.status == pending_mod.FILLED
    assert decision.fill_date == "2026-10-02"


def test_fill_at_limit_when_the_bar_trades_through() -> None:
    bars = [_bar("2026-10-02", 100.0, 100.5, 98.4, 99.0)]
    decision = rules.evaluate_fill(_geometry(), "2026-10-01", bars)
    assert decision.fill_price == pytest.approx(98.5)


def test_fill_expires_after_three_sessions() -> None:
    bars = [
        _bar("2026-10-02", 101.0, 102.0, 99.0, 101.0),
        _bar("2026-10-05", 101.0, 102.0, 99.0, 101.0),
        _bar("2026-10-06", 101.0, 102.0, 99.0, 101.0),
        _bar("2026-10-07", 100.0, 101.0, 98.0, 99.0),
    ]
    decision = rules.evaluate_fill(_geometry(), "2026-10-01", bars)
    assert decision.status == pending_mod.EXPIRED


def test_fill_cancels_when_the_open_gaps_through_the_stop() -> None:
    bars = [_bar("2026-10-02", 95.0, 96.0, 94.0, 95.0)]
    decision = rules.evaluate_fill(_geometry(), "2026-10-01", bars)
    assert decision.status == pending_mod.CANCELLED


# ── Exits ───────────────────────────────────────────────────────────────────


def test_v01_exit_checks_t2_before_t1_within_a_bar() -> None:
    bars = [
        _bar("2026-10-02", 100.0, 100.5, 99.0, 100.0),   # entry bar
        _bar("2026-10-05", 100.0, 125.0, 99.0, 120.0),   # spans both targets
    ]
    outcome = rules.v01_outcome(
        bars, fill=_fill(), stop_loss=96.0, targets=[110.0, 120.0], shares=100.0
    )
    assert outcome.exit_reason == exits_mod.EXIT_TARGET_2
    assert outcome.exit_price == 120.0


def test_v01_exit_time_stop_at_the_close() -> None:
    bars = [_bar("2026-10-02", 100.0, 100.5, 99.0, 100.0)]
    bars.append(_bar("2026-12-15", 100.0, 100.5, 99.0, 100.0))
    outcome = rules.v01_outcome(
        bars, fill=_fill(), stop_loss=96.0, targets=[130.0], shares=100.0
    )
    assert outcome.exit_reason == exits_mod.EXIT_TIME


def test_v02_mean_reversion_exits_fully_at_t1() -> None:
    bars = [
        _bar("2026-10-02", 100.0, 100.5, 99.0, 100.0),
        _bar("2026-10-05", 100.0, 106.0, 99.5, 105.0),
    ]
    outcome = rules.v02_outcome(
        bars, fill=_fill(), stop_loss=96.0, targets=[104.0],
        family="mean_reversion", atr=2.0, shares=100.0,
    )
    assert outcome.exit_reason == exits_mod.EXIT_TARGET_1
    assert outcome.legs and outcome.legs[0]["size_pct"] == 100.0
    assert outcome.exit_price == 104.0


def test_v02_trend_scales_out_and_trails_the_runner() -> None:
    bars = [
        _bar("2026-10-02", 100.0, 100.5, 99.0, 100.0),
        _bar("2026-10-05", 100.0, 105.0, 99.5, 104.0),   # T1 at 104
        _bar("2026-10-06", 104.0, 109.0, 103.0, 108.0),  # T2 at 108
        _bar("2026-10-07", 108.0, 108.5, 100.0, 101.0),  # trail (2×ATR) stops the rest
    ]
    outcome = rules.v02_outcome(
        bars, fill=_fill(), stop_loss=96.0, targets=[104.0, 108.0],
        family="trend", atr=2.0, shares=300.0,
    )
    assert [leg["reason"] for leg in outcome.legs] == [
        exits_mod.EXIT_TARGET_1,
        exits_mod.EXIT_TARGET_2,
        "trail",
    ]
    assert sum(leg["size_pct"] for leg in outcome.legs) == pytest.approx(100.0, abs=0.01)
    assert outcome.realized_r == pytest.approx(2.73, abs=0.05)


def test_v02_trail_supersedes_breakeven_after_t1() -> None:
    bars = [
        _bar("2026-10-02", 100.0, 100.5, 99.0, 100.0),
        _bar("2026-10-05", 100.0, 105.0, 99.5, 104.0),   # T1 at 104, BE + trail armed
        _bar("2026-10-06", 104.0, 104.5, 98.4, 99.0),    # back through the trail
    ]
    outcome = rules.v02_outcome(
        bars, fill=_fill(), stop_loss=96.0, targets=[104.0, 200.0],
        family="trend", atr=2.0, shares=300.0,
    )
    assert [leg["reason"] for leg in outcome.legs] == [
        exits_mod.EXIT_TARGET_1,
        "trail",
    ]
    # The trail (close − 2×ATR = 100) is above breakeven (the 98.5 fill).
    assert outcome.legs[-1]["price"] == pytest.approx(100.0)


def test_censor_closes_at_the_last_close() -> None:
    bars = [
        _bar("2026-10-02", 100.0, 100.5, 99.0, 100.0),
        _bar("2026-10-05", 100.0, 100.5, 99.0, 100.5),
    ]
    outcome = rules.v01_outcome(
        bars, fill=_fill(), stop_loss=96.0, targets=[130.0], shares=100.0
    )
    assert outcome.censored is True
    assert outcome.exit_reason == "eod"
    assert outcome.exit_price == 100.5


def test_same_session_stop_is_conservative() -> None:
    decision = pending_mod.FillDecision(
        pending_mod.FILLED,
        fill_date="2026-10-02",
        fill_price=98.5,
        bar=_bar("2026-10-02", 99.0, 99.5, 95.0, 96.0),
    )
    assert rules.same_session_stop(decision, 96.0) is True
    outcome = rules.stop_outcome(decision, 96.0, 100.0)
    assert outcome.exit_reason == exits_mod.EXIT_STOP
    assert outcome.realized_r == pytest.approx(-1.0)


# ── Accounting ──────────────────────────────────────────────────────────────


def test_accounting_matches_the_canonical_cost_model() -> None:
    money = rules.accounting(100.0, 110.0, 95.0, 200.0)
    assert money["realized_r"] == pytest.approx(2.0)
    assert money["pnl_gross_usd"] == pytest.approx(2000.0)
    assert money["costs_usd"] == pytest.approx(63.0)
    assert money["pnl_usd"] == pytest.approx(1937.0)


def test_shares_for_uses_fixed_fractional_risk() -> None:
    assert rules.shares_for(100.0, 95.0) == pytest.approx(200.0)
    assert rules.shares_for(100.0, 100.0) is None
