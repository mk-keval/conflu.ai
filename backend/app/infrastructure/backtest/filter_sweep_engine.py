"""Filter Sweep Engine — runs grid search over filter parameter combinations.

This engine takes a screen configuration and parameter grid, generates
all parameter combinations, runs backtests for each combination,
and returns ranked results by the specified optimization metric.
"""

from __future__ import annotations

import asyncio
import hashlib
import itertools
import json
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

import numpy as np
import pandas as pd

from backend.app.core.logging import get_logger
from backend.app.domain.models import Metrics
from backend.app.infrastructure.backtest.lightweight_engine import LightweightBacktestEngine
from backend.app.infrastructure.backtest.filter_sweep import (
    FilterParamRange,
    FilterSweepConfig,
    FilterSweepResult,
    FilterSweepSummary,
)
from backend.app.infrastructure.backtest.models import BacktestRunConfig
from backend.app.infrastructure.screener.configs import ScreenConfig, load_screen_template

log = get_logger("conflu.backtest.filter_sweep")


# ── Indicator computation helpers ─────────────────────────────────────────────

def _compute_indicators_for_snapshot(df: pd.DataFrame) -> pd.DataFrame:
    """Compute technical indicators required by TV screener filters from OHLCV data.
    
    Args:
        df: DataFrame with OHLCV data, index=timestamp, columns include symbol, open, high, low, close, volume
        
    Returns:
        DataFrame with additional indicator columns
    """
    try:
        import pandas_ta as ta
    except ImportError:
        log.warning("pandas_ta not available, skipping indicator computation")
        return df
    
    result = df.copy()
    
    # Compute indicators per symbol
    for symbol in result['symbol'].unique():
        mask = result['symbol'] == symbol
        sym_data = result.loc[mask].copy()
        
        if len(sym_data) < 200:  # Need enough data for EMA200
            continue
        
        close = sym_data['close']
        high = sym_data['high']
        low = sym_data['low']
        volume = sym_data['volume']
        
        # EMA indicators - compute a wide range for price_above_ema filter
        for period in [20, 30, 40, 50, 60, 80, 100, 120, 140, 150, 160, 180, 200]:
            result.loc[mask, f'EMA{period}'] = ta.ema(close, length=period)
        
        # MACD
        macd = ta.macd(close, fast=12, slow=26, signal=9)
        if macd is not None:
            result.loc[mask, 'MACD.macd'] = macd.iloc[:, 0]  # MACD line
            result.loc[mask, 'MACD.signal'] = macd.iloc[:, 1]  # Signal line
            result.loc[mask, 'MACD.hist'] = macd.iloc[:, 2]  # Histogram
        
        # RSI
        result.loc[mask, 'RSI'] = ta.rsi(close, length=14)
        
        # ADX
        adx = ta.adx(high, low, close, length=14)
        if adx is not None:
            result.loc[mask, 'ADX'] = adx.iloc[:, 0]  # ADX line
        
        # ATR
        result.loc[mask, 'ATR'] = ta.atr(high, low, close, length=14)
        
        # Bollinger Bands
        bb = ta.bbands(close, length=20, std=2)
        if bb is not None:
            result.loc[mask, 'BB.upper'] = bb.iloc[:, 0]  # Upper band
            result.loc[mask, 'BB.basis'] = bb.iloc[:, 1]  # Basis (middle) band
            result.loc[mask, 'BB.lower'] = bb.iloc[:, 2]  # Lower band
        
        # VWAP (Volume Weighted Average Price)
        # VWAP = cumulative(volume * price) / cumulative(volume)
        typical_price = (high + low + close) / 3
        vwap = (typical_price * volume).cumsum() / volume.cumsum()
        result.loc[mask, 'VWAP'] = vwap
        
        # OBV (On Balance Volume)
        obv = ta.obv(close, volume)
        if obv is not None:
            result.loc[mask, 'OBV'] = obv
        
        # Stochastic
        stoch = ta.stoch(high, low, close, k=14, d=3)
        if stoch is not None:
            result.loc[mask, 'Stoch.K'] = stoch.iloc[:, 0]
            result.loc[mask, 'Stoch.D'] = stoch.iloc[:, 1]
        
        # CCI
        result.loc[mask, 'CCI20'] = ta.cci(high, low, close, length=20)
        
        # Average volume 10d
        result.loc[mask, 'average_volume_10d_calc'] = volume.rolling(10).mean()
        
        # Relative volume 10d (current volume / 10d avg volume)
        avg_vol_10d = volume.rolling(10).mean()
        result.loc[mask, 'relative_volume_10d_calc'] = volume / avg_vol_10d
        
        # Volume change
        result.loc[mask, 'volume_change'] = volume.pct_change()
        
        # 52-week high
        result.loc[mask, 'price_52_week_high'] = close.rolling(252).max()
        
        # Performance columns
        result.loc[mask, 'Perf.1M'] = close.pct_change(21) * 100
        result.loc[mask, 'Perf.3M'] = close.pct_change(63) * 100
        
        # Price (alias for close)
        result.loc[mask, 'price'] = close
        
        # Change (daily %)
        result.loc[mask, 'change'] = close.pct_change() * 100
        
    return result


