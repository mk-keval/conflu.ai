"""Tests for configuration management."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.app.core.config import (
    APISettings,
    AppSettings,
    ComputeSettings,
    CoreSettings,
    DataSettings,
    FrontendSettings,
)


class TestCoreSettings:
    def test_defaults(self) -> None:
        s = CoreSettings()
        assert s.duckdb_path == "data/conflu.duckdb"
        assert s.duckdb_data_dir == "data"
        assert s.log_level == "INFO"
        assert s.log_json is True

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CONFLU_CORE_LOG_LEVEL", "DEBUG")
        s = CoreSettings()
        assert s.log_level == "DEBUG"


class TestDataSettings:
    def test_timeframes(self) -> None:
        s = DataSettings()
        assert "1D" in s.timeframes
        assert "1h" in s.timeframes
        assert "15m" in s.timeframes

    def test_max_concurrent_bounds(self) -> None:
        with pytest.raises(ValidationError):
            DataSettings(max_concurrent=0)
        with pytest.raises(ValidationError):
            DataSettings(max_concurrent=300)


class TestComputeSettings:
    def test_default_indicator_timeframe(self) -> None:
        s = ComputeSettings()
        assert s.default_indicator_timeframe == "1D"

    def test_broadcast_indicators(self) -> None:
        s = ComputeSettings()
        assert "rsi" in s.broadcast_indicators


class TestAPISettings:
    def test_default_port(self) -> None:
        s = APISettings()
        assert s.port == 8000

    def test_rate_limit_positive(self) -> None:
        with pytest.raises(ValidationError):
            APISettings(rate_limit=0)


class TestFrontendSettings:
    def test_ws_endpoint(self) -> None:
        s = FrontendSettings()
        assert s.ws_endpoint == "ws://localhost:8000/ws"


class TestAppSettings:
    def test_nested_settings(self) -> None:
        s = AppSettings()
        assert isinstance(s.core, CoreSettings)
        assert isinstance(s.data, DataSettings)
        assert isinstance(s.compute, ComputeSettings)
        assert isinstance(s.api, APISettings)
        assert isinstance(s.frontend, FrontendSettings)

    def test_env_nested_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CONFLU_CORE__LOG_LEVEL", "DEBUG")
        s = AppSettings()
        assert s.core.log_level == "DEBUG"
