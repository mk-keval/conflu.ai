"""Tests for metrics computer."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backend.app.infrastructure.backtest.metrics import MetricsComputer


class TestUlcerIndex:
    def test_constant_drawdown(self):
        """Ulcer index of constant drawdown equals the drawdown value."""
        dd = pd.Series([-0.1, -0.1, -0.1])
        result = MetricsComputer.ulcer_index(dd)
        assert result == pytest.approx(0.1, abs=1e-10)

    def test_zero_drawdown(self):
        """Ulcer index of zero drawdown is 0."""
        dd = pd.Series([0.0, 0.0, 0.0])
        result = MetricsComputer.ulcer_index(dd)
        assert result == 0.0

    def test_varying_drawdown(self):
        """Ulcer index of varying drawdown computes correctly."""
        dd = pd.Series([-0.05, -0.15, -0.10])
        # sqrt(mean(0.0025, 0.0225, 0.01)) = sqrt(0.035/3) = sqrt(0.01167) ≈ 0.108
        expected = np.sqrt(np.mean(np.array([0.0025, 0.0225, 0.01])))
        result = MetricsComputer.ulcer_index(dd)
        assert result == pytest.approx(expected, abs=1e-10)


class TestComputeMaeMfe:
    @pytest.fixture
    def ohlcv(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "high": [152.0, 154.0, 150.0, 158.0, 155.0],
                "low": [148.0, 150.0, 147.0, 153.0, 152.0],
                "close": [150.0, 153.0, 149.0, 156.0, 154.0],
            },
        )

    def test_long_trade(self, ohlcv):
        """Long: MFE = max(high) - entry, MAE = entry - min(low)."""
        mae, mfe = MetricsComputer.compute_mae_mfe(
            trade_entry_idx=1,
            trade_exit_idx=3,
            entry_price=153.0,
            ohlcv=ohlcv,
            direction="Long",
        )
        # high[1..3] = max(154, 150, 158) = 158, MFE = 158 - 153 = 5
        assert mfe == pytest.approx(5.0, abs=0.01)
        # low[1..3] = min(150, 147, 153) = 147, MAE = 153 - 147 = 6
        assert mae == pytest.approx(6.0, abs=0.01)

    def test_short_trade(self, ohlcv):
        """Short: MFE = entry - min(low), MAE = max(high) - entry."""
        mae, mfe = MetricsComputer.compute_mae_mfe(
            trade_entry_idx=1,
            trade_exit_idx=3,
            entry_price=153.0,
            ohlcv=ohlcv,
            direction="Short",
        )
        # low[1..3] = min(150, 147, 153) = 147, MFE = 153 - 147 = 6
        assert mfe == pytest.approx(6.0, abs=0.01)
        # high[1..3] = max(154, 150, 158) = 158, MAE = 158 - 153 = 5
        assert mae == pytest.approx(5.0, abs=0.01)

    def test_single_bar_trade(self, ohlcv):
        """Trade that opens and closes on same bar."""
        mae, mfe = MetricsComputer.compute_mae_mfe(
            trade_entry_idx=2,
            trade_exit_idx=2,
            entry_price=149.0,
            ohlcv=ohlcv,
            direction="Long",
        )
        # Only bar 2: high=150, low=147
        assert mfe == pytest.approx(1.0, abs=0.01)
        assert mae == pytest.approx(2.0, abs=0.01)


class TestComputeDrawdownStats:
    def test_no_drawdown(self):
        dd = pd.Series([0.0, 0.0, 0.0])
        stats = MetricsComputer.compute_drawdown_stats(dd)
        assert stats["periods"] == []
        assert stats["avg_depth"] == 0.0

    def test_single_drawdown_period(self):
        dd = pd.Series([0.0, -0.1, -0.2, -0.15, 0.0])
        stats = MetricsComputer.compute_drawdown_stats(dd)
        assert len(stats["periods"]) == 1
        assert stats["periods"][0]["depth"] == pytest.approx(0.2, abs=0.01)
        assert stats["periods"][0]["duration_bars"] == 3

    def test_multiple_drawdown_periods(self):
        dd = pd.Series([0.0, -0.1, -0.05, 0.0, -0.3, -0.2, 0.0])
        stats = MetricsComputer.compute_drawdown_stats(dd)
        assert len(stats["periods"]) == 2
        # Second period should have deeper max_depth
        assert stats["max_depth"] == pytest.approx(0.3, abs=0.01)


class TestCompute:
    def test_with_valid_stats(self):
        stats = pd.Series({
            "sharpe_ratio": 1.5,
            "sortino_ratio": 2.0,
            "calmar_ratio": 1.2,
            "max_drawdown": -0.15,
            "win_rate": 0.6,
            "expectancy": 50.0,
            "profit_factor": 1.8,
            "sqn": 2.5,
            "cagr": 0.12,
        })
        dd = pd.Series([0.0, -0.1, -0.05])
        computer = MetricsComputer()
        metrics = computer.compute(stats, dd)
        assert metrics.sharpe == pytest.approx(1.5)
        assert metrics.sortino == pytest.approx(2.0)
        assert metrics.calmar == pytest.approx(1.2)
        assert metrics.max_dd == pytest.approx(-0.15)
        assert metrics.win_rate == pytest.approx(0.6)
        assert metrics.cagr == pytest.approx(0.12)
        assert metrics.ulcer is not None

    def test_without_drawdown(self):
        stats = pd.Series({"sharpe_ratio": 1.5})
        computer = MetricsComputer()
        metrics = computer.compute(stats)
        assert metrics.sharpe == 1.5
        assert metrics.ulcer is None


class TestSafeGet:
    def test_existing_key(self):
        s = pd.Series({"sharpe_ratio": 1.5})
        assert MetricsComputer._safe_get(s, "sharpe_ratio") == 1.5

    def test_missing_key(self):
        s = pd.Series({"sharpe_ratio": 1.5})
        assert MetricsComputer._safe_get(s, "nonexistent") is None

    def test_nan_value(self):
        s = pd.Series({"sharpe_ratio": float("nan")})
        assert MetricsComputer._safe_get(s, "sharpe_ratio") is None
