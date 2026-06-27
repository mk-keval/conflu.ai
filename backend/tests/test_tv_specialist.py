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
