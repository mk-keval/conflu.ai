"""Risk sizing tests (plan Sec.2D)."""

from __future__ import annotations

import pytest

from backend.app.domain.workflow import sizing


def test_sizing_inverse_to_stop_distance() -> None:
    """1% risk on a 5% stop → 20% size; on a 2% stop → 40% but capped at 25%."""
    assert sizing.compute_position_size_pct(100.0, 95.0, "PASS") == pytest.approx(20.0)
    assert sizing.compute_position_size_pct(100.0, 98.0, "PASS") == pytest.approx(25.0)  # capped
    assert sizing.stop_distance_pct(100.0, 95.0) == pytest.approx(5.0)


def test_sizing_halves_on_conditional() -> None:
    """CONDITIONAL verdict → half size (the plan's ×0.5)."""
    assert sizing.compute_position_size_pct(100.0, 95.0, "CONDITIONAL") == pytest.approx(10.0)
    assert sizing.compute_position_size_pct(100.0, 98.0, "CONDITIONAL") == pytest.approx(12.5)


def test_sizing_respects_floor() -> None:
    """Risk-driven size that lands below MIN_SIZE_PCT is floored, never 0."""
    # 0.25% risk budget on a 50% stop → 0.5% = the floor exactly.
    assert sizing.compute_position_size_pct(
        100.0, 50.0, "PASS", risk_budget_pct=0.25
    ) == pytest.approx(sizing.MIN_SIZE_PCT)
    # Even smaller implied size cannot push below the floor.
    assert sizing.compute_position_size_pct(
        100.0, 50.0, "PASS", risk_budget_pct=0.1
    ) == pytest.approx(sizing.MIN_SIZE_PCT)


def test_sizing_rejects_degenerate_geometry() -> None:
    with pytest.raises(ValueError):
        sizing.compute_position_size_pct(0.0, -1.0, "PASS")
    with pytest.raises(ValueError):
        sizing.compute_position_size_pct(100.0, 100.0, "PASS")  # stop == entry
    with pytest.raises(ValueError):
        sizing.compute_position_size_pct(100.0, 110.0, "PASS")  # stop above entry
    with pytest.raises(ValueError):
        sizing.compute_position_size_pct(float("nan"), 95.0, "PASS")


def test_sizing_custom_cap_and_budget() -> None:
    assert sizing.compute_position_size_pct(
        100.0, 95.0, "PASS", cap=15.0
    ) == pytest.approx(15.0)  # 20% would be natural, capped
    assert sizing.compute_position_size_pct(
        100.0, 95.0, "PASS", risk_budget_pct=2.0
    ) == pytest.approx(25.0)  # 40% natural → capped at 25%


def test_sizing_none_verdict_is_pass_behavior() -> None:
    """Unknown/None verdict → sized like PASS (no halving)."""
    assert sizing.compute_position_size_pct(100.0, 95.0, None) == pytest.approx(20.0)