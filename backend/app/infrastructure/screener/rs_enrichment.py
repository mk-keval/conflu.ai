# RS-vs-index enrichment — percentile ranks from ONE snapshot (P1.3)
"""
Computes relative-strength percentiles for every symbol in a base TV
snapshot against an index benchmark (SPY row) or the market median, at 1M
and 3M horizons using TradingView perf columns.

ZERO extra upstream calls: the perf columns ride along on the same
snapshot query that discovery already makes.

Output shape (additive, attached per scored item under ``item["rs"]``):

    {
        "perf_1m": float,          # raw % perf
        "perf_3m": float,
        "excess_1m": float | None, # vs SPY row (or market median fallback)
        "excess_3m": float | None,
        "pct_1m": float,           # 0-100 percentile vs full universe
        "pct_3m": float,
        "composite": float,        # mean of pct_1m/pct_3m
    }
"""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

from backend.app.core.logging import get_logger

log = get_logger("conflu.screener.rs_enrichment")

_PERF_COLUMNS: dict[str, str] = {"1m": "Perf.1M", "3m": "Perf.3M"}
_BENCHMARK_SYMBOLS: tuple[str, ...] = ("SPY",)


def _symbol_of(ticker_cell: object) -> str | None:
    """'NASDAQ:AAPL' -> 'AAPL'; returns None for malformed cells."""
    if not isinstance(ticker_cell, str) or not ticker_cell:
        return None
    return ticker_cell.split(":")[-1].upper() or None


def _to_float(value: Any) -> float | None:
    """Coerce a scalar to a finite float; anything else becomes None."""
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _percentile_ranks(series: pd.Series) -> pd.Series:
    """0-100 percentile rank, NaN-preserving."""
    return series.rank(pct=True) * 100.0


def compute_rs_percentiles(
    snapshot: pd.DataFrame,
    *,
    benchmarks: tuple[str, ...] = _BENCHMARK_SYMBOLS,
) -> dict[str, dict[str, float | None]]:
    """RS percentile enrichment for every symbol in the snapshot.

    Benchmark anchoring: the first listed benchmark symbol present in the
    snapshot; otherwise the cross-sectional MEDIAN of each horizon (the
    median defines the 50th-percentile anchor by construction).

    Returns {} when the frame lacks the perf columns — callers treat RS as
    unavailable rather than fabricating neutral scores.
    """
    if snapshot.empty:
        return {}
    for col in _PERF_COLUMNS.values():
        if col not in snapshot.columns:
            log.debug("rs_enrichment_missing_column", column=col)
            return {}
    if "ticker" not in snapshot.columns:
        return {}

    df = pd.DataFrame(index=snapshot.index)
    df["symbol"] = snapshot["ticker"].map(_symbol_of)
    for key, col in _PERF_COLUMNS.items():
        df[key] = pd.to_numeric(snapshot[col], errors="coerce")
    df = df.dropna(subset=["symbol"])
    df = df.dropna(how="all", subset=list(_PERF_COLUMNS.keys()))
    if df.empty:
        return {}

    out: dict[str, dict[str, float | None]] = {}
    # Seed neutral entries so both horizons write into the same record.
    for sym in df["symbol"]:
        out[str(sym)] = {
            "perf_1m": None,
            "perf_3m": None,
            "excess_1m": None,
            "excess_3m": None,
            "pct_1m": 50.0,
            "pct_3m": 50.0,
            "composite": 50.0,
        }

    for horizon in _PERF_COLUMNS:
        series = df[horizon]
        bench_value: float | None = None
        for bench in benchmarks:
            rows = df.loc[df["symbol"] == bench.upper(), horizon].dropna()
            if not rows.empty:
                bench_value = _to_float(rows.iloc[0])
                break
        if bench_value is None:
            bench_value = _to_float(series.median())

        excess = series - bench_value if bench_value is not None else series
        pct = _percentile_ranks(excess)

        for idx in df.index:
            entry = out[str(df.at[idx, "symbol"])]
            entry[f"perf_{horizon}"] = _to_float(series.at[idx])
            entry[f"excess_{horizon}"] = _to_float(excess.at[idx])
            p = _to_float(pct.at[idx])
            entry[f"pct_{horizon}"] = round(p, 1) if p is not None else 50.0

    for entry in out.values():
        p1, p3 = entry["pct_1m"], entry["pct_3m"]
        entry["composite"] = round(((p1 or 50.0) + (p3 or 50.0)) / 2.0, 1)

    return out
