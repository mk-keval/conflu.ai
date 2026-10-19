"""Counterfactual 'what-if' experiments on the D-71 replay window (design learning).

DESIGN LEARNING ONLY — this is not forward evidence and not a P&L promise. Every
variant replays the same cached OHLCV and the same as-of regime map as the official
2-month replay; only the hypothesis under test changes:

  1. baseline                    — default deployed screen mix (sanity: should reproduce
                                   the stored replay: 371 trades, -0.203R, PF 0.63)
  2. choppy_meanrev              — choppy days use the "ranging" menu (mean reversion)
                                   instead of the continuation menu
  3. wide_target_4.5             — same mix, target 4.5 ATR instead of 3.0 (winners can
                                   run to 2.25R instead of 1.5R)
  4. choppy_meanrev+wide_target  — both fixes at once

Also computes a post-hoc note: halving risk on choppy trades (R-multiples unchanged;
only the hypothetical $ P&L scales).

Never writes to the replay ledger (data/paper_trades.db) — JSON artifact only.

Usage:
  python run_replay_experiments.py
  python run_replay_experiments.py --no-json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, ".")

from backend.app.infrastructure.backtest.replay import (  # noqa: E402
    ReplayParams,
    load_screen_mix,
    run_replay,
)
from backend.app.infrastructure.backtest.replay_data import (  # noqa: E402
    fetch_history,
    fetch_regime_frames,
    load_universe,
)


def build_variants() -> list[dict]:
    base = load_screen_mix()

    def clone(mix: dict) -> dict:
        return {key: [dict(item) for item in items] for key, items in mix.items()}

    choppy_meanrev = clone(base)
    choppy_meanrev["choppy"] = [dict(item) for item in base["ranging"]]

    # Post-hoc refinement of experiment 2: on choppy days the full "ranging"
    # menu brought two losers along (smr and low-vol are strongly negative on
    # choppy days), while mean-reversion was positive. This variant tests that
    # single-screen choppy menu. In-sample hypothesis refinement — not proof.
    choppy_mr_only = clone(base)
    choppy_mr_only["choppy"] = [
        {**item, "rank": index + 1}
        for index, item in enumerate(
            [entry for entry in base["ranging"] if entry["stem"] == "mean-reversion"]
        )
    ]

    return [
        {"name": "baseline", "params": ReplayParams(window_days=60), "mix": base},
        {
            "name": "choppy_meanrev",
            "params": ReplayParams(window_days=60),
            "mix": choppy_meanrev,
        },
        {
            "name": "wide_target_4.5",
            "params": ReplayParams(window_days=60, target_atr_mult=4.5),
            "mix": base,
        },
        {
            "name": "choppy_meanrev+wide_target",
            "params": ReplayParams(window_days=60, target_atr_mult=4.5),
            "mix": choppy_meanrev,
        },
        {
            "name": "choppy_meanrev_only",
            "params": ReplayParams(window_days=60),
            "mix": choppy_mr_only,
        },
    ]


def _flat_summary(result) -> dict:
    rows = result.rows
    summary = result.summary
    choppy = [row for row in rows if row.get("regime_key") == "choppy"]
    choppy_pnl = sum(float(row["pnl_usd"]) for row in choppy)
    choppy_exp = (
        sum(float(row["realized_r"]) for row in choppy) / len(choppy) if choppy else None
    )
    total_pnl = float(summary["pnl_usd"])
    return {
        "trades": summary["trades"],
        "wins": summary["wins"],
        "losses": summary["losses"],
        "win_rate": summary["win_rate"],
        "expectancy_r": summary["expectancy_r"],
        "profit_factor_r": summary["profit_factor_r"],
        "pnl_usd": total_pnl,
        "avg_win_r": summary["avg_win_r"],
        "avg_loss_r": summary["avg_loss_r"],
        "exit_mix": dict(Counter(row["exit_reason"] for row in rows)),
        "choppy_trades": len(choppy),
        "choppy_expectancy_r": choppy_exp,
        "choppy_pnl_usd": choppy_pnl,
        "note_half_risk_choppy_pnl": (total_pnl - choppy_pnl) + 0.5 * choppy_pnl,
        "counts": result.run["metadata"]["counts"],
    }


async def main() -> int:
    parser = argparse.ArgumentParser(description="Replay what-if experiments (design learning).")
    parser.add_argument("--no-json", action="store_true", help="do not write the JSON artifact")
    parser.add_argument("--limit", type=int, default=0, help="use only the first N symbols (smoke test)")
    parser.add_argument("--only", default=None, help="run a single named variant")
    args = parser.parse_args()

    now = datetime.now(UTC)
    today = now.date()
    daily_start = (today - timedelta(days=760)).isoformat()
    hourly_start = (today - timedelta(days=200)).isoformat()
    end_date = today.isoformat()

    symbols = load_universe()
    if args.limit and args.limit > 0:
        symbols = symbols[: args.limit]
    print(f"Universe: {len(symbols)} symbols | daily lookback from {daily_start}", flush=True)
    print("Loading cached OHLCV (fetches only what is missing)...", flush=True)
    raw_daily, missing_daily = fetch_history(
        symbols, start=daily_start, end=end_date, interval="1d", progress=True
    )
    raw_hourly, missing_hourly = fetch_history(
        symbols, start=hourly_start, end=end_date, interval="1h", progress=True
    )
    regime_frames = fetch_regime_frames(start=daily_start, end=end_date)
    print(
        f"Loaded daily={len(raw_daily)} hourly={len(raw_hourly)} "
        f"missing d={len(missing_daily)} h={len(missing_hourly)}",
        flush=True,
    )

    variants = build_variants()
    if args.only:
        variants = [variant for variant in variants if variant["name"] == args.only]
        if not variants:
            parser.error(f"unknown variant {args.only!r}")

    records: list[dict] = []
    for variant in variants:
        print(f"\n=== variant: {variant['name']} ===", flush=True)
        result = await run_replay(
            variant["params"],
            daily=raw_daily,
            hourly=raw_hourly,
            regime_frames=regime_frames,
            screen_mix=variant["mix"],
            progress=True,
            now=now,
        )
        flat = _flat_summary(result)
        records.append(
            {
                "name": variant["name"],
                "params": asdict(variant["params"]),
                "flat": flat,
                "run": result.run,
                "summary": result.summary,
                "rows": result.rows,
            }
        )
        print(
            f"--> {variant['name']}: {flat['trades']} trades | W/L {flat['wins']}/{flat['losses']}"
            f" | WR {flat['win_rate'] * 100:.1f}% | exp {flat['expectancy_r']:+.3f}R"
            f" | PF {flat['profit_factor_r']:.2f} | P&L {flat['pnl_usd']:+,.0f}",
            flush=True,
        )

    print("\n" + "=" * 100)
    print("COMPARISON (design learning only — NOT forward evidence, NOT a P&L promise)")
    print("=" * 100)
    header = (
        f"{'variant':30} {'trades':>6} {'W/L':>9} {'WR':>6} {'expR':>7} "
        f"{'PF':>5} {'P&L $':>10} {'choppy n':>8} {'choppy expR':>11}"
    )
    print(header)
    print("-" * len(header))
    for rec in records:
        flat = rec["flat"]
        choppy_exp = flat["choppy_expectancy_r"]
        choppy_txt = f"{choppy_exp:+.3f}" if choppy_exp is not None else "n/a"
        print(
            f"{rec['name']:30} {flat['trades']:6d} "
            f"{str(flat['wins']) + '/' + str(flat['losses']):>9} "
            f"{flat['win_rate'] * 100:5.1f}% {flat['expectancy_r']:+7.3f} "
            f"{flat['profit_factor_r']:5.2f} {flat['pnl_usd']:+10,.0f} "
            f"{flat['choppy_trades']:8d} {choppy_txt:>11}"
        )
    print("-" * len(header))

    print("\nExit mix per variant:")
    for rec in records:
        print(f"  {rec['name']:30} {rec['flat']['exit_mix']}")

    print("\nPost-hoc: halving risk on choppy days scales only $ (R is unchanged):")
    for rec in records:
        flat = rec["flat"]
        print(
            f"  {rec['name']:30} P&L {flat['pnl_usd']:+,.0f} -> "
            f"{flat['note_half_risk_choppy_pnl']:+,.0f}"
        )

    if not args.no_json:
        out_dir = Path("docs/backtests")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"replay_whatif_{now.strftime('%Y%m%d_%H%M%S')}.json"
        out_path.write_text(
            json.dumps(records, indent=2, default=str), encoding="utf-8"
        )
        print(f"\nWrote {out_path}")

    print("\nNOTE: design-learning experiments on the same window — hypotheses, not proof.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
