#!/usr/bin/env python
"""Freeze the Phase 4 ETF snapshot and write a data-quality report (F2).

Downloads the frozen 20-symbol ETF universe twice, runs pure data-quality
checks, and only writes the snapshot when there are no HARD findings.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.research.data_quality import (  # noqa: E402
    build_manifest,
    compare_returns,
    run_all,
    sha256_of_file,
)

FROZEN_SYMBOLS = [
    "SPY",
    "QQQ",
    "IWM",
    "EFA",
    "EEM",
    "XLB",
    "XLE",
    "XLF",
    "XLI",
    "XLK",
    "XLP",
    "XLU",
    "XLV",
    "XLY",
    "TLT",
    "IEF",
    "LQD",
    "GLD",
    "VNQ",
    "SHY",
]
START = "2003-01-01"
COLUMNS = [
    "Open",
    "High",
    "Low",
    "Close",
    "Adj Close",
    "Volume",
    "Dividends",
    "Stock Splits",
]


def _today() -> str:
    return datetime.now(UTC).date().isoformat()


def _run_date() -> str:
    return datetime.now(UTC).strftime("%Y%m%d")


def _git_revision() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        )
        return out.strip()
    except Exception:
        return "unknown"


def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=COLUMNS)
    out = df.copy()
    if isinstance(out.columns, pd.MultiIndex):
        # yfinance may return MultiIndex columns; pick first ticker level if present.
        if out.columns.nlevels == 2:
            lvl0 = out.columns.get_level_values(0)
            lvl1 = out.columns.get_level_values(1)
            if set(FROZEN_SYMBOLS).intersection(set(lvl0)):
                # ticker first
                ticker = [t for t in lvl0 if t in FROZEN_SYMBOLS][0]
                out = out[ticker]
            elif set(FROZEN_SYMBOLS).intersection(set(lvl1)):
                ticker = [t for t in lvl1 if t in FROZEN_SYMBOLS][0]
                out = out.xs(ticker, axis=1, level=1, drop_level=True)
            else:
                out.columns = [c[0] if isinstance(c, tuple) else c for c in out.columns]
    out = out.rename(columns={c: str(c).strip() for c in out.columns})
    # Keep only required columns, create missing action columns as 0.
    for col in ["Dividends", "Stock Splits"]:
        if col not in out.columns:
            out[col] = 0.0
    missing = [c for c in COLUMNS if c not in out.columns]
    if missing:
        # Return as-is with available columns; checks will flag.
        for c in missing:
            out[c] = pd.NA
    out = out[COLUMNS].copy()
    idx = pd.to_datetime(out.index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_convert(None)
    out.index = pd.DatetimeIndex(idx).normalize()
    out = out.sort_index()
    return out


def _download_once(symbol: str, start: str, end: str) -> pd.DataFrame:
    last_err = None
    for attempt in range(3):
        try:
            df = yf.download(
                symbol,
                start=start,
                end=end,
                auto_adjust=False,
                actions=True,
                repair=False,
                progress=False,
                threads=False,
            )
            return _normalize_df(df)
        except Exception as exc:  # pragma: no cover - network
            last_err = exc
            if attempt < 2:
                time.sleep(2)
    raise RuntimeError(f"download failed for {symbol}: {last_err}")


def _download_twice(symbols: list[str], start: str, end: str) -> tuple[dict, dict, list[dict]]:
    first: dict[str, pd.DataFrame] = {}
    second: dict[str, pd.DataFrame] = {}
    comparisons: list[dict] = []
    for i, sym in enumerate(symbols):
        df1 = _download_once(sym, start, end)
        first[sym] = df1
        if i < len(symbols) - 1:
            time.sleep(2)
    time.sleep(10)
    for i, sym in enumerate(symbols):
        df2 = _download_once(sym, start, end)
        second[sym] = df2
        a, b = first[sym], df2
        common = a.index.intersection(b.index)
        close_equal = bool(a.loc[common, "Close"].equals(b.loc[common, "Close"])) if len(common) else False
        ret_findings = compare_returns(a, b)
        ret_frac = None
        ret_count = None
        if ret_findings:
            # compare_returns returns WARN with count when fraction > 0.02; compute exact anyway
            pass
        # compute exact fraction for report
        if len(common) >= 2:
            ra = a.loc[common, "Adj Close"].astype(float).pct_change().dropna()
            rb = b.loc[common, "Adj Close"].astype(float).pct_change().dropna()
            common_ret = ra.index.intersection(rb.index)
            if len(common_ret):
                diff = (ra.loc[common_ret] - rb.loc[common_ret]).abs()
                ret_count = int((diff > 0.0005).sum())
                ret_frac = ret_count / len(common_ret)
            else:
                ret_count, ret_frac = 0, 0.0
        else:
            ret_count, ret_frac = 0, 0.0
        comparisons.append(
            {
                "symbol": sym,
                "rows_pull1": len(a),
                "rows_pull2": len(b),
                "close_equal_common": close_equal,
                "ret_diff_count_tol_0005": ret_count,
                "ret_diff_fraction_tol_0005": ret_frac,
            }
        )
        if i < len(symbols) - 1:
            time.sleep(2)
    return first, second, comparisons


def _drop_trailing_nan_close(symbol: str, df: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
    if df.empty or "Close" not in df.columns:
        return df, False
    if pd.isna(df["Close"].iloc[-1]):
        return df.iloc[:-1].copy(), True
    return df, False


def _tiingo_cross_check(symbols: list[str], start: str, end: str, refs: dict[str, pd.DataFrame]) -> dict:
    token = __import__("os").environ.get("TIINGO_API_KEY")
    if not token:
        return {"status": "NOT RUN (no key)", "rows": []}
    rows = []
    # 50 requests/hour => 72 seconds between requests.
    for i, sym in enumerate(symbols):
        url = (
            f"https://api.tiingo.com/tiingo/daily/{sym}/prices"
            f"?startDate={start}&endDate={end}&format=json"
        )
        req = Request(url, headers={"Content-Type": "application/json", "Authorization": f"Token {token}"})
        with urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        tdf = pd.DataFrame(payload)
        if not tdf.empty and "adjClose" in tdf.columns and "date" in tdf.columns:
            tdf.index = pd.to_datetime(tdf["date"]).dt.tz_localize(None).dt.normalize()
            tdf = tdf.sort_index()
            tdf = pd.DataFrame({"Adj Close": tdf["adjClose"].astype(float)}, index=tdf.index)
        else:
            tdf = pd.DataFrame(columns=["Adj Close"])
        ref = refs.get(sym, pd.DataFrame())
        common = ref.index.intersection(tdf.index) if not ref.empty and not tdf.empty else pd.Index([])
        if len(common) >= 2:
            ra = ref.loc[common, "Adj Close"].astype(float).pct_change().dropna()
            rb = tdf.loc[common, "Adj Close"].astype(float).pct_change().dropna()
            common_ret = ra.index.intersection(rb.index)
            if len(common_ret):
                diff = (ra.loc[common_ret] - rb.loc[common_ret]).abs()
                count = int((diff > 0.0005).sum())
                frac = count / len(common_ret)
            else:
                count, frac = 0, 0.0
        else:
            count, frac = 0, 0.0
        rows.append({"symbol": sym, "common_return_days": int(len(common) - 1) if len(common) >= 2 else 0, "ret_diff_count_tol_0005": count, "ret_diff_fraction_tol_0005": frac})
        if i < len(symbols) - 1:
            time.sleep(72)
    return {"status": "RUN", "rows": rows}


def _write_report(path: Path, *, symbol_table, findings, comparisons, tiingo, manifest_sha, revision, snapshot_dir, hard_count, warn_count):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    lines.append("# ETF Data Quality Report (F2)")
    lines.append("")
    lines.append(f"- Generated (UTC): {datetime.now(UTC).isoformat()}")
    lines.append(f"- Code revision: `{revision}`")
    lines.append(f"- Snapshot dir: `{snapshot_dir}`")
    lines.append(f"- Manifest sha256: `{manifest_sha}`")
    lines.append(f"- HARD findings: {hard_count}")
    lines.append(f"- WARN findings: {warn_count}")
    lines.append("")
    lines.append("## Symbol table")
    lines.append("")
    lines.append("| Symbol | First date | Last date | Rows |")
    lines.append("|---|---:|---:|---:|")
    for r in symbol_table:
        lines.append(f"| {r['symbol']} | {r['first_date']} | {r['last_date']} | {r['rows']} |")
    lines.append("")
    lines.append("## Findings")
    lines.append("")
    if findings:
        lines.append("| Symbol | Check | Severity | Count | Detail |")
        lines.append("|---|---|---|---:|---|")
        for f in findings:
            lines.append(f"| {f.symbol} | {f.check} | {f.severity} | {f.count} | {f.detail} |")
    else:
        lines.append("No WARN/HARD findings.")
    lines.append("")
    lines.append("## Two-pull comparison")
    lines.append("")
    lines.append("| Symbol | Rows pull 1 | Rows pull 2 | Close equal (common) | Ret diff count (tol 0.0005) | Ret diff fraction |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for c in comparisons:
        frac = c["ret_diff_fraction_tol_0005"]
        frac_s = f"{frac:.6f}" if isinstance(frac, float) else str(frac)
        lines.append(
            f"| {c['symbol']} | {c['rows_pull1']} | {c['rows_pull2']} | {c['close_equal_common']} | {c['ret_diff_count_tol_0005']} | {frac_s} |"
        )
    lines.append("")
    lines.append("## Tiingo cross-check")
    lines.append("")
    if tiingo.get("status") != "RUN":
        lines.append(f"Tiingo cross-check: {tiingo.get('status', 'NOT RUN (no key)')}")
    else:
        lines.append("Tiingo cross-check: RUN (summary only; no Tiingo price data saved)")
        lines.append("")
        lines.append("| Symbol | Common return days | Ret diff count (tol 0.0005) | Ret diff fraction |")
        lines.append("|---|---:|---:|---:|")
        for r in tiingo["rows"]:
            frac = r["ret_diff_fraction_tol_0005"]
            frac_s = f"{frac:.6f}" if isinstance(frac, float) else str(frac)
            lines.append(f"| {r['symbol']} | {r['common_return_days']} | {r['ret_diff_count_tol_0005']} | {frac_s} |")
    lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default=START)
    parser.add_argument("--end", default=_today())
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--report", default="docs/backtests/research/ETF_DATA_QUALITY.md")
    args = parser.parse_args()

    end_request = args.end
    # yfinance end is exclusive; include requested end day.
    end_exclusive = (pd.Timestamp(end_request) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    run_date = _run_date()
    snapshot_dir = Path(args.out_dir) if args.out_dir else Path("research_data") / f"etf_{run_date}"
    report_path = Path(args.report)
    revision = _git_revision()

    print(f"F2 snapshot start={args.start} end={end_request} (yf exclusive {end_exclusive})")
    first, _second, comparisons = _download_twice(FROZEN_SYMBOLS, args.start, end_exclusive)

    # Use SPY as calendar
    spy = first.get("SPY")
    if spy is None or spy.empty:
        _write_report(report_path, symbol_table=[], findings=[], comparisons=comparisons, tiingo={"status": "NOT RUN (SPY missing)"}, manifest_sha="NONE", revision=revision, snapshot_dir=str(snapshot_dir), hard_count=1, warn_count=0)
        print("STOP: SPY missing/empty")
        return 2
    calendar = pd.DatetimeIndex(spy.index)

    all_findings = []
    dropped_trailing = {}
    cleaned: dict[str, pd.DataFrame] = {}
    for sym in FROZEN_SYMBOLS:
        df = first.get(sym, pd.DataFrame(columns=COLUMNS)).copy()
        df, dropped = _drop_trailing_nan_close(sym, df)
        dropped_trailing[sym] = dropped
        cleaned[sym] = df
        findings = run_all(sym, df, calendar=calendar, as_of=end_request)
        all_findings.extend(findings)

    hard = [f for f in all_findings if f.severity == "HARD"]
    warn = [f for f in all_findings if f.severity == "WARN"]

    symbol_table = []
    for sym in FROZEN_SYMBOLS:
        df = cleaned.get(sym, pd.DataFrame())
        symbol_table.append(
            {
                "symbol": sym,
                "first_date": df.index.min().date().isoformat() if len(df) else "",
                "last_date": df.index.max().date().isoformat() if len(df) else "",
                "rows": int(len(df)),
            }
        )

    if hard:
        _write_report(report_path, symbol_table=symbol_table, findings=all_findings, comparisons=comparisons, tiingo={"status": "NOT RUN (HARD findings)"}, manifest_sha="NONE", revision=revision, snapshot_dir=str(snapshot_dir), hard_count=len(hard), warn_count=len(warn))
        print(f"STOP: {len(hard)} HARD findings; snapshot not written")
        return 1

    snapshot_dir.mkdir(parents=True, exist_ok=False)
    manifest_entries = []
    for sym in FROZEN_SYMBOLS:
        df = cleaned[sym]
        out_path = snapshot_dir / f"{sym}.csv.gz"
        df.to_csv(out_path, compression="gzip")
        manifest_entries.append(
            {
                "symbol": sym,
                "file_name": out_path.name,
                "sha256": sha256_of_file(out_path),
                "rows": int(len(df)),
                "first_date": df.index.min().date().isoformat() if len(df) else "",
                "last_date": df.index.max().date().isoformat() if len(df) else "",
                "source": "yfinance",
                "auto_adjust": False,
                "yfinance_version": getattr(yf, "__version__", "unknown"),
                "created_utc": datetime.now(UTC).isoformat(),
            }
        )
    manifest = build_manifest(manifest_entries)
    manifest["pandas_version"] = pd.__version__
    manifest["yfinance_version"] = getattr(yf, "__version__", "unknown")
    manifest["auto_adjust"] = False
    manifest["source"] = "yfinance"
    manifest["start"] = args.start
    manifest["end"] = end_request
    manifest_path = snapshot_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest_sha = sha256_of_file(manifest_path)

    tiingo = _tiingo_cross_check(FROZEN_SYMBOLS, args.start, end_request, cleaned)
    _write_report(report_path, symbol_table=symbol_table, findings=all_findings, comparisons=comparisons, tiingo=tiingo, manifest_sha=manifest_sha, revision=revision, snapshot_dir=str(snapshot_dir), hard_count=len(hard), warn_count=len(warn))

    print(f"snapshot_written={snapshot_dir}")
    print(f"manifest_sha256={manifest_sha}")
    print(f"hard={len(hard)} warn={len(warn)}")
    print(f"report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
