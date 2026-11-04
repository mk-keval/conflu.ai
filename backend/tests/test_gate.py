"""Workflow gate wiring regression tests (plan Sec.1C, D-53/D-55).

Verifies that `synthesis.synthesise()` attaches an honest `GateResult` to the
final `AnalysisVerdict`:

1. The gate is evaluated LAST — it must read the FINAL conviction (post D-44
   binary-risk cap), not pre-cap values.
2. Missing inputs degrade to CONDITIONAL (never a false PASS).
3. The 2.5:1 R:R floor (5d) is NOT enforced yet (deferred to plan 1H).
"""

from __future__ import annotations

from typing import Any

import pytest

from backend.app.domain.ticker_analysis.models import (
    AnalysisVerdict,
    EarningsAnalysis,
    FundamentalAnalysis,
    GateResult,
    TechnicalAnalysis,
    TradePlan,
)
from backend.app.domain.ticker_analysis import synthesis
from backend.app.domain.workflow import gate as gate_module


# ── Helpers (mirror test_synthesis_geometry fixtures) ──


def _make_technical(**kw: Any) -> TechnicalAnalysis:
    base = TechnicalAnalysis(
        score=0.6,
        ma_alignment="bullish",
        rsi=58.0,
        rsi_regime="neutral_bullish",
        adx=28.0,
        adx_verdict="moderate",
        atr_pct=2.0,
        volatility_regime="normal",
        volume_ratio=1.3,
        bb_position="inside",
        macd_status="bullish",
        structure="bullish",
        swing_highs=[110.0, 115.0, 120.0],
        swing_lows=[95.0, 98.0, 100.0],
        key_resistance=[115.0, 120.0],
        key_support=[98.0, 95.0],
        pullback_quality="A",
        pullback_score=85.0,
        findings=[],
    )
    return base.model_copy(update=kw) if kw else base


def _make_fundamental(**kw: Any) -> FundamentalAnalysis:
    base = FundamentalAnalysis(
        score=0.5,
        instrument_type="equity",
        exchange_category="primary",
        asset_category="operating",
        lifecycle_stage="operating",
        market_cap=50_000_000_000,
        pe_ratio=20.0,
        eps=2.5,
        profit_margin=15.0,
        debt_to_equity=0.5,
        revenue_growth_yoy=10.0,
        findings=[],
    )
    return base.model_copy(update=kw) if kw else base


def _synthesise(
    technical: TechnicalAnalysis | None = None,
    fundamental: FundamentalAnalysis | None = None,
    earnings: EarningsAnalysis | None = None,
    price: float = 100.0,
    tv_data: dict[str, Any] | None = None,
) -> AnalysisVerdict:
    return synthesis.synthesise(
        technical=technical or _make_technical(),
        fundamental=fundamental or _make_fundamental(),
        earnings=earnings,
        sentiment=None,
        risk=None,
        price=price,
        tv_data=tv_data,
        regime=None,
    )


# ── Wiring tests ──


def test_verdict_always_carries_a_gate_result() -> None:
    """Every synthesise() call attaches a typed GateResult to the verdict."""
    verdict = _synthesise()
    assert verdict.gate is not None
    gate: GateResult = verdict.gate
    # All seven steps present, in plan order.
    assert [s.name for s in gate.steps] == [
        "Liquidity", "Structure", "Positioning", "Catalyst",
        "Risk/Reward", "Portfolio Fit", "Conviction",
    ]
    assert gate.overall in ("PASS", "FAIL", "CONDITIONAL")
    assert gate.conviction_score == verdict.conviction
    assert gate.evaluated_at  # non-empty ISO timestamp


def test_gate_reads_post_binary_risk_conviction() -> None:
    """The gate must read the FINAL conviction (post D-44 cap at 5)."""
    earnings = EarningsAnalysis(
        score=0.5,
        days_until_earnings=2,
        next_earnings_date="2026-09-30",
        findings=[],
    )
    verdict = _synthesise(earnings=earnings)
    assert verdict.binary_risk is True
    assert verdict.conviction <= 5
    assert verdict.gate is not None
    # Same number the gate saw — no pre-cap leakage.
    assert verdict.gate.conviction_score == verdict.conviction


def test_gate_is_honest_conditional_not_false_pass() -> None:
    """Wave-1 un-wired steps (Positioning, Portfolio Fit) must NOT pass."""
    verdict = _synthesise()
    assert verdict.gate is not None
    by_name = {s.name: s for s in verdict.gate.steps}
    # Positioning and Portfolio Fit are not wired in Wave-1 → CONDITIONAL.
    assert by_name["Positioning"].passed is False
    assert by_name["Positioning"].conditional is True
    assert by_name["Portfolio Fit"].passed is False
    assert by_name["Portfolio Fit"].conditional is True
    # Overall cannot be PASS while any step is CONDITIONAL.
    assert verdict.gate.overall != "PASS"


