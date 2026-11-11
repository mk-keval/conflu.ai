"""Tests for research data loading and cache integrity (D-79 remediation)."""

import json
import os

import pandas as pd
import pytest

import backend.app.research.data as data_mod
from backend.app.research.data import download_daily, load_universe, panel_span


def _frame(start, end_exclusive, symbol="AAA"):
    """Plain OHLCV frame shaped like a cleaned yfinance download."""
    idx = pd.bdate_range(start, end_exclusive, inclusive="left")
    return pd.DataFrame(
        {
            "Open": 100.0,
            "High": 101.0,
            "Low": 99.0,
            "Close": 100.0,
            "Volume": 1_000_000,
        },
        index=idx,
    )


class FakeYF:
    """Records download calls and returns spans derived from the request."""

    def __init__(self):
        self.calls = []

    def download(self, symbol, start=None, end=None, **kwargs):
        self.calls.append((symbol, start, end))
        return _frame(start, end)


@pytest.fixture
def fake_yf(monkeypatch):
    fake = FakeYF()
    monkeypatch.setattr(data_mod.yf, "download", fake.download)
    return fake


def _aaa_calls(fake):
    return [c for c in fake.calls if c[0] == "AAA"]


def test_cache_is_keyed_by_requested_span(tmp_path, fake_yf):
    """A 2020-only cache entry must not satisfy a 2020-2023 request."""
    cache = str(tmp_path)

    data_2020, _, stats_2020 = download_daily(["AAA"], "2020-01-01", "2020-12-31", cache)
    assert len(_aaa_calls(fake_yf)) == 1
    assert data_2020["AAA"].index.max().year == 2020

    data_long, _, stats_long = download_daily(["AAA"], "2020-01-01", "2023-12-31", cache)

    # Second call must download again rather than reuse the 2020 file.
    assert len(_aaa_calls(fake_yf)) == 2
    assert data_long["AAA"].index.max().year == 2023
    # AAA, SPY and VIX are all re-downloaded for the wider span.
    assert stats_long["downloaded"] == 3
    # The short span is still a separate, valid entry.
    assert stats_2020["downloaded"] == 3


def test_same_span_reuses_cache(tmp_path, fake_yf):
    cache = str(tmp_path)

    download_daily(["AAA"], "2020-01-01", "2023-12-31", cache)
    _, _, stats = download_daily(["AAA"], "2020-01-01", "2023-12-31", cache)

    assert len(_aaa_calls(fake_yf)) == 1
    assert stats["downloaded"] == 0


def test_force_download_bypasses_cache(tmp_path, fake_yf):
    cache = str(tmp_path)

    download_daily(["AAA"], "2020-01-01", "2023-12-31", cache)
    _, _, stats = download_daily(
        ["AAA"], "2020-01-01", "2023-12-31", cache, force_download=True
    )

    assert len(_aaa_calls(fake_yf)) == 2
    # AAA, SPY and VIX are all re-downloaded.
    assert stats["downloaded"] == 3


def test_cache_expiry_forces_download(tmp_path, fake_yf):
    cache = str(tmp_path)

    download_daily(["AAA"], "2020-01-01", "2023-12-31", cache)
    cached = next(tmp_path.glob("AAA__*.csv.gz"))
    old = cached.stat().st_mtime - 48 * 3600
    os.utime(cached, (old, old))

    _, _, stats = download_daily(["AAA"], "2020-01-01", "2023-12-31", cache)
    assert len(_aaa_calls(fake_yf)) == 2
    assert stats["downloaded"] == 1


def test_end_is_inclusive(tmp_path, fake_yf):
    """The runner's --end is inclusive; yfinance receives end + 1 day."""
    download_daily(["AAA"], "2020-01-01", "2020-12-31", str(tmp_path))

    _, start, end = _aaa_calls(fake_yf)[0]
    assert start == "2020-01-01"
    assert end == "2021-01-01"


def test_manifest_records_the_request(tmp_path, fake_yf):
    cache = str(tmp_path)
    download_daily(["AAA"], "2020-01-01", "2023-12-31", cache)

    manifest = json.loads((tmp_path / "_manifest.json").read_text(encoding="utf-8"))
    entry = manifest["AAA__2020-01-01__2023-12-31"]
    assert entry["requested_start"] == "2020-01-01"
    assert entry["requested_end"] == "2023-12-31"
    assert entry["actual_start"] == "2020-01-01"
    assert entry["actual_end"] == "2023-12-29"
    assert entry["rows"] > 100


def test_panel_span_excludes_benchmarks():
    idx_a = pd.bdate_range("2020-01-01", periods=10)
    idx_b = pd.bdate_range("2020-01-01", periods=20)
    data = {
        "AAA": pd.DataFrame({"close": 1.0}, index=idx_a),
        "BBB": pd.DataFrame({"close": 1.0}, index=idx_b),
        "SPY": pd.DataFrame({"close": 1.0}, index=pd.bdate_range("2015-01-01", periods=50)),
    }

    start, end = panel_span(data)
    assert start == idx_a[0]
    assert end == idx_b[-1]


def test_load_universe_normalises_symbols(tmp_path):
    path = tmp_path / "universe.txt"
    path.write_text("# comment\nbrk.b\nAAPL\n\n", encoding="utf-8")

    assert load_universe(str(path)) == ["BRK-B", "AAPL"]
