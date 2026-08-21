"""Tests for local pandas filter evaluation (P1.2 One-Snapshot-Multi-Screen).

Covers the LocalColumn/LocalCond shims, FILTER_MAP local-vs-expected mask
semantics on synthetic frames, and the specialist's fail-closed evaluator.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backend.app.infrastructure.screener.configs import FilterRule
from backend.app.infrastructure.screener.tv_local_eval import (
    FilterEvaluationError,
    LocalColumn,
    LocalCond,
)
from backend.app.infrastructure.screener.tv_specialist import TVScreenerSpecialist


@pytest.fixture
def frame() -> pd.DataFrame:
    """Synthetic snapshot: 4 symbols with known indicator states.

    AAPL — fresh MACD cross above signal (was below yesterday), RSI 55
    MSFT — MACD above signal both days, RSI 75 (overbought)
    GOOG — MACD below signal both days, RSI 25 (oversold), tiny volume
    AMZN — NaN RSI, MACD above signal today only
    """
    return pd.DataFrame({
        "ticker": ["NASDAQ:AAPL", "NASDAQ:MSFT", "NASDAQ:GOOG", "NASDAQ:AMZN"],
        "close": [180.0, 420.0, 150.0, 180.0],
        "RSI": [55.0, 75.0, 25.0, np.nan],
        "MACD.macd": [2.0, 3.0, -1.0, 1.5],
        "MACD.signal": [1.5, 2.5, -0.5, 2.0],
        "relative_volume_10d_calc": [1.8, 1.1, 0.6, 1.3],
        "exchange": ["NASDAQ"] * 4,
        "market_cap_basic": [3e12, 3.1e12, 1.9e12, 1.8e12],
    })


class TestLocalColumnSemantics:
    """Shim operators mirror TV-side expression semantics."""

    def test_numeric_comparison_nan_is_false(self, frame: pd.DataFrame) -> None:
        cond = LocalColumn(frame, "RSI") > 30
        assert list(cond.mask) == [True, True, False, False]  # AMZN NaN → False

    def test_eq_on_raw_strings(self, frame: pd.DataFrame) -> None:
        cond = LocalColumn(frame, "exchange") == "NASDAQ"
        assert cond.mask.all()

    def test_isin(self, frame: pd.DataFrame) -> None:
        frame["rating"] = ["Buy", "Sell", "StrongBuy", "Hold"]
        cond = LocalColumn(frame, "rating").isin(["StrongBuy", "Buy"])
        assert list(cond.mask) == [True, False, True, False]

    def test_crosses_above_requires_fresh_cross(self, frame: pd.DataFrame) -> None:
        # Two-day history columns: yesterday vs today encoded in separate rows
        hist = pd.DataFrame({
            "MACD.macd": [1.0, 2.0],
            "MACD.signal": [1.5, 1.5],  # was below, now above → cross
        })
        cond = LocalColumn(hist, "MACD.macd").crosses_above(LocalColumn(hist, "MACD.signal"))
        assert list(cond.mask) == [False, True]

    def test_crosses_above_false_when_already_above(self) -> None:
        hist = pd.DataFrame({"a": [2.0, 3.0], "b": [1.0, 2.0]})
        cond = LocalColumn(hist, "a").crosses_above(LocalColumn(hist, "b"))
        assert not cond.mask.any()  # above both days — no FRESH cross

    def test_below_pct_multiplier(self, frame: pd.DataFrame) -> None:
        # RSI < close * 1.0 → true for the three numeric RSIs (AMZN is NaN → False)
        cond_true = LocalColumn(frame, "RSI").below_pct(LocalColumn(frame, "close"), 1.0)
        assert list(cond_true.mask) == [True, True, True, False]
        # close < mcap * 1e-12 → false for these large caps
        cond_false = LocalColumn(frame, "close").below_pct(
            LocalColumn(frame, "market_cap_basic"), 1e-12
        )
        assert not cond_false.mask.any()

    def test_missing_column_raises(self, frame: pd.DataFrame) -> None:
        with pytest.raises(FilterEvaluationError, match="missing from base snapshot"):
            LocalColumn(frame, "EMA100")

    def test_cond_composition_and_or(self, frame: pd.DataFrame) -> None:
        rsi_ok = LocalColumn(frame, "RSI") > 50
        rvol_ok = LocalColumn(frame, "relative_volume_10d_calc") > 1.2
        both = rsi_ok & rvol_ok
        assert list(both.mask) == [True, False, False, False]
        either = rsi_ok | rvol_ok
        assert list(either.mask) == [True, True, False, True]


def _specialist_with_frame(frame: pd.DataFrame) -> TVScreenerSpecialist:
    spec = TVScreenerSpecialist()
    return spec


class TestEvaluateFiltersLocal:
    """Fail-closed evaluation of full rule lists against a snapshot."""

    @pytest.mark.asyncio
    async def test_rsi_oversold_mask(self, frame: pd.DataFrame) -> None:
        spec = _specialist_with_frame(frame)
        rules = [
            FilterRule(category="momentum", indicator="rsi_oversold", params={"threshold": 30})
        ]
        mask = spec.evaluate_filters_local(frame, rules)
        assert mask is not None
        assert list(mask) == [False, False, True, False]

    @pytest.mark.asyncio
    async def test_conjunction_of_rules(self, frame: pd.DataFrame) -> None:
        spec = _specialist_with_frame(frame)
        rules = [
            FilterRule(category="momentum", indicator="rsi_gt", params={"threshold": 50}),
            FilterRule(category="volume", indicator="rvol_high", params={"threshold": 1.5}),
            FilterRule(
                category="fundamental",
                indicator="exchange_in",
                params={"exchanges": ["NYSE", "NASDAQ"]},
            ),
        ]
        mask = spec.evaluate_filters_local(frame, rules)
        assert mask is not None
        assert list(mask) == [True, False, False, False]

    @pytest.mark.asyncio
    async def test_unknown_indicator_fails_closed(self, frame: pd.DataFrame) -> None:
        spec = _specialist_with_frame(frame)
        rules = [FilterRule(category="x", indicator="no_such_indicator")]
        assert spec.evaluate_filters_local(frame, rules) is None

    @pytest.mark.asyncio
    async def test_missing_column_fails_closed(self, frame: pd.DataFrame) -> None:
        spec = _specialist_with_frame(frame)
        rules = [
            FilterRule(
                category="trend",
                indicator="price_above_ema",
                params={"period": 100},  # EMA100 absent from the fixture frame
            )
        ]
        assert spec.evaluate_filters_local(frame, rules) is None

    @pytest.mark.asyncio
    async def test_empty_rules_return_none(self, frame: pd.DataFrame) -> None:
        spec = _specialist_with_frame(frame)
        assert spec.evaluate_filters_local(frame, []) is None

    @pytest.mark.asyncio
    async def test_macd_cross_bullish_semantics(self, frame: pd.DataFrame) -> None:
        """Single-row frames have no prior bar → crosses yield all-False."""
        spec = _specialist_with_frame(frame)
        rules = [FilterRule(category="momentum", indicator="macd_cross_above")]
        mask = spec.evaluate_filters_local(frame, rules)
        assert mask is not None
        assert not mask.any()
