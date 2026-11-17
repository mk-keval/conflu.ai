#!/usr/bin/env python
"""Event study: forward returns after each signal, with no exits or portfolio rules.

Isolates signal information from exit design and costs. Loads the same panel as
the baseline runner (``download_daily`` + ``add_indicators``, 2015 warm-up), marks
events for each setup, subtracts the same-date universe mean and compares the
mean excess with matched-random event sets.

Writes ``docs/backtests/research/EVENT_STUDY.md`` and a JSON under
``docs/backtests/research/event_study/`` (a sub-folder so the baseline report
loader, which only scans the top level, ignores it).

Usage:
    python scripts/research_event_study.py
    python scripts/research_event_study.py --setups breakout_52week --n-null 20
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

from backend.app.research import events
from backend.app.research.data import download_daily, load_universe, panel_span
from backend.app.research.engine import NON_TRADABLE
from backend.app.research.indicators import add_indicators
from backend.app.research.setups import SETUPS

REQUESTED_START = "2015-01-01"
EVAL_START = events.EVAL_START
DEFAULT_REPORT = "docs/backtests/research/EVENT_STUDY.md"
DEFAULT_JSON_DIR = "docs/backtests/research/event_study"
NULL_BASE_SEED = 50000
BOOTSTRAP_RESAMPLES = 2000
BOOTSTRAP_SEED = 42
BY_YEAR_HORIZONS = (5, 20)


def build_signals(data, elig, setup_fn):
    """Real setup signals; benchmark/ineligible symbols get an all-False series."""
    signals = {}
    for symbol, df in data.items():
        if symbol in NON_TRADABLE or symbol not in elig.columns or not bool(elig[symbol].any()):
            signals[symbol] = pd.Series(False, index=df.index)
            continue
        signals[symbol] = setup_fn(df).reindex(df.index, fill_value=False).fillna(False).astype(bool)
    return signals


def spy_reference(data, start=EVAL_START):
    """SPY buy-and-hold CAGR (calendar years) and max drawdown. Reference only."""
    df = data.get("SPY")
    if df is None or len(df) == 0:
        return {"available": False}
    close = df["close"]
    close = close[close.index >= pd.Timestamp(start)]
    if len(close) < 2:
        return {"available": False}
    first = float(close.iloc[0])
    last = float(close.iloc[-1])
    years = (close.index[-1] - close.index[0]).days / 365.25
    cagr = (last / first) ** (1.0 / years) - 1.0 if years > 0 and first > 0 else float("nan")
    drawdown = close / close.cummax() - 1.0
    return {
        "available": True,
        "start": str(close.index[0].date()),
        "end": str(close.index[-1].date()),
        "n_bars": int(len(close)),
        "cagr": float(cagr),
        "max_drawdown": float(drawdown.min()),
    }


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
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    return value


def _fmt_bp(value, digits=1):
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return "n/a"
    return f"{float(value):,.{digits}f}"


def _fmt_pct(value, digits=3):
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return "n/a"
    return f"{float(value) * 100:.{digits}f}%"


def _fmt_rate(value):
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return "n/a"
    return f"{float(value) * 100:.1f}%"


def _fmt_p(value):
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return "n/a"
    return f"{float(value):.4f}"


def definitions_text(setups, horizons, cooldown, n_null):
    """Verbatim definition block used at the top of the report and in the JSON."""
    return [
        f"- **Signal:** `SETUPS[name](df)` is True at the CLOSE of day `t`; entry row `e` is the "
        "symbol's NEXT bar (entry at the open of `t+1`).",
        f"- **Forward return for horizon `h` (trading days, `h >= 1`):** "
        f"`ret_h = close[e+h-1] / open[e] - 1`. `h=1` is the entry day open-to-close; `h=5` holds "
        f"through the 5th bar including the entry day. Horizons: {', '.join(str(h) for h in horizons)}. "
        "Rows where `close[e+h-1]` does not exist are dropped for that horizon (never filled).",
        f"- **Event:** signal at `t` AND `eligible(df)` at `t`, entry row `e` with "
        f"`entry date >= {EVAL_START}`. **Cooldown:** a repeat is dropped when the previous accepted "
        f"event on the same symbol is at most `{cooldown}` bars earlier (default 5), so accepted events "
        f"are more than {cooldown} bars apart.",
        "- **Universe benchmark:** for each entry date `e`, the mean `ret_h` over ALL symbols that were "
        "eligible at their signal-day (the bar before `e`) and have the forward data. "
        "**Excess return** = event `ret_h` minus that same-date universe mean.",
        "- **Statistics:** n events, n distinct entry dates, event-weighted mean excess (basis points), "
        "hit rate (share of events with excess > 0), raw mean return, raw mean minus 30 bps "
        "(a 15 bps/side round trip), 95% CI of the mean excess from a month-block bootstrap "
        f"(resample entry year-months with replacement, {BOOTSTRAP_RESAMPLES} resamples, seed "
        f"{BOOTSTRAP_SEED}), and the mean excess by calendar year for h=5 and h=20.",
        f"- **Null:** {n_null} matched-random event sets per setup from "
        "`backend.app.research.control.matched_random_signals` (same number of events per day, random "
        f"eligible symbols), the same cooldown and statistics; seeds {NULL_BASE_SEED}.."
        f"{NULL_BASE_SEED + n_null - 1}. `p_high = (count(null >= real)+1)/(n+1)`, "
        "`p_low = (count(null <= real)+1)/(n+1)` per horizon.",
        "- **Panel:** loaded as the baseline runner does (`download_daily` with the `.cache/research` "
        f"span {REQUESTED_START} -> latest, then `add_indicators`); `NON_TRADABLE` symbols are excluded. "
        "2015 is warm-up; entries are evaluated from 2016-01-01.",
    ]


def write_markdown(path, *, generated_at, setups, horizons, cooldown, n_null, panel, spy,
                   results, command):
    """Render the event-study report."""
    lines = [
        "# Event Study — signal information without exits",
        "",
        f"Generated `{generated_at}` by `scripts/research_event_study.py`.",
        "",
        "Exploratory, in-sample, survivorship-biased universe (today's S&P 500). "
        "Not evidence of a live edge.",
        "",
        "## Definitions",
        "",
    ]
    lines.extend(definitions_text(setups, horizons, cooldown, n_null))
    lines.extend(
        [
            "",
            "## Panel and reference",
            "",
            "| Item | Value |",
            "|---|---|",
            f"| Requested span | {REQUESTED_START} -> {panel['requested_end']} |",
            f"| Actual panel | {panel['actual_start']} -> {panel['actual_end']} |",
            f"| Tradable symbols | {panel['n_symbols']} |",
            f"| Dropped at load | {panel['n_dropped']} |",
            f"| Evaluation start | {EVAL_START} |",
            "",
            "**SPY reference only (not compared to anything in this task).**",
            "",
        ]
    )
    if spy.get("available"):
        lines.extend(
            [
                "| Item | Value |",
                "|---|---|",
                f"| Window | {spy['start']} -> {spy['end']} |",
                f"| CAGR (calendar years) | {_fmt_pct(spy['cagr'], 2)} |",
                f"| Max drawdown (daily close) | {_fmt_pct(spy['max_drawdown'], 2)} |",
                f"| Bars | {spy['n_bars']} |",
                "",
            ]
        )
    else:
        lines.extend(["SPY data unavailable.", ""])

    lines.extend(
        [
            "## Results",
            "",
            "Mean excess, null mean/std and the CI are in basis points; raw mean and "
            "raw mean minus 30 bps are returns. `p_high` tests the strategy against "
            "the null from above, `p_low` from below.",
            "",
        ]
    )
    for setup in setups:
        payload = results[setup]
        lines.extend([f"### `{setup}`", "", f"Events after cooldown: {payload['n_events']}.", ""])
        lines.extend(
            [
                "| h | n | dates | mean excess (bp) | 95% CI (bp) | hit rate | raw mean | "
                "raw mean - 30 bp | null mean (bp) | null std (bp) | p_high | p_low |",
                "|---|---|---|---|---|---|---|---|---|---|---|---|",
            ]
        )
        for horizon in horizons:
            row = payload["horizons"][str(horizon)]
            real = row["real"]
            null = row["null"]
            ci = real["ci95_excess_bp"]
            ci_text = f"[{_fmt_bp(ci[0])}, {_fmt_bp(ci[1])}]"
            lines.append(
                f"| {horizon} | {real['n']} | {real['n_dates']} | "
                f"{_fmt_bp(real['mean_excess_bp'])} | {ci_text} | "
                f"{_fmt_rate(real['hit_rate'])} | {_fmt_pct(real['raw_mean'])} | "
                f"{_fmt_pct(real['raw_mean_minus_cost'])} | "
                f"{_fmt_bp(null['null_mean'])} | {_fmt_bp(null['null_std'])} | "
                f"{_fmt_p(null['p_high'])} | {_fmt_p(null['p_low'])} |"
            )
        lines.append("")

        for horizon in BY_YEAR_HORIZONS:
            if horizon not in horizons:
                continue
            by_year = payload["horizons"][str(horizon)]["real"]["by_year"]
            lines.extend([f"**Mean excess by calendar year, h={horizon}**", ""])
            if not by_year:
                lines.extend(["No events with forward data.", ""])
                continue
            lines.extend(["| Year | n | mean excess (bp) | hit rate |", "|---|---|---|---|"])
            for year, stats in by_year.items():
                lines.append(
                    f"| {year} | {stats['n']} | {_fmt_bp(stats['mean_excess_bp'])} | "
                    f"{_fmt_rate(stats['hit_rate'])} |"
                )
            lines.append("")

    lines.extend(
        [
            "## Notes",
            "",
            f"- Command: `{command}`.",
            f"- Null base seed {NULL_BASE_SEED}; bootstrap resamples {BOOTSTRAP_RESAMPLES}, "
            f"seed {BOOTSTRAP_SEED}.",
            "- The universe benchmark uses all eligible symbols, not the setup's candidate pool; "
            "it is a same-date market/eligibility mean, not a sector- or size-matched benchmark.",
            "- The event study has no stops, targets, position limits, slot competition or "
            "capital constraint; it cannot be read as a portfolio result.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Event study of signal forward returns")
    parser.add_argument("--setups", default=",".join(SETUPS),
                        help="Comma-separated setup names (default: all four)")
    parser.add_argument("--horizons", default=",".join(str(h) for h in events.DEFAULT_HORIZONS),
                        help="Comma-separated positive trading-day horizons")
    parser.add_argument("--cooldown", type=int, default=5)
    parser.add_argument("--n-null", type=int, default=200)
    parser.add_argument("--report", default=DEFAULT_REPORT)
    parser.add_argument("--json-dir", default=DEFAULT_JSON_DIR)
    args = parser.parse_args()

    setups = [name.strip() for name in args.setups.split(",") if name.strip()]
    unknown = [name for name in setups if name not in SETUPS]
    if unknown:
        parser.error(f"unknown setup(s): {unknown}; choose from {sorted(SETUPS)}")
    horizons = sorted({int(h.strip()) for h in args.horizons.split(",") if h.strip()})
    if not horizons or any(h < 1 for h in horizons):
        parser.error("--horizons must be a non-empty list of integers >= 1")
    if args.cooldown < 0:
        parser.error("--cooldown must be >= 0")
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

    print("Building eligibility and forward-return frames")
    elig = events.eligibility_frame(data)
    forward = {
        symbol: events.forward_return_frame(df, horizons)
        for symbol, df in data.items()
        if symbol not in events.TRADABLE_BENCHMARK and len(df) >= 2
    }
    benchmark = events.universe_benchmark(
        data, elig, horizons=horizons, eval_start=EVAL_START, forward=forward,
    )
    spy = spy_reference(data)
    print(f"Universe benchmark dates: {len(benchmark)}")

    results = {}
    for setup in setups:
        print(f"[{setup}] building signals and events")
        signals = build_signals(data, elig, SETUPS[setup])
        real_events = events.collect_events(
            data, signals, elig, cooldown=args.cooldown, eval_start=EVAL_START,
            horizons=horizons, forward=forward,
        )
        print(f"[{setup}] events after cooldown: {len(real_events)}")

        def progress(done, total=args.n_null, name=setup):
            if done == total or done % 25 == 0:
                print(f"[{name}] null draws {done}/{total}")

        nulls = events.null_distribution(
            data, signals, elig, benchmark, horizons=horizons, n_null=args.n_null,
            cooldown=args.cooldown, eval_start=EVAL_START, base_seed=NULL_BASE_SEED,
            forward=forward, progress=progress,
        )

        horizon_rows = {}
        for horizon in horizons:
            real = events.event_stats(
                real_events, benchmark, horizon,
                n_resamples=BOOTSTRAP_RESAMPLES, seed=BOOTSTRAP_SEED,
            )
            null_bp = [value * 10_000.0 for value in nulls[horizon]]
            null = events.p_values(real["mean_excess_bp"], null_bp)
            horizon_rows[str(horizon)] = {"real": real, "null": null}
            print(
                f"[{setup}] h={horizon}: n={real['n']} mean excess="
                f"{real['mean_excess_bp']:+.1f} bp p_high={null['p_high']:.4f} "
                f"p_low={null['p_low']:.4f}"
            )
        results[setup] = {"n_events": int(len(real_events)), "horizons": horizon_rows}

    payload = {
        "task": "E1",
        "generated_at": generated_at,
        "command": " ".join(sys.argv),
        "definitions": definitions_text(setups, horizons, args.cooldown, args.n_null),
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
            "horizons": horizons,
            "cooldown": args.cooldown,
            "n_null": args.n_null,
            "null_base_seed": NULL_BASE_SEED,
            "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
            "bootstrap_seed": BOOTSTRAP_SEED,
        },
        "spy_reference": spy,
        "results": results,
    }

    report_path = Path(args.report)
    write_markdown(
        report_path,
        generated_at=generated_at,
        setups=setups,
        horizons=horizons,
        cooldown=args.cooldown,
        n_null=args.n_null,
        panel={
            "requested_end": requested_end,
            "actual_start": str(actual_start.date()),
            "actual_end": str(actual_end.date()),
            "n_symbols": n_symbols,
            "n_dropped": len(dropped),
        },
        spy=spy,
        results=results,
        command=" ".join(sys.argv),
    )

    json_dir = Path(args.json_dir)
    json_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = json_dir / f"event_study_{stamp}.json"
    json_path.write_text(json.dumps(_json_safe(payload), indent=2), encoding="utf-8")
    print(f"Wrote {report_path} and {json_path}")


if __name__ == "__main__":
    main()
