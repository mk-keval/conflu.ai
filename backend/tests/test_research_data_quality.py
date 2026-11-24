"""Tests for pure data-quality checks (F1)."""

from __future__ import annotations

import hashlib

import pandas as pd

from backend.app.research.data_quality import (
    build_manifest,
    check_adj_ratio,
    check_close_moves,
    check_dividend_yield,
    check_index,
    check_missing_dates,
    check_ohlc_adjclose,
    check_ohlc_ordering,
    check_staleness,
    check_volume,
    compare_returns,
    run_all,
    sha256_of_file,
)


def _clean_frame(n: int = 30, start: str = "2024-01-02") -> pd.DataFrame:
    idx = pd.bdate_range(start, periods=n)
    base = 100.0 + pd.Series(range(n), dtype=float).values * 0.1
    return pd.DataFrame(
        {
            "Open": base,
            "High": base + 1.0,
            "Low": base - 1.0,
            "Close": base + 0.2,
            "Adj Close": base + 0.2,
            "Volume": [1_000_000.0] * n,
            "Dividends": [0.0] * n,
            "Stock Splits": [0.0] * n,
        },
        index=idx,
    )


def _findings(checks, name, severity=None):
    out = [f for f in checks if f.check == name]
    if severity is not None:
        out = [f for f in out if f.severity == severity]
    return out


def test_clean_frame_passes_all_checks():
    df = _clean_frame()
    cal = pd.DatetimeIndex(df.index)
    findings = run_all("SPY", df, calendar=cal, as_of=df.index.max())
    assert findings == []


def test_check_index_duplicate_hard():
    df = _clean_frame(5)
    df = pd.concat([df, df.iloc[[-1]]])
    findings = check_index("AAA", df)
    hard = _findings(findings, "index", "HARD")
    assert hard
    assert hard[0].severity == "HARD"
    assert hard[0].count >= 1


def test_check_index_non_monotonic_hard():
    df = _clean_frame(5)
    df = df.iloc[[0, 2, 1, 3, 4]]
    findings = check_index("AAA", df)
    hard = _findings(findings, "index", "HARD")
    assert any(f.detail == "non-monotonic index" for f in hard)
    assert any(f.count == 1 for f in hard if f.detail == "non-monotonic index")


def test_check_ohlc_adjclose_nan_hard_and_trailing_close_warn():
    df = _clean_frame(5)
    df.loc[df.index[1], "High"] = float("nan")
    df.loc[df.index[-1], "Close"] = float("nan")
    findings = check_ohlc_adjclose("AAA", df)
    hard = _findings(findings, "ohlc_adjclose", "HARD")
    warn = _findings(findings, "ohlc_adjclose", "WARN")
    assert len(hard) == 1
    assert hard[0].count == 1  # only the High NaN row; trailing Close NaN excluded
    assert len(warn) == 1
    assert warn[0].count == 1


def test_check_ohlc_adjclose_nonpositive_hard():
    df = _clean_frame(5)
    df.loc[df.index[2], "Adj Close"] = 0.0
    findings = check_ohlc_adjclose("AAA", df)
    hard = _findings(findings, "ohlc_adjclose", "HARD")
    assert hard and hard[0].severity == "HARD"
    assert hard[0].count == 1


def test_check_ohlc_ordering_warn_and_hard_boundary():
    # 0.5% boundary: 1 bad row in 200 rows = 0.5% -> WARN (not > 0.5%)
    df = _clean_frame(200)
    df.loc[df.index[10], "Low"] = df.loc[df.index[10], "High"] + 1.0
    findings = check_ohlc_ordering("AAA", df)
    warn = _findings(findings, "ohlc_ordering", "WARN")
    assert warn and warn[0].count == 1

    # 2 bad rows in 200 = 1.0% -> HARD
    df2 = _clean_frame(200)
    df2.loc[df2.index[10], "Low"] = df2.loc[df2.index[10], "High"] + 1.0
    df2.loc[df2.index[20], "Low"] = df2.loc[df2.index[20], "High"] + 1.0
    findings2 = check_ohlc_ordering("AAA", df2)
    hard = _findings(findings2, "ohlc_ordering", "HARD")
    assert hard and hard[0].count == 2


