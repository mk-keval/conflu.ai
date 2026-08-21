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
#
# LEGEND:
#   col = tradingview_screener.Column class (callable returns a column expr)
#   p   = dict of params from the FilterRule
#
# Each lambda receives (params: dict, Column: class) and returns a condition.
# Complex conditions use And(*conds), Or(*conds) from the TV query builder.
# ---------------------------------------------------------------------------

# ── Helper to build And multi-condition ──────────────────────────────


def _and(*conds: Any) -> Any:
    """Combine conditions conjunctively.

    Polymorphic (P1.2): locally-evaluated conditions (:class:`LocalCond`)
    reduce via ``&``; TV query expressions use tradingview_screener's And.
    """
    from backend.app.infrastructure.screener.tv_local_eval import _is_local_cond
    if conds and all(_is_local_cond(c) for c in conds):
        result = conds[0]
        for c in conds[1:]:
            result = result & c
        return result
    from tradingview_screener.query import And as _And
    return _And(*conds)


def _or(*conds: Any) -> Any:
    """Combine conditions disjunctively (local shims reduce via ``|``)."""
    from backend.app.infrastructure.screener.tv_local_eval import _is_local_cond
    if conds and all(_is_local_cond(c) for c in conds):
        result = conds[0]
        for c in conds[1:]:
            result = result | c
        return result
    from tradingview_screener.query import Or as _Or
    return _Or(*conds)


