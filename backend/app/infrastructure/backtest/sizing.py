"""Position sizing strategies: fixed, ATR-based, and Kelly Criterion.

All strategies operate on DataFrames and return position size arrays
of the same shape as the input price data — no loops over rows.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


class PositionSizer:
    """Compute position sizes for backtest entries.

    Supports three methods:
    - fixed: Fixed number of units or fixed cash amount per trade
    - atr: ATR-based sizing (risk% × equity / (ATR × multiplier))
    - kelly: Kelly Criterion optimal sizing from expected win rate/odds
    """

    def compute_position_size(
        self,
        close: pd.DataFrame,
        entries: pd.DataFrame,
        method: str,
        initial_cash: float,
        params: dict[str, Any] | None = None,
        atr_series: pd.Series | None = None,
    ) -> pd.DataFrame:
        """Compute per-bar, per-symbol position sizes.

        Args:
            close: Price DataFrame (n_bars × n_columns).
            entries: Entry signal DataFrame (bool, same shape as close).
            method: One of 'fixed', 'atr', 'kelly'.
            initial_cash: Initial account equity for %-based sizing.
            params: Method-specific parameters.
            atr_series: ATR values aligned with close.index (required for 'atr' method).

        Returns:
            DataFrame of same shape as close with position sizes in units.

        Raises:
            ValueError: If method is unknown or required params missing.
        """
        params = params or {}
        if method == "fixed":
            return self._fixed_size(close, entries, initial_cash, params)
        elif method == "atr":
            return self._atr_size(close, entries, initial_cash, params, atr_series)
        elif method == "kelly":
            return self._kelly_size(close, entries, initial_cash, params)
        else:
            msg = f"Unknown position sizing method: '{method}'. Choose 'fixed', 'atr', or 'kelly'."
            raise ValueError(msg)

    def _fixed_size(
        self,
        close: pd.DataFrame,
        entries: pd.DataFrame,
        initial_cash: float,
        params: dict[str, Any],
    ) -> pd.DataFrame:
        """Fixed position sizing.

        Params:
            - mode: 'units' (default) or 'cash'
            - value: Units amount or cash amount (default: 100)

        For 'units' mode: buys `value` shares per entry.
        For 'cash' mode: buys `value / close_price` shares per entry.
        """
        mode = params.get("mode", "units")
        value = float(params.get("value", 100))

        if mode == "cash":
            # Buy 'value' dollars worth: shares = cash / price
            data = np.where(entries.values, value / close.values, 0.0)
        else:
            # Buy 'value' units
            data = np.where(entries.values, float(value), 0.0)

        return pd.DataFrame(data, index=close.index, columns=close.columns)

    def _atr_size(
        self,
        close: pd.DataFrame,
        entries: pd.DataFrame,
        initial_cash: float,
        params: dict[str, Any],
        atr_series: pd.Series | None,
    ) -> pd.DataFrame:
        """ATR-based position sizing.

        Params:
            - risk_per_trade: Fraction of equity to risk per trade (default: 0.01)
            - atr_multiplier: Multiplier for ATR stop distance (default: 2.0)
            - max_position_pct: Max fraction of equity for one position (default: 0.25)

        Formula: size = risk_per_trade * equity / (ATR * atr_multiplier)
        """
        risk_per_trade = float(params.get("risk_per_trade", 0.01))
        atr_multiplier = float(params.get("atr_multiplier", 2.0))
        max_position_pct = float(params.get("max_position_pct", 0.25))

        size = pd.DataFrame(
            np.zeros_like(close.values, dtype=np.float64),
            index=close.index,
            columns=close.columns,
        )

        if atr_series is not None:
            # Align ATR with close index
            atr_aligned = atr_series.reindex(close.index, method="ffill").ffill().bfill()
            # Compute per-bar risk amount
            risk_amount = risk_per_trade * initial_cash
            raw_size = risk_amount / (atr_aligned.values * atr_multiplier)

            # Only apply at entry signals, cap at max position per column
            for col in size.columns:
                col_size = np.where(entries[col].values, raw_size, 0.0)
                max_units = (initial_cash * max_position_pct) / close[col].iloc[0]
                col_size = np.minimum(col_size, max_units)
                size[col] = col_size
        else:
            # No ATR available — fall back to fixed sizing
            return self._fixed_size(
                close, entries, initial_cash, {"mode": "cash", "value": initial_cash * risk_per_trade}
            )

        return size

    def _kelly_size(
        self,
        close: pd.DataFrame,
        entries: pd.DataFrame,
        initial_cash: float,
        params: dict[str, Any],
    ) -> pd.DataFrame:
        """Kelly Criterion position sizing.

        Params:
            - kelly_fraction: Fraction of full Kelly to use (default: 0.5 — half-Kelly)
            - win_rate: Expected win rate (0-1). If not provided, defaults to 0.5
            - avg_win_avg_loss_ratio: Expected ratio of avg win / avg loss. If not
              provided, defaults to 1.5

        Kelly formula: f* = p - q/b where:
            p = win_rate, q = 1-p, b = avg_win / avg_loss

        The final position fraction is kelly_fraction * f*.
        """
        kelly_fraction = float(params.get("kelly_fraction", 0.5))
        win_rate = float(params.get("win_rate", 0.5))
        avg_win_loss_ratio = float(params.get("avg_win_avg_loss_ratio", 1.5))

        # Kelly formula: f* = (p * b - q) / b  =  p - q/b
        q = 1.0 - win_rate
        if avg_win_loss_ratio > 0:
            f_star = win_rate - q / avg_win_loss_ratio
        else:
            f_star = 0.0

        f_star = max(0.0, min(f_star, 1.0))  # Clamp to [0, 1]
        f_star *= kelly_fraction  # Apply half-Kelly (or custom fraction)

        # Kelly position size = f* * equity / price
        cash_per_trade = f_star * initial_cash
        data = np.where(entries.values, cash_per_trade / close.values, 0.0)

        return pd.DataFrame(data, index=close.index, columns=close.columns)
