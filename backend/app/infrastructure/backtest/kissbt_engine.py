"""KissBT Engine — Lightweight vectorized backtesting using kissbt.

Replaces vectorbt with kissbt for signal-based backtesting without plotly dependency.

Data flow:
1. Build entry/exit signals from screen config
2. Prepare market data in kissbt format (MultiIndex DataFrame)
3. Run kissbt engine with custom strategy
4. Extract metrics from kissbt Analyzer
5. Return structured results matching our domain models
"""

from __future__ import annotations

from datetime import datetime, UTC
from typing import Any, Optional
from uuid import uuid4

import numpy as np
import pandas as pd

# Monkey-patch plotly template to fix scattermapbox -> scattermap (plotly v6 breaking change)
# Must be done BEFORE importing kissbt which imports plotly internally
try:
    import plotly.graph_objects as go
    from plotly.graph_objs.layout.template import Data as TemplateData
    
    # Patch the TemplateData class to accept scattermapbox
    original_setattr = TemplateData.__setattr__
    def patched_setattr(self, name, value):
        if name == 'scattermapbox':
            name = 'scattermap'
        return original_setattr(self, name, value)
    TemplateData.__setattr__ = patched_setattr
    
    original_setitem = TemplateData.__setitem__
    def patched_setitem(self, key, value):
        if key == 'scattermapbox':
            key = 'scattermap'
        return original_setitem(self, key, value)
    TemplateData.__setitem__ = patched_setitem
    
except ImportError:
    pass
except Exception:
    pass

from backend.app.core.logging import get_logger
from backend.app.domain.models import Metrics, Trade
from backend.app.infrastructure.backtest.sizing import PositionSizer
from backend.app.infrastructure.backtest.ledger import TradeLedger

log = get_logger("conflu.backtest.kissbt")


