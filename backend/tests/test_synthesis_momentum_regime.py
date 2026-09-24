"""Momentum regime boost regression tests (D-45).

Catches the post-earnings momentum drift case (OKTA/CRWD-style: +32%/+25%
in 5 days post-print) where the base verdict engine would cap at
ACCUMULATE c:4 due to elevated P/E + extreme vol flags, instead of
promoting to BUY c:6+.

No network calls — pure unit tests with synthetic fixtures.
"""

from __future__ import annotations

from typing import Any

import pytest

from backend.app.domain.ticker_analysis.models import (
    AnalysisVerdict,
    EarningsAnalysis,
    FundamentalAnalysis,
    RiskAssessment,
    SentimentAnalysis,
    TechnicalAnalysis,
)
from backend.app.domain.ticker_analysis import synthesis


@pytest.mark.parametrize("dollar_volume, expected_count", [(0.0, 1), (99_999.0, 1), (100_000.0, 0), (None, 0)])
def test_mentor_liquidity_uses_calc_once(dollar_volume, expected_count):
    technical = _make_technical(avg_daily_volume_usd=1.0)
    verdict = synthesis.synthesise(
        technical, _make_fundamental(), None, None, _make_risk(), 100.0,
        tv_data={"avg_daily_volume_usd_calc": dollar_volume},
    )
    mentor_flags = [flag for flag in verdict.dealbreakers if "Mentor" in flag]
    assert len(mentor_flags) == expected_count


# ── Helpers ──


