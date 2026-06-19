"""Tests for CorrelationAnalyzer — symmetry, self-correlation, diversification score."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backend.app.infrastructure.risk.correlation import CorrelationAnalyzer


@pytest.fixture
def correlation_analyzer():
    return CorrelationAnalyzer()


class TestCorrelationProperties:
    def test_correlation_symmetry(self, correlation_analyzer):
        """corr(i,j) = corr(j,i)"""
        matrix = pd.DataFrame(
            [[1.0, 0.5, 0.3], [0.5, 1.0, 0.7], [0.3, 0.7, 1.0]],
            index=["AAPL", "MSFT", "GOOGL"],
            columns=["AAPL", "MSFT", "GOOGL"],
        )
        symbols = ["AAPL", "MSFT", "GOOGL"]
        for i, s1 in enumerate(symbols):
            for j, s2 in enumerate(symbols):
                assert abs(matrix.loc[s1, s2] - matrix.loc[s2, s1]) < 1e-10

    def test_self_correlation_is_one(self, correlation_analyzer):
        """corr(i,i) = 1.0"""
        matrix = pd.DataFrame(
            [[1.0, 0.5], [0.5, 1.0]],
            index=["AAPL", "MSFT"],
            columns=["AAPL", "MSFT"],
        )
        assert matrix.loc["AAPL", "AAPL"] == 1.0
        assert matrix.loc["MSFT", "MSFT"] == 1.0

    def test_diversification_score_range(self, correlation_analyzer):
        """0 ≤ diversification_score ≤ 1"""
        # Perfectly correlated
        matrix1 = pd.DataFrame(
            [[1.0, 1.0, 1.0], [1.0, 1.0, 1.0], [1.0, 1.0, 1.0]],
            index=["A", "B", "C"],
            columns=["A", "B", "C"],
        )
        score1 = correlation_analyzer._compute_diversification_score(matrix1, ["A", "B", "C"])
        assert score1 >= 0.0
        assert score1 <= 1.0

        # Perfectly uncorrelated
        matrix2 = pd.DataFrame(
            [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            index=["A", "B", "C"],
            columns=["A", "B", "C"],
        )
        score2 = correlation_analyzer._compute_diversification_score(matrix2, ["A", "B", "C"])
        assert score2 >= 0.0
        assert score2 <= 1.0

    def test_high_correlation_detection(self, correlation_analyzer):
        """High correlation pairs are detected above threshold."""
        matrix = pd.DataFrame(
            [[1.0, 0.95, 0.3], [0.95, 1.0, 0.4], [0.3, 0.4, 1.0]],
            index=["AAPL", "MSFT", "SPY"],
            columns=["AAPL", "MSFT", "SPY"],
        )
        pairs = correlation_analyzer._find_high_correlation_pairs(matrix, ["AAPL", "MSFT", "SPY"], threshold=0.8)
        assert len(pairs) == 1
        assert pairs[0]["symbols"] == ["AAPL", "MSFT"]

    def test_group_aggregation_symmetry(self, correlation_analyzer):
        """Group aggregation produces symmetric matrix."""
        matrix = pd.DataFrame(
            [[1.0, 0.5, 0.3], [0.5, 1.0, 0.2], [0.3, 0.2, 1.0]],
            index=["AAPL", "MSFT", "BTC"],
            columns=["AAPL", "MSFT", "BTC"],
        )
        group_map = {"AAPL": "Tech", "MSFT": "Tech", "BTC": "Crypto"}
        agg_matrix, labels = correlation_analyzer._aggregate_by_group(matrix, group_map)
        assert len(labels) == 2
        # Aggregated matrix should be symmetric
        assert abs(agg_matrix[0][1] - agg_matrix[1][0]) < 1e-10
