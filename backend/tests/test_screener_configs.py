"""Tests for screen configuration loading and validation."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from backend.app.infrastructure.screener.configs import (
    FilterRule,
    ScreenConfig,
    list_screen_templates,
    load_screen_template,
)
from backend.app.infrastructure.screener.models import (
    FilterRunResult,
    ScreenRunResult,
    ScreenStreamMessage,
)


class TestScreenConfig:
    """Test ScreenConfig model validation."""

    def test_valid_config_loads(self) -> None:
        """A valid ScreenConfig with proper filters loads without error."""
        config = ScreenConfig(
            name="Test Screen",
            description="A test screen",
            asset_classes=["equities"],
            timeframes=["1D"],
            filters=[
                FilterRule(
                    category="momentum",
                    indicator="rsi_oversold",
                    params={"threshold": 30},
                    timeframe="1D",
                ),
            ],
        )
        assert config.name == "Test Screen"

    def test_invalid_filter_name_raises_error(self) -> None:
        """Using an unregistered filter name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown filter"):
            ScreenConfig(
                name="Bad Screen",
                filters=[
                    FilterRule(
                        category="momentum",
                        indicator="nonexistent_filter",
                        timeframe="1D",
                    ),
                ],
            )

    def test_default_values(self) -> None:
        """ScreenConfig assigns sensible defaults."""
        config = ScreenConfig(name="Minimal")
        assert config.asset_classes == ["equities", "crypto"]
        assert config.timeframes == ["1D", "4h"]
        assert config.filters == []


class TestFilterRule:
    """Test FilterRule model defaults and validation."""

    def test_default_values(self) -> None:
        rule = FilterRule(category="trend", indicator="price_above_ema")
        assert rule.operator == "gt"
        assert rule.timeframe == "1D"
        assert rule.params == {}
        assert rule.negate is False

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValueError, match="extra_forbidden"):
            FilterRule(
                category="trend",
                indicator="adx_trending",
                unknown_field="test",  # type: ignore[call-arg]
            )


class TestScreenTemplates:
    """Test YAML template loading."""

    def test_trend_follower_loads(self) -> None:
        config = load_screen_template("trend-follower")
        assert config.name == "Trend Follower"
        assert len(config.filters) == 4

    def test_mean_reversion_loads(self) -> None:
        config = load_screen_template("mean-reversion")
        assert config.name == "Mean Reversion"
        assert len(config.filters) == 3

    def test_breakout_loads(self) -> None:
        config = load_screen_template("breakout")
        assert config.name == "Breakout"
        assert len(config.filters) == 3

    def test_volume_surge_loads(self) -> None:
        config = load_screen_template("volume-surge")
        assert config.name == "Volume Surge"
        assert len(config.filters) == 3

    def test_oversold_bounce_loads(self) -> None:
        config = load_screen_template("oversold-bounce")
        assert config.name == "Oversold Bounce"
        assert len(config.filters) == 3

    def test_list_screen_templates_returns_5(self) -> None:
        templates = list_screen_templates()
        assert len(templates) >= 5

    def test_missing_template_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_screen_template("nonexistent_template")


class TestScreenRunResult:
    """Test ScreenRunResult serialization."""

    def test_model_serialization(self) -> None:
        result = ScreenRunResult(
            screen_name="Test",
            timestamp=datetime.now(UTC),
            duration_ms=100.0,
            total_symbols=100,
            symbols_matched=25,
            filter_results=[
                FilterRunResult(
                    filter_name="rsi_oversold",
                    category="momentum",
                    matched=25,
                    total=100,
                    pass_rate=0.25,
                ),
            ],
        )
        data = result.model_dump(mode="json")
        assert data["screen_name"] == "Test"
        assert data["symbols_matched"] == 25
        assert len(data["filter_results"]) == 1


class TestScreenStreamMessage:
    """Test ScreenStreamMessage types."""

    def test_screen_update_type(self) -> None:
        msg = ScreenStreamMessage(
            type="screen_update",
            screen_id="trend-follower",
            timestamp=datetime.now(UTC),
            total_matched=10,
            total_symbols=100,
        )
        assert msg.type == "screen_update"

    def test_delta_update_type(self) -> None:
        msg = ScreenStreamMessage(
            type="delta_update",
            screen_id="trend-follower",
            timestamp=datetime.now(UTC),
            added=[{"symbol": "AAPL", "score": 100.0}],
        )
        assert msg.type == "delta_update"
        assert len(msg.added) == 1

    def test_error_type(self) -> None:
        msg = ScreenStreamMessage(
            type="error",
            screen_id="trend-follower",
            timestamp=datetime.now(UTC),
        )
        assert msg.type == "error"
