"""Tests for screen configuration loading and validation."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

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


class TestRegimeScreensConfig:
    """Guard: every template referenced by config/regime_screens.yaml must load.

    The short-squeeze deletion (D-61) left stale references behind once already;
    this test makes that class of drift fail loudly instead of rotting silently.
    """

    def test_regime_map_templates_all_load(self) -> None:
        config_path = Path(__file__).resolve().parents[2] / "config" / "regime_screens.yaml"
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))

        failures: list[str] = []
        for regime, entries in (data.get("regimes") or {}).items():
            for entry in entries or []:
                name = entry.get("name")
                if not name:
                    failures.append(f"{regime}: entry missing 'name'")
                    continue
                try:
                    load_screen_template(name)
                except Exception as exc:  # noqa: BLE001 — collect every failure
                    failures.append(f"{regime}: {name}: {exc}")

        assert not failures, f"regime_screens.yaml references unloadable templates: {failures}"



