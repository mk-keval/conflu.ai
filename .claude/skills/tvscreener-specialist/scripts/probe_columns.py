"""Live-verify tradingview-screener columns — ships with the tvscreener-specialist skill.

Unknown columns are silently null-filled by the TV scan API, so every column a query
depends on should be probed before use. This script measures non-null counts + samples
for the skill's standard registry over the current top-mcap US stocks.

Usage:
    python probe_columns.py                       # standard registry (working + dead lists)
    python probe_columns.py --extra COL1 COL2     # additionally probe candidate columns
    python probe_columns.py --limit 10            # rows to sample (default 5)

Exit code 0 always (it is a report, not a test). Re-run whenever TV column behavior is
suspected to have changed, then update the SKILL.md registry tables with the date.
"""
from __future__ import annotations

import argparse
import json
import sys

from tradingview_screener import Query

# Verified working 2026-10-19 (package 3.2.2)
WORKING = [
    # price/action
    "close", "change", "gap", "premarket_change", "High.All", "Low.All",
    "price_52_week_high", "price_52_week_low",
    # volume/liquidity
    "volume", "average_volume_10d_calc", "relative_volume_10d_calc",
    "volume_change", "VWAP", "Value.Traded",
    # trend
    "EMA9", "EMA10", "EMA20", "EMA21", "EMA50", "EMA100", "EMA150", "EMA200",
    "SMA20", "SMA50", "SMA200",
    # momentum
    "RSI", "RSI7", "RSI21", "Stoch.K", "Stoch.D", "CCI20",
    "MACD.macd", "MACD.signal", "MACD.hist", "Recommend.All", "TechRating_1D",
    # volatility/risk
    "ATR", "BB.upper", "BB.basis", "BB.lower", "Volatility.D",
    "beta_1_year", "beta_5_year",
    # performance
    "Perf.W", "Perf.1M", "Perf.3M", "Perf.6M", "Perf.Y",
    # fundamentals
    "market_cap_basic", "market_cap_calc", "price_earnings_ttm",
    "earnings_per_share_diluted_ttm", "dividends_yield_current",
    # meta/classification/sentiment
    "name", "sector", "industry", "exchange", "country", "type", "typespecs",
    "update_mode", "AnalystRating",
]

# Verified dead / wrong-name 2026-10-19 — must re-read as all-null
DEAD = [
    "STOCH.K", "STOCH.D", "RSI14", "ADX14", "ATR14", "CCI",
    "BB.width", "BB.middle", "Perf.M", "price",
    "ipo_date", "institutional_ownership", "short_float", "float_shares",
    "free_float", "turnover", "postmarket_change", "price_earnings_forward",
    "relative_strength_rank", "relative_strength_rating", "relative_strength",
    "OBV", "supertrend", "supertrend.up", "supertrend.down",
]


def probe(columns: list[str], limit: int) -> dict:
    q = Query()
    q.select(*columns)
    q.limit(limit)
    total, df = q.get_scanner_data()
    report: dict[str, dict] = {}
    for c in columns:
        if c not in df.columns:
            report[c] = {"non_null": None, "note": "absent from dataframe"}
            continue
        vals = df[c].dropna()
        sample = None
        if len(vals):
            first = vals.iloc[0]
            sample = first.item() if hasattr(first, "item") else str(first)
        report[c] = {"non_null": int(df[c].notna().sum()), "of": int(len(df)), "sample": sample}
    return {"total_matches": int(total), "columns": report}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extra", nargs="*", default=[], help="extra candidate columns")
    parser.add_argument("--limit", type=int, default=5, help="rows to sample (default 5)")
    args = parser.parse_args()

    print(json.dumps({"probe": "working", **probe(WORKING + args.extra, args.limit)}, default=str, indent=1))
    print(json.dumps({"probe": "dead_expected", **probe(DEAD, args.limit)}, default=str, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
