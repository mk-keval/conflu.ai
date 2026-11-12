#!/usr/bin/env python
"""Read-only diagnostics for the research baseline harness (D-82 T1).

Loads one panel through the existing span-keyed cache, builds each setup's
signals, and reports:

  (a) seed sensitivity of the candidate shuffle;
  (b) cost sensitivity across 0 / 7.5 / 15 / 30 bps per side;
  (c) a data-integrity scan of the loaded panel plus every artifact trade that
      touches a flagged bar;
  (d) exit mix and win rate for the strategy versus a matched-random control.

Writes ``docs/backtests/research/DIAGNOSTICS.md``. It does not change the
engine, the setups or any artifact.

Usage:
    python scripts/research_diagnostics.py --setups breakout_52week,low_vol_setup
    python scripts/research_diagnostics.py --seeds 42-51
"""

import argparse
import glob
import json
import sys
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.research.control import matched_random_signals
from backend.app.research.data import download_daily, load_universe, panel_span
from backend.app.research.engine import (
    NON_TRADABLE,
    ExitRules,
    PortfolioRules,
    run_portfolio,
)
from backend.app.research.indicators import add_indicators
from backend.app.research.metrics import compute_metrics
from backend.app.research.setups import SETUPS, eligible

EVAL_START = "2016-01-01"
COST_LEVELS = [0.0, 7.5, 15.0, 30.0]
MATCHED_SEEDS = [30042, 30043, 30044, 30045, 30046]
EXIT_REASONS = ["stop", "stop_gap", "target", "target_gap", "time"]


# ---------------------------------------------------------------------------
# Pure helpers (unit-tested)
# ---------------------------------------------------------------------------

def window_trades(trades, since=EVAL_START):
    """Uncensored trades whose exit date is on or after ``since``."""
    since_ts = pd.Timestamp(since)
    return [
        t for t in trades
        if not t.censored and pd.Timestamp(t.exit_date) >= since_ts
    ]


def r_net_stats(trades, since=EVAL_START):
    """n / mean / std / min / max of net R over the evaluation window."""
    values = np.array([t.r_net for t in window_trades(trades, since)], dtype=float)
    if values.size == 0:
        return {"n": 0, "mean": 0.0, "std": 0.0, "min": 0.0, "max": 0.0}
    return {
        "n": int(values.size),
        "mean": float(np.mean(values)),
        "std": float(np.std(values)),
        "min": float(np.min(values)),
        "max": float(np.max(values)),
    }


def interpolate_zero_crossing(xs, ys):
    """Cost level where ``ys`` crosses zero, by linear interpolation.

    Returns ``None`` when no adjacent pair changes sign (a flat zero is
    treated as a crossing at that x).
    """
    if len(xs) != len(ys):
        raise ValueError("xs and ys must have equal length")
    for i in range(len(xs) - 1):
        y0, y1 = float(ys[i]), float(ys[i + 1])
        if y0 == 0.0:
            return float(xs[i])
        if (y0 > 0) != (y1 > 0):
            return float(xs[i] + (0.0 - y0) * (xs[i + 1] - xs[i]) / (y1 - y0))
    if ys and float(ys[-1]) == 0.0:
        return float(xs[-1])
    return None


def integrity_flags(df):
    """Count data-quality flags on one OHLCV frame.

    Returns a dict of counts plus ``flagged_bars`` (bars with any bar-level
    flag) and ``bars``. Duplicate dates and gaps are index-level counts.
    """
    n = len(df)
    if n == 0:
        return {
            "bars": 0, "flagged_bars": 0, "ret_gt_40pct": 0, "high_lt_low": 0,
            "ohlc_out_of_range": 0, "nonpositive_price": 0, "zero_volume": 0,
            "duplicate_dates": 0, "gap_gt_5bd": 0,
        }

    close = df["close"]
    ret = close.pct_change()
    ret_flag = ret.abs() > 0.40
    ret_flag = ret_flag.fillna(False)

    high_lt_low = df["high"] < df["low"]

    out_of_range = (
        (df["open"] < df["low"]) | (df["open"] > df["high"])
        | (close < df["low"]) | (close > df["high"])
    )

    nonpositive = (df[["open", "high", "low", "close"]] <= 0).any(axis=1)

    zero_volume = df["volume"] == 0

    bar_mask = ret_flag | high_lt_low | out_of_range | nonpositive | zero_volume

    duplicate_dates = int(df.index.duplicated().sum())

    gap_gt_5bd = 0
    if n > 1:
        dates = df.index.to_numpy()
        for prev, nxt in zip(dates[:-1], dates[1:]):
            if np.busday_count(prev.astype("datetime64[D]"), nxt.astype("datetime64[D]")) > 5:
                gap_gt_5bd += 1

    return {
        "bars": int(n),
        "flagged_bars": int(bar_mask.sum()),
        "ret_gt_40pct": int(ret_flag.sum()),
        "high_lt_low": int(high_lt_low.sum()),
        "ohlc_out_of_range": int(out_of_range.sum()),
        "nonpositive_price": int(nonpositive.sum()),
        "zero_volume": int(zero_volume.sum()),
        "duplicate_dates": duplicate_dates,
        "gap_gt_5bd": gap_gt_5bd,
    }


