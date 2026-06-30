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
        # Sub-factors: distance above EMAs graded (0-20), EMA alignment graded (0-10)
        # Old code: binary checks (close > EMA = +10). No differentiation between
        # a stock barely above its EMA vs one 30% above. Now graded by percentage distance.
        trend_score = 0
        close = row.get("close", 0)
        ema200 = row.get("EMA200", 0)
        ema50 = row.get("EMA50", 0)
        ema20 = row.get("EMA20", 0)

        # Distance above EMA200 (0-10 pts)
        if ema200 and close > ema200:
            pct_above = (close - ema200) / ema200 * 100
            if pct_above > 20:
                trend_score += 10   # Deep in secular uptrend
            elif pct_above > 10:
                trend_score += 8
            elif pct_above > 5:
                trend_score += 6
            else:
                trend_score += 4    # Barely above

        # Distance above EMA50 (0-10 pts)
        if ema50 and close > ema50:
            pct_above = (close - ema50) / ema50 * 100
            if pct_above > 15:
                trend_score += 10   # Strong intermediate trend
            elif pct_above > 8:
                trend_score += 8
            elif pct_above > 3:
                trend_score += 6
            else:
                trend_score += 4    # Barely above

        # EMA alignment (EMA20 > EMA50), graded (0-10 pts)
        if ema20 and ema50:
            alignment_pct = (ema20 - ema50) / ema50 * 100
            if ema20 > ema50:
                if alignment_pct > 3:
                    trend_score += 10   # Strong bullish alignment, steep
                elif alignment_pct > 1:
                    trend_score += 7    # Moderate alignment
                else:
                    trend_score += 4    # Barely aligned — flat EMAs
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
        # Sub-factors: relative volume graded (0-10), volume change graded (0-5), VWAP graded (0-5)
        # Old code: binary rel_vol > 1.5 (+10) rewarded 1.51 the same as 10.0.
        # Binary vol_change > 0 (+5) was nearly always true for trending stocks — useless signal.
        vol_score = 0
        rel_vol = row.get("relative_volume_10d_calc", 1.0)
        vol_change = row.get("volume_change", 0)
        vwap = row.get("VWAP", 0)
        close_val = row.get("close", 0)

        # Relative volume graded (0-10 pts)
        if rel_vol > 3.0:
            vol_score += 10   # Massive volume surge
        elif rel_vol > 2.0:
            vol_score += 8    # Strong volume
        elif rel_vol > 1.5:
            vol_score += 6    # Above average
        elif rel_vol > 1.2:
            vol_score += 3    # Slight increase
        elif rel_vol > 1.0:
            vol_score += 1    # Barely above normal

        # Volume change graded (0-5 pts)
        # vol_change = daily volume % change (e.g., 150 = +150%)
        if vol_change > 100:
            vol_score += 5    # Volume doubled
        elif vol_change > 50:
            vol_score += 3    # Significant increase
        elif vol_change > 20:
            vol_score += 2    # Moderate increase
        elif vol_change > 0:
            vol_score += 1    # Minimal increase

        # VWAP position graded (0-5 pts)
        if vwap and close_val > vwap:
            pct_above = (close_val - vwap) / vwap * 100
            if pct_above > 3:
                vol_score += 5   # Strongly above VWAP — aggressive buying
            elif pct_above > 1:
                vol_score += 3   # Moderately above
            else:
                vol_score += 1   # Barely above — noise level
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
        # Sub-factors: analyst rating graded (0-4), market cap tiered (0-3), EPS strength (0-3)
        # Old code: StrongBuy/Buy = +5 (no distinction), mcap > $10B = +3 (binary),
        # EPS > 0 = +2 (binary — $0.01 same as $100). Zero differentiation.
        fund_score = 0
        analyst = row.get("AnalystRating", "")
        mcap = row.get("market_cap_basic", 0)
        eps = row.get("earnings_per_share_diluted_ttm", 0)

        # Analyst rating graded (0-4 pts)
        if analyst in ["StrongBuy"]:
            fund_score += 4   # Strong institutional conviction
        elif analyst in ["Buy"]:
            fund_score += 3
        elif analyst in ["Outperform", "Overweight"]:
            fund_score += 2
        elif analyst in ["Hold", "Neutral"]:
            fund_score += 1   # Neutral but not negative
        # Sell/StrongSell/Underperform = 0

        # Market cap tiers (0-3 pts) — larger = more stable, institutional-grade
        if mcap > 200_000_000_000:
            fund_score += 3   # Mega cap — most stable
        elif mcap > 10_000_000_000:
            fund_score += 2   # Large cap
        elif mcap > 2_000_000_000:
            fund_score += 1   # Mid cap
        # Small/micro cap = 0

        # EPS strength (0-3 pts)
        if eps > 10:
            fund_score += 3   # Highly profitable
        elif eps > 2:
            fund_score += 2   # Solidly profitable
        elif eps > 0:
            fund_score += 1   # Barely profitable
        # Negative EPS = 0
        scores["fundamental"] = fund_score

        total = sum(scores.values())

        # ENTRY/EXIT/SL from TV data — volatility regime adaptive
        # ATR% of price determines volatility regime: low (<1%), normal (1-3%), high (>3%).
        # In low vol: tighter stops (1.5 ATR) so stops sit closer to price action.
        # In high vol: wider stops (3 ATR) to avoid noise-driven stop-outs.
        # Target multiples scale proportionally to maintain consistent R:R.
        atr = row.get("ATR", 0)
        close_val = row.get("close", 0)
        
        if atr and close_val:
            entry = close_val
            atr_pct = (atr / close_val) * 100

            if atr_pct < 1.0:
                # Low volatility regime — tighter stops, conservative targets
                stop_mult = 1.5
                target_mult_1 = 1.5
                target_mult_2 = 2.5
            elif atr_pct > 3.0:
                # High volatility regime — wider stops, extended targets
                stop_mult = 3.0
                target_mult_1 = 3.0
                target_mult_2 = 4.5
            else:
                # Normal volatility regime — standard 2-3 ATR
                stop_mult = 2.0
                target_mult_1 = 2.0
                target_mult_2 = 3.0

            stop_loss = close_val - (stop_mult * atr)
            target_1 = close_val + (target_mult_1 * atr)
            target_2 = close_val + (target_mult_2 * atr)
            risk_reward = round(target_mult_1 / stop_mult, 2)
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