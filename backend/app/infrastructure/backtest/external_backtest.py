"""
Comprehensive Backtest Engine using External Data (Yahoo Finance)
No database dependency - fetches fresh data for backtesting
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Literal, TYPE_CHECKING

import numpy as np
import pandas as pd

from backend.app.core.logging import get_logger

if TYPE_CHECKING:
    from backend.app.infrastructure.data.fetcher import OHLCVFetcher

log = get_logger("conflu.backtest.external")


@dataclass
class BacktestConfig:
    """Configuration for a backtest run."""
    symbol: str
    timeframe: str = "1D"
    start_date: str = ""
    end_date: str = ""
    initial_cash: float = 100_000.0
    fees_bps: float = 10.0
    slippage_bps: float = 5.0
    position_sizing: Literal["fixed", "atr", "kelly"] = "fixed"
    sizing_params: dict = field(default_factory=dict)
    signal_params: dict = field(default_factory=dict)
    # Preferred over signal_params: full rule objects keep per-rule operator,
    # timeframe, and duplicate indicators intact. Populate from ScreenConfig.filters.
    signal_filters: list = field(default_factory=list)
    direction: Literal["long", "short"] = "long"
    stop_atr_mult: float = 2.0
    target_atr_mult: float = 3.0
    max_hold_bars: Optional[int] = None
    exit_on_signal: bool = False


@dataclass
class BacktestResult:
    """Results from a backtest run."""
    symbol: str
    timeframe: str
    start_date: str
    end_date: str
    initial_cash: float
    final_equity: float
    total_return: float
    annualized_return: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    max_drawdown_pct: float
    win_rate: float
    profit_factor: float
    expectancy: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_win: float
    avg_loss: float
    avg_hold_days: float
    max_consecutive_wins: int
    max_consecutive_losses: int
    trades: list[dict] = field(default_factory=list)
    equity_curve: list[dict] = field(default_factory=list)
    error: Optional[str] = None
    # Validation-reset additions (2026-10-19): R-based stats + data-quality notes
    expectancy_r: float = 0.0
    avg_win_r: float = 0.0
    avg_loss_r: float = 0.0
    avg_hold_bars: float = 0.0
    exit_reason_counts: dict = field(default_factory=dict)
    time_in_market_pct: float = 0.0
    skipped_filters: list[str] = field(default_factory=list)


@dataclass
class _EvalRule:
    """Lightweight filter rule wrapper (legacy signal_params path)."""

    indicator: str
    params: dict = field(default_factory=dict)
    operator: str = "gt"
    timeframe: str = "1D"
    negate: bool = False


def _rule_num(params: dict, default: float, *keys: str) -> float:
    """Read a numeric rule parameter, accepting both 'threshold' and 'value' styles."""
    for key in (keys or ("threshold", "value")):
        if key in params:
            try:
                return float(params[key])
            except (TypeError, ValueError):
                continue
    return default


# Declarative evaluator table: indicator -> (required columns, builder(columns, params)).
# Covers every technical rule used by config/screens/*.yaml (audited 2026-10-19).
_SIMPLE_FILTER_RULES: dict[str, tuple[tuple[str, ...], object]] = {
    "price_above_vwap": (("close", "VWAP"), lambda c, p: c[0] > c[1]),
    "price_below_vwap": (("close", "VWAP"), lambda c, p: c[0] < c[1]),
    "price_above_bb_upper": (("close", "BB.upper"), lambda c, p: c[0] > c[1]),
    "price_below_bb_lower": (("close", "BB.lower"), lambda c, p: c[0] < c[1]),
    "ema_stack_bullish": (("EMA20", "EMA50", "EMA200"), lambda c, p: (c[0] > c[1]) & (c[1] > c[2])),
    "ema_stack_bearish": (("EMA20", "EMA50", "EMA200"), lambda c, p: (c[0] < c[1]) & (c[1] < c[2])),
    "rsi_oversold": (("RSI",), lambda c, p: c[0] < _rule_num(p, 30)),
    "rsi_overbought": (("RSI",), lambda c, p: c[0] > _rule_num(p, 70)),
    "rsi_gt": (("RSI",), lambda c, p: c[0] > _rule_num(p, 50)),
    "rsi_lt": (("RSI",), lambda c, p: c[0] < _rule_num(p, 50)),
    "rsi_in_range": (("RSI",), lambda c, p: (c[0] > _rule_num(p, 40, "min")) & (c[0] < _rule_num(p, 80, "max"))),
    "rsi_in_range_max": (("RSI",), lambda c, p: (c[0] > _rule_num(p, 40, "min")) & (c[0] < _rule_num(p, 80, "max"))),
    "rsi_macd_bullish": (("RSI", "MACD.macd", "MACD.signal"), lambda c, p: (c[0] > 50) & (c[1] > c[2])),
    "macd_bullish": (("MACD.macd", "MACD.signal"), lambda c, p: c[0] > c[1]),
    "macd_bearish": (("MACD.macd", "MACD.signal"), lambda c, p: c[0] < c[1]),
    "macd_hist_rising": (("MACD.hist",), lambda c, p: c[0] > 0),
    "adx_trending": (("ADX",), lambda c, p: c[0] > _rule_num(p, 25)),
    "adx_rising": (("ADX",), lambda c, p: c[0] > _rule_num(p, 25)),
    "atr_pct_below": (("ATR", "close"), lambda c, p: (c[0] / c[1]) < _rule_num(p, 0.03)),
    "inside_bar": (("ATR", "close"), lambda c, p: (c[0] / c[1]) < _rule_num(p, 0.03, "max_atr_pct")),
    "bb_squeeze": (("BB.upper", "BB.lower"), lambda c, p: (c[0] / c[1]) < _rule_num(p, 1.10)),
    "bb_squeeze_tight": (("BB.upper", "BB.lower"), lambda c, p: (c[0] / c[1]) < _rule_num(p, 1.05)),
    "rvol_high": (("relative_volume_10d_calc",), lambda c, p: c[0] > _rule_num(p, 1.5)),
    "rvol_low": (("relative_volume_10d_calc",), lambda c, p: c[0] < _rule_num(p, 0.7)),
    "volume_spike": (("relative_volume_10d_calc",), lambda c, p: c[0] > _rule_num(p, 2.0)),
    "volume_gt": (("volume",), lambda c, p: c[0] > _rule_num(p, 0)),
    "avg_volume_gt": (("average_volume_10d_calc",), lambda c, p: c[0] > _rule_num(p, 500000)),
    "close_above": (("close",), lambda c, p: c[0] > _rule_num(p, 0)),
    "price_near_52w_high": (
        ("close", "price_52_week_high"),
        lambda c, p: c[0] > c[1] * (1 - _rule_num(p, 5, "pct_within", "pct") / 100),
    ),
    "price_above_52w_low": (
        ("close", "price_52_week_low"),
        lambda c, p: c[0] > c[1] * (1 + _rule_num(p, 30, "pct_above", "pct") / 100),
    ),
    "obv_rising": (
        ("close", "SMA20", "relative_volume_10d_calc"),
        lambda c, p: (c[0] > c[1]) & (c[2] > _rule_num(p, 1.0, "min_rvol")),
    ),
    "obv_falling": (
        ("close", "SMA20", "relative_volume_10d_calc"),
        lambda c, p: (c[0] < c[1]) & (c[2] > _rule_num(p, 1.0, "min_rvol")),
    ),
    "cci_oversold": (("CCI20",), lambda c, p: c[0] < _rule_num(p, -100)),
}


class ExternalBacktestEngine:
    """
    Backtest engine that fetches data from Yahoo Finance on demand.
    No database dependency - completely self-contained.
    """

    def __init__(
        self,
        fetcher: Optional[object] = None,
        initial_cash: float = 100_000.0,
        fees_bps: float = 10.0,
        slippage_bps: float = 5.0,
    ):
        self.fetcher = fetcher
        self.initial_cash = initial_cash
        self.fees_bps = fees_bps
        self.slippage_bps = slippage_bps
        self._log = log

    def set_fetcher(self, fetcher):
        """Set the data fetcher."""
        self.fetcher = fetcher

    async def run_backtest(
        self,
        config: BacktestConfig,
    ) -> BacktestResult:
        """Run a complete backtest for a single symbol."""
        self._log.info(f"Starting backtest for {config.symbol} ({config.timeframe})")

        if self.fetcher is None:
            return BacktestResult(
                symbol=config.symbol,
                timeframe=config.timeframe,
                start_date=config.start_date,
                end_date=config.end_date,
                initial_cash=config.initial_cash,
                final_equity=0,
                total_return=0,
                annualized_return=0,
                sharpe_ratio=0,
                sortino_ratio=0,
                max_drawdown=0,
                max_drawdown_pct=0,
                win_rate=0,
                profit_factor=0,
                expectancy=0,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                avg_win=0,
                avg_loss=0,
                avg_hold_days=0,
                max_consecutive_wins=0,
                max_consecutive_losses=0,
                error="No data fetcher configured",
            )

        df = await self.fetcher.fetch_yahoo(  # type: ignore
            config.symbol,
            config.timeframe,
            config.start_date,
            config.end_date,
        )

        if df is None or df.empty:
            return BacktestResult(
                symbol=config.symbol,
                timeframe=config.timeframe,
                start_date=config.start_date,
                end_date=config.end_date,
                initial_cash=config.initial_cash,
                final_equity=0,
                total_return=0,
                annualized_return=0,
                sharpe_ratio=0,
                sortino_ratio=0,
                max_drawdown=0,
                max_drawdown_pct=0,
                win_rate=0,
                profit_factor=0,
                expectancy=0,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                avg_win=0,
                avg_loss=0,
                avg_hold_days=0,
                max_consecutive_wins=0,
                max_consecutive_losses=0,
                error="No data available",
            )

        df_ind = self._compute_indicators(df)

        entries, skipped_filters = await self._generate_signals(
            df, config, df_with_indicators=df_ind
        )

        if entries is None:
            return BacktestResult(
                symbol=config.symbol,
                timeframe=config.timeframe,
                start_date=config.start_date,
                end_date=config.end_date,
                initial_cash=config.initial_cash,
                final_equity=0,
                total_return=0,
                annualized_return=0,
                sharpe_ratio=0,
                sortino_ratio=0,
                max_drawdown=0,
                max_drawdown_pct=0,
                win_rate=0,
                profit_factor=0,
                expectancy=0,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                avg_win=0,
                avg_loss=0,
                avg_hold_days=0,
                max_consecutive_wins=0,
                max_consecutive_losses=0,
                error="Signal generation failed",
                skipped_filters=skipped_filters,
            )

        size_df = self._compute_position_sizes(df_ind, entries, config)

        result = self._run_simulation(df_ind, entries, size_df, config)
        result.skipped_filters = skipped_filters

        self._log.info(
            f"Backtest complete for {config.symbol}: "
            f"{result.total_trades} trades, "
            f"Return: {result.total_return:.2%}, "
            f"Sharpe: {result.sharpe_ratio:.2f}"
        )

        return result

    # Indicators that cannot be evaluated from OHLCV alone. Rules using them
    # are recorded in result.skipped_filters and excluded from the mask —
    # recorded deviations, never silent passes (2026-10-19 validation reset).
    _NOT_APPLIED_INDICATORS = {
        "market_cap_gt",
        "exchange_in",
        "country_in",
        "eps_positive",
        "pe_max",
        "analyst_rating_in",
        "sector_in",
        "dividend_yield_gt",
        "rs_rank_min",
    }
    # Fundamental-category rules that ARE evaluable from price/volume alone.
    _LOCALLY_EVALUABLE = {"close_above", "volume_gt"}
    _TF_ALIASES = {"1d": "1D", "d": "1D", "day": "1D", "4h": "4h", "240": "4h", "1h": "1h", "60": "1h"}

    def _norm_timeframe(self, tf: Optional[str]) -> str:
        key = str(tf or "1D").strip().lower()
        return self._TF_ALIASES.get(key, str(tf or "1D"))

    def _resolve_filter_rules(self, config: BacktestConfig, skipped: list[str]) -> list:
        """Return evaluable rules; record every rule that is dropped.

        Preferred path: ``config.signal_filters`` — full rule objects that keep
        per-rule operator, timeframe, and duplicate indicators intact.
        Legacy path: ``config.signal_params`` (indicator -> params dict) is
        wrapped into single-timeframe rules for backward compatibility.
        """
        rules: list = []
        if config.signal_filters:
            for rule in config.signal_filters:
                indicator = getattr(rule, "indicator", None)
                if not indicator:
                    continue
                category = getattr(rule, "category", "") or ""
                if (
                    indicator in self._NOT_APPLIED_INDICATORS
                    or (category == "fundamental" and indicator not in self._LOCALLY_EVALUABLE)
                ):
                    skipped.append(f"{indicator} (not available offline)")
                    continue
                rules.append(rule)
            return rules

        for indicator, params in (config.signal_params or {}).items():
            if indicator in self._NOT_APPLIED_INDICATORS:
                skipped.append(f"{indicator} (not available offline)")
                continue
            rules.append(
                _EvalRule(indicator=indicator, params=dict(params or {}), timeframe=config.timeframe)
            )
        return rules

    async def _build_intraday_view(
        self,
        config: BacktestConfig,
        tf: str,
        daily_index: pd.Index,
    ) -> Optional[pd.DataFrame]:
        """Build a daily-indexed frame of intraday values aligned as-of each day.

        Fetches 1h bars and (for ``tf == "4h"``) resamples them to 4h buckets,
        computes indicators per intraday bar, then takes the last completed
        intraday bar per calendar day and forward-fills onto the daily index.
        Returns None when no usable intraday history exists.
        """
        intraday = await self.fetcher.fetch_yahoo(  # type: ignore[union-attr]
            config.symbol, "1h", config.start_date, config.end_date
        )
        if intraday is None or intraday.empty or len(intraday) < 30:
            return None

        if tf == "4h":
            intraday = (
                intraday.resample("4h")
                .agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"})
                .dropna(subset=["Close"])
            )
            if intraday.empty:
                return None

        with_indicators = self._compute_indicators(intraday)

        days = [pd.Timestamp(ts).date() for ts in with_indicators.index]
        last_per_day = with_indicators.groupby(days).last()

        daily_dates = [pd.Timestamp(ts).date() for ts in daily_index]
        view = pd.DataFrame(index=daily_index)
        for col in last_per_day.columns:
            aligned = last_per_day[col].reindex(daily_dates, method="ffill")
            view[col] = aligned.to_numpy()
        view = view.rename(
            columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}
        )
        return view

    async def _generate_signals(
        self,
        df: pd.DataFrame,
        config: BacktestConfig,
        df_with_indicators: Optional[pd.DataFrame] = None,
    ) -> tuple[Optional[pd.Series], list[str]]:
        """Generate entry signals by evaluating the full filter rules.

        Returns ``(entries, skipped)``. ``entries`` is None when the symbol
        cannot be evaluated at all (e.g. a 4h rule with no intraday data) —
        callers must exclude it, never treat it as "no signal".

        Honesty rules (2026-10-19 validation reset):
        - per-rule timeframes are honored (4h rules are evaluated on 4h bars)
        - unknown indicators / missing columns are recorded in ``skipped``
          and treated as NOT matched — never as silent passes
        """
        skipped: list[str] = []
        try:
            rules = self._resolve_filter_rules(config, skipped)
            if not rules:
                log.warning(f"No evaluable technical filters for {config.symbol}")
                return None, skipped

            base_tf = self._norm_timeframe(config.timeframe)
            df_with_indicators = (
                df_with_indicators if df_with_indicators is not None else self._compute_indicators(df)
            )
            daily_view = df_with_indicators.rename(
                columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}
            )

            rules_by_tf: dict[str, list] = {}
            for rule in rules:
                tf = self._norm_timeframe(getattr(rule, "timeframe", None) or base_tf)
                rules_by_tf.setdefault(tf, []).append(rule)

            mask = pd.Series(True, index=df.index)
            for tf, tf_rules in rules_by_tf.items():
                if tf == base_tf:
                    view = daily_view
                elif tf in ("4h", "1h") and base_tf == "1D":
                    view = await self._build_intraday_view(config, tf, df.index)
                    if view is None:
                        for rule in tf_rules:
                            skipped.append(f"{rule.indicator}|{tf} (no intraday data available)")
                        log.warning(
                            f"Intraday data unavailable for {config.symbol} — "
                            f"{tf} rules cannot be evaluated"
                        )
                        return None, skipped
                else:
                    for rule in tf_rules:
                        skipped.append(f"{rule.indicator} ({tf} not supported in local backtest)")
                    log.warning(f"Unsupported rule timeframe {tf} for {config.symbol}")
                    return None, skipped

                rule_mask = self._evaluate_filters_frame(view, tf_rules, skipped)
                if rule_mask is None:
                    return None, skipped
                mask &= rule_mask

            log.info(
                f"Signals for {config.symbol}: {int(mask.sum())} entry bars, "
                f"{len(skipped)} skipped filters"
            )
            return mask, skipped
        except Exception as e:
            log.error(f"Signal generation failed for {config.symbol}: {e}")
            return None, skipped

    def _evaluate_filters_frame(
        self,
        frame: pd.DataFrame,
        rules: list,
        skipped: list[str],
    ) -> Optional[pd.Series]:
        """Evaluate every rule against a frame and AND the results.

        Unknown indicators and missing columns are recorded in ``skipped``
        and evaluate to False so a broken rule can never manufacture entries.
        """
        try:
            mask = pd.Series(True, index=frame.index)
            for rule in rules:
                mask &= self._eval_one_rule(frame, rule, skipped)
            return mask
        except Exception as e:
            log.warning(f"Pandas filter evaluation failed: {e}")
            return None

    def _eval_one_rule(self, frame: pd.DataFrame, rule, skipped: list[str]) -> pd.Series:
        indicator = getattr(rule, "indicator", "") or ""
        params = getattr(rule, "params", None) or {}
        index = frame.index
        no_match = pd.Series(False, index=index)

        if getattr(rule, "negate", False):
            skipped.append(f"{indicator} (negate unsupported in local backtest)")
            return no_match

        def need(*cols: str) -> Optional[list[pd.Series]]:
            missing = [c for c in cols if c not in frame.columns]
            if missing:
                skipped.append(f"{indicator} (missing column: {', '.join(missing)})")
                return None
            return [frame[c] for c in cols]

        # Dynamic-column rules
        if indicator in ("price_above_ema", "price_below_ema", "price_near_ema"):
            default_period = 20 if indicator == "price_near_ema" else 50
            period = int(params.get("period", default_period))
            cols = need(f"EMA{period}", "close")
            if cols is None:
                return no_match
            ema, close = cols
            if indicator == "price_above_ema":
                return (close > ema).astype(bool)
            if indicator == "price_below_ema":
                return (close < ema).astype(bool)
            pct = _rule_num(params, 2, "pct_within", "pct") / 100
            return ((close > ema * (1 - pct)) & (close < ema * (1 + pct))).astype(bool)

        if indicator in ("macd_cross_above", "macd_cross_below"):
            cols = need("MACD.macd", "MACD.signal")
            if cols is None:
                return no_match
            macd, signal = cols
            above = (macd > signal).astype(bool)
            prev_above = above.shift(1).fillna(False).astype(bool)
            if indicator == "macd_cross_above":
                return (above & ~prev_above).astype(bool)
            return ((~above) & prev_above).astype(bool)

        spec = _SIMPLE_FILTER_RULES.get(indicator)
        if spec is not None:
            cols = need(*spec[0])
            if cols is None:
                return no_match
            return spec[1](cols, params).astype(bool)

        skipped.append(f"{indicator} (unknown indicator — treated as NOT matched)")
        return no_match

    def _compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute technical indicators for the dataframe."""
        try:
            import pandas_ta as ta
        except ImportError:
            log.warning("pandas_ta not available")
            return df
        
        result = df.copy()
        close = df['Close']
        high = df['High']
        low = df['Low']
        volume = df['Volume']
        
        for period in [20, 50, 150, 200]:
            result[f'EMA{period}'] = ta.ema(close, length=period)
        
        macd = ta.macd(close, fast=12, slow=26, signal=9)
        if macd is not None:
            result['MACD.macd'] = macd.iloc[:, 0]
            result['MACD.signal'] = macd.iloc[:, 1]
            result['MACD.hist'] = macd.iloc[:, 2]
        
        result['RSI'] = ta.rsi(close, length=14)
        result['RSI2'] = ta.rsi(close, length=2)
        
        adx = ta.adx(high, low, close, length=14)
        if adx is not None:
            result['ADX'] = adx.iloc[:, 0]
        
        result['ATR'] = ta.atr(high, low, close, length=14)
        
        bb = ta.bbands(close, length=20, std=2)
        if bb is not None:
            result['BB.upper'] = bb.iloc[:, 0]
            result['BB.basis'] = bb.iloc[:, 1]
            result['BB.lower'] = bb.iloc[:, 2]
        
        typical_price = (high + low + close) / 3
        vwap = (typical_price * volume).cumsum() / volume.cumsum()
        result['VWAP'] = vwap
        
        obv = ta.obv(close, volume)
        if obv is not None:
            result['OBV'] = obv
        
        result['average_volume_10d_calc'] = volume.rolling(10).mean()
        
        avg_vol_10d = volume.rolling(10).mean()
        result['relative_volume_10d_calc'] = volume / avg_vol_10d
        
        result['price_52_week_high'] = close.rolling(252).max()
        result['price_52_week_low'] = close.rolling(252).min()
        
        result['CCI20'] = ta.cci(high, low, close, length=20)
        
        stoch = ta.stoch(high, low, close, k=14, d=3)
        if stoch is not None:
            result['Stoch.K'] = stoch.iloc[:, 0]
            result['Stoch.D'] = stoch.iloc[:, 1]
        
        result['SMA20'] = ta.sma(close, length=20)
        
        return result

    def _compute_position_sizes(
        self,
        df: pd.DataFrame,
        entries: pd.Series,
        config: BacktestConfig,
    ) -> pd.DataFrame:
        """Compute position sizes based on config."""
        n_bars = len(df)
        size_df = pd.DataFrame(0.0, index=df.index, columns=['size'])
        
        if config.position_sizing == "fixed":
            cash_per_trade = config.sizing_params.get("cash_per_trade", 10000)
            size_df.loc[entries, 'size'] = cash_per_trade / df.loc[entries, 'Close']
            
        elif config.position_sizing == "atr":
            atr_period = config.sizing_params.get("atr_period", 14)
            atr_mult = config.sizing_params.get("atr_multiplier", 2.0)
            risk_pct = config.sizing_params.get("risk_per_trade", 0.01)
            
            high = df['High']
            low = df['Low']
            close = df['Close']
            
            tr1 = high - low
            tr2 = (high - close.shift()).abs()
            tr3 = (low - close.shift()).abs()
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(atr_period).mean()
            
            risk_amount = config.initial_cash * risk_pct
            size = risk_amount / (atr * atr_mult)
            size_df.loc[entries, 'size'] = size[entries]
            
        elif config.position_sizing == "kelly":
            kelly_fraction = config.sizing_params.get("kelly_fraction", 0.5)
            win_rate = config.sizing_params.get("win_rate", 0.55)
            avg_win = config.sizing_params.get("avg_win", 1.0)
            avg_loss = config.sizing_params.get("avg_loss", 1.0)
            
            if avg_loss > 0:
                kelly_pct = win_rate - (1 - win_rate) / (avg_win / avg_loss)
                kelly_pct = max(0, min(kelly_pct * kelly_fraction, 0.25))
            else:
                kelly_pct = 0.1
            
            size_df.loc[entries, 'size'] = (config.initial_cash * kelly_pct) / df.loc[entries, 'Close']
        
        return size_df

    def _run_simulation(
        self,
        df: pd.DataFrame,
        entries: pd.Series,
        size_df: pd.DataFrame,
        config: BacktestConfig,
    ) -> BacktestResult:
        """Run the backtest simulation.

        Model (2026-10-19 validation reset — replaces the look-ahead
        ``entries.shift(-N)`` exit hack that never modeled stops or targets):

        - Signals observed at bar t execute at bar t+1's open (never the same
          bar — no look-ahead).
        - Stops/targets come from ATR at the signal bar:
          stop = entry ± stop_atr_mult*ATR, target = entry ± target_atr_mult*ATR.
          When both are touched in the same bar, the stop is assumed first.
        - Optional exits: signal drop (``exit_on_signal``) and time cap
          (``max_hold_bars``); open positions close at the last bar (``eod``).
        - ``r_multiple`` = directional return per unit of initial stop risk.
        """
        n_bars = len(df)
        direction = 1 if config.direction == "long" else -1
        fees_rate = config.fees_bps / 10_000.0
        slip = config.slippage_bps / 10_000.0

        close = df["Close"].to_numpy(dtype=float)
        high = df["High"].to_numpy(dtype=float)
        low = df["Low"].to_numpy(dtype=float)
        open_ = df["Open"].to_numpy(dtype=float) if "Open" in df.columns else close.copy()
        atr = df["ATR"].to_numpy(dtype=float) if "ATR" in df.columns else np.full(n_bars, np.nan)
        sizes = (
            size_df["size"].to_numpy(dtype=float)
            if size_df is not None and "size" in size_df.columns
            else np.zeros(n_bars)
        )
        entry_signals = entries.to_numpy(dtype=bool)

        cash = float(config.initial_cash)
        equity = np.zeros(n_bars)
        trades: list[dict] = []
        bars_in_market = 0

        in_position = False
        pending_signal_idx: Optional[int] = None
        units = 0.0
        entry_idx = -1
        entry_signal_idx = -1
        entry_raw = 0.0
        entry_fill = 0.0
        entry_atr = 0.0
        stop_price = 0.0
        target_price = 0.0

        def _date(i: int) -> str:
            ts = df.index[i]
            return str(ts.date()) if hasattr(ts, "date") else str(ts)

        for i in range(n_bars):
            # 1) Manage an open position (checked from the bar after entry fill)
            if in_position:
                bars_held = i - entry_idx
                exit_raw: Optional[float] = None
                exit_reason = ""

                if direction == 1:
                    if low[i] <= stop_price:
                        exit_raw, exit_reason = stop_price, "stop"
                    elif high[i] >= target_price:
                        exit_raw, exit_reason = target_price, "target"
                else:
                    if high[i] >= stop_price:
                        exit_raw, exit_reason = stop_price, "stop"
                    elif low[i] <= target_price:
                        exit_raw, exit_reason = target_price, "target"

                if exit_raw is None and config.exit_on_signal and i > entry_idx and not entry_signals[i]:
                    exit_raw, exit_reason = close[i], "signal"
                if (
                    exit_raw is None
                    and config.max_hold_bars is not None
                    and bars_held >= config.max_hold_bars
                ):
                    exit_raw, exit_reason = close[i], "time"
                if exit_raw is None and i == n_bars - 1:
                    exit_raw, exit_reason = close[i], "eod"

                if exit_raw is not None:
                    exit_fill = exit_raw * (1 - direction * slip)
                    gross = direction * units * (exit_fill - entry_fill)
                    fees = (units * entry_fill + units * exit_fill) * fees_rate
                    pnl = gross - fees
                    stop_dist = abs(entry_raw - stop_price)
                    r_multiple = direction * (exit_raw - entry_raw) / stop_dist if stop_dist > 0 else 0.0
                    cash += direction * units * exit_fill - fees

                    trades.append(
                        {
                            "trade_id": len(trades),
                            "entry_date": _date(entry_idx),
                            "signal_date": _date(entry_signal_idx),
                            "exit_date": _date(i),
                            "direction": "long" if direction == 1 else "short",
                            "entry_price": float(entry_raw),
                            "exit_price": float(exit_raw),
                            "stop_price": float(stop_price),
                            "target_price": float(target_price),
                            "atr": float(entry_atr),
                            "risk_per_share": float(abs(entry_raw - stop_price)),
                            "exit_reason": exit_reason,
                            "units": float(units),
                            "pnl": float(pnl),
                            "fees": float(fees),
                            "return_pct": float(pnl / (units * entry_fill)) if units * entry_fill > 0 else 0.0,
                            "hold_days": bars_held,
                            "hold_bars": bars_held,
                            "r_multiple": float(r_multiple),
                        }
                    )
                    in_position = False
                    units = 0.0
                    entry_idx = -1
                    entry_signal_idx = -1
                    entry_atr = 0.0

            # 2) Execute a pending entry at this bar's open
            if not in_position and pending_signal_idx is not None:
                sig = pending_signal_idx
                pending_signal_idx = None
                a = atr[sig]
                if np.isfinite(a) and a > 0 and sizes[sig] > 0:
                    entry_units = float(sizes[sig])
                    entry_price_raw = float(open_[i])
                    fill = entry_price_raw * (1 + direction * slip)
                    cost = entry_units * fill
                    if cost <= cash:
                        units = entry_units
                        entry_idx = i
                        entry_signal_idx = sig
                        entry_raw = entry_price_raw
                        entry_fill = fill
                        entry_atr = float(a)
                        stop_price = entry_raw - direction * config.stop_atr_mult * a
                        target_price = entry_raw + direction * config.target_atr_mult * a
                        cash -= direction * units * entry_fill
                        in_position = True

            # 3) Record today's signal for tomorrow's open (never same bar)
            if entry_signals[i] and not in_position:
                pending_signal_idx = i

            equity[i] = cash + direction * units * close[i] if in_position else cash
            if in_position:
                bars_in_market += 1

        # ---- portfolio stats ----
        total_return = (equity[-1] / config.initial_cash) - 1.0 if config.initial_cash else 0.0
        cagr = 0.0
        if config.initial_cash and n_bars > 0 and equity[-1] > 0:
            years = n_bars / 252.0
            if years > 0:
                cagr = (equity[-1] / config.initial_cash) ** (1.0 / years) - 1.0

        sharpe = 0.0
        sortino = 0.0
        returns = pd.Series(equity).pct_change().dropna()
        if len(returns) > 1 and returns.std() > 0:
            sharpe = float(np.sqrt(252) * returns.mean() / returns.std())
        downside = returns[returns < 0]
        if len(downside) > 0 and downside.std() > 0:
            sortino = float(np.sqrt(252) * returns.mean() / downside.std())

        running_max = np.maximum.accumulate(equity)
        drawdown = np.divide(
            equity - running_max, running_max, out=np.zeros_like(equity), where=running_max > 0
        )
        max_dd = float(np.min(drawdown)) if n_bars else 0.0

        win_rate = profit_factor = expectancy = avg_win = avg_loss = 0.0
        total_trades = winning_trades = losing_trades = 0
        avg_hold_days = avg_hold_bars = 0.0
        expectancy_r = avg_win_r = avg_loss_r = 0.0
        max_consecutive_wins = max_consecutive_losses = 0
        exit_reason_counts: dict[str, int] = {}

        if trades:
            trades_df = pd.DataFrame(trades)
            pnls = trades_df["pnl"].to_numpy(dtype=float)
            r_multiples = trades_df["r_multiple"].to_numpy(dtype=float)
            winning = pnls[pnls > 0]
            losing = pnls[pnls < 0]
            wins_r = r_multiples[r_multiples > 0]
            losses_r = r_multiples[r_multiples < 0]

            total_trades = len(trades)
            winning_trades = int(len(winning))
            losing_trades = int(len(losing))
            win_rate = winning_trades / total_trades if total_trades else 0.0
            avg_win = float(np.mean(winning)) if len(winning) else 0.0
            avg_loss = float(np.mean(losing)) if len(losing) else 0.0
            gross_profit = float(np.sum(winning))
            gross_loss = float(abs(np.sum(losing)))
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0
            expectancy = float(np.mean(pnls))
            expectancy_r = float(np.mean(r_multiples))
            avg_win_r = float(np.mean(wins_r)) if len(wins_r) else 0.0
            avg_loss_r = float(np.mean(losses_r)) if len(losses_r) else 0.0

            pnl_signs = np.sign(pnls)
            max_consecutive_wins = self._max_consecutive(pnl_signs, 1)
            max_consecutive_losses = self._max_consecutive(pnl_signs, -1)
            avg_hold_days = float(np.mean([t["hold_days"] for t in trades]))
            avg_hold_bars = avg_hold_days
            for t in trades:
                exit_reason_counts[t["exit_reason"]] = exit_reason_counts.get(t["exit_reason"], 0) + 1

        equity_curve = [
            {"date": _date(i), "equity": float(equity[i])}
            for i in range(0, n_bars, max(1, n_bars // 200))
        ]

        return BacktestResult(
            symbol=config.symbol,
            timeframe=config.timeframe,
            start_date=_date(0),
            end_date=_date(n_bars - 1),
            initial_cash=config.initial_cash,
            final_equity=float(equity[-1]) if n_bars else float(config.initial_cash),
            total_return=total_return,
            annualized_return=cagr,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            max_drawdown=max_dd,
            max_drawdown_pct=max_dd * 100,
            win_rate=win_rate,
            profit_factor=profit_factor,
            expectancy=expectancy,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            avg_win=avg_win,
            avg_loss=avg_loss,
            avg_hold_days=avg_hold_days,
            max_consecutive_wins=max_consecutive_wins,
            max_consecutive_losses=max_consecutive_losses,
            trades=trades,
            equity_curve=equity_curve,
            expectancy_r=expectancy_r,
            avg_win_r=avg_win_r,
            avg_loss_r=avg_loss_r,
            avg_hold_bars=avg_hold_bars,
            exit_reason_counts=exit_reason_counts,
            time_in_market_pct=bars_in_market / n_bars if n_bars else 0.0,
        )

    @staticmethod
    def _max_consecutive(arr: np.ndarray, target: int) -> int:
        max_count = 0
        current = 0
        for v in arr:
            if v == target:
                current += 1
                max_count = max(max_count, current)
            else:
                current = 0
        return max_count


async def run_multi_backtest(
    symbols: list[str],
    screen_config: dict,
    timeframe: str = "1D",
    start_date: str = "",
    end_date: str = "",
    fetcher: Optional[object] = None,
) -> dict[str, BacktestResult]:
    from backend.app.infrastructure.data.fetcher import OHLCVFetcher
    
    fetcher_instance = fetcher or OHLCVFetcher()
    engine = ExternalBacktestEngine(fetcher=fetcher_instance)
    
    results = {}
    for symbol in symbols:
        config = BacktestConfig(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            signal_filters=screen_config.get("signal_filters", []),
            direction=screen_config.get("direction", "long"),
            stop_atr_mult=screen_config.get("stop_atr_mult", 2.0),
            target_atr_mult=screen_config.get("target_atr_mult", 3.0),
            max_hold_bars=screen_config.get("max_hold_bars"),
            signal_params=screen_config.get("signal_params", {}),
        )
        result = await engine.run_backtest(config)
        results[symbol] = result
    
    return results