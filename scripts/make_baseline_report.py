#!/usr/bin/env python
"""Build BASELINE_REPORT.md from research backtest artifacts.

Standard library only. Reads the newest artifact per setup directly inside
``--dir`` (sub-folders are ignored) and writes ``BASELINE_REPORT.md`` there.

Statistics use closed trades only (``censored == False``) with
``exit_date >= 2016-01-01``; 2015 is warm-up.
"""

import argparse
import glob
import json
import math
import os
import random
import statistics
from datetime import datetime

WARNING = (
    "Universe = today's S&P 500 members. Survivorship bias flatters old results. "
    "In-sample, no walk-forward. Not evidence of a live edge."
)

CONTROL_NOTE = (
    "The p-value is the fraction of matched-random controls that do at least as "
    "well as the real strategy (`mean(control >= real)`), with the finite-sample "
    "correction `(p_raw*n + 1)/(n + 1)`; it is never direction-flipped for "
    "negative results."
)


def load_newest(dirpath):
    """Newest artifact (by ``timestamp``) per setup, skipping files without run_info."""
    newest = {}
    paths = sorted(glob.glob(os.path.join(dirpath, "*.json")))
    for path in paths:
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                payload = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"WARNING: skipping unreadable {os.path.basename(path)}: {exc}")
            continue
        if "run_info" not in payload:
            print(f"WARNING: skipping {os.path.basename(path)} (no run_info)")
            continue
        setup = payload.get("setup") or os.path.basename(path).split("_20")[0]
        stamp = str(payload.get("timestamp", ""))
        if setup not in newest or stamp > newest[setup][0]:
            newest[setup] = (stamp, path, payload)
    return {setup: (path, payload) for setup, (_, path, payload) in newest.items()}


def bootstrap_ci(values, n_resamples=2000, seed=42):
    """95% percentile bootstrap CI of the mean."""
    if len(values) < 2:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    size = len(values)
    means = []
    for _ in range(n_resamples):
        sample = [values[rng.randrange(size)] for _ in range(size)]
        means.append(sum(sample) / size)
    means.sort()
    low = means[int(0.025 * n_resamples)]
    high = means[int(0.975 * n_resamples) - 1]
    return (low, high)


def trade_stats(payload, since="2016-01-01"):
    """Trade-level statistics from closed trades with exit_date >= since."""
    all_trades = payload.get("trades", [])
    trades = [
        t
        for t in all_trades
        if not t.get("censored", False) and str(t.get("exit_date", "")) >= since
    ]
    n = len(trades)
    r = [float(t["r_net"]) for t in trades]
    wins = [x for x in r if x > 0]
    losses = [x for x in r if x < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(x for x in r if x <= 0))

    return {
        "n": n,
        "win_rate": (len(wins) / n) if n else 0.0,
        "avg_win_r": statistics.mean(wins) if wins else 0.0,
        "avg_loss_r": statistics.mean(losses) if losses else 0.0,
        "expectancy_net": statistics.mean(r) if n else 0.0,
        "ci95": bootstrap_ci(r),
        "expectancy_gross": (
            statistics.mean(float(t["r_gross"]) for t in trades) if n else 0.0
        ),
        "profit_factor": (gross_profit / gross_loss) if gross_loss > 0 else float("inf"),
        "stop_gap_share": (
            sum(1 for t in trades if t.get("exit_reason") == "stop_gap") / n
            if n
            else 0.0
        ),
        "data_end_count": sum(
            1 for t in all_trades if t.get("exit_reason") == "data_end"
        ),
        "trades": trades,
    }


def account_stats(payload, start_equity):
    """CAGR, max drawdown and the cash reconciliation check from the equity curve."""
    curve = payload.get("equity_curve", [])
    values = [float(point["equity"]) for point in curve]
    if len(values) < 2:
        return {"cagr": 0.0, "max_dd": 0.0, "final": values[-1] if values else 0.0}

    final = values[-1]
    years = len(values) / 252.0
    cagr = ((final / start_equity) ** (1 / years) - 1) if years > 0 and start_equity else 0.0

    peak = values[0]
    max_dd = 0.0
    for value in values:
        peak = max(peak, value)
        max_dd = min(max_dd, value / peak - 1.0)

    expected = start_equity + sum(
        float(t["pnl_usd"]) for t in payload.get("trades", [])
    )
    return {
        "cagr": cagr,
        "max_dd": max_dd,
        "final": final,
        "expected": expected,
        "reconciles": abs(final - expected) <= 1.0,
    }


