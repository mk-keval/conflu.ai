"""CorrelationAnalyzer — Rolling Pearson correlation matrix with sector aggregation.

Computes 30-day rolling pairwise Pearson correlation via fully vectorized
pandas operations, with sector-level aggregation, high-correlation pair
detection, and diversification scoring.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.logging import get_logger
from backend.app.infrastructure.risk.models import CorrelationResult

log = get_logger("conflu.risk.correlation")


class CorrelationAnalyzer:
    """Compute rolling Pearson correlation matrices with sector aggregation.

    Uses pandas.DataFrame.rolling().corr(pairwise=True) for fully vectorized
    computation. No Python loops over symbols.
    """

    def __init__(self) -> None:
        self._default_window = settings.risk.correlation_window_days
        self._max_symbols = settings.risk.max_correlation_symbols
        self._log = get_logger("conflu.risk.correlation")

    def compute_correlation(
        self,
        symbols: list[str],
        window: int | None = None,
        min_periods: int = 15,
        group_by: str | None = None,
    ) -> CorrelationResult:
        """Compute rolling Pearson correlation for a set of symbols.

        Args:
            symbols: List of asset symbols. Limited by max_correlation_symbols.
            window: Rolling window in days. Defaults to config.
            min_periods: Minimum observations required for valid correlation.
            group_by: Column name for grouping (e.g., 'asset_class', 'sector').
                      If None, no sector aggregation is performed.

        Returns:
            CorrelationResult with latest matrix, sector aggregation, high pairs.
        """
        window = window or self._default_window

        # Limit symbols
        if self._max_symbols > 0 and len(symbols) > self._max_symbols:
            self._log.warning("correlation_symbols_truncated", requested=len(symbols), max=self._max_symbols)
            symbols = symbols[: self._max_symbols]

        returns_matrix = self._load_returns_matrix(symbols)
        if returns_matrix is None or returns_matrix.empty:
            return CorrelationResult(
                timestamp=datetime.now(UTC),
                window_days=window,
                diversification_score=None,
            )

        # Rolling pairwise correlation
        rolling_corr = returns_matrix.rolling(window, min_periods=min_periods).corr(pairwise=True)

        # Get latest correlation matrix
        latest_timestamp = rolling_corr.index.get_level_values(0).max()
        latest_corr = rolling_corr.loc[latest_timestamp].copy()

        # Clean NaN columns/rows
        latest_corr = latest_corr.dropna(how="all", axis=0).dropna(how="all", axis=1)
        clean_symbols = list(latest_corr.columns)
        matrix_values = latest_corr.values.tolist()

        # Sector aggregation
        sector_matrix: list[list[float]] | None = None
        sector_labels: list[str] | None = None
        if group_by:
            group_map = self._get_group_map(clean_symbols, group_by)
            sector_matrix, sector_labels = self._aggregate_by_group(latest_corr, group_map)

        # High correlation pairs
        high_pairs = self._find_high_correlation_pairs(latest_corr, clean_symbols)

        # Diversification score
        div_score = self._compute_diversification_score(latest_corr, clean_symbols)

        return CorrelationResult(
            timestamp=latest_timestamp.to_pydatetime()
            if hasattr(latest_timestamp, "to_pydatetime")
            else latest_timestamp,
            window_days=window,
            symbols=clean_symbols,
            matrix=matrix_values,
            sector_matrix=sector_matrix,
            sector_labels=sector_labels,
            high_correlation_pairs=high_pairs,
            diversification_score=div_score,
        )

    def _load_returns_matrix(self, symbols: list[str]) -> pd.DataFrame | None:
        """Load daily returns matrix from DuckDB OHLCV data.

        Args:
            symbols: List of symbols to load.

        Returns:
            DataFrame with symbols as columns and daily returns as values,
            or None if no data available.
        """
        try:
            with get_db(read_only=True) as con:
                placeholders = ",".join("?" * len(symbols))
                result = con.sql(
                    f"""
                    SELECT symbol, timestamp, close
                    FROM ohlcv
                    WHERE symbol IN ({placeholders})
                      AND timeframe = '1D'
                    ORDER BY symbol, timestamp
                    """,
                    params=[*symbols],
                ).fetchdf()
        except Exception:
            self._log.exception("Failed to load OHLCV for correlation")
            return None

        if result.empty:
            return None

        # Pivot to wide format
        pivoted = result.pivot(index="timestamp", columns="symbol", values="close")
        pivoted = pivoted.sort_index()

        # Compute daily returns
        returns = pivoted.pct_change().dropna(how="all")
        return returns

    def _get_group_map(self, symbols: list[str], group_by: str) -> dict[str, str]:
        """Query symbol_metadata for group mapping.

        Args:
            symbols: List of symbols.
            group_by: Column name for grouping ('asset_class', 'sector', etc.).

        Returns:
            Dict mapping symbol -> group label. Defaults to "Unclassified".
        """
        group_map: dict[str, str] = {}
        try:
            with get_db(read_only=True) as con:
                placeholders = ",".join("?" * len(symbols))
                result = con.sql(
                    f"""
                    SELECT symbol, {group_by} AS group_label
                    FROM symbol_metadata
                    WHERE symbol IN ({placeholders})
                    """,
                    params=[*symbols],
                ).fetchdf()

            for _, row in result.iterrows():
                group_map[str(row["symbol"])] = str(row["group_label"])
        except Exception:
            self._log.warning("group_lookup_failed", group_by=group_by)

        # Default unclassified
        for s in symbols:
            if s not in group_map:
                group_map[s] = "Unclassified"

        return group_map

    def _aggregate_by_group(
        self,
        correlation_matrix: pd.DataFrame,
        group_map: dict[str, str],
    ) -> tuple[list[list[float]], list[str]]:
        """Aggregate correlation matrix to sector/asset-class level.

        For each group, computes average intra-group (within) and inter-group
        (cross) correlations.

        Args:
            correlation_matrix: N×N DataFrame of Pearson correlations.
            group_map: Mapping of symbol -> group label.

        Returns:
            Tuple of (sector_matrix, sector_labels).
            sector_matrix is M×M with average correlations between groups.
            sector_labels is list of M group names.
        """
        groups = sorted(set(group_map.values()))
        n_groups = len(groups)

        result = pd.DataFrame(index=groups, columns=groups, dtype=float)

        for i, g1 in enumerate(groups):
            g1_symbols = [s for s, g in group_map.items() if g == g1 and s in correlation_matrix.columns]
            for j, g2 in enumerate(groups):
                g2_symbols = [s for s, g in group_map.items() if g == g2 and s in correlation_matrix.columns]

                if not g1_symbols or not g2_symbols:
                    result.loc[g1, g2] = float("nan")
                    continue

                sub = correlation_matrix.loc[g1_symbols, g2_symbols]

                if i == j:
                    # Intra-group: average of within-group pairwise correlations (upper triangle)
                    if len(g1_symbols) > 1:
                        values = sub.values
                        triu_values = values[np.triu_indices_from(values, k=1)]
                        result.loc[g1, g2] = float(np.nanmean(triu_values)) if len(triu_values) > 0 else float("nan")
                    else:
                        result.loc[g1, g2] = 1.0
                else:
                    # Inter-group: average of cross-group correlations
                    result.loc[g1, g2] = float(sub.values.mean())

        sector_matrix = result.values.tolist()
        sector_labels = list(result.index)
        return sector_matrix, sector_labels

    def _find_high_correlation_pairs(
        self,
        matrix: pd.DataFrame,
        symbols: list[str],
        threshold: float = 0.8,
        max_pairs: int = 20,
    ) -> list[dict[str, Any]]:
        """Find top pairs with correlation above threshold.

        Args:
            matrix: N×N correlation DataFrame.
            symbols: List of symbol names.
            threshold: Minimum absolute correlation to report.
            max_pairs: Maximum number of pairs to return.

        Returns:
            List of dicts with 'symbols' and 'correlation' keys.
        """
        pairs: list[dict[str, Any]] = []
        for i, s1 in enumerate(symbols):
            for s2 in symbols[i + 1 :]:
                if s1 in matrix.columns and s2 in matrix.columns:
                    corr_val = matrix.loc[s1, s2]
                    if not np.isnan(corr_val) and abs(corr_val) > threshold:
                        pairs.append(
                            {
                                "symbols": [s1, s2],
                                "correlation": round(float(corr_val), 4),
                            }
                        )

        # Sort by absolute correlation descending
        pairs.sort(key=lambda p: abs(p["correlation"]), reverse=True)
        return pairs[:max_pairs]

    def _compute_diversification_score(
        self,
        matrix: pd.DataFrame,
        symbols: list[str],
    ) -> float:
        """Compute diversification score from correlation matrix.

        Score = 1 - mean(|pairwise_correlation|)
        Range: 0 (perfectly correlated, no diversification) to
               1 (perfectly uncorrelated, maximum diversification).

        Args:
            matrix: N×N correlation DataFrame.
            symbols: List of symbol names.

        Returns:
            Diversification score between 0 and 1.
        """
        correlations: list[float] = []
        for i, s1 in enumerate(symbols):
            for s2 in symbols[i + 1 :]:
                if s1 in matrix.columns and s2 in matrix.columns:
                    val = matrix.loc[s1, s2]
                    if not np.isnan(val):
                        correlations.append(abs(float(val)))

        if not correlations:
            return 0.0

        mean_corr = float(np.mean(correlations))
        return max(0.0, min(1.0, 1.0 - mean_corr))