def exit_mix(trades, since=EVAL_START):
    """Win rate, exit-reason shares and mean bars held in the window."""
    closed = window_trades(trades, since)
    n = len(closed)
    if n == 0:
        out = {"n": 0, "win_rate": 0.0, "mean_bars_held": 0.0}
        out.update({reason: 0.0 for reason in EXIT_REASONS})
        return out

    out = {
        "n": n,
        "win_rate": float(sum(1 for t in closed if t.r_net > 0) / n),
        "mean_bars_held": float(np.mean([t.bars_held for t in closed])),
    }
    for reason in EXIT_REASONS:
        out[reason] = float(sum(1 for t in closed if t.exit_reason == reason) / n)
    return out


# ---------------------------------------------------------------------------
# Data / signal preparation
# ---------------------------------------------------------------------------

def load_panel(start, end, cache_dir, max_cache_age_hours):
    """Load the universe plus benchmarks from the existing span-keyed cache."""
    symbols = load_universe("config/replay_universe_sp500.txt")
    if "SPY" not in symbols:
        symbols.append("SPY")
    data, dropped, stats = download_daily(
        symbols, start, end, cache_dir, max_age_hours=max_cache_age_hours,
    )
    for symbol, df in data.items():
        data[symbol] = add_indicators(df)
    actual_start, actual_end = panel_span(data)
    print(
        f"Panel: {len(data)} symbols, {actual_start.date()} -> {actual_end.date()}, "
        f"cache hits={stats['hits']} downloads={stats['downloaded']} failed={stats['failed']}"
    )
    return data, dropped, stats, actual_start, actual_end


def build_signals(data, setup_name):
    """Signals for one setup, using the same eligibility gate as the runner."""
    setup_fn = SETUPS[setup_name]
    signals = {}
    for symbol, df in data.items():
        if symbol in NON_TRADABLE:
            signals[symbol] = pd.Series(False, index=df.index)
            continue
        if not eligible(df).any():
            signals[symbol] = pd.Series(False, index=df.index)
            continue
        signals[symbol] = setup_fn(df)
    return signals


def build_eligibility(data):
    """Eligibility frame (dates x tradable symbols), built once per panel."""
    tradable = sorted(s for s in data if s not in NON_TRADABLE)
    union = pd.DatetimeIndex(sorted({d for s in tradable for d in data[s].index}))
    return pd.DataFrame(
        {
            s: eligible(data[s]).reindex(union, fill_value=False).astype(bool)
            for s in tradable
        },
        index=union,
    )


def newest_artifact(output_dir, setup_name):
    """Newest top-level artifact for a setup, or None."""
    paths = glob.glob(str(Path(output_dir) / f"{setup_name}_*.json"))
    best = None
    best_ts = ""
    for path in paths:
        try:
            with open(path, encoding="utf-8") as f:
                payload = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        ts = str(payload.get("timestamp", ""))
        if ts > best_ts:
            best_ts = ts
            best = payload
            best["_path"] = path
    return best


# ---------------------------------------------------------------------------
# Analyses
# ---------------------------------------------------------------------------

def analyze_seeds(data, signals, exit_rules, portfolio_rules, seeds):
    """(a) Distribution of windowed net expectancy across candidate seeds."""
    rows = []
    for seed in seeds:
        trades, _ = run_portfolio(data, signals, exit_rules, portfolio_rules, seed=seed)
        stats = r_net_stats(trades)
        rows.append({"seed": seed, **stats})
        print(f"    seed {seed}: n={stats['n']} mean={stats['mean']:+.4f}")
    means = np.array([r["mean"] for r in rows], dtype=float)
    return {
        "rows": rows,
        "n_seeds": len(rows),
        "mean": float(np.mean(means)),
        "std": float(np.std(means)),
        "min": float(np.min(means)),
        "max": float(np.max(means)),
    }


