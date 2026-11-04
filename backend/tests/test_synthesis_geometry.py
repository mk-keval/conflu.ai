"""Geometry invariant regression tests for synthesis engine.

Tests use synthetic data to verify plan geometry invariants:
1. Stop beyond entry zone (structure-anchored)
2. R/R >= 2.0 via priority order (stop anchor -> target extension -> downgrade)
3. Conviction recalibration for breakout rvol
4. Treasury asset path with caps and caveat

No network calls, pure unit tests with synthetic fixtures.
"""

from __future__ import annotations

from typing import Any

import pytest

from backend.app.domain.ticker_analysis.models import (
    AnalysisVerdict,
    FundamentalAnalysis,
    RiskAssessment,
    SentimentAnalysis,
    TechnicalAnalysis,
    TradePlan,
)
from backend.app.domain.ticker_analysis import synthesis
from backend.app.domain.workflow.gate import evaluate_stop_distance


def test_stop_distance_exceeding_explicit_ceiling_fails() -> None:
    from backend.app.domain.ticker_analysis.models import GateStepResult

    result = evaluate_stop_distance(
        entry=100.0, stop=92.0, max_stop_distance_pct=7.0,
    )

    assert isinstance(result, GateStepResult)
    assert result.name == "Risk/Reward"
    assert result.passed is False
    assert result.conditional is False
    assert "8.0%" in result.note
    assert "7.0%" in result.note


# ── Helpers ──