def per_year_stats(trades):
    """Per exit-year n, expectancy_net and profit factor (2016+)."""
    buckets = {}
    for t in trades:
        year = str(t.get("exit_date", ""))[:4]
        if not year.isdigit() or int(year) < 2016:
            continue
        buckets.setdefault(int(year), []).append(float(t["r_net"]))

    rows = []
    for year in sorted(buckets):
        r = buckets[year]
        gross_profit = sum(x for x in r if x > 0)
        gross_loss = abs(sum(x for x in r if x <= 0))
        rows.append(
            {
                "year": year,
                "n": len(r),
                "expectancy_net": statistics.mean(r),
                "profit_factor": (
                    gross_profit / gross_loss if gross_loss > 0 else float("inf")
                ),
            }
        )
    return rows


def _fmt(value, digits=2):
    if value is None:
        return "n/a"
    if isinstance(value, float):
        if math.isnan(value):
            return "n/a"
        if math.isinf(value):
            return "inf"
        return f"{value:.{digits}f}"
    return str(value)


def _pct(value, digits=1):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "n/a"
    return f"{value * 100:.{digits}f}%"


def verdict(row, stats, per_year):
    """Apply the pre-registered verdict rules verbatim. No opinions."""
    if stats["n"] < 100:
        return "INSUFFICIENT SAMPLE"

    if (
        not row["account"]["reconciles"]
        or stats["profit_factor"] > 2.5
        or stats["win_rate"] > 0.65
        or row["account"]["max_dd"] < -0.40
    ):
        return "SUSPECTED BUG investigate before trusting"

    p = row["p_matched"]
    qualifying = [y for y in per_year if y["n"] >= 10]
    profitable = sum(1 for y in qualifying if y["expectancy_net"] > 0)
    share = profitable / len(qualifying) if qualifying else 0.0

    if (
        stats["ci95"][0] > 0
        and p is not None
        and p <= 0.05
        and qualifying
        and share >= 0.75
    ):
        return "CANDIDATE needs out-of-sample test"
    return "NO EVIDENCE OF EDGE"