@dataclass
class SweepProgress:
    """Progress tracking for a running sweep."""
    sweep_id: str
    total_combinations: int
    completed: int = 0
    failed: int = 0
    current_params: dict[str, Any] | None = None
    start_time: float = 0.0
    status: Literal["running", "completed", "failed"] = "running"


class FilterSweepEngine:
    """Runs grid search over filter parameter combinations to find optimal filter settings."""

    def __init__(self) -> None:
        self._engine = LightweightBacktestEngine()
        self._log = get_logger("conflu.backtest.filter_sweep")
        self._active_sweeps: dict[str, SweepProgress] = {}

    async def run_sweep(
        self,
        config: FilterSweepConfig,
        progress_callback: callable | None = None,
    ) -> FilterSweepSummary:
        """Run a complete filter parameter sweep.

        Args:
            config: Filter sweep configuration with parameter grid.
            progress_callback: Optional callback for progress updates.

        Returns:
            FilterSweepSummary with all results ranked by optimization metric.
        """
        sweep_id = config.sweep_id
        start_time = time.monotonic()

        # Initialize progress tracking
        progress = SweepProgress(sweep_id=config.sweep_id, total_combinations=0, start_time=start_time)
        self._active_sweeps[config.sweep_id] = progress

        try:
            # Load screen template
            screen_config = load_screen_template(config.screen_name)

            # Generate parameter combinations
            param_combos = self._generate_param_combinations(config)
            total_combinations = len(param_combos)

            if total_combinations > config.max_combinations:
                self._log.warning(
                    "sweep_combinations_exceed_limit",
                    sweep_id=config.sweep_id,
                    total=total_combinations,
                    max=config.max_combinations,
                )
                # Truncate to max_combinations (random sample)
                import random
                param_combos = random.sample(param_combos, config.max_combinations)

            progress.total_combinations = len(param_combos)
            self._log.info(
                "filter_sweep_started",
                sweep_id=config.sweep_id,
                screen=config.screen_name,
                combinations=len(param_combos),
                symbols=config.symbols,
                metric=config.optimization_metric,
            )

            # Run backtests for each combination
            results = []
            for i, params in enumerate(param_combos):
                progress.completed = i
                progress.current_params = params

                if progress_callback:
                    progress_callback(progress)

                try:
                    result = await self._run_single_backtest(
                        config=config,
                        screen_config=screen_config,
                        params=params,
                    )
                    results.append(result)
                except Exception as e:
                    self._log.warning(
                        "filter_sweep_combo_failed",
                        sweep_id=config.sweep_id,
                        params=params,
                        error=str(e),
                    )
                    progress.failed += 1
                    # Add failed result
                    results.append(FilterSweepResult(
                        params=params,
                        valid=False,
                        error_message=str(e),
                        run_id=str(uuid4()),
                    ))

            # Build summary
            summary = self._build_summary(
                sweep_id=config.sweep_id,
                config=config,
                results=results,
                duration_ms=(time.monotonic() - start_time) * 1000,
            )

            progress.status = "completed"
            progress.completed = len(param_combos)

            if progress_callback:
                progress_callback(progress)

            self._log.info(
                "filter_sweep_completed",
                sweep_id=config.sweep_id,
                total=len(param_combos),
                valid=summary.valid_results,
                failed=summary.failed_results,
                duration_ms=summary.duration_ms,
            )

            return summary

        except Exception as e:
            progress.status = "failed"
            self._log.exception("filter_sweep_failed", sweep_id=config.sweep_id, error=str(e))
            return FilterSweepSummary(
                sweep_id=config.sweep_id,
                name=config.name,
                screen_name=config.screen_name,
                total_combinations=0,
                valid_results=0,
                failed_results=0,
                status="failed",
                error_message=str(e),
                duration_ms=(time.monotonic() - start_time) * 1000,
            )
        finally:
            # Clean up
            if config.sweep_id in self._active_sweeps:
                del self._active_sweeps[config.sweep_id]

    def get_progress(self, sweep_id: str) -> SweepProgress | None:
        """Get current progress for a sweep."""
        return self._active_sweeps.get(sweep_id)

    def _generate_param_combinations(self, config: FilterSweepConfig) -> list[dict[str, Any]]:
        """Generate all parameter combinations from the grid."""
        param_ranges = config.param_grid

        # For each parameter, generate the list of values
        param_values: dict[str, list[Any]] = {}
        for name, range_def in param_ranges.items():
            param_values[name] = self._expand_param_range(range_def)

        # Generate all combinations
        keys = list(param_values.keys())
        values = list(param_values.values())

        if not keys:
            return [{}]

        combinations = list(itertools.product(*values))
        return [dict(zip(keys, combo)) for combo in combinations]

    def _expand_param_range(self, range_def: FilterParamRange) -> list[Any]:
        """Expand a parameter range into a list of values."""
        if range_def.param_type == "categorical":
            return range_def.choices or []

        values = []
        low = range_def.low
        high = range_def.high
        step = range_def.step or 1

        if range_def.param_type == "int":
            current = low
            while current <= high:
                values.append(int(current))
                current += step
        else:  # float
            current = low
            while current <= high + 1e-9:  # Floating point tolerance
                values.append(round(current, 4))
                current += step

        return values

    async def _run_single_backtest(
        self,
        config: FilterSweepConfig,
        screen_config: ScreenConfig,
        params: dict[str, Any],
    ) -> FilterSweepResult:
        """Run a single backtest with the given filter parameters."""
        # Apply parameters to screen config
        modified_config = self._apply_params_to_screen(screen_config, params)

        # Load OHLCV data
        ohlcv = await self._load_ohlcv_for_sweep(config)

        if ohlcv is None or ohlcv.empty:
            self._log.warning("no_ohlcv_data_for_sweep", sweep_id=config.sweep_id, symbols=config.symbols)
            return FilterSweepResult(
                params=params,
                valid=False,
                error_message="No OHLCV data available",
                run_id=str(uuid4()),
            )

        # Build entry/exit signals from screen config
        close, entries, exits = await self._build_signals_from_screen(
            modified_config, config.symbols, config.timeframe, config.start_date, config.end_date
        )

        if close is None or entries is None or exits is None:
            return FilterSweepResult(
                params=params,
                valid=False,
                error_message="Failed to build signals",
                run_id=str(uuid4()),
            )

        # Also load high/low for proper trade ledger (MAE/MFE calculation)
        high, low = await self._load_high_low_for_sweep(config)

        # Compute position sizes
        size_df = self._engine._sizer.compute_position_size(
            close=close,
            entries=entries,
            method=config.position_sizing,
            initial_cash=config.initial_cash,
            params=config.sizing_params,
            atr_series=None,  # TODO: compute ATR if needed
        )

        # Run lightweight backtest
        loop = asyncio.get_running_loop()
        try:
            equity_df, stats, trades = await loop.run_in_executor(
                None,
                self._engine.run,
                close, entries, exits, size_df,
                config.initial_cash,
                config.fees_bps / 10000,  # Convert bps to decimal
                config.slippage_bps / 10000,
                self._infer_freq(close.index),
                high, low,  # Pass high/low for proper MAE/MFE
            )
        except Exception as e:
            # Print full traceback to stdout for debugging
            import traceback
            print(f"\n=== BACKTEST ERROR ===")
            print(f"Params: {params}")
            traceback.print_exc()
            print(f"=== END ERROR ===\n")
            self._log.warning("lightweight_backtest_failed", params=params, error=str(e))
            raise

        # Calculate expectancy from stats
        expectancy = None
        win_rate = stats.get("win_rate", 0) or 0
        avg_win = stats.get("avg_win", 0) or 0
        avg_loss = stats.get("avg_loss", 0) or 0
        expectancy = (win_rate * avg_win) - ((1 - win_rate) * abs(avg_loss))

        # Check validity
        valid = (stats.get("total_trades", 0) or 0) >= 10

        # Build config hash
        config_hash = self._compute_config_hash_for_sweep(config, params)

        return FilterSweepResult(
            params=params,
            total_return=stats.get("total_return"),
            annualized_return=stats.get("cagr"),
            sharpe=stats.get("sharpe_ratio"),
            sortino=stats.get("sortino_ratio"),
            calmar=stats.get("calmar_ratio"),
            max_drawdown=stats.get("max_drawdown"),
            win_rate=stats.get("win_rate"),
            profit_factor=stats.get("profit_factor"),
            expectancy=expectancy,
            avg_win=stats.get("avg_win"),
            avg_loss=stats.get("avg_loss"),
            total_trades=int(stats.get("total_trades", 0)),
            winning_trades=int(stats.get("winning_trades", 0)),
            losing_trades=int(stats.get("losing_trades", 0)),
            max_consecutive_wins=int(stats.get("max_consecutive_wins", 0)),
            max_consecutive_losses=int(stats.get("max_consecutive_losses", 0)),
            max_drawdown_pct=stats.get("max_drawdown"),
            recovery_factor=None,
            payoff_ratio=None,
            avg_hold_days=stats.get("avg_hold_days"),
            best_trade=stats.get("best_trade"),
            worst_trade=stats.get("worst_trade"),
            run_id=str(uuid4()),
            config_hash=config_hash,
            valid=valid,
            duration_ms=0.0,  # TODO: track per-combo duration
        )

    def _apply_params_to_screen(self, screen_config: ScreenConfig, params: dict[str, Any]) -> ScreenConfig:
        """Apply parameter overrides to a screen config."""
        import copy
        new_config = copy.deepcopy(screen_config)

        # Map sweep parameter names to filter indicator parameter keys
        PARAM_TO_FILTER_PARAM = {
            "market_cap_gt": "value",
            "avg_volume_gt": "threshold",
            "rvol_high": "threshold",
            "close_above": "threshold",
            "pe_max": "max_pe",
            "adx_trending": "threshold",
            "rsi_in_range": "min",
            "rsi_in_range_max": "max",
            "rsi_oversold": "threshold",
            "cci_oversold": "threshold",
            "atr_pct_below": "threshold",
            "price_above_ema": "period",
            "bb_squeeze": "threshold",
            "volume_gt": "threshold",
        }

        # Apply each parameter to the appropriate filter
        for filter_obj in new_config.filters:
            indicator = filter_obj.indicator
            if indicator in params:
                param_value = params[indicator]
                filter_param_key = PARAM_TO_FILTER_PARAM.get(indicator)
                if filter_param_key:
                    filter_obj.params[filter_param_key] = param_value
                else:
                    # Fallback: use the indicator name as key
                    filter_obj.params[indicator] = param_value

        return new_config

    async def _load_ohlcv_for_sweep(self, config: FilterSweepConfig) -> pd.DataFrame | None:
        """Load OHLCV data from DuckDB for the configured symbols and date range."""
        try:
            from backend.app.core.database import get_db
            placeholders = ",".join("?" * len(config.symbols))
            with get_db(read_only=True) as con:
                result = con.sql(
                    f"""
                    SELECT symbol, timestamp, open, high, low, close, volume
                    FROM ohlcv
                    WHERE symbol IN ({placeholders})
                      AND timeframe = ?
                      AND timestamp >= ?
                      AND timestamp <= ?
                    ORDER BY symbol, timestamp
                    """,
                    params=[
                        *config.symbols,
                        config.timeframe,
                        config.start_date,
                        config.end_date or datetime.now().strftime("%Y-%m-%d"),
                    ],
                ).fetchdf()

                if result.empty:
                    return None

                result.set_index("timestamp", inplace=True)
                result.index = pd.DatetimeIndex(result.index)
                return result
        except Exception:
            self._log.exception("ohlcv_load_failed_for_sweep", symbols=config.symbols)
            return None

    async def _load_ohlcv_for_sweep(self, config: FilterSweepConfig) -> pd.DataFrame | None:
        """Load OHLCV data from DuckDB for the configured symbols and date range."""
        try:
            from backend.app.core.database import get_db
            placeholders = ",".join("?" * len(config.symbols))
            with get_db(read_only=True) as con:
                result = con.sql(
                    f"""
                    SELECT symbol, timestamp, open, high, low, close, volume
                    FROM ohlcv
                    WHERE symbol IN ({placeholders})
                      AND timeframe = ?
                      AND timestamp >= ?
                      AND timestamp <= ?
                    ORDER BY symbol, timestamp
                    """,
                    params=[
                        *config.symbols,
                        config.timeframe,
                        config.start_date,
                        config.end_date or datetime.now().strftime("%Y-%m-%d"),
                    ],
                ).fetchdf()

                if result.empty:
                    return None

                result.set_index("timestamp", inplace=True)
                result.index = pd.DatetimeIndex(result.index)
                return result
        except Exception:
            self._log.exception("ohlcv_load_failed_for_sweep", symbols=config.symbols)
            return None

    async def _load_high_low_for_sweep(self, config: FilterSweepConfig) -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
        """Load high/low price data from DuckDB for the configured symbols and date range.
        
        Returns:
            Tuple of (high DataFrame, low DataFrame) with symbols as columns and timestamps as index,
            or (None, None) if data unavailable.
        """
        try:
            from backend.app.core.database import get_db
            placeholders = ",".join("?" * len(config.symbols))
            with get_db(read_only=True) as con:
                result = con.sql(
                    f"""
                    SELECT symbol, timestamp, high, low
                    FROM ohlcv
                    WHERE symbol IN ({placeholders})
                      AND timeframe = ?
                      AND timestamp >= ?
                      AND timestamp <= ?
                    ORDER BY symbol, timestamp
                    """,
                    params=[
                        *config.symbols,
                        config.timeframe,
                        config.start_date,
                        config.end_date or datetime.now().strftime("%Y-%m-%d"),
                    ],
                ).fetchdf()

                if result.empty:
                    return None, None

                result.set_index("timestamp", inplace=True)
                result.index = pd.DatetimeIndex(result.index)
                
                # Pivot to get symbols as columns
                high_pivot = result.pivot(columns='symbol', values='high')
                low_pivot = result.pivot(columns='symbol', values='low')
                
                return high_pivot, low_pivot
        except Exception:
            self._log.exception("high_low_load_failed_for_sweep", symbols=config.symbols)
            return None, None

    async def _build_signals_from_screen(
        self,
        screen_config: ScreenConfig,
        symbols: list[str],
        timeframe: str,
        start_date: str,
        end_date: str | None,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame] | tuple[None, None, None]:
        """Build entry/exit signals by evaluating screen filters over historical OHLCV data.
        
        Note: Filters out fundamental filters since we don't have fundamental data in OHLCV.
        Only technical filters (volume, trend, momentum, volatility) are evaluated.
        """
        try:
            from backend.app.infrastructure.screener.tv_specialist import TVScreenerSpecialist
            specialist = TVScreenerSpecialist()
            
            # Filter out fundamental filters - we only have OHLCV data
            technical_filters = [
                f for f in screen_config.filters 
                if f.category != 'fundamental'
            ]
            
            if not technical_filters:
                self._log.warning("no_technical_filters_in_screen", screen=screen_config.name)
                return None, None, None
            
            # Load OHLCV data for all symbols
            ohlcv = await self._load_ohlcv_for_sweep(
                FilterSweepConfig(
                    name="signal_build",
                    screen_name=screen_config.name,
                    symbols=symbols,
                    timeframe=timeframe,
                    start_date="2025-07-01",
                    end_date="2026-06-01",
                )
            )
            
            if ohlcv is None or ohlcv.empty:
                return None, None, None
            
            # Compute indicators on full OHLCV history first
            ohlcv_with_indicators = _compute_indicators_for_snapshot(ohlcv)
            
            # Get unique timestamps and symbols from OHLCV
            # ohlcv has columns: symbol, timestamp, open, high, low, close, volume
            # Pivot to wide format for vectorized operations
            ohlcv_pivot = ohlcv_with_indicators.reset_index().pivot_table(
                index='timestamp', 
                columns='symbol', 
                values=['open', 'high', 'low', 'close', 'volume']
            )
            
            # Extract close prices - columns are MultiIndex with (field, symbol)
            # Use xs to extract the 'close' level from the column MultiIndex
            close = ohlcv_pivot.xs('close', level=0, axis=1)
            
            # Evaluate filters for each timestamp using TVScreenerSpecialist local evaluation
            # We need to evaluate filters at each timestamp to generate entry/exit signals
            entries = pd.DataFrame(False, index=close.index, columns=close.columns)
            exits = pd.DataFrame(False, index=close.index, columns=close.columns)
            
            # For each timestamp, evaluate which symbols pass the screen filters
            # This simulates the screen running at each historical timestamp
            for i, timestamp in enumerate(close.index):
                # Get OHLCV snapshot up to this timestamp (with indicators)
                snapshot = ohlcv_with_indicators[ohlcv_with_indicators.index <= timestamp].copy()
                if snapshot.empty:
                    continue
                    
                # Get the latest data for each symbol up to this timestamp (with indicators)
                latest_data = snapshot.groupby('symbol').last()
                if latest_data.empty:
                    continue
                
                # Evaluate ONLY technical screen filters against this snapshot
                try:
                    mask = specialist.evaluate_filters_local(latest_data, technical_filters)
                    if mask is not None:
                        matched_tickers = mask[mask].index.tolist()
                        for sym in matched_tickers:
                            if sym in entries.columns:
                                entries.loc[timestamp, sym] = True
                except Exception as e:
                    self._log.warning("filter_eval_failed", timestamp=timestamp, error=str(e))
                    continue
            
            # Generate exits: exit when signal turns off (or simple hold-1-bar)
            # For simplicity, use hold-1-bar exit strategy
            exits = entries.shift(-1).fillna(False)
            
            # Ensure close has the right symbols
            close = close.reindex(columns=entries.columns)
            
            return close, entries, exits

        except Exception:
            self._log.exception("signal_build_failed", screen=screen_config.name)
            return None, None, None

    def _infer_freq(self, index: pd.DatetimeIndex) -> str:
        """Infer frequency from DatetimeIndex for vectorbt annualization."""
        inferred = pd.infer_freq(index)
        if inferred:
            return inferred

        if len(index) > 1:
            deltas = pd.Series(index).diff().dt.total_seconds().median()
            if deltas < 240:  # 4 minutes
                return "1min"
            elif deltas < 1800:  # 30 minutes
                return "5min"
            elif deltas < 7200:  # 2 hours
                return "1h"
            elif deltas < 43200:  # 12 hours
                return "4h"
            else:
                return "D"
        return "D"

    def _compute_config_hash_for_sweep(self, config: FilterSweepConfig, params: dict[str, Any]) -> str:
        """Compute hash of config + params for deduplication."""
        import hashlib
        import json
        combined = {
            "screen": config.screen_name,
            "symbols": config.symbols,
            "timeframe": config.timeframe,
            "start": config.start_date,
            "end": config.end_date,
            "params": params,
        }
        return hashlib.sha256(json.dumps(combined, sort_keys=True).encode()).hexdigest()[:16]

    def _build_summary(
        self,
        sweep_id: str,
        config: FilterSweepConfig,
        results: list[FilterSweepResult],
        duration_ms: float,
    ) -> FilterSweepSummary:
        """Build summary from sweep results."""
        valid_results = [r for r in results if r.valid]
        failed_results = [r for r in results if not r.valid]

        if not valid_results:
            return FilterSweepSummary(
                sweep_id=sweep_id,
                name=config.name,
                screen_name=config.screen_name,
                total_combinations=len(results),
                valid_results=0,
                failed_results=len(results),
                status="completed",
            )

        # Sort by optimization metric
        metric_key = config.optimization_metric
        sorted_results = sorted(
            valid_results,
            key=lambda r: getattr(r, metric_key, -float('inf')) if getattr(r, metric_key) is not None else -float('inf'),
            reverse=True,
        )

        # Build best-by-metric dicts
        best_by_sharpe = self._result_to_dict(sorted_results[0]) if sorted_results else None
        best_by_expectancy = self._result_to_dict(
            max(valid_results, key=lambda r: r.expectancy if r.expectancy is not None else -float('inf'))
        ) if valid_results else None
        best_by_win_rate = self._result_to_dict(
            max(valid_results, key=lambda r: r.win_rate if r.win_rate is not None else -float('inf'))
        ) if valid_results else None
        best_by_profit_factor = self._result_to_dict(
            max(valid_results, key=lambda r: r.profit_factor if r.profit_factor is not None else -float('inf'))
        ) if valid_results else None
        best_by_calmar = self._result_to_dict(
            max(valid_results, key=lambda r: r.calmar if r.calmar is not None else -float('inf'))
        ) if valid_results else None

        # Calculate parameter sensitivity
        param_sensitivity = self._calculate_param_sensitivity(valid_results, config.param_grid.keys())

        return FilterSweepSummary(
            sweep_id=sweep_id,
            name=config.name,
            screen_name=config.screen_name,
            total_combinations=len(config.param_grid),
            valid_results=len(valid_results),
            failed_results=len(failed_results),
            best_by_sharpe=best_by_sharpe,
            best_by_expectancy=best_by_expectancy,
            best_by_win_rate=best_by_win_rate,
            best_by_profit_factor=best_by_profit_factor,
            best_by_calmar=best_by_calmar,
            param_sensitivity=param_sensitivity,
            all_results=[self._result_to_dict(r) for r in results],
            sweep_config=config.model_dump(),
            duration_ms=sum(r.duration_ms for r in valid_results if r.duration_ms),
        )

    def _result_to_dict(self, result: FilterSweepResult) -> dict[str, Any]:
        """Convert result to dict for JSON serialization."""
        return {
            "params": result.params,
            "total_return": result.total_return,
            "annualized_return": result.annualized_return,
            "sharpe": result.sharpe,
            "sortino": result.sortino,
            "calmar": result.calmar,
            "max_drawdown": result.max_drawdown,
            "win_rate": result.win_rate,
            "profit_factor": result.profit_factor,
            "expectancy": result.expectancy,
            "avg_win": result.avg_win,
            "avg_loss": result.avg_loss,
            "total_trades": result.total_trades,
            "winning_trades": result.winning_trades,
            "losing_trades": result.losing_trades,
            "avg_hold_days": result.avg_hold_days,
            "max_consecutive_wins": result.max_consecutive_wins,
            "max_consecutive_losses": result.max_consecutive_losses,
            "max_drawdown_pct": result.max_drawdown_pct,
            "recovery_factor": result.recovery_factor,
            "payoff_ratio": result.payoff_ratio,
            "avg_hold_days": result.avg_hold_days,
            "best_trade": result.best_trade,
            "worst_trade": result.worst_trade,
            "run_id": result.run_id,
            "config_hash": result.config_hash,
            "valid": result.valid,
            "error_message": result.error_message,
        }

    def _calculate_param_sensitivity(
        self,
        results: list[FilterSweepResult],
        param_names: list[str],
    ) -> dict[str, dict[str, float]]:
        """Calculate how sensitive each metric is to each parameter."""
        if not results:
            return {}

        metrics_of_interest = ["sharpe", "expectancy", "win_rate", "profit_factor", "calmar", "win_rate"]
        sensitivity: dict[str, dict[str, float]] = {p: {} for p in param_names}

        for param in param_names:
            # Group results by parameter value
            param_groups: dict[Any, list[FilterSweepResult]] = {}
            for r in results:
                if param in r.params:
                    val = r.params[param]
                    if val not in param_groups:
                        param_groups[val] = []
                    param_groups[val].append(r)

            for metric in metrics_of_interest:
                values = []
                for val, group in param_groups.items():
                    metric_vals = [getattr(r, metric) for r in group if getattr(r, metric) is not None]
                    if metric_vals:
                        values.append((val, np.mean(metric_vals)))

                if len(values) > 1:
                    # Sensitivity = coefficient of variation of metric across param values
                    metric_means = [v[1] for v in values]
                    cv = np.std(metric_means) / (np.mean(metric_means) + 1e-9)
                    sensitivity[param][metric] = float(cv)

        return sensitivity


# Convenience function for running a sweep
async def run_filter_sweep(
    config: FilterSweepConfig,
    progress_callback: callable | None = None,
) -> FilterSweepSummary:
    """Run a filter parameter sweep."""
    engine = FilterSweepEngine()
    return await engine.run_sweep(config, progress_callback)


# Pre-defined sweeps
async def run_preset_sweep(preset_name: str, progress_callback: callable | None = None) -> FilterSweepSummary:
    """Run a preset sweep by name."""
    from backend.app.infrastructure.backtest.filter_sweep import PRESET_SWEEPS

    if preset_name not in PRESET_SWEEPS:
        raise ValueError(f"Unknown preset: {preset_name}. Available: {list(PRESET_SWEEPS.keys())}")

    config = PRESET_SWEEPS[preset_name]
    engine = FilterSweepEngine()
    return await engine.run_sweep(config, progress_callback)