def test_check_volume_negative_hard_zero_warn():
    df = _clean_frame(5)
    df.loc[df.index[1], "Volume"] = -1.0
    df.loc[df.index[3], "Volume"] = 0.0
    findings = check_volume("AAA", df)
    hard = _findings(findings, "volume", "HARD")
    warn = _findings(findings, "volume", "WARN")
    assert hard and hard[0].count == 1
    assert warn and warn[0].count == 1


def test_check_missing_dates_warn_and_hard_boundary():
    cal = pd.bdate_range("2024-01-02", periods=200)
    df = _clean_frame(200, start="2024-01-02")
    # drop 2 dates out of 200 = 1.0% -> WARN (not > 1%)
    df_warn = df.drop(index=[cal[10], cal[20]])
    findings_warn = check_missing_dates("AAA", df_warn, cal)
    warn = _findings(findings_warn, "missing_dates", "WARN")
    assert warn and warn[0].count == 2

    # drop 3 dates out of 200 = 1.5% -> HARD
    df_hard = df.drop(index=[cal[10], cal[20], cal[30]])
    findings_hard = check_missing_dates("AAA", df_hard, cal)
    hard = _findings(findings_hard, "missing_dates", "HARD")
    assert hard and hard[0].count == 3


def test_check_close_moves_warn_and_hard_boundary():
    df = _clean_frame(5)
    # 30% move, no split -> WARN
    df.loc[df.index[1], "Close"] = df.loc[df.index[0], "Close"] * 1.30
    df.loc[df.index[1], "Adj Close"] = df.loc[df.index[1], "Close"]
    # 41% move -> HARD; normalize next row to avoid an extra move
    df.loc[df.index[3], "Close"] = df.loc[df.index[2], "Close"] * 1.41
    df.loc[df.index[3], "Adj Close"] = df.loc[df.index[3], "Close"]
    df.loc[df.index[4], "Close"] = df.loc[df.index[3], "Close"] * 1.001
    df.loc[df.index[4], "Adj Close"] = df.loc[df.index[4], "Close"]
    findings = check_close_moves("AAA", df)
    warn = _findings(findings, "close_moves", "WARN")
    hard = _findings(findings, "close_moves", "HARD")
    assert warn and warn[0].count >= 1
    assert hard and hard[0].count >= 1


def test_check_close_moves_40pct_boundary_not_hard():
    df = _clean_frame(4)
    # exactly 40% move - should be WARN (>20% and <=40%), not HARD
    df.loc[df.index[1], "Close"] = df.loc[df.index[0], "Close"] * 1.40
    df.loc[df.index[1], "Adj Close"] = df.loc[df.index[1], "Close"]
    # Keep next row's move normal so only row 1 is flagged.
    df.loc[df.index[2], "Close"] = df.loc[df.index[1], "Close"] * 1.001
    df.loc[df.index[2], "Adj Close"] = df.loc[df.index[2], "Close"]
    df.loc[df.index[3], "Close"] = df.loc[df.index[2], "Close"] * 1.001
    df.loc[df.index[3], "Adj Close"] = df.loc[df.index[3], "Close"]
    findings = check_close_moves("AAA", df)
    hard = _findings(findings, "close_moves", "HARD")
    warn = _findings(findings, "close_moves", "WARN")
    assert not hard
    assert warn and warn[0].count == 1


