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

        entries, exits = self._generate_signals(df, config)

        if entries is None or exits is None:
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
            )

        size_df = self._compute_position_sizes(df, entries, exits, config)

        result = self._run_simulation(df, entries, exits, size_df, config)

        self._log.info(
            f"Backtest complete for {config.symbol}: "
            f"{result.total_trades} trades, "
            f"Return: {result.total_return:.2%}, "
            f"Sharpe: {result.sharpe_ratio:.2f}"
        )

        return result

    def _generate_signals(
        self,
        df: pd.DataFrame,
        config: BacktestConfig,
    ) -> tuple[Optional[pd.Series], Optional[pd.Series]]:
        """Generate entry/exit signals by evaluating screen filters at each bar using pandas directly.
        
        Only uses technical indicators computable from OHLCV data.
        Fundamental filters (market_cap, eps, pe, etc.) are skipped since 
        Yahoo Finance OHLCV doesn't provide fundamental data.
        """
        # Fundamental filter names to skip - not available in Yahoo OHLCV
        FUNDAMENTAL_FILTERS = {
            'market_cap_gt', 'market_cap_lt', 'exchange_in', 'country_in',
            'eps_positive', 'pe_max', 'analyst_rating_in', 'dividend_yield_gt',
            'close_above', 'close_below', 'volume_gt', 'volume_lt',
            'avg_volume_gt', 'avg_volume_lt',
        }
        
        try:
            from backend.app.infrastructure.screener.configs import FilterRule
            
            # Filter out fundamental filters - only use technical ones available in Yahoo OHLCV
            filters = []
            for indicator, params in config.signal_params.items():
                if indicator in FUNDAMENTAL_FILTERS:
                    log.debug(f"Skipping fundamental filter: {indicator}")
                    continue
                filters.append(FilterRule(
                    category="technical",
                    indicator=indicator,
                    params=params,
                    operator="gt",
                    timeframe=config.timeframe,
                ))
            
            if not filters:
                log.warning(f"No technical filters available for {config.symbol}")
                return None, None
            
            # Compute indicators for the full dataframe
            df_with_indicators = self._compute_indicators(df)
            
            df_with_indicators = df_with_indicators.copy()
            df_with_indicators['symbol'] = config.symbol
            
            entries = pd.Series(False, index=df.index)
            exits = pd.Series(False, index=df.index)
            
            # Evaluate filters at each timestamp using pandas directly
            for i, timestamp in enumerate(df.index):
                snapshot = df_with_indicators[df_with_indicators.index <= timestamp].copy()
                if snapshot.empty:
                    continue
                
                latest_data = snapshot.groupby('symbol').last()
                if latest_data.empty:
                    continue
                
                # Rename columns to lowercase for consistency
                latest_data = latest_data.rename(columns={
                    'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close',
                    'Volume': 'volume', 'EMA20': 'EMA20', 'EMA50': 'EMA50', 'EMA200': 'EMA200',
                    'MACD.macd': 'MACD.macd', 'MACD.signal': 'MACD.signal', 'MACD.hist': 'MACD.hist',
                    'RSI': 'RSI', 'RSI2': 'RSI2', 'ADX': 'ADX', 'ATR': 'ATR',
                    'BB.upper': 'BB.upper', 'BB.middle': 'BB.middle', 'BB.lower': 'BB.lower',
                    'VWAP': 'VWAP', 'OBV': 'OBV', 'average_volume_10d_calc': 'average_volume_10d_calc',
                    'relative_volume_10d_calc': 'relative_volume_10d_calc',
                    'price_52_week_high': 'price_52_week_high', 'price_52_week_low': 'price_52_week_low',
                    'CCI20': 'CCI20', 'STOCH.K': 'STOCH.K', 'STOCH.D': 'STOCH.D',
                    'VWAP': 'VWAP', 'OBV': 'OBV', 'price': 'price', 'change': 'change',
                    'price_52_week_high': 'price_52_week_high', 'price_52_week_low': 'price_52_week_low',
                })
                
                # Evaluate filters using pandas directly (more robust than TV screener local eval)
                try:
                    mask = self._evaluate_filters_pandas(latest_data, filters)
                    if mask is not None:
                        matched = mask[mask].index.tolist()
                        for sym in matched:
                            if sym == config.symbol:
                                entries.iloc[i] = True
                except Exception as e:
                    log.warning(f"Filter eval failed at {timestamp}: {e}")
                    continue
            
            exits = entries.shift(-5).fillna(False)
            
            return entries, exits
            
        except Exception as e:
            log.error(f"Signal generation failed: {e}")
            return None, None
    
    def _evaluate_filters_pandas(
        self,
        latest_data: pd.DataFrame,
        filters: list,
    ) -> Optional[pd.Series]:
        """Evaluate filters using pandas operations directly (more robust than TV screener local eval)."""
        try:
            mask = pd.Series(True, index=latest_data.index)
            
            for f in filters:
                indicator = f.indicator
                params = f.params
                op = f.operator
                
                if indicator == 'price_above_ema':
                    period = params.get('period', 50)
                    col = f'EMA{period}'
                    if col in latest_data.columns:
                        mask &= (latest_data['close'] > latest_data[col])
                elif indicator == 'price_below_ema':
                    period = params.get('period', 50)
                    col = f'EMA{period}'
                    if col in latest_data.columns:
                        mask &= (latest_data['close'] < latest_data[col])
                elif indicator == 'price_above_vwap':
                    if 'VWAP' in latest_data.columns:
                        mask &= (latest_data['close'] > latest_data['VWAP'])
                elif indicator == 'price_below_vwap':
                    if 'VWAP' in latest_data.columns:
                        mask &= (latest_data['close'] < latest_data['VWAP'])
                elif indicator == 'ema_stack_bullish':
                    if all(c in latest_data.columns for c in ['EMA20', 'EMA50', 'EMA200']):
                        mask &= (latest_data['EMA20'] > latest_data['EMA50']) & (latest_data['EMA50'] > latest_data['EMA200'])
                elif indicator == 'ema_stack_bearish':
                    if all(c in latest_data.columns for c in ['EMA20', 'EMA50', 'EMA200']):
                        mask &= (latest_data['EMA20'] < latest_data['EMA50']) & (latest_data['EMA50'] < latest_data['EMA200'])
                elif indicator == 'rsi_oversold':
                    threshold = params.get('threshold', 30)
                    if 'RSI' in latest_data.columns:
                        mask &= (latest_data['RSI'] < threshold)
                elif indicator == 'rsi_overbought':
                    threshold = params.get('threshold', 70)
                    if 'RSI' in latest_data.columns:
                        mask &= (latest_data['RSI'] > threshold)
                elif indicator == 'rsi_gt':
                    threshold = params.get('threshold', 50)
                    if 'RSI' in latest_data.columns:
                        mask &= (latest_data['RSI'] > threshold)
                elif indicator == 'rsi_lt':
                    threshold = params.get('threshold', 50)
                    if 'RSI' in latest_data.columns:
                        mask &= (latest_data['RSI'] < threshold)
                elif indicator == 'rsi_in_range':
                    min_val = params.get('min', 40)
                    max_val = params.get('max', 80)
                    if 'RSI' in latest_data.columns:
                        mask &= (latest_data['RSI'] > min_val) & (latest_data['RSI'] < max_val)
                elif indicator == 'rsi_in_range_max':
                    min_val = params.get('min', 40)
                    max_val = params.get('max', 80)
                    if 'RSI' in latest_data.columns:
                        mask &= (latest_data['RSI'] > min_val) & (latest_data['RSI'] < max_val)
                elif indicator == 'macd_bullish':
                    if all(c in latest_data.columns for c in ['MACD.macd', 'MACD.signal']):
                        mask &= (latest_data['MACD.macd'] > latest_data['MACD.signal'])
                elif indicator == 'macd_bearish':
                    if all(c in latest_data.columns for c in ['MACD.macd', 'MACD.signal']):
                        mask &= (latest_data['MACD.macd'] < latest_data['MACD.signal'])
                elif indicator == 'macd_cross_above':
                    if all(c in latest_data.columns for c in ['MACD.macd', 'MACD.signal']):
                        macd = latest_data['MACD.macd']
                        signal = latest_data['MACD.signal']
                        mask &= (macd > signal) & (macd.shift(1) <= signal.shift(1))
                elif indicator == 'macd_cross_below':
                    if all(c in latest_data.columns for c in ['MACD.macd', 'MACD.signal']):
                        macd = latest_data['MACD.macd']
                        signal = latest_data['MACD.signal']
                        mask &= (macd < signal) & (macd.shift(1) >= signal.shift(1))
                elif indicator == 'macd_hist_rising':
                    if 'MACD.hist' in latest_data.columns:
                        mask &= (latest_data['MACD.hist'] > 0)
                elif indicator == 'adx_trending':
                    threshold = params.get('threshold', 25)
                    if 'ADX' in latest_data.columns:
                        mask &= (latest_data['ADX'] > threshold)
                elif indicator == 'bb_squeeze':
                    threshold = params.get('threshold', 1.10)
                    if all(c in latest_data.columns for c in ['BB.upper', 'BB.lower']):
                        mask &= (latest_data['BB.upper'] / latest_data['BB.lower'] < threshold)
                elif indicator == 'bb_squeeze_tight':
                    threshold = params.get('threshold', 1.05)
                    if all(c in latest_data.columns for c in ['BB.upper', 'BB.lower']):
                        mask &= (latest_data['BB.upper'] / latest_data['BB.lower'] < threshold)
                elif indicator == 'atr_pct_below':
                    threshold = params.get('threshold', 0.03)
                    if 'ATR' in latest_data.columns:
                        mask &= (latest_data['ATR'] / latest_data['close'] < threshold)
                elif indicator == 'rvol_high':
                    threshold = params.get('threshold', 1.5)
                    if 'relative_volume_10d_calc' in latest_data.columns:
                        mask &= (latest_data['relative_volume_10d_calc'] > threshold)
                elif indicator == 'rvol_low':
                    threshold = params.get('threshold', 0.7)
                    if 'relative_volume_10d_calc' in latest_data.columns:
                        mask &= (latest_data['relative_volume_10d_calc'] < threshold)
                elif indicator == 'avg_volume_gt':
                    threshold = params.get('threshold', 500000)
                    if 'average_volume_10d_calc' in latest_data.columns:
                        mask &= (latest_data['average_volume_10d_calc'] > threshold)
                elif indicator == 'price_above_ema':
                    period = params.get('period', 50)
                    col = f'EMA{period}'
                    if col in latest_data.columns:
                        mask &= (latest_data['close'] > latest_data[col])
                elif indicator == 'price_below_ema':
                    period = params.get('period', 50)
                    col = f'EMA{period}'
                    if col in latest_data.columns:
                        mask &= (latest_data['close'] < latest_data[col])
                elif indicator == 'price_above_vwap':
                    if 'VWAP' in latest_data.columns:
                        mask &= (latest_data['close'] > latest_data['VWAP'])
                elif indicator == 'price_below_vwap':
                    if 'VWAP' in latest_data.columns:
                        mask &= (latest_data['close'] < latest_data['VWAP'])
                elif indicator == 'price_near_52w_high':
                    pct = params.get('pct_within', 5) / 100
                    if 'price_52_week_high' in latest_data.columns:
                        mask &= (latest_data['close'] > latest_data['price_52_week_high'] * (1 - pct))
                elif indicator == 'price_above_52w_low':
                    pct = params.get('pct_above', 30) / 100
                    if 'price_52_week_low' in latest_data.columns:
                        mask &= (latest_data['close'] > latest_data['price_52_week_low'] * (1 + pct))
                elif indicator == 'price_near_ema':
                    period = params.get('period', 20)
                    pct = params.get('pct_within', 2) / 100
                    col = f'EMA{period}'
                    if col in latest_data.columns:
                        mask &= (latest_data['close'] > latest_data[col] * (1 - pct)) & \
                                (latest_data['close'] < latest_data[col] * (1 + pct))
                elif indicator == 'obv_rising':
                    min_rvol = params.get('min_rvol', 1.0)
                    if all(c in latest_data.columns for c in ['close', 'SMA20', 'relative_volume_10d_calc']):
                        mask &= (latest_data['close'] > latest_data['SMA20']) & \
                                (latest_data['relative_volume_10d_calc'] > min_rvol)
                elif indicator == 'obv_falling':
                    min_rvol = params.get('min_rvol', 1.0)
                    if all(c in latest_data.columns for c in ['close', 'SMA20', 'relative_volume_10d_calc']):
                        mask &= (latest_data['close'] < latest_data['SMA20']) & \
                                (latest_data['relative_volume_10d_calc'] > min_rvol)
                elif indicator == 'volume_spike':
                    threshold = params.get('threshold', 2.0)
                    if 'relative_volume_10d_calc' in latest_data.columns:
                        mask &= (latest_data['relative_volume_10d_calc'] > threshold)
                elif indicator == 'price_above_vwap':
                    if 'VWAP' in latest_data.columns:
                        mask &= (latest_data['close'] > latest_data['VWAP'])
                elif indicator == 'price_below_vwap':
                    if 'VWAP' in latest_data.columns:
                        mask &= (latest_data['close'] < latest_data['VWAP'])
                elif indicator == 'price_above_bb_upper':
                    if 'BB.upper' in latest_data.columns:
                        mask &= (latest_data['close'] > latest_data['BB.upper'])
                elif indicator == 'price_below_bb_lower':
                    if 'BB.lower' in latest_data.columns:
                        mask &= (latest_data['close'] < latest_data['BB.lower'])
                elif indicator == 'rsi_in_range':
                    min_val = params.get('min', 40)
                    max_val = params.get('max', 80)
                    if 'RSI' in latest_data.columns:
                        mask &= (latest_data['RSI'] > min_val) & (latest_data['RSI'] < max_val)
                elif indicator == 'rsi_in_range_max':
                    min_val = params.get('min', 40)
                    max_val = params.get('max', 80)
                    if 'RSI' in latest_data.columns:
                        mask &= (latest_data['RSI'] > min_val) & (latest_data['RSI'] < max_val)
                elif indicator == 'macd_bullish':
                    if all(c in latest_data.columns for c in ['MACD.macd', 'MACD.signal']):
                        mask &= (latest_data['MACD.macd'] > latest_data['MACD.signal'])
                elif indicator == 'macd_bearish':
                    if all(c in latest_data.columns for c in ['MACD.macd', 'MACD.signal']):
                        mask &= (latest_data['MACD.macd'] < latest_data['MACD.signal'])
                elif indicator == 'macd_cross_above':
                    if all(c in latest_data.columns for c in ['MACD.macd', 'MACD.signal']):
                        macd = latest_data['MACD.macd']
                        signal = latest_data['MACD.signal']
                        mask &= (macd > signal) & (macd.shift(1) <= signal.shift(1))
                elif indicator == 'macd_cross_below':
                    if all(c in latest_data.columns for c in ['MACD.macd', 'MACD.signal']):
                        macd = latest_data['MACD.macd']
                        signal = latest_data['MACD.signal']
                        mask &= (macd < signal) & (macd.shift(1) >= signal.shift(1))
                elif indicator == 'macd_hist_rising':
                    if 'MACD.hist' in latest_data.columns:
                        mask &= (latest_data['MACD.hist'] > 0)
                elif indicator == 'adx_rising':
                    threshold = params.get('threshold', 25)
                    if 'ADX' in latest_data.columns:
                        mask &= (latest_data['ADX'] > threshold)
                elif indicator == 'inside_bar':
                    max_atr_pct = params.get('max_atr_pct', 0.03)
                    if 'ATR' in latest_data.columns:
                        mask &= (latest_data['ATR'] / latest_data['close'] < max_atr_pct)
                elif indicator == 'rs_rank_min':
                    threshold = params.get('value', 90)
                    if 'relative_strength_rank' in latest_data.columns:
                        mask &= (latest_data['relative_strength_rank'] >= threshold)
                elif indicator == 'rsi_macd_bullish':
                    if all(c in latest_data.columns for c in ['RSI', 'MACD.macd', 'MACD.signal']):
                        mask &= (latest_data['RSI'] > 50) & (latest_data['MACD.macd'] > latest_data['MACD.signal'])
                elif indicator == 'cci_oversold':
                    threshold = params.get('threshold', -100)
                    if 'CCI20' in latest_data.columns:
                        mask &= (latest_data['CCI20'] < threshold)
                else:
                    log.debug(f"Unknown filter indicator: {indicator}")
                    continue
            
            return mask
        except Exception as e:
            log.warning(f"Pandas filter evaluation failed: {e}")
            return None

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
        
        for period in [20, 50, 200]:
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
            result['BB.middle'] = bb.iloc[:, 1]
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
            result['STOCH.K'] = stoch.iloc[:, 0]
            result['STOCH.D'] = stoch.iloc[:, 1]
        
        result['SMA20'] = ta.sma(close, length=20)
        
        return result

    def _compute_position_sizes(
        self,
        df: pd.DataFrame,
        entries: pd.Series,
        exits: pd.Series,
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
        exits: pd.Series,
        size_df: pd.DataFrame,
        config: BacktestConfig,
    ) -> BacktestResult:
        """Run the backtest simulation."""
        n_bars = len(df)
        symbols = [config.symbol]
        
        cash = float(config.initial_cash)
        positions = {config.symbol: 0.0}
        entry_prices = {config.symbol: 0.0}
        entry_indices = {config.symbol: -1}
        
        equity = np.zeros(n_bars)
        trades = []
        trade_id = 0
        
        fees = config.fees_bps / 10000.0
        slippage = config.slippage_bps / 10000.0
        
        for i in range(n_bars):
            date = df.index[i]
            close_price = df['Close'].iloc[i]
            high_price = df['High'].iloc[i]
            low_price = df['Low'].iloc[i]
            
            # Process exits first
            if exits.iloc[i] and positions[config.symbol] > 0:
                entry_price = entry_prices[config.symbol]
                units = positions[config.symbol]
                
                exit_price = close_price * (1 - slippage)
                entry_price_adj = entry_price * (1 + slippage)
                
                gross_pnl = units * (exit_price - entry_price_adj)
                trade_value = units * exit_price
                total_fees = trade_value * fees * 2
                net_pnl = gross_pnl - total_fees
                
                trades.append({
                    'trade_id': trade_id,
                    'entry_date': str(df.index[entry_indices[config.symbol]].date()),
                    'exit_date': str(date.date()),
                    'entry_price': float(entry_price),
                    'exit_price': float(exit_price),
                    'units': float(units),
                    'pnl': float(net_pnl),
                    'fees': float(total_fees),
                    'return_pct': float(net_pnl / (units * entry_price_adj)),
                    'hold_days': i - entry_indices[config.symbol],
                })
                trade_id += 1
                
                cash += units * exit_price - total_fees
                positions[config.symbol] = 0.0
                entry_prices[config.symbol] = 0.0
                entry_indices[config.symbol] = -1
            
            # Process entries
            if entries.iloc[i] and positions[config.symbol] == 0:
                size_units = size_df['size'].iloc[i]
                if size_units > 0:
                    entry_price = close_price * (1 + slippage)
                    cost = size_units * entry_price
                    
                    if cost <= cash:
                        positions[config.symbol] = size_units
                        entry_prices[config.symbol] = close_price
                        entry_indices[config.symbol] = i
                        cash -= cost
            
            # Compute equity
            position_value = positions[config.symbol] * close_price
            equity[i] = cash + position_value
        
        total_return = 0
        annualized_return = 0
        sharpe = 0
        sortino = 0
        max_drawdown = 0
        max_drawdown_pct = 0
        win_rate = 0
        profit_factor = 0
        expectancy = 0
        total_trades = 0
        winning_trades = 0
        losing_trades = 0
        avg_win = 0
        avg_loss = 0
        avg_hold_days = 0
        max_consecutive_wins = 0
        max_consecutive_losses = 0
        equity_curve = []
        cagr = 0
        
        if trades:
            trades_df = pd.DataFrame(trades)
            pnls = trades_df['pnl'].values
            winning = pnls[pnls > 0]
            losing = pnls[pnls < 0]
            
            total_return = (equity[-1] / config.initial_cash) - 1.0
            returns = pd.Series(equity).pct_change().dropna()
            
            sharpe = 0
            if returns.std() > 0:
                sharpe = np.sqrt(252) * returns.mean() / returns.std()
            
            sortino = 0
            downside = returns[returns < 0]
            if len(downside) > 0 and downside.std() > 0:
                sortino = np.sqrt(252) * returns.mean() / downside.std()
            
            running_max = np.maximum.accumulate(equity)
            drawdown = (equity - running_max) / running_max
            max_dd = float(np.min(drawdown))
            max_drawdown = max_dd
            max_drawdown_pct = max_dd * 100
            
            cagr = (equity[-1] / config.initial_cash) ** (252 / len(equity)) - 1
            
            total_trades = len(trades)
            winning_trades = len(winning)
            losing_trades = len(losing)
            win_rate = winning_trades / total_trades if total_trades > 0 else 0
            
            avg_win = float(np.mean(winning)) if len(winning) > 0 else 0
            avg_loss = float(np.mean(losing)) if len(losing) > 0 else 0
            
            gross_profit = float(np.sum(winning))
            gross_loss = float(abs(np.sum(losing)))
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
            
            expectancy = win_rate * avg_win - (1 - win_rate) * avg_loss
            
            pnl_signs = np.sign(pnls)
            max_consecutive_wins = self._max_consecutive(pnl_signs, 1)
            max_consecutive_losses = self._max_consecutive(pnl_signs, -1)
            
            avg_hold_days = float(np.mean([t['hold_days'] for t in trades]))
            
            equity_curve = [
                {'date': str(df.index[i].date()), 'equity': float(equity[i])}
                for i in range(0, n_bars, max(1, n_bars // 200))
            ]
            
            cagr = (equity[-1] / config.initial_cash) ** (252 / len(equity)) - 1
        
        max_drawdown_pct = max_drawdown * 100
        
        return BacktestResult(
            symbol=config.symbol,
            timeframe="1D",
            start_date=str(df.index[0].date()),
            end_date=str(df.index[-1].date()),
            initial_cash=config.initial_cash,
            final_equity=equity[-1],
            total_return=total_return,
            annualized_return=cagr,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            max_drawdown=max_drawdown,
            max_drawdown_pct=max_drawdown_pct,
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
        )
        result = await engine.run_backtest(config)
        results[symbol] = result
    
    return results