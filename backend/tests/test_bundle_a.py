"""Bundle A (D-77) — gate floors, planned-fill Plan R and synthesis geometry.

These lock the v0.2 behaviour the frozen spec requires:

- Plan R is T1 measured from the planned fill (``entry_low``), not the last
  target (the CRS defect).
- The 5d floor is the family's full-size floor, with the half-size floor as
  CONDITIONAL.
- Synthesis selects the nearest structural level inside the family band; no
  level in the band rejects the plan instead of manufacturing a target.
- The stored management plan matches the family policy (tranches, ATR trail,
  breakeven, time stop).
"""

from __future__ import annotations

from typing import Any

import pytest

from backend.app.domain.ticker_analysis import synthesis
from backend.app.domain.ticker_analysis.models import (
    AnalysisVerdict,
    FundamentalAnalysis,
    RiskAssessment,
    SentimentAnalysis,
    TechnicalAnalysis,
)
from backend.app.domain.workflow import exit_policy as ep
from backend.app.domain.workflow import gate


# ── Fixtures ────────────────────────────────────────────────────────────


def _technical(**kw: Any) -> TechnicalAnalysis:
    base = TechnicalAnalysis(
        score=0.4,
        ma_alignment="bullish",
        rsi=55.0,
        rsi_regime="neutral_bullish",
        adx=28.0,
        adx_verdict="moderate",
        atr_pct=2.0,
        volatility_regime="normal",
        volume_ratio=1.2,
        bb_position="inside",
        macd_status="bullish",
        structure="bullish",
        # Default fixture: levels sit far above the 4R trend cap.
        swing_highs=[110.0, 115.0, 120.0],
        swing_lows=[95.0, 98.0, 100.0],
        key_resistance=[115.0, 120.0],
        key_support=[98.0, 95.0],
        pullback_quality="A",
        pullback_score=85.0,
        findings=[],
    )
    return base.model_copy(update=kw) if kw else base


def _fundamental() -> FundamentalAnalysis:
    return FundamentalAnalysis(
        score=0.3,
        instrument_type="equity",
        exchange_category="primary",
        findings=[],
    )


def _sentiment() -> SentimentAnalysis:
    return SentimentAnalysis(
        score=0.2,
        analyst_consensus="Buy",
        insider_status="neutral",
        short_interest_pct=5.0,
        days_to_cover=2.0,
        institutional_ownership=0.6,
        beta=1.1,
        target_price=110.0,
        target_upside_pct=10.0,
        undervalued=False,
        findings=[],
    )


def _risk() -> RiskAssessment:
    return RiskAssessment(
        score=0.1,
        volatility_regime="normal",
        suggested_stop_pct=5.0,
        suggested_position_size_pct=10.0,
        max_risk_per_trade_pct=1.0,
        findings=[],
    )


def _verdict(technical: TechnicalAnalysis, family: str) -> AnalysisVerdict:
    return synthesis.synthesise(
        technical=technical,
        fundamental=_fundamental(),
        earnings=None,
        sentiment=_sentiment(),
        risk=_risk(),
        price=100.0,
        tv_data={"ATR": 2.5},
        setup_family=family,
    )


# ── Gate: family floors (5d) ────────────────────────────────────────────


def _rr_step(
    *,
    targets: list[float],
    reported_rr: float,
    family: str | None,
) -> gate.GateStepResult:
    inp = gate.build_gate_input(
        symbol="TEST",
        entry_low=95.0,
        entry_high=96.0,
        stop_loss=90.0,
        targets=targets,
        risk_reward=reported_rr,
        setup_family=family,
    )
    return gate.evaluate_risk_reward(inp)


def test_trend_floor_pass_at_full_size() -> None:
    result = _rr_step(targets=[107.5], reported_rr=2.5, family="trend")
    assert result.passed is True
    assert result.conditional is False
    assert "full-size floor" in result.note


def test_trend_floor_conditional_between_half_and_full() -> None:
    result = _rr_step(targets=[105.0], reported_rr=2.0, family="trend")
    assert result.passed is False
    assert result.conditional is True
    assert "half-size tier" in result.note


def test_trend_floor_fails_below_half_size() -> None:
    result = _rr_step(targets=[104.0], reported_rr=1.8, family="trend")
    assert result.passed is False
    assert result.conditional is False
    assert "below the trend floor" in result.note


@pytest.mark.parametrize(
    ("target", "rr", "passed", "conditional"),
    [
        (101.25, 1.25, False, True),   # mean-reversion half-size floor
        (102.5, 1.5, True, False),     # mean-reversion full-size floor
        (100.0, 1.0, False, False),    # below the mean-reversion floor
    ],
)
def test_mean_reversion_floor_tiers(
    target: float, rr: float, passed: bool, conditional: bool,
) -> None:
    result = _rr_step(targets=[target], reported_rr=rr, family="mean_reversion")
    assert result.passed is passed
    assert result.conditional is conditional