def test_gate_passes_liquidity_when_adv_above_floor() -> None:
    tv_data = {"avg_daily_volume_usd_calc": 25_000_000.0}
    verdict = _synthesise(tv_data=tv_data)
    assert verdict.gate is not None
    by_name = {s.name: s for s in verdict.gate.steps}
    assert by_name["Liquidity"].passed is True
    assert by_name["Liquidity"].conditional is False


def test_gate_conditionally_fails_tiny_adv() -> None:
    """Zero-dollar tickers keep their volume and gate honestly (D-55)."""
    tv_data = {"avg_daily_volume_usd_calc": 0.0}
    verdict = _synthesise(tv_data=tv_data)
    assert verdict.gate is not None
    by_name = {s.name: s for s in verdict.gate.steps}
    # 0 < $5M half-floor → hard liquidity FAIL (too thin to trade), not a pass.
    assert by_name["Liquidity"].passed is False
    assert by_name["Liquidity"].conditional is False
    assert verdict.gate.overall == "FAIL"


def test_gate_uses_verdict_catalyst_bias() -> None:
    tv_data = {"catalyst_bias_direction": "bullish"}
    verdict = _synthesise(tv_data=tv_data)
    assert verdict.gate is not None
    assert {s.name: s for s in verdict.gate.steps}["Catalyst"].passed is True

    tv_data = {"catalyst_bias_direction": "bearish"}
    verdict = _synthesise(tv_data=tv_data)
    assert verdict.gate is not None
    assert {s.name: s for s in verdict.gate.steps}["Catalyst"].passed is False


def test_rr_floor_still_deferred() -> None:
    """5d (2.5:1 R:R floor) is NOT enforced until plan item 1H."""
    # A setup with a low reported R:R must NOT hard-fail on the floor.
    verdict = _synthesise(tv_data={})
    assert verdict.gate is not None
    rr_step = {s.name: s for s in verdict.gate.steps}["Risk/Reward"]
    # No hard fail (passed=False AND conditional=False) purely for a low R:R.
    assert not (rr_step.passed is False and rr_step.conditional is False and "2.5" in rr_step.note)


# ── 1E: stop-distance ceiling (5b) active + 5d stub surfaced ──


def test_stop_ceiling_hard_fails_wide_stop() -> None:
    """A stop wider than MAX_STOP_DISTANCE_PCT (10%) hard-fails Step 5 (D-8)."""
    step = gate_module.evaluate_stop_distance(
        entry=100.0, stop=77.2, max_stop_distance_pct=gate_module.MAX_STOP_DISTANCE_PCT
    )
    assert step.passed is False
    assert step.conditional is False  # hard fail — not a conditional
    assert "22.8%" in step.note


def test_stop_ceiling_passes_tight_stop() -> None:
    step = gate_module.evaluate_stop_distance(
        entry=100.0, stop=95.0, max_stop_distance_pct=gate_module.MAX_STOP_DISTANCE_PCT
    )
    assert step.passed is True
    assert step.conditional is False


def test_evaluate_risk_reward_applies_ceiling_by_default() -> None:
    """evaluate_risk_reward wires MAX_STOP_DISTANCE_PCT into 5b automatically."""
    inp = gate_module.build_gate_input(
        entry_low=100.0, stop_loss=77.2, targets=[110.0, 120.0], risk_reward=2.0
    )
    step = gate_module.evaluate_risk_reward(inp)
    assert step.passed is False
    assert step.conditional is False
    assert "22.8%" in step.note  # ceiling applied, hard fail surfaced


def test_rr_floor_active_enforces_min_2_5() -> None:
    """5d floor is now active: enforces R/R >= 2.5 on plan geometry for PASS."""
    inp = gate_module.build_gate_input(
        entry_low=100.0, stop_loss=98.0, targets=[104.0, 110.0], risk_reward=2.0
    )
    step = gate_module.evaluate_risk_reward(inp)
    # With D1 tier: R/R=2.0 >= 2.0 and r1=2.0 >= 1.0 → CONDITIONAL (half-size)
    assert step.passed is False
    assert step.conditional is True
    assert "D1 tier" in step.note
    assert "half-size CONDITIONAL" in step.note


