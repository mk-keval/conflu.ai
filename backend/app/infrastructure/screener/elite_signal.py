"""Elite Signal Processor — post-TV signal enrichment that adds edge TV cannot provide.

TradingView Screener returns current-snapshot data (no multi-bar history),
so true divergence detection and sequential-pattern recognition are impossible
server-side. This module bridges that gap:

1. **Relative Strength Ranking** — percentile rank vs peer universe (single most
   persistent anomaly in equity markets)
2. **Institutional Quality Score** — composite of market cap, volume consistency,
   analyst consensus, and sector positioning
3. **Factor Conflict Detection** — flags contradictory signals (e.g., bullish
   trend + bearish volume = low conviction)
4. **Wyckoff Phase Proxy** — accumulation/distribution inference from volume-price
   relationships on the snapshot
5. **Regime Signal Feed** — provides the current market regime string to the
   adaptive confluence scorer, derived from SPY ADX + VIX + sector breadth

Usage:
    processor = EliteSignalProcessor()
    enriched_df = processor.enrich(result.raw_data, direction="long", regime="strong_trend")
    # enriched_df now has columns: rs_rating, inst_quality, signal_conviction, wyckoff_phase
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from backend.app.core.logging import get_logger

log = get_logger("conflu.screener.elite_signal")


# ── Enriched ticker data model ─────────────────────────────────────────


@dataclass
class EliteSignalEnrichment:
    """Additional signal dimensions computed by the EliteSignalProcessor.

    Attached to each scored ticker alongside the ConfluenceScore.
    """
    rs_rating: int = 50              # Relative strength percentile (0-100)
    inst_quality: int = 50            # Institutional quality score (0-100)
    signal_conviction: str = "low"    # low / medium / high
    wyckoff_phase: str | None = None  # accumulation / markup / distribution / markdown / unknown
    factor_conflicts: list[str] = field(default_factory=list)
    regime: str | None = None


# ── EliteSignalProcessor ──────────────────────────────────────────────


class EliteSignalProcessor:
    """Post-TV signal enrichment: RS ranking, quality scoring, conflict detection.

    Operates entirely on TV snapshot data (no OHLCV required), making it
    suitable for the fast discovery path. For deeper analysis that requires
    historical bars, see DeepAnalysisOrchestrator.
    """

    # ── Relative Strength Ranking ─────────────────────────────────────

    def compute_rs_ratings(self, df: pd.DataFrame) -> dict[str, int]:
        """Compute relative strength percentile for each ticker in discovery results.

        Uses multi-factor RS:
        - Distance above EMA200 (trend quality)
        - RSI bullishness (momentum quality)
        - Relative volume (participation quality)

        Each ticker gets a percentile rank 0-100 vs its peers in the result set.
        This is INTERNAL RS (ranking within discovered candidates), not external
        RS vs the broad market (which requires sector ETF data).

        Returns dict of {ticker: rs_percentile_0_100}.
        """
        if df is None or df.empty:
            return {}

        tickers = df["ticker"].str.split(":").str[-1].tolist()
        scores_list: list[float] = []

        for _, row in df.iterrows():
            score = 50.0  # baseline

            # EMA200 distance (0-25 pts)
            close = row.get("close", 0) or 0
            ema200 = row.get("EMA200", 0) or 0
            if ema200 and close:
                pct = (close - ema200) / ema200 * 100
                if pct > 10:
                    score += 25
                elif pct > 5:
                    score += 20
                elif pct > 2:
                    score += 12
                elif pct > 0:
                    score += 5
                else:
                    score -= min(20, abs(pct) * 2)

            # RSI (0-15 pts)
            rsi = row.get("RSI", 50) or 50
            if rsi > 65:
                score += 15
            elif rsi > 55:
                score += 10
            elif rsi > 50:
                score += 5
            elif rsi < 35:
                score += 10  # oversold bounce candidates
            elif rsi < 45:
                score += 5

            # Relative volume (0-10 pts)
            rvol = row.get("relative_volume_10d_calc", 1.0) or 1.0
            if rvol > 2.0:
                score += 10
            elif rvol > 1.5:
                score += 7
            elif rvol > 1.2:
                score += 4
            elif rvol > 1.0:
                score += 2

            # MACD alignment (0-5 pts)
            macd = row.get("MACD.macd", 0) or 0
            macd_sig = row.get("MACD.signal", 0) or 0
            if macd > macd_sig:
                score += 5
            else:
                score -= 5

            scores_list.append(max(0.0, min(100.0, score)))

        # Convert to percentile rank
        arr = np.array(scores_list)
        percentiles = (np.argsort(np.argsort(arr)) + 1) / len(arr) * 100

        return {t: int(round(p)) for t, p in zip(tickers, percentiles)}

    # ── Institutional Quality Score (0-100) ───────────────────────────

    def compute_inst_quality(self, row: pd.Series) -> int:
        """Rate institutional quality from TV snapshot data.

        Measures suitability for institutional capital:
        - Market cap (large-cap = higher quality, more liquid)
        - Volume consistency (active = easier to build positions)
        - Analyst coverage (more analyst attention = higher quality)
        - EPS (profitable = lower risk of bankruptcy/distress)

        Returns score 0-100.
        """
        score = 50  # baseline

        # Market cap (0-30 pts) — large caps have institutional liquidity
        mcap = row.get("market_cap_basic", 0) or 0
        if mcap > 200_000_000_000:
            score += 30  # mega-cap
        elif mcap > 50_000_000_000:
            score += 25
        elif mcap > 10_000_000_000:
            score += 20  # large-cap
        elif mcap > 5_000_000_000:
            score += 15
        elif mcap > 2_000_000_000:
            score += 10
        elif mcap > 1_000_000_000:
            score += 5

        # Volume liquidity (0-20 pts)
        volume = row.get("volume", 0) or 0
        if volume > 5_000_000:
            score += 20  # highly liquid
        elif volume > 1_000_000:
            score += 15
        elif volume > 500_000:
            score += 10
        elif volume > 100_000:
            score += 5

        # Analyst coverage (0-25 pts)
        analyst = row.get("AnalystRating", "")
        if analyst in ("StrongBuy",):
            score += 25
        elif analyst in ("Buy", "Outperform", "Overweight"):
            score += 18
        elif analyst in ("Hold", "Neutral"):
            score += 10
        elif analyst in ("Sell", "StrongSell"):
            score -= 10

        # EPS profitability (0-25 pts)
        eps = row.get("earnings_per_share_diluted_ttm", 0) or 0
        if eps > 10:
            score += 25
        elif eps > 5:
            score += 20
        elif eps > 2:
            score += 15
        elif eps > 0:
            score += 8
        else:
            score -= 10  # negative EPS = distress risk

        return max(0, min(100, score))

    # ── Signal Conviction ─────────────────────────────────────────────

    def assess_conviction(self, row: pd.Series, scores: dict[str, int]) -> str:
        """Assess overall signal conviction: high / medium / low.

        Based on factor ALIGNMENT. When factors agree, conviction is high.
        When they contradict (e.g., strong trend + poor quality), conviction drops.

        Rules:
        - HIGH: 4+ factors score >50% of their max (trend > 15, mom > 12,
          vol > 10, quality > 7, fund > 5)
        - MEDIUM: 3 factors >50%, no critical conflicts
        - LOW: anything else
        """
        thresholds = {"trend": 20, "momentum": 15, "volume": 12, "quality": 8, "fundamental": 6}
        strong = sum(1 for k, t in thresholds.items() if scores.get(k, 0) >= t)

        # Check critical conflicts
        macd = row.get("MACD.macd", 0) or 0
        macd_sig = row.get("MACD.signal", 0) or 0
        close = row.get("close", 0) or 0
        vwap = row.get("VWAP", 0) or 0

        conflicts: list[bool] = []

        # Trend says up but MACD says down
        if scores.get("trend", 0) >= 15 and macd <= macd_sig:
            conflicts.append(True)

        # Volume says up but price below VWAP
        if scores.get("volume", 0) >= 10 and vwap and close < vwap:
            conflicts.append(True)

        # MACD says up but RSI says overbought
        rsi = row.get("RSI", 50) or 50
        if macd > macd_sig and rsi > 85:
            conflicts.append(True)

        has_conflict = len(conflicts) >= 2

        if strong >= 4 and not has_conflict:
            return "high"
        if strong >= 3 and not has_conflict:
            return "medium"
        return "low"

    # ── Wyckoff Phase Proxy ───────────────────────────────────────────

    def classify_wyckoff_phase(self, row: pd.Series) -> str | None:
        """Infer Wyckoff phase from TV snapshot data.

        This is a PROXY classification — true Wyckoff analysis requires
        multi-bar structural patterns. However, volume + price + volatility
        relationships on a single bar can suggest the current phase:

        - **accumulation**: Volume elevated but price contained (absorption),
          price near support (VWAP/EMA50), tight BB = Phase B/C
        - **markup**: Price trending up with expanding volume and volatility,
          MACD bullish, price well above EMAs = Phase D
        - **distribution**: Volume elevated, price stalling near resistance,
          bearish divergences forming = Phase A
        - **markdown**: Price below key EMAs, heavy volume but no recovery,
          bearish MACD = Phase E

        Returns one of: accumulation / markup / distribution / markdown / None
        """
        close = row.get("close", 0) or 0
        ema50 = row.get("EMA50", 0) or 0
        ema200 = row.get("EMA200", 0) or 0
        rvol = row.get("relative_volume_10d_calc", 1.0) or 1.0
        vwap = row.get("VWAP", 0) or 0
        rsi = row.get("RSI", 50) or 50
        macd = row.get("MACD.macd", 0) or 0
        macd_sig = row.get("MACD.signal", 0) or 0
        bb_upper = row.get("BB.upper", 0) or 0
        bb_lower = row.get("BB.lower", 0) or 0

        near_high = bb_upper and close >= bb_upper * 0.98
        near_low = bb_lower and close <= bb_lower * 1.02

        # Markup (Phase D) — trending up, expanding volume, bullish MACD
        if (close > ema50 > ema200 and macd > macd_sig and rsi > 55
                and rvol > 1.2 and near_high):
            return "markup"

        # Distribution (Phase A) — stalling near highs, volume but no progress
        if (close > ema200 and rvol > 1.3 and rsi > 60
                and near_high and macd < macd_sig):
            return "distribution"

        # Accumulation (Phase B/C) — volume picking up, price contained near support
        if (close >= ema50 and rvol > 1.0 and rsi < 55
                and macd_sig > macd and vwap and close >= vwap * 0.98):
            return "accumulation"

        # Markdown (Phase E) — below EMAs, heavy volume selling, bearish
        if (close < ema50 and rvol > 1.3 and rsi < 40
                and macd < macd_sig and near_low):
            return "markdown"

        return None

    # ── Factor Conflicts ──────────────────────────────────────────────

    def detect_conflicts(self, row: pd.Series, scores: dict[str, int]) -> list[str]:
        """Detect contradictory signals that reduce trade quality.

        Returns human-readable conflict descriptions.
        """
        conflicts: list[str] = []
        close = row.get("close", 0) or 0
        vwap = row.get("VWAP", 0) or 0
        rsi = row.get("RSI", 50) or 50
        macd = row.get("MACD.macd", 0) or 0
        macd_sig = row.get("MACD.signal", 0) or 0

        # Trend up but momentum weakening
        if scores.get("trend", 0) >= 15 and macd <= macd_sig:
            conflicts.append("Trend bullish but MACD bearish — momentum divergence")
        elif scores.get("trend", 0) <= 5 and macd > macd_sig:
            conflicts.append("MACD bullish but trend weak — needs price confirmation")

        # Volume says bullish but VWAP says bearish
        if scores.get("volume", 0) >= 10 and vwap and close < vwap:
            conflicts.append("Volume elevated but below VWAP — distribution risk")

        # RSI extreme + MACD still bullish = extended, not strong
        if macd > macd_sig and rsi > 80:
            conflicts.append("RSI overbought (>80) despite MACD bullish — extended, not entry")

        # Price below EMA200 but volume surging — possible capitulation, not accumulation
        ema200 = row.get("EMA200", 0) or 0
        if ema200 and close < ema200:
            rvol = row.get("relative_volume_10d_calc", 1.0) or 1.0
            if rvol > 2.0:
                conflicts.append("Price below EMA200 with heavy volume — distribution/capitulation risk")

        return conflicts

    # ── Top-Level Enrichment ──────────────────────────────────────────

    def enrich(
        self,
        df: pd.DataFrame,
        direction: str = "long",
        regime: str | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Run all enrichment passes on a TV discovery result DataFrame.

        Args:
            df: Raw TV discovery DataFrame (with ticker column).
            direction: "long" or "short".
            regime: Market regime string (passed through to enrichment).

        Returns:
            Dict of {ticker: enrichment_data} where enrichment_data includes
            rs_rating, inst_quality, signal_conviction, wyckoff_phase,
            factor_conflicts, and regime.
        """
        if df is None or df.empty:
            return {}

        rs_ratings = self.compute_rs_ratings(df)
        tickers = df["ticker"].str.split(":").str[-1].tolist()
        enrichments: dict[str, dict[str, Any]] = {}

        for i, (_, row) in enumerate(df.iterrows()):
            ticker = tickers[i] if i < len(tickers) else ""
            if not ticker:
                continue

            # ConfluenceScore-like scores dict for conviction + conflicts
            scores = self._compute_scores_snapshot(row, direction)

            rs = rs_ratings.get(ticker, 50)
            inst_q = self.compute_inst_quality(row)
            conviction = self.assess_conviction(row, scores)
            wyckoff = self.classify_wyckoff_phase(row)
            conflicts = self.detect_conflicts(row, scores)

            enrichments[ticker] = {
                "rs_rating": rs,
                "inst_quality": inst_q,
                "signal_conviction": conviction,
                "wyckoff_phase": wyckoff,
                "factor_conflicts": conflicts,
                "regime": regime,
            }

        return enrichments

    def _compute_scores_snapshot(
        self, row: pd.Series, direction: str
    ) -> dict[str, int]:
        """Compute a quick scores snapshot for conflict detection.

        Lightweight version of TVConfluenceScorer scoring — just enough
        to assess factor alignment. Not a replacement for the full scorer.
        """
        is_long = direction == "long"
        scores: dict[str, int] = {}

        close = row.get("close", 0) or 0
        ema200 = row.get("EMA200", 0) or 0
        ema50 = row.get("EMA50", 0) or 0

        # Quick trend score (0-30)
        trend = 0
        if ema200 and close > ema200:
            pct = (close - ema200) / ema200 * 100
            trend += 10 if pct > 10 else (8 if pct > 5 else (4 if pct > 2 else 2))
        if ema50 and close > ema50:
            pct = (close - ema50) / ema50 * 100
            trend += 10 if pct > 8 else (6 if pct > 3 else (4 if pct > 1 else 2))
        scores["trend"] = trend if is_long else max(0, 30 - trend)

        # Quick momentum score (0-25)
        macd = row.get("MACD.macd", 0) or 0
        macd_sig = row.get("MACD.signal", 0) or 0
        rsi = row.get("RSI", 50) or 50
        mom = 0
        if (macd > macd_sig) if is_long else (macd < macd_sig):
            mom += 8
            spread = abs(macd - macd_sig) / (abs(macd_sig) + 1e-9)
            mom += 7 if spread > 1.0 else (4 if spread > 0.5 else 1)
        if (rsi > 55) if is_long else (rsi < 45):
            mom += 10 if rsi > 65 else (5 if rsi > 55 else 3)
        scores["momentum"] = min(25, mom)

        # Quick volume score (0-20)
        vol = 0
        rvol = row.get("relative_volume_10d_calc", 1.0) or 1.0
        vwap = row.get("VWAP", 0) or 0
        vol += 8 if rvol > 2.0 else (5 if rvol > 1.5 else (3 if rvol > 1.2 else 1))
        if vwap and close:
            if (close > vwap) if is_long else (close < vwap):
                vol += 7
        scores["volume"] = min(20, vol)

        # Quick quality score (0-15)
        adx = row.get("ADX", 0) or 0
        qual = 0
        qual += 8 if adx > 25 else (5 if adx > 20 else (2 if adx > 15 else 0))
        scores["quality"] = min(15, qual)

        # Quick fundamental score (0-10)
        fund = 0
        analyst = row.get("AnalystRating", "")
        if analyst in ("StrongBuy",):
            fund += 5
        elif analyst in ("Buy", "Outperform"):
            fund += 3
        mcap = row.get("market_cap_basic", 0) or 0
        if mcap > 10_000_000_000:
            fund += 3
        elif mcap > 1_000_000_000:
            fund += 1
        scores["fundamental"] = min(10, fund)

        return scores
