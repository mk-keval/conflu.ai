#!/usr/bin/env python
"""Survivorship / current-membership size estimate (E9), MEASUREMENT only.

Compares a daily-rebalanced equal-weight portfolio of today's S&P 500
constituents with RSP (equal-weight S&P 500 ETF, point-in-time membership) and
SPY, calendar year by calendar year from 2016-01-01.

The panel is read from the existing span-keyed cache; the only symbol without a
cache entry is RSP, so RSP is the only new download.  No other URL, package or
data source is used.

Writes ``docs/backtests/research/SURVIVORSHIP_ESTIMATE.md`` and a JSON under
``docs/backtests/research/event_study/``.
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

from backend.app.research import survivorship
from backend.app.research.data import download_daily, load_universe, panel_span
from backend.app.research.engine import NON_TRADABLE

PANEL_START = "2015-01-01"
RETURN_START = "2016-01-01"
DEFAULT_REPORT = "docs/backtests/research/SURVIVORSHIP_ESTIMATE.md"
DEFAULT_JSON_DIR = "docs/backtests/research/event_study"
CACHE_DIR = ".cache/research"

DEFINITIONS = [
    "The panel = the 501 current-constituent symbols loaded exactly as in the "
    "other scripts.",
    "For each trading day d from 2016-01-01, "
    "`ew_ret[d] = mean` over panel symbols that have both `close[d]` and "
    "`close[d-1]` of `close[d]/close[d-1] - 1` (daily-rebalanced equal weight; "
    "no eligibility filter).",
    "Calendar-year return = `product(1 + ew_ret) - 1`.",
    "Benchmarks: RSP (equal-weight S&P 500 ETF, point-in-time membership, "
    "~0.20%/yr fee) and SPY, same adjusted-close method.",
    "Per year report: panel EW return, RSP return, gap = panel EW - RSP "
    "(percentage points), SPY return, symbols with data; plus the cumulative "
    "2016->latest of each series and the average annual gap.",
]

CAVEATS = [
    "Gap = survivorship + current-membership selection + RSP fees + "
    "rebalancing-method differences.",
    "It is an indicator of size, NOT a corrected estimate.",
    "It says nothing about the sign of the bias on any one signal.",
    "Daily-rebalanced equal weight is not RSP's quarterly rebalance.",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Survivorship / current-membership size estimate (MEASUREMENT)"
    )
    parser.add_argument("--start", default=PANEL_START)
    parser.add_argument("--end", default=None,
                        help="Defaults to the latest requested end in the cache manifest")
    parser.add_argument("--report", default=DEFAULT_REPORT)
    parser.add_argument("--json-dir", default=DEFAULT_JSON_DIR)
    return parser


def latest_cached_end(cache_dir: str = CACHE_DIR, start: str = PANEL_START) -> str:
    """Latest ``requested_end`` already cached for ``start``.

    The panel must be read from the cache: only RSP and SPY may be downloaded.
    Falls back to today when the manifest is absent or has no matching span.
    """
    manifest_path = Path(cache_dir) / "_manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            ends = [
                meta.get("requested_end")
                for meta in manifest.values()
                if meta.get("requested_start") == start and meta.get("requested_end")
            ]
            if ends:
                return str(max(ends))
        except Exception:
            pass
    return datetime.now().strftime("%Y-%m-%d")


def cached_symbols_for_span(symbols, cache_dir, start, end):
    """Split universe symbols into cached-for-this-span and uncached.

    Only RSP and SPY may be downloaded, so the panel request is restricted to
    symbols that already have a cache entry for the exact span.  An absent
    manifest stops the run rather than triggering a full re-download.
    """
    manifest_path = Path(cache_dir) / "_manifest.json"
    if not manifest_path.exists():
        print("STOP: cache manifest is missing; the panel must be read from cache")
        raise SystemExit(6)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    available = {
        meta.get("symbol")
        for meta in manifest.values()
        if meta.get("requested_start") == start and meta.get("requested_end") == end
    }
    cached = [symbol for symbol in symbols if symbol in available]
    uncached = [symbol for symbol in symbols if symbol not in available]
    return cached, uncached


def _git_state() -> tuple[str, bool]:
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


def _fmt_pct(value, digits=2):
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return "n/a"
    return f"{float(value) * 100:.{digits}f}%"


def _fmt_pp(value, digits=2):
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return "n/a"
    return f"{float(value):+.{digits}f} pp"


def _fmt_bool(value):
    return "yes" if value else "no"


def write_markdown(path, *, generated_at, command, revision, dirty, args,
                   panel, table, cumulative, average_gap, cache_stats, elapsed_minutes):
    ok_years = [year for year, row in table.items() if math.isfinite(row["gap_pp"])]
    positive = sum(1 for year in ok_years if table[year]["gap_pp"] > 0)
    lines = [
        "# Survivorship / Current-Membership Size Estimate (E9)",
        "",
        "**Label: MEASUREMENT — no pass/fail.**",
        "",
        f"Generated `{generated_at}` by `scripts/research_survivorship.py`.",
        "",
        "## Definitions",
        "",
    ]
    lines.extend(f"- {item}" for item in DEFINITIONS)
    lines.extend(
        [
            "",
            "## Data and provenance",
            "",
            "| Item | Value |",
            "|---|---|",
            f"| Requested span | {args.start} -> {args.end} |",
            f"| Actual panel | {panel['actual_start']} -> {panel['actual_end']} |",
            f"| Universe symbols | {panel['n_universe']} |",
            f"| Cached for span | {panel['n_cached']} |",
            f"| Not loaded (no cache, never downloaded) | {panel['n_uncached']}"
            f" ({', '.join(panel['uncached']) if panel['uncached'] else 'none'}) |",
            f"| Panel symbols loaded | {panel['n_symbols']} |",
            f"| Dropped by loader | {panel['n_dropped']} |",
            f"| Cache hits / downloads | {cache_stats['hits']} / {cache_stats['downloaded']} |",
            f"| Git revision | `{revision}` |",
            f"| Dirty worktree | {_fmt_bool(dirty)} |",
            f"| Command | `{command}` |",
            f"| Elapsed | {elapsed_minutes:.1f} minutes |",
            "",
            "## Per-year returns and gap",
            "",
            "| Year | Panel EW return | RSP return | Gap (panel - RSP) | SPY return | Symbols with data |",
            "|---|---|---|---|---|---|",
        ]
    )
    for year in sorted(table):
        row = table[year]
        lines.append(
            f"| {year} | {_fmt_pct(row['panel_return'])} | {_fmt_pct(row['rsp_return'])} | "
            f"{_fmt_pp(row['gap_pp'])} | {_fmt_pct(row['spy_return'])} | {row['symbols']} |"
        )
    lines.extend(
        [
            "",
            "## Cumulative 2016 -> latest",
            "",
            "| Series | Cumulative return |",
            "|---|---|",
            f"| Panel EW | {_fmt_pct(cumulative['panel'])} |",
            f"| RSP | {_fmt_pct(cumulative['rsp'])} |",
            f"| Gap (panel - RSP) | {_fmt_pp(cumulative['gap_pp'])} |",
            f"| SPY | {_fmt_pct(cumulative['spy'])} |",
            "",
            f"Average annual gap: {_fmt_pp(average_gap)} "
            f"({positive} of {len(ok_years)} years positive).",
            "",
            "## Caveats",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in CAVEATS)
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.end = args.end or latest_cached_end(CACHE_DIR, args.start)
    started = time.time()
    generated_at = datetime.now().isoformat(timespec="seconds")
    revision, dirty = _git_state()

    print(f"Loading panel and benchmarks {args.start} -> {args.end} from {CACHE_DIR}")
    symbols = load_universe()
    cached, uncached = cached_symbols_for_span(symbols, CACHE_DIR, args.start, args.end)
    print(
        f"Universe symbols: {len(symbols)}; cached for span: {len(cached)}; "
        f"not loaded (no cache, never downloaded): {uncached}"
    )
    data, dropped, cache_stats = download_daily(
        cached + ["RSP"], args.start, args.end, CACHE_DIR, max_age_hours=1e9,
    )
    if cache_stats["downloaded"] > 1:
        print(
            "STOP: only RSP may be downloaded, but "
            f"{cache_stats['downloaded']} symbols were downloaded"
        )
        raise SystemExit(2)
    if "RSP" not in data or "SPY" not in data:
        print("STOP: RSP or SPY is missing from the loaded data")
        raise SystemExit(3)

    for symbol in ("RSP", "SPY"):
        data[symbol] = data[symbol].loc[args.start:args.end]
    for symbol in list(data):
        if symbol not in {"RSP", "SPY"}:
            data[symbol] = data[symbol].loc[args.start:args.end]

    panel_symbols = sorted(
        symbol for symbol in symbols
        if symbol in data and symbol not in NON_TRADABLE and symbol != "RSP"
    )
    if len(panel_symbols) < 250:
        print(f"STOP: only {len(panel_symbols)} panel symbols loaded (minimum 250)")
        raise SystemExit(4)

    closes = pd.DataFrame(
        {symbol: data[symbol]["close"] for symbol in panel_symbols}
    ).sort_index()
    closes = closes.loc[pd.Timestamp(RETURN_START):]
    rsp = data["RSP"]["close"].loc[pd.Timestamp(RETURN_START):]
    spy = data["SPY"]["close"].loc[pd.Timestamp(RETURN_START):]

    panel_daily = survivorship.equal_weight_returns(closes)
    rsp_daily = survivorship.equal_weight_returns(rsp.to_frame("RSP"))
    spy_daily = survivorship.equal_weight_returns(spy.to_frame("SPY"))
    symbols_by_year = survivorship.symbols_with_data_by_year(closes)
    table = survivorship.annual_gap_table(panel_daily, rsp_daily, spy_daily, symbols_by_year)
    average_gap = survivorship.average_annual_gap(table)
    cumulative = {
        "panel": survivorship.cumulative_return(panel_daily),
        "rsp": survivorship.cumulative_return(rsp_daily),
        "spy": survivorship.cumulative_return(spy_daily),
    }
    cumulative["gap_pp"] = (cumulative["panel"] - cumulative["rsp"]) * 100.0

    actual_start, actual_end = panel_span(
        {symbol: data[symbol] for symbol in panel_symbols}
    )
    elapsed_minutes = (time.time() - started) / 60.0
    panel = {
        "actual_start": str(actual_start.date()),
        "actual_end": str(actual_end.date()),
        "n_universe": int(len(symbols)),
        "n_cached": int(len(cached)),
        "n_uncached": int(len(uncached)),
        "uncached": list(uncached),
        "n_symbols": int(len(panel_symbols)),
        "n_dropped": int(len(dropped)),
        "dropped": [list(item) for item in dropped],
    }

    write_markdown(
        Path(args.report),
        generated_at=generated_at,
        command=" ".join(sys.argv),
        revision=revision,
        dirty=dirty,
        args=args,
        panel=panel,
        table=table,
        cumulative=cumulative,
        average_gap=average_gap,
        cache_stats=cache_stats,
        elapsed_minutes=elapsed_minutes,
    )

    payload = {
        "task": "E9",
        "label": "MEASUREMENT",
        "generated_at": generated_at,
        "command": " ".join(sys.argv),
        "definitions": DEFINITIONS,
        "caveats": CAVEATS,
        "git": {"revision": revision, "dirty": bool(dirty)},
        "elapsed_minutes": elapsed_minutes,
        "span": {"start": args.start, "end": args.end},
        "panel": panel,
        "cache": cache_stats,
        "per_year": table,
        "cumulative": cumulative,
        "average_annual_gap_pp": average_gap,
    }

    json_dir = Path(args.json_dir)
    json_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = json_dir / f"survivorship_{stamp}.json"
    json_path.write_text(json.dumps(_json_safe(payload), indent=2), encoding="utf-8")
    print(f"Wrote {Path(args.report)} and {json_path}")
    print(
        f"Panel {panel['actual_start']} -> {panel['actual_end']}, "
        f"{panel['n_symbols']} symbols; average annual gap {average_gap:+.2f} pp; "
        f"dirty={dirty}"
    )
    print(f"Elapsed: {elapsed_minutes:.1f} minutes")


if __name__ == "__main__":
    main()
