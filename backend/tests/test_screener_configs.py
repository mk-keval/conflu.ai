"""Tests for screen configuration loading and validation."""

from __future__ import annotations

import pytest

from backend.app.infrastructure.screener.configs import (
    FilterRule,
    ScreenConfig,
    list_screen_templates,
    load_screen_template,
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
        assert len(config.filters) == 10

    def test_mean_reversion_loads(self) -> None:
        config = load_screen_template("mean-reversion")
        assert config.name == "Mean Reversion"
        assert len(config.filters) == 9

    def test_breakdown_loads(self) -> None:
        config = load_screen_template("breakdown")
        assert config.name == "Breakdown"
        assert len(config.filters) >= 9

    def test_vcp_breakout_loads(self) -> None:
        config = load_screen_template("vcp-breakout")
        assert config.name == "vcp-breakout"
        assert len(config.filters) >= 9

    def test_distribution_loads(self) -> None:
        config = load_screen_template("distribution")
        assert config.name == "Distribution"
        assert len(config.filters) >= 9

    def test_list_screen_templates_returns_5(self) -> None:
        templates = list_screen_templates()
        assert len(templates) >= 5

    def test_missing_template_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_screen_template("nonexistent_template")



