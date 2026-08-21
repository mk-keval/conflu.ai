"""Tests for the earnings-proximity warning chip (P1.5).

Backend surfaces: ``EarningsAnalysis.days_until_earnings`` (analyze stage),
``TickerBrief.days_to_earnings`` (brief cards), and
``WatchlistItemResponse.days_to_earnings`` (watchlist rows).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.app.domain.ticker_analysis.earnings import analyze
from backend.app.infrastructure.professional.models import (
    TickerBrief,
    WatchlistItemResponse,
)


def _info_with_next_earnings(days_ahead: int) -> dict:
    ts = datetime.now(timezone.utc).astimezone() + timedelta(days=days_ahead)
    return {"earningsTimestampStart": int(ts.timestamp())}


def _brief(**overrides: object) -> TickerBrief:
    base: dict = {
        "symbol": "AAPL",
        "screen_name": "s",
        "screen_score": 0.8,
        "confluence_score": 80,
        "entry": 100.0,
        "stop_loss": 95.0,
        "targets": [110.0],
        "verdict": "BUY",
        "conviction": 7,
    }
    base.update(overrides)
    return TickerBrief(**base)  # type: ignore[arg-type]


class TestEarningsAnalysisProximity:
    @staticmethod
    def _assert_near(value: int | None, expected_days: int) -> None:
        # int(ts) truncation can shift the calendar-day delta by one.
        assert value is not None
        assert abs(value - expected_days) <= 1

    def test_upcoming_report_within_risk_window(self) -> None:
        result = analyze(_info_with_next_earnings(days_ahead=5))
        self._assert_near(result.days_until_earnings, 5)
        assert any("risk window" in f for f in result.findings)

    def test_report_far_out(self) -> None:
        result = analyze(_info_with_next_earnings(days_ahead=45))
        self._assert_near(result.days_until_earnings, 45)
        assert not any("risk window" in f for f in result.findings)

    def test_last_print_in_past(self) -> None:
        result = analyze(_info_with_next_earnings(days_ahead=-10))
        assert result.days_until_earnings is not None
        assert result.days_until_earnings < 0

    def test_no_timestamp_gives_none(self) -> None:
        result = analyze({})
        assert result.days_until_earnings is None


class TestChipFieldsAdditive:
    def test_brief_defaults_none(self) -> None:
        assert _brief().days_to_earnings is None

    def test_brief_accepts_days(self) -> None:
        assert _brief(days_to_earnings=4).days_to_earnings == 4

    def test_watchlist_item_defaults_none(self) -> None:
        item = WatchlistItemResponse(symbol="AAPL", verdict="BUY", conviction=6)
        assert item.days_to_earnings is None

    def test_watchlist_item_accepts_days(self) -> None:
        item = WatchlistItemResponse(
            symbol="AAPL", verdict="BUY", conviction=6, days_to_earnings=9
        )
        assert item.days_to_earnings == 9
