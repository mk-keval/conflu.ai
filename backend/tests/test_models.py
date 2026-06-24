"""Tests for domain Pydantic models."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from backend.app.domain.models import (
    OHLCV,
    BacktestConfig,
    Metrics,
    Position,
    RiskParams,
    ScreenResult,
    Signal,
    Trade,
)


class TestOHLCV:
    def test_valid(self, sample_ohlcv_row: dict[str, object]) -> None:
        ohlcv = OHLCV(**sample_ohlcv_row)  # type: ignore[arg-type]
        assert ohlcv.symbol == "AAPL"
        assert ohlcv.close == 151.5

    def test_frozen(self, sample_ohlcv_row: dict[str, object]) -> None:
        ohlcv = OHLCV(**sample_ohlcv_row)  # type: ignore[arg-type]
        with pytest.raises(ValidationError):
            ohlcv.symbol = "MSFT"

    def test_naive_timestamp_raises(self) -> None:
        data: dict[str, object] = {
            "symbol": "AAPL",
            "timestamp": datetime(2024, 1, 1),  # naive — no tzinfo
            "open": 150.0,
            "high": 152.0,
            "low": 149.0,
            "close": 151.0,
            "volume": 10000,
            "timeframe": "1D",
            "asset_class": "equities",
        }
        with pytest.raises(ValidationError, match="timezone-aware"):
            OHLCV(**data)  # type: ignore[arg-type]

    def test_extra_field_forbidden(self, sample_ohlcv_row: dict[str, object]) -> None:
        with pytest.raises(ValidationError):
            OHLCV(**sample_ohlcv_row, extra_field="should_fail")  # type: ignore[arg-type,call-arg]


class TestSignal:
    def test_valid(self) -> None:
        s = Signal(
            symbol="AAPL",
            timestamp=datetime(2024, 1, 1, tzinfo=UTC),
            direction="buy",
        )
        assert s.direction == "buy"
        assert s.strength == 1.0

    def test_invalid_direction(self) -> None:
        with pytest.raises(ValidationError):
            Signal(
                symbol="AAPL",
                timestamp=datetime(2024, 1, 1, tzinfo=UTC),
                direction="invalid",  # type: ignore[arg-type]
            )

    def test_strength_out_of_range(self) -> None:
        with pytest.raises(ValidationError):
            Signal(
                symbol="AAPL",
                timestamp=datetime(2024, 1, 1, tzinfo=UTC),
                direction="buy",
                strength=1.5,
            )


class TestMetrics:
    def test_all_optional(self) -> None:
        m = Metrics()
        assert m.sharpe is None

    def test_win_rate_bounds(self) -> None:
        with pytest.raises(ValidationError):
            Metrics(win_rate=1.5)


class TestBacktestConfig:
    def test_defaults(self) -> None:
        cfg = BacktestConfig(
            symbols=["AAPL", "SPY"],
            start=datetime(2024, 1, 1, tzinfo=UTC),
            end=datetime(2024, 12, 31, tzinfo=UTC),
        )
        assert cfg.initial_cash == 100_000.0
        assert cfg.position_sizing == "fixed"

    def test_naive_timestamp_raises(self) -> None:
        with pytest.raises(ValidationError):
            BacktestConfig(
                symbols=["AAPL"],
                start=datetime(2024, 1, 1),  # naive
                end=datetime(2024, 12, 31, tzinfo=UTC),
            )


class TestRiskParams:
    def test_defaults(self) -> None:
        r = RiskParams()
        assert r.risk_per_trade == 0.01
        assert r.kelly_fraction == 0.5

    def test_risk_per_trade_bounds(self) -> None:
        with pytest.raises(ValidationError):
            RiskParams(risk_per_trade=0.0)
        with pytest.raises(ValidationError):
            RiskParams(risk_per_trade=0.2)


class TestTrade:
    def test_minimal(self) -> None:
        t = Trade(
            symbol="AAPL",
            entry_time=datetime(2024, 1, 1, tzinfo=UTC),
            entry_price=150.0,
            size=100,
        )
        assert t.exit_time is None


class TestPosition:
    def test_minimal(self) -> None:
        p = Position(
            symbol="AAPL",
            entry_time=datetime(2024, 1, 1, tzinfo=UTC),
            entry_price=150.0,
            size=100,
        )
        assert p.pnl is None


class TestScreenResult:
    def test_empty_signals(self) -> None:
        sr = ScreenResult(
            symbol="AAPL",
            timestamp=datetime(2024, 1, 1, tzinfo=UTC),
        )
        assert sr.signals == []
        assert sr.indicators == {}
