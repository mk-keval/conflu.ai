"""Paper-trade replay runner — D-71 (v0.1) and H-09 (v0.2).

``--rules-version v0.1`` (default) reproduces the published D-71 screen replay:
the deployed templates over a broad liquid universe, entered at the next bar's
open and exited with the original ATR rules. Stored in a separate replay ledger
(``replay_runs`` / ``replay_trades``) that the Journal tab shows under "Replay".

``--rules-version v0.2`` runs H-09 (D-78): the **same signal stream** is planned
and exited twice — once with the reconstructed v0.1 rules and once with the
frozen Bundle A (v0.2) rules. Only the v0.2 accepted trades are stored in the
ledger; the JSON artifact keeps both arms for audit. The result is exploratory:
it never enters the forward scorecard, the D-75 pass bar, the kill rule,
``/expectancy`` or any v0.2 verdict.

Important: TradingView's screener cannot be rewound, so this replays the
templates + regime screen-selection logic — not the exact live brief. It is
simulated evidence and never counts toward the forward scorecard.

Usage:
  python run_paper_replay.py                          # D-71, 60d, deployed screens
  python run_paper_replay.py --days 30 --max-per-day 10
  python run_paper_replay.py --refresh-universe       # refresh the ticker list too
  python run_paper_replay.py --no-write               # print + JSON only, no DB

  # H-09 dry run (frozen window 2026-08-20 -> 2026-10-19; no DB write):
  python run_paper_replay.py --rules-version v0.2 --no-write
  # H-09 write (refused before 2026-11-24 unless --allow-censored):
  python run_paper_replay.py --rules-version v0.2
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, ".")

from backend.app.domain.workflow import replay_store  # noqa: E402
from backend.app.infrastructure.backtest import replay_rules  # noqa: E402
from backend.app.infrastructure.backtest.replay import (  # noqa: E402
    ReplayParams,
    run_replay,
)
from backend.app.infrastructure.backtest.replay_data import (  # noqa: E402
    refresh_sp500_universe,
)

# D-78 / H-09 plan §9: one frozen window. A different window is a new
# exploratory design and must be a dry run (the write gate enforces this).
H09_WINDOW_START = "2026-08-20"
H09_WINDOW_END = "2026-10-19"
H09_EARLIEST_FULL_RUN = "2026-11-24"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replay deployed screens (D-71 v0.1 or H-09 v0.2)."
    )
    parser.add_argument(
        "--rules-version",
        choices=list(replay_rules.RULES_VERSIONS),
        default=replay_rules.RULES_V01,
        help="v0.1 = published D-71 replay; v0.2 = H-09 two-arm exploratory replay",
    )
    parser.add_argument("--days", type=int, default=60, help="v0.1 replay window in calendar days")
    parser.add_argument("--window-start", default=None, help="explicit window start (YYYY-MM-DD)")
    parser.add_argument("--window-end", default=None, help="explicit window end (YYYY-MM-DD)")
    parser.add_argument(
        "--max-per-day",
        type=int,
        default=0,
        help="cap entries per day (0 = keep every deduped signal; H-09 requires 0)",
    )
    parser.add_argument("--risk-pct", type=float, default=1.0, help="risk per trade in %% of account")
    parser.add_argument("--account", type=float, default=100_000.0, help="hypothetical account value")
    parser.add_argument("--stop-atr", type=float, default=2.0, help="v0.1 engine stop / v0.2 plan stop")
    parser.add_argument("--target-atr", type=float, default=3.0, help="v0.1 engine target (frozen at 3.0 for H-09)")
    parser.add_argument("--max-hold", type=int, default=15, help="v0.1 engine swing cap (frozen at 15 for H-09)")
    parser.add_argument(
        "--entry-zone-atr",
        type=float,
        default=replay_rules.ENTRY_ZONE_ATR_MULT,
        help="H-09 entry-zone half-width in ATR (frozen 0.5)",
    )
    parser.add_argument(
        "--min-zone-pct",
        type=float,
        default=replay_rules.MIN_ZONE_PCT,
        help="H-09 minimum entry-zone width in %% (frozen 1.5)",
    )
    parser.add_argument(
        "--expiry-sessions",
        type=int,
        default=replay_rules.FILL_EXPIRY_SESSIONS,
        help="H-09 limit-fill expiry in sessions (frozen 3)",
    )
    parser.add_argument(
        "--v01-max-hold",
        type=int,
        default=replay_rules.V01_MAX_HOLD_DAYS,
        help="v0.1 arm calendar-day time stop (frozen 30)",
    )
    parser.add_argument(
        "--allow-censored",
        action="store_true",
        help="write an H-09 ledger before the 36-day data horizon (eod rows stay excluded)",
    )
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


def _print_v01_report(run: dict[str, Any], summary: dict[str, Any], args: argparse.Namespace) -> None:
    counts = run["metadata"]["counts"]
    print(
        f"Signals: raw={counts['raw_signals']} -> regime-gated={counts['after_regime_gate']} "
        f"-> deduped={counts['after_dedupe']} -> rows={counts['rows']}"
    )
    print(f"Regime days: {run['metadata']['regime_days']}")
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


def _print_arm_line(label: str, stats: dict[str, Any]) -> None:
    print(
        f"{label:22} {stats['trades']:5d} {stats['win_rate'] * 100:5.1f}% "
        f"{stats['expectancy_r']:+7.3f} {_fmt_pf(stats['profit_factor_r'])} "
        f"{stats['avg_win_r']:+6.2f}R {stats['avg_loss_r']:+6.2f}R "
        f"{stats['pnl_usd']:+10,.0f} {stats['censored']:3d}"
    )


def _print_h09_report(run: dict[str, Any], summary: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    meta = run["metadata"]["h09"] or {}
    funnel = meta.get("funnel") or {}
    horizon = run["metadata"]["data_horizon"]
    design = meta.get("design") or {}

    print("\nH-09 EXPLORATORY ONLY — exploratory_h09_not_evidence")
    print(
        "Same signal stream, entry zone, stop and fills; the arms differ only in "
        "targets, the gate floor and the exit policy."
    )
    print(
        f"Funnel: deduped={funnel.get('deduped', 0)} orders={funnel.get('orders', 0)} "
        f"filled={funnel.get('filled', 0)} expired={funnel.get('expired', 0)} "
        f"gap-cancelled={funnel.get('cancelled_gap', 0)} "
        f"geometry-invalid={funnel.get('geometry_invalid', 0)}"
    )
    print(
        f"Data horizon: {horizon['days']}d past window_end "
        f"({horizon['required_days']}d required) — "
        f"{'OK' if horizon['ok'] else 'CENSORED / early'}"
    )
    print(
        f"v0.2 rejected={funnel.get('v02_rejected', 0)} reasons={funnel.get('v02_rejected_reasons', {})} "
        f"gate-failed={funnel.get('v02_gated_out', 0)} accepted={funnel.get('v02_accepted', 0)} "
        f"closed={funnel.get('v02_closed', 0)} eod={funnel.get('v02_eod', 0)}"
    )
    if design.get("deviations"):
        print(f"DESIGN DEVIATIONS: {design['deviations']} (write refused)")
    print()

    header = (
        f"{'arm':22} {'n':>5} {'win%':>6} {'exp_r':>7} {'PF':>6} "
        f"{'avgW':>7} {'avgL':>7} {'P&L$':>10} {'eod':>3}"
    )
    print(header)
    print("-" * len(header))
    arms = meta.get("arm_summaries") or {}
    _print_arm_line("v0.1 all filled", arms.get("v01") or {})
    _print_arm_line("v0.1 accepted", arms.get("v01_accepted") or {})
    _print_arm_line("v0.2 all filled", arms.get("v02") or {})
    _print_arm_line("v0.2 accepted", arms.get("v02_accepted") or {})
    _print_arm_line("v0.2 accepted (closed)", arms.get("v02_accepted_closed") or {})
    print("-" * len(header))

    delta = meta.get("delta") or {}
    exit_only = delta.get("exit_only") or {}
    print(
        f"Exit-only delta on {exit_only.get('n_paired', 0)} paired exits: "
        f"v0.1 {exit_only.get('v01', {}).get('expectancy_r', 0.0):+.3f}R vs "
        f"v0.2 {exit_only.get('v02', {}).get('expectancy_r', 0.0):+.3f}R"
    )
    policy = delta.get("policy") or {}
    print(
        f"Policy delta (each arm's accepted book): "
        f"v0.1 {policy.get('v01', {}).get('trades', 0)} trades "
        f"{policy.get('v01', {}).get('expectancy_r', 0.0):+.3f}R vs "
        f"v0.2 {policy.get('v02', {}).get('trades', 0)} trades "
        f"{policy.get('v02', {}).get('expectancy_r', 0.0):+.3f}R"
    )
    rejected = (delta.get("rejection_quality") or {}).get("v02_rejected") or {}
    print(
        f"Rejected-plan quality: n={rejected.get('n', 0)}, v0.1 counterfactual "
        f"{rejected.get('v01_counterfactual', {}).get('expectancy_r', 0.0):+.3f}R"
    )
    print(f"Family mix (accepted closed): {summary.get('family_mix', {})}")
    unknown = meta.get("unknown_screens") or []
    if unknown:
        print(f"Unknown-family screens (live display-name map, G11): {', '.join(unknown)}")
    print(
        f"Primary aggregate excludes {summary.get('censored_excluded', 0)} eod row(s); "
        f"all-accepted view: {summary.get('all_accepted', {}).get('trades', 0)} trades, "
        f"{summary.get('all_accepted', {}).get('expectancy_r', 0.0):+.3f}R"
    )


async def main() -> None:
    args = _parse_args()

    h09 = args.rules_version == replay_rules.RULES_V02
    if h09 and args.max_per_day:
        raise SystemExit(
            "H-09 requires --max-per-day 0: the replay has no portfolio caps (D-78)."
        )

    window_start = args.window_start
    window_end = args.window_end
    if h09:
        window_start = window_start or H09_WINDOW_START
        window_end = window_end or H09_WINDOW_END
        if args.target_atr != replay_rules.SIGNAL_TARGET_ATR_MULT or args.max_hold != replay_rules.SIGNAL_MAX_HOLD_BARS:
            print(
                "NOTE: H-09 freezes the signal engine at "
                f"{replay_rules.SIGNAL_STOP_ATR_MULT:g}/"
                f"{replay_rules.SIGNAL_TARGET_ATR_MULT:g} ATR and "
                f"{replay_rules.SIGNAL_MAX_HOLD_BARS} bars; --target-atr/--max-hold "
                "are ignored (the stream must not move)."
            )

    if args.refresh_universe:
        symbols = refresh_sp500_universe(args.universe_file)
        print(f"Refreshed universe: {len(symbols)} symbols")

    params = ReplayParams(
        window_days=args.days,
        window_start=window_start,
        window_end=window_end,
        rules_version=args.rules_version,
        stop_atr_mult=args.stop_atr,
        target_atr_mult=args.target_atr,
        max_hold_bars=args.max_hold,
        entry_zone_atr_mult=args.entry_zone_atr,
        min_zone_pct=args.min_zone_pct,
        fill_expiry_sessions=args.expiry_sessions,
        v01_max_hold_days=args.v01_max_hold,
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
    label = "H-09 EXPLORATORY" if h09 else "D-71"
    print(
        f"REPLAY [{args.rules_version} / {label}] {run['window_start']} -> {run['window_end']} "
        f"| {run['templates_count']} deployed screens | {run['universe_count']} symbols"
    )
    print("=" * 92)
    if h09:
        _print_h09_report(run, summary, rows)
    else:
        _print_v01_report(run, summary, args)

    if not args.no_json:
        out_dir = Path("docs/backtests")
        out_dir.mkdir(parents=True, exist_ok=True)
        stem = "h09_replay" if h09 else "replay"
        out_path = out_dir / f"{stem}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
        payload: dict[str, Any] = {"run": run, "rows": rows}
        if result.artifacts:
            payload.update(result.artifacts)
        out_path.write_text(
            json.dumps(payload, indent=2, default=str), encoding="utf-8"
        )
        print(f"\nWrote {out_path}")

    if not args.no_write:
        blockers: list[str] = []
        if h09:
            horizon = run["metadata"]["data_horizon"]
            if not horizon["ok"] and not args.allow_censored:
                blockers.append(
                    f"data horizon is {horizon['days']} days past window_end "
                    f"(need {horizon['required_days']}); the earliest full D-71 "
                    f"window run is {H09_EARLIEST_FULL_RUN}"
                )
            design = (run["metadata"].get("h09") or {}).get("design") or {}
            if design.get("deviations"):
                blockers.append(
                    "frozen-design deviation: " + ", ".join(design["deviations"])
                )
            if (run["window_start"], run["window_end"]) != (
                H09_WINDOW_START,
                H09_WINDOW_END,
            ):
                blockers.append(
                    f"window {run['window_start']}..{run['window_end']} is not the "
                    f"frozen {H09_WINDOW_START}..{H09_WINDOW_END}"
                )
        if blockers:
            print("\nREFUSED to write the replay ledger:")
            for reason in blockers:
                print(f"  - {reason}")
            print("The JSON artifact was still written. Re-run with --no-write for a dry run.")
            raise SystemExit(2)

        if h09:
            horizon = run["metadata"]["data_horizon"]
            if not horizon["ok"]:
                run["metadata"]["write_consent"] = {
                    "allow_censored": True,
                    "horizon_days": horizon["days"],
                    "required_days": horizon["required_days"],
                    "note": (
                        "Written before the 36-day data horizon. eod rows stay "
                        "excluded from the primary aggregate."
                    ),
                }
        run_id = replay_store.replace_run(run, rows)
        print(
            f"Stored replay run #{run_id} in data/paper_trades.db "
            f"(replay_runs / replay_trades) — view it in Workflow -> Journal -> Replay."
        )

    if h09:
        print(
            "\nNOTE: exploratory H-09 replay (exploratory_h09_not_evidence) — never "
            "forward evidence, never the D-75 pass bar or kill rule."
        )
    else:
        print("\nNOTE: simulated screen replay, not forward evidence.")


if __name__ == "__main__":
    asyncio.run(main())
