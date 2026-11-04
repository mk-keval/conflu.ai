"""Lightweight Backtest Engine — pure pandas/numpy vectorized backtesting.

Replaces vectorbt.Portfolio.from_signals() and portfolio.stats() with
a minimal implementation using only pandas/numpy. No plotly, no vectorbt.

Data flow:
1. Build entry/exit signals (bool arrays) from filters or indicators
2. Compute position sizes using existing PositionSizer
3. Simulate trades: track entry/exit prices, P&L, fees, slippage
4. Compute equity curve and all metrics from trade history
5. Return structured results matching vectorbt interface
"""

from __future__ import annotations

from datetime import datetime, UTC
from typing import Any

import numpy as np
import pandas as pd

from backend.app.core.logging import get_logger
from backend.app.domain.models import Metrics, Trade
from backend.app.infrastructure.backtest.sizing import PositionSizer
from backend.app.infrastructure.backtest.ledger import TradeLedger
from backend.app.infrastructure.backtest.metrics import MetricsComputer

log = get_logger("conflu.backtest.lightweight")


class LightweightBacktestEngine:
    """Pure pandas/numpy vectorized backtest engine.

    Replaces vectorbt for signal-based backtesting without plotly dependency.
    """

    def __init__(self) -> None:
        self._sizer = PositionSizer()
        self._ledger = TradeLedger()
        self._metrics = MetricsComputer()

    def run(
        self,
        close: pd.DataFrame,
        entries: pd.DataFrame,
        exits: pd.DataFrame,
        size: pd.DataFrame,
        initial_cash: float,
        fees: float,
        slippage: float,
        freq: str,
        high: pd.DataFrame | None = None,
        low: pd.DataFrame | None = None,
    ) -> tuple[pd.DataFrame, pd.Series, list[Trade]]:
        """Run backtest simulation and return equity curve, stats, and trades.

        Args:
            close: Price DataFrame (n_bars × n_symbols)
            entries: Entry signal DataFrame (bool, same shape as close)
            exits: Exit signal DataFrame (bool, same shape as close)
            size: Position size DataFrame (same shape as close, in units)
            initial_cash: Starting capital
            fees: Fee per trade side (decimal, e.g., 0.001 = 0.1%)
            slippage: Slippage per trade side (decimal)
            freq: Data frequency for annualization
            high: High price DataFrame (same shape as close) - optional
            low: Low price DataFrame (same shape as close) - optional

        Returns:
            Tuple of (equity_curve_df, stats_series, trades_list)
        """
        n_bars, n_symbols = close.shape
        symbols = list(close.columns)

        # Initialize tracking
        cash = float(initial_cash)
        positions = np.zeros(n_symbols, dtype=np.float64)  # current units held
        entry_prices = np.full(n_symbols, np.nan)
        entry_indices = np.full(n_symbols, -1, dtype=int)
        entry_cash = np.full(n_symbols, np.nan)

        equity = np.zeros(n_bars, dtype=np.float64)
        trades_list: list[dict] = []

        for i in range(n_bars):
            # 1. Process exits first (free up cash for new entries on same bar)
            for j in range(n_symbols):
                if exits.iloc[i, j] and positions[j] != 0:
                    # Exit position
                    exit_price = close.iloc[i, j]
                    if np.isnan(exit_price) or exit_price <= 0:
                        continue

                    units = positions[j]
                    direction = 1 if units > 0 else -1
                    units_abs = abs(units)

                    # P&L with fees and slippage
                    entry_price = entry_prices[j]
                    if np.isnan(entry_price) or entry_price <= 0:
                        positions[j] = 0
                        continue

                    # Apply slippage: worse price for both entry and exit
                    effective_entry = entry_price * (1 + direction * slippage)
                    effective_exit = exit_price * (1 - direction * slippage)

                    # Gross P&L
                    gross_pnl = direction * units_abs * (effective_exit - effective_entry)

                    # Fees: both entry and exit
                    trade_value = units_abs * exit_price
                    total_fees = trade_value * fees * 2  # entry + exit

                    net_pnl = gross_pnl - total_fees

                    # Record trade
                    trades_list.append({
                        "symbol": symbols[j],
                        "column": j,  # Column index for multi-symbol support
                        "entry_idx": int(entry_indices[j]),
                        "exit_idx": i,
                        "entry_price": float(entry_price),
                        "exit_price": float(exit_price),
                        "size": float(units),
                        "pnl": float(net_pnl),
                        "fees": float(total_fees),
                        "direction": "Long" if direction > 0 else "Short",
                    })

                    # Update cash
                    cash += units_abs * effective_exit - total_fees
                    positions[j] = 0
                    entry_prices[j] = np.nan
                    entry_indices[j] = -1
                    entry_cash[j] = np.nan

            # 2. Process entries
            for j in range(n_symbols):
                if entries.iloc[i, j] and positions[j] == 0:
                    size_units = size.iloc[i, j]
                    if np.isnan(size_units) or size_units <= 0:
                        continue

                    entry_price = close.iloc[i, j]
                    if np.isnan(entry_price) or entry_price <= 0:
                        continue

                    # Apply slippage on entry
                    effective_entry = entry_price * (1 + slippage)
                    cost = size_units * effective_entry

                    # Check if we have enough cash
                    if cost > cash:
                        continue

                    # Enter position
                    positions[j] = size_units
                    entry_prices[j] = entry_price
                    entry_indices[j] = i
                    entry_cash[j] = cost
                    cash -= cost

            # 3. Compute equity at end of bar
            position_value = np.sum(np.where(
                np.isnan(entry_prices), 0, positions * close.iloc[i].values
            ))
            equity[i] = cash + position_value

        # Build equity curve DataFrame
        equity_df = pd.DataFrame({
            "equity": equity,
            "cash": np.full(n_bars, cash),  # approximate
            "positions": np.full(n_bars, equity[-1] - cash),  # approximate
        }, index=close.index)

        # Build trade records DataFrame for ledger
        if trades_list:
            trades_df = pd.DataFrame(trades_list)
        else:
            trades_df = pd.DataFrame(columns=[
                "symbol", "entry_idx", "exit_idx", "entry_price",
                "exit_price", "size", "pnl", "fees", "direction"
            ])

        # Compute stats
        stats = self._compute_stats(equity, trades_list, initial_cash, freq)

        # Build Trade objects via ledger
        ohlcv_for_ledger = close.copy()
        # Add high/low if provided, otherwise synthesize from close
        if high is not None and low is not None:
            for col in close.columns:
                ohlcv_for_ledger[f"{col}_high"] = high[col]
                ohlcv_for_ledger[f"{col}_low"] = low[col]
        elif "high" not in ohlcv_for_ledger.columns:
            # Synthesize from close as fallback
            for col in close.columns:
                ohlcv_for_ledger[f"{col}_high"] = close[col] * 1.001
                ohlcv_for_ledger[f"{col}_low"] = close[col] * 0.999
        trades_objs = self._ledger.build_ledger(
            trades_records=trades_df,
            ohlcv=ohlcv_for_ledger,
        )

        return equity_df, stats, trades_objs

    def _compute_stats(
        self,
        equity: np.ndarray,
        trades: list[dict],
        initial_cash: float,
        freq: str,
    ) -> pd.Series:
        """Compute portfolio statistics from equity curve and trades."""
        if len(equity) < 2:
            return pd.Series(dtype=object)

        # Returns
        returns = pd.Series(equity).pct_change().dropna()
        total_return = (equity[-1] / initial_cash) - 1.0

        # Annualization factor
        freq_map = {"1min": 525600, "5min": 105120, "1h": 8760, "4h": 2190, "1D": 252, "1W": 52}
        periods_per_year = freq_map.get(freq, 252)

        # Sharpe
        sharpe = None
        if returns.std() > 0:
            sharpe = float(np.sqrt(periods_per_year) * returns.mean() / returns.std())

        # Sortino (downside deviation)
        sortino = None
        downside = returns[returns < 0]
        if len(downside) > 0 and downside.std() > 0:
            sortino = float(np.sqrt(periods_per_year) * returns.mean() / downside.std())

        # Max Drawdown
        running_max = np.maximum.accumulate(equity)
        drawdown = (equity - running_max) / running_max
        max_dd = float(np.min(drawdown))

        # Calmar
        cagr = self._compute_cagr(equity, periods_per_year)
        calmar = None
        if max_dd < 0 and cagr is not None:
            calmar = cagr / abs(max_dd)

        # Trade statistics
        if trades:
            pnls = np.array([t["pnl"] for t in trades])
            winning = pnls[pnls > 0]
            losing = pnls[pnls < 0]

            total_trades = len(trades)
            winning_trades = len(winning)
            losing_trades = len(losing)
            win_rate = winning_trades / total_trades if total_trades > 0 else 0.0

            avg_win = float(np.mean(winning)) if len(winning) > 0 else 0.0
            avg_loss = float(np.mean(losing)) if len(losing) > 0 else 0.0

            gross_profit = float(np.sum(winning))
            gross_loss = float(abs(np.sum(losing)))
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

            expectancy = win_rate * avg_win - (1 - win_rate) * avg_loss

            # Max consecutive wins/losses
            pnl_signs = np.sign(pnls)
            max_consec_wins = self._max_consecutive(pnl_signs, 1)
            max_consec_losses = self._max_consecutive(pnl_signs, -1)

            # Hold duration
            hold_durations = [t["exit_idx"] - t["entry_idx"] for t in trades]
            avg_hold = float(np.mean(hold_durations)) if hold_durations else 0.0

            # Best/worst trade
            best_trade = float(np.max(pnls))
            worst_trade = float(np.min(pnls))

            # CAGR
            if cagr is None:
                cagr = self._compute_cagr_from_equity(equity, periods_per_year)

        else:
            total_trades = 0
            winning_trades = 0
            losing_trades = 0
            win_rate = 0.0
            avg_win = 0.0
            avg_loss = 0.0
            profit_factor = None
            expectancy = 0.0
            max_consec_wins = 0
            max_consec_losses = 0
            avg_hold = 0.0
            best_trade = 0.0
            worst_trade = 0.0
            if cagr is None:
                cagr = self._compute_cagr_from_equity(equity, periods_per_year)

        # Build stats Series matching vectorbt format
        stats = pd.Series({
            "total_return": float(total_return),
            "cagr": float(cagr) if cagr else 0.0,
            "sharpe_ratio": float(sharpe) if sharpe else 0.0,
            "sortino_ratio": float(sortino) if sortino else 0.0,
            "calmar_ratio": float(calmar) if calmar else 0.0,
            "max_drawdown": float(max_dd),
            "win_rate": float(win_rate),
            "profit_factor": float(profit_factor) if profit_factor and profit_factor != float("inf") else 0.0,
            "expectancy": float(expectancy),
            "avg_win": float(avg_win),
            "avg_loss": float(avg_loss),
            "total_trades": int(total_trades),
            "winning_trades": int(winning_trades),
            "losing_trades": int(losing_trades),
            "max_consecutive_wins": int(max_consec_wins),
            "max_consecutive_losses": int(max_consec_losses),
            "avg_hold_days": float(avg_hold),
            "best_trade": float(best_trade),
            "worst_trade": float(worst_trade),
        })

        return stats

    def _compute_cagr(self, equity: np.ndarray, periods_per_year: int) -> float | None:
        """Compute CAGR from equity curve."""
        n_periods = len(equity)
        if n_periods < 2:
            return None
        years = n_periods / periods_per_year
        if years <= 0:
            return None
        return (equity[-1] / equity[0]) ** (1.0 / years) - 1.0

    def _compute_cagr_from_equity(self, equity: np.ndarray, periods_per_year: int) -> float | None:
        return self._compute_cagr(equity, periods_per_year)

    @staticmethod
    def _max_consecutive(arr: np.ndarray, target: int) -> int:
        """Find max consecutive occurrences of target value."""
        max_count = 0
        current = 0
        for v in arr:
            if v == target:
                current += 1
                max_count = max(max_count, current)
            else:
                current = 0
        return max_count


