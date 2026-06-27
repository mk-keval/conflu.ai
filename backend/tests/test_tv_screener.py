"""Tests for TV Screener API — request/response model validation + endpoint helpers.

No FastAPI test client calls; focuses on model validation and helper logic.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.app.infrastructure.screener.tv_models import (
    TVScreenRequest,
    TVScreenResponse,
    ScoredTickerResponse,
    DeepAnalysisRequest,
    DeepAnalysisResponse,
    dict_to_screen_config,
)


class TestTVScreenRequest:
    """Test TVScreenRequest model validation."""

    def test_valid_config_dict(self) -> None:
        req = TVScreenRequest(config={"name": "Test", "filters": []})
        assert isinstance(req.config, dict)
        assert req.config["name"] == "Test"

    def test_valid_config_string(self) -> None:
        req = TVScreenRequest(config="trend-follower")
        assert isinstance(req.config, str)

    def test_limit_default(self) -> None:
        req = TVScreenRequest(config={})
        assert req.limit == 500

    def test_limit_minimum(self) -> None:
        TVScreenRequest(config={}, limit=1)  # should pass

    def test_limit_below_min_raises(self) -> None:
        with pytest.raises(ValidationError):
            TVScreenRequest(config={}, limit=0)

    def test_limit_above_max_raises(self) -> None:
        with pytest.raises(ValidationError):
            TVScreenRequest(config={}, limit=2001)

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            TVScreenRequest.model_validate({"config": {}, "unknown_field": "test"})


class TestTVScreenResponse:
    """Test TVScreenResponse model."""

    def test_valid_response(self) -> None:
        ticker = ScoredTickerResponse(
            symbol="AAPL",
            score=75,
            breakdown={"momentum": 25, "trend": 25, "volume": 25},
            entry=180.0,
            stop_loss=175.0,
            targets=[185.0, 190.0],
            risk_reward=2.0,
            rating="Strong Buy",
            tv_data={"close": 180.0},
        )
        resp = TVScreenResponse(
            screen_name="Test",
            total_matches=1,
            execution_ms=100,
            timeframe="1D",
            results=[ticker],
        )
        assert resp.screen_name == "Test"
        assert len(resp.results) == 1


class TestDeepAnalysisRequest:
    """Test DeepAnalysisRequest model."""

    def test_valid_request(self) -> None:
        req = DeepAnalysisRequest(symbol="AAPL")
        assert req.timeframe == "1D"
        assert req.include_backtest is True
        assert req.include_risk is True

    def test_symbol_required(self) -> None:
        with pytest.raises(ValidationError):
            DeepAnalysisRequest.model_validate({"timeframe": "4h"})

    def test_custom_timeframe(self) -> None:
        req = DeepAnalysisRequest(symbol="BTC", timeframe="4h")
        assert req.timeframe == "4h"

    def test_optional_analysis_disabled(self) -> None:
        req = DeepAnalysisRequest(symbol="ETH", include_backtest=False, include_risk=False)
        assert req.include_backtest is False
        assert req.include_risk is False


class TestDeepAnalysisResponse:
    """Test DeepAnalysisResponse model."""

    def test_minimal_response(self) -> None:
        resp = DeepAnalysisResponse(
            symbol="AAPL",
            timeframe="1D",
            tv_discovery={"close": 180.0},
            execution_ms=100,
        )
        assert resp.confluence is None
        assert resp.backtest is None

    def test_full_response(self) -> None:
        resp = DeepAnalysisResponse(
            symbol="AAPL",
            timeframe="1D",
            tv_discovery={"close": 180.0},
            confluence={"score": 75},
            backtest={"total_trades": 10},
            risk={"var": 0.02},
            execution_ms=200,
        )
        assert resp.confluence is not None
        assert resp.backtest is not None
        assert resp.risk is not None


class TestDictToScreenConfig:
    """Test dict_to_screen_config helper."""

    def test_minimal_config(self) -> None:
        config = dict_to_screen_config({"name": "Test"})
        assert config.name == "Test"
        assert config.filters == []

    def test_with_filters(self) -> None:
        data = {
            "name": "Test Filters",
            "filters": [
                {
                    "category": "momentum",
                    "indicator": "rsi_oversold",
                    "params": {"threshold": 30},
                    "timeframe": "1D",
                },
            ],
        }
        config = dict_to_screen_config(data)
        assert len(config.filters) == 1
        assert config.filters[0].indicator == "rsi_oversold"
        assert config.filters[0].params["threshold"] == 30

    def test_with_universe(self) -> None:
        data = {
            "name": "Test Universe",
            "universe": {"markets": ["america"], "index": "SPX"},
        }
        config = dict_to_screen_config(data)
        assert config.universe is not None
        assert config.universe.index == "SPX"
        assert config.universe.markets == ["america"]

    def test_default_universe(self) -> None:
        config = dict_to_screen_config({"name": "No Universe"})
        assert config.universe is not None
        assert config.universe.markets == ["america"]
