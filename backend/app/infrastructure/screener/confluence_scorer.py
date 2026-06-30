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

    def score(self, row: pd.Series, config: Any = None) -> ConfluenceScore:
        """
        Score a single ticker from TV Screener row data.
        
        Args:
            row: Single row from TV Screener result (contains ALL TV columns)
            config: Optional ScreenConfig for filter-specific weighting
            
        Returns:
            ConfluenceScore with entry, stop_loss, targets, rating
        """
        scores = {}

        # 1. TREND CONFLUENCE (0-30 pts)
        trend_score = 0
        if row.get("close", 0) > row.get("EMA200", 0):
            trend_score += 10
        if row.get("close", 0) > row.get("EMA50", 0):
            trend_score += 10
        if row.get("EMA20", 0) > row.get("EMA50", 0):
            trend_score += 10
        scores["trend"] = trend_score

        # 2. MOMENTUM CONFLUENCE (0-25 pts)
        # Sub-factors: MACD direction + spread (0-10), RSI graded (0-12), RSI-MACD confluence (0-3)
        mom_score = 0
        macd = row.get("MACD.macd", 0)
        macd_signal = row.get("MACD.signal", 0)
        rsi = row.get("RSI", 50)
        
        # MACD direction + spread strength (0-10 pts)
        # Replaces old binary macd > signal (+10) + macd_hist > 0 (+5) check.
        # macd_hist > 0 was redundant: it's almost always true when MACD > signal.
        # Spread ratio (macd - signal) / signal measures histogram strength directly.
        if macd > macd_signal:
            mom_score += 5  # Base directional alignment
            spread = macd - macd_signal
            spread_ratio = spread / (abs(macd_signal) + 1e-9)
            if spread_ratio > 1.0:
                mom_score += 5  # Strong acceleration
            elif spread_ratio > 0.5:
                mom_score += 3  # Moderate acceleration
            else:
                mom_score += 1  # Barely positive
        
        # RSI graded (0-12 pts) — smooth scale, no cliff at 70
        # Old code awarded +10 for 50 < RSI < 70, then +0 for RSI >= 70.
        # This punished stocks breaking out into overbought territory.
        if rsi > 90:
            mom_score += 1   # Extreme overbought — mean reversion risk dominates
        elif rsi > 80:
            mom_score += 3   # Very extended — caution, momentum may snap
        elif rsi > 75:
            mom_score += 5   # Extended — bullish but late-stage
        elif rsi > 65:
            mom_score += 10  # Sweet spot: 66–75, strong momentum without being overbought
        elif rsi > 55:
            mom_score += 7   # Building momentum
        elif rsi > 50:
            mom_score += 3   # Just above neutral — weak bullish
        # else 0 — RSI <= 50, bearish momentum
        
        # RSI-MACD confluence bonus (0-3 pts) — both aligned = higher conviction
        if rsi > 50 and macd > macd_signal:
            mom_score += 3
        scores["momentum"] = mom_score

        # 3. VOLUME CONFLUENCE (0-20 pts)
        vol_score = 0
        rel_vol = row.get("relative_volume_10d_calc", 1.0)
        vol_change = row.get("volume_change", 0)
        vwap = row.get("VWAP", 0)
        close = row.get("close", 0)
        
        if rel_vol > 1.5:
            vol_score += 10
        if vol_change > 0:
            vol_score += 5
        if vwap and close > vwap:
            vol_score += 5
        scores["volume"] = vol_score

        # 4. VOLATILITY/QUALITY (0-15 pts)
        qual_score = 0
        adx = row.get("ADX", 0)
        bb_upper = row.get("BB.upper", 0)
        bb_lower = row.get("BB.lower", 0)
        atr = row.get("ATR", 0)
        close_val = row.get("close", 0)
        
        if adx > 45:
            qual_score += 8   # Very strong trend
        elif adx > 35:
            qual_score += 6   # Strong trend
        elif adx > 25:
            qual_score += 4   # Trending threshold
        elif adx > 20:
            qual_score += 2   # Weak trend beginning
        if bb_upper and bb_lower and close_val:
            # BB width as % of price  (BB.width is not a TV column, compute from upper/lower)
            bb_width = bb_upper - bb_lower
            if bb_width > 0:
                bb_pct = (bb_width / close_val) * 100
                if bb_pct < 2.0:
                    qual_score += 7   # Tight squeeze — breakout imminent
                elif bb_pct < 3.5:
                    qual_score += 4   # Moderate squeeze — contracting
        scores["quality"] = qual_score

        # 5. FUNDAMENTAL BACKDROP (0-10 pts)
        fund_score = 0
        analyst = row.get("AnalystRating", "")
        mcap = row.get("market_cap_basic", 0)
        eps = row.get("earnings_per_share_diluted_ttm", 0)
        
        if analyst in ["StrongBuy", "Buy"]:
            fund_score += 5
        if mcap > 10_000_000_000:
            fund_score += 3
        if eps > 0:
            fund_score += 2
        scores["fundamental"] = fund_score

        total = sum(scores.values())

        # ENTRY/EXIT/SL from TV data
        atr = row.get("ATR", 0)
        close_val = row.get("close", 0)
        
        if atr and close_val:
            entry = close_val
            stop_loss = close_val - (2 * atr)  # 2 ATR stop
            target_1 = close_val + (2 * atr)   # 1:2 R:R
            target_2 = close_val + (3 * atr)   # 1:3 R:R
            risk_reward = 2.0
        else:
            entry = close_val
            stop_loss = close_val * 0.95  # 5% fallback
            target_1 = close_val * 1.05
            target_2 = close_val * 1.10
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