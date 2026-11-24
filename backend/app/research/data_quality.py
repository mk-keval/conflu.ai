"""Pure data-quality checks for research price frames.

No I/O, no network, no randomness. Every check takes pandas objects and
returns a list of Finding records.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = [
    "Open",
    "High",
    "Low",
    "Close",
    "Adj Close",
    "Volume",
    "Dividends",
    "Stock Splits",
]


@dataclass(frozen=True)
class Finding:
    check: str
    severity: str  # "HARD" or "WARN"
    symbol: str
    detail: str
    count: int


def _rel_ok(low: float, high: float, tol: float = 1e-6) -> bool:
    """Return True when low <= high within relative tolerance."""
    if low <= high:
        return True
    scale = max(abs(low), abs(high), 1.0)
    return (low - high) / scale <= tol


def check_index(symbol: str, df: pd.DataFrame) -> list[Finding]:
    """1. duplicate or non-monotonic index -> HARD."""
    findings: list[Finding] = []
    if df.index.has_duplicates:
        n = int(df.index.duplicated().sum())
        findings.append(
            Finding("index", "HARD", symbol, "duplicate index values", n)
        )
    if not df.index.is_monotonic_increasing:
        findings.append(
            Finding("index", "HARD", symbol, "non-monotonic index", 1)
        )
    return findings


def check_ohlc_adjclose(symbol: str, df: pd.DataFrame) -> list[Finding]:
    """2. NaN in any OHLC/Adj Close or any value <= 0 -> HARD,
    except a trailing row whose Close is NaN: that is WARN."""
    findings: list[Finding] = []
    cols = ["Open", "High", "Low", "Close", "Adj Close"]
    if df.empty:
        return findings

    trailing_nan_close = bool(pd.isna(df["Close"].iloc[-1]))
    hard_mask = pd.Series(False, index=df.index)

    for col in cols:
        if col not in df.columns:
            findings.append(
                Finding("ohlc_adjclose", "HARD", symbol, f"missing column {col}", 1)
            )
            return findings
        series = df[col]
        bad = series.isna() | (series <= 0)
        if trailing_nan_close and col == "Close":
            bad = bad.copy()
            bad.iloc[-1] = False
        hard_mask = hard_mask | bad

    hard_count = int(hard_mask.sum())
    if hard_count > 0:
        findings.append(
            Finding(
                "ohlc_adjclose",
                "HARD",
                symbol,
                "NaN or <= 0 in OHLC/Adj Close",
                hard_count,
            )
        )

    if trailing_nan_close:
        findings.append(
            Finding(
                "ohlc_adjclose",
                "WARN",
                symbol,
                "trailing row has NaN Close (loader drops it and records it)",
                1,
            )
        )
    return findings


def check_ohlc_ordering(symbol: str, df: pd.DataFrame) -> list[Finding]:
    """3. OHLC ordering (Low <= Open,Close <= High, Low <= High, tol 1e-6 relative):
    WARN with count; HARD if more than 0.5% of rows violate."""
    findings: list[Finding] = []
    if df.empty:
        return findings
    required = ["Open", "High", "Low", "Close"]
    if any(c not in df.columns for c in required):
        return findings

    low = df["Low"]
    high = df["High"]
    open_ = df["Open"]
    close = df["Close"]
    bad = ~(
        pd.Series([_rel_ok(lo, o) for lo, o in zip(low, open_)], index=df.index)
        & pd.Series([_rel_ok(lo, c) for lo, c in zip(low, close)], index=df.index)
        & pd.Series([_rel_ok(lo, h) for lo, h in zip(low, high)], index=df.index)
        & pd.Series([_rel_ok(o, h) for o, h in zip(open_, high)], index=df.index)
        & pd.Series([_rel_ok(c, h) for c, h in zip(close, high)], index=df.index)
    )
    count = int(bad.sum())
    if count > 0:
        pct = count / len(df)
        severity = "HARD" if pct > 0.005 else "WARN"
        findings.append(
            Finding(
                "ohlc_ordering",
                severity,
                symbol,
                f"OHLC ordering violations ({pct:.4%} of rows)",
                count,
            )
        )
    return findings


def check_volume(symbol: str, df: pd.DataFrame) -> list[Finding]:
    """4. Volume < 0 -> HARD; zero-volume days -> WARN with the count."""
    findings: list[Finding] = []
    if "Volume" not in df.columns or df.empty:
        return findings
    vol = df["Volume"]
    neg = int((vol < 0).sum())
    zero = int((vol == 0).sum())
    if neg > 0:
        findings.append(Finding("volume", "HARD", symbol, "negative volume", neg))
    if zero > 0:
        findings.append(Finding("volume", "WARN", symbol, "zero-volume days", zero))
    return findings


def check_missing_dates(
    symbol: str, df: pd.DataFrame, calendar: pd.DatetimeIndex
) -> list[Finding]:
    """5. Missing dates versus a given trading calendar, counted only after the
    symbol's first date: WARN; HARD if more than 1% missing."""
    findings: list[Finding] = []
    if df.empty or calendar is None or len(calendar) == 0:
        return findings
    cal = pd.DatetimeIndex(calendar).sort_values()
    first = df.index.min()
    expected = cal[cal >= first]
    if len(expected) == 0:
        return findings
    present = pd.DatetimeIndex(df.index).intersection(expected)
    missing = len(expected) - len(present)
    if missing > 0:
        pct = missing / len(expected)
        severity = "HARD" if pct > 0.01 else "WARN"
        findings.append(
            Finding(
                "missing_dates",
                severity,
                symbol,
                f"missing {missing}/{len(expected)} calendar dates after first date ({pct:.4%})",
                missing,
            )
        )
    return findings


