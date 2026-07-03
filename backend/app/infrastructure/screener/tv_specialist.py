# TV Screener Specialist -- Domain expert for tradingview-screener package.

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable
import asyncio
import time
import pandas as pd
from backend.app.infrastructure.screener.configs import ScreenConfig, FilterRule
from backend.app.core.logging import get_logger

log = get_logger("conflu.screener.tv_specialist")

# ---------------------------------------------------------------------------
# Filter map: ScreenConfig filter names -> tradingview_screener Query expressions
# ---------------------------------------------------------------------------

FILTER_MAP: dict[str, Callable[..., Any]] = {
    "price_above_ema":      lambda p, col: col("close") > col(f"EMA{p.get('period', 50)}"),
    "price_below_ema":      lambda p, col: col("close") < col(f"EMA{p.get('period', 50)}"),
    "rsi_oversold":         lambda p, col: col("RSI") < p.get("threshold", 30),
    "rsi_overbought":       lambda p, col: col("RSI") > p.get("threshold", 70),
    "macd_bullish":         lambda p, col: col("MACD.macd") > col("MACD.signal"),
    "macd_bearish":         lambda p, col: col("MACD.macd") < col("MACD.signal"),
    # Uses crosses_above — detects when MACD just crossed above signal.
    # (Column has no .shift(), so this is the closest proxy for "histogram rising")
    "macd_hist_rising":     lambda p, col: col("MACD.macd").crosses_above(col("MACD.signal")),
    "rvol_high":            lambda p, col: col("relative_volume_10d_calc") > p.get("threshold", 1.5),
    "adx_trending":         lambda p, col: col("ADX") > p.get("threshold", 25),
    "ema_cross":            lambda p, col: col(f"EMA{p['fast']}") > col(f"EMA{p['slow']}"),
    # Uses below_pct — BB.upper <= BB.lower * threshold. threshold=1.10 means 10% bandwidth.
    # (Column has no arithmetic ops, so this is the closest proxy for squeeze detection)
    "bb_squeeze":           lambda p, col: col("BB.upper").below_pct(col("BB.lower"), p.get("threshold", 1.10)),
    "price_above_vwap":     lambda p, col: col("close") > col("VWAP"),
    "price_below_vwap":     lambda p, col: col("close") < col("VWAP"),
    "rvol_low":             lambda p, col: col("relative_volume_10d_calc") < p.get("threshold", 0.7),
    "ema_cross_bearish":    lambda p, col: col(f"EMA{p['fast']}") < col(f"EMA{p['slow']}"),
    "sector_is":            lambda p, col: col("sector").isin(p["sectors"]),
    "market_cap_gt":        lambda p, col: col("market_cap_basic") > p["value"],
    "analyst_strongbuy":    lambda p, col: col("AnalystRating") == "StrongBuy",
    "analyst_sell":         lambda p, col: col("AnalystRating").isin(["Sell", "StrongSell"]),
    "dividend_yield_gt":    lambda p, col: col("dividends_yield_current") > p.get("threshold", 0.03),
}


@dataclass
class TVDiscoveryResult:
    screen_name: str
    total_matches: int
    tickers: list[str]
    execution_ms: int
    raw_data: pd.DataFrame | None
    timeframe: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


