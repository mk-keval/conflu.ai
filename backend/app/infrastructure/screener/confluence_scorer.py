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


class TVConfluenceScorer:
    """
    Scores tickers using ONLY TV Screener data (no OHLCV needed).
    Returns entry, exit, stop_loss, confluence_score from TV columns.
    """

    def score(self, row: pd.Series, config: Any = None, direction: str = "long") -> ConfluenceScore:
        """
        Score a single ticker from TV Screener row data.

        Args:
            row: Single row from TV Screener result (contains ALL TV columns)
            config: Optional ScreenConfig for filter-specific weighting
            direction: "long" (default) or "short". When "short", inverts the
                sign of directional factors (EMA distance, RSI, MACD, VWAP)
                so bearish setups score high instead of low.

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
            elif rsi > 53:
                mom_score += 5   # Cusp of momentum (bridge 3→7)
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
            vol_score += 4   # Intermediate bracket to smooth 1.2→1.5 cliff
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
        # ADX > 45 means the trend is already very extended — increases confidence
        # but makes for a later entry. Give it the top score for reliability
        # but add a trend initiation bonus for the 25-35 zone.
        # ADX — reward 25-35 (trend initiation sweet spot) highest,
        # penalize extremely extended trends (>45)
        if adx > 45:
            qual_score += 4   # Very extended trend — reliable but late entry
        elif adx > 35:
            qual_score += 6   # Established trend, still tradeable
        elif adx > 25:
            qual_score += 8   # Trend initiation sweet spot — highest score
        elif adx > 20:
            qual_score += 4   # Weak trend beginning
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

        total = sum(scores.values())

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

        return ConfluenceScore(
            total=total,
            breakdown=scores,
            entry=entry,
            stop_loss=stop_loss,
            targets=[target_1, target_2],
            risk_reward=risk_reward,
            rating=self._rating(total),
        )

    def _rating(self, score: int) -> str:
        if score >= 80: return "A+"
        if score >= 70: return "A"
        if score >= 60: return "B+"
        if score >= 50: return "B"
        if score >= 40: return "C"
        return "D"