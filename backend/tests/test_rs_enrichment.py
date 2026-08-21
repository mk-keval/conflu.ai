"""Tests for RS-vs-index percentile enrichment (P1.3).

Zero-extra-upstream-call enrichment computed from the SAME base snapshot:
SPY-row anchoring with market-median fallback, 1M+3M horizons.
"""

from __future__ import annotations

import pandas as pd
import pytest

from backend.app.infrastructure.screener.rs_enrichment import compute_rs_percentiles


def _frame(with_spy: bool = True) -> pd.DataFrame:
    """5 symbols + optional SPY row; perf spread is deterministic."""
    tickers = ["NASDAQ:AA", "NASDAQ:BB", "NASDAQ:CC", "NASDAQ:DD", "NASDAQ:EE"]
    p1m = [10.0, 5.0, 0.0, -5.0, -10.0]
    p3m = [30.0, -20.0, 0.0, 15.0, -40.0]
    if with_spy:
        tickers.append("AMEX:SPY")
        p1m.append(2.0)
        p3m.append(5.0)
    return pd.DataFrame({
        "ticker": tickers,
        "Perf.1M": p1m,
        "Perf.3M": p3m,
    })


def _num(value: float | None) -> float:
    assert isinstance(value, float)
    return value


class TestComputeRsPercentiles:
    def test_spy_anchored_excess(self) -> None:
        rs = compute_rs_percentiles(_frame(with_spy=True))
        # SPY present → excess_1m for AA = 10 - 2 = 8
        assert _num(rs["AA"]["excess_1m"]) == pytest.approx(8.0)
        assert _num(rs["EE"]["excess_1m"]) == pytest.approx(-12.0)

    def test_percentiles_monotonic_with_perf(self) -> None:
        rs = compute_rs_percentiles(_frame(with_spy=True))
        assert _num(rs["AA"]["pct_1m"]) > _num(rs["BB"]["pct_1m"]) > _num(rs["CC"]["pct_1m"])
        assert _num(rs["CC"]["pct_1m"]) > _num(rs["DD"]["pct_1m"]) > _num(rs["EE"]["pct_1m"])
        # Top performer sits at/above 90th percentile of 6 rows
        assert _num(rs["AA"]["pct_1m"]) >= 90.0
        assert _num(rs["EE"]["pct_1m"]) <= 20.0

    def test_median_fallback_without_spy(self) -> None:
        rs = compute_rs_percentiles(_frame(with_spy=False))
        # Median of [10,5,0,-5,-10] = 0 → CC (perf 0) has zero excess at 1M.
        # Average-rank percentiles: middle element of 5 sits at 60%.
        assert _num(rs["CC"]["excess_1m"]) == pytest.approx(0.0)
        assert _num(rs["CC"]["pct_1m"]) == pytest.approx(60.0)

    def test_composite_is_mean_of_horizons(self) -> None:
        rs = compute_rs_percentiles(_frame())
        for sym in ("AA", "CC", "EE"):
            expected = round((_num(rs[sym]["pct_1m"]) + _num(rs[sym]["pct_3m"])) / 2.0, 1)
            assert _num(rs[sym]["composite"]) == pytest.approx(expected)

    def test_missing_perf_columns_returns_empty(self) -> None:
        df = pd.DataFrame({"ticker": ["NASDAQ:AAPL"], "close": [180.0]})
        assert compute_rs_percentiles(df) == {}

    def test_empty_frame_returns_empty(self) -> None:
        assert compute_rs_percentiles(pd.DataFrame({"ticker": [], "Perf.1M": []})) == {}

    def test_nan_rows_get_neutral_percentile(self) -> None:
        df = _frame()
        df.loc[len(df)] = ["NASDAQ:FF", float("nan"), 0.0]
        rs = compute_rs_percentiles(df)
        ff = rs["FF"]
        assert ff["perf_1m"] is None
        assert _num(ff["pct_1m"]) == pytest.approx(50.0)

    def test_symbol_extraction_from_prefixed_tickers(self) -> None:
        rs = compute_rs_percentiles(_frame())
        assert "SPY" in rs
        assert set(rs) == {"AA", "BB", "CC", "DD", "EE", "SPY"}
