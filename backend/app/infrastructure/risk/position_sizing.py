"""PositionSizingRefiner — Enhanced position sizing with risk overlays.

Composes on top of Phase 4's PositionSizer (NOT a rewrite), adding:
- Correlation-aware position limits
- VaR-based position caps
- Beta-adjusted sizing constraints
- Leverage bounds

CRITICAL: Does NOT reimplement ATR or Kelly formulas.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from backend.app.core.config import settings
from backend.app.core.logging import get_logger
from backend.app.infrastructure.backtest.sizing import PositionSizer

log = get_logger("conflu.risk.position_sizing")


class PositionSizingRefiner:
    """Enhanced position sizing with correlation, VaR, beta, and leverage constraints.

    Composes on top of Phase 4's PositionSizer. All ATR and Kelly formulas
    are handled by the underlying PositionSizer — this class only adds
    risk-management overlays.
    """

    def __init__(self) -> None:
        self._sizer = PositionSizer()
        self._default_risk_per_trade = settings.risk.default_risk_per_trade
        self._default_atr_mult = settings.risk.default_atr_multiplier
        self._log = get_logger("conflu.risk.position_sizing")

    def compute_size_with_risk_constraints(
        self,
        close: pd.DataFrame,
        entries: pd.DataFrame,
        method: str,
        initial_cash: float,
        params: dict[str, Any] | None = None,
        atr_series: pd.Series | None = None,
        correlation_matrix: pd.DataFrame | None = None,
        position_var: pd.Series | None = None,
        portfolio_var: float | None = None,
        beta_values: pd.Series | None = None,
        max_correlation: float | None = None,
        max_var_pct: float | None = None,
        max_leverage: float | None = None,
    ) -> pd.DataFrame:
        """Compute position sizes with risk overlays.

        5-step pipeline:
        1. Base sizing via self._sizer.compute_position_size()
        2. Correlation limit — reduce combined sizing for highly correlated pairs
        3. VaR cap — bound positions by VaR contribution
        4. Beta constraint — reduce high-beta positions
        5. Leverage bound — scale all positions if total leverage exceeds limit

        Args:
            close: Price DataFrame.
            entries: Entry signal DataFrame (bool).
            method: Sizing method ('fixed', 'atr', 'kelly').
            initial_cash: Initial account equity.
            params: PositionSizer params.
            atr_series: ATR values (required for 'atr' method).
            correlation_matrix: N×N correlation DataFrame for correlation limits.
            position_var: Per-symbol VaR Series for VaR caps.
            portfolio_var: Portfolio-wide VaR for VaR cap computation.
            beta_values: Per-symbol beta Series for beta constraints.
            max_correlation: Max allowed pairwise correlation (default config).
            max_var_pct: Max VaR fraction per position (default config).
            max_leverage: Max total leverage (default config).

        Returns:
            DataFrame of same shape as close with constrained position sizes.
        """
        max_correlation = max_correlation or settings.risk.max_correlation_symbols
        _var_pct = max_var_pct if max_var_pct is not None else 0.05
        _leverage = max_leverage or 1.0

        params = params or {}
        # Apply defaults from risk settings if not in params
        if "risk_per_trade" not in params:
            params["risk_per_trade"] = self._default_risk_per_trade
        if "atr_multiplier" not in params:
            params["atr_multiplier"] = self._default_atr_mult

        # Step 1: Base sizing
        base = self._sizer.compute_position_size(
            close=close,
            entries=entries,
            method=method,
            initial_cash=initial_cash,
            params=params,
            atr_series=atr_series,
        )

        constrained = base.copy()

        # Step 2: Correlation limit
        if correlation_matrix is not None:
            constrained = self._apply_correlation_limit(
                constrained, base, correlation_matrix, max_correlation, initial_cash, close
            )

        # Step 3: VaR cap
        if position_var is not None and portfolio_var is not None and portfolio_var > 0:
            constrained = self._apply_var_cap(constrained, base, position_var, portfolio_var, _var_pct)

        # Step 4: Beta constraint
        if beta_values is not None:
            constrained = self._apply_beta_constraint(constrained, base, beta_values, initial_cash)

        # Step 5: Leverage bound
        constrained = self._apply_leverage_bound(constrained, base, initial_cash, _leverage)

        return constrained

    def _apply_correlation_limit(
        self,
        constrained: pd.DataFrame,
        base: pd.DataFrame,
        corr_matrix: pd.DataFrame,
        max_corr: float,
        cash: float,
        close: pd.DataFrame,
    ) -> pd.DataFrame:
        """Reduce combined sizing for pairs whose correlation exceeds limit.

        For each pair with |correlation| > max_corr, proportionally reduce
        both positions' sizes to bring combined exposure within bounds.

        Args:
            constrained: Current constrained size DataFrame.
            base: Base size DataFrame.
            corr_matrix: N×N correlation DataFrame.
            max_corr: Max allowed correlation.
            cash: Account equity for bound computation.
            close: Price DataFrame.

        Returns:
            Updated constrained size DataFrame.
        """
        symbols = [c for c in base.columns if c in corr_matrix.columns and c in close.columns]
        if len(symbols) < 2:
            return constrained

        for i, s1 in enumerate(symbols):
            for s2 in symbols[i + 1 :]:
                if s1 in corr_matrix.index and s2 in corr_matrix.columns:
                    corr_val = corr_matrix.loc[s1, s2]
                    if not np.isnan(corr_val) and abs(corr_val) > max_corr:
                        # Reduce both by factor: max_corr / |correlation|
                        reduction = max_corr / abs(corr_val)
                        constrained[s1] = constrained[s1] * reduction
                        constrained[s2] = constrained[s2] * reduction

        return constrained

    def _apply_var_cap(
        self,
        constrained: pd.DataFrame,
        base: pd.DataFrame,
        position_var: pd.Series,
        portfolio_var: float,
        max_var_pct: float,
    ) -> pd.DataFrame:
        """Cap position sizes so no single position exceeds VaR-based limit.

        VaR cap = max_var_pct × portfolio_var / position_var

        Args:
            constrained: Current constrained size DataFrame.
            base: Base size DataFrame.
            position_var: Per-symbol VaR Series.
            portfolio_var: Portfolio VaR.
            max_var_pct: Max VaR fraction per position.

        Returns:
            Updated constrained size DataFrame.
        """
        for symbol in constrained.columns:
            if symbol in position_var.index:
                pos_var = position_var[symbol]
                if pos_var is not None and not np.isnan(pos_var) and pos_var > 0:
                    max_size_ratio = max_var_pct * portfolio_var / pos_var
                    # Scale down the constrained values by the max ratio
                    constrained[symbol] = constrained[symbol].clip(upper=base[symbol].max() * max_size_ratio)

        return constrained

    def _apply_beta_constraint(
        self,
        constrained: pd.DataFrame,
        base: pd.DataFrame,
        betas: pd.Series,
        cash: float,
    ) -> pd.DataFrame:
        """Reduce high-beta positions.

        Positions with beta > 1.5 are scaled down by factor 1.5/beta.
        Positions with beta < 0.5 are left unchanged.

        Args:
            constrained: Current constrained size DataFrame.
            base: Base size DataFrame.
            betas: Per-symbol beta Series.
            cash: Account equity.

        Returns:
            Updated constrained size DataFrame.
        """
        for symbol in constrained.columns:
            if symbol in betas.index:
                beta_val = betas[symbol]
                if beta_val is not None and not np.isnan(beta_val) and beta_val > 1.5:
                    factor = 1.5 / beta_val
                    constrained[symbol] = constrained[symbol] * factor

        return constrained

    def _apply_leverage_bound(
        self,
        constrained: pd.DataFrame,
        base: pd.DataFrame,
        cash: float,
        max_leverage: float,
    ) -> pd.DataFrame:
        """Scale all positions if total leverage exceeds the maximum.

        Args:
            constrained: Current constrained size DataFrame.
            base: Base size DataFrame.
            cash: Account equity.
            max_leverage: Max allowed leverage ratio.

        Returns:
            Updated constrained size DataFrame.
        """
        # Estimate total exposure as sum of position market values / cash
        total_exposure = constrained.sum(axis=1).mean() / cash if cash > 0 else 0.0

        if total_exposure > max_leverage:
            scale_factor = max_leverage / total_exposure
            constrained = constrained * scale_factor

        return constrained
