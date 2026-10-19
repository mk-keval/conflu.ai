"""Paper-trade replay runner (D-71) — see docs/DECISIONS/D-71.

Runs the deployed screen templates over a broad liquid universe for the last
N days using the honest engine, then stores the trade-by-trade result in a
separate replay ledger (``replay_runs`` / ``replay_trades``) that the Journal
tab can display under a "Replay" toggle.

Important: TradingView's screener cannot be rewound, so this replays the
templates + regime screen-selection logic — not the exact live brief. It is
simulated evidence and never counts toward the forward scorecard.

Usage:
  python run_paper_replay.py                      # 60d, S&P 500, deployed screens
  python run_paper_replay.py --days 30 --max-per-day 10
  python run_paper_replay.py --refresh-universe   # refresh the ticker list too
  python run_paper_replay.py --no-write           # print + JSON only, no DB
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, ".")

from backend.app.domain.workflow import replay_store  # noqa: E402
from backend.app.infrastructure.backtest.replay import (  # noqa: E402
    ReplayParams,
    run_replay,
)
from backend.app.infrastructure.backtest.replay_data import (  # noqa: E402
    refresh_sp500_universe,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replay deployed screens over the last N days (simulated journal)."
    )
    parser.add_argument("--days", type=int, default=60, help="replay window in calendar days")
    parser.add_argument(
        "--max-per-day",
        type=int,
        default=0,
        help="cap entries per day (0 = keep every deduped signal)",
    )
    parser.add_argument("--risk-pct", type=float, default=1.0, help="risk per trade in %% of account")
    parser.add_argument("--account", type=float, default=100_000.0, help="hypothetical account value")
    parser.add_argument("--stop-atr", type=float, default=2.0)
    parser.add_argument("--target-atr", type=float, default=3.0)
    parser.add_argument("--max-hold", type=int, default=15, help="swing cap in trading bars")
    parser.add_argument(
        "--templates",
        default="deployed",
        help="'deployed' (from config/regime_screens.yaml) or comma-separated stems",
    )
    parser.add_argument("--universe-file", default=None, help="ticker list file override")
    parser.add_argument("--refresh-data", action="store_true", help="ignore the OHLCV cache")
    parser.add_argument(
        "--refresh-universe",
        action="store_true",
        help="re-download the S&P 500 list before running",
    )
    parser.add_argument("--no-write", action="store_true", help="do not write the replay ledger")
    parser.add_argument("--no-json", action="store_true", help="do not write the JSON artifact")
    parser.add_argument("--verbose", action="store_true", help="keep per-symbol engine logging")
    return parser.parse_args()


def _fmt_pf(value: float | None) -> str:
    return f"{value:5.2f}" if value else "  n/a"


async def main() -> None:
    args = _parse_args()

    if args.refresh_universe:
        symbols = refresh_sp500_universe(args.universe_file)
        print(f"Refreshed universe: {len(symbols)} symbols")

    params = ReplayParams(
        window_days=args.days,
        stop_atr_mult=args.stop_atr,
        target_atr_mult=args.target_atr,
        max_hold_bars=args.max_hold,
        risk_pct=args.risk_pct,
        account_value=args.account,
        max_per_day=args.max_per_day,
    )
    templates_filter = None
    if args.templates != "deployed":
        templates_filter = [s.strip() for s in args.templates.split(",") if s.strip()]

    result = await run_replay(
        params,
        universe_file=args.universe_file,
        refresh_data=args.refresh_data,
        templates_filter=templates_filter,
        suppress_engine_logs=not args.verbose,
    )

    run, rows, summary = result.run, result.rows, result.summary

    print()
    print("=" * 92)
    print(
        f"REPLAY {run['window_start']} -> {run['window_end']} "
        f"| {run['templates_count']} deployed screens | {run['universe_count']} symbols"
    )
    print("=" * 92)
    counts = run["metadata"]["counts"]
    print(
        f"Signals: raw={counts['raw_signals']} -> regime-gated={counts['after_regime_gate']} "
        f"-> deduped={counts['after_dedupe']} -> rows={counts['rows']}"
    )
    regime_days = run["metadata"]["regime_days"]
    print(f"Regime days: {regime_days}")
    print()
    header = (
        f"{'template':38} {'trades':>6} {'win%':>6} {'exp_r':>7} "
        f"{'PF':>6} {'P&L$':>10}"
    )
    print(header)
    print("-" * len(header))
    for name, stats in sorted(
        summary["templates"].items(), key=lambda kv: kv[1]["trades"], reverse=True
    ):
        print(
            f"{name:38} {stats['trades']:6d} {stats['win_rate'] * 100:5.1f}% "
            f"{stats['expectancy_r']:+7.3f} {_fmt_pf(stats['profit_factor_r'])} "
            f"{stats['pnl_usd']:+10,.0f}"
        )
    print("-" * len(header))
    print(
        f"{'TOTAL':38} {summary['trades']:6d} {summary['win_rate'] * 100:5.1f}% "
        f"{summary['expectancy_r']:+7.3f} {_fmt_pf(summary['profit_factor_r'])} "
        f"{summary['pnl_usd']:+10,.0f}"
    )
    print(
        f"\nWinners: {summary['wins']}  Losers: {summary['losses']}  "
        f"Avg win: {summary['avg_win_r']:+.2f}R  Avg loss: {summary['avg_loss_r']:+.2f}R  "
        f"Avg hold: {summary['avg_hold_bars']:.1f} bars"
    )
    print(
        f"Hypothetical P&L at {args.risk_pct:g}% risk/trade on ${args.account:,.0f}: "
        f"${summary['pnl_usd']:+,.0f}"
    )
    print(f"Exit reasons: {summary['exit_reasons']}")

    if not args.no_json:
        out_dir = Path("docs/backtests")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"replay_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
        payload = {"run": run, "rows": rows}
        out_path.write_text(
            json.dumps(payload, indent=2, default=str), encoding="utf-8"
        )
        print(f"\nWrote {out_path}")

    if not args.no_write:
        run_id = replay_store.replace_run(run, rows)
        print(
            f"Stored replay run #{run_id} in data/paper_trades.db "
            f"(replay_runs / replay_trades) — view it in Workflow -> Journal -> Replay."
        )

    print("\nNOTE: simulated screen replay, not forward evidence.")


if __name__ == "__main__":
    asyncio.run(main())