def build_report(artifacts):
    lines = []
    add = lines.append

    first = next(iter(artifacts.values()))[1] if artifacts else {}
    run_info = first.get("run_info", {})
    portfolio = run_info.get("portfolio_rules", {})
    exits = run_info.get("exit_rules", {})

    add("# Research Baseline Report")
    add("")
    add(f"- Run date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    add(f"- Git commit: `{run_info.get('git_commit', 'unknown')}`")
    add(f"- Window: {run_info.get('start', 'n/a')} -> {run_info.get('end', 'n/a')}")
    add(f"- Symbols used: {run_info.get('n_symbols_used', 'n/a')}")
    add(f"- Dropped symbols: {len(run_info.get('dropped', []))}")
    add(
        "- Costs: {cost} bps per side".format(
            cost=portfolio.get("cost_bps_per_side", "n/a")
        )
    )
    add(
        "- Exit rules: stop {stop} ATR, target {target} ATR, max hold {hold} bars".format(
            stop=exits.get("stop_atr", "n/a"),
            target=exits.get("target_atr", "n/a"),
            hold=exits.get("max_hold_bars", "n/a"),
        )
    )
    add(
        "- Portfolio rules: start equity {eq}, risk {risk}%/trade, max {pos} positions, "
        "max position {pct}% of equity".format(
            eq=portfolio.get("start_equity", "n/a"),
            risk=portfolio.get("risk_pct", "n/a"),
            pos=portfolio.get("max_positions", "n/a"),
            pct=portfolio.get("max_position_pct", "n/a"),
        )
    )
    add("")
    add(f"> **{WARNING}**")
    add("")

    # Per-setup statistics first (the main table needs them).
    rows = []
    for setup in sorted(artifacts):
        path, payload = artifacts[setup]
        info = payload.get("run_info", {})
        start_equity = float(
            info.get("portfolio_rules", {}).get("start_equity", 100_000.0)
        )
        stats = trade_stats(payload)
        account = account_stats(payload, start_equity)
        years = per_year_stats(stats["trades"])
        controls = payload.get("control_summary", {}).get("matched_random", {})
        p_values = payload.get("p_values", {})
        rows.append(
            {
                "setup": setup,
                "path": path,
                "payload": payload,
                "stats": stats,
                "account": account,
                "years": years,
                "controls": controls,
                "p_matched": p_values.get("matched_random"),
                "run_info": info,
            }
        )

    add("## Main table")
    add("")
    add(
        "| Setup | n | Win rate | Avg win R | Avg loss R | Expectancy net | 95% CI | "
        "Expectancy gross | PF | CAGR | Max DD | Reconciliation |"
    )
    add("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for row in rows:
        s = row["stats"]
        a = row["account"]
        ci = f"[{_fmt(s['ci95'][0], 3)}, {_fmt(s['ci95'][1], 3)}]"
        add(
            f"| {row['setup']} | {s['n']} | {_pct(s['win_rate'])} | "
            f"{_fmt(s['avg_win_r'], 3)} | {_fmt(s['avg_loss_r'], 3)} | "
            f"{_fmt(s['expectancy_net'], 3)} | {ci} | "
            f"{_fmt(s['expectancy_gross'], 3)} | {_fmt(s['profit_factor'])} | "
            f"{_pct(a['cagr'])} | {_pct(a['max_dd'])} | "
            f"{'PASS' if a['reconciles'] else 'FAIL'} |"
        )
    add("")

    add("## Per-year tables")
    for row in rows:
        add("")
        add(f"### {row['setup']}")
        add("")
        add("| Year | n | Expectancy net | PF |")
        add("|---|---|---|---|")
        for year in row["years"]:
            add(
                f"| {year['year']} | {year['n']} | "
                f"{_fmt(year['expectancy_net'], 3)} | "
                f"{_fmt(year['profit_factor'])} |"
            )
        if not row["years"]:
            add("| n/a | 0 | n/a | n/a |")
    add("")

    add("## Control comparison")
    add("")
    add(
        "| Setup | Control runs | Control trades (mean) | Control expectancy (mean +/- std) | "
        "Strategy expectancy | p (matched_random) |"
    )
    add("|---|---|---|---|---|---|")
    for row in rows:
        controls = row["controls"]
        p = row["p_matched"]
        add(
            f"| {row['setup']} | {controls.get('n_runs', 0)} | "
            f"{_fmt(controls.get('n_trades_mean'), 1)} | "
            f"{_fmt(controls.get('r_net_mean_mean'), 3)} +/- "
            f"{_fmt(controls.get('r_net_mean_std'), 3)} | "
            f"{_fmt(row['stats']['expectancy_net'], 3)} | "
            f"{_fmt(p, 4)} |"
        )
    add("")
    add(CONTROL_NOTE)
    add("")

    add("## Sanity checks")
    add("")
    for row in rows:
        s = row["stats"]
        a = row["account"]
        info = row["run_info"]
        max_hold = info.get("exit_rules", {}).get("max_hold_bars")
        trades = row["payload"].get("trades", [])
        no_lookahead = all(
            str(t.get("entry_date", "")) > str(t.get("signal_date", ""))
            for t in trades
        )
        max_bars = max((int(t.get("bars_held", 0)) for t in trades), default=0)
        hold_ok = max_hold is None or max_bars <= int(max_hold)
        coverage = info.get("n_symbols_ending_early")
        if coverage is None:
            # D-80 artifacts record this under run.panel, not run_info.
            coverage = row["payload"].get("run", {}).get("panel", {}).get(
                "n_symbols_ending_early", "n/a"
            )
        add(f"### {row['setup']}")
        add("")
        add(f"- Reconciliation: {'PASS' if a['reconciles'] else 'FAIL'}")
        add(f"- No trade enters on or before its signal: {'PASS' if no_lookahead else 'FAIL'}")
        add(f"- Max bars held <= max_hold ({max_hold}): {'PASS' if hold_ok else 'FAIL'} (max {max_bars})")
        add(f"- Stop-gap share: {_pct(s['stop_gap_share'])}")
        add(f"- data_end trades: {s['data_end_count']} (info)")
        add(f"- data-coverage early_end: {coverage}")
        add("")

    add("## Deviations")
    add("")
    add(
        "- Trade statistics exclude censored trades (`data_end` / `eod_censored`) and "
        "anything exiting before 2016-01-01 (2015 is warm-up)."
    )
    add("- `expectancy_gross` and `expectancy_net` are per-trade R averages.")
    add("- The p-value metric is per-trade expectancy (`r_net_mean`), not R sum.")
    add(
        "- The matched-random control fires the same number of entries per day as the "
        "strategy, on random liquid symbols with valid indicators."
    )
    add(
        "- Artifacts without `run_info` are ignored; older artifacts are quarantined in "
        "`invalid_20261110/`."
    )
    add("")

    add("## Verdict")
    add("")
    for row in rows:
        add(f"- **{row['setup']}**: {verdict(row, row['stats'], row['years'])}")

    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Build the research baseline report")
    parser.add_argument("--dir", default="docs/backtests/research",
                        help="Directory containing the artifacts")
    args = parser.parse_args()

    artifacts = load_newest(args.dir)
    if not artifacts:
        raise SystemExit(f"No artifacts with run_info found in {args.dir}")

    report = build_report(artifacts)
    out_path = os.path.join(args.dir, "BASELINE_REPORT.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Wrote {out_path} ({len(artifacts)} setups)")


if __name__ == "__main__":
    main()