def test_check_adj_ratio_warn_per_date_hard_over_5():
    df = _clean_frame(10)
    # 1 unexplained ratio change at row 2; keep later rows at same ratio.
    ratio_1 = 1.01
    df.loc[df.index[2], "Adj Close"] = df.loc[df.index[2], "Close"] * ratio_1
    for i in range(3, len(df)):
        df.loc[df.index[i], "Adj Close"] = df.loc[df.index[i], "Close"] * ratio_1
    findings = check_adj_ratio("AAA", df)
    warn = _findings(findings, "adj_ratio", "WARN")
    assert warn and warn[0].count == 1

    df2 = _clean_frame(10)
    # 7 unexplained ratio changes (rows 1..7), then hold ratio steady.
    for i in range(1, 8):
        ratio = 1.0 + 0.001 * i
        df2.loc[df2.index[i], "Adj Close"] = df2.loc[df2.index[i], "Close"] * ratio
    last_ratio = 1.0 + 0.001 * 7
    for i in range(8, len(df2)):
        df2.loc[df2.index[i], "Adj Close"] = df2.loc[df2.index[i], "Close"] * last_ratio
    findings2 = check_adj_ratio("AAA", df2)
    hard = _findings(findings2, "adj_ratio", "HARD")
    assert hard and hard[0].count > 5


def test_check_dividend_yield_warn():
    df = _clean_frame(5)
    df.loc[df.index[2], "Dividends"] = 6.0  # 6/close > 5%
    findings = check_dividend_yield("AAA", df)
    warn = _findings(findings, "dividend_yield", "WARN")
    assert warn and warn[0].count == 1


def test_check_staleness_warn():
    df = _clean_frame(5, start="2024-01-02")
    findings = check_staleness("AAA", df, as_of="2024-01-20")
    warn = _findings(findings, "staleness", "WARN")
    assert warn and warn[0].count == 1


def test_compare_returns_warn_above_2pct():
    a = _clean_frame(100)
    b = _clean_frame(100)
    # Make 5% of common return dates differ by > tol
    for i in range(2, 7):
        b.loc[b.index[i], "Adj Close"] = b.loc[b.index[i], "Adj Close"] * 1.01
    findings = compare_returns(a, b, tol=0.0005)
    warn = _findings(findings, "compare_returns", "WARN")
    assert warn
    assert warn[0].severity == "WARN"
    assert warn[0].count > 0


def test_compare_returns_no_finding_when_close():
    a = _clean_frame(100)
    b = a.copy()
    assert compare_returns(a, b, tol=0.0005) == []


def test_manifest_hash_changes_when_byte_changes(tmp_path):
    p = tmp_path / "x.csv.gz"
    p.write_bytes(b"hello")
    h1 = sha256_of_file(p)
    p.write_bytes(b"hellp")
    h2 = sha256_of_file(p)
    assert h1 != h2
    assert h1 == hashlib.sha256(b"hello").hexdigest()

    entries = [
        {
            "symbol": "SPY",
            "file_name": "SPY.csv.gz",
            "sha256": h1,
            "rows": 10,
            "first_date": "2020-01-01",
            "last_date": "2020-01-10",
            "source": "yfinance",
            "auto_adjust": False,
            "yfinance_version": "1.0",
            "created_utc": "2026-01-01T00:00:00Z",
        }
    ]
    m1 = build_manifest(entries)
    entries2 = [dict(entries[0], sha256=h2)]
    m2 = build_manifest(entries2)
    assert m1 != m2
    assert m1["entries"][0]["symbol"] == "SPY"


def test_build_manifest_sorted_and_validates():
    e = {
        "symbol": "SPY",
        "file_name": "SPY.csv.gz",
        "sha256": "abc",
        "rows": 1,
        "first_date": "2020-01-01",
        "last_date": "2020-01-01",
        "source": "yfinance",
        "auto_adjust": False,
        "yfinance_version": "1.0",
        "created_utc": "2026-01-01T00:00:00Z",
    }
    m = build_manifest([e])
    assert list(m.keys()) == ["entries"]
    assert m["entries"][0]["symbol"] == "SPY"
    try:
        build_manifest([{"symbol": "SPY"}])
    except ValueError as exc:
        assert "missing keys" in str(exc)
    else:
        raise AssertionError("expected ValueError")