def test_breakout_floor_matches_the_trend_floor_tiers() -> None:
    # The gate enforces floors, not the selection cap: a hand-built 4.5R T1 is
    # above the breakout/trend full-size floor and PASSES. The 5R breakout cap
    # lives in target selection (test_exit_policy), not in the gate.
    breakout = _rr_step(targets=[117.5], reported_rr=4.5, family="breakout")
    trend = _rr_step(targets=[117.5], reported_rr=4.5, family="trend")
    assert breakout.passed is True
    assert trend.passed is True


# ── Gate 5c: T1 from the planned fill (A1) ─────────────────────────────


def test_rr_consistency_measures_t1_for_v02_not_last_target() -> None:
    result = _rr_step(targets=[107.5, 130.0], reported_rr=2.5, family="trend")
    assert result.passed is True
    assert "T1 (planned fill)" in result.note
    assert "consistent with T1" in result.note


def test_rr_consistency_legacy_keeps_last_target_basis() -> None:
    result = _rr_step(targets=[105.0, 130.0], reported_rr=7.0, family=None)
    assert result.passed is True
    assert "last target" in result.note


# ── Synthesis: accepted plan (trend) ────────────────────────────────────


def test_trend_plan_selects_nearest_structural_target_in_band() -> None:
    technical = _technical(
        swing_highs=[101.5, 102.5, 103.5],
        key_resistance=[101.5, 102.5],
    )
    verdict = _verdict(technical, "trend")

    assert verdict.plan_rejection is None
    assert verdict.entry_zone_low == pytest.approx(98.5)
    assert verdict.stop_loss == pytest.approx(97.51)
    assert verdict.targets == pytest.approx([101.5, 102.5, 103.5])
    # T1 R from the planned fill, not the last target.
    assert verdict.risk_reward == pytest.approx(3.03, abs=0.01)

    plan = verdict.trade_plan
    assert plan is not None
    assert plan.setup_family == "trend"
    assert plan.atr_at_entry == pytest.approx(2.5)
    assert plan.max_hold_days == 30
    assert plan.move_to_breakeven_at_r == 1.0
    assert plan.trail_type == "atr"
    assert plan.trail_value == 2.0
    assert [leg["target"] for leg in plan.scale_out] == ["T1", "T2", "runner"]
    assert sum(leg["position_fraction"] for leg in plan.scale_out) == pytest.approx(1.0)
    assert plan.scale_out[0]["position_fraction"] == pytest.approx(1 / 3, abs=1e-4)
    assert plan.scale_out[1]["position_fraction"] == pytest.approx(1 / 3, abs=1e-4)


# ── Synthesis: accepted plan (mean reversion) ───────────────────────────


def test_mean_reversion_plan_exits_fully_at_t1_and_has_no_runner() -> None:
    technical = _technical(
        swing_highs=[100.8, 101.5, 102.5],
        key_resistance=[100.8, 101.5],
    )
    verdict = _verdict(technical, "mean_reversion")

    assert verdict.plan_rejection is None
    assert verdict.targets[0] == pytest.approx(100.8)
    assert verdict.risk_reward == pytest.approx(2.32, abs=0.01)

    plan = verdict.trade_plan
    assert plan is not None
    assert plan.setup_family == "mean_reversion"
    assert plan.max_hold_days == 10
    assert plan.move_to_breakeven_at_r == 0.0
    assert plan.trail_type == "none"
    assert len(plan.scale_out) == 1
    assert plan.scale_out[0]["target"] == "T1"
    assert plan.scale_out[0]["position_fraction"] == pytest.approx(1.0)


# ── Synthesis: rejection when nothing is inside the band ────────────────


def test_plan_rejected_when_no_structural_level_is_inside_the_band() -> None:
    verdict = _verdict(_technical(), "trend")

    assert verdict.action == "WATCH"
    assert verdict.conviction <= 4
    assert verdict.targets == []
    assert verdict.risk_reward is None
    assert verdict.plan_rejection == ep.REJECT_TOO_FAR
    assert any("Plan rejected" in d for d in verdict.dealbreakers)

    # The family policy is still recorded so the rejection is attributable.
    assert verdict.trade_plan is not None
    assert verdict.trade_plan.setup_family == "trend"
    assert verdict.trade_plan.max_hold_days == 30


def test_target_too_close_is_rejected_with_its_own_label() -> None:
    # With no swing lows there is no measured move; 100.3 is the only level and
    # sits below the 2.0R trend floor.
    technical = _technical(
        swing_highs=[100.3],
        swing_lows=[],
        key_resistance=[100.3],
    )
    verdict = _verdict(technical, "trend")

    assert verdict.plan_rejection == ep.REJECT_TOO_CLOSE
    assert verdict.targets == []


def test_no_structural_objective_is_rejected_without_a_fallback() -> None:
    technical = _technical(swing_highs=[], swing_lows=[], key_resistance=[])
    verdict = _verdict(technical, "trend")

    assert verdict.plan_rejection == ep.REJECT_NO_OBJECTIVE
    assert verdict.targets == []
