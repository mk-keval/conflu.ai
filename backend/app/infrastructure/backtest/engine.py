"""BacktestEngine — orchestrator for running backtests.

Data flow:
1. Load OHLCV from DuckDB/Parquet
2. Build signal arrays (entries/exits) via SignalAdapter
3. Compute position sizes via PositionSizer
4. Run vbt.Portfolio.from_signals()
5. Compute metrics via MetricsComputer
6. Build trade ledger via TradeLedger
7. Store results in DuckDB
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from typing import Any

import numpy as np
import pandas as pd

from backend.app.core.database import get_db
from backend.app.core.logging import get_logger, set_correlation_id
from backend.app.infrastructure.backtest.ledger import TradeLedger
from backend.app.infrastructure.backtest.metrics import MetricsComputer
from backend.app.infrastructure.backtest.models import (
    BacktestRunConfig,
    BacktestRunRecord,
    MCSimulationResult,
    OptimizationResult,
)
from backend.app.infrastructure.backtest.signals import SignalAdapter
from backend.app.infrastructure.backtest.sizing import PositionSizer

log = get_logger("conflu.backtest.engine")


class BacktestEngine:
    """Orchestrator for running backtest simulations.

    Coordinates the full backtest pipeline:
    config -> load data -> build signals -> size positions -> run portfolio -> compute metrics -> build ledger -> store results

    All vectorbt CPU-bound operations run via loop.run_in_executor()
    to avoid blocking the async event loop.
    """

    def __init__(self) -> None:
        self._sizer = PositionSizer()
        self._signal_adapter = SignalAdapter()
        self._metrics_computer = MetricsComputer()
        self._ledger = TradeLedger()
        self._log = get_logger("conflu.backtest.engine")

    async def run(self, config: BacktestRunConfig) -> BacktestRunRecord:
        """Run a single backtest and return results.

        Args:
            config: Complete backtest run configuration.

        Returns:
            BacktestRunRecord with metrics, trade info, and metadata.
        """
        set_correlation_id(config.run_id)
        self._log.info("backtest_started", symbol=config.symbols, timeframe=config.timeframe)
        start_time = time.monotonic()

        loop = asyncio.get_running_loop()

        # Run the synchronous backtest in a thread pool
        record = await loop.run_in_executor(None, self._run_sync, config)

        duration_ms = (time.monotonic() - start_time) * 1000
        self._log.info(
            "backtest_completed",
            run_id=config.run_id,
            duration_ms=round(duration_ms, 2),
            trades=record.trades_count,
        )

        return record

    def _run_sync(self, config: BacktestRunConfig) -> BacktestRunRecord:
        """Synchronous backtest implementation (runs in thread pool).

        All vectorbt/numpy operations are CPU-bound and run here.
        """
        try:
            import vectorbt as vbt
        except ImportError:
            self._log.exception("vectorbt_import_failed")
            raise

        # 1. Load OHLCV data
        ohlcv = self._load_ohlcv(config)

        if ohlcv is None or ohlcv.empty:
            self._log.warning("no_ohlcv_data", symbol=config.symbols)
            return BacktestRunRecord(
                run_id=config.run_id,
                config_hash=self._compute_config_hash(config),
                symbol=",".join(config.symbols),
                timeframe=config.timeframe,
                start_date=config.start,
                end_date=config.end,
                initial_cash=config.initial_cash,
                position_sizing=config.position_sizing,
                duration_ms=0.0,
            )

        # Handle multi-symbol case: process each symbol separately
        if "symbol" in ohlcv.columns and len(config.symbols) > 1:
            # For multi-symbol, process first symbol for now
            ohlcv = ohlcv[ohlcv["symbol"] == config.symbols[0]].copy()

        # 2. Build signals (entries/exits)
        price = ohlcv[["close"]].copy() if "close" in ohlcv.columns else ohlcv

        # For single-symbol backtests, wrap in single-column format
        if isinstance(price, pd.Series):
            price = price.to_frame("price")

        # Create entries/exits based on signal source
        # Phase 4 base: simple RSI-based signals as default
        entries, exits = self._build_default_signals(ohlcv, config)

        # 3. Compute position sizes
        atr_series = None
        if config.position_sizing == "atr":
            # Try to load ATR from indicator cache or compute on-the-fly
            try:
                import pandas_ta as ta

                atr_values = ta.atr(
                    high=ohlcv["high"].values,
                    low=ohlcv["low"].values,
                    close=ohlcv["close"].values,
                    length=14,
                )
                atr_series = pd.Series(atr_values, index=ohlcv.index)
            except Exception:
                self._log.warning("atr_computation_failed", symbol=config.symbols)

        # Wrap price, entries, exits as single-column DataFrames for from_signals
        close_df = price if isinstance(price, pd.DataFrame) else price.to_frame("price")
        entries_df = entries if isinstance(entries, pd.DataFrame) else entries.to_frame("signal")
        exits_df = exits if isinstance(exits, pd.DataFrame) else exits.to_frame("signal")

        size_df = self._sizer.compute_position_size(
            close=close_df,
            entries=entries_df,
            method=config.position_sizing,
            initial_cash=config.initial_cash,
            params=config.sizing_params,
            atr_series=atr_series,
        )

        # 4. Run vectorbt portfolio
        portfolio = vbt.Portfolio.from_signals(
            close=close_df,
            entries=entries_df,
            exits=exits_df,
            size=size_df,
            direction="both",
            upon_opposite_entry="close",
            init_cash=config.initial_cash,
            fees=config.fees_decimal,
            slippage=config.slippage_decimal,
            freq=self._infer_freq(close_df.index),
        )

        # 5. Compute metrics
        try:
            stats = portfolio.stats()
        except Exception:
            stats = pd.Series(dtype=object)

        drawdown = portfolio.drawdown()
        metrics = self._metrics_computer.compute(stats, drawdown)

        # 6. Build trade ledger
        try:
            trades_records = portfolio.trades.records
            trades = self._ledger.build_ledger(trades_records, ohlcv)
        except Exception:
            self._log.warning("trade_ledger_failed")
            trades = []

        # 7. Compute config hash and build result
        config_hash = self._compute_config_hash(config)

        record = BacktestRunRecord(
            run_id=config.run_id,
            config_hash=config_hash,
            symbol=",".join(config.symbols),
            timeframe=config.timeframe,
            start_date=config.start,
            end_date=config.end,
            initial_cash=config.initial_cash,
            position_sizing=config.position_sizing,
            metrics=metrics,
            stats_json=json.dumps(stats.to_dict() if hasattr(stats, "to_dict") else {}),
            trades_count=len(trades),
            total_fees=sum(t.fees for t in trades),
        )

        return record

    async def run_walk_forward(
        self,
        config: BacktestRunConfig,
        param_grid: dict[str, list[Any]] | None = None,
    ) -> OptimizationResult:
        """Run walk-forward optimization.

        Delegates to WalkForwardOptimizer. Runs CPU-bound work in thread pool.

        Args:
            config: Base backtest configuration.
            param_grid: Parameter grid for optimization. If None, uses
                config.optimization.param_grid.

        Returns:
            OptimizationResult with fold results and best params.
        """
        from backend.app.infrastructure.backtest.walk_forward import WalkForwardOptimizer

        optimizer = WalkForwardOptimizer(engine=self)
        return await optimizer.optimize(config, param_grid)

    async def run_monte_carlo(
        self,
        config: BacktestRunConfig,
        n_paths: int | None = None,
    ) -> MCSimulationResult:
        """Run Monte Carlo simulation.

        Delegates to MonteCarloSimulator. Runs CPU-bound work in thread pool.

        Args:
            config: Base backtest configuration.
            n_paths: Number of simulation paths. If None, uses config.monte_carlo.n_paths.

        Returns:
            MCSimulationResult with path percentiles and ruin stats.
        """
        from backend.app.infrastructure.backtest.monte_carlo import MonteCarloSimulator

        simulator = MonteCarloSimulator()
        return await simulator.simulate(config, n_paths)

    async def run_full_analysis(
        self,
        config: BacktestRunConfig,
        param_grid: dict[str, list[Any]] | None = None,
        n_mc_paths: int | None = None,
    ) -> dict[str, Any]:
        """Run a complete analysis: backtest + walk-forward + Monte Carlo.

        Args:
            config: Base backtest configuration.
            param_grid: Optional parameter grid for walk-forward optimization.
            n_mc_paths: Optional number of Monte Carlo paths.

        Returns:
            Dict with keys: 'backtest', 'optimization', 'monte_carlo'.
        """
        results: dict[str, Any] = {}

        # Run base backtest
        results["backtest"] = await self.run(config)

        # Run walk-forward if configured
        if config.optimization.enabled:
            results["optimization"] = await self.run_walk_forward(config, param_grid)

        # Run Monte Carlo if configured
        if config.monte_carlo.enabled:
            results["monte_carlo"] = await self.run_monte_carlo(config, n_mc_paths)

        return results

    def _load_ohlcv(self, config: BacktestRunConfig) -> pd.DataFrame | None:
        """Load OHLCV data from DuckDB for the configured symbols and date range.

        Args:
            config: Backtest run configuration.

        Returns:
            DataFrame with OHLCV columns and DatetimeIndex, or None if no data.
        """
        try:
            with get_db(read_only=True) as con:
                placeholders = ",".join("?" * len(config.symbols))
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
                        config.start,
                        config.end,
                    ],
                ).fetchdf()

                if result.empty:
                    return None

                # Set datetime index
                result.set_index("timestamp", inplace=True)
                result.index = pd.DatetimeIndex(result.index)

                return result
        except Exception:
            self._log.exception("ohlcv_load_failed", symbol=config.symbols)
            return None

    def _build_default_signals(
        self,
        ohlcv: pd.DataFrame,
        config: BacktestRunConfig,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Build default entry/exit signals.

        Phase 4 default: Simple RSI-based strategy.
        - Entry: RSI(14) < 30 (oversold)
        - Exit: RSI(14) > 70 (overbought)

        Uses pandas-ta for vectorized computation.

        Args:
            ohlcv: OHLCV DataFrame with 'close' column.
            config: Backtest run config (for future signal source routing).

        Returns:
            Tuple of (entries_df, exits_df) — boolean DataFrames.
        """
        try:
            import pandas_ta as ta
        except ImportError:
            entries = pd.DataFrame(np.zeros((len(ohlcv), 1), dtype=bool), index=ohlcv.index)
            exits = pd.DataFrame(np.zeros((len(ohlcv), 1), dtype=bool), index=ohlcv.index)
            return entries, exits

        close = ohlcv["close"]
        rsi = ta.rsi(close=close.values, length=14) if hasattr(ta, "rsi") else None

        if rsi is not None:
            entries = pd.DataFrame(
                (rsi < 30).astype(bool),
                index=ohlcv.index,
                columns=["signal"],
            )
            exits = pd.DataFrame(
                (rsi > 70).astype(bool),
                index=ohlcv.index,
                columns=["signal"],
            )
        else:
            entries = pd.DataFrame(np.zeros(len(ohlcv), dtype=bool), index=ohlcv.index, columns=["signal"])
            exits = pd.DataFrame(np.zeros(len(ohlcv), dtype=bool), index=ohlcv.index, columns=["signal"])

        return entries, exits

    @staticmethod
    def _infer_freq(index: pd.DatetimeIndex) -> str:
        """Infer frequency from DatetimeIndex for vectorbt annualization.

        Returns pandas frequency string, falling back to 'D' if inference fails.
        """
        inferred = pd.infer_freq(index)
        if inferred:
            return inferred

        # Fallback: estimate from median spacing
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

    @staticmethod
    def _compute_config_hash(config: BacktestRunConfig) -> str:
        """Compute SHA256 hash of configuration for cache lookup.

        Args:
            config: Backtest run config.

        Returns:
            Hex digest string.
        """
        config_dict = config.model_dump(mode="json", exclude={"run_id"})
        raw = json.dumps(config_dict, sort_keys=True).encode()
        return hashlib.sha256(raw).hexdigest()


async def run_backtest(config: BacktestRunConfig) -> BacktestRunRecord:
    """Convenience function to run a single backtest.

    Args:
        config: Backtest run configuration.

    Returns:
        BacktestRunRecord with results.
    """
    engine = BacktestEngine()
    return await engine.run(config)
