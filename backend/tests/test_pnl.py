"""Tests for the canonical P&L and plan-metric helpers (D-74)."""

from __future__ import annotations

import pytest

from backend.app.domain.workflow import pnl


def test_crs_closed_trade_is_dollars_not_notional() -> None:
    """D-74: the live row reported -$1,624.99 on a $25.17 price loss."""
    result = pnl.dollar_pnl(278.24, 273.93, 5.84)
    assert result is not None
    assert result["pnl_gross_usd"] == pytest.approx(-25.17, abs=0.01)
    assert result["costs_usd"] == pytest.approx(4.84, abs=0.01)
    assert result["pnl_usd"] == pytest.approx(-30.01, abs=0.01)


def test_winner_nets_fees_and_slippage_per_side() -> None:
    # 100 sh, 100 -> 110: gross 1000; costs = 210 * 100 * 0.0015 = 31.50
    result = pnl.dollar_pnl(100.0, 110.0, 100.0)
    assert result is not None
    assert result["pnl_gross_usd"] == 1000.0
    assert result["costs_usd"] == 31.5
    assert result["pnl_usd"] == 968.5


def test_missing_or_zero_shares_returns_none() -> None:
    assert pnl.dollar_pnl(100.0, 110.0, None) is None
    assert pnl.dollar_pnl(100.0, 110.0, 0) is None
    assert pnl.dollar_pnl("", 110.0, 10) is None
    assert pnl.dollar_pnl(100.0, "nan", 10) is None


def test_plan_metrics_match_the_gate_geometry() -> None:
    # DUK's stored plan: zone 122.57-125.37, stop 111.84, targets 131.82,
    # 132.18 and a third structural level ~248.70. The gate recorded 10.28.
    result = pnl.plan_metrics(122.57, 125.37, 111.84, [131.82, 132.18, 248.70])
    assert result is not None
    assert result["entry_basis"] == pytest.approx(123.97, abs=0.01)
    assert result["target_1_r"] == pytest.approx(0.65, abs=0.01)
    assert result["plan_rr"] == pytest.approx(10.28, abs=0.02)


def test_plan_metrics_single_entry_price() -> None:
    result = pnl.plan_metrics(100.0, None, 90.0, [110.0, 120.0])
    assert result is not None
    assert result["plan_rr"] == 2.0
    assert result["target_1_r"] == 1.0


def test_plan_metrics_degenerate_geometry_returns_none() -> None:
    assert pnl.plan_metrics(100.0, 101.0, 100.5, [110.0]) is None
    assert pnl.plan_metrics(100.0, 101.0, 90.0, []) is None