def analyze_costs(data, signals, exit_rules, portfolio_rules):
    """(b) Metrics per cost level and the zero-crossing cost."""
    rows = []
    for cost in COST_LEVELS:
        rules = replace(portfolio_rules, cost_bps_per_side=cost)
        trades, equity = run_portfolio(data, signals, exit_rules, rules, seed=42)
        windowed = window_trades(trades)
        metrics = compute_metrics(trades, equity, start_equity=rules.start_equity)
        rows.append({
            "cost": float(cost),
            "n": len(windowed),
            "expectancy_net": float(np.mean([t.r_net for t in windowed])) if windowed else 0.0,
            "expectancy_gross": float(np.mean([t.r_gross for t in windowed])) if windowed else 0.0,
            "cagr": float(metrics.cagr),
            "max_drawdown_pct": float(metrics.max_drawdown_pct),
        })
        print(
            f"    cost {cost:>4} bps: n={len(windowed)} "
            f"exp_net={rows[-1]['expectancy_net']:+.4f}"
        )
    crossing = interpolate_zero_crossing(
        [r["cost"] for r in rows], [r["expectancy_net"] for r in rows]
    )
    return {"rows": rows, "zero_crossing": crossing}


def flagged_dates_by_symbol(data):
    """Map symbol -> sorted list of dates whose bar has any integrity flag."""
    flagged = {}
    for symbol, df in data.items():
        if symbol in NON_TRADABLE or not len(df):
            continue
        close = df["close"]
        ret_flag = (close.pct_change().abs() > 0.40).fillna(False)
        mask = (
            ret_flag
            | (df["high"] < df["low"])
            | (df["open"] < df["low"]) | (df["open"] > df["high"])
            | (close < df["low"]) | (close > df["high"])
            | (df[["open", "high", "low", "close"]] <= 0).any(axis=1)
            | (df["volume"] == 0)
        )
        dates = df.index[mask.to_numpy(dtype=bool)]
        if len(dates):
            flagged[symbol] = dates
    return flagged


def analyze_integrity(data, setups, output_dir):
    """(c) Panel-wide integrity counts, worst symbols, artifact trades on flags."""
    per_symbol = {}
    for symbol, df in data.items():
        if symbol in NON_TRADABLE or not len(df):
            continue
        per_symbol[symbol] = integrity_flags(df)

    totals = {key: 0 for key in next(iter(per_symbol.values()))} if per_symbol else {}
    for flags in per_symbol.values():
        for key, value in flags.items():
            totals[key] = totals.get(key, 0) + value

    worst = sorted(
        per_symbol.items(), key=lambda kv: kv[1]["flagged_bars"], reverse=True,
    )[:20]

    flagged = flagged_dates_by_symbol(data)
    touched = []
    for setup in setups:
        artifact = newest_artifact(output_dir, setup)
        if artifact is None:
            continue
        for trade in artifact.get("trades", []):
            dates = flagged.get(trade["symbol"])
            if dates is None:
                continue
            entry = pd.Timestamp(trade["entry_date"])
            exit_ = pd.Timestamp(trade["exit_date"])
            hits = dates[(dates >= entry) & (dates <= exit_)]
            if len(hits):
                touched.append({
                    "setup": setup,
                    "symbol": trade["symbol"],
                    "entry_date": trade["entry_date"][:10],
                    "exit_date": trade["exit_date"][:10],
                    "exit_reason": trade["exit_reason"],
                    "flagged_bars": int(len(hits)),
                    "first_flag": hits[0].strftime("%Y-%m-%d"),
                })
    return {"totals": totals, "worst": worst, "touched": touched}


