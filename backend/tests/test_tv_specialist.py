"""Tests for TV Screener specialist — filter compilation + query building.

All tests are unit-level; no live TradingView API calls.
"""

from __future__ import annotations

import pytest

from backend.app.infrastructure.screener.configs import FilterRule, ScreenConfig, UniverseConfig
from backend.app.infrastructure.screener.tv_specialist import (
    FILTER_MAP,
    TVScreenerSpecialist,
)


class TestFILTER_MAP:
    """Test that all 16 registered filter builders return valid Column expressions."""

    @pytest.mark.parametrize(
        "indicator,params",
        [
            ("price_above_ema", {"period": 20}),
            ("price_below_ema", {"period": 50}),
            ("rsi_oversold", {"threshold": 30}),
            ("rsi_overbought", {"threshold": 70}),
            ("rsi_gt", {"threshold": 50}),
            ("rsi_lt", {"threshold": 50}),
            ("macd_bullish", {}),
            ("macd_bearish", {}),
            ("macd_hist_rising", {}),
            ("rvol_high", {"threshold": 1.5}),
            ("adx_trending", {"threshold": 25}),
            ("ema_cross", {"fast": 20, "slow": 50}),
            ("bb_squeeze", {"threshold": 1.10}),
            ("price_above_vwap", {}),
            ("sector_is", {"sectors": ["Technology"]}),
            ("market_cap_gt", {"value": 1_000_000_000}),
            ("analyst_strongbuy", {}),
            ("dividend_yield_gt", {"threshold": 0.03}),
        ],
    )
    def test_builder_returns_callable(self, indicator: str, params: dict) -> None:
        """Every builder in FILTER_MAP returns a callable Column expression."""
        builder = FILTER_MAP[indicator]
        from tradingview_screener.column import Column
        result = builder(params, Column)
        assert result is not None


class TestCompileFilters:
    """Test compile_filters produces correct conditions."""

    def setup_method(self) -> None:
        self.specialist = TVScreenerSpecialist()

    def test_empty_filters_returns_none(self) -> None:
        result = self.specialist.compile_filters([])
        assert result is None

    def test_single_filter_returns_condition(self) -> None:
        filters = [
            FilterRule(category="momentum", indicator="rsi_oversold", params={"threshold": 30}),
        ]
        result = self.specialist.compile_filters(filters)
        assert result is not None

    def test_multiple_filters_wrapped_in_and(self) -> None:
        filters = [
            FilterRule(category="momentum", indicator="rsi_oversold", params={"threshold": 30}),
            FilterRule(category="trend", indicator="adx_trending", params={"threshold": 25}),
        ]
        result = self.specialist.compile_filters(filters)
        assert result is not None

    def test_unknown_filter_skipped(self) -> None:
        filters = [
            FilterRule(category="momentum", indicator="rsi_oversold", params={"threshold": 30}),
            FilterRule(category="unknown", indicator="nonexistent", params={}),
        ]
        result = self.specialist.compile_filters(filters)
        # Unknown filter should be skipped; valid filter still produces a condition
        assert result is not None


class TestBuildQuery:
    """Test query building from ScreenConfig."""

    def setup_method(self) -> None:
        self.specialist = TVScreenerSpecialist()

    def test_build_query_with_filters(self) -> None:
        config = ScreenConfig(
            name="Test",
            filters=[FilterRule(category="momentum", indicator="rsi_oversold")],
        )
        q = self.specialist.build_query(config)
        assert q is not None

    def test_build_query_with_index(self) -> None:
        config = ScreenConfig(
            name="Test Index",
            universe=UniverseConfig(markets=[], index="SPX"),
        )
        q = self.specialist.build_query(config)
        assert q is not None

    def test_build_query_with_markets(self) -> None:
        config = ScreenConfig(
            name="Test Markets",
            universe=UniverseConfig(markets=["america", "crypto"]),
        )
        q = self.specialist.build_query(config)
        assert q is not None


class TestDiscover:
    """Test discover() error paths (no live API calls)."""

    def setup_method(self) -> None:
        self.specialist = TVScreenerSpecialist()

    def test_discover_empty_filters_returns_no_matches(self) -> None:
        """Empty config returns a result with 0 matches when build_query returns None."""
        import asyncio
        from unittest.mock import patch

        with patch.object(self.specialist, "build_query", return_value=None):
            config = ScreenConfig(name="Empty")
            result = asyncio.run(self.specialist.discover(config))
            assert result.total_matches == 0
            assert result.tickers == []
            assert result.raw_data is None


class TestLiveColumnNames:
    """Dead TV field casing replaced with live-verified names (2026-10-19)."""

    def test_snapshot_columns_use_live_names(self) -> None:
        from backend.app.infrastructure.screener.tv_specialist import SNAPSHOT_COLUMNS

        assert "Stoch.K" in SNAPSHOT_COLUMNS
        assert "Stoch.D" in SNAPSHOT_COLUMNS
        assert "BB.basis" in SNAPSHOT_COLUMNS
        assert "STOCH.K" not in SNAPSHOT_COLUMNS
        assert "STOCH.D" not in SNAPSHOT_COLUMNS
        assert "BB.middle" not in SNAPSHOT_COLUMNS

    def test_stoch_filters_use_live_names(self) -> None:
        from tradingview_screener.column import Column

        assert FILTER_MAP["stoch_oversold"]({}, Column)["left"] == "Stoch.K"
        assert FILTER_MAP["stoch_overbought"]({}, Column)["left"] == "Stoch.K"
        assert FILTER_MAP["stoch_bullish_cross"]({}, Column)["left"] == "Stoch.K"
        assert FILTER_MAP["stoch_bearish_cross"]({}, Column)["left"] == "Stoch.K"


