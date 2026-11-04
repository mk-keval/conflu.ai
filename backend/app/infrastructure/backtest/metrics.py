"""Portfolio metrics computation — wraps vectorbt stats + custom metrics.

vectorbt.stats() provides: Sharpe, Sortino, Calmar, Max DD, Win Rate,
Expectancy, Profit Factor, SQN, CAGR.
Custom: Ulcer Index, MAE/MFE (per trade).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from backend.app.domain.models import Metrics


class MetricsComputer:
    """Compute portfolio metrics from a vectorbt Portfolio object.

    Wraps vbt.Portfolio.stats() and adds custom computations
    (Ulcer Index, CAGR if missing, drawdown statistics).
    """

    def compute(
        self,
        portfolio_stats: pd.Series,
        drawdown_series: pd.Series | None = None,
    ) -> Metrics:
        """Compute all metrics from vectorbt portfolio stats.

        Args:
            portfolio_stats: Result from portfolio.stats() — a pandas Series
                with metric names as index.
            drawdown_series: Optional drawdown series for Ulcer Index computation.
                If None, Ulcer Index will be None.

        Returns:
            Metrics model with all available fields populated.
        """
        ulcer = self.ulcer_index(drawdown_series) if drawdown_series is not None and not drawdown_series.empty else None

        metrics = Metrics(
            sharpe=self._safe_get(portfolio_stats, "sharpe_ratio"),
            sortino=self._safe_get(portfolio_stats, "sortino_ratio"),
            calmar=self._safe_get(portfolio_stats, "calmar_ratio"),
            max_dd=self._safe_get(portfolio_stats, "max_drawdown"),
            win_rate=self._safe_get(portfolio_stats, "win_rate"),
            expectancy=self._safe_get(portfolio_stats, "expectancy"),
            profit_factor=self._safe_get(portfolio_stats, "profit_factor"),
            sqn=self._safe_get(portfolio_stats, "sqn"),
            cagr=self._safe_get(portfolio_stats, "cagr"),
            ulcer=ulcer,
        )

        return metrics

    @staticmethod
    def _safe_get(series: pd.Series, key: str) -> float | None:
        """Safely get a value from a pandas Series, returning None if missing."""
        try:
            val = series.get(key)
            if val is None or (isinstance(val, float) and np.isnan(val)):
                return None
            return float(val)
        except (KeyError, IndexError, TypeError):
            return None

    @staticmethod
    def ulcer_index(drawdown_series: pd.Series) -> float:
        """Compute Ulcer Index from drawdown series.

        UI = sqrt(mean(drawdown^2))
        where drawdown is as decimal (0.25 = 25% underwater).

        Args:
            drawdown_series: Drawdown series as fractional values.

        Returns:
            Ulcer Index value.
        """
        # Use only underwater periods for Ulcer computation
        dd_squared = drawdown_series**2
        return float(np.sqrt(np.mean(dd_squared)))

    @staticmethod
    def compute_mae_mfe(
        trade_entry_idx: int,
        trade_exit_idx: int,
        entry_price: float,
        ohlcv: pd.DataFrame,
        direction: str,
        symbol: str | None = None,
    ) -> tuple[float, float]:
        """Compute MAE (Maximum Adverse Excursion) and MFE (Maximum Favorable Excursion).

        Uses daily OHLC high/low for approximation. For long trades:
            MFE = max(high[entry..exit]) - entry_price
            MAE = entry_price - min(low[entry..exit])

        For short trades:
            MFE = entry_price - min(low[entry..exit])
            MAE = max(high[entry..exit]) - entry_price

        Args:
            trade_entry_idx: Bar index of trade entry.
            trade_exit_idx: Bar index of trade exit.
            entry_price: Price at entry.
            ohlcv: DataFrame with 'high' and 'low' columns (single symbol)
                   or symbol-specific columns like 'AAPL_high', 'AAPL_low' (multi-symbol).
            direction: 'Long' or 'Short'.
            symbol: Optional symbol name for multi-symbol OHLCV. If provided,
                   extracts high/low for that symbol.

        Returns:
            Tuple of (mae, mfe). Both are non-negative floats.
        """
        start = max(0, trade_entry_idx)
        end = min(len(ohlcv) - 1, trade_exit_idx)

        # Handle multi-symbol OHLCV with symbol-specific columns
        if symbol is not None:
            high_col = f"{symbol}_high"
            low_col = f"{symbol}_low"
            if high_col in ohlcv.columns and low_col in ohlcv.columns:
                high = float(ohlcv.iloc[start : end + 1][high_col].max())
                low = float(ohlcv.iloc[start : end + 1][low_col].min())
            else:
                # Fallback to generic high/low if symbol-specific not found
                high = float(ohlcv.iloc[start : end + 1]["high"].max())
                low = float(ohlcv.iloc[start : end + 1]["low"].min())
        else:
            # Single symbol OHLCV with generic high/low columns
            high = float(ohlcv.iloc[start : end + 1]["high"].max())
            low = float(ohlcv.iloc[start : end + 1]["low"].min())

        if direction == "Long":
            mfe = max(0.0, high - entry_price)
            mae = max(0.0, entry_price - low)
        else:
            mfe = max(0.0, entry_price - low)
            mae = max(0.0, high - entry_price)

        return mae, mfe

    @staticmethod
    def compute_drawdown_stats(drawdown: pd.Series) -> dict[str, Any]:
        """Compute drawdown statistics: periods, average depth, average duration.

        Args:
            drawdown: Drawdown series (fractional, e.g., -0.25 = 25% underwater).

        Returns:
            Dict with 'periods' (list of drawdown periods), 'avg_depth',
            'avg_duration_bars', 'max_depth', 'max_duration_bars'.
        """
        is_underwater = drawdown < 0
        if not is_underwater.any():
            return {
                "periods": [],
                "avg_depth": 0.0,
                "avg_duration_bars": 0,
                "max_depth": 0.0,
                "max_duration_bars": 0,
            }

        # Detect transitions: start and end of each drawdown period
        regime = (is_underwater != is_underwater.shift(1)).cumsum()

        periods = []
        for _, group in drawdown.groupby(regime):
            if group.iloc[0] < 0:  # In drawdown
                depth = abs(float(group.min()))
                duration = len(group)
                periods.append(
                    {
                        "start": str(group.index[0]),
                        "trough": str(group.idxmin()),
                        "end": str(group.index[-1]),
                        "depth": depth,
                        "duration_bars": duration,
                    }
                )

        if not periods:
            return {
                "periods": [],
                "avg_depth": 0.0,
                "avg_duration_bars": 0,
                "max_depth": 0.0,
                "max_duration_bars": 0,
            }

        depths = [p["depth"] for p in periods]
        durations = [p["duration_bars"] for p in periods]

        return {
            "periods": periods,
            "avg_depth": float(np.mean(depths)),
            "avg_duration_bars": int(np.mean(durations)),
            "max_depth": float(max(depths)),
            "max_duration_bars": int(max(durations)),
        }