class TVScreenerSpecialist:
    """Domain expert for tradingview-screener package."""

    def __init__(self) -> None:
        from backend.app.core.logging import get_logger
        self.log = get_logger("conflu.screener.tv_specialist")

    # ------------------------------------------------------------------
    # Filter compilation
    # ------------------------------------------------------------------

    def compile_filters(self, filters: list[FilterRule]) -> Any | None:
        """Compile a list of FilterRules into a single tradingview_screener condition.

        Returns None if no filters to apply.
        note: `tradingview_screener` does not provide a `Not` operator.
              For negated filters, invert the comparison at the filter-map level.
        """
        from tradingview_screener.column import Column
        from tradingview_screener.query import And

        conditions = []
        for flt in filters:
            builder = FILTER_MAP.get(flt.indicator)
            if builder is None:
                self.log.warning("unknown_filter", indicator=flt.indicator)
                continue
            condition = builder(flt.params, Column)
            conditions.append(condition)

        if not conditions:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return And(*conditions)

    # ------------------------------------------------------------------
    # Query building
    # ------------------------------------------------------------------

    def build_query(self, config: ScreenConfig) -> Any | None:
        """Build a tradingview_screener Query from a ScreenConfig.

        Returns None if filters cannot be compiled.
        Selects extra columns needed by the confluence scorer so it can
        compute meaningful scores from real TV data (not default zeros).
        """
        from tradingview_screener.query import Query

        q = Query()
        if config.universe and config.universe.index:
            q.set_index(config.universe.index)
        else:
            markets = config.universe.markets or ["america"]
            q.set_markets(*markets)
        if config.timeframes:
            q.set_property("interval", config.timeframes[0])

        # Select columns needed by the confluence scorer
        # NOTE: .select() replaces TV's default columns, so we must include
        # all the default columns the scorer references here too.
        q.select(
            # TV defaults the scorer needs (+ frontend display columns)
            "close",
            "change",
            "volume",
            "relative_volume_10d_calc",
            "sector",
            "AnalystRating",
            "market_cap_basic",
            "price_earnings_ttm",
            "earnings_per_share_diluted_ttm",
            "dividends_yield_current",
            # Trend
            "EMA20",
            "EMA50",
            "EMA200",
            # Momentum
            "MACD.macd",
            "MACD.signal",
            "MACD.hist",
            "RSI",
            # Volume
            "volume_change",
            "VWAP",
            # Quality/volatility
            "ADX",
            "ATR",
            "BB.upper",
            "BB.lower",
        )

        # Apply filters
        condition = self.compile_filters(config.filters)
        if condition is not None:
            q.where2(condition)

        return q

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    async def discover(self, config: ScreenConfig, timeout: float = 30.0) -> TVDiscoveryResult:
        """Run a single TF screen against TV, with timeout.

        Args:
            config: ScreenConfig with filters, universe, timeframe.
            timeout: Max seconds to wait for TV API response.

        Returns:
            TVDiscoveryResult with matched tickers + raw TV data.
        """
        start = time.monotonic()
        q = self.build_query(config)
        if q is None:
            return TVDiscoveryResult(
                screen_name=config.name,
                total_matches=0,
                tickers=[],
                execution_ms=0,
                raw_data=None,
                timeframe=config.timeframes[0] if config.timeframes else "1D",
            )
        q.limit(config.limit or 500)
        loop = asyncio.get_running_loop()

        try:
            total, df = await asyncio.wait_for(
                loop.run_in_executor(None, q.get_scanner_data),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            self.log.warning("tv_timeout", screen=config.name, timeout=timeout)
            return TVDiscoveryResult(
                screen_name=config.name,
                total_matches=0,
                tickers=[],
                execution_ms=round((time.monotonic() - start) * 1000),
                raw_data=None,
                timeframe=config.timeframes[0] if config.timeframes else "1D",
            )
        except Exception:
            self.log.exception("tv_discover_failed", screen=config.name)
            return TVDiscoveryResult(
                screen_name=config.name,
                total_matches=0,
                tickers=[],
                execution_ms=round((time.monotonic() - start) * 1000),
                raw_data=None,
                timeframe=config.timeframes[0] if config.timeframes else "1D",
            )

        duration_ms = round((time.monotonic() - start) * 1000)
        tickers = df["ticker"].str.split(":").str[-1].unique().tolist() if df is not None else []
        return TVDiscoveryResult(
            screen_name=config.name,
            total_matches=total,
            tickers=tickers,
            execution_ms=duration_ms,
            raw_data=df,
            timeframe=config.timeframes[0] if config.timeframes else "1D",
        )

    async def discover_multi_tf(self, config: ScreenConfig) -> list[TVDiscoveryResult]:
        """Multi-timeframe discovery: run separate TV query per TF, intersect tickers."""
        tf_filters: dict[str, list[FilterRule]] = {}
        for flt in config.filters:
            tf = flt.timeframe or "1D"
            tf_filters.setdefault(tf, []).append(flt)

        results: list[TVDiscoveryResult] = []
        for tf, filters in tf_filters.items():
            tf_config = ScreenConfig(
                name=config.name,
                asset_classes=config.asset_classes,
                timeframes=[tf],
                filters=filters,
                universe=config.universe,
                limit=config.limit,
            )
            results.append(await self.discover(tf_config))

        return results

    def intersect_tickers(self, results: list[TVDiscoveryResult]) -> list[str]:
        """Intersect tickers across timeframes (strict: must match ALL)."""
        if not results:
            return []
        sets = [set(r.tickers) for r in results]
        return list(set.intersection(*sets))
