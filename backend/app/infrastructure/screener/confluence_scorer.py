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
        mom_score = 0
        macd = row.get("MACD.macd", 0)
        macd_signal = row.get("MACD.signal", 0)
        macd_hist = row.get("MACD.hist", 0)
        rsi = row.get("RSI", 50)
        
        if macd > macd_signal:
            mom_score += 10
        if macd_hist > 0:
            mom_score += 5
        if 50 < rsi < 70:
            mom_score += 10
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
        
        if adx > 25:
            qual_score += 8
        if bb_upper and bb_lower and close_val:
            # BB width as % of price  (BB.width is not a TV column, compute from upper/lower)
            bb_width = bb_upper - bb_lower
            if bb_width > 0:
                bb_pct = (bb_width / close_val) * 100
                if bb_pct < 5:  # Squeeze
                    qual_score += 7
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