class KissBTEngine:
    """KissBT-based backtest engine for signal-based backtesting."""

    def __init__(self) -> None:
        self._sizer = PositionSizer()
        self._ledger = TradeLedger()
        self._log = get_logger("conflu.backtest.kissbt")

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
    ) -> tuple[pd.DataFrame, pd.Series, list[Trade]]:
        """Run backtest simulation using kissbt.

        Args:
            close: Price DataFrame (n_bars × n_symbols)
            entries: Entry signal DataFrame (bool, same shape as close)
            exits: Exit signal DataFrame (bool, same shape as close)
            size: Position size DataFrame (same shape as close, in units)
            initial_cash: Starting capital
            fees: Fee per trade side (decimal, e.g., 0.001 = 0.1%)
            slippage: Slippage per trade side (decimal)
            freq: Data frequency for annualization

        Returns:
            Tuple of (equity_curve_df, stats_series, trades_list)
        """
        try:
            from kissbt import Broker, Engine, Order, Strategy, Analyzer
        except ImportError:
            self._log.exception("kissbt_not_installed")
            raise

        n_bars, n_symbols = close.shape
        symbols = list(close.columns)

        # Prepare market data in kissbt format (MultiIndex: timestamp, ticker)
        market_data = self._prepare_market_data(close)

        # Create custom strategy from signals
        strategy_class = self._create_strategy_class(entries, exits, size, symbols)

        # Setup broker
        broker = Broker(
            start_capital=initial_cash,
            fees=fees,  # kissbt uses fee per trade
        )

        strategy = strategy_class(broker)
        engine = Engine(broker, strategy)

        # Run backtest
        result = engine.run(market_data)

        # Extract equity curve and trades
        equity_df, trades = self._extract_results(result, close.index, initial_cash)

        # Compute stats
        stats = self._compute_stats(equity_df["equity"].values, trades, initial_cash, freq)

        # Build Trade objects via ledger
        trades_objs = self._ledger.build_ledger(
            trades_records=trades,
            ohlcv=close,
        )

        return equity_df, stats, trades_objs

    def _prepare_market_data(self, close: pd.DataFrame) -> pd.DataFrame:
        """Convert close prices to kissbt MultiIndex format."""
        # Stack to long format
        df = close.stack().reset_index()
        df.columns = ["timestamp", "ticker", "close"]
        
        # Add dummy OHLC columns (kissbt expects open/high/low/close)
        df["open"] = df["close"]
        df["high"] = df["close"]
        df["low"] = df["close"]
        
        # Set MultiIndex
        df.set_index(["timestamp", "ticker"], inplace=True)
        df.sort_index(inplace=True)
        
        return df[["open", "high", "low", "close"]]

    def _create_strategy_class(
        self,
        entries: pd.DataFrame,
        exits: pd.DataFrame,
        size: pd.DataFrame,
        symbols: list[str],
    ):
        """Create a dynamic Strategy class that uses pre-computed signals."""
        
        # Pre-compute signal arrays for fast lookup
        entry_arrays = {sym: entries[sym].values for sym in symbols}
        exit_arrays = {sym: exits[sym].values for sym in symbols}
        size_arrays = {sym: size[sym].values for sym in symbols}
        
        class SignalStrategy:
            """KissBT strategy that uses pre-computed entry/exit signals."""
            
            def __init__(self, broker):
                self.broker = broker
                self.position_state = {sym: 0 for sym in symbols}  # 0=flat, 1=long, -1=short
                self._log = get_logger("conflu.backtest.kissbt.strategy")
            
            def initialize(self) -> None:
                pass
            
            def generate_orders(self, current_data, current_timestamp) -> None:
                """Generate orders based on pre-computed signals."""
                # Get current bar index
                try:
                    bar_idx = entries.index.get_loc(current_timestamp)
                except KeyError:
                    return
                
                for sym in symbols:
                    current_pos = self.position_state[sym]
                    entry_signal = entry_arrays[sym][bar_idx]
                    exit_signal = exit_arrays[sym][bar_idx]
                    position_size = size_arrays[sym][bar_idx]
                    
                    if current_pos == 0 and entry_signal:
                        # Enter long position
                        if position_size > 0:
                            self.broker.place_order(Order(
                                ticker=sym,
                                size=position_size,
                                order_type="market",
                            ))
                            self.position_state[sym] = 1
                    
                    elif current_pos == 1 and exit_signal:
                        # Exit long position
                        self.broker.place_order(Order(
                            ticker=sym,
                            size=-self.broker.get_position(sym).size,
                            order_type="market",
                        ))
                        self.position_state[sym] = 0
                    
                    # Handle short positions if needed
                    elif current_pos == -1 and exit_signal:
                        self.broker.place_order(Order(
                            ticker=sym,
                            size=-self.broker.get_position(sym).size,
                            order_type="market",
                        ))
                        self.position_state[sym] = 0
        
        return SignalStrategy

    def _extract_results(
        self,
        result,
        index: pd.DatetimeIndex,
        initial_cash: float,
    ) -> tuple[pd.DataFrame, list[dict]]:
        """Extract equity curve and trades from kissbt result."""
        # Get portfolio value history
        portfolio_values = result.portfolio_value
        
        equity_df = pd.DataFrame({
            "equity": portfolio_values,
        }, index=index)
        
        # Extract trades from result.trades
        trades = []
        if hasattr(result, 'trades') and result.trades:
            for trade in result.trades:
                trades.append({
                    "symbol": trade.ticker,
                    "entry_idx": trade.entry_idx,
                    "exit_idx": trade.exit_idx,
                    "entry_price": trade.entry_price,
                    "exit_price": trade.exit_price,
                    "size": trade.size,
                    "pnl": trade.pnl,
                    "fees": trade.fees,
                    "direction": "Long" if trade.size > 0 else "Short",
                })
        
        return equity_df, trades

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

        returns = pd.Series(equity).pct_change().dropna()
        total_return = (equity[-1] / initial_cash) - 1.0

        freq_map = {"1min": 525600, "5min": 105120, "1h": 8760, "4h": 2190, "1D": 252, "1W": 52}
        periods_per_year = freq_map.get(freq, 252)

        sharpe = None
        if returns.std() > 0:
            sharpe = float(np.sqrt(periods_per_year) * returns.mean() / returns.std())

        sortino = None
        downside = returns[returns < 0]
        if len(downside) > 0 and downside.std() > 0:
            sortino = float(np.sqrt(periods_per_year) * returns.mean() / downside.std())

        running_max = np.maximum.accumulate(equity)
        drawdown = (equity - running_max) / running_max
        max_dd = float(np.min(drawdown))

        cagr = self._compute_cagr(equity, periods_per_year)
        calmar = None
        if max_dd < 0 and cagr is not None:
            calmar = cagr / abs(max_dd)

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

            pnl_signs = np.sign(pnls)
            max_consec_wins = self._max_consecutive(pnl_signs, 1)
            max_consec_losses = self._max_consecutive(pnl_signs, -1)

            hold_durations = [t["exit_idx"] - t["entry_idx"] for t in trades]
            avg_hold = float(np.mean(hold_durations)) if hold_durations else 0.0

            best_trade = float(np.max(pnls))
            worst_trade = float(np.min(pnls))
        else:
            total_trades = 0
            winning_trades = 0
            losing_trades = 0
            win_rate = 0.0
            avg_win = 0.0
            avg_loss = 0.0
            profit_factor = 0.0
            expectancy = 0.0
            max_consec_wins = 0
            max_consec_losses = 0
            avg_hold = 0.0
            best_trade = 0.0
            worst_trade = 0.0

        stats = pd.Series({
            "total_return": float(total_return),
            "cagr": float(cagr) if cagr else 0.0,
            "sharpe_ratio": float(sharpe) if sharpe else 0.0,
            "sortino_ratio": float(sortino) if sortino else 0.0,
            "calmar_ratio": float(calmar) if calmar else 0.0,
            "max_drawdown": float(max_dd),
            "win_rate": float(win_rate),
            "profit_factor": float(profit_factor) if profit_factor != float("inf") else 0.0,
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
        n_periods = len(equity)
        if n_periods < 2:
            return None
        years = n_periods / periods_per_year
        if years <= 0:
            return None
        return (equity[-1] / equity[0]) ** (1.0 / years) - 1.0

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


class KissBTResult:
    """Container for backtest results matching our domain interface."""

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
        return Metrics(
            sharpe=self._safe_get(self.stats, "sharpe_ratio"),
            sortino=self._safe_get(self.stats, "sortino_ratio"),
            calmar=self._safe_get(self.stats, "calmar_ratio"),
            max_dd=self._safe_get(self.stats, "max_drawdown"),
            win_rate=self._safe_get(self.stats, "win_rate"),
            expectancy=self._safe_get(self.stats, "expectancy"),
            profit_factor=self._safe_get(self.stats, "profit_factor"),
            sqn=None,
            cagr=self._safe_get(self.stats, "cagr"),
            ulcer=None,
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