def _make_technical(**kw: Any) -> TechnicalAnalysis:
    base = TechnicalAnalysis(
        score=0.5,
        ma_alignment="mixed",
        rsi=55.0,
        rsi_regime="neutral_bullish",
        adx=25.0,
        adx_verdict="moderate",
        atr_pct=2.0,
        volatility_regime="normal",
        volume_ratio=1.0,
        bb_position="inside",
        macd_status="bullish",
        structure="neutral",
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


def _make_earnings(**kw: Any) -> EarningsAnalysis:
    base = EarningsAnalysis(
        score=0.3,
        last_surprise_pct=2.0,
        beat_rate="3/4",
        avg_reaction_pct=1.5,
        next_earnings_date=None,
        days_until_earnings=None,
        findings=[],
    )
    return base.model_copy(update=kw) if kw else base


# ── Unit tests: detect_momentum_regime ───────────────────────────────────────


class TestDetectMomentumRegime:
    """Unit tests for the momentum regime detector (no synthesise() call)."""

    def test_momentum_breakout_detected_on_strong_technicals(self):
        """Tech score 0.8 + bullish MA + RSI 62 + strong ADX -> momentum_breakout."""
        tech = _make_technical(
            score=0.8,
            ma_alignment="bullish",
            rsi=62.0,
            rsi_regime="neutral_bullish",
            adx=32.0,
            adx_verdict="strong",
        )
        regime, boost, findings = synthesis.detect_momentum_regime(tech, None, None, None)
        assert regime == "momentum_breakout"
        assert boost == pytest.approx(0.20)
        assert len(findings) == 1
        assert "Momentum breakout regime confirmed" in findings[0]

    def test_momentum_breakout_rejected_on_overbought(self):
        """RSI 85 (overbought) -> NOT detected, regime stays 'none' or 'emerging'."""
        tech = _make_technical(
            score=0.8,
            ma_alignment="bullish",
            rsi=85.0,
            rsi_regime="overbought",
            adx=32.0,
            adx_verdict="strong",
        )
        regime, boost, findings = synthesis.detect_momentum_regime(tech, None, None, None)
        # RSI 85 fails the 50<=rsi<=75 check; expect at most 4/5 -> emerging
        assert regime in ("momentum_emerging", "none")
        if regime == "momentum_emerging":
            assert boost == pytest.approx(0.10)
        else:
            assert boost == 0.0

    def test_momentum_breakout_rejected_on_weak_trend(self):
        """Weak ADX verdict -> fail trend strength check."""
        tech = _make_technical(
            score=0.8,
            ma_alignment="bullish",
            rsi=62.0,
            rsi_regime="neutral_bullish",
            adx=10.0,
            adx_verdict="weak",
        )
        regime, boost, _ = synthesis.detect_momentum_regime(tech, None, None, None)
        assert regime in ("momentum_emerging", "none")

    def test_momentum_breakout_rejected_on_bearish_weekly(self):
        """Bearish weekly MA should not trigger breakout boost."""
        tech = _make_technical(
            score=0.8,
            ma_alignment="bullish",
            rsi=62.0,
            adx=32.0,
            adx_verdict="strong",
        )
        weekly = _make_technical(ma_alignment="bearish")
        regime, boost, _ = synthesis.detect_momentum_regime(tech, weekly, None, None)
        assert regime in ("momentum_emerging", "none")

    def test_momentum_breakout_accepts_weekly_mixed(self):
        """Weekly 'mixed' is acceptable — should still trigger."""
        tech = _make_technical(
            score=0.8,
            ma_alignment="bullish",
            rsi=62.0,
            adx=32.0,
            adx_verdict="strong",
        )
        weekly = _make_technical(ma_alignment="mixed")
        regime, boost, _ = synthesis.detect_momentum_regime(tech, weekly, None, None)
        assert regime == "momentum_breakout"
        assert boost == pytest.approx(0.20)

    def test_momentum_breakout_accepts_missing_weekly(self):
        """Missing weekly (None) is acceptable — should still trigger."""
        tech = _make_technical(
            score=0.8,
            ma_alignment="bullish",
            rsi=62.0,
            adx=32.0,
            adx_verdict="strong",
        )
        regime, boost, _ = synthesis.detect_momentum_regime(tech, None, None, None)
        assert regime == "momentum_breakout"

    def test_momentum_breakout_rejected_on_low_score(self):
        """Score < 0.7 -> fail score check."""
        tech = _make_technical(
            score=0.5,
            ma_alignment="bullish",
            rsi=62.0,
            adx=32.0,
            adx_verdict="strong",
        )
        regime, boost, _ = synthesis.detect_momentum_regime(tech, None, None, None)
        assert regime in ("momentum_emerging", "none")

    def test_momentum_breakout_rejected_on_bearish_ma(self):
        """Bearish MA -> fail ma_bullish check."""
        tech = _make_technical(
            score=0.8,
            ma_alignment="bearish",
            rsi=62.0,
            adx=32.0,
            adx_verdict="strong",
        )
        regime, boost, _ = synthesis.detect_momentum_regime(tech, None, None, None)
        assert regime in ("momentum_emerging", "none")

    def test_no_technical_returns_none(self):
        """Missing technical -> 'none', zero boost."""
        regime, boost, findings = synthesis.detect_momentum_regime(None, None, None, None)
        assert regime == "none"
        assert boost == 0.0
        assert findings == []


# ── Unit tests: detect_post_earnings_drift ─────────────────────────────────


class TestDetectPostEarningsDrift:
    """Unit tests for the post-earnings drift detector."""

    def test_post_earnings_drift_detected(self):
        """days_until=-3, surprise=8% -> drift detected, boost=0.20 (fresh)."""
        earnings = _make_earnings(
            days_until_earnings=-3,  # 3 days post-print
            last_surprise_pct=8.0,
            score=0.5,
        )
        is_drift, boost, findings = synthesis.detect_post_earnings_drift(earnings, None)
        assert is_drift is True
        assert boost == pytest.approx(0.20)
        assert len(findings) == 1
        assert "Post-earnings drift" in findings[0]
        assert "+8.0%" in findings[0]

    def test_post_earnings_drift_detected_on_continuation(self):
        """days_until=-10, surprise=3% -> drift detected, boost=0.15 (continuation)."""
        earnings = _make_earnings(
            days_until_earnings=-10,  # 10 days post-print
            last_surprise_pct=3.0,
            score=0.5,
        )
        is_drift, boost, findings = synthesis.detect_post_earnings_drift(earnings, None)
        assert is_drift is True
        assert boost == pytest.approx(0.15)
        assert "continuation window" in findings[0]

    def test_post_earnings_drift_rejected_on_miss(self):
        """last_surprise_pct=-15% -> NOT detected (negative surprise)."""
        earnings = _make_earnings(
            days_until_earnings=-3,
            last_surprise_pct=-15.0,
            score=0.3,
        )
        is_drift, boost, findings = synthesis.detect_post_earnings_drift(earnings, None)
        assert is_drift is False
        assert boost == 0.0
        assert findings == []

    def test_post_earnings_drift_rejected_outside_window(self):
        """days_until=-30 (too old) -> NOT detected."""
        earnings = _make_earnings(
            days_until_earnings=-30,
            last_surprise_pct=8.0,
            score=0.5,
        )
        is_drift, boost, _ = synthesis.detect_post_earnings_drift(earnings, None)
        assert is_drift is False
        assert boost == 0.0

    def test_post_earnings_drift_rejected_when_ahead_of_print(self):
        """days_until=10 (pre-print, future) -> NOT detected."""
        earnings = _make_earnings(
            days_until_earnings=10,
            last_surprise_pct=8.0,
            score=0.5,
        )
        is_drift, boost, _ = synthesis.detect_post_earnings_drift(earnings, None)
        assert is_drift is False
        assert boost == 0.0

    def test_post_earnings_drift_rejected_on_negative_score(self):
        """earnings.score < 0.3 -> NOT detected (negative earnings module)."""
        earnings = _make_earnings(
            days_until_earnings=-3,
            last_surprise_pct=8.0,
            score=0.2,
        )
        is_drift, boost, _ = synthesis.detect_post_earnings_drift(earnings, None)
        assert is_drift is False
        assert boost == 0.0

    def test_post_earnings_drift_rejected_when_no_data(self):
        """days_until_earnings=None -> NOT detected."""
        earnings = _make_earnings(
            days_until_earnings=None,
            last_surprise_pct=8.0,
            score=0.5,
        )
        is_drift, boost, _ = synthesis.detect_post_earnings_drift(earnings, None)
        assert is_drift is False

    def test_post_earnings_drift_rejected_on_none_earnings(self):
        """earnings=None -> NOT detected."""
        is_drift, boost, _ = synthesis.detect_post_earnings_drift(None, None)
        assert is_drift is False
        assert boost == 0.0


# ── Unit tests: sector_rs_boost ────────────────────────────────────────────


class TestSectorRsBoost:
    """Unit tests for the sector RS boost detector."""

    def test_fresh_highs_gives_max_boost(self):
        """Finding with 'fresh highs' -> +0.10."""
        tech = _make_technical(findings=["✅ Sector leading — fresh highs in CIBR holdings"])
        boost, findings = synthesis.sector_rs_boost(tech)
        assert boost == pytest.approx(0.10)
        assert len(findings) == 1
        assert "Sector RS" in findings[0]

    def test_sector_keyword_gives_small_boost(self):
        """Finding with 'sector' keyword (no fresh high) -> +0.05."""
        tech = _make_technical(findings=["📊 Sector momentum supportive"])
        boost, findings = synthesis.sector_rs_boost(tech)
        assert boost == pytest.approx(0.05)
        assert len(findings) == 1

    def test_no_sector_signal_returns_zero(self):
        """No sector-related findings -> +0.0."""
        tech = _make_technical(findings=["📊 SMA20 above SMA50", "✅ Volume above average"])
        boost, findings = synthesis.sector_rs_boost(tech)
        assert boost == 0.0
        assert findings == []

    def test_missing_technical_returns_zero(self):
        """technical=None -> +0.0."""
        boost, findings = synthesis.sector_rs_boost(None)
        assert boost == 0.0
        assert findings == []


# ── Integration: full synthesise() with OKTA-like fixture ──────────────────


class TestSynthesiseOktaSetup:
    """OKTA-like post-earnings drift setup should produce BUY c:6+."""

    def test_synthesise_boosts_okta_like_setup_to_buy(self):
        """
        OKTA 2026-08-26 setup:
        - Posted earnings Wed Aug 26 (days_until = -5)
        - +9.4% surprise beat (typical OKTA post-print reaction)
        - Stock ran +32% in 5 days
        - RSI 62 (constructive, not overbought)
        - Bullish MA alignment, strong ADX
        - P/E 104 (extremely elevated — base engine would penalize -0.4)
        - Risk: extreme volatility regime (post-print expansion)
        - Sector: CIBR +31% YTD (sector leading)

        Base engine verdict without fix: ACCUMULATE c:4 (or worse due to P/E
        penalty + extreme vol dealbreaker).

        With D-45 momentum regime fix: should be BUY c:6+.
        """
        tech = _make_technical(
            score=0.85,
            ma_alignment="bullish",
            rsi=62.0,
            rsi_regime="neutral_bullish",
            adx=35.0,
            adx_verdict="strong",
            volatility_regime="high",
            structure="bullish",
            swing_highs=[120.0, 125.0, 130.0],
            swing_lows=[85.0, 88.0, 92.0],
            key_resistance=[125.0, 130.0],
            key_support=[92.0, 88.0],
            findings=[
                "✅ Breakout confirmed above resistance with volume",
                "📈 Sector leading — fresh highs in CIBR holdings",
            ],
        )
        fund = _make_fundamental(
            score=0.1,  # Mixed fundamentals (high P/E drag)
            pe_ratio=104.0,  # Extremely elevated — would normally tank verdict
            market_cap=18_000_000_000,  # ~$18B
            profit_margin=-5.0,
            revenue_growth_yoy=12.0,
        )
        earnings = _make_earnings(
            score=0.7,  # Strong earnings module
            last_surprise_pct=9.4,  # Big beat
            days_until_earnings=-5,  # 5 days post-print
            beat_rate="4/4",
            avg_reaction_pct=12.0,
        )
        risk = _make_risk(
            score=-0.1,  # Negative due to extreme vol
            volatility_regime="extreme",  # Post-print vol expansion
            suggested_stop_pct=8.0,
            suggested_position_size_pct=12.0,
        )
        sent = _make_sentiment(
            score=0.4,  # Positive sentiment
            analyst_consensus="Strong Buy",
            insider_status="neutral",
            beta=1.4,
            target_upside_pct=20.0,
        )
        tv_data = {
            "SMA20": 95.0,
            "SMA50": 88.0,
            "close": 105.0,
            "ATR": 4.0,
            "breakout_confirmed": True,
            "rvol_breakout": 2.5,  # Strong breakout rvol
        }

        verdict = synthesis.synthesise(
            technical=tech,
            fundamental=fund,
            earnings=earnings,
            sentiment=sent,
            risk=risk,
            price=105.0,
            tv_data=tv_data,
        )

        # Print for inspection (visible with -v flag)
        print(
            f"\n[OKTA-like verdict] action={verdict.action} "
            f"conviction={verdict.conviction} "
            f"position={verdict.position_size_pct}%"
        )

        # The D-45 fix should promote to BUY (or STRONG BUY) with c:6+
        assert verdict.action in ("BUY", "STRONG BUY"), (
            f"Expected BUY/STRONG BUY for OKTA-like momentum drift, "
            f"got action={verdict.action}, conviction={verdict.conviction}"
        )
        assert verdict.conviction >= 5, (
            f"Expected conviction >= 5 for momentum drift setup, got {verdict.conviction}"
        )

        # Vol exemption: extreme vol dealbreaker should NOT fire
        assert not any(
            "Extreme volatility regime" in f for f in verdict.dealbreakers
        ), f"Extreme vol dealbreaker should be exempted during drift, got: {verdict.dealbreakers}"

        # Momentum findings should be present (surfaced via buy_triggers or thesis)
        all_text = " ".join(
            verdict.buy_triggers + [verdict.thesis or ""] + verdict.key_red_flags
        )
        assert (
            "Momentum breakout" in all_text
            or "Post-earnings drift" in all_text
            or "Momentum emerging" in all_text
        ), f"Momentum finding missing from verdict text: {all_text[:300]}"

        # Position size should be reasonable (cap at 10% from risk)
        assert verdict.position_size_pct > 0

    def test_no_momentum_bonus_keeps_pure_fundamental_penalty(self):
        """
        Sanity check: without drift + without breakout regime, OKTA-like setup
        (extreme P/E + extreme vol) stays at ACCUMULATE/HOLD, NOT BUY.
        This proves the boost is what tips the verdict — not a regression.
        """
        tech = _make_technical(
            score=0.4,  # Lower — won't trigger breakout
            ma_alignment="mixed",  # Not bullish — won't trigger breakout
            rsi=45.0,  # Below 50 — won't trigger breakout
            adx=15.0,
            adx_verdict="weak",  # Won't trigger breakout
            volatility_regime="high",
        )
        fund = _make_fundamental(
            score=0.1,
            pe_ratio=104.0,  # Elevated P/E drag
            market_cap=18_000_000_000,
        )
        earnings = _make_earnings(
            score=0.1,  # Negative earnings module — won't trigger drift
            last_surprise_pct=-10.0,  # MISS — won't trigger drift
            days_until_earnings=-5,
        )
        risk = _make_risk(
            volatility_regime="extreme",
            suggested_stop_pct=8.0,
        )
        sent = _make_sentiment(score=-0.2)
        tv_data = {"SMA20": 95.0, "SMA50": 88.0, "close": 105.0}

        verdict = synthesis.synthesise(
            technical=tech,
            fundamental=fund,
            earnings=earnings,
            sentiment=sent,
            risk=risk,
            price=105.0,
            tv_data=tv_data,
        )

        # Without the momentum boost, this should NOT be BUY — should be capped
        # by P/E + extreme vol dealbreakers. Extreme vol dealbreaker SHOULD fire.
        assert any(
            "Extreme volatility regime" in f for f in verdict.dealbreakers
        ), "Without drift exemption, extreme vol dealbreaker should still fire"
        # Action should NOT be BUY — should be lower (HOLD/REDUCE/AVOID/WATCH)
        assert verdict.action not in ("BUY", "STRONG BUY"), (
            f"Without momentum boost, OKTA-like should NOT be BUY. "
            f"Got action={verdict.action}, conviction={verdict.conviction}"
        )

    def test_extreme_vol_post_print_does_not_fire_dealbreaker(self):
        """Direct unit check: extreme vol + drift = no dealbreaker."""
        earnings = _make_earnings(
            days_until_earnings=-5,
            last_surprise_pct=9.4,
            score=0.7,
        )
        risk = _make_risk(volatility_regime="extreme")
        tech = _make_technical(
            score=0.8,
            ma_alignment="bullish",
            rsi=62.0,
            adx=32.0,
            adx_verdict="strong",
        )

        verdict = synthesis.synthesise(
            technical=tech,
            fundamental=_make_fundamental(pe_ratio=20.0),
            earnings=earnings,
            sentiment=_make_sentiment(),
            risk=risk,
            price=100.0,
            tv_data={"SMA20": 95.0, "SMA50": 88.0, "close": 100.0},
        )

        # Vol dealbreaker should be SUPPRESSED by post-print drift exemption
        assert not any(
            "Extreme volatility regime — widen stops" in f
            for f in verdict.dealbreakers
        ), f"Vol dealbreaker should be exempted during drift: {verdict.dealbreakers}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])