def analyze_exit_mix(data, signals, elig, exit_rules, portfolio_rules):
    """(d) Exit mix for the strategy and five matched-random control runs."""
    trades, _ = run_portfolio(data, signals, exit_rules, portfolio_rules, seed=42)
    strategy = exit_mix(trades)

    controls = []
    for seed in MATCHED_SEEDS:
        control_signals = matched_random_signals(data, signals, seed, elig=elig)
        control_trades, _ = run_portfolio(
            data, control_signals, exit_rules, portfolio_rules, seed=seed,
        )
        controls.append(exit_mix(control_trades))
        print(f"    matched seed {seed}: n={controls[-1]['n']}")

    keys = ["n", "win_rate", "mean_bars_held", *EXIT_REASONS]
    aggregate = {
        key: float(np.mean([c[key] for c in controls])) for key in keys
    }
    return {"strategy": strategy, "control_runs": controls, "control_mean": aggregate}


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def render_markdown(results, meta):
    """Render the diagnostics document. Numbers only, one neutral sentence each."""
    lines = [
        "# Research Baseline Diagnostics (D-82)",
        "",
        f"- Generated: {meta['generated_at']}",
        f"- Window: {meta['start']} -> {meta['end']} "
        f"(panel {meta['actual_start']} -> {meta['actual_end']})",
        f"- Setups: {', '.join(results['setups'])}",
        f"- Candidate seeds: {meta['seed_min']}..{meta['seed_max']} "
        f"({meta['n_seeds']} seeds)",
        f"- Evaluation window for trade statistics: exit date >= {EVAL_START} "
        f"and `censored == False`",
        "",
    ]

    lines += ["## (a) Seed sensitivity", ""]
    lines.append(
        "Each row re-runs the same signals with a different candidate-shuffle seed."
    )
    lines.append("")
    lines += [
        "| Setup | Seeds | Mean of r_net mean | Std | Min | Max | "
        "Matched-control std (newest artifact) |",
        "|---|---|---|---|---|---|---|",
    ]
    for setup in results["setups"]:
        seed = results["seed_sensitivity"][setup]
        artifact = results["artifacts"][setup]
        control_std = "n/a"
        if artifact is not None:
            control_std = f"{artifact['control_summary']['matched_random']['r_net_mean_std']:.4f}"
        lines.append(
            f"| {setup} | {seed['n_seeds']} | {seed['mean']:+.4f} | {seed['std']:.4f} | "
            f"{seed['min']:+.4f} | {seed['max']:+.4f} | {control_std} |"
        )

    lines += ["", "## (b) Cost sensitivity", ""]
    lines.append("Per-side cost stepped over 0, 7.5, 15 and 30 bps on the same signals.")
    lines.append("")
    lines += [
        "| Setup | Cost bps/side | n | Expectancy net | Expectancy gross | CAGR % | Max DD % |",
        "|---|---|---|---|---|---|---|",
    ]
    for setup in results["setups"]:
        analysis = results["cost_sensitivity"][setup]
        for row in analysis["rows"]:
            lines.append(
                f"| {setup} | {row['cost']:g} | {row['n']} | {row['expectancy_net']:+.4f} | "
                f"{row['expectancy_gross']:+.4f} | {row['cagr']:+.2f} | "
                f"{row['max_drawdown_pct']:.2f} |"
            )
    lines += ["", "| Setup | Cost where expectancy_net crosses 0 |", "|---|---|"]
    for setup in results["setups"]:
        crossing = results["cost_sensitivity"][setup]["zero_crossing"]
        label = "not crossed" if crossing is None else f"{crossing:.2f} bps/side"
        lines.append(f"| {setup} | {label} |")

    lines += ["", "## (c) Data integrity scan", ""]
    lines.append("Counts are over every loaded tradable bar in the panel.")
    lines.append("")
    totals = results["integrity"]["totals"]
    lines += [
        "| Metric | Count |",
        "|---|---|",
        f"| Bars | {totals.get('bars', 0)} |",
        f"| Bars with any flag | {totals.get('flagged_bars', 0)} |",
        f"| |close-to-close return| > 40% | {totals.get('ret_gt_40pct', 0)} |",
        f"| high < low | {totals.get('high_lt_low', 0)} |",
        f"| open or close outside [low, high] | {totals.get('ohlc_out_of_range', 0)} |",
        f"| price <= 0 | {totals.get('nonpositive_price', 0)} |",
        f"| volume == 0 | {totals.get('zero_volume', 0)} |",
        f"| Duplicate dates | {totals.get('duplicate_dates', 0)} |",
        f"| Gaps > 5 business days | {totals.get('gap_gt_5bd', 0)} |",
    ]

    lines += ["", "Worst 20 symbols by flagged bars:", ""]
    lines += [
        "| Symbol | Bars | Flagged | >40% ret | high<low | out of range | "
        "price<=0 | vol==0 | dup dates | gap>5bd |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for symbol, flags in results["integrity"]["worst"]:
        lines.append(
            f"| {symbol} | {flags['bars']} | {flags['flagged_bars']} | "
            f"{flags['ret_gt_40pct']} | {flags['high_lt_low']} | "
            f"{flags['ohlc_out_of_range']} | {flags['nonpositive_price']} | "
            f"{flags['zero_volume']} | {flags['duplicate_dates']} | "
            f"{flags['gap_gt_5bd']} |"
        )

    lines += ["", "Artifact trades whose entry-to-exit window touches a flagged bar:", ""]
    touched = results["integrity"]["touched"]
    if touched:
        lines += [
            "| Setup | Symbol | Entry | Exit | Exit reason | Flagged bars | First flag |",
            "|---|---|---|---|---|---|---|",
        ]
        for row in touched:
            lines.append(
                f"| {row['setup']} | {row['symbol']} | {row['entry_date']} | "
                f"{row['exit_date']} | {row['exit_reason']} | {row['flagged_bars']} | "
                f"{row['first_flag']} |"
            )
    else:
        lines.append("None.")

    lines += ["", "## (d) Exit mix and win rate", ""]
    lines.append(
        "Strategy is one run (seed 42); the control is five matched-random runs "
        "(seeds 30042..30046), averaged."
    )
    lines.append("")
    lines += [
        "| Setup | Book | n | Win rate | stop | stop_gap | target | target_gap | "
        "time | Mean bars held |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for setup in results["setups"]:
        mix = results["exit_mix"][setup]
        for label, row in (("strategy", mix["strategy"]), ("matched_random", mix["control_mean"])):
            n = row["n"]
            n_text = f"{n:.1f}" if isinstance(n, float) else str(n)
            lines.append(
                f"| {setup} | {label} | {n_text} | {row['win_rate']:.3f} | "
                f"{row['stop']:.3f} | {row['stop_gap']:.3f} | {row['target']:.3f} | "
                f"{row['target_gap']:.3f} | {row['time']:.3f} | "
                f"{row['mean_bars_held']:.2f} |"
            )

    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_seeds(text):
    """Parse ``42-61`` or ``42,44,50`` into a list of ints."""
    seeds = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, hi = part.split("-", 1)
            seeds.extend(range(int(lo), int(hi) + 1))
        else:
            seeds.append(int(part))
    return seeds


def main():
    parser = argparse.ArgumentParser(description="Research baseline diagnostics")
    parser.add_argument("--setups", default=",".join(SETUPS.keys()),
                        help="Comma-separated setup names (default: all)")
    parser.add_argument("--seeds", default="42-61",
                        help="Candidate seeds as '42-61' or '42,44,50' (default: 42-61)")
    parser.add_argument("--start", default="2015-01-01")
    parser.add_argument("--end", default="2026-11-11",
                        help="Last cached bar end (default matches .cache/research)")
    parser.add_argument("--universe", default="config/replay_universe_sp500.txt")
    parser.add_argument("--cache-dir", default=".cache/research")
    parser.add_argument("--cache-max-age-hours", type=float, default=1e9,
                        help="Reuse the existing span-keyed cache regardless of age")
    parser.add_argument("--output-dir", default="docs/backtests/research")
    parser.add_argument("--report", default="docs/backtests/research/DIAGNOSTICS.md")
    args = parser.parse_args()

    setups = [s.strip() for s in args.setups.split(",") if s.strip()]
    for setup in setups:
        if setup not in SETUPS:
            parser.error(f"unknown setup: {setup}")
    seeds = parse_seeds(args.seeds)
    if not seeds:
        parser.error("no seeds given")

    exit_rules = ExitRules()
    portfolio_rules = PortfolioRules()

    print("Loading panel...")
    data, _dropped, _stats, actual_start, actual_end = load_panel(
        args.start, args.end, args.cache_dir, args.cache_max_age_hours,
    )
    elig = build_eligibility(data)

    results = {
        "setups": setups,
        "seed_sensitivity": {},
        "cost_sensitivity": {},
        "artifacts": {},
        "exit_mix": {},
    }

    for setup in setups:
        print(f"\n[{setup}] building signals")
        signals = build_signals(data, setup)
        print(f"[{setup}] (a) seed sensitivity, {len(seeds)} seeds")
        results["seed_sensitivity"][setup] = analyze_seeds(
            data, signals, exit_rules, portfolio_rules, seeds,
        )
        print(f"[{setup}] (b) cost sensitivity")
        results["cost_sensitivity"][setup] = analyze_costs(
            data, signals, exit_rules, portfolio_rules,
        )
        print(f"[{setup}] (d) exit mix")
        results["exit_mix"][setup] = analyze_exit_mix(
            data, signals, elig, exit_rules, portfolio_rules,
        )

    print("\n(c) data integrity scan")
    results["integrity"] = analyze_integrity(data, setups, args.output_dir)
    for setup in setups:
        results["artifacts"][setup] = newest_artifact(args.output_dir, setup)

    meta = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "start": args.start,
        "end": args.end,
        "actual_start": actual_start.strftime("%Y-%m-%d") if actual_start is not None else "n/a",
        "actual_end": actual_end.strftime("%Y-%m-%d") if actual_end is not None else "n/a",
        "seed_min": min(seeds),
        "seed_max": max(seeds),
        "n_seeds": len(seeds),
    }
    report = render_markdown(results, meta)
    Path(args.report).write_text(report + "\n", encoding="utf-8")
    print(f"\nWrote {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