class LightweightBacktestResult:
    """Container for backtest results matching vectorbt interface."""

    def __init__(
        self,
        equity_df: pd.DataFrame,
        stats: pd.Series,
        trades: list[Trade],
        config_hash: str,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        initial_cash: float,
        position_sizing: str,
        duration_ms: float = 0.0,
    ):
        self.equity_df = equity_df
        self.stats = stats
        self.trades = trades
        self.config_hash = config_hash
        self.symbol = symbol
        self.timeframe = timeframe
        self.start_date = start_date
        self.end_date = end_date
        self.initial_cash = initial_cash
        self.position_sizing = position_sizing
        self.duration_ms = duration_ms

    @property
    def metrics(self) -> Metrics:
        """Convert stats to domain Metrics model."""
        return Metrics(
            sharpe=self._safe_get(self.stats, "sharpe_ratio"),
            sortino=self._safe_get(self.stats, "sortino_ratio"),
            calmar=self._safe_get(self.stats, "calmar_ratio"),
            max_dd=self._safe_get(self.stats, "max_drawdown"),
            win_rate=self._safe_get(self.stats, "win_rate"),
            expectancy=self._safe_get(self.stats, "expectancy"),
            profit_factor=self._safe_get(self.stats, "profit_factor"),
            sqn=self._safe_get(self.stats, "sqn"),
            cagr=self._safe_get(self.stats, "cagr"),
            ulcer=None,  # Could add if needed
        )

    @property
    def trades_count(self) -> int:
        return int(self.stats.get("total_trades", 0))

    @staticmethod
    def _safe_get(series: pd.Series, key: str) -> float | None:
        try:
            val = series.get(key)
            if val is None or (isinstance(val, float) and np.isnan(val)):
                return None
            return float(val)
        except (KeyError, IndexError, TypeError):
            return None