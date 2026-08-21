"""Tests for TVScreenEngine.screen_batch — One-Snapshot-Multi-Screen (P1.2).

Flag OFF (default) → legacy per-template path. Flag ON → ONE base snapshot
fetch + local masking, with circuit-breaker and fail-closed fallbacks.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pandas as pd
import pytest

from backend.app.core.config import settings
from backend.app.infrastructure.screener.configs import FilterRule, ScreenConfig
from backend.app.infrastructure.screener.snapshot_engine import (
    SnapshotMultiScreenEngine,
    _required_extra_columns,
    build_base_config,
)
from backend.app.infrastructure.screener.tv_engine import TVScreenEngine
from backend.app.infrastructure.screener.tv_specialist import TVDiscoveryResult


@pytest.fixture
def mock_specialist() -> MagicMock:
    """Mock specialist for upstream calls, with the REAL local evaluator attached.

    The P1.2 masking path must exercise genuine filter semantics, so
    ``evaluate_filters_local`` binds to a real specialist while every other
    upstream surface stays mocked.
    """
    from backend.app.infrastructure.screener.tv_specialist import TVScreenerSpecialist

    mock = MagicMock()
    real = TVScreenerSpecialist()
    mock.evaluate_filters_local = real.evaluate_filters_local
    mock.discover = AsyncMock(
        return_value=TVDiscoveryResult(
            screen_name="Test",
            total_matches=1,
            tickers=["AAPL"],
            execution_ms=100,
            raw_data=pd.DataFrame({
                "ticker": ["NASDAQ:AAPL"],
                "close": [180.0],
                "RSI": [55.0],
            }),
            timeframe="1D",
        )
    )
    return mock


@pytest.fixture
def engine(mock_specialist: MagicMock) -> TVScreenEngine:
    eng = TVScreenEngine()
    eng.specialist = mock_specialist  # type: ignore[assignment]
    return eng


def _snapshot_frame() -> pd.DataFrame:
    return pd.DataFrame({
        "ticker": ["NASDAQ:AAPL", "NASDAQ:MSFT", "NASDAQ:GOOG"],
        "close": [180.0, 420.0, 150.0],
        "RSI": [55.0, 75.0, 25.0],
        "relative_volume_10d_calc": [1.8, 1.1, 0.6],
        "exchange": ["NASDAQ"] * 3,
    })


@pytest.fixture
def two_configs() -> list[ScreenConfig]:
    momentum = ScreenConfig(
        name="Momentum Test",
        filters=[FilterRule(category="momentum", indicator="rsi_gt", params={"threshold": 50})],
    )
    oversold = ScreenConfig(
        name="Oversold Test",
        filters=[FilterRule(category="momentum", indicator="rsi_oversold", params={"threshold": 30})],
    )
    return [momentum, oversold]


@pytest.fixture
def snapshot_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Enable the flag and stub the upstream fetch to a canned frame."""
    monkeypatch.setattr(settings.screen, "snapshot_multi_screen", True)
    frame = _snapshot_frame()
    monkeypatch.setattr(
        SnapshotMultiScreenEngine,
        "fetch_snapshot",
        AsyncMock(return_value=frame),
    )


class TestRequiredExtraColumns:
    def test_no_dynamic_columns_for_standard_templates(self) -> None:
        config = ScreenConfig(
            name="x",
            filters=[FilterRule(category="momentum", indicator="rsi_gt")],
        )
        assert _required_extra_columns([config]) == []

    def test_period_param_adds_ema_column(self) -> None:
        config = ScreenConfig(
            name="x",
            filters=[
                FilterRule(
                    category="trend",
                    indicator="price_above_ema",
                    params={"period": 100},
                )
            ],
        )
        assert _required_extra_columns([config]) == ["EMA100"]

    def test_periods_list_and_fast_slow(self) -> None:
        stack = ScreenConfig(
            name="stack",
            filters=[
                FilterRule(
                    category="trend",
                    indicator="price_above_emas",
                    params={"periods": [20, 100]},
                )
            ],
        )
        cross = ScreenConfig(
            name="cross",
            filters=[
                FilterRule(
                    category="trend",
                    indicator="ema_cross",
                    params={"fast": 9, "slow": 21},
                )
            ],
        )
        cols = _required_extra_columns([stack, cross])
        assert set(cols) == {"EMA9", "EMA21", "EMA100"}


