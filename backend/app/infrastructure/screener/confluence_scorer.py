# Confluence Scorer — Scores tickers using ONLY TV Screener data (no OHLCV needed)
"""
Scores tickers from TV Screener raw data using multi-factor confluence:
- Trend Confluence (0-30 pts)
- Momentum Confluence (0-25 pts)
- Volume Confluence (0-20 pts)
- Volatility/Quality (0-15 pts)
- Fundamental Backdrop (0-10 pts)

Total: 0-100 pts → A+/A/B+/B/C/D rating
Generates entry, stop_loss, targets from ATR
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import pandas as pd


@dataclass
class ConfluenceScore:
    total: int
    breakdown: dict[str, int]
    entry: float
    stop_loss: float
    targets: list[float]
    risk_reward: float
    rating: str
    rationale: list[str] | None = None
    regime_adjusted_total: int | None = None  # Set when regime-adaptive scoring used
    rs_rating: int | None = None  # Relative strength percentile (0-100)
    regime: str | None = None  # Market regime used for weighting


class TVConfluenceScorer:
    """
    Scores tickers using ONLY TV Screener data (no OHLCV needed).
    Returns entry, exit, stop_loss, confluence_score from TV columns.

    Supports regime-adaptive weighting: when `regime` is passed, each
    factor is normalised to 0-100 and weighted per market regime.
    When omitted, the original fixed-range scoring is used (backward
    compatible).
    """

    # Regime-adaptive weight maps (factor → weight as percentage of total)
    # Each factor is scored 0-100, then weighted by these percentages.
    # Designed from elite-trader research: factor importance shifts
    # dramatically across market regimes.
    REGIME_WEIGHTS: dict[str, dict[str, int]] = {
        # Strong trend (ADX > 25, price > EMA200): trend + momentum dominate
        "strong_trend": {
            "trend": 40, "momentum": 30, "volume": 15, "quality": 10, "fundamental": 5,
        },
        # Ranging / choppy (ADX < 20, BB narrow): volume + quality matter most
        "ranging": {
            "trend": 15, "momentum": 20, "volume": 25, "quality": 25, "fundamental": 15,
        },
        # High vol / crisis (VIX > 30, ATR% > 3%): volume confirms, quality protects
        "high_vol": {
            "trend": 20, "momentum": 15, "volume": 30, "quality": 25, "fundamental": 10,
        },
        # Low vol / complacency (VIX < 15, ATR% < 1%): momentum leads, trend steady
        "low_vol": {
            "trend": 25, "momentum": 25, "volume": 15, "quality": 20, "fundamental": 15,
        },
    }

    def score(
        self,
        row: pd.Series,
        config: Any = None,
        direction: str = "long",
        regime: str | None = None,
        rs_rating: int | None = None,
    ) -> ConfluenceScore:
        """
        Score a single ticker from TV Screener row data.

        Args:
            row: Single row from TV Screener result (contains ALL TV columns)
            config: Optional ScreenConfig for filter-specific weighting
            direction: "long" (default) or "short". When "short", inverts the
                sign of directional factors (EMA distance, RSI, MACD, VWAP)
                so bearish setups score high instead of low.
            regime: Optional market regime for adaptive weighting.
                One of: "strong_trend", "ranging", "high_vol", "low_vol".
                When None, uses original fixed-range scoring (backward compat).
            rs_rating: Optional relative strength rating (0-100) from
                post-TV processing. Boosts the momentum factor when present.

        Returns:
            ConfluenceScore with entry, stop_loss, targets, rating
        """
        is_long = direction == "long"
        scores = {}

        # 1. TREND CONFLUENCE (0-30 pts)
        # In long mode: distance ABOVE EMAs = points.
        # In short mode: distance BELOW EMAs = points (mirror image).
        # Thresholds are calibrated for swing trading (2d-2wk holds):
        #   - EMA200 sweet spot is 5-15% above (not >20% which is extended)
        #   - EMA50 sweet spot is 3-8% above
        trend_score = 0
        close = row.get("close", 0)
        ema200 = row.get("EMA200", 0)
        ema50 = row.get("EMA50", 0)
        ema20 = row.get("EMA20", 0)

        if ema200:
            if is_long and close > ema200:
                pct = (close - ema200) / ema200 * 100
                # Bell curve: sweet spot 5-15%, penalize extended
                if pct > 15:
                    trend_score += 8   # Extended, still trending but risky
                elif pct > 10:
                    trend_score += 10  # Sweet spot for swing entries
                elif pct > 5:
                    trend_score += 8
                elif pct > 2:
                    trend_score += 4
            elif not is_long and close < ema200:
                pct = (ema200 - close) / ema200 * 100
                if pct > 15:
                    trend_score += 8   # Deep breakdown, may be exhausted
                elif pct > 10:
                    trend_score += 10  # Sweet spot for short entries
                elif pct > 5:
                    trend_score += 8
                elif pct > 2:
                    trend_score += 4

        if ema50:
            if is_long and close > ema50:
                pct = (close - ema50) / ema50 * 100
                # Sweet spot 3-8% for swing entries, >8% is extended
                if pct > 8:
                    trend_score += 8   # Extended above EMA50
                elif pct > 5:
                    trend_score += 10  # Sweet spot
                elif pct > 2:
                    trend_score += 6
                elif pct > 1:
                    trend_score += 4
            elif not is_long and close < ema50:
                pct = (ema50 - close) / ema50 * 100
                if pct > 8:
                    trend_score += 8   # Extended below EMA50
                elif pct > 5:
                    trend_score += 10  # Sweet spot for short
                elif pct > 2:
                    trend_score += 6
                elif pct > 1:
                    trend_score += 4

        # EMA alignment (long: EMA20 > EMA50, short: EMA20 < EMA50), graded (0-10 pts)
        if ema20 and ema50:
            if is_long and ema20 > ema50:
                spread = (ema20 - ema50) / ema50 * 100
                trend_score += 10 if spread > 3 else (7 if spread > 1 else 4)
            elif not is_long and ema20 < ema50:
                spread = (ema50 - ema20) / ema50 * 100
                trend_score += 10 if spread > 3 else (7 if spread > 1 else 4)
        scores["trend"] = trend_score

        # 2. MOMENTUM CONFLUENCE (0-25 pts)
        # Long: MACD > signal, RSI 55-75 sweet spot.
        # Short: MACD < signal, RSI 25-45 sweet spot.
        mom_score = 0
        macd = row.get("MACD.macd", 0)
        macd_signal = row.get("MACD.signal", 0)
        rsi = row.get("RSI", 50)

        # MACD direction + spread strength (0-10 pts)
        macd_aligned = (macd > macd_signal) if is_long else (macd < macd_signal)
        if macd_aligned:
            mom_score += 5  # Base directional alignment
            spread = abs(macd - macd_signal)
            spread_ratio = spread / (abs(macd_signal) + 1e-9)
            if spread_ratio > 1.0:
                mom_score += 5  # Strong acceleration
            elif spread_ratio > 0.5:
                mom_score += 3  # Moderate acceleration
            else:
                mom_score += 1  # Barely positive

        # RSI graded (0-12 pts) — direction-aware sweet spot
        if is_long:
            if rsi > 90:
                mom_score += 1   # Extreme overbought
            elif rsi > 80:
                mom_score += 3   # Extended
            elif rsi > 75:
                mom_score += 5   # Late stage
            elif rsi > 65:
                mom_score += 10  # Sweet spot: 66-75
            elif rsi > 55:
                mom_score += 7   # Building momentum
            elif rsi > 54:
                mom_score += 6   # Nearing sweet spot (smooth bridge 5→7)
            elif rsi > 53:
                mom_score += 5   # Cusp of momentum
            elif rsi > 50:
                mom_score += 3   # Weak bullish
        else:
            # Short mode: reverse the scale
            if rsi < 10:
                mom_score += 1   # Extreme oversold — bounce risk
            elif rsi < 20:
                mom_score += 3   # Deep oversold
            elif rsi < 25:
                mom_score += 5   # Very weak
            elif rsi < 35:
                mom_score += 10  # Sweet spot: 25-34
            elif rsi < 45:
                mom_score += 7   # Weak momentum
            elif rsi < 47:
                mom_score += 5   # Cusp of weakness (bridge 3→7)
            elif rsi < 50:
                mom_score += 3   # Just below neutral

        # RSI-MACD confluence bonus (0-3 pts)
        rsi_aligned = (rsi > 50) if is_long else (rsi < 50)
        if rsi_aligned and macd_aligned:
            mom_score += 3
        scores["momentum"] = mom_score

        # 3. VOLUME CONFLUENCE (0-20 pts)
        # Volume factors are direction-agnostic (volume confirms move in either direction)
        # EXCEPT VWAP: long rewards above VWAP, short rewards below VWAP.
        vol_score = 0
        rel_vol = row.get("relative_volume_10d_calc", 1.0)
        vol_change = row.get("volume_change", 0)
        vwap = row.get("VWAP", 0)
        close_val = row.get("close", 0)

        # Relative volume graded (0-10 pts) — direction-agnostic
        if rel_vol > 3.0:
            vol_score += 10
        elif rel_vol > 2.0:
            vol_score += 8
        elif rel_vol > 1.5:
            vol_score += 6
        elif rel_vol > 1.35:
            vol_score += 5   # Moderate volume pickup (bridges 3→6 smoothly)
        elif rel_vol > 1.2:
            vol_score += 3
        elif rel_vol > 1.0:
            vol_score += 1

        # Volume change graded (0-5 pts) — direction-agnostic
        if vol_change > 100:
            vol_score += 5   # Volume doubling — strongest signal
        elif vol_change > 75:
            vol_score += 4   # Near doubling — strong confirmation
        elif vol_change > 50:
            vol_score += 3   # Significant volume pickup
        elif vol_change > 20:
            vol_score += 2
        elif vol_change > 0:
            vol_score += 1

        # VWAP position (0-5 pts) — direction-aware
        if vwap and close_val:
            if is_long and close_val > vwap:
                pct = (close_val - vwap) / vwap * 100
                if pct > 3:
                    vol_score += 5
                elif pct > 1:
                    vol_score += 3
                else:
                    vol_score += 1
            elif not is_long and close_val < vwap:
                pct = (vwap - close_val) / vwap * 100
                if pct > 3:
                    vol_score += 5
                elif pct > 1:
                    vol_score += 3
                else:
                    vol_score += 1
        scores["volume"] = vol_score

        # 4. VOLATILITY/QUALITY (0-15 pts)
        # Direction-agnostic (trend quality benefits both longs and shorts).
        # ADX measures trend STRENGTH, not direction — same for long/short.
        # BB squeeze = volatility contraction = big move coming (either direction).
        qual_score = 0
        adx = row.get("ADX", 0)
        bb_upper = row.get("BB.upper", 0)
        bb_lower = row.get("BB.lower", 0)
        atr = row.get("ATR", 0)
        close_val = row.get("close", 0)

        # ADX graded + trend initiation bonus (0-10 pts)
        # ADX 25-35 is the sweet spot for swing entries (trend initiating).
        # ADX 20-25 is the transition zone where a trend is forming — score it
        # high enough to catch early entries before the crowd piles in.
        # ADX > 45 means the trend is extended — reliable but late entry.
        if adx > 45:
            qual_score += 4   # Very extended trend — reliable but late entry
        elif adx > 35:
            qual_score += 6   # Established trend, still tradeable
        elif adx > 25:
            qual_score += 8   # Trend initiation sweet spot — highest score
        elif adx > 20:
            qual_score += 6   # Trend forming transition zone (was 4)
        elif adx > 15:
            qual_score += 2   # Very early

        # BB squeeze (0-5 pts, down from 7 — rebalanced since total is 0-15)
        if bb_upper and bb_lower and close_val:
            bb_width = bb_upper - bb_lower
            if bb_width > 0:
                bb_pct = (bb_width / close_val) * 100
                if bb_pct < 2.0:
                    qual_score += 5   # Tight squeeze
                elif bb_pct < 3.5:
                    qual_score += 3   # Moderate squeeze
                elif adx and adx > 25:
                    qual_score += 2   # Wide bands but trending strongly
        scores["quality"] = qual_score

        # 5. FUNDAMENTAL BACKDROP (0-10 pts)
        # Direction-agnostic (company quality is the same regardless of trade direction)
        fund_score = 0
        analyst = row.get("AnalystRating", "")
        mcap = row.get("market_cap_basic", 0)
        eps = row.get("earnings_per_share_diluted_ttm", 0)

        if analyst in ["StrongBuy"]:
            fund_score += 4
        elif analyst in ["Buy"]:
            fund_score += 3
        elif analyst in ["Outperform", "Overweight"]:
            fund_score += 2
        elif analyst in ["Hold", "Neutral"]:
            fund_score += 1

        if mcap > 200_000_000_000:
            fund_score += 3
        elif mcap > 10_000_000_000:
            fund_score += 2
        elif mcap > 2_000_000_000:
            fund_score += 1

        if eps > 10:
            fund_score += 3
        elif eps > 2:
            fund_score += 2
        elif eps > 0:
            fund_score += 1
        scores["fundamental"] = fund_score

        # ── Apply regime-adaptive weighting when regime is provided ──
        # Each factor is normalised to 0-100, then multiplied by its regime weight.
        # This prevents trend-following weights in choppy markets (and vice versa).
        raw_total = sum(scores.values())
        regime_total: int | None = None
        active_regime: str | None = None

        if regime and regime in self.REGIME_WEIGHTS:
            active_regime = regime
            weights = self.REGIME_WEIGHTS[regime]

            # Normalise each factor to 0-100 scale
            factor_max = {
                "trend": 30, "momentum": 25, "volume": 20,
                "quality": 15, "fundamental": 10,
            }
            pcts: dict[str, float] = {}
            for factor, raw_score in scores.items():
                mx = factor_max.get(factor, 1)
                pcts[factor] = min(100.0, (raw_score / mx) * 100.0)

            # Boost momentum by RS rating when available (max +15%)
            if rs_rating is not None and "momentum" in pcts:
                rs_bonus = min(15, rs_rating * 0.15)
                pcts["momentum"] = min(100, pcts["momentum"] + rs_bonus)

            # Weighted total with applied percentages
            regime_total = int(round(
                sum(pcts[f] * weights.get(f, 0) / 100.0 for f in pcts)
            ))

        # Choose the display total: regime-adjusted wins if available
        total = regime_total if regime_total is not None else raw_total

        # ENTRY/EXIT/SL from TV data — volatility regime adaptive + direction aware
        # ATR% of price determines volatility regime: low (<1%), normal (1-3%), high (>3%).
        # First target R:R is asymmetric: T1 offers ~1.5x the stop distance so swing
        # traders get meaningful reward for the risk taken.
        atr = row.get("ATR", 0)
        close_val = row.get("close", 0)

        if atr and close_val:
            entry = close_val
            atr_pct = (atr / close_val) * 100

            if atr_pct < 1.0:
                stop_mult = 1.5
                target_mult_1 = 2.5   # R:R = 1.67 for T1
                target_mult_2 = 3.5
            elif atr_pct > 3.0:
                stop_mult = 3.0
                target_mult_1 = 5.0   # R:R = 1.67 for T1
                target_mult_2 = 7.0
            else:
                stop_mult = 2.0
                target_mult_1 = 3.0   # R:R = 1.5 for T1
                target_mult_2 = 4.5

            if is_long:
                stop_loss = close_val - (stop_mult * atr)
                target_1 = close_val + (target_mult_1 * atr)
                target_2 = close_val + (target_mult_2 * atr)
            else:
                stop_loss = close_val + (stop_mult * atr)
                target_1 = close_val - (target_mult_1 * atr)
                target_2 = close_val - (target_mult_2 * atr)
            risk_reward = round(target_mult_1 / stop_mult, 2)
        else:
            entry = close_val
            stop_loss = close_val * (0.95 if is_long else 1.05)
            target_1 = close_val * (1.05 if is_long else 0.95)
            target_2 = close_val * (1.10 if is_long else 0.90)
            risk_reward = 1.0

        rationale = self.generate_rationale(scores)

        # Add RS-based rationale when available
        if rs_rating is not None:
            if rs_rating >= 80:
                rationale.append(f"Elite RS rating ({rs_rating}) — top-quartile relative strength vs peers")
            elif rs_rating >= 60:
                rationale.append(f"Strong RS rating ({rs_rating}) — above-median relative strength")
            elif rs_rating >= 40:
                rationale.append(f"Moderate RS rating ({rs_rating}) — inline with sector peers")
            else:
                rationale.append(f"Weak RS rating ({rs_rating}) — lagging sector peers")

        # Add regime-awareness insight
        if active_regime:
            rationale.append(
                f"Weights adapted for {active_regime.replace('_', ' ')} regime"
            )

        return ConfluenceScore(
            total=total,
            breakdown=scores,
            entry=entry,
            stop_loss=stop_loss,
            targets=[target_1, target_2],
            risk_reward=risk_reward,
            rating=self._rating(total),
            rationale=rationale,
            regime_adjusted_total=regime_total,
            rs_rating=rs_rating,
            regime=active_regime,
        )

    def generate_rationale(self, scores: dict[str, int]) -> list[str]:
        """Return a list of human-readable reasoning points for the score breakdown.

        Each factor maps its score bracket to a compact explanation so users
        understand *why* a ticker scored the way it did.
        """
        reasons = []

        # Trend
        t = scores.get("trend", 0)
        if t >= 25:
            reasons.append("Strong trend alignment — price well above EMAs with bullish stacking")
        elif t >= 15:
            reasons.append("Moderate trend support — above key EMAs, alignment mixed")
        elif t >= 8:
            reasons.append("Weak trend — price near EMAs, no clear direction")
        else:
            reasons.append("No trend confirmation — price below key EMAs")

        # Momentum
        m = scores.get("momentum", 0)
        if m >= 20:
            reasons.append("Strong momentum — MACD accelerating, RSI in sweet spot (55-75)")
        elif m >= 12:
            reasons.append("Good momentum — RSI building, MACD directionally aligned")
        elif m >= 6:
            reasons.append("Moderate momentum — early signs, needs price confirmation")
        else:
            reasons.append("Weak momentum — RSI neutral or MACD crossing")

        # Volume
        v = scores.get("volume", 0)
        if v >= 16:
            reasons.append("Strong volume — well above average with VWAP confirmation")
        elif v >= 10:
            reasons.append("Good volume — above-average participation supporting the move")
        elif v >= 5:
            reasons.append("Moderate volume — some interest, but needs stronger confirmation")
        else:
            reasons.append("Low volume — weak participation, move lacks conviction")

        # Quality
        q = scores.get("quality", 0)
        if q >= 12:
            reasons.append("High quality — ADX confirms strong, healthy trend")
        elif q >= 7:
            reasons.append("Decent quality — measurable trend via ADX")
        elif q >= 3:
            reasons.append("Low quality — ADX below trending threshold")
        else:
            reasons.append("Poor quality — no measurable trend strength")

        # Fundamental
        f = scores.get("fundamental", 0)
        if f >= 8:
            reasons.append("Strong fundamentals — analyst upgrades, large-cap stability")
        elif f >= 5:
            reasons.append("Solid fundamentals — institutional-grade market cap")
        elif f >= 3:
            reasons.append("Moderate fundamentals — small-cap or neutral analyst views")
        else:
            reasons.append("Weak/no fundamental data available")

        return reasons

    def _rating(self, score: int) -> str:
        if score >= 80: return "A+"
        if score >= 70: return "A"
        if score >= 60: return "B+"
        if score >= 50: return "B"
        if score >= 40: return "C"
        return "D"