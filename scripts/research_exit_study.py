#!/usr/bin/env python
"""Exit-shape study: same entries, different exit rules, one trade at a time.

For every setup it applies variants B0-B4 to the identical entries and compares
each with matched-random entries under the same exit. It ignores portfolio
capacity, slot competition and position sizing, so it measures exit shape rather
than a portfolio result.

Writes ``docs/backtests/research/EXIT_STUDY.md`` and a JSON under
``docs/backtests/research/event_study/`` (a sub-folder so the top-level-only
baseline report loader ignores it).

Usage:
    python scripts/research_exit_study.py
    python scripts/research_exit_study.py --setups breakout_52week --n-null 5
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.research import exit_study
from backend.app.research.data import download_daily, load_universe, panel_span
from backend.app.research.engine import NON_TRADABLE
from backend.app.research.events import eligibility_frame
from backend.app.research.indicators import add_indicators
from backend.app.research.setups import SETUPS

REQUESTED_START = "2015-01-01"
EVAL_START = exit_study.EVAL_START
DEFAULT_REPORT = "docs/backtests/research/EXIT_STUDY.md"
DEFAULT_JSON_DIR = "docs/backtests/research/event_study"
NULL_BASE_SEED = exit_study.DEFAULT_NULL_BASE_SEED
DEFAULT_N_NULL = 100
COST_BPS = exit_study.DEFAULT_COST_BPS
WARNING = "Exploratory, in-sample, survivorship-biased. Not evidence of a live edge."
CAPACITY = (
    "This analysis ignores portfolio capacity and slot competition: every signal "
    "is taken as an independent trade, with no limit on concurrent positions or "
    "capital."
)


def build_signals(data, elig, setup_fn):
    """Real setup signals; benchmark/ineligible symbols get an all-False series."""
    signals = {}
    for symbol, df in data.items():
        if symbol in NON_TRADABLE or symbol not in elig.columns or not bool(elig[symbol].any()):
            signals[symbol] = pd.Series(False, index=df.index)
            continue
        signals[symbol] = setup_fn(df).reindex(df.index, fill_value=False).fillna(False).astype(bool)
    return signals


def _json_safe(value):
    """Replace non-finite floats with None so the JSON is standard-compliant."""
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if not math.isfinite(float(value)) else float(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def _fmt(value, digits=4):
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return "n/a"
    return f"{float(value):.{digits}f}"


def _fmt_rate(value):
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return "n/a"
    return f"{float(value) * 100:.1f}%"


def _fmt_exits(exit_share):
    if not exit_share:
        return "n/a"
    parts = [f"{reason} {_fmt_rate(share)}" for reason, share in exit_share.items()]
    return "; ".join(parts)


def definitions_text(setups, n_null):
    """Verbatim definition block used at the top of the report and in the JSON."""
    lines = [
        f"- **Entry (same as the engine):** a setup signal is True at the CLOSE of day `t`; the "
        "trade enters at the OPEN of `t+1`. ATR is `atr14` of the signal bar; entries with a NaN "
        "ATR or `ATR <= 0` are skipped.",
        "- **1R:** always `2 * ATR` (the initial stop distance) for every variant, so R values are "
        "comparable even for variants without a stop.",
        f"- **Costs:** {COST_BPS:.0f} bps per side using the engine's formula "
        "`r_net = (exit*(1-c) - entry*(1+c)) / (2*ATR)` with `c = 0.0015`; `r_gross` has no costs.",
        "- **Stop order (engine rules):** gap stop at the open, then the stop, then the gap target, "
        "then the target, then the time exit at the close. The stop wins ties. A gap below the stop "
        "exits at the open; otherwise a stop hit exits at the stop price.",
        "- **Trailing stop:** the entry bar uses only the initial stop. Each later bar `k` uses the "
        "highest HIGH of the open trade's bars from the entry bar through `k-1` minus the trail "
        "distance, never lowered. Bar `k`'s own high cannot move the stop used on bar `k` (no "
        "look-ahead); a spike on bar `k` raises the stop on bar `k+1`.",
        "- **Panel end:** a trade whose path would run past the panel end is dropped, never marked "
        "to market.",
        f"- **Evaluation window:** entry date >= {EVAL_START} (2015 is indicator warm-up).",
        f"- **Null:** {n_null} matched-random entry sets per setup from "
        "`backend.app.research.control.matched_random_signals` (same daily count of eligible "
        f"signals, random eligible symbols), the same entry and exit rules; seeds {NULL_BASE_SEED}.."
        f"{NULL_BASE_SEED + n_null - 1}. Reported are the null mean/std of mean `r_net`, the gap "
        "`strategy - null mean`, `gap / null std`, and one-sided `p_high = (count(null >= real)+1)/"
        "(n+1)`, `p_low = (count(null <= real)+1)/(n+1)`.",
        f"- **Capacity caveat:** {CAPACITY}",
    ]
    return lines


def write_markdown(path, *, generated_at, setups, variants, n_null, panel, results, command):
    """Render the exit-shape report."""
    lines = [
        "# Exit Study — same entries, different exits",
        "",
        f"Generated `{generated_at}` by `scripts/research_exit_study.py`.",
        "",
        WARNING,
        "",
        CAPACITY,
        "",
        "## Definitions",
        "",
    ]
    lines.extend(definitions_text(setups, n_null))

    lines.extend(
        [
            "",
            "### Exit variants",
            "",
            "| Variant | Rules |",
            "|---|---|",
        ]
    )
    for name, variant in variants.items():
        lines.append(f"| {name} | {variant.description} |")

    lines.extend(
        [
            "",
            "## Panel",
            "",
            "| Item | Value |",
            "|---|---|",
            f"| Requested span | {REQUESTED_START} -> {panel['requested_end']} |",
            f"| Actual panel | {panel['actual_start']} -> {panel['actual_end']} |",
            f"| Tradable symbols | {panel['n_symbols']} |",
            f"| Dropped at load | {panel['n_dropped']} |",
            f"| Evaluation start | {EVAL_START} |",
            "",
            "## Results",
            "",
            "Means, win/loss R and profit factor are in R units; `gap` is strategy mean "
            "`r_net` minus the null mean. Exit shares are of that variant's closed trades.",
            "",
        ]
    )

    header = (
        "| Variant | n | mean r_net | mean r_gross | win rate | avg win R | avg loss R | "
        "profit factor | mean bars | exits | null mean | null std | gap | gap/std | "
        "p_high | p_low |"
    )
    separator = "|" + "---|" * 16

    for setup in setups:
        payload = results[setup]
        lines.extend(
            [
                f"### `{setup}`",
                "",
                f"Entries considered before exit-variant drops: {payload['n_entries']}.",
                "",
                header,
                separator,
            ]
        )
        for name in variants:
            row = payload["variants"][name]
            stats = row["stats"]
            null = row["null"]
            lines.append(
                f"| {name} | {stats['n']} | {_fmt(stats['mean_r_net'])} | "
                f"{_fmt(stats['mean_r_gross'])} | {_fmt_rate(stats['win_rate'])} | "
                f"{_fmt(stats['avg_win_r'])} | {_fmt(stats['avg_loss_r'])} | "
                f"{_fmt(stats['profit_factor'], 2)} | {_fmt(stats['mean_bars_held'], 2)} | "
                f"{_fmt_exits(stats['exit_share'])} | {_fmt(null['null_mean'])} | "
                f"{_fmt(null['null_std'])} | {_fmt(null['gap'])} | "
                f"{_fmt(null['gap_over_std'], 2)} | {_fmt(null['p_high'])} | "
                f"{_fmt(null['p_low'])} |"
            )
        lines.append("")

    lines.extend(
        [
            "## Notes",
            "",
            f"- Command: `{command}`.",
            f"- Null base seed {NULL_BASE_SEED}; costs {COST_BPS:.0f} bps per side.",
            "- B0 must reproduce the engine's exit price, reason and `r_net` for the same entry; "
            "the unit tests check this against `run_portfolio` with `max_positions=1`.",
            "- B4 exits at the close of the 20th bar including the entry day, the same endpoint as "
            "the event study's `h=20`.",
            "- Variants share the same entries and the same signals are reused across variants and "
            "null draws, so the cells are not independent trials.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Exit-shape study on fixed entries")
    parser.add_argument("--setups", default=",".join(SETUPS),
                        help="Comma-separated setup names (default: all four)")
    parser.add_argument("--n-null", type=int, default=DEFAULT_N_NULL,
                        help="Matched-random entry sets per setup (default 100)")
    parser.add_argument("--report", default=DEFAULT_REPORT)
    parser.add_argument("--json-dir", default=DEFAULT_JSON_DIR)
    args = parser.parse_args()

    setups = [name.strip() for name in args.setups.split(",") if name.strip()]
    unknown = [name for name in setups if name not in SETUPS]
    if unknown:
        parser.error(f"unknown setup(s): {unknown}; choose from {sorted(SETUPS)}")
    if args.n_null < 1:
        parser.error("--n-null must be >= 1")

    generated_at = datetime.now().isoformat(timespec="seconds")
    requested_end = datetime.now().strftime("%Y-%m-%d")
    print(f"Loading panel {REQUESTED_START} -> {requested_end} from .cache/research")
    symbols = load_universe()
    data, dropped, cache_stats = download_daily(
        symbols, REQUESTED_START, requested_end, ".cache/research",
    )
    for symbol, df in data.items():
        data[symbol] = add_indicators(df)
    actual_start, actual_end = panel_span(data)
    n_symbols = sum(1 for s in data if s not in NON_TRADABLE)
    print(
        f"Panel: {actual_start.date()} -> {actual_end.date()}, {n_symbols} tradable symbols, "
        f"{len(dropped)} dropped (cache hits={cache_stats['hits']}, "
        f"downloads={cache_stats['downloaded']})"
    )

    print("Building eligibility")
    elig = eligibility_frame(data)
    print(f"Eligibility dates: {len(elig)}")

    cache: dict[str, dict] = {}
    results = {}
    for setup in setups:
        print(f"[{setup}] building signals and entries")
        signals = build_signals(data, elig, SETUPS[setup])
        masked = exit_study.mask_ineligible(data, signals, elig)
        entries = exit_study.entry_candidates(
            data, signals, elig, eval_start=EVAL_START,
        )
        print(f"[{setup}] entries: {len(entries)}")

        variant_rows = {}
        for name, variant in exit_study.VARIANTS.items():
            trades = exit_study.simulate_entries(
                data, entries, variant, cost_bps=COST_BPS, cache=cache,
            )
            variant_rows[name] = {
                "stats": exit_study.trade_stats(trades),
                "null": None,
            }
            stats = variant_rows[name]["stats"]
            print(
                f"[{setup}] {name}: n={stats['n']} mean r_net={stats['mean_r_net']:+.4f} "
                f"mean r_gross={stats['mean_r_gross']:+.4f}"
            )

        def progress(done, total=args.n_null, name=setup):
            if done == total or done % 10 == 0:
                print(f"[{name}] null draws {done}/{total}")

        nulls = exit_study.null_distributions(
            data, masked, elig, exit_study.VARIANTS, n_null=args.n_null,
            base_seed=NULL_BASE_SEED, cost_bps=COST_BPS, eval_start=EVAL_START,
            progress=progress,
        )
        for name in exit_study.VARIANTS:
            real_mean = variant_rows[name]["stats"]["mean_r_net"]
            summary = exit_study.null_summary(real_mean, nulls[name])
            variant_rows[name]["null"] = summary
            print(
                f"[{setup}] {name}: null mean={summary['null_mean']:+.4f} "
                f"gap={summary['gap']:+.4f} gap/std={summary['gap_over_std']:+.2f} "
                f"p_high={summary['p_high']:.4f} p_low={summary['p_low']:.4f}"
            )
        results[setup] = {
            "n_entries": int(len(entries)),
            "variants": variant_rows,
        }

    payload = {
        "task": "E2",
        "generated_at": generated_at,
        "command": " ".join(sys.argv),
        "definitions": definitions_text(setups, args.n_null),
        "warning": WARNING,
        "capacity_caveat": CAPACITY,
        "window": {
            "requested_start": REQUESTED_START,
            "requested_end": requested_end,
            "eval_start": EVAL_START,
        },
        "panel": {
            "actual_start": str(actual_start.date()),
            "actual_end": str(actual_end.date()),
            "n_symbols": int(n_symbols),
            "n_dropped": int(len(dropped)),
            "dropped": [list(item) for item in dropped],
            "cache": cache_stats,
        },
        "params": {
            "setups": setups,
            "n_null": args.n_null,
            "null_base_seed": NULL_BASE_SEED,
            "cost_bps_per_side": COST_BPS,
            "variants": {
                name: {
                    "stop_atr": variant.stop_atr,
                    "target_atr": variant.target_atr,
                    "trail_atr": variant.trail_atr,
                    "max_hold": variant.max_hold,
                    "description": variant.description,
                }
                for name, variant in exit_study.VARIANTS.items()
            },
        },
        "results": results,
    }

    report_path = Path(args.report)
    write_markdown(
        report_path,
        generated_at=generated_at,
        setups=setups,
        variants=exit_study.VARIANTS,
        n_null=args.n_null,
        panel={
            "requested_end": requested_end,
            "actual_start": str(actual_start.date()),
            "actual_end": str(actual_end.date()),
            "n_symbols": n_symbols,
            "n_dropped": len(dropped),
        },
        results=results,
        command=" ".join(sys.argv),
    )

    json_dir = Path(args.json_dir)
    json_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = json_dir / f"exit_study_{stamp}.json"
    json_path.write_text(json.dumps(_json_safe(payload), indent=2), encoding="utf-8")
    print(f"Wrote {report_path} and {json_path}")


if __name__ == "__main__":
    main()
