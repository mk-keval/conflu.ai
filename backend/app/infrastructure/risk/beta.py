"""BetaHedger — Rolling OLS beta computation, hedge ratios, and effectiveness tracking.

Computes rolling 60-day beta vs configurable benchmarks using vectorized
covariance formula for performance, with full regression statistics via
scipy.stats.linregress for the latest window.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.logging import get_logger
from backend.app.infrastructure.risk.models import BetaResult, HedgeRecommendation, PortfolioBetaResult

log = get_logger("conflu.risk.beta")


class BetaHedger:
    """Compute rolling beta vs benchmark and generate hedge recommendations.

    Uses vectorized covariance formula: β = Cov(r_asset, r_benchmark) / Var(r_benchmark)
    for fast rolling computation, and scipy.stats.linregress for full regression stats
    on the latest window.
    """

    def __init__(self) -> None:
        self._default_window = settings.risk.beta_window_days
        self._benchmark_map = settings.risk.beta_benchmark_map
        self._log = get_logger("conflu.risk.beta")

    def compute_beta(
        self,
        symbols: list[str],
        benchmark: str | None = None,
        window: int | None = None,
        min_periods: int = 20,
    ) -> list[BetaResult]:
        """Compute rolling beta for all symbols vs a benchmark.

        Uses vectorized rolling covariance for bulk computation, then
        scipy.stats.linregress for full statistics on the latest observation.

        Args:
            symbols: List of asset symbols.
            benchmark: Benchmark symbol. If None, resolves from asset class.
            window: Rolling window in days. Defaults to settings.
            min_periods: Minimum observations required.

        Returns:
            List of BetaResult, one per symbol.
        """
        window = window or self._default_window
        benchmark = benchmark or self._benchmark_map.get("equities", "SPY")

        returns_matrix, benchmark_returns = self._load_returns(symbols, benchmark)
        if returns_matrix is None or returns_matrix.empty:
            return []

        # Vectorized rolling beta across all symbols
        rolling_betas = self._compute_beta_vectorized(returns_matrix, benchmark_returns, window)

        # Get latest values
        results: list[BetaResult] = []
        for symbol in symbols:
            if symbol not in rolling_betas.columns:
                continue

            # Get the rolling beta series for this symbol
            beta_series = rolling_betas[symbol].dropna()
            if beta_series.empty:
                results.append(self._empty_result(symbol, benchmark, window))
                continue

            latest_beta = float(beta_series.iloc[-1])

            # Full regression stats on latest window
            asset_returns = returns_matrix[symbol].dropna()
            bench_returns = benchmark_returns.reindex(asset_returns.index).dropna()

            # Align both series
            common_idx = asset_returns.index.intersection(bench_returns.index)
            if len(common_idx) < min_periods:
                results.append(self._empty_result(symbol, benchmark, window))
                continue

            y = asset_returns.loc[common_idx].values[-window:]
            x = bench_returns.loc[common_idx].values[-window:]
            # Remove any NaN pairs
            valid = ~(np.isnan(x) | np.isnan(y))
            x, y = x[valid], y[valid]

            if len(x) < min_periods:
                results.append(self._empty_result(symbol, benchmark, window))
                continue

            slope, intercept, r_value, p_value, std_err = scipy_stats.linregress(x, y)
            residuals = y - (slope * x + intercept)
            tracking_error = float(np.std(residuals, ddof=1))

            results.append(
                BetaResult(
                    symbol=symbol,
                    benchmark=benchmark,
                    beta=float(slope),
                    alpha=float(intercept),
                    r_squared=float(r_value**2),
                    std_err=float(std_err),
                    p_value=float(p_value),
                    tracking_error=tracking_error,
                    window_days=window,
                    n_observations=len(x),
                    computed_at=datetime.now(timezone.utc),
                )
            )

        return results

    def compute_portfolio_beta(
        self,
        portfolio_id: str,
        positions: dict[str, float],
        benchmark: str | None = None,
        window: int | None = None,
    ) -> PortfolioBetaResult:
        """Compute market-value-weighted portfolio beta.

        Args:
            portfolio_id: Portfolio identifier.
            positions: Dict mapping symbol -> position market value.
            benchmark: Benchmark symbol.
            window: Rolling window in days.

        Returns:
            PortfolioBetaResult with weighted beta and per-symbol betas.
        """
        symbols = list(positions.keys())
        betas = self.compute_beta(symbols, benchmark, window)

        symbol_betas: dict[str, float] = {}
        for br in betas:
            if br.beta is not None:
                symbol_betas[br.symbol] = br.beta

        if not symbol_betas:
            return PortfolioBetaResult(
                portfolio_id=portfolio_id,
                benchmark=benchmark or self._benchmark_map.get("equities", "SPY"),
                computed_at=datetime.now(timezone.utc),
            )

        total_value = sum(abs(v) for v in positions.values())
        if total_value == 0:
            return PortfolioBetaResult(
                portfolio_id=portfolio_id,
                benchmark=benchmark or self._benchmark_map.get("equities", "SPY"),
                computed_at=datetime.now(timezone.utc),
            )

        weighted_beta = 0.0
        for symbol, value in positions.items():
            if symbol in symbol_betas:
                weight = abs(value) / total_value
                weighted_beta += weight * symbol_betas[symbol]

        return PortfolioBetaResult(
            portfolio_id=portfolio_id,
            benchmark=benchmark or self._benchmark_map.get("equities", "SPY"),
            weighted_beta=weighted_beta,
            symbol_betas=symbol_betas,
            computed_at=datetime.now(timezone.utc),
        )

    def recommend_hedge(
        self,
        symbol: str,
        asset_class: str,
        position_value: float,
        benchmark_price: float | None = None,
        beta_result: BetaResult | None = None,
        contract_multiplier: float = 1.0,
    ) -> HedgeRecommendation:
        """Generate hedge recommendation for a position based on beta result.

        Hedge ratio = beta × position_value / (benchmark_price × multiplier)

        Recommendation tiers:
        - beta > 0.5 and R² > 0.7 → 'required'
        - beta > 0.3 and R² > 0.4 → 'optional'
        - else → 'none'

        Args:
            symbol: Asset symbol.
            asset_class: Asset class (equities, crypto, etc.).
            position_value: Current market value of the position.
            benchmark_price: Current benchmark price (for units calculation).
            beta_result: Pre-computed BetaResult. If None, computes on the fly.
            contract_multiplier: Contract multiplier for futures.

        Returns:
            HedgeRecommendation with hedge ratio, units, and action.
        """
        if beta_result is None or beta_result.beta is None:
            return HedgeRecommendation(
                symbol=symbol,
                asset_class=asset_class,
                recommendation="none",
                computed_at=datetime.now(timezone.utc),
            )

        beta = beta_result.beta
        r_squared = beta_result.r_squared or 0.0

        # Hedge ratio = beta × position_value
        hedge_value = beta * position_value
        hedge_ratio = beta

        # Hedge units
        hedge_units: float | None = None
        if benchmark_price is not None and benchmark_price > 0:
            hedge_units = hedge_value / (benchmark_price * contract_multiplier)

        # Recommendation logic
        if beta > 0.5 and r_squared > 0.7:
            recommendation = "required"
            hedge_instrument = "inverse_etf" if beta > 0 else "direct_etf"
        elif beta > 0.3 and r_squared > 0.4:
            recommendation = "optional"
            hedge_instrument = "inverse_etf" if beta > 0 else "direct_etf"
        else:
            recommendation = "none"
            hedge_instrument = None
            hedge_value = 0.0
            hedge_units = None

        return HedgeRecommendation(
            symbol=symbol,
            asset_class=asset_class,
            beta=beta,
            r_squared=r_squared,
            tracking_error=beta_result.tracking_error,
            hedge_ratio=hedge_ratio,
            hedge_value=hedge_value,
            hedge_units=hedge_units,
            hedge_instrument=hedge_instrument,
            recommendation=recommendation,
            computed_at=datetime.now(timezone.utc),
        )

    def resolve_benchmark(self, asset_class: str, override: str | None = None) -> str:
        """Resolve benchmark symbol for an asset class.

        Args:
            asset_class: Asset class name (equities, crypto, forex, etc.).
            override: Optional manual override.

        Returns:
            Benchmark symbol string.
        """
        if override:
            return override
        return self._benchmark_map.get(asset_class, self._benchmark_map.get("equities", "SPY"))

    def _load_returns(
        self,
        symbols: list[str],
        benchmark: str,
    ) -> tuple[pd.DataFrame | None, pd.Series | None]:
        """Load daily returns for symbols and benchmark from DuckDB.

        Args:
            symbols: Asset symbols.
            benchmark: Benchmark symbol.

        Returns:
            Tuple of (returns_matrix, benchmark_returns).
            returns_matrix: DataFrame with symbols as columns, daily returns as values.
            benchmark_returns: Series with daily benchmark returns.
        """
        all_symbols = list(set(symbols + [benchmark]))
        try:
            with get_db(read_only=True) as con:
                placeholders = ",".join("?" * len(all_symbols))
                result = con.sql(
                    f"""
                    SELECT symbol, timestamp, close
                    FROM ohlcv
                    WHERE symbol IN ({placeholders})
                      AND timeframe = '1D'
                    ORDER BY symbol, timestamp
                    """,
                    params=[*all_symbols],
                ).fetchdf()
        except Exception:
            self._log.exception("Failed to load OHLCV for beta computation")
            return None, None

        if result.empty:
            return None, None

        # Pivot to wide format
        pivoted = result.pivot(index="timestamp", columns="symbol", values="close")
        pivoted = pivoted.sort_index()

        # Compute daily returns
        returns = pivoted.pct_change().dropna(how="all")

        if benchmark not in returns.columns:
            self._log.warning("benchmark_not_found", benchmark=benchmark)
            return None, None

        benchmark_returns = returns[benchmark]
        asset_returns = returns[[s for s in symbols if s in returns.columns]]

        return asset_returns, benchmark_returns

    def _compute_beta_vectorized(
        self,
        returns_matrix: pd.DataFrame,
        benchmark_returns: pd.Series,
        window: int,
    ) -> pd.DataFrame:
        """Vectorized rolling beta across all symbols.

        β_i = Cov(r_i, r_benchmark) / Var(r_benchmark)

        Uses pandas rolling cov/var for fully vectorized computation.

        Args:
            returns_matrix: Daily returns for all assets (columns = symbols).
            benchmark_returns: Daily returns for the benchmark.
            window: Rolling window in days.

        Returns:
            DataFrame of shape (n_days, n_symbols) with rolling betas.
        """
        # Rolling covariance between each asset and benchmark
        rolling_cov = returns_matrix.rolling(window).cov(benchmark_returns)
        # Rolling variance of benchmark
        rolling_var = benchmark_returns.rolling(window).var()
        # Vectorized beta: Cov / Var
        betas = rolling_cov.divide(rolling_var, axis=0)
        return betas

    def _empty_result(self, symbol: str, benchmark: str, window: int) -> BetaResult:
        """Create an empty BetaResult for symbols with insufficient data."""
        return BetaResult(
            symbol=symbol,
            benchmark=benchmark,
            window_days=window,
            n_observations=0,
            computed_at=datetime.now(timezone.utc),
        )
