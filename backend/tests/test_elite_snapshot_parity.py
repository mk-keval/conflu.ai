"""Golden baseline guard: the EliteSignalProcessor snapshot scorer must stay a
faithful proxy of TVConfluenceScorer (per D-32 follow-up decision).

The baseline (see scripts/compare_scorers.py) measured mean per-factor
divergence of 2.97 pts on diverse rows — small enough that factor-ALIGNMENT
detection (which uses >50%-of-max thresholds) is robust. BUT conviction can
flip on ~1/3 of edge rows, so we deliberately do NOT replace the snapshot with
the real scorer (behavior change). This guard prevents the two from silently
drifting further apart in future refactors.
"""

from __future__ import annotations

import pandas as pd
import pytest

from backend.app.infrastructure.screener.confluence_scorer import TVConfluenceScorer
from backend.app.infrastructure.screener.elite_signal import EliteSignalProcessor

# Diverse rows: strong/weak/extended/bearish/low-vol/high-vol setups
ROWS: list[dict[str, float]] = [
    {"close": 110.0, "EMA20": 105.0, "EMA50": 100.0, "EMA200": 92.0,
     "RSI": 62.0, "MACD.macd": 1.2, "MACD.signal": 0.6, "ADX": 28.0,
     "ATR": 3.0, "VWAP": 108.0, "relative_volume_10d_calc": 1.8,
     "earnings_per_share_diluted_ttm": 4.0},
    {"close": 130.0, "EMA20": 115.0, "EMA50": 108.0, "EMA200": 95.0,
     "RSI": 82.0, "MACD.macd": 2.5, "MACD.signal": 1.0, "ADX": 35.0,
     "ATR": 5.0, "VWAP": 122.0, "relative_volume_10d_calc": 2.4,
     "earnings_per_share_diluted_ttm": 6.5},
    {"close": 100.5, "EMA20": 100.0, "EMA50": 99.0, "EMA200": 98.0,
     "RSI": 52.0, "MACD.macd": 0.1, "MACD.signal": 0.0, "ADX": 15.0,
     "ATR": 1.5, "VWAP": 100.0, "relative_volume_10d_calc": 0.9,
     "earnings_per_share_diluted_ttm": 2.0},
    {"close": 85.0, "EMA20": 95.0, "EMA50": 100.0, "EMA200": 108.0,
     "RSI": 38.0, "MACD.macd": -1.4, "MACD.signal": -0.5, "ADX": 30.0,
     "ATR": 3.5, "VWAP": 92.0, "relative_volume_10d_calc": 2.1,
     "earnings_per_share_diluted_ttm": 1.5},
    {"close": 51.0, "EMA20": 50.2, "EMA50": 49.8, "EMA200": 49.0,
     "RSI": 57.0, "MACD.macd": 0.2, "MACD.signal": 0.15, "ADX": 18.0,
     "ATR": 0.4, "VWAP": 50.8, "relative_volume_10d_calc": 1.1,
     "earnings_per_share_diluted_ttm": 3.0},
    {"close": 75.0, "EMA20": 68.0, "EMA50": 64.0, "EMA200": 60.0,
     "RSI": 71.0, "MACD.macd": 2.0, "MACD.signal": 1.2, "ADX": 42.0,
     "ATR": 4.0, "VWAP": 70.0, "relative_volume_10d_calc": 3.4,
     "earnings_per_share_diluted_ttm": 2.8},
]


def _per_row_divergence(scorer: TVConfluenceScorer, elite: EliteSignalProcessor) -> list[float]:
    divergences: list[float] = []
    for row_dict in ROWS:
        row = pd.Series(row_dict)
        snap = elite._compute_scores_snapshot(row, "long")
        real = scorer.score(row, direction="long")
        divs = [
            abs(snap.get(f, 0) - real.breakdown.get(f, 0))
            for f in ["trend", "momentum", "volume", "quality", "fundamental"]
        ]
        divergences.append(sum(divs) / len(divs))
    return divergences


class TestSnapshotVsRealScorerDivergence:
    def test_mean_divergence_stays_bounded(self) -> None:
        scorer = TVConfluenceScorer()
        elite = EliteSignalProcessor()
        divs = _per_row_divergence(scorer, elite)
        # Baseline 2026-08-17: mean 2.97, max 4.20. Allow headroom so small
        # intentional scoring tweaks don't red-flag; catch material drift.
        assert sum(divs) / len(divs) < 8.0

    def test_no_factor_diverges_extremely(self) -> None:
        scorer = TVConfluenceScorer()
        elite = EliteSignalProcessor()
        divs = _per_row_divergence(scorer, elite)
        assert max(divs) < 12.0

    def test_snapshot_output_shape(self) -> None:
        elite = EliteSignalProcessor()
        row = pd.Series(ROWS[0])
        snap = elite._compute_scores_snapshot(row, "long")
        assert set(snap.keys()) == {"trend", "momentum", "volume", "quality", "fundamental"}
        assert all(0 <= v <= 30 for v in snap.values())