FILTER_MAP: dict[str, Callable[..., Any]] = {
    # =====================================================================
    # PRICE ACTION
    # =====================================================================
    "price_above_ema":      lambda p, col: col("close") > col(f"EMA{p.get('period', 50)}"),
    "price_below_ema":      lambda p, col: col("close") < col(f"EMA{p.get('period', 50)}"),
    "price_above_vwap":     lambda p, col: col("close") > col("VWAP"),
    "price_below_vwap":     lambda p, col: col("close") < col("VWAP"),

    # Price above MULTIPLE EMAs — requires periods as a list, e.g. [20, 50, 200]
    "price_above_emas":     lambda p, col: _and(*[
        col("close") > col(f"EMA{period}")
        for period in p["periods"]
    ]),
    "price_below_emas":     lambda p, col: _and(*[
        col("close") < col(f"EMA{period}")
        for period in p["periods"]
    ]),

    # Crossovers — detect FRESH breakouts / breakdowns
    "cross_above_ma":       lambda p, col: col("close").crosses_above(col(f"EMA{p.get('period', 50)}")),
    "cross_below_ma":       lambda p, col: col("close").crosses_below(col(f"EMA{p.get('period', 50)}")),
    "bb_breakout_upper":    lambda p, col: col("close").crosses_above(col("BB.upper")),
    "bb_breakout_lower":    lambda p, col: col("close").crosses_below(col("BB.lower")),

    # Price position relative to Bollinger Bands (state, not fresh cross)
    "price_below_bb_lower": lambda p, col: col("close") < col("BB.lower"),
    "price_above_bb_upper": lambda p, col: col("close") > col("BB.upper"),

    # =====================================================================
    # TREND QUALITY
    # =====================================================================
    # Bullish EMA stack: EMA20 > EMA50 > EMA200 (ideal long-side alignment)
    "ema_stack_bullish":    lambda p, col: _and(
        col("EMA20") > col("EMA50"),
        col("EMA50") > col("EMA200"),
    ),
    # Bearish EMA stack: EMA20 < EMA50 < EMA200 (ideal short-side alignment)
    "ema_stack_bearish":    lambda p, col: _and(
        col("EMA20") < col("EMA50"),
        col("EMA50") < col("EMA200"),
    ),
    # EMA crossover — fast MA just crossed above slow MA
    "ema_cross":            lambda p, col: col(f"EMA{p['fast']}").crosses_above(col(f"EMA{p['slow']}")),
    "ema_cross_bearish":    lambda p, col: col(f"EMA{p['fast']}").crosses_below(col(f"EMA{p['slow']}")),

    # Supertrend — trend-following indicator by moving-average + ATR
    "supertrend_uptrend":   lambda p, col: col("supertrend.up") > 0,
    "supertrend_downtrend": lambda p, col: col("supertrend.down") > 0,

    # =====================================================================
    # MOMENTUM
    # =====================================================================
    "rsi_oversold":         lambda p, col: col("RSI") < p.get("threshold", 30),
    "rsi_overbought":       lambda p, col: col("RSI") > p.get("threshold", 70),

    # Generic RSI comparators — semantically clear for non-overbought/oversold thresholds
    "rsi_gt":               lambda p, col: col("RSI") > p.get("threshold", 50),
    "rsi_lt":               lambda p, col: col("RSI") < p.get("threshold", 50),

    # RSI in a specific range — detect sweet spots, e.g. [55, 75] for long momentum
    "rsi_in_range":         lambda p, col: _and(
        col("RSI") > p["min"],
        col("RSI") < p["max"],
    ),

    # Confluence filters — two independent indicators agreeing = stronger signal
    "rsi_macd_bullish":     lambda p, col: _and(
        col("RSI") > 50,
        col("MACD.macd") > col("MACD.signal"),
    ),
    "rsi_macd_bearish":     lambda p, col: _and(
        col("RSI") < 50,
        col("MACD.macd") < col("MACD.signal"),
    ),

    "macd_bullish":         lambda p, col: col("MACD.macd") > col("MACD.signal"),
    "macd_bearish":         lambda p, col: col("MACD.macd") < col("MACD.signal"),
    # Detects FRESH MACD bullish crossover (just crossed above signal)
    "macd_cross_above":     lambda p, col: col("MACD.macd").crosses_above(col("MACD.signal")),
    # Detects FRESH MACD bearish crossover
    "macd_cross_below":     lambda p, col: col("MACD.macd").crosses_below(col("MACD.signal")),
    # MACD histogram above zero (positive momentum)
    # TV Column v3.x lacks .shift(), so "rising" is approximated as "positive"
    "macd_hist_rising":     lambda p, col: col("MACD.hist") > 0,

    # Stochastic Oscillator — momentum + mean-reversion timing
    "stoch_bullish_cross":  lambda p, col: col("STOCH.K").crosses_above(col("STOCH.D")),
    "stoch_bearish_cross":  lambda p, col: col("STOCH.K").crosses_below(col("STOCH.D")),
    "stoch_oversold":       lambda p, col: col("STOCH.K") < p.get("threshold", 20),
    "stoch_overbought":     lambda p, col: col("STOCH.K") > p.get("threshold", 80),

    # CCI — commodity channel index for cyclical entries
    "cci_oversold":         lambda p, col: col("CCI20") < p.get("threshold", -100),
    "cci_overbought":       lambda p, col: col("CCI20") > p.get("threshold", 100),

    # =====================================================================
    # VOLUME / ACCUMULATION
    # =====================================================================
    "rvol_high":            lambda p, col: col("relative_volume_10d_calc") > p.get("threshold", 1.5),
    "rvol_low":             lambda p, col: col("relative_volume_10d_calc") < p.get("threshold", 0.7),

    # OBV trending up (accumulation) — price up on above-avg volume
    # TV Column v3.x does NOT support .shift(), so we use volume/price proxy:
    #   close > SMA20 (price trending up) + above-avg relative volume (accumulation)
    "obv_rising":           lambda p, col: _and(
        col("close") > col("SMA20"),
        col("relative_volume_10d_calc") > p.get("min_rvol", 1.0),
    ),
    # OBV trending down (distribution) — price down on above-avg volume
    "obv_falling":          lambda p, col: _and(
        col("close") < col("SMA20"),
        col("relative_volume_10d_calc") > p.get("min_rvol", 1.0),
    ),

    # Volume spike vs 10-day average (TV Column v3.x has no .shift())
    "volume_spike":         lambda p, col: col("relative_volume_10d_calc") > p.get("threshold", 2.0),

    # Price inside/outside VWAP by a percentage band
    "vwap_band":            lambda p, col: col("close").below_pct(col("VWAP"), p.get("upper", 1.03))
        if p.get("side", "above") == "above"
        else col("VWAP").below_pct(col("close"), p.get("upper", 1.03)),

    # =====================================================================
    # VOLATILITY / QUALITY
    # =====================================================================
    "adx_trending":         lambda p, col: col("ADX") > p.get("threshold", 25),

    # BB squeeze: bands are tight relative to each other (low vol contraction)
    "bb_squeeze":           lambda p, col: col("BB.upper").below_pct(col("BB.lower"), p.get("threshold", 1.10)),

    # Tighter BB squeeze — for detecting coiled-spring setups
    "bb_squeeze_tight":     lambda p, col: col("BB.upper").below_pct(col("BB.lower"), p.get("threshold", 1.05)),

    # ATR as % of price below threshold (low volatility regime filter)
    "atr_pct_below":        lambda p, col: col("ATR").below_pct(col("close"), p.get("threshold", 0.03)),

    # ADX trending — trend strength above threshold (TV Column v3.x has no .shift())
    "adx_rising":           lambda p, col: col("ADX") > p.get("threshold", 25),

    # Consolidation proxy — narrow ATR range / tight BB (TV Column v3.x has no .shift())
    # Reveals contraction before expansion — Wyckoff "absorption" phase
    "inside_bar":           lambda p, col: col("ATR").below_pct(col("close"), p.get("max_atr_pct", 0.03)),

    # VWAP reclaim — price above VWAP (TV Column v3.x has no .shift() for prior-bar confirmation)
    # crosses_above alone captures the fresh reclaim most faithfully.
    "vwap_reclaim":         lambda p, col: col("close").crosses_above(col("VWAP")),

    # VWAP rejection — price below VWAP
    "vwap_reject":          lambda p, col: col("close").crosses_below(col("VWAP")),

    # BB expansion — volatility expanding after compression.
    # Width proxy via below_pct: large width = bands wide apart
    "bb_expanding":         lambda p, col: col("BB.lower").below_pct(col("BB.upper"), p.get("threshold", 0.85)),

    # =====================================================================
    # SECTOR / INDUSTRY
    # =====================================================================
    "sector_is":            lambda p, col: col("sector").isin(p["sectors"]),
    "industry_in":          lambda p, col: col("industry").isin(p["industries"]),

    # =====================================================================
    # FUNDAMENTAL
    # =====================================================================
    "market_cap_gt":        lambda p, col: col("market_cap_basic") > p["value"],
    "market_cap_lt":        lambda p, col: col("market_cap_basic") < p["value"],
    "analyst_strongbuy":    lambda p, col: col("AnalystRating") == "StrongBuy",
    "analyst_sell":         lambda p, col: col("AnalystRating").isin(["Sell", "StrongSell"]),
    "analyst_rating_in":    lambda p, col: col("AnalystRating").isin(p["ratings"]),
    "dividend_yield_gt":    lambda p, col: col("dividends_yield_current") > p.get("threshold", 0.03),
    "eps_positive":         lambda p, col: col("earnings_per_share_diluted_ttm") > 0,
    "pe_max":               lambda p, col: col("price_earnings_ttm") < p.get("max_pe", 50),

    # =====================================================================
    # PRICE / EXCHANGE / COUNTRY / VOLUME
    # =====================================================================
    "close_above":          lambda p, col: col("close") > p.get("threshold", 1.0),
    "close_below":          lambda p, col: col("close") < p.get("threshold", 1.0),

    "exchange_in":          lambda p, col: col("exchange").isin(p["exchanges"]),
    "country_in":           lambda p, col: col("country").isin(p["countries"]),

    "volume_gt":            lambda p, col: col("volume") > p.get("threshold", 500000),
    "volume_lt":            lambda p, col: col("volume") < p.get("threshold", 1.0),
    "avg_volume_gt":        lambda p, col: col("average_volume_10d_calc") > p.get("threshold", 500000),
    "avg_volume_lt":        lambda p, col: col("average_volume_10d_calc") < p.get("threshold", 1.0),
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


# Columns selected for every TV discovery query: everything the confluence
# scorer references + all indicator columns FILTER_MAP can evaluate + the
# elite/frontend display fields. Shared by the legacy per-template query
# builder AND the P1.2 One-Snapshot-Multi-Screen base query.
SNAPSHOT_COLUMNS: list[str] = [
    # TV defaults the scorer needs (+ frontend display columns)
    "close",
    "change",
    "volume",
    "relative_volume_10d_calc",
    "sector",
    "industry",
    "AnalystRating",
    "market_cap_basic",
    "price_earnings_ttm",
    "earnings_per_share_diluted_ttm",
    "dividends_yield_current",
    # Exchange, country, price, volume, IPO date, institutional ownership
    "exchange",
    "country",
    "price",
    "volume",
    "average_volume_10d_calc",
    "ipo_date",
    "institutional_ownership",
    "short_float",
    "float_shares",
    # Trend
    "EMA20",
    "EMA50",
    "EMA200",
    # Momentum
    "MACD.macd",
    "MACD.signal",
    "MACD.hist",
    "RSI",
    "STOCH.K",
    "STOCH.D",
    "CCI20",
    # Volume
    "volume_change",
    "VWAP",
    "OBV",
    # Quality/volatility
    "ADX",
    "ATR",
    "BB.upper",
    "BB.middle",
    "BB.lower",
    # Supertrend — trend-following overlay
    "supertrend",
    "supertrend.up",
    "supertrend.down",
]


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

    def evaluate_filters_local(self, df: pd.DataFrame, filters: list[FilterRule]) -> pd.Series | None:
        """Evaluate FILTER_MAP rules LOCALLY against a snapshot DataFrame.

        Feeds :class:`LocalColumn` as the Column factory so every lambda
        produces boolean masks instead of TV query expressions — one source
        of truth for filter semantics (P1.2 One-Snapshot-Multi-Screen).

        Fail-closed: any rule that can't be evaluated locally (unknown
        indicator, missing column) makes the whole template unmatched and
        logs loudly — we never silently widen a template's match set.
        """
        from backend.app.infrastructure.screener.tv_local_eval import (
            FilterEvaluationError,
            LocalColumn,
            LocalCond,
        )

        def col_factory(name: str) -> LocalColumn:
            return LocalColumn(df, name)

        mask = pd.Series(True, index=df.index)
        matched_any_rule = False
        for flt in filters:
            builder = FILTER_MAP.get(flt.indicator)
            if builder is None:
                log.warning("local_eval_unknown_filter", indicator=flt.indicator)
                return None
            try:
                cond = builder(flt.params, col_factory)
            except FilterEvaluationError as exc:
                log.warning(
                    "local_eval_missing_column",
                    indicator=flt.indicator,
                    error=str(exc),
                )
                return None
            if not isinstance(cond, LocalCond):
                # e.g. a nested TV-side And/Or slipped through — cannot evaluate
                log.warning("local_eval_non_local_condition", indicator=flt.indicator)
                return None
            mask = mask & cond.mask
            matched_any_rule = True

        if not matched_any_rule:
            return None
        return mask

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

        # Select columns needed by the confluence scorer + all elite filters
        # NOTE: .select() replaces TV's default columns, so we must include
        # all the default columns the scorer references here too.
        q.select(*SNAPSHOT_COLUMNS)

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
