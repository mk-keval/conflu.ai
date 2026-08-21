"""Tests for the Catalyst-Breakout badge (P1.4).

Badge = recent EPS beat + rvol > 1.2 + within 3% of the 52-week high.
Structural inputs come from TV snapshot rows; EPS surprise rides along on
the same yfinance .info payload used for premarket quotes.
"""

from __future__ import annotations

import pytest

from backend.app.infrastructure.professional.models import TickerBrief
from backend.app.infrastructure.professional.morning_brief import _catalyst_breakout_state


def _tv(
    *,
    close: float = 98.0,
    high_52w: float = 100.0,
    rvol: float = 1.5,
) -> dict:
    return {
        "close": close,
        "price_52_week_high": high_52w,
        "relative_volume_10d_calc": rvol,
    }


class TestCatalystBreakoutState:
    def test_all_conditions_met(self) -> None:
        on, reason = _catalyst_breakout_state(_tv(), eps_surprise_pct=4.2)
        assert on is True
        assert reason is not None
        assert "EPS beat +4.2%" in reason
        assert "rvol 1.5x" in reason
        assert "52-week high" in reason

    def test_rvol_below_threshold_blocks(self) -> None:
        on, _ = _catalyst_breakout_state(_tv(rvol=1.19), eps_surprise_pct=5.0)
        assert on is False

    def test_far_from_high_blocks(self) -> None:
        on, _ = _catalyst_breakout_state(_tv(close=90.0, high_52w=100.0), eps_surprise_pct=5.0)
        assert on is False

    def test_eps_miss_blocks(self) -> None:
        on, _ = _catalyst_breakout_state(_tv(), eps_surprise_pct=-1.5)
        assert on is False

    def test_unknown_eps_blocks(self) -> None:
        """No data ⇒ no badge — never claim an unseen catalyst."""
        on, reason = _catalyst_breakout_state(_tv(), eps_surprise_pct=None)
        assert on is False
        assert reason is None

    def test_empty_tv_data_blocks(self) -> None:
        on, _ = _catalyst_breakout_state({}, eps_surprise_pct=5.0)
        assert on is False

    def test_boundary_exactly_at_proximity_threshold(self) -> None:
        # close == 97% of high → inside the band
        on, _ = _catalyst_breakout_state(
            _tv(close=97.0, high_52w=100.0), eps_surprise_pct=1.0
        )
        assert on is True

    def test_just_outside_proximity_band(self) -> None:
        on, _ = _catalyst_breakout_state(
            _tv(close=96.9, high_52w=100.0), eps_surprise_pct=1.0
        )
        assert on is False

    def test_garbage_values_block(self) -> None:
        tv = {"close": "abc", "price_52_week_high": None, "relative_volume_10d_calc": "x"}
        on, _ = _catalyst_breakout_state(tv, eps_surprise_pct=5.0)
        assert on is False

    def test_zero_52w_high_blocks(self) -> None:
        on, _ = _catalyst_breakout_state(
            _tv(close=50.0, high_52w=0.0), eps_surprise_pct=5.0
        )
        assert on is False


class TestTickerBriefBadgeFields:
    def test_badge_fields_default_off(self) -> None:
        brief = TickerBrief(
            symbol="AAPL",
            screen_name="s",
            screen_score=0.8,
            confluence_score=80,
            entry=100.0,
            stop_loss=95.0,
            targets=[110.0],
            verdict="BUY",
            conviction=7,
        )
        assert brief.catalyst_breakout is False
        assert brief.catalyst_breakout_reason is None

    def test_badge_fields_accept_values(self) -> None:
        brief = TickerBrief(
            symbol="AAPL",
            screen_name="s",
            screen_score=0.8,
            confluence_score=80,
            entry=100.0,
            stop_loss=95.0,
            targets=[110.0],
            verdict="BUY",
            conviction=7,
            catalyst_breakout=True,
            catalyst_breakout_reason="Catalyst breakout: EPS beat +3.0%",
        )
        assert brief.catalyst_breakout is True
        assert brief.catalyst_breakout_reason == "Catalyst breakout: EPS beat +3.0%"
