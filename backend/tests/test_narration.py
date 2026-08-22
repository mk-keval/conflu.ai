"""Tests for the mentor narration layer (P2.1 + P2.2).

Deterministic reasoning chain: Why-this / Why-now / What-kills-it on every
verdict, plus trader-style thesis one-liners on brief cards.
"""

from __future__ import annotations

import pytest

from backend.app.domain.ticker_analysis.models import (
    AnalysisVerdict,
    EarningsAnalysis,
    FundamentalAnalysis,
    MentorNarration,
    SentimentAnalysis,
    TechnicalAnalysis,
    TradePlan,
)
from backend.app.domain.ticker_analysis.narration import (
    brief_thesis_line,
    build_narration,
)


def _technical(**overrides: object) -> TechnicalAnalysis:
    base: dict = {
        "score": 0.6,
        "ma_alignment": "bullish",
        "rsi": 58.0,
        "rsi_regime": "neutral",
        "adx": 28.0,
        "adx_verdict": "strong",
        "volatility_regime": "normal",
        "volume_ratio": 1.8,
        "macd_status": "bullish",
        "structure": "bullish",
        "pullback_quality": "A",
        "pullback_score": 82.0,
        "key_resistance": [320.0, 340.0],
        "findings": ["Trend intact"],
    }
    base.update(overrides)
    return TechnicalAnalysis(**base)  # type: ignore[arg-type]


def _verdict(**overrides: object) -> AnalysisVerdict:
    base: dict = {
        "action": "ACCUMULATE",
        "conviction": 7,
        "entry_zone_low": 295.0,
        "entry_zone_high": 305.0,
        "stop_loss": 282.0,
        "targets": [330.0, 355.0],
        "risk_reward": 2.4,
        "thesis": "trend continuation with volume confirmation",
    }
    base.update(overrides)
    return AnalysisVerdict(**base)  # type: ignore[arg-type]


def _earnings(**overrides: object) -> EarningsAnalysis:
    base: dict = {
        "score": 0.5,
        "last_surprise_pct": 6.1,
        "beat_rate": "3/4",
        "days_until_earnings": 9,
        "findings": [],
    }
    base.update(overrides)
    return EarningsAnalysis(**base)  # type: ignore[arg-type]


class TestWhyThis:
    def test_trend_and_pullback_surfaced(self) -> None:
        n = build_narration(
            symbol="ADBE", price=300.0, verdict=_verdict(),
            technical=_technical(), fundamental=None, earnings=None, sentiment=None,
        )
        assert any("moving averages stacked bullishly" in l for l in n.why_this)
        assert any("Pullback quality A" in l for l in n.why_this)

    def test_capped_at_four_lines(self) -> None:
        n = build_narration(
            symbol="X", price=10.0, verdict=_verdict(),
            technical=_technical(),
            fundamental=FundamentalAnalysis(score=0.5, findings=["✅ Strong growth"]),
            earnings=_earnings(), sentiment=SentimentAnalysis(score=0.5, findings=["Analysts positive"]),
        )
        assert len(n.why_this) <= 4


class TestWhyNow:
    def test_eps_beat_is_the_catalyst(self) -> None:
        n = build_narration(
            symbol="X", price=10.0, verdict=_verdict(),
            technical=_technical(), fundamental=None, earnings=_earnings(), sentiment=None,
        )
        assert any("beat by 6.1%" in l for l in n.why_now)

    def test_earnings_window_flagged(self) -> None:
        n = build_narration(
            symbol="X", price=10.0, verdict=_verdict(),
            technical=None, fundamental=None, earnings=_earnings(days_until_earnings=5), sentiment=None,
        )
        assert any("Earnings lands in 5d" in l for l in n.why_now)

    def test_no_catalyst_falls_back_to_staged_language(self) -> None:
        n = build_narration(
            symbol="X", price=10.0, verdict=_verdict(),
            technical=None, fundamental=None, earnings=None, sentiment=None,
        )
        assert any("staged setup" in l for l in n.why_now)


class TestWhatKillsIt:
    def test_names_level_and_condition(self) -> None:
        v = _verdict(trade_plan=TradePlan(max_hold_days=20))
        n = build_narration(
            symbol="X", price=300.0, verdict=v,
            technical=None, fundamental=None, earnings=None, sentiment=None,
        )
        assert any("close below 282" in k and "exit, no averaging down" in k
                   for k in n.what_kills_it)
        assert any("time stop" in k for k in n.what_kills_it)

    def test_no_plan_says_so(self) -> None:
        v = _verdict(action="WATCH", stop_loss=None, trade_plan=None)
        n = build_narration(
            symbol="X", price=10.0, verdict=v,
            technical=None, fundamental=None, earnings=None, sentiment=None,
        )
        assert any("No plan, no invalidation" in k for k in n.what_kills_it)

    def test_watch_with_levels_gets_invalidation(self) -> None:
        """Level-bearing WATCHes carry the kill-condition too (parity bar b)."""
        v = _verdict(action="WATCH")
        n = build_narration(
            symbol="X", price=300.0, verdict=v,
            technical=None, fundamental=None, earnings=None, sentiment=None,
        )
        assert any("282" in k for k in n.what_kills_it)


class TestThesisOneLiner:
    def test_contains_action_zone_rr(self) -> None:
        n = build_narration(
            symbol="ADBE", price=300.0, verdict=_verdict(),
            technical=None, fundamental=None, earnings=None, sentiment=None,
        )
        assert n.thesis_one_liner.startswith("ACCUMULATE ADBE: zone 295–305 at 2.4R")

    def test_brief_line_from_screen_data(self) -> None:
        line = brief_thesis_line(
            symbol="PD",
            verdict="BUY",
            entry=30.0,
            stop_loss=27.5,
            targets=[34.0],
            tv_data={"close": 31.0, "EMA50": 28.0, "ADX": 27.0,
                     "relative_volume_10d_calc": 1.7},
            rs_composite=84.0,
        )
        assert line.startswith("BUY PD:")
        assert "50-EMA" in line
        assert "rvol 1.7x" in line
        assert "RS percentile 84" in line
        assert "Risk from 27.5." in line

    def test_brief_line_degrades_gracefully(self) -> None:
        line = brief_thesis_line(
            symbol="XX", verdict="WATCH", entry=0.0, stop_loss=0.0,
            targets=[], tv_data={}, rs_composite=None,
        )
        assert line.startswith("WATCH XX:")
        assert "confluence-ranked setup" in line


class TestNarrationModelAdditive:
    def test_verdict_defaults_none(self) -> None:
        assert _verdict().narration is None

    def test_mentor_narration_shape(self) -> None:
        m = MentorNarration()
        assert m.why_this == [] and m.why_now == [] and m.what_kills_it == []
        assert m.thesis_one_liner == ""
