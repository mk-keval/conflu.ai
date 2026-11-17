#!/usr/bin/env python
"""Volatility-matched re-measurement of the event study (E1) and exit study (E2).

Part 1 repeats the event study against a previous-bar volatility-bucket
benchmark.  Part 2 repeats the exit study in both R and percent units against
volatility-matched random entries.  Significance uses a 95% month-block CI and a
Bonferroni ``block_t`` threshold (20 cells per part); the old null's spread is
reported as descriptive only.

Writes ``docs/backtests/research/VOL_MATCHED_STUDY.md`` and a JSON under
``docs/backtests/research/event_study/`` (a sub-folder so the baseline report
loader ignores it).

Usage:
    python scripts/research_vol_matched.py
    python scripts/research_vol_matched.py --setups breakout_52week --n-sanity 2 --n-null 2
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.research import events, exit_study, matched_control
from backend.app.research.data import download_daily, load_universe, panel_span
from backend.app.research.engine import NON_TRADABLE
from backend.app.research.indicators import add_indicators
from backend.app.research.setups import SETUPS

REQUESTED_START = "2015-01-01"
EVAL_START = events.EVAL_START
DEFAULT_REPORT = "docs/backtests/research/VOL_MATCHED_STUDY.md"
DEFAULT_JSON_DIR = "docs/backtests/research/event_study"
COOLDOWN = 5
COST_BPS = exit_study.DEFAULT_COST_BPS
SANITY_BASE_SEED = 70000
NULL_BASE_SEED = 80000
DEFAULT_N_BUCKETS = 10
DEFAULT_N_SANITY = 20
DEFAULT_N_NULL = 100
BOOTSTRAP_RESAMPLES = 2000
BOOTSTRAP_SEED = 42
M_CELLS = 20

WARNING = (
    "Exploratory, in-sample, survivorship-biased universe (today's S&P 500). "
    "Not evidence of a live edge."
)
CAPACITY = (
    "This analysis ignores portfolio capacity and slot competition: every signal "
    "is taken as an independent trade, with no limit on concurrent positions or "
    "capital."
)
PRE_DECLARED_RULE = (
    "Any cell that does not pass is NOT evidence of an edge. A passing cell is "
    "only a candidate to be pre-registered and tested on the locked 2021-2026 "
    "holdout; it is never a result. This study re-measures the same 4 setups on "
    "the same data as E1/E2, so cumulative trials are 20+20+20+20 = 80 cells, "
    "and none of this is out-of-sample."
)
WHY = (
    "Two flaws were found in E1/E2. (1) The old null "
    "(`control.matched_random_signals`) picks random stocks of ANY volatility, "
    "so its spread is 2-3.5x smaller than the strategy's own month-block "
    "uncertainty. The reported `p_high`/`p_low` and `gap/std` are therefore NOT "
    "valid significance tests. (2) The exit study measures R, where 1R = 2*ATR. "
    "`low_vol_setup` picks low-ATR stocks, so the same percent move counts as "
    "more R. E2 shows `low_vol_setup` B4 beating the null in R (+0.031R) while "
    "E1 shows the same signals underperforming the market by 15 bp at h=20. The "
    "sign disagreement is probably a volatility/R artifact. This task checks it."
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


def _git_state() -> tuple[str, bool]:
    """HEAD revision and whether tracked files differ from HEAD."""
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            capture_output=True, text=True, check=True,
        ).stdout
        return revision, bool(status.strip())
    except Exception:
        return "unknown", True


def _json_safe(value):
    """Replace non-finite floats with None so the JSON is standard-compliant."""
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, (np.floating, float)):
        return None if not math.isfinite(float(value)) else float(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def _fmt(value, digits=4):
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return "n/a"
    return f"{float(value):,.{digits}f}"


def _fmt_bp(value, digits=1):
    return _fmt(value, digits)


def _fmt_rate(value):
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return "n/a"
    return f"{float(value) * 100:.1f}%"


def _fmt_bool(value):
    return "yes" if value else "no"


def definitions_text(horizons, n_buckets, n_sanity, n_null):
    """Verbatim definition block used at the top of the report and in the JSON."""
    return [
        f"- **Volatility bucket:** on each date, the symbols eligible on that date are ranked by "
        "`atr_pct` with `rank(pct=True, method=\"first\")` and assigned "
        f"`bucket = ceil(pct * {n_buckets}) - 1`, clipped to `0..{n_buckets - 1}`. "
        f"`--n-buckets {n_buckets}`. Not eligible or NaN `atr_pct` -> `-1`. An event's bucket is "
        "the bucket on its SIGNAL date `t`, so no data after `t` is used.",
        "- **Bucket benchmark (Part 1):** for each entry date `e` and bucket `b`, the mean `ret_h` "
        "over all symbols whose bucket on the bar BEFORE `e` was `b` (the bucket series is shifted "
        "by one bar per symbol, mirroring `events.universe_benchmark`'s previous-bar eligibility) "
        "and that have the forward data. Event excess = event `ret_h` - bucket benchmark at the "
        "event's signal-date bucket.",
        "- **Forward return (same as `events.py`):** `ret_h = close[e+h-1] / open[e] - 1` for "
        f"horizons {', '.join(str(h) for h in horizons)}, cooldown `{COOLDOWN}`. A row without the "
        "future close is dropped for that horizon, never filled.",
        "- **Vol-matched random signals:** for every date and every bucket in which the real setup "
        "fires `c` times, draw `k = min(c, pool size)` distinct symbols from the symbols that are "
        "eligible AND in that bucket on that date. Dates and buckets are visited in sorted order; "
        "non-tradable symbols get an all-False series. Shortfalls (`requested > drawn`) are "
        "reported, never hidden.",
        "- **Percent returns (Part 2):** `add_pct_returns(trades, cost_bps)` adds "
        "`ret_gross_pct = exit_price*(1-c)/(entry_price*(1+c)) - 1` with `c = cost_bps/10000`; "
        "`ret_net_pct` carries the same cost-aware value and is the name reported in Part 2. Same "
        f"entries and the same five variants B0-B4 as E2, {COST_BPS:.0f} bps per side.",
        "- **Honest significance:** `block_summary` returns the mean, the 95% month-block bootstrap "
        "CI (`events.month_block_bootstrap_ci`, `n_resamples=2000`, seed `42`), "
        "`se_block = (ci_high - ci_low)/(2*1.96)`, `reference_in_ci`, and "
        "`block_t = (mean - reference)/se_block` (NaN when `se_block` is 0 or NaN). Reference is 0 "
        "for the Part 1 bucket excess and the vol-matched null mean for Part 2.",
        f"- **Bonferroni:** `z_crit(m) = NormalDist().inv_cdf(1 - 0.05/(2*m))`; `m = {M_CELLS}` "
        f"cells per part (4 setups x 5 horizons for Part 1, 4 setups x 5 variants for Part 2), so "
        f"`z_crit({M_CELLS}) = {_fmt(matched_control.z_crit(M_CELLS), 3)}`. A cell passes only if "
        "`|block_t| >= z_crit` AND `reference_in_ci` is False. An E2 cell passes only if BOTH the R "
        "metric and the percent metric pass AND their gap signs agree.",
        "- **Null spread:** the null std is the descriptive spread of the null mean, NOT a test. "
        "No `p_high`/`p_low` is reported anywhere in this task.",
        f"- **Seeds:** Part 1 sanity draws use `{SANITY_BASE_SEED} + i` ({n_sanity} draws); Part 2 "
        f"null draws use `{NULL_BASE_SEED} + i` ({n_null} draws).",
        f"- **Capacity caveat:** {CAPACITY}",
    ]


def analyse_part1(data, elig, buckets, forward, universe_benchmark, bucket_benchmark,
                  setups, horizons, n_sanity):
    """Part 1: event study vs the volatility-bucket benchmark, plus sanity draws."""
    results = {}
    sanity = {}
    z = matched_control.z_crit(M_CELLS)
    for setup in setups:
        print(f"[E1 {setup}] building signals and events")
        signals = build_signals(data, elig, SETUPS[setup])
        masked = exit_study.mask_ineligible(data, signals, elig)
        real_events = events.collect_events(
            data, masked, elig, cooldown=COOLDOWN, eval_start=EVAL_START,
            horizons=horizons, forward=forward,
        )
        with_bucket = matched_control.add_event_bucket(real_events, buckets)
        print(f"[E1 {setup}] events after cooldown: {len(real_events)}")

        horizon_rows = {}
        for horizon in horizons:
            old = events.event_stats(
                real_events, universe_benchmark, horizon,
                n_resamples=BOOTSTRAP_RESAMPLES, seed=BOOTSTRAP_SEED,
            )
            frame = matched_control.bucket_excess_frame(with_bucket, bucket_benchmark, horizon)
            summary = matched_control.block_summary(
                frame["excess"].to_numpy(dtype=float),
                frame["entry_date"].to_list(),
                0.0,
                n_resamples=BOOTSTRAP_RESAMPLES,
                seed=BOOTSTRAP_SEED,
            )
            hit_rate = float((frame["excess"] > 0).mean()) if len(frame) else float("nan")
            passes = matched_control.cell_passes(
                summary["block_t"], summary["reference_in_ci"], z
            )
            horizon_rows[str(horizon)] = {
                "n": summary["n"],
                "old_excess_bp": float(old["mean_excess_bp"]),
                "new_excess_bp": float(summary["mean"] * 10_000.0),
                "ci95_bp": [summary["ci_low"] * 10_000.0, summary["ci_high"] * 10_000.0],
                "se_block_bp": summary["se_block"] * 10_000.0,
                "hit_rate": hit_rate,
                "reference_in_ci": summary["reference_in_ci"],
                "block_t": summary["block_t"],
                "passes": passes,
            }
            print(
                f"[E1 {setup}] h={horizon}: n={summary['n']} old={old['mean_excess_bp']:+.1f} bp "
                f"bucket={summary['mean'] * 10_000.0:+.1f} bp "
                f"block_t={_fmt(summary['block_t'], 2)} pass={passes}"
            )

        per_horizon = {int(h): [] for h in horizons}
        for draw in range(int(n_sanity)):
            random_signals = matched_control.vol_matched_random_signals(
                data, masked, seed=SANITY_BASE_SEED + draw, elig=elig, buckets=buckets,
            )
            random_events = events.collect_events(
                data, random_signals, elig, cooldown=COOLDOWN, eval_start=EVAL_START,
                horizons=horizons, forward=forward,
            )
            random_bucket = matched_control.add_event_bucket(random_events, buckets)
            for horizon in horizons:
                frame = matched_control.bucket_excess_frame(
                    random_bucket, bucket_benchmark, horizon
                )
                per_horizon[int(horizon)].append(
                    float(frame["excess"].mean()) if len(frame) else float("nan")
                )
            if draw + 1 == n_sanity or (draw + 1) % 10 == 0:
                print(f"[E1 {setup}] sanity draws {draw + 1}/{n_sanity}")

        sanity_rows = {}
        for horizon in horizons:
            values = np.asarray(per_horizon[int(horizon)], dtype=float)
            finite = values[np.isfinite(values)]
            sanity_rows[str(horizon)] = {
                "n_draws": int(finite.size),
                "mean_bp": float(finite.mean() * 10_000.0) if finite.size else float("nan"),
                "std_bp": float(finite.std() * 10_000.0) if finite.size else float("nan"),
            }
        results[setup] = {"n_events": int(len(real_events)), "horizons": horizon_rows}
        sanity[setup] = sanity_rows
    return results, sanity


def analyse_part2(data, elig, buckets, setups, n_null):
    """Part 2: exit study in R and percent units vs vol-matched random entries."""
    variants = exit_study.VARIANTS
    z = matched_control.z_crit(M_CELLS)
    results = {}
    for setup in setups:
        print(f"[E2 {setup}] building signals and entries")
        signals = build_signals(data, elig, SETUPS[setup])
        masked = exit_study.mask_ineligible(data, signals, elig)
        entries = exit_study.entry_candidates(data, masked, elig, eval_start=EVAL_START)
        print(f"[E2 {setup}] real entries: {len(entries)}")

        real = {}
        cache: dict[str, dict] = {}
        for name, variant in variants.items():
            trades = exit_study.simulate_entries(
                data, entries, variant, cost_bps=COST_BPS, cache=cache,
            )
            trades = matched_control.add_pct_returns(trades, COST_BPS)
            real[name] = trades
            if trades.empty:
                print(f"[E2 {setup}] {name}: n=0")
            else:
                print(
                    f"[E2 {setup}] {name}: n={len(trades)} "
                    f"mean r_net={trades['r_net'].mean():+.4f} "
                    f"mean pct={trades['ret_net_pct'].mean() * 10_000.0:+.1f} bp"
                )

        nulls = {name: {"r": [], "pct_bp": []} for name in variants}
        draw_stats: dict[str, int] = {"requested": 0, "drawn": 0}
        cache = {}
        for draw in range(int(n_null)):
            random_signals = matched_control.vol_matched_random_signals(
                data, masked, seed=NULL_BASE_SEED + draw, elig=elig,
                buckets=buckets, stats=draw_stats,
            )
            random_entries = exit_study.entry_candidates(
                data, random_signals, elig, eval_start=EVAL_START,
            )
            for name, variant in variants.items():
                trades = exit_study.simulate_entries(
                    data, random_entries, variant, cost_bps=COST_BPS, cache=cache,
                )
                trades = matched_control.add_pct_returns(trades, COST_BPS)
                if trades.empty:
                    nulls[name]["r"].append(float("nan"))
                    nulls[name]["pct_bp"].append(float("nan"))
                else:
                    nulls[name]["r"].append(float(trades["r_net"].mean()))
                    nulls[name]["pct_bp"].append(
                        float(trades["ret_net_pct"].mean() * 10_000.0)
                    )
            if draw + 1 == n_null or (draw + 1) % 10 == 0:
                print(f"[E2 {setup}] null draws {draw + 1}/{n_null}")

        variant_rows = {}
        for name in variants:
            trades = real[name]
            r_values = trades["r_net"].to_numpy(dtype=float) if not trades.empty else np.array([])
            pct_values = (
                trades["ret_net_pct"].to_numpy(dtype=float) if not trades.empty else np.array([])
            )
            dates = trades["entry_date"].to_list() if not trades.empty else []
            mean_r = float(r_values.mean()) if r_values.size else float("nan")
            mean_pct_bp = float(pct_values.mean() * 10_000.0) if pct_values.size else float("nan")

            r_null = np.asarray(nulls[name]["r"], dtype=float)
            r_null = r_null[np.isfinite(r_null)]
            pct_null = np.asarray(nulls[name]["pct_bp"], dtype=float)
            pct_null = pct_null[np.isfinite(pct_null)]
            null_mean_r = float(r_null.mean()) if r_null.size else float("nan")
            null_std_r = float(r_null.std()) if r_null.size else float("nan")
            null_mean_pct = float(pct_null.mean()) if pct_null.size else float("nan")
            null_std_pct = float(pct_null.std()) if pct_null.size else float("nan")
            gap_r = mean_r - null_mean_r
            gap_pct = mean_pct_bp - null_mean_pct
            sign_agree = bool(
                math.isfinite(gap_r)
                and math.isfinite(gap_pct)
                and ((gap_r > 0 and gap_pct > 0) or (gap_r < 0 and gap_pct < 0))
            )

            block_r = matched_control.block_summary(
                r_values, dates, null_mean_r,
                n_resamples=BOOTSTRAP_RESAMPLES, seed=BOOTSTRAP_SEED,
            )
            block_pct = matched_control.block_summary(
                pct_values, dates, null_mean_pct / 10_000.0,
                n_resamples=BOOTSTRAP_RESAMPLES, seed=BOOTSTRAP_SEED,
            )
            pass_r = matched_control.cell_passes(
                block_r["block_t"], block_r["reference_in_ci"], z
            )
            pass_pct = matched_control.cell_passes(
                block_pct["block_t"], block_pct["reference_in_ci"], z
            )
            passes = bool(pass_r and pass_pct and sign_agree)
            variant_rows[name] = {
                "n": int(r_values.size),
                "mean_r_net": mean_r,
                "mean_pct_bp": mean_pct_bp,
                "null_mean_r": null_mean_r,
                "null_std_r": null_std_r,
                "null_mean_pct_bp": null_mean_pct,
                "null_std_pct_bp": null_std_pct,
                "n_null_r": int(r_null.size),
                "n_null_pct": int(pct_null.size),
                "gap_r": gap_r,
                "gap_pct_bp": gap_pct,
                "sign_agree": sign_agree,
                "block_r": block_r,
                "block_pct": block_pct,
                "pass_r": pass_r,
                "pass_pct": pass_pct,
                "passes": passes,
            }
            print(
                f"[E2 {setup}] {name}: gapR={gap_r:+.4f} gapPct={gap_pct:+.1f} bp "
                f"signs={sign_agree} block_t(R)={_fmt(block_r['block_t'], 2)} "
                f"block_t(pct)={_fmt(block_pct['block_t'], 2)} pass={passes}"
            )

        results[setup] = {
            "n_entries": int(len(entries)),
            "shortfall": {
                "n_draws": int(n_null),
                "requested_total": int(draw_stats.get("requested", 0)),
                "drawn_total": int(draw_stats.get("drawn", 0)),
                "mean_requested_per_draw": (
                    float(draw_stats.get("requested", 0)) / float(n_null) if n_null else float("nan")
                ),
                "mean_drawn_per_draw": (
                    float(draw_stats.get("drawn", 0)) / float(n_null) if n_null else float("nan")
                ),
                "shortfall_total": int(
                    draw_stats.get("requested", 0) - draw_stats.get("drawn", 0)
                ),
            },
            "variants": variant_rows,
        }
    return results


def write_markdown(path, *, generated_at, setups, horizons, n_buckets, n_sanity, n_null,
                   panel, revision, dirty, command, part1, sanity, part2, elapsed_minutes):
    """Render the vol-matched study report."""
    z = matched_control.z_crit(M_CELLS)
    e1_pass = [
        f"`{setup}` h={horizon}"
        for setup in setups
        for horizon in horizons
        if part1[setup]["horizons"][str(horizon)]["passes"]
    ]
    e2_pass = [
        f"`{setup}` {name}"
        for setup in setups
        for name in exit_study.VARIANTS
        if part2[setup]["variants"][name]["passes"]
    ]
    sanity_flags = [
        f"`{setup}` h={horizon}: mean {_fmt_bp(sanity[setup][str(horizon)]['mean_bp'])} bp"
        for setup in setups
        for horizon in horizons
        if math.isfinite(sanity[setup][str(horizon)]["mean_bp"])
        and abs(sanity[setup][str(horizon)]["mean_bp"]) > 3.0
    ]

    lines = [
        "# Volatility-Matched Re-measurement (E4) — event study (E1) and exit study (E2)",
        "",
        f"Generated `{generated_at}` by `scripts/research_vol_matched.py`.",
        "",
        WARNING,
        "",
        CAPACITY,
        "",
        "## Why",
        "",
        WHY,
        "",
        "## Pre-declared rule",
        "",
        PRE_DECLARED_RULE,
        "",
        "## Definitions",
        "",
    ]
    lines.extend(definitions_text(horizons, n_buckets, n_sanity, n_null))
    lines.extend(
        [
            "",
            "## Data and provenance",
            "",
            "| Item | Value |",
            "|---|---|",
            f"| Requested span | {REQUESTED_START} -> {panel['requested_end']} |",
            f"| Actual panel | {panel['actual_start']} -> {panel['actual_end']} |",
            f"| Tradable symbols | {panel['n_symbols']} |",
            f"| Dropped at load | {panel['n_dropped']} |",
            f"| Evaluation start | {EVAL_START} |",
            f"| Volatility buckets | {n_buckets} |",
            f"| Git revision | `{revision}` |",
            f"| Dirty worktree | {_fmt_bool(dirty)} |",
            f"| Command | `{command}` |",
            f"| Elapsed | {_fmt(elapsed_minutes, 1)} minutes |",
            "",
        ]
    )
    if sanity_flags:
        lines.extend(
            [
                "**SANITY WARNING: the vol-matched random event sets show a mean bucket excess "
                "whose absolute value exceeds 3 bp in at least one cell:** "
                + "; ".join(sanity_flags) + ".",
                "",
            ]
        )

    lines.extend(["## Part 1 — event study vs the volatility-bucket benchmark", ""])
    for setup in setups:
        payload = part1[setup]
        lines.extend(
            [
                f"### `{setup}`",
                "",
                f"Events after cooldown: {payload['n_events']}.",
                "",
                "| h | n | old excess vs universe (bp) | bucket excess (bp) | 95% CI (bp) | "
                "hit rate | reference in CI | block t | passes |",
                "|---|---|---|---|---|---|---|---|---|",
            ]
        )
        for horizon in horizons:
            row = payload["horizons"][str(horizon)]
            ci = row["ci95_bp"]
            lines.append(
                f"| {horizon} | {row['n']} | {_fmt_bp(row['old_excess_bp'])} | "
                f"{_fmt_bp(row['new_excess_bp'])} | "
                f"[{_fmt_bp(ci[0])}, {_fmt_bp(ci[1])}] | {_fmt_rate(row['hit_rate'])} | "
                f"{_fmt_bool(row['reference_in_ci'])} | {_fmt(row['block_t'], 2)} | "
                f"{_fmt_bool(row['passes'])} |"
            )
        lines.append("")

    lines.extend(
        [
            "## Sanity check — vol-matched random event sets",
            "",
            "Each draw uses the same per-date/per-bucket counts, cooldown and bucket excess as "
            f"the real events. Seeds {SANITY_BASE_SEED}..{SANITY_BASE_SEED + n_sanity - 1}. "
            "The mean should be about 0; a value whose absolute size exceeds 3 bp is flagged.",
            "",
            "| Setup | h | draws | mean (bp) | std (bp) |",
            "|---|---|---|---|---|",
        ]
    )
    for setup in setups:
        for horizon in horizons:
            row = sanity[setup][str(horizon)]
            lines.append(
                f"| `{setup}` | {horizon} | {row['n_draws']} | "
                f"{_fmt_bp(row['mean_bp'])} | {_fmt_bp(row['std_bp'])} |"
            )
    lines.append("")

    lines.extend(
        [
            "## Part 2 — exit study in R and percent units",
            "",
            "R means and gaps are in R units; percent means and gaps are in basis points. "
            "`null std` is the descriptive spread of the null mean, NOT a test. CI columns are "
            "the 95% month-block CI of the real trade mean; `ref in CI` says whether the "
            "vol-matched null mean sits inside it. `block t` is `(mean - null mean)/se_block`. "
            "An E2 cell passes only if both metrics pass and the two gap signs agree.",
            "",
        ]
    )
    for setup in setups:
        payload = part2[setup]
        lines.extend(
            [
                f"### `{setup}`",
                "",
                f"Real entries: {payload['n_entries']}.",
                "",
                "| Variant | n | mean r_net | null r mean | null r std | gap R | "
                "CI R | ref in CI (R) | block t (R) |",
                "|---|---|---|---|---|---|---|---|---|",
            ]
        )
        for name in exit_study.VARIANTS:
            row = payload["variants"][name]
            block = row["block_r"]
            lines.append(
                f"| {name} | {row['n']} | {_fmt(row['mean_r_net'])} | "
                f"{_fmt(row['null_mean_r'])} | {_fmt(row['null_std_r'])} | "
                f"{_fmt(row['gap_r'])} | "
                f"[{_fmt(block['ci_low'])}, {_fmt(block['ci_high'])}] | "
                f"{_fmt_bool(block['reference_in_ci'])} | {_fmt(block['block_t'], 2)} |"
            )
        lines.extend(
            [
                "",
                "| Variant | mean ret_net_pct (bp) | null pct mean (bp) | null pct std (bp) | "
                "gap pct (bp) | CI pct (bp) | ref in CI (pct) | block t (pct) | signs agree | "
                "passes |",
                "|---|---|---|---|---|---|---|---|---|---|",
            ]
        )
        for name in exit_study.VARIANTS:
            row = payload["variants"][name]
            block = row["block_pct"]
            lines.append(
                f"| {name} | {_fmt_bp(row['mean_pct_bp'])} | "
                f"{_fmt_bp(row['null_mean_pct_bp'])} | {_fmt_bp(row['null_std_pct_bp'])} | "
                f"{_fmt_bp(row['gap_pct_bp'])} | "
                f"[{_fmt_bp(block['ci_low'] * 10_000.0)}, {_fmt_bp(block['ci_high'] * 10_000.0)}] | "
                f"{_fmt_bool(block['reference_in_ci'])} | {_fmt(block['block_t'], 2)} | "
                f"{_fmt_bool(row['sign_agree'])} | {_fmt_bool(row['passes'])} |"
            )
        lines.append("")

    lines.extend(
        [
            "## Control shortfall",
            "",
            "Requested signals are the real per-date/per-bucket counts; drawn signals are what the "
            "vol-matched control could draw from the eligible pool of that bucket.",
            "",
            "| Setup | real entries | requested (total) | drawn (total) | mean requested/draw | "
            "mean drawn/draw | shortfall (total) |",
            "|---|---|---|---|---|---|---|",
        ]
    )
    for setup in setups:
        short = part2[setup]["shortfall"]
        lines.append(
            f"| `{setup}` | {part2[setup]['n_entries']} | {short['requested_total']} | "
            f"{short['drawn_total']} | {_fmt(short['mean_requested_per_draw'], 2)} | "
            f"{_fmt(short['mean_drawn_per_draw'], 2)} | {short['shortfall_total']} |"
        )

    lines.extend(["", "## Cell summary", ""])
    if not e1_pass and not e2_pass:
        lines.append("No cell passes.")
    else:
        lines.append(
            f"Part 1 (E1): {len(e1_pass)} of {len(setups) * len(horizons)} cells pass"
            + (": " + ", ".join(e1_pass) if e1_pass else ".")
        )
        lines.append("")
        lines.append(
            f"Part 2 (E2): {len(e2_pass)} of {len(setups) * len(exit_study.VARIANTS)} cells pass"
            + (": " + ", ".join(e2_pass) if e2_pass else ".")
        )
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Bucket controls match on size (pool size) and volatility, not on sector, industry, "
            "beta or liquidity beyond the existing eligibility rule.",
            "- The same four setups are re-used on the same data, so the cumulative trial count is "
            "80 cells and none of this is out-of-sample.",
            "- No holdout was used in this study.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(
        description="Volatility-matched re-measurement of the event and exit studies"
    )
    parser.add_argument("--setups", default=",".join(SETUPS),
                        help="Comma-separated setup names (default: all four)")
    parser.add_argument("--horizons", default=",".join(str(h) for h in events.DEFAULT_HORIZONS),
                        help="Comma-separated positive trading-day horizons")
    parser.add_argument("--n-buckets", type=int, default=DEFAULT_N_BUCKETS)
    parser.add_argument("--n-sanity", type=int, default=DEFAULT_N_SANITY)
    parser.add_argument("--n-null", type=int, default=DEFAULT_N_NULL)
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
    if args.n_buckets < 1:
        parser.error("--n-buckets must be >= 1")
    if args.n_sanity < 1:
        parser.error("--n-sanity must be >= 1")
    if args.n_null < 1:
        parser.error("--n-null must be >= 1")

    started = time.time()
    generated_at = datetime.now().isoformat(timespec="seconds")
    requested_end = datetime.now().strftime("%Y-%m-%d")
    revision, dirty = _git_state()

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

    print("Building eligibility, forward returns and benchmarks")
    elig = events.eligibility_frame(data)
    forward = {
        symbol: events.forward_return_frame(df, horizons)
        for symbol, df in data.items()
        if symbol not in events.TRADABLE_BENCHMARK and len(df) >= 2
    }
    buckets = matched_control.vol_bucket_frame(data, elig, n_buckets=args.n_buckets)
    universe_benchmark = events.universe_benchmark(
        data, elig, horizons=horizons, eval_start=EVAL_START, forward=forward,
    )
    bucket_benchmark = matched_control.bucket_benchmark(
        data, elig, buckets, horizons, eval_start=EVAL_START, forward=forward,
    )
    print(f"Universe benchmark dates: {len(universe_benchmark)}")
    print(f"Bucket benchmark rows: {len(bucket_benchmark)}")

    part1, sanity = analyse_part1(
        data, elig, buckets, forward, universe_benchmark, bucket_benchmark,
        setups, horizons, args.n_sanity,
    )
    part2 = analyse_part2(data, elig, buckets, setups, args.n_null)

    elapsed_minutes = (time.time() - started) / 60.0
    panel = {
        "requested_end": requested_end,
        "actual_start": str(actual_start.date()),
        "actual_end": str(actual_end.date()),
        "n_symbols": int(n_symbols),
        "n_dropped": int(len(dropped)),
        "dropped": [list(item) for item in dropped],
        "cache": cache_stats,
    }
    write_markdown(
        Path(args.report),
        generated_at=generated_at,
        setups=setups,
        horizons=horizons,
        n_buckets=args.n_buckets,
        n_sanity=args.n_sanity,
        n_null=args.n_null,
        panel=panel,
        revision=revision,
        dirty=dirty,
        command=" ".join(sys.argv),
        part1=part1,
        sanity=sanity,
        part2=part2,
        elapsed_minutes=elapsed_minutes,
    )

    e1_pass = [
        f"{setup} h={horizon}"
        for setup in setups
        for horizon in horizons
        if part1[setup]["horizons"][str(horizon)]["passes"]
    ]
    e2_pass = [
        f"{setup} {name}"
        for setup in setups
        for name in exit_study.VARIANTS
        if part2[setup]["variants"][name]["passes"]
    ]
    payload = {
        "task": "E4",
        "generated_at": generated_at,
        "command": " ".join(sys.argv),
        "pre_declared_rule": PRE_DECLARED_RULE,
        "why": WHY,
        "definitions": definitions_text(horizons, args.n_buckets, args.n_sanity, args.n_null),
        "warning": WARNING,
        "capacity_caveat": CAPACITY,
        "git": {"revision": revision, "dirty": bool(dirty)},
        "elapsed_minutes": elapsed_minutes,
        "window": {
            "requested_start": REQUESTED_START,
            "requested_end": requested_end,
            "eval_start": EVAL_START,
        },
        "panel": {
            "actual_start": panel["actual_start"],
            "actual_end": panel["actual_end"],
            "n_symbols": panel["n_symbols"],
            "n_dropped": panel["n_dropped"],
            "dropped": panel["dropped"],
            "cache": panel["cache"],
        },
        "params": {
            "setups": setups,
            "horizons": horizons,
            "n_buckets": args.n_buckets,
            "n_sanity": args.n_sanity,
            "n_null": args.n_null,
            "sanity_base_seed": SANITY_BASE_SEED,
            "null_base_seed": NULL_BASE_SEED,
            "cooldown": COOLDOWN,
            "cost_bps_per_side": COST_BPS,
            "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
            "bootstrap_seed": BOOTSTRAP_SEED,
            "m_cells_per_part": M_CELLS,
            "z_crit": matched_control.z_crit(M_CELLS),
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
        "part1": part1,
        "sanity": sanity,
        "part2": part2,
        "cell_summary": {
            "e1_passing": e1_pass,
            "e2_passing": e2_pass,
            "e1_total": len(setups) * len(horizons),
            "e2_total": len(setups) * len(exit_study.VARIANTS),
            "no_cell_passes": not e1_pass and not e2_pass,
        },
    }

    json_dir = Path(args.json_dir)
    json_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = json_dir / f"vol_matched_{stamp}.json"
    json_path.write_text(json.dumps(_json_safe(payload), indent=2), encoding="utf-8")
    print(f"Wrote {Path(args.report)} and {json_path}")
    print(f"Elapsed: {elapsed_minutes:.1f} minutes; dirty={dirty}")


if __name__ == "__main__":
    main()
