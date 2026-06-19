"""Score computation from matched filters and indicator values."""

from __future__ import annotations

import pandas as pd


def compute_score(
    mask: pd.Series,
    total_filters: int,
    per_filter_masks: dict[str, pd.Series] | None = None,
) -> pd.Series:
    """Compute fractional score for each symbol.

    Phase 3 uses Approach A: fraction-based scoring.
    score = (matched_filters / total_filters) x 100

    With multiple AND-combined filters, the score is binary:
    100.0 if all filters pass, 0.0 otherwise.

    When per_filter_masks is provided (for future OR-group support),
    computes a nuanced score: (sum of passed filters / total_filters) x 100.

    Args:
        mask: Boolean Series where True means the symbol passed all filters.
        total_filters: Total number of filter expressions.
        per_filter_masks: Optional dict of {filter_name: boolean_mask}
            for per-filter granularity.

    Returns:
        Series with float scores 0.0-100.0.
    """
    if per_filter_masks and total_filters > 1:
        # Nuanced scoring: count how many filters each symbol passed
        passed_count = sum(
            per_filter_masks[name].astype(int)
            for name in per_filter_masks
            if name in per_filter_masks
        )
        return (passed_count / total_filters * 100.0).clip(0, 100)

    # Binary: all or nothing (AND-combined)
    return mask.astype(float) * 100.0


def compute_pass_rates(
    per_filter_masks: dict[str, pd.Series],
) -> dict[str, float]:
    """Compute pass rate for each filter.

    Returns dict mapping filter_name -> pass_rate (0.0-1.0).
    pass_rate = number of True / total symbols.

    Args:
        per_filter_masks: Dict of {filter_name: boolean_mask}.

    Returns:
        Dict of {filter_name: pass_rate}.
    """
    rates: dict[str, float] = {}
    for name, mask in per_filter_masks.items():
        total = len(mask)
        passed = int(mask.sum()) if total > 0 else 0
        rates[name] = round(passed / total, 4) if total > 0 else 0.0
    return rates


def rank_results(
    scores: pd.Series,
    ascending: bool = False,
) -> pd.Series:
    """Rank symbols by score.

    Args:
        scores: Series of scores indexed by symbol.
        ascending: If True, lowest scores first (default: highest first).

    Returns:
        Series with rank (1 = best). NaN scores are ranked last.
    """
    return scores.rank(method="min", ascending=ascending, na_option="bottom").astype(int)
