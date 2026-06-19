"""Tests for scoring engine."""

from __future__ import annotations

import pandas as pd
import pytest

from backend.app.infrastructure.screener.scoring import (
    compute_pass_rates,
    compute_score,
    rank_results,
)


class TestComputeScore:
    """Test score computation."""

    def test_binary_score_all_pass(self) -> None:
        """All symbols pass -> score 100.0 for all."""
        mask = pd.Series([True, True, True])
        scores = compute_score(mask, total_filters=3)
        assert (scores == 100.0).all()

    def test_binary_score_none_pass(self) -> None:
        """No symbols pass -> score 0.0 for all."""
        mask = pd.Series([False, False, False])
        scores = compute_score(mask, total_filters=3)
        assert (scores == 0.0).all()

    def test_binary_score_mixed(self) -> None:
        """Some pass, some don't."""
        mask = pd.Series([True, False, True])
        scores = compute_score(mask, total_filters=2)
        assert scores.iloc[0] == 100.0
        assert scores.iloc[1] == 0.0
        assert scores.iloc[2] == 100.0

    def test_nuanced_score_with_per_filter(self) -> None:
        """With per_filter_masks, score reflects fraction passed."""
        mask = pd.Series([True, False, True])
        per_filter = {
            "filter_a": pd.Series([True, True, False]),
            "filter_b": pd.Series([True, False, True]),
        }
        scores = compute_score(mask, total_filters=2, per_filter_masks=per_filter)
        # Symbol 0 passed 2/2 = 100.0
        assert scores.iloc[0] == 100.0
        # Symbol 1 passed 1/2 = 50.0
        assert scores.iloc[1] == 50.0
        # Symbol 2 passed 1/2 = 50.0
        assert scores.iloc[2] == 50.0

    def test_score_clipped_to_100(self) -> None:
        """Score is clipped to 100 max."""
        mask = pd.Series([True])
        per_filter = {
            "a": pd.Series([True]),
            "b": pd.Series([True]),
        }
        scores = compute_score(mask, total_filters=1, per_filter_masks=per_filter)
        # Passed 2/1, should be clipped to 100
        assert scores.iloc[0] == 100.0

    def test_score_empty_mask(self) -> None:
        """Empty mask produces empty scores."""
        mask = pd.Series(dtype=bool)
        scores = compute_score(mask, total_filters=0)
        assert scores.empty


class TestComputePassRates:
    """Test pass rate computation."""

    def test_all_pass(self) -> None:
        rates = compute_pass_rates({
            "filter_a": pd.Series([True, True, True]),
        })
        assert rates["filter_a"] == 1.0

    def test_some_pass(self) -> None:
        rates = compute_pass_rates({
            "filter_a": pd.Series([True, False, True]),
        })
        assert rates["filter_a"] == pytest.approx(0.6667, rel=0.01)

    def test_all_fail(self) -> None:
        rates = compute_pass_rates({
            "filter_a": pd.Series([False, False, False]),
        })
        assert rates["filter_a"] == 0.0

    def test_empty_mask(self) -> None:
        rates = compute_pass_rates({"filter_a": pd.Series(dtype=bool)})
        assert rates["filter_a"] == 0.0

    def test_multiple_filters(self) -> None:
        rates = compute_pass_rates({
            "a": pd.Series([True, True, False]),
            "b": pd.Series([False, True, False]),
        })
        assert rates["a"] == pytest.approx(0.6667, rel=0.01)
        assert rates["b"] == pytest.approx(0.3333, rel=0.01)


class TestRankResults:
    """Test score ranking."""

    def test_descending_default(self) -> None:
        """Default is descending (highest score = rank 1)."""
        scores = pd.Series([80.0, 100.0, 60.0], index=["A", "B", "C"])
        ranks = rank_results(scores)
        assert ranks["B"] == 1  # Highest score
        assert ranks["A"] == 2
        assert ranks["C"] == 3

    def test_ascending(self) -> None:
        """Ascending ranking: lowest score = rank 1."""
        scores = pd.Series([80.0, 100.0, 60.0], index=["A", "B", "C"])
        ranks = rank_results(scores, ascending=True)
        assert ranks["C"] == 1  # Lowest score
        assert ranks["A"] == 2
        assert ranks["B"] == 3

    def test_ties_get_same_rank(self) -> None:
        """Tied scores get the same minimum rank."""
        scores = pd.Series([100.0, 100.0, 80.0])
        ranks = rank_results(scores)
        assert ranks.iloc[0] == 1
        assert ranks.iloc[1] == 1
        assert ranks.iloc[2] == 3