def _filter_lefts(q) -> list:
    """Extract comparison left-hand columns from a built query's filter2 tree."""
    f2 = q.query["filter2"]
    if "operands" in f2:
        return [op["expression"]["left"] for op in f2["operands"] if "expression" in op]
    return []


class TestTimeframeSuffixes:
    """Pipe-suffix timeframes: the TV server ignores a top-level `interval`."""

    def setup_method(self) -> None:
        self.specialist = TVScreenerSpecialist()

    def test_build_query_4h_suffixes_select_and_filters(self) -> None:
        config = ScreenConfig(
            name="TF 4h",
            timeframes=["4h"],
            filters=[
                FilterRule(
                    category="momentum",
                    indicator="rsi_gt",
                    params={"threshold": 60},
                    timeframe="4h",
                )
            ],
        )
        q = self.specialist.build_query(config)
        assert q is not None

        columns = q.query["columns"]
        assert "RSI|240" in columns
        assert "EMA20|240" in columns
        assert "MACD.macd|240" in columns
        assert "Stoch.K|240" in columns
        assert "relative_volume_10d_calc|240" in columns
        # Fundamentals / non-TF fields stay on the daily default
        assert "market_cap_basic" in columns
        assert "market_cap_basic|240" not in columns

        assert _filter_lefts(q) == ["RSI|240"]

    def test_build_query_1d_has_no_suffixes(self) -> None:
        config = ScreenConfig(
            name="TF 1D",
            timeframes=["1D"],
            filters=[
                FilterRule(
                    category="momentum",
                    indicator="rsi_gt",
                    params={"threshold": 60},
                    timeframe="1D",
                )
            ],
        )
        q = self.specialist.build_query(config)
        assert q is not None
        assert "RSI" in q.query["columns"]
        assert "RSI|240" not in q.query["columns"]
        assert _filter_lefts(q) == ["RSI"]

    def test_mixed_tf_rules_get_per_rule_suffixes(self) -> None:
        config = ScreenConfig(
            name="Mixed TF",
            timeframes=["1D", "4h"],
            filters=[
                FilterRule(
                    category="volume",
                    indicator="rvol_high",
                    params={"threshold": 1.2},
                    timeframe="1D",
                ),
                FilterRule(
                    category="momentum",
                    indicator="macd_bullish",
                    timeframe="4h",
                ),
            ],
        )
        q = self.specialist.build_query(config)
        assert q is not None
        lefts = _filter_lefts(q)
        assert "relative_volume_10d_calc" in lefts  # 1D rule untouched
        assert "MACD.macd|240" in lefts  # 4h rule suffixed on all columns

    def test_single_filter_wraps_in_and(self) -> None:
        """where2() requires And/Or wrapping — one filter used to yield filter2='greater'."""
        config = ScreenConfig(
            name="Single",
            filters=[FilterRule(category="momentum", indicator="rsi_gt", params={"threshold": 60})],
        )
        q = self.specialist.build_query(config)
        assert q is not None
        assert isinstance(q.query["filter2"], dict)
        assert q.query["filter2"]["operator"] == "and"

    def test_price_near_ema_suffixes_ema_on_both_paths(self) -> None:
        """below_pct() takes a Column now, so the EMA name gets the TF suffix too."""
        rule4h = FilterRule(
            category="trend",
            indicator="price_near_ema",
            params={"period": 20, "pct_within": 2},
            timeframe="4h",
        )
        q4 = self.specialist.build_query(
            ScreenConfig(name="Near 4h", timeframes=["4h"], filters=[rule4h])
        )
        expr4 = q4.query["filter2"]["operands"][0]["expression"]
        assert expr4["left"] == "close|240"
        assert expr4["right"][0] == "EMA20|240"

        rule1d = FilterRule(
            category="trend",
            indicator="price_near_ema",
            params={"period": 20, "pct_within": 2},
            timeframe="1D",
        )
        q1 = self.specialist.build_query(
            ScreenConfig(name="Near 1D", timeframes=["1D"], filters=[rule1d])
        )
        expr1 = q1.query["filter2"]["operands"][0]["expression"]
        assert expr1["left"] == "close"
        assert expr1["right"][0] == "EMA20"

    def test_discover_strips_pipe_suffixes_from_result_columns(self) -> None:
        import asyncio
        from unittest.mock import patch

        import pandas as pd

        class _FakeQuery:
            def limit(self, n: int) -> "_FakeQuery":
                return self

            def get_scanner_data(self):
                return (
                    1,
                    pd.DataFrame(
                        {
                            "ticker": ["NASDAQ:AAPL"],
                            "EMA20|240": [1.5],
                            "close|240": [100.0],
                            "market_cap_basic": [3e12],
                        }
                    ),
                )

        config = ScreenConfig(
            name="TF 4h",
            timeframes=["4h"],
            filters=[
                FilterRule(
                    category="momentum",
                    indicator="rsi_gt",
                    params={"threshold": 60},
                    timeframe="4h",
                )
            ],
        )
        with patch.object(self.specialist, "build_query", return_value=_FakeQuery()):
            result = asyncio.run(self.specialist.discover(config))

        assert result.raw_data is not None
        assert "EMA20" in result.raw_data.columns
        assert "close" in result.raw_data.columns
        assert "EMA20|240" not in result.raw_data.columns
        assert result.tickers == ["AAPL"]
        assert result.timeframe == "4h"