def test_d1_tier_requires_r1_ge_1_0() -> None:
    """D1 tier requires first target to give at least 1R (r1 >= 1.0)."""
    # R/R=2.2 >= 2.0 but r1=0.5 < 1.0 → should FAIL (not meet D1 tier)
    inp = gate_module.build_gate_input(
        entry_low=100.0, stop_loss=98.0, targets=[101.0, 108.0], risk_reward=2.2
    )
    step = gate_module.evaluate_risk_reward(inp)
    assert step.passed is False
    assert step.conditional is False
    assert "r1=" in step.note
    assert "< 1.0" in step.note


def test_d1_tier_conditional_at_rr_2_0() -> None:
    """D1 tier: CONDITIONAL at R/R >= 2.0 with r1 >= 1.0."""
    # R/R=2.0, risk=3, target1=103 → r1=1.0 exactly
    inp = gate_module.build_gate_input(
        entry_low=100.0, stop_loss=97.0, targets=[103.0, 110.0], risk_reward=2.0
    )
    step = gate_module.evaluate_risk_reward(inp)
    assert step.passed is False
    assert step.conditional is True
    assert "D1 tier" in step.note


def test_full_pass_tier_at_rr_2_5() -> None:
    """Full PASS tier: R/R >= 2.5."""
    # entry=100, stop=96 → risk=4, target=110 → R/R=(110-100)/4=2.5
    inp = gate_module.build_gate_input(
        entry_low=100.0, stop_loss=96.0, targets=[110.0], risk_reward=2.5
    )
    step = gate_module.evaluate_risk_reward(inp)
    assert step.passed is True
    assert step.conditional is False
    assert "R/R floor satisfied" in step.note


# ── 2C: real portfolio fit (journal positions supplied) ──


def _book() -> list[dict]:
    return [
        {"symbol": "MSFT", "sector": "Technology", "position_size_pct": 5.0, "stop_loss": 90.0, "entry_type": "initial"},
        {"symbol": "NVDA", "sector": "Technology", "position_size_pct": 6.0, "stop_loss": 40.0, "entry_type": "initial"},
    ]


def test_portfolio_fit_hard_fails_count_cap() -> None:
    positions = [{"symbol": f"T{i}", "sector": "Other", "position_size_pct": 2.0, "stop_loss": 10.0, "entry_type": "initial"}
                 for i in range(gate_module.MAX_OPEN_POSITIONS)]
    inp = gate_module.build_gate_input(symbol="NEW", open_positions=positions)
    step = gate_module.evaluate_portfolio_fit(inp)
    assert step.passed is False
    assert step.conditional is False
    assert "cap" in step.note.lower()


def test_portfolio_fit_hard_fails_sector_exposure() -> None:
    inp = gate_module.build_gate_input(
        symbol="AAPL", sector="Technology", position_size_pct=25.0, open_positions=_book()
    )
    step = gate_module.evaluate_portfolio_fit(inp)
    assert step.passed is False
    assert step.conditional is False
    assert "36.0%" in step.note  # 5 + 6 + 25 planned


def test_portfolio_fit_passes_under_sector_limit() -> None:
    inp = gate_module.build_gate_input(
        symbol="AAPL", sector="Technology", position_size_pct=10.0, open_positions=_book()
    )
    step = gate_module.evaluate_portfolio_fit(inp)
    assert step.passed is True
    assert step.conditional is False
    assert "21.0%" in step.note  # 5 + 6 + 10 planned


def test_portfolio_fit_blocks_market_add_on_same_stop() -> None:
    inp = gate_module.build_gate_input(
        symbol="MSFT", sector="Technology", stop_loss=90.0, entry_type="initial", open_positions=_book()
    )
    step = gate_module.evaluate_portfolio_fit(inp)
    assert step.passed is False
    assert step.conditional is False
    assert "unchanged stop" in step.note.lower()


def test_portfolio_fit_allows_planned_add_at_new_stop() -> None:
    inp = gate_module.build_gate_input(
        symbol="MSFT", sector="Technology", stop_loss=85.0, entry_type="add", open_positions=_book()
    )
    step = gate_module.evaluate_portfolio_fit(inp)
    assert step.passed is False
    assert step.conditional is True  # permitted but sized as an add
    assert "scale-in" in step.note.lower()


def test_portfolio_fit_stays_conditional_without_journal() -> None:
    """Verdict path (no journal) → honest CONDITIONAL, never a false pass."""
    inp = gate_module.build_gate_input(symbol="MSFT", sector="Technology", position_size_pct=10.0)
    step = gate_module.evaluate_portfolio_fit(inp)
    assert step.passed is False
    assert step.conditional is True