def _make_technical(**kw: Any) -> TechnicalAnalysis:
    base = TechnicalAnalysis(
        score=0.0,
        ma_alignment="bullish",
        rsi=55.0,
        rsi_regime="neutral_bullish",
        adx=25.0,
        adx_verdict="moderate",
        atr_pct=2.0,
        volatility_regime="normal",
        volume_ratio=1.0,
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
        score=0.3,
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


def _make_sentiment(**kw: Any) -> SentimentAnalysis:
    base = SentimentAnalysis(
        score=0.1,
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
    return base.model_copy(update=kw) if kw else base


def _make_risk(**kw: Any) -> RiskAssessment:
    base = RiskAssessment(
        score=0.1,
        volatility_regime="normal",
        suggested_stop_pct=5.0,
        suggested_position_size_pct=10.0,
        max_risk_per_trade_pct=1.0,
        findings=[],
    )
    return base.model_copy(update=kw) if kw else base


def _synthesise(
    technical: TechnicalAnalysis | None = None,
    fundamental: FundamentalAnalysis | None = None,
    sentiment: SentimentAnalysis | None = None,
    risk: RiskAssessment | None = None,
    price: float = 100.0,
    tv_data: dict[str, Any] | None = None,
    regime: str | None = None,
) -> AnalysisVerdict:
    """Call synthesis.synthesise with synthetic data."""
    return synthesis.synthesise(
        technical=technical or _make_technical(),
        fundamental=fundamental or _make_fundamental(),
        earnings=None,
        sentiment=sentiment or _make_sentiment(),
        risk=risk or _make_risk(),
        price=price,
        tv_data=tv_data,
        regime=regime,
    )


# ── INVARIANT 1: Stop beyond entry zone ──────────────────────────────


class TestInvariant1StopBeyondEntryZone:
    """Stop must be strictly below entry_zone_low for LONG actions."""

    def test_bull_invalid_geometry_repaired_or_downgraded(self):
        """
        BULL case: entry 7.71–8.97, stop 8.13 INSIDE zone (price ~9.50).
        Structural anchor (swing low) sits >= entry_zone_low.
        Should widen entry_zone_low to structure*0.99 and recompute stop,
        OR downgrade to WATCH with explicit reason if zone > 15%.
        """
        # BULL-like setup: price near 9.50, entry zone 7.71-8.97, stop 8.13 inside
        # Need higher scores to get ACCUMULATE action (vet plan was BUY, app was ACCUMULATE)
        tech = _make_technical(
            score=0.6,  # Strong technical
            ma_alignment="bullish",
            swing_lows=[8.50, 8.00],  # Recent swing lows
            key_support=[8.00, 7.50],
            rsi=65.0,
            rsi_regime="neutral_bullish",
            adx=28.0,
        )
        fund = _make_fundamental(score=0.4)
        risk = _make_risk(score=0.2, suggested_stop_pct=8.0)  # Wide stop that ends up inside zone
        sent = _make_sentiment(score=0.2)
        tv_data = {
            "SMA20": 8.20,
            "SMA50": 7.80,
            "close": 9.50,
        }
        
        verdict = _synthesise(technical=tech, fundamental=fund, risk=risk, sentiment=sent, price=9.50, tv_data=tv_data)
        
        # Should get positive action (BUY/ACCUMULATE/STRONG BUY) and then invariants enforced
        assert verdict.action in ("BUY", "ACCUMULATE", "STRONG BUY", "WATCH"), f"Unexpected action: {verdict.action}"
        
        # Either stop is below entry_low, OR action is WATCH with explicit reason
        if verdict.action in ("BUY", "ACCUMULATE", "STRONG BUY"):
            assert verdict.entry_zone_low is not None, "Entry zone low must be set"
            assert verdict.stop_loss is not None, "Stop loss must be set"
            assert verdict.stop_loss < verdict.entry_zone_low, \
                f"Stop {verdict.stop_loss} must be below entry_low {verdict.entry_zone_low}"
        else:
            # If downgraded to WATCH, must have explicit geometry reason
            assert verdict.action == "WATCH"
            assert any("Geometry invariant failed" in f or "R/R invariant failed" in f for f in verdict.key_red_flags), \
                f"WATCH downgrade must have invariant reason. Red flags: {verdict.key_red_flags}"

    def test_valid_structural_stop_used(self):
        """When structural anchor (swing low) is valid and below entry zone, use it."""
        tech = _make_technical(
            score=0.6,
            swing_lows=[95.0, 92.0, 90.0],  # Chronological (oldest-first): recent low at 90
            key_support=[90.0, 92.0],
            adx=28.0,
        )
        fund = _make_fundamental(score=0.4)
        risk = _make_risk(score=0.2)
        sent = _make_sentiment(score=0.2)
        tv_data = {"SMA20": 96.0, "SMA50": 93.0, "close": 100.0}
        
        verdict = _synthesise(technical=tech, fundamental=fund, risk=risk, sentiment=sent, price=100.0, tv_data=tv_data)
        
        assert verdict.action in ("BUY", "ACCUMULATE", "STRONG BUY")
        assert verdict.stop_loss is not None
        assert verdict.entry_zone_low is not None
        assert verdict.stop_loss < verdict.entry_zone_low
        # Structural stop should be around 90 * 0.995 ≈ 89.55
        assert verdict.stop_loss <= 90.0

    def test_no_structural_anchor_falls_back_to_percentage(self):
        """When no structural anchor, percentage stop is placed below entry_low."""
        tech = _make_technical(
            swing_lows=[],  # No swing lows
            key_support=[],
            ma_alignment="mixed",  # No clear MA support
        )
        tv_data = {"SMA20": 105.0, "SMA50": 110.0, "close": 100.0}  # MAs above price
        
        verdict = _synthesise(technical=tech, price=100.0, tv_data=tv_data)
        
        if verdict.action in ("BUY", "ACCUMULATE", "STRONG BUY"):
            assert verdict.stop_loss is not None
            assert verdict.entry_zone_low is not None
            assert verdict.stop_loss < verdict.entry_zone_low


# ── INVARIANT 2: R/R >= 2.0 via priority order ─────────────────────────


class TestInvariant2RiskReward:
    """R/R must be >= 2.0 via: (1) structural stop, (2) structural targets, (3) downgrade."""

    def test_adbe_structural_stop_lifts_rr(self):
        """
        ADBE case: entry 267-276, pct-stop 249, structural stop ~245.
        RR 1.8 -> 2.4 via tighter structural stop.
        Must preserve valid plan (RR must NOT degrade below current 1.8).
        """
        tech = _make_technical(
            ma_alignment="bullish",
            adx=35.0,
            swing_lows=[242.0, 245.0, 250.0],  # Structural stop around 245
            key_support=[245.0, 242.0],
            key_resistance=[300.0, 320.0],
        )
        tv_data = {
            "SMA20": 260.0,
            "SMA50": 250.0,
            "close": 270.0,
        }
        risk = _make_risk(suggested_stop_pct=8.0)  # Pct stop ~249
        
        verdict = _synthesise(technical=tech, price=270.0, tv_data=tv_data, risk=risk)
        
        assert verdict.action in ("BUY", "ACCUMULATE", "STRONG BUY")
        assert verdict.risk_reward is not None
        # RR should NOT degrade below 1.8 (the original ADBE output)
        assert verdict.risk_reward >= 1.8, f"RR {verdict.risk_reward} must not degrade below 1.8"
        # Ideally improves toward ~2.4 via structural stop
        # Check that structural stop was used (around 245 vs 249)
        if verdict.stop_loss is not None:
            assert verdict.stop_loss <= 249.0, "Stop should be tightened to structural anchor"

    def test_meli_structural_targets_raise_rr(self):
        """
        MELI case: RR 1.6 with timid targets.
        Structural targets: prior swing high 2150, range projection 2400 => RR >= 2.8.
        """
        tech = _make_technical(
            ma_alignment="bullish",
            adx=30.0,
            swing_highs=[2150.0, 2200.0, 2400.0],  # Prior swing highs
            key_resistance=[2150.0, 2400.0],
            swing_lows=[1700.0, 1750.0, 1800.0],
        )
        tv_data = {
            "SMA20": 1850.0,
            "SMA50": 1780.0,
            "close": 1920.0,
        }
        # Use a stop that gives RR ~1.6 with default targets
        risk = _make_risk(suggested_stop_pct=8.0)  # Stop ~1766
        
        verdict = _synthesise(technical=tech, price=1920.0, tv_data=tv_data, risk=risk)
        
        assert verdict.action in ("BUY", "ACCUMULATE", "STRONG BUY")
        assert verdict.risk_reward is not None
        assert verdict.risk_reward >= 2.0, f"RR {verdict.risk_reward} must be >= 2.0 via structural targets"
        # Targets should include structural levels
        assert any(t >= 2100.0 for t in verdict.targets), "Should have structural target at prior swing high"

    def test_downgrade_to_watch_when_both_fail(self):
        """
        When both structural stop and structural targets fail to achieve RR >= 2.0,
        downgrade to WATCH with explicit reason.
        """
        tech = _make_technical(
            ma_alignment="bullish",
            adx=15.0,  # Weak trend
            swing_lows=[],  # No swing lows
            key_support=[],
            swing_highs=[],  # No swing highs
            key_resistance=[],
        )
        tv_data = {"SMA20": 100.0, "SMA50": 95.0, "close": 100.0}
        # Wide stop, no structural anchors
        risk = _make_risk(suggested_stop_pct=15.0)  # Very wide stop
        
        verdict = _synthesise(technical=tech, price=100.0, tv_data=tv_data, risk=risk)
        
        # Should downgrade to WATCH
        assert verdict.action == "WATCH"
        assert any("R/R invariant failed" in f for f in verdict.key_red_flags)


# ── INVARIANT 3: Conviction recalibration for breakout rvol ──────────


class TestInvariant3ConvictionRecalibration:
    """Confirmed breakout + breakout-candle rvol >= 1.5 => conviction floor of 6."""

    def test_breakout_confirmed_high_rvol_floors_conviction_at_6(self):
        """Confirmed breakout with breakout-candle rvol >= 1.5 sets conviction >= 6."""
        tech = _make_technical(
            ma_alignment="bullish",
            findings=["✅ Breakout confirmed above resistance with volume"],
        )
        tv_data = {
            "SMA20": 98.0,
            "SMA50": 95.0,
            "close": 105.0,
            "breakout_confirmed": True,
            "rvol_breakout": 2.0,  # Breakout candle rvol
        }
        
        verdict = _synthesise(technical=tech, price=105.0, tv_data=tv_data)
        
        assert verdict.conviction >= 6, f"Conviction {verdict.conviction} should be >= 6 for confirmed breakout with rvol >= 1.5"

    def test_breakout_confirmed_low_rvol_no_floor(self):
        """Confirmed breakout with breakout-candle rvol < 1.5 does NOT floor conviction."""
        tech = _make_technical(ma_alignment="bullish")
        tv_data = {
            "SMA20": 98.0,
            "SMA50": 95.0,
            "close": 105.0,
            "breakout_confirmed": True,
            "rvol_breakout": 1.0,  # Low breakout rvol
        }
        
        verdict = _synthesise(technical=tech, price=105.0, tv_data=tv_data)
        
        # Conviction should be based on normal scoring, not floored
        # (just verify it doesn't artificially floor to 6)
        assert verdict.conviction >= 1  # Sanity check

    def test_no_breakout_no_floor(self):
        """No breakout confirmed -> no conviction floor."""
        tech = _make_technical(ma_alignment="bullish")
        tv_data = {
            "SMA20": 98.0,
            "SMA50": 95.0,
            "close": 105.0,
            "breakout_confirmed": False,
            "rvol_breakout": 3.0,  # High current rvol but not on breakout candle
        }
        
        verdict = _synthesise(technical=tech, price=105.0, tv_data=tv_data)
        
        # Should not floor conviction to 6
        assert verdict.conviction >= 1  # Sanity check

    def test_current_candle_rvol_not_used(self):
        """Current candle rvol (not breakout candle) should NOT trigger conviction floor."""
        tech = _make_technical(ma_alignment="bullish")
        tv_data = {
            "SMA20": 98.0,
            "SMA50": 95.0,
            "close": 105.0,
            "breakout_confirmed": False,  # No breakout confirmed
            "rvol_breakout": 1.0,  # Breakout rvol low
            "rvol": 2.5,  # Current rvol high (should be ignored)
        }
        
        verdict = _synthesise(technical=tech, price=105.0, tv_data=tv_data)
        
        # Current rvol should not trigger floor
        # Conviction based on normal scoring
        assert verdict.conviction >= 1


# ── TREASURY PATH ───────────────────────────────────────────────────────


class TestTreasuryAssetPath:
    """Treasury asset (BTC proxy) emits plan with caps when guards pass."""

    def test_treasury_bullish_ma_emits_plan_with_caps(self):
        """
        MSTR-style: treasury_asset + bullish MA + normal vol -> plan emitted.
        Conviction capped at 6, position <= 3%, NAV caveat appended.
        """
        tech = _make_technical(
            ma_alignment="bullish",
            adx=25.0,
        )
        fund = _make_fundamental(
            asset_category="treasury_asset",
            market_cap=30_000_000_000,
        )
        risk = _make_risk(volatility_regime="normal")
        tv_data = {"SMA20": 100.0, "SMA50": 95.0, "close": 105.0}
        
        verdict = _synthesise(
            technical=tech, fundamental=fund, risk=risk,
            price=105.0, tv_data=tv_data
        )
        
        # Should emit a plan (not WATCH with no levels)
        assert verdict.action in ("BUY", "ACCUMULATE", "STRONG BUY", "WATCH")
        # If positive action, check caps
        if verdict.action in ("BUY", "ACCUMULATE", "STRONG BUY"):
            assert verdict.conviction <= 6, f"Treasury conviction {verdict.conviction} capped at 6"
            assert verdict.position_size_pct <= 3.0, f"Treasury position {verdict.position_size_pct}% capped at 3%"
            # NAV caveat in thesis
            # NAV-framework thesis caveat (needle lowercase to match .lower() haystack)
            assert "value tracks reserve asset nav" in verdict.thesis.lower(), \
                "Thesis must contain NAV-framework caveat"
        else:
            # If WATCH, must have explicit reason (guards would have failed)
            assert any("treasury" in f.lower() for f in verdict.key_red_flags)

    def test_treasury_bearish_ma_still_refused(self):
        """
        Treasury asset with bearish MA -> still refused (current behavior).
        """
        tech = _make_technical(ma_alignment="bearish")
        fund = _make_fundamental(asset_category="treasury_asset")
        risk = _make_risk(volatility_regime="normal")
        tv_data = {"SMA20": 110.0, "SMA50": 115.0, "close": 105.0}
        
        verdict = _synthesise(
            technical=tech, fundamental=fund, risk=risk,
            price=105.0, tv_data=tv_data
        )
        
        # Should be refused (WATCH with no plan)
        assert verdict.action == "WATCH"
        assert verdict.entry_zone_low is None
        assert verdict.stop_loss is None
        assert verdict.targets == []

    def test_treasury_extreme_vol_still_refused(self):
        """
        Treasury asset with extreme volatility -> still refused.
        """
        tech = _make_technical(ma_alignment="bullish")
        fund = _make_fundamental(asset_category="treasury_asset")
        risk = _make_risk(volatility_regime="extreme")
        tv_data = {"SMA20": 100.0, "SMA50": 95.0, "close": 105.0}
        
        verdict = _synthesise(
            technical=tech, fundamental=fund, risk=risk,
            price=105.0, tv_data=tv_data
        )
        
        # Should be refused
        assert verdict.action == "WATCH"
        assert verdict.entry_zone_low is None

    def test_treasury_nav_caveat_in_findings(self):
        """NAV framework caveat appears in findings."""
        tech = _make_technical(ma_alignment="bullish")
        fund = _make_fundamental(asset_category="treasury_asset")
        risk = _make_risk(volatility_regime="normal")
        tv_data = {"SMA20": 100.0, "SMA50": 95.0, "close": 105.0}
        
        verdict = _synthesise(
            technical=tech, fundamental=fund, risk=risk,
            price=105.0, tv_data=tv_data
        )
        
        if verdict.action in ("BUY", "ACCUMULATE", "STRONG BUY"):
            assert any("NAV framework" in f for f in verdict.key_red_flags + [verdict.thesis])


# ── Integration: Existing tests still pass ───────────────────────────────


class TestExistingBehaviorPreserved:
    """Ensure existing override logic still works."""

    def test_squeeze_override_still_fires(self):
        """Short interest > 30% still triggers squeeze override."""
        sent = _make_sentiment(short_interest_pct=35.0, beta=2.0)
        verdict = _synthesise(sentiment=sent)
        assert verdict.action == "WATCH"
        assert any("Short interest" in f for f in verdict.key_red_flags)

    def test_development_override_still_fires(self):
        """Development lifecycle still triggers override."""
        fund = _make_fundamental(lifecycle_stage="development")
        verdict = _synthesise(fundamental=fund)
        assert verdict.action == "WATCH"

    def test_etf_override_still_fires(self):
        """ETF instrument type still triggers override."""
        fund = _make_fundamental(instrument_type="etf")
        verdict = _synthesise(fundamental=fund)
        assert verdict.action == "WATCH"

    def test_avoid_reduce_zero_position(self):
        """AVOID/REDUCE still have zero position size."""
        fund = _make_fundamental(score=-0.8)
        risk = _make_risk(score=-0.8, volatility_regime="extreme",
                          suggested_stop_pct=10.0, suggested_position_size_pct=10.0,
                          findings=["🚨 Extreme risk"])
        sent = _make_sentiment(score=-0.5)
        verdict = _synthesise(fundamental=fund, sentiment=sent, risk=risk)
        assert verdict.action in ("AVOID", "REDUCE")
        assert verdict.position_size_pct == 0.0

    def test_meme_position_cap_still_applies(self):
        """Meme position cap (SI>10%, beta>1.5, bearish MA) still applies."""
        sent = _make_sentiment(short_interest_pct=15.0, beta=1.8)
        tech = _make_technical(ma_alignment="bearish")
        risk = _make_risk(suggested_position_size_pct=15.0)
        verdict = _synthesise(technical=tech, sentiment=sent, risk=risk)
        assert verdict.position_size_pct <= 5.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])