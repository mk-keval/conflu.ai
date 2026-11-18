#!/usr/bin/env python
"""Pre-2016 window study for H-16 (E8).

Runs the pre-registered check: does ``breakout_52week`` show positive
volatility-bucket excess at h=60 on entries 2006-01-01..2015-12-31?  Only the
single primary cell has a pass/fail rule; the other 19 setup x horizon cells
are descriptive.  The pre-registration is frozen in
``docs/backtests/research/PREREGISTRATION-H-16-v1.md``.

Writes ``docs/backtests/research/WINDOW_STUDY_H16.md`` and a JSON under
``docs/backtests/research/event_study/``.

Usage:
    python scripts/research_window_study.py
    python scripts/research_window_study.py --setups breakout_52week --n-sanity 2 \\
        --report "$env:TEMP/ws/r.md" --json-dir "$env:TEMP/ws"
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

from backend.app.research import events, exit_study, matched_control, window_study
from backend.app.research.data import download_daily, load_universe, panel_span
from backend.app.research.engine import NON_TRADABLE
from backend.app.research.indicators import add_indicators
from backend.app.research.setups import SETUPS

REQUESTED_START = "2005-01-01"
REQUESTED_END = "2015-12-31"
EVAL_START = "2006-01-01"
COOLDOWN = 5
HORIZONS = (1, 5, 10, 20, 60)
N_BUCKETS = 10
N_SANITY = 20
SANITY_BASE_SEED = 90000
BOOTSTRAP_RESAMPLES = 2000
BOOTSTRAP_SEED = 42
PRIMARY_SETUP = "breakout_52week"
PRIMARY_HORIZON = 60
M_CELLS = 1
DEFAULT_REPORT = "docs/backtests/research/WINDOW_STUDY_H16.md"
DEFAULT_JSON_DIR = "docs/backtests/research/event_study"
PREREGISTRATION = "docs/backtests/research/PREREGISTRATION-H-16-v1.md"

LIMITS = [
    "In-sample, survivorship-biased universe; no walk-forward.",
    "The universe is today's S&P 500 snapshot; the bias is larger for 2006-2015 than for "
    "later windows, and there is no point-in-time membership; results cannot rule out "
    "survivorship.",
    "The liquidity gate is evaluated on dividend-adjusted prices, which is stricter in "
    "older years.",
    "Exploratory: never the scorecard, D-75 pass bar, kill rule or any forward verdict.",
    "Capacity and slot competition are ignored.",
    "The descriptive cells share signals and are not independent trials.",
    "The bucket benchmark is a same-date eligibility mean, not sector- or size-matched.",
]

PREREG_FIELDS = [
    "Research question (one sentence)",
    "Primary threshold",
    "Direction",
    "Significance rule",
]


def build_parser() -> argparse.ArgumentParser:
    """Argument parser; every default is a pre-registered value."""
    parser = argparse.ArgumentParser(
        description="Pre-2016 window study for H-16 (breakout_52week h=60)"
    )
    parser.add_argument("--start", default=REQUESTED_START)
    parser.add_argument("--end", default=REQUESTED_END)
    parser.add_argument("--eval-start", default=EVAL_START)
    parser.add_argument("--setups", default=",".join(SETUPS),
                        help="Comma-separated setup names (default: all four)")
    parser.add_argument("--horizons", default=",".join(str(h) for h in HORIZONS),
                        help="Comma-separated positive trading-day horizons")
    parser.add_argument("--n-buckets", type=int, default=N_BUCKETS)
    parser.add_argument("--n-sanity", type=int, default=N_SANITY)
    parser.add_argument("--report", default=DEFAULT_REPORT)
    parser.add_argument("--json-dir", default=DEFAULT_JSON_DIR)
    return parser


def build_signals(data, elig, setup_fn):
    """Real setup signals; benchmark/ineligible symbols get an all-False series."""
    signals = {}
    for symbol, df in data.items():
        if symbol in NON_TRADABLE or symbol not in elig.columns or not bool(elig[symbol].any()):
            signals[symbol] = pd.Series(False, index=df.index)
            continue
        signals[symbol] = setup_fn(df).reindex(df.index, fill_value=False).fillna(False).astype(bool)
    return signals


def preregistration_quote(path: str = PREREGISTRATION) -> dict[str, str]:
    """Read the frozen question and pass-rule rows verbatim from the file."""
    text = Path(path).read_text(encoding="utf-8")
    rows: dict[str, str] = {}
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) >= 2 and cells[0] in PREREG_FIELDS:
            rows[cells[0]] = cells[1]
    missing = [field for field in PREREG_FIELDS if field not in rows]
    if missing:
        raise ValueError(f"pre-registration is missing field(s): {missing}")
    return rows


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


def matches_preregistration(args, setups, horizons) -> bool:
    """True only when every flag equals the pre-registered value."""
    return bool(
        args.start == REQUESTED_START
        and args.end == REQUESTED_END
        and args.eval_start == EVAL_START
        and setups == list(SETUPS)
        and horizons == list(HORIZONS)
        and args.n_buckets == N_BUCKETS
        and args.n_sanity == N_SANITY
    )


def analyse_setup(data, elig, buckets, forward, bucket_benchmark, setup, horizons, n_sanity):
    """Real cells plus vol-matched sanity draws for one setup."""
    print(f"[H-16 {setup}] building signals and events")
    signals = build_signals(data, elig, SETUPS[setup])
    masked = exit_study.mask_ineligible(data, signals, elig)
    real = events.collect_events(
        data, masked, elig, cooldown=COOLDOWN, eval_start=EVAL_START,
        horizons=horizons, forward=forward,
    )
    with_bucket = matched_control.add_event_bucket(real, buckets)
    print(f"[H-16 {setup}] events after cooldown: {len(real)}")

    rows = {}
    frames = {}
    for horizon in horizons:
        frame = matched_control.bucket_excess_frame(with_bucket, bucket_benchmark, horizon)
        summary = matched_control.block_summary(
            frame["excess"].to_numpy(dtype=float),
            frame["entry_date"].to_list(),
            0.0,
            n_resamples=BOOTSTRAP_RESAMPLES,
            seed=BOOTSTRAP_SEED,
        )
        hit_rate = float((frame["excess"] > 0).mean()) if len(frame) else float("nan")
        raw_bp = float(frame["ret"].mean() * 10_000.0) if len(frame) else float("nan")
        rows[str(horizon)] = {
            "n": int(summary["n"]),
            "raw_mean_bp": raw_bp,
            "bucket_excess_bp": float(summary["mean"] * 10_000.0),
            "ci95_bp": [summary["ci_low"] * 10_000.0, summary["ci_high"] * 10_000.0],
            "hit_rate": hit_rate,
            "block_t": summary["block_t"],
        }
        frames[str(horizon)] = frame
        print(
            f"[H-16 {setup}] h={horizon}: n={summary['n']} "
            f"raw={raw_bp:+.1f} bp excess={summary['mean'] * 10_000.0:+.1f} bp "
            f"block_t={_fmt(summary['block_t'], 2)}"
        )

    sanity = {str(horizon): [] for horizon in horizons}
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
            sanity[str(horizon)].append(
                float(frame["excess"].mean()) if len(frame) else float("nan")
            )
        if draw + 1 == n_sanity or (draw + 1) % 10 == 0:
            print(f"[H-16 {setup}] sanity draws {draw + 1}/{n_sanity}")

    sanity_rows = {}
    for horizon in horizons:
        values = np.asarray(sanity[str(horizon)], dtype=float)
        finite = values[np.isfinite(values)]
        mean_bp = float(finite.mean() * 10_000.0) if finite.size else float("nan")
        sanity_rows[str(horizon)] = {
            "n_draws": int(finite.size),
            "mean_bp": mean_bp,
            "std_bp": float(finite.std() * 10_000.0) if finite.size else float("nan"),
            "flag": bool(math.isfinite(mean_bp) and abs(mean_bp) > 3.0),
        }

    return {
        "n_events": int(len(real)),
        "horizons": rows,
        "sanity": sanity_rows,
        "per_year": {
            str(horizon): window_study.by_year_excess(frames[str(horizon)])
            for horizon in horizons
        },
    }


def write_markdown(path, *, generated_at, command, quote, args, setups, horizons,
                   panel, revision, dirty, matches, elapsed_minutes, results,
                   thinning, primary, primary_pass):
    """Render the pre-registered report; mechanical content only."""
    z = matched_control.z_crit(M_CELLS)
    lines = [
        "# Pre-2016 Window Study (H-16) — breakout 52week h=60",
        "",
        f"Generated `{generated_at}` by `scripts/research_window_study.py`.",
        "",
        "## 1. Pre-registration quote",
        "",
        "Verbatim from `docs/backtests/research/PREREGISTRATION-H-16-v1.md`:",
        "",
    ]
    for field in PREREG_FIELDS:
        lines.append(f"> {field}: {quote[field]}")
    lines.extend(["", "## 2. Primary cell", ""])
    lines.extend(
        [
            f"Setup `{PRIMARY_SETUP}`, horizon {PRIMARY_HORIZON}, entries from {EVAL_START}.",
            "",
            "| Item | Value |",
            "|---|---|",
            f"| n | {primary['n']} |",
            f"| Mean bucket excess (bp) | {_fmt_bp(primary['mean_bp'])} |",
            f"| 95% month-block CI (bp) | "
            f"[{_fmt_bp(primary['ci_low_bp'])}, {_fmt_bp(primary['ci_high_bp'])}] |",
            f"| block_t | {_fmt(primary['block_t'], 2)} |",
            f"| z_crit(1) | {z:.2f} |",
            "",
            "PRE-REGISTERED PRIMARY CELL: " + ("PASS" if primary_pass else "FAIL"),
            "",
        ]
    )
    lines.extend(
        [
            "## 3. Data and provenance",
            "",
            "| Item | Value |",
            "|---|---|",
            f"| Requested span | {args.start} -> {args.end} |",
            f"| Actual panel | {panel['actual_start']} -> {panel['actual_end']} |",
            f"| Tradable symbols | {panel['n_symbols']} |",
            f"| Dropped at load | {panel['n_dropped']} |",
            f"| Evaluation start | {args.eval_start} |",
            f"| Git revision | `{revision}` |",
            f"| Dirty worktree | {_fmt_bool(dirty)} |",
            f"| Matches pre-registration | {_fmt_bool(matches)} |",
            f"| Command | `{command}` |",
            f"| Elapsed | {_fmt(elapsed_minutes, 1)} minutes |",
            "",
        ]
    )
    lines.extend(
        [
            "## 4. Panel thinning",
            "",
            "Eligible symbols are those passing the liquidity gate on at least one day of the year.",
            "",
            "| Year | Eligible symbols |",
            "|---|---|",
        ]
    )
    for year in sorted(thinning):
        lines.append(f"| {year} | {thinning[year]} |")
    lines.extend(["", "## 5. Descriptive cells (no pass/fail)", ""])
    for setup in setups:
        lines.extend(
            [
                f"### `{setup}`",
                "",
                f"Events after cooldown: {results[setup]['n_events']}.",
                "",
                "| h | n | raw mean (bp) | bucket excess (bp) | 95% CI (bp) | hit rate | block_t |",
                "|---|---|---|---|---|---|---|",
            ]
        )
        for horizon in horizons:
            row = results[setup]["horizons"][str(horizon)]
            lines.append(
                f"| {horizon} | {row['n']} | {_fmt_bp(row['raw_mean_bp'])} | "
                f"{_fmt_bp(row['bucket_excess_bp'])} | "
                f"[{_fmt_bp(row['ci95_bp'][0])}, {_fmt_bp(row['ci95_bp'][1])}] | "
                f"{_fmt_rate(row['hit_rate'])} | {_fmt(row['block_t'], 2)} |"
            )
        lines.append("")
    lines.extend(
        [
            "## 6. Per-year bucket excess for `breakout_52week`",
            "",
        ]
    )
    for horizon in (10, 20, 60):
        if str(horizon) not in results[PRIMARY_SETUP]["per_year"]:
            continue
        lines.extend(
            [
                f"### h={horizon}",
                "",
                "| Year | n | mean bucket excess (bp) | hit rate |",
                "|---|---|---|---|",
            ]
        )
        for year, row in sorted(results[PRIMARY_SETUP]["per_year"][str(horizon)].items()):
            lines.append(
                f"| {year} | {row['n']} | {_fmt_bp(row['mean_excess_bp'])} | "
                f"{_fmt_rate(row['hit_rate'])} |"
            )
        lines.append("")
    lines.extend(
        [
            "## 7. Sanity check — vol-matched random event sets",
            "",
            f"Seeds {SANITY_BASE_SEED}..{SANITY_BASE_SEED + args.n_sanity - 1}. "
            "The mean should be about 0; a value whose absolute size exceeds 3 bp is flagged.",
            "",
            "| Setup | h | draws | mean (bp) | std (bp) | flagged |",
            "|---|---|---|---|---|---|",
        ]
    )
    for setup in setups:
        for horizon in horizons:
            row = results[setup]["sanity"][str(horizon)]
            lines.append(
                f"| `{setup}` | {horizon} | {row['n_draws']} | "
                f"{_fmt_bp(row['mean_bp'])} | {_fmt_bp(row['std_bp'])} | "
                f"{_fmt_bool(row['flag'])} |"
            )
    lines.extend(["", "## 8. Limits", ""])
    lines.extend(f"- {limit}" for limit in LIMITS)
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = build_parser()
    args = parser.parse_args()

    setups = [name.strip() for name in args.setups.split(",") if name.strip()]
    unknown = [name for name in setups if name not in SETUPS]
    if unknown:
        parser.error(f"unknown setup(s): {unknown}; choose from {sorted(SETUPS)}")
    if PRIMARY_SETUP not in setups:
        parser.error(f"the pre-registered primary setup {PRIMARY_SETUP!r} must be included")
    horizons = sorted({int(h.strip()) for h in args.horizons.split(",") if h.strip()})
    if not horizons or any(h < 1 for h in horizons):
        parser.error("--horizons must be a non-empty list of integers >= 1")
    if PRIMARY_HORIZON not in horizons:
        parser.error(f"the pre-registered primary horizon {PRIMARY_HORIZON} must be included")
    if args.n_buckets < 1:
        parser.error("--n-buckets must be >= 1")
    if args.n_sanity < 1:
        parser.error("--n-sanity must be >= 1")

    started = time.time()
    generated_at = datetime.now().isoformat(timespec="seconds")
    revision, dirty = _git_state()
    matches = matches_preregistration(args, setups, horizons)

    print(f"Loading panel {args.start} -> {args.end} from .cache/research")
    symbols = load_universe()
    data, dropped, cache_stats = download_daily(
        symbols, args.start, args.end, ".cache/research",
    )
    for symbol, df in data.items():
        data[symbol] = add_indicators(df)

    try:
        window_study.assert_no_data_after(data, args.end)
    except ValueError as error:
        print(f"STOP: {error}")
        raise SystemExit(2) from error

    actual_start, actual_end = panel_span(data)
    n_symbols = sum(1 for s in data if s not in NON_TRADABLE)
    print(
        f"Panel: {actual_start.date()} -> {actual_end.date()}, {n_symbols} tradable symbols, "
        f"{len(dropped)} dropped (cache hits={cache_stats['hits']}, "
        f"downloads={cache_stats['downloaded']})"
    )
    if n_symbols < 250:
        print(f"STOP: only {n_symbols} tradable symbols loaded (minimum 250)")
        raise SystemExit(3)
    drop_rate = len(dropped) / float(max(1, len(data) + len(dropped)))
    if drop_rate > 0.40:
        print(
            f"STOP: download/drop rate {drop_rate:.1%} exceeds 40% "
            f"({len(dropped)} dropped of {len(data) + len(dropped)})"
        )
        raise SystemExit(4)
    if matches and dirty:
        print("STOP: dirty worktree during a pre-registered run")
        raise SystemExit(5)

    print("Building eligibility, forward returns and volatility buckets")
    elig = events.eligibility_frame(data)
    forward = {
        symbol: events.forward_return_frame(df, horizons)
        for symbol, df in data.items()
        if symbol not in events.TRADABLE_BENCHMARK and len(df) >= 2
    }
    buckets = matched_control.vol_bucket_frame(data, elig, n_buckets=args.n_buckets)
    bucket_benchmark = matched_control.bucket_benchmark(
        data, elig, buckets, horizons, eval_start=args.eval_start, forward=forward,
    )
    thinning = window_study.eligible_symbols_by_year(elig)
    print(f"Bucket benchmark rows: {len(bucket_benchmark)}")

    results = {}
    for setup in setups:
        results[setup] = analyse_setup(
            data, elig, buckets, forward, bucket_benchmark,
            setup, horizons, args.n_sanity,
        )

    elapsed_minutes = (time.time() - started) / 60.0
    primary_row = results[PRIMARY_SETUP]["horizons"][str(PRIMARY_HORIZON)]
    primary = {
        "n": primary_row["n"],
        "mean_bp": primary_row["bucket_excess_bp"],
        "ci_low_bp": primary_row["ci95_bp"][0],
        "ci_high_bp": primary_row["ci95_bp"][1],
        "block_t": primary_row["block_t"],
        "z_crit": matched_control.z_crit(M_CELLS),
    }
    primary_pass = window_study.primary_cell_passes(
        primary["mean_bp"], primary["ci_low_bp"], primary["block_t"], primary["z_crit"],
    )
    print(
        f"PRIMARY CELL: n={primary['n']} mean={primary['mean_bp']:+.1f} bp "
        f"ci=[{primary['ci_low_bp']:+.1f}, {primary['ci_high_bp']:+.1f}] "
        f"block_t={_fmt(primary['block_t'], 2)} "
        f"z={primary['z_crit']:.2f} -> {'PASS' if primary_pass else 'FAIL'}"
    )

    panel = {
        "requested_start": args.start,
        "requested_end": args.end,
        "actual_start": str(actual_start.date()),
        "actual_end": str(actual_end.date()),
        "n_symbols": int(n_symbols),
        "n_dropped": int(len(dropped)),
        "drop_rate": drop_rate,
        "dropped": [list(item) for item in dropped],
        "cache": cache_stats,
    }

    write_markdown(
        Path(args.report),
        generated_at=generated_at,
        command=" ".join(sys.argv),
        quote=preregistration_quote(),
        args=args,
        setups=setups,
        horizons=horizons,
        panel=panel,
        revision=revision,
        dirty=dirty,
        matches=matches,
        elapsed_minutes=elapsed_minutes,
        results=results,
        thinning=thinning,
        primary=primary,
        primary_pass=primary_pass,
    )

    payload = {
        "task": "E8",
        "hypothesis": "H-16",
        "generated_at": generated_at,
        "command": " ".join(sys.argv),
        "pre_registration": PREREGISTRATION,
        "preregistration_quote": preregistration_quote(),
        "git": {"revision": revision, "dirty": bool(dirty)},
        "matches_preregistration": matches,
        "elapsed_minutes": elapsed_minutes,
        "window": {
            "requested_start": args.start,
            "requested_end": args.end,
            "eval_start": args.eval_start,
        },
        "panel": panel,
        "params": {
            "setups": setups,
            "horizons": horizons,
            "n_buckets": args.n_buckets,
            "n_sanity": args.n_sanity,
            "sanity_base_seed": SANITY_BASE_SEED,
            "cooldown": COOLDOWN,
            "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
            "bootstrap_seed": BOOTSTRAP_SEED,
            "m_cells": M_CELLS,
            "z_crit": matched_control.z_crit(M_CELLS),
            "primary_setup": PRIMARY_SETUP,
            "primary_horizon": PRIMARY_HORIZON,
        },
        "primary_cell": {
            **primary,
            "pass": bool(primary_pass),
        },
        "panel_thinning": thinning,
        "results": results,
        "limits": LIMITS,
    }

    json_dir = Path(args.json_dir)
    json_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = json_dir / f"window_study_{stamp}.json"
    json_path.write_text(json.dumps(_json_safe(payload), indent=2), encoding="utf-8")
    print(f"Wrote {Path(args.report)} and {json_path}")
    print(f"Elapsed: {elapsed_minutes:.1f} minutes; dirty={dirty}; matches={matches}")


if __name__ == "__main__":
    main()
