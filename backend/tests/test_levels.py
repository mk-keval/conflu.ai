"""Golden tests for shared ATR trade-levels math (infrastructure/analysis/levels.py).

These pin the EXACT historical outputs of the two callers so future refactors
cannot silently change numbers:
- confluence scorer: regime-adaptive multipliers (1.5/2.5/3.5, 2/3/4.5, 3/5/7)
- deep analysis: fixed 2x ATR stop / 2x / 3x ATR targets
Levels are intentionally NOT rounded (historical behavior); risk_reward is 2dp.
"""

import pytest

from backend.app.infrastructure.analysis.levels import (
    compute_atr_levels,
    compute_fallback_levels,
    vol_regime_multipliers,
)


class TestVolRegimeMultipliers:
    def test_low_vol(self) -> None:
        assert vol_regime_multipliers(0.5) == (1.5, 2.5, 3.5)

    def test_normal_vol(self) -> None:
        assert vol_regime_multipliers(2.0) == (2.0, 3.0, 4.5)

    def test_high_vol(self) -> None:
        assert vol_regime_multipliers(4.0) == (3.0, 5.0, 7.0)

    def test_boundaries(self) -> None:
        # atr_pct == 1.0 is NOT < 1.0 → normal regime; == 3.0 is NOT > 3.0 → normal
        assert vol_regime_multipliers(1.0) == (2.0, 3.0, 4.5)
        assert vol_regime_multipliers(3.0) == (2.0, 3.0, 4.5)


class TestComputeAtrLevels:
    def test_long_normal(self) -> None:
        levels = compute_atr_levels(100.0, 2.0, 2.0, 3.0, 4.5)
        assert levels.entry == 100.0
        assert levels.stop_loss == 96.0
        assert levels.target_1 == 106.0
        assert levels.target_2 == 109.0
        assert levels.risk_reward == 1.5

    def test_short_normal(self) -> None:
        levels = compute_atr_levels(100.0, 2.0, 2.0, 3.0, 4.5, is_long=False)
        assert levels.stop_loss == 104.0
        assert levels.target_1 == 94.0
        assert levels.target_2 == 91.0
        assert levels.risk_reward == 1.5

    def test_low_vol_long(self) -> None:
        # confluence low-vol policy (1.5 stop / 2.5 / 3.5 targets) → R:R 1.67
        levels = compute_atr_levels(100.0, 1.0, 1.5, 2.5, 3.5)
        assert levels.stop_loss == 98.5
        assert levels.target_1 == 102.5
        assert levels.target_2 == 103.5
        assert levels.risk_reward == 1.67

    def test_high_vol_long(self) -> None:
        levels = compute_atr_levels(100.0, 6.0, 3.0, 5.0, 7.0)
        assert levels.stop_loss == 82.0
        assert levels.target_1 == 130.0
        assert levels.target_2 == 142.0
        assert levels.risk_reward == 1.67

    def test_deep_analysis_policy(self) -> None:
        # deep_analysis fixed policy: 2x ATR stop, 2x / 3x ATR targets
        levels = compute_atr_levels(50.0, 1.5, 2.0, 2.0, 3.0)
        assert levels.stop_loss == 47.0
        assert levels.target_1 == 53.0
        assert levels.target_2 == 54.5

    def test_float_exactness_no_rounding(self) -> None:
        # Levels must NOT be rounded — pin the raw float behavior
        levels = compute_atr_levels(100.0, 2.0, 2.0, 3.0, 4.5)
        assert levels.stop_loss == pytest.approx(96.0, abs=1e-12)
        assert levels.risk_reward == 1.5  # rounded


class TestComputeFallbackLevels:
    def test_long(self) -> None:
        levels = compute_fallback_levels(100.0)
        assert levels.stop_loss == 95.0
        assert levels.target_1 == 105.0
        assert levels.target_2 == pytest.approx(110.0)
        assert levels.risk_reward == 1.0

    def test_short(self) -> None:
        levels = compute_fallback_levels(100.0, is_long=False)
        assert levels.stop_loss == 105.0
        assert levels.target_1 == 95.0
        assert levels.target_2 == 90.0
        assert levels.risk_reward == 1.0