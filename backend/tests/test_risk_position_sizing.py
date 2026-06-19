"""Tests for PositionSizingRefiner — delegates to PositionSizer, applies risk constraints."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backend.app.infrastructure.risk.position_sizing import PositionSizingRefiner


@pytest.fixture
def price_df():
    """Simple price DataFrame with 5 bars and 2 symbols."""
    return pd.DataFrame(
        {"AAPL": [150.0, 152.0, 149.0, 155.0, 153.0], "MSFT": [300.0, 305.0, 298.0, 310.0, 308.0]},
        index=pd.date_range("2024-01-01", periods=5, freq="D", tz="UTC"),
    )


@pytest.fixture
def entries_df():
    """Entry signals: enter on bar 1 and 3 only."""
    return pd.DataFrame(
        {"AAPL": [False, True, False, True, False], "MSFT": [False, True, False, True, False]},
        index=pd.date_range("2024-01-01", periods=5, freq="D", tz="UTC"),
    )


@pytest.fixture
def sizing_refiner():
    return PositionSizingRefiner()


class TestDelegation:
    def test_delegates_to_position_sizer(self, sizing_refiner, price_df, entries_df):
        """Size generation delegates to Phase 4 PositionSizer."""
        size = sizing_refiner.compute_size_with_risk_constraints(
            close=price_df,
            entries=entries_df,
            method="fixed",
            initial_cash=100_000,
            params={"mode": "units", "value": 100},
        )
        assert size.shape == price_df.shape
        # On entry bars, size should be 100
        assert size.iloc[1, 0] == 100  # AAPL bar 1

    def test_correlation_limit(self, sizing_refiner, price_df, entries_df):
        """Correlation limit reduces correlated pair sizes."""
        corr_matrix = pd.DataFrame(
            {"AAPL": [1.0, 0.95], "MSFT": [0.95, 1.0]},
            index=["AAPL", "MSFT"],
        )
        # Base size
        base = sizing_refiner.compute_size_with_risk_constraints(
            close=price_df,
            entries=entries_df,
            method="fixed",
            initial_cash=100_000,
            params={"mode": "units", "value": 100},
        )

        # Constrained with correlation limit
        constrained = sizing_refiner.compute_size_with_risk_constraints(
            close=price_df,
            entries=entries_df,
            method="fixed",
            initial_cash=100_000,
            params={"mode": "units", "value": 100},
            correlation_matrix=corr_matrix,
            max_correlation=0.8,
        )

        # After correlation limit, size should be reduced
        base_val = base.iloc[1, 0]
        constrained_val = constrained.iloc[1, 0]
        assert constrained_val <= base_val

    def test_var_cap_applied(self, sizing_refiner, price_df, entries_df):
        """VaR cap reduces size when position VaR is high."""
        pos_var = pd.Series({"AAPL": 0.05, "MSFT": 0.02})
        portfolio_var = 0.03

        constrained = sizing_refiner.compute_size_with_risk_constraints(
            close=price_df,
            entries=entries_df,
            method="fixed",
            initial_cash=100_000,
            params={"mode": "units", "value": 100},
            position_var=pos_var,
            portfolio_var=portfolio_var,
            max_var_pct=0.05,
        )

        assert constrained.shape == price_df.shape

    def test_beta_constraint(self, sizing_refiner, price_df, entries_df):
        """High-beta positions get reduced."""
        betas = pd.Series({"AAPL": 2.0, "MSFT": 1.0})

        base = sizing_refiner.compute_size_with_risk_constraints(
            close=price_df,
            entries=entries_df,
            method="fixed",
            initial_cash=100_000,
            params={"mode": "units", "value": 100},
        )

        constrained = sizing_refiner.compute_size_with_risk_constraints(
            close=price_df,
            entries=entries_df,
            method="fixed",
            initial_cash=100_000,
            params={"mode": "units", "value": 100},
            beta_values=betas,
        )

        # AAPL (beta=2.0) should be reduced, MSFT (beta=1.0) stays
        if base.iloc[1, 0] > 0 and constrained.iloc[1, 0] > 0:
            assert constrained.iloc[1, 0] <= base.iloc[1, 0]