class TestBuildBaseConfig:
    def test_base_config_carries_universal_gates(self) -> None:
        base = build_base_config([], size=1200)
        assert base.name == "base-snapshot"
        assert base.limit == 1200
        indicators = {f.indicator for f in base.filters}
        assert indicators == {"exchange_in", "country_in", "close_above", "avg_volume_gt"}


class TestScreenBatchLegacyPaths:
    async def test_flag_off_defaults_to_legacy(
        self,
        engine: TVScreenEngine,
        mock_specialist: MagicMock,
        two_configs: list[ScreenConfig],
    ) -> None:
        assert settings.screen.snapshot_multi_screen is False
        results = await engine.screen_batch(two_configs)

        assert len(results) == 2
        assert all(isinstance(r, dict) for r in results)
        # Legacy path: one specialist.discover per template.
        assert mock_specialist.discover.call_count == 2

    async def test_breaker_open_forces_legacy_even_when_enabled(
        self,
        engine: TVScreenEngine,
        mock_specialist: MagicMock,
        two_configs: list[ScreenConfig],
        snapshot_env: None,
    ) -> None:
        for _ in range(25):
            engine.circuit_breaker.record_call()
        assert engine.circuit_breaker.is_open() is True

        results = await engine.screen_batch(two_configs)
        assert all(isinstance(r, dict) for r in results)
        assert mock_specialist.discover.call_count == 2  # legacy fan-out happened


class TestScreenBatchSnapshotPath:
    async def test_one_fetch_masks_all_templates_locally(
        self,
        engine: TVScreenEngine,
        mock_specialist: MagicMock,
        two_configs: list[ScreenConfig],
        snapshot_env: None,
    ) -> None:
        results = await engine.screen_batch(two_configs)

        assert len(results) == 2
        assert all(isinstance(r, dict) for r in results)
        dicts = [r for r in results if isinstance(r, dict)]
        by_name = {r["screen_name"]: r for r in dicts}
        # Local masks against the same 3-row snapshot:
        # RSI>50 → AAPL(55), MSFT(75); RSI<30 → GOOG(25)
        assert by_name["Momentum Test"]["total_matches"] == 2
        assert {r["symbol"] for r in by_name["Momentum Test"]["results"]} == {"AAPL", "MSFT"}
        assert by_name["Oversold Test"]["total_matches"] == 1
        assert by_name["Oversold Test"]["results"][0]["symbol"] == "GOOG"

        # THE point of P1.2: zero per-template upstream calls.
        assert mock_specialist.discover.call_count == 0

    async def test_snapshot_cached_across_calls(
        self, engine: TVScreenEngine, two_configs: list[ScreenConfig], snapshot_env: None
    ) -> None:
        await engine.screen_batch(two_configs)
        await engine.screen_batch(two_configs)
        fetch_mock = SnapshotMultiScreenEngine.fetch_snapshot
        assert isinstance(fetch_mock, AsyncMock)
        assert fetch_mock.await_count == 1

    async def test_empty_fetch_falls_back_to_legacy(
        self,
        engine: TVScreenEngine,
        mock_specialist: MagicMock,
        two_configs: list[ScreenConfig],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings.screen, "snapshot_multi_screen", True)
        monkeypatch.setattr(
            SnapshotMultiScreenEngine, "fetch_snapshot", AsyncMock(return_value=None)
        )

        results = await engine.screen_batch(two_configs)
        assert all(isinstance(r, dict) for r in results)
        assert mock_specialist.discover.call_count == 2  # legacy fallback ran

    async def test_fail_closed_template_falls_back_individually(
        self,
        engine: TVScreenEngine,
        mock_specialist: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
        snapshot_env: None,
    ) -> None:
        broken = ScreenConfig(
            name="Broken Template",
            filters=[
                FilterRule(
                    category="trend",
                    indicator="price_above_ema",
                    params={"period": 100},  # EMA100 not in the canned snapshot
                )
            ],
        )

        results = await engine.screen_batch([broken])
        assert len(results) == 1
        assert isinstance(results[0], dict)
        # Snapshot used (no batch-wide legacy), then single legacy call for broken one.
        assert mock_specialist.discover.call_count == 1

    async def test_per_item_exception_contract_preserved(
        self,
        engine: TVScreenEngine,
        mock_specialist: MagicMock,
        two_configs: list[ScreenConfig],
    ) -> None:
        """Legacy path surfaces failures as per-item exceptions, never raises."""
        mock_specialist.discover = AsyncMock(side_effect=RuntimeError("tv down"))
        results = await engine.screen_batch(two_configs)
        assert len(results) == 2
        assert all(isinstance(r, Exception) for r in results)