def check_close_moves(symbol: str, df: pd.DataFrame) -> list[Finding]:
    """6. Absolute one-day change of raw Close above 20% on a date with no
    Stock Splits value: WARN; above 40%: HARD."""
    findings: list[Finding] = []
    if df.empty or "Close" not in df.columns or len(df) < 2:
        return findings
    close = df["Close"].astype(float)
    prev = close.shift(1)
    pct_change = (close / prev - 1.0).abs().replace([np.inf, -np.inf], np.nan)
    splits = (
        df["Stock Splits"]
        if "Stock Splits" in df.columns
        else pd.Series(0, index=df.index)
    )
    splits = splits.fillna(0)
    no_split = splits == 0
    warn_mask = no_split & (pct_change > 0.20) & (pct_change <= 0.40)
    hard_mask = no_split & (pct_change > 0.40)
    warn_count = int(warn_mask.fillna(False).sum())
    hard_count = int(hard_mask.fillna(False).sum())
    if hard_count > 0:
        findings.append(
            Finding(
                "close_moves",
                "HARD",
                symbol,
                "raw Close move > 40% with no Stock Splits",
                hard_count,
            )
        )
    if warn_count > 0:
        findings.append(
            Finding(
                "close_moves",
                "WARN",
                symbol,
                "raw Close move > 20% with no Stock Splits",
                warn_count,
            )
        )
    return findings


def check_adj_ratio(symbol: str, df: pd.DataFrame) -> list[Finding]:
    """7. Adj Close / Close ratio changes by more than 1e-4 relative on a date
    with no Dividends > 0 and no Stock Splits > 0: WARN per date; HARD if there
    are more than 5 such dates.

    Authorized deviation (2026-11-23, user option 1): F1 spec stated 1e-6; F2
    investigation showed ~1e-6..1.6e-6 yfinance Adj Close/Close precision drift
    on non-dividend/non-split days (bond ETFs especially). Threshold relaxed to
    1e-4 to avoid precision-noise HARDs while still flagging real unexplained
    ratio changes. Logged in docs/SESSIONS/research-etf-log.nd."""
    findings: list[Finding] = []
    needed = ["Adj Close", "Close"]
    if df.empty or any(c not in df.columns for c in needed) or len(df) < 2:
        return findings
    close = df["Close"].astype(float)
    adj = df["Adj Close"].astype(float)
    ratio = adj / close
    ratio_prev = ratio.shift(1)
    rel_change = (ratio - ratio_prev).abs() / ratio_prev.abs().clip(lower=1e-12)
    div = (
        df["Dividends"].fillna(0)
        if "Dividends" in df.columns
        else pd.Series(0, index=df.index)
    )
    spl = (
        df["Stock Splits"].fillna(0)
        if "Stock Splits" in df.columns
        else pd.Series(0, index=df.index)
    )
    no_corp = (div <= 0) & (spl <= 0)
    # Authorized deviation: 1e-4 (was 1e-6 in F1 spec) for yfinance precision noise.
    bad = no_corp & (rel_change > 1e-4)
    bad = bad.fillna(False)
    if len(bad) > 0:
        bad.iloc[0] = False
    count = int(bad.sum())
    if count > 0:
        severity = "HARD" if count > 5 else "WARN"
        findings.append(
            Finding(
                "adj_ratio",
                severity,
                symbol,
                "Adj Close/Close ratio changed without dividend/split",
                count,
            )
        )
    return findings


