"""Tests for RegimeScreenSelector — config-driven per-regime screen weights (P1.1).

Covers the RC1 fix: NEUTRAL/CHOPPY regimes must surface momentum/breakout/
catalyst screens as PRIMARY with exactly one defensive secondary, instead of
collapsing into all-defensive mean-reversion lists.
"""

from __future__ import annotations

from typing import Any

import pytest

from backend.app.infrastructure.professional import regime_selector as rs
from backend.app.infrastructure.screener.configs import ScreenConfig, load_screen_template


def _display(stem: str) -> str:
    """Map a filename stem to the ScreenConfig display name its YAML carries."""
    return load_screen_template(stem).name


@pytest.fixture(autouse=True)
def _fresh_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate module-level caches between tests."""
    monkeypatch.setattr(rs, "_selector_cache", {})
    monkeypatch.setattr(rs, "_regime_config_cache", None)


def _install_config(monkeypatch: pytest.MonkeyPatch, regimes: dict[str, Any]) -> None:
    """Point the selector at an in-memory regime config."""
    monkeypatch.setattr(rs, "_regime_config_cache", regimes)


class TestConfigDrivenSelection:
    """Config path: weighted top-3 with one defensive secondary."""

    def test_neutral_surfaces_momentum_primary_with_defensive(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_config(monkeypatch, {
            "neutral": [
                {"name": "52week-breakout", "weight": 90},
                {"name": "vcp-breakout", "weight": 85},
                {"name": "volume-trend-accumulation", "weight": 80},
                {"name": "bull-flag-continuation", "weight": 75},
                {"role": "defensive", "name": "statistical-mean-reversion", "weight": 60},
            ],
        })

        selector = rs.RegimeScreenSelector()
        screens = selector.select_top_screens("neutral")

        assert len(screens) == 3
        names = [s.name for s in screens]
        # Top-2 primaries by weight + defensive secondary replacing slot 3
        assert names[0] == _display("52week-breakout")
        assert names[1] == _display("vcp-breakout")
        assert names[2] == _display("statistical-mean-reversion")
        assert all(isinstance(s, ScreenConfig) for s in screens)

    def test_defensive_appended_last_when_slots_free(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Primaries keep weight order; the defensive secondary goes last."""
        _install_config(monkeypatch, {
            "choppy": [
                {"name": "bull-flag-continuation", "weight": 85},
                {"role": "defensive", "name": "low-vol-setup", "weight": 70},
                {"name": "vcp-breakout", "weight": 65},
            ],
        })

        screens = rs.RegimeScreenSelector().select_top_screens("choppy")
        names = [s.name for s in screens]
        assert names == [
            _display("bull-flag-continuation"),
            _display("vcp-breakout"),
            _display("low-vol-setup"),
        ]

    def test_weights_order_respected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_config(monkeypatch, {
            "strong_trend": [
                {"name": "quality-trend-fundamentals", "weight": 60},
                {"name": "trend-follower", "weight": 95},
                {"name": "52week-breakout", "weight": 85},
            ],
        })

        screens = rs.RegimeScreenSelector().select_top_screens("strong_trend")
        assert [s.name for s in screens] == [
            _display("trend-follower"),
            _display("52week-breakout"),
            _display("quality-trend-fundamentals"),
        ]

    def test_fewer_than_three_entries_returns_all(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_config(monkeypatch, {
            "ranging": [
                {"name": "mean-reversion", "weight": 80},
                {"role": "defensive", "name": "low-vol-setup", "weight": 50},
            ],
        })

        screens = rs.RegimeScreenSelector().select_top_screens("ranging")
        assert len(screens) == 2


class TestConfigFallbacks:
    """Missing/garbage config must degrade to heuristic/fallback paths."""

    def test_missing_regime_key_uses_fallback_map(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_config(monkeypatch, {"unrelated": []})

        screens = rs.RegimeScreenSelector().select_top_screens("strong_trend")
        # Hardcoded fallback map for strong_trend (no YAML carries `regime`).
        names = [s.name for s in screens]
        assert names == [_display(x) for x in ("trend-follower", "52week-breakout", "bull-flag-continuation")]

    def test_empty_config_dict_uses_fallback_map(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_config(monkeypatch, {})

        screens = rs.RegimeScreenSelector().select_top_screens("ranging")
        assert [s.name for s in screens] == [
            _display(x) for x in ("mean-reversion", "low-vol-setup", "statistical-mean-reversion")
        ]

    def test_malformed_entries_skipped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_config(monkeypatch, {
            "neutral": [
                "garbage-string",
                {"no_name_field": True, "weight": 99},
                {"name": "  ", "weight": 98},  # blank name
                {"name": "vcp-breakout", "weight": "not-a-number"},  # bad weight -> 0.0
                {"name": "52week-breakout", "weight": 90},
                {"role": "defensive", "name": "statistical-mean-reversion", "weight": 60},
            ],
        })

        screens = rs.RegimeScreenSelector().select_top_screens("neutral")
        names = [s.name for s in screens]
        assert _display("52week-breakout") in names
        assert len(names) == 3

    def test_failed_template_load_backfills_from_remaining(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A primary whose template fails to load is replaced by the next
        weighted candidate so NEUTRAL still gets a full three-screen mix."""
        _install_config(monkeypatch, {
            "neutral": [
                {"name": "does-not-exist", "weight": 95},
                {"name": "52week-breakout", "weight": 90},
                {"name": "vcp-breakout", "weight": 85},
                {"name": "bull-flag-continuation", "weight": 75},
                {"role": "defensive", "name": "statistical-mean-reversion", "weight": 60},
            ],
        })

        screens = rs.RegimeScreenSelector().select_top_screens("neutral")
        names = [s.name for s in screens]
        assert len(names) == 3
        assert set(names) == {
            _display(x) for x in ("52week-breakout", "vcp-breakout", "statistical-mean-reversion")
        }


class TestResponseContractUnchanged:
    """Identical response schema mandate: list[ScreenConfig] in, same as before."""

    def test_result_is_plain_screenconfig_list(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_config(monkeypatch, {
            "neutral": [
                {"name": "52week-breakout", "weight": 90},
                {"name": "vcp-breakout", "weight": 85},
                {"role": "defensive", "name": "statistical-mean-reversion", "weight": 60},
            ],
        })

        result = rs.RegimeScreenSelector().select_top_screens("neutral")
        assert isinstance(result, list)
        assert all(isinstance(s, ScreenConfig) for s in result)
        # ScreenConfigs carry the standard fields the brief pipeline consumes.
        first = result[0]
        assert first.filters, "loaded ScreenConfig should be fully populated from its YAML"

    def test_daily_cache_roundtrip(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_config(monkeypatch, {
            "neutral": [{"name": "52week-breakout", "weight": 90}],
        })
        selector = rs.RegimeScreenSelector()
        first = selector.select_top_screens("neutral")
        second = selector.select_top_screens("neutral")
        assert [s.name for s in first] == [s.name for s in second]
