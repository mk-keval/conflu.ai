"""Tests for vectorized indicator computation."""

from __future__ import annotations

import pandas as pd

from backend.app.infrastructure.indicators import (
    compute_all,
    compute_atr,
    compute_ema,
    compute_macd,
    compute_rsi,
    compute_sma,
    list_indicators,
)


class TestIndicatorRegistry:
    def test_list_indicators(self) -> None:
        registry = list_indicators()
        assert "rsi" in registry
        assert "macd" in registry
        assert "ema" in registry
        assert "sma" in registry
        assert "atr" in registry

    def test_compute_all(self, synthetic_ohlcv: pd.DataFrame) -> None:
        results = compute_all(synthetic_ohlcv)
        assert isinstance(results, dict)
        assert "rsi" in results
        assert "macd" in results


class TestComputeRsi:
    def test_output_columns(self, synthetic_ohlcv: pd.DataFrame) -> None:
        result = compute_rsi(synthetic_ohlcv)
        assert "symbol" in result.columns
        assert "timestamp" in result.columns
        assert "indicator_name" in result.columns
        assert "value" in result.columns

    def test_rsi_bounded(self, synthetic_ohlcv: pd.DataFrame) -> None:
        result = compute_rsi(synthetic_ohlcv)
        values = result["value"].dropna()
        assert (values >= 0).all()
        assert (values <= 100).all()

    def test_rsi_length(self, synthetic_ohlcv: pd.DataFrame) -> None:
        result_14 = compute_rsi(synthetic_ohlcv, length=14)
        result_7 = compute_rsi(synthetic_ohlcv, length=7)
        assert len(result_14["value"].dropna()) <= len(result_7["value"].dropna())


class TestComputeMacd:
    def test_output_shape(self, synthetic_ohlcv: pd.DataFrame) -> None:
        result = compute_macd(synthetic_ohlcv)
        assert not result.empty
        assert result["indicator_name"].nunique() == 3


class TestComputeEma:
    def test_output_shape(self, synthetic_ohlcv: pd.DataFrame) -> None:
        result = compute_ema(synthetic_ohlcv)
        assert result["indicator_name"].iloc[0] == "ema_20"


class TestComputeSma:
    def test_output_shape(self, synthetic_ohlcv: pd.DataFrame) -> None:
        result = compute_sma(synthetic_ohlcv)
        assert result["indicator_name"].iloc[0] == "sma_50"


class TestComputeAtr:
    def test_positive_values(self, synthetic_ohlcv: pd.DataFrame) -> None:
        result = compute_atr(synthetic_ohlcv)
        values = result["value"].dropna()
        assert (values >= 0).all()
