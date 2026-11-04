"""Regression tests for OHLCVFetcher window handling (2026-10-19 validation reset).

The reset found that a cold-cache fetch ignored the requested ``start``/``end``
(the default ``period="max"`` won) and returned full history, while cache reads
returned only the requested window. The same backtest could therefore silently
use different spans depending on cache state.
"""

from __future__ import annotations

import pandas as pd

from backend.app.infrastructure.data import fetcher as fetcher_module
from backend.app.infrastructure.data.fetcher import OHLCVFetcher


def _full_history() -> pd.DataFrame:
    idx = pd.bdate_range("2020-01-01", "2020-12-31")
    base = pd.Series(range(len(idx)), index=idx, dtype=float) + 100.0
    return pd.DataFrame(
        {
            "Open": base,
            "High": base + 1.0,
            "Low": base - 1.0,
            "Close": base + 0.5,
            "Volume": 1_000_000,
        }
    )


class _FakeTicker:
    """Mimics yfinance: ignores start/end only when called with period."""

    calls: list[dict] = []

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol

    def history(self, **kwargs):
        type(self).calls.append(kwargs)
        df = _full_history()
        start = kwargs.get("start")
        end = kwargs.get("end")
        if start:
            df = df[df.index >= pd.Timestamp(start)]
        if end:  # yfinance treats `end` as exclusive
            df = df[df.index < pd.Timestamp(end)]
        return df.copy()


def _make_fetcher(tmp_path) -> OHLCVFetcher:
    return OHLCVFetcher(cache_dir=tmp_path, request_delay=0.0)


async def test_fresh_fetch_honours_window(tmp_path, monkeypatch):
    _FakeTicker.calls = []
    monkeypatch.setattr(fetcher_module.yf, "Ticker", _FakeTicker)

    fetcher = _make_fetcher(tmp_path)
    df = await fetcher.fetch_yahoo("TEST", "1D", "2020-03-01", "2020-06-01")

    assert df is not None
    assert df.index.min() >= pd.Timestamp("2020-03-01")
    assert df.index.max() == pd.Timestamp("2020-06-01")
    assert 40 < len(df) < 100  # window slice, not the 262-bar full history

    # The cache must contain only the windowed frame as well.
    cached = pd.read_parquet(tmp_path / "TEST_1D_2020-03-01_2020-06-01.parquet")
    assert cached.index.min() >= pd.Timestamp("2020-03-01")
    assert cached.index.max() == pd.Timestamp("2020-06-01")


async def test_cache_read_matches_fresh_fetch(tmp_path, monkeypatch):
    _FakeTicker.calls = []
    monkeypatch.setattr(fetcher_module.yf, "Ticker", _FakeTicker)

    fetcher = _make_fetcher(tmp_path)
    fresh = await fetcher.fetch_yahoo("TEST", "1D", "2020-03-01", "2020-06-01")
    cached = await fetcher.fetch_yahoo("TEST", "1D", "2020-03-01", "2020-06-01")

    assert fresh is not None and cached is not None
    # parquet round-trips drop DatetimeIndex.freq; values/columns must match.
    pd.testing.assert_frame_equal(fresh, cached, check_freq=False)
    # Second call must be served from cache, not the network.
    assert len(_FakeTicker.calls) == 1


async def test_no_start_keeps_period_semantics(tmp_path, monkeypatch):
    _FakeTicker.calls = []
    monkeypatch.setattr(fetcher_module.yf, "Ticker", _FakeTicker)

    fetcher = _make_fetcher(tmp_path)
    df = await fetcher.fetch_yahoo("TEST", "1D")

    assert df is not None
    assert len(df) == len(_full_history())
    assert _FakeTicker.calls[0].get("period") == "max"
