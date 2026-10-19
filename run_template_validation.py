"""Template Validation Runner — honest re-validation of deployed screens.

Replaces the 2026-09-26 D-61 run, which used look-ahead exits
(``entries.shift(-5)``), collapsed params (operators/timeframes dropped),
10 mega-caps and a 2023-2024 window. This runner:

  - evaluates the FULL filter rules per template (per-rule timeframes are
    honored: 4h rules run on 4h bars resampled from 1h data)
  - simulates ATR stop/target exits (2.0 / 3.0 ATR) plus a swing time cap
    (``max_hold_bars``, default 15) — no look-ahead
  - uses the trailing ~700-day window (yfinance 1h history limit; needed
    so 4h rules can be evaluated at all)
  - runs a broader 30-name universe across sectors and market caps
  - records every filter that could NOT be applied (fundamentals, missing
    data) in the output instead of silently passing it

Output: docs/backtests/validation_<UTC timestamp>.json (committed artifact).

Usage:  python run_template_validation.py [--max-hold 15] [--universe quick]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, ".")

from backend.app.infrastructure.backtest.external_backtest import (  # noqa: E402
    BacktestConfig,
    ExternalBacktestEngine,
)
from backend.app.infrastructure.data.fetcher import OHLCVFetcher  # noqa: E402
from backend.app.infrastructure.screener.configs import load_screen_template  # noqa: E402

# ~30 liquid names across sectors and market caps (mega -> upper mid).
UNIVERSE = [
    # Technology mega caps (kept for comparability with the D-61 cohort)
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AVGO", "ORCL", "CRM",
    # Large caps, other sectors
    "JPM", "V", "UNH", "LLY", "XOM", "COST", "WMT", "CAT", "GE", "NFLX",
    # Higher-beta / mid caps
    "AMD", "MU", "PANW", "SHOP", "COIN", "UBER", "DECK", "ON", "MRNA", "LULU",
]

QUICK_UNIVERSE = ["AAPL", "MSFT", "NVDA", "JPM", "XOM", "AMD", "PANW", "COIN"]

WINDOW_DAYS = 700  # yfinance 1h history goes back ~730 days; stay inside it
FETCH_DELAY_SECONDS = 2.2  # yfinance rate limit politeness


class _PrefetchedFetcher:
    """Serves pre-fetched OHLCV frames; records misses."""

    def __init__(self, data: dict[tuple[str, str], object]):
        self.data = data
        self.misses: Counter[tuple[str, str]] = Counter()

    async def fetch_yahoo(self, symbol: str, timeframe: str, start: str, end: str):  # noqa: ARG002
        df = self.data.get((symbol, timeframe))
        if df is None:
            self.misses[(symbol, timeframe)] += 1
        return df


async def prefetch_universe(
    symbols: list[str], start: str, end: str
) -> dict[tuple[str, str], object]:
    fetcher = OHLCVFetcher()
    data: dict[tuple[str, str], object] = {}
    total = len(symbols) * 2
    done = 0
    for symbol in symbols:
        for timeframe in ("1D", "1h"):
            done += 1
            try:
                await asyncio.sleep(FETCH_DELAY_SECONDS)
                df = await fetcher.fetch_yahoo(symbol, timeframe, start, end)
                if df is not None and not df.empty:
                    data[(symbol, timeframe)] = df
                else:
                    print(f"  [{done}/{total}] {symbol} {timeframe}: EMPTY")
                    continue
                print(f"  [{done}/{total}] {symbol} {timeframe}: {len(df)} bars")
            except Exception as exc:  # noqa: BLE001 - report and continue
                print(f"  [{done}/{total}] {symbol} {timeframe}: FETCH FAILED ({exc})")
    return data


def _pool(trades: list[dict]) -> dict:
    if not trades:
        return {
            "trades": 0, "win_rate": 0.0, "profit_factor": 0.0, "expectancy_r": 0.0,
            "avg_win_r": 0.0, "avg_loss_r": 0.0, "avg_hold_bars": 0.0,
            "exit_reasons": {},
        }
    pnls = [t["pnl"] for t in trades]
    rs = [t["r_multiple"] for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    wins_r = [r for r in rs if r > 0]
    losses_r = [r for r in rs if r < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    return {
        "trades": len(trades),
        "win_rate": len(wins) / len(trades),
        "profit_factor": (gross_profit / gross_loss) if gross_loss > 0 else None,
        "expectancy_r": sum(rs) / len(rs),
        "avg_win_r": (sum(wins_r) / len(wins_r)) if wins_r else 0.0,
        "avg_loss_r": (sum(losses_r) / len(losses_r)) if losses_r else 0.0,
        "avg_hold_bars": sum(t["hold_bars"] for t in trades) / len(trades),
        "exit_reasons": dict(Counter(t["exit_reason"] for t in trades)),
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Honest template re-validation (validation reset 2026-10-19)")
    parser.add_argument("--max-hold", type=int, default=15, help="swing time cap in trading bars (0 = none)")
    parser.add_argument("--universe", choices=["full", "quick"], default="full")
    parser.add_argument("--templates", default="all", help="comma-separated stems, or 'all'")
    parser.add_argument("--stop-atr", type=float, default=2.0)
    parser.add_argument("--target-atr", type=float, default=3.0)
    args = parser.parse_args()

    universe = UNIVERSE if args.universe == "full" else QUICK_UNIVERSE
    max_hold = args.max_hold or None

    end_date = date.today()
    start_date = end_date - timedelta(days=WINDOW_DAYS)
    start_str, end_str = start_date.isoformat(), end_date.isoformat()

    screens_dir = Path("config/screens")
    if args.templates == "all":
        template_stems = sorted(p.stem for p in screens_dir.glob("*.yaml"))
    else:
        template_stems = [s.strip() for s in args.templates.split(",") if s.strip()]

    print(f"Window:        {start_str} -> {end_str} ({WINDOW_DAYS}d)")
    print(f"Universe:      {len(universe)} symbols ({args.universe})")
    print(f"Templates:     {len(template_stems)}")
    print(f"Exits:         stop {args.stop_atr} ATR / target {args.target_atr} ATR / max hold {max_hold or 'none'} bars")
    print("\nPrefetching OHLCV (1D + 1h per symbol)...")
    data = await prefetch_universe(universe, start_str, end_str)

    fetcher = _PrefetchedFetcher(data)
    engine = ExternalBacktestEngine(fetcher=fetcher)

    report: dict = {
        "generated_at": datetime.now(UTC).isoformat(),
        "engine": "external_backtest v2 — validation reset 2026-10-19 (no look-ahead, per-rule timeframes, ATR exits)",
        "window": {
            "start": start_str,
            "end": end_str,
            "days": WINDOW_DAYS,
            "max_hold_bars": max_hold,
            "stop_atr_mult": args.stop_atr,
            "target_atr_mult": args.target_atr,
        },
        "universe": universe,
        "universe_note": "Current liquid names (survivorship bias remains); not a P&L promise — screen-behavior evidence.",
        "caveats": [
            "4h rules are computed from 1h bars resampled into calendar 4h buckets (TV parity is approximate).",
            "Intraday history from yfinance only covers ~730 days; the window is capped accordingly.",
            "Stop/target fills are assumed at the level (no gap slippage).",
            "Fundamental rules are recorded as 'not applied' — templates are validated on their technical subset.",
            "Fees 10 bps + slippage 5 bps per side applied; entries at next bar's open.",
        ],
        "templates": {},
    }

    print("\nRunning templates...")
    for stem in template_stems:
        try:
            screen = load_screen_template(stem)
        except Exception as exc:  # noqa: BLE001 - skip unloadable configs loudly
            print(f"  {stem}: LOAD FAILED ({exc})")
            continue

        all_trades: list[dict] = []
        per_symbol: dict[str, dict] = {}
        excluded: list[dict] = []
        skipped_union: Counter[str] = Counter()

        for symbol in universe:
            if (symbol, "1D") not in data:
                excluded.append({"symbol": symbol, "error": "no daily data fetched"})
                continue
            config = BacktestConfig(
                symbol=symbol,
                timeframe="1D",
                start_date=start_str,
                end_date=end_str,
                signal_filters=list(screen.filters),
                direction=getattr(screen, "direction", "long"),
                stop_atr_mult=args.stop_atr,
                target_atr_mult=args.target_atr,
                max_hold_bars=max_hold,
            )
            result = await engine.run_backtest(config)
            skipped_union.update(result.skipped_filters)
            if result.error:
                excluded.append(
                    {"symbol": symbol, "error": result.error, "skipped": result.skipped_filters}
                )
                continue
            all_trades.extend(result.trades)
            per_symbol[symbol] = {
                "trades": result.total_trades,
                "win_rate": round(result.win_rate, 4),
                "expectancy_r": round(result.expectancy_r, 4),
                "profit_factor": round(result.profit_factor, 4) if result.profit_factor else None,
                "avg_hold_bars": round(result.avg_hold_bars, 2),
                "exit_reasons": result.exit_reason_counts,
            }

        pooled = _pool(all_trades)
        report["templates"][stem] = {
            "direction": getattr(screen, "direction", "long"),
            "symbols_evaluated": len(per_symbol),
            "symbols_excluded": excluded,
            "pooled": pooled,
            "not_applied_filters": dict(skipped_union),
            "per_symbol": per_symbol,
        }
        pf = pooled["profit_factor"]
        print(
            f"  {stem:38} syms={len(per_symbol):2d} trades={pooled['trades']:4d} "
            f"wr={pooled['win_rate']*100:5.1f}% exp_r={pooled['expectancy_r']:+.3f} "
            f"pf={('%.2f' % pf) if pf else 'n/a':>5} hold={pooled['avg_hold_bars']:5.1f}"
        )

    out_dir = Path("docs/backtests")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"validation_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nWrote {out_path}")
    if fetcher.misses:
        print(f"Fetch misses: {dict(fetcher.misses)}")


if __name__ == "__main__":
    asyncio.run(main())