def check_dividend_yield(symbol: str, df: pd.DataFrame) -> list[Finding]:
    """8. Dividends/Close above 5% on any date -> WARN."""
    findings: list[Finding] = []
    if df.empty or "Dividends" not in df.columns or "Close" not in df.columns:
        return findings
    div = df["Dividends"].fillna(0).astype(float)
    close = df["Close"].astype(float)
    bad = (div > 0) & (close > 0) & ((div / close) > 0.05)
    count = int(bad.sum())
    if count > 0:
        findings.append(
            Finding(
                "dividend_yield",
                "WARN",
                symbol,
                "Dividends/Close > 5%",
                count,
            )
        )
    return findings


def check_staleness(
    symbol: str, df: pd.DataFrame, as_of: pd.Timestamp | str | None
) -> list[Finding]:
    """9. Staleness: last index date older than a given as of date minus 4
    calendar days -> WARN."""
    findings: list[Finding] = []
    if df.empty or as_of is None:
        return findings
    as_of_ts = pd.Timestamp(as_of).normalize()
    last = pd.Timestamp(df.index.max()).normalize()
    if last < as_of_ts - pd.Timedelta(days=4):
        findings.append(
            Finding(
                "staleness",
                "WARN",
                symbol,
                f"last date {last.date()} older than as_of {as_of_ts.date()} minus 4 days",
                1,
            )
        )
    return findings


def compare_returns(
    df_a: pd.DataFrame, df_b: pd.DataFrame, tol: float = 0.0005
) -> list[Finding]:
    """10. fraction of common dates where |Adj Close daily return difference| > tol.
    Return WARN if the fraction > 0.02, else no finding."""
    findings: list[Finding] = []
    if df_a.empty or df_b.empty:
        return findings
    a = df_a["Adj Close"].astype(float).sort_index()
    b = df_b["Adj Close"].astype(float).sort_index()
    common = a.index.intersection(b.index)
    if len(common) < 2:
        return findings
    ra = a.loc[common].pct_change().dropna()
    rb = b.loc[common].pct_change().dropna()
    common_ret = ra.index.intersection(rb.index)
    if len(common_ret) == 0:
        return findings
    diff = (ra.loc[common_ret] - rb.loc[common_ret]).abs()
    bad = int((diff > tol).sum())
    frac = bad / len(common_ret)
    if frac > 0.02:
        findings.append(
            Finding(
                "compare_returns",
                "WARN",
                "MULTI",
                f"return difference > {tol} on {frac:.4%} of common dates",
                bad,
            )
        )
    return findings


def sha256_of_file(path: str | Path) -> str:
    """SHA-256 hex digest of a file's bytes."""
    p = Path(path)
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_manifest(entries: list[dict]) -> dict:
    """Manifest = sorted JSON-able dict with symbol, file name, sha256, rows,
    first date, last date, source, auto_adjust flag, yfinance version, created_utc."""
    required = {
        "symbol",
        "file_name",
        "sha256",
        "rows",
        "first_date",
        "last_date",
        "source",
        "auto_adjust",
        "yfinance_version",
        "created_utc",
    }
    normalized = []
    for e in entries:
        missing = required - set(e.keys())
        if missing:
            raise ValueError(f"manifest entry missing keys: {sorted(missing)}")
        normalized.append({k: e[k] for k in sorted(e.keys())})
    normalized.sort(
        key=lambda x: (str(x.get("symbol", "")), str(x.get("file_name", "")))
    )
    return {"entries": normalized}


def run_all(
    symbol: str,
    df: pd.DataFrame,
    calendar: pd.DatetimeIndex | None = None,
    as_of: pd.Timestamp | str | None = None,
) -> list[Finding]:
    """Run all per-symbol checks and return all findings."""
    findings: list[Finding] = []
    findings.extend(check_index(symbol, df))
    findings.extend(check_ohlc_adjclose(symbol, df))
    findings.extend(check_ohlc_ordering(symbol, df))
    findings.extend(check_volume(symbol, df))
    if calendar is not None:
        findings.extend(check_missing_dates(symbol, df, calendar))
    findings.extend(check_close_moves(symbol, df))
    findings.extend(check_adj_ratio(symbol, df))
    findings.extend(check_dividend_yield(symbol, df))
    findings.extend(check_staleness(symbol, df, as_of))
    return findings
