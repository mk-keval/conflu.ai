"""KellyOptimizer — Kelly Criterion optimization from backtest results.

Consumes Phase 4 BacktestRunRecord trades to compute optimal Kelly fraction,
validates against max drawdown constraints (D-17 formula), and produces
recommended position sizing parameters. Never fails — returns sensible defaults.
"""

from __future__ import annotations

import numpy as np

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.logging import get_logger
from backend.app.infrastructure.risk.models import KellyRecommendation

log = get_logger("conflu.risk.kelly")


class KellyOptimizer:
    """Kelly Criterion optimization from backtest results.

    Consumes Phase 4 trade data to compute optimal Kelly fraction,
    validates against max drawdown, and produces a recommendation.
    """

    def __init__(self) -> None:
        self._default_kelly_fraction = settings.risk.default_kelly_fraction
        self._default_max_dd = settings.risk.max_dd_target
        self._log = get_logger("conflu.risk.kelly")

    def optimize_from_backtest(
        self,
        backtest_run_id: str | None = None,
        trades: list[dict] | None = None,
        max_dd_target: float | None = None,
        use_half_kelly: bool = True,
    ) -> KellyRecommendation:
        """Compute Kelly-optimal position sizing from backtest trade data.

        Full pipeline:
        1. Load trades from DuckDB (if not provided)
        2. Compute win_rate, avg_win, avg_loss from trade PnL
        3. Compute Kelly fraction: f* = win_rate - (1 - win_rate) / avg_win_loss_ratio
        4. Validate against max drawdown constraint (D-17)
        5. Apply half-Kelly if configured
        6. Return recommendation with sizing params

        Args:
            backtest_run_id: Backtest run ID for loading trades from DuckDB.
            trades: List of trade dicts with 'pnl' key. If provided, skips DB load.
            max_dd_target: Max acceptable drawdown. Defaults to settings.
            use_half_kelly: If True, limit recommendation to half-Kelly.

        Returns:
            KellyRecommendation with full/constrained/recommended Kelly.
        """
        max_dd_target = max_dd_target or self._default_max_dd

        # Load trades if not provided
        if trades is None:
            trades = self._load_trades(backtest_run_id) if backtest_run_id else []

        if not trades:
            self._log.info("no_trades_available", backtest_run_id=backtest_run_id)
            return self._empty_recommendation(backtest_run_id)

        # Compute trade statistics
        win_rate, avg_win_loss_ratio = self._compute_trade_stats(trades)

        # Compute Kelly fraction
        full_kelly = self._compute_kelly_fraction(win_rate, avg_win_loss_ratio)

        # Validate against max drawdown
        backtest_max_dd = self._estimate_max_dd(trades)
        constrained_kelly = self._validate_against_max_dd(full_kelly, backtest_max_dd, max_dd_target)

        # Apply half-Kelly
        recommended_kelly = constrained_kelly
        is_valid = constrained_kelly >= full_kelly * 0.5

        if use_half_kelly:
            half_kelly = full_kelly * 0.5
            if recommended_kelly > half_kelly:
                recommended_kelly = half_kelly

        # Build suggested params
        suggested_params: dict[str, float] = {
            "kelly_fraction": max(0.05, recommended_kelly),
            "risk_per_trade": max(0.005, recommended_kelly * 0.02),
        }

        return KellyRecommendation(
            backtest_run_id=backtest_run_id,
            asset_class="unknown",
            win_rate=win_rate,
            avg_win_loss_ratio=avg_win_loss_ratio,
            full_kelly=full_kelly,
            constrained_kelly=constrained_kelly,
            recommended_kelly=recommended_kelly,
            max_dd_target=max_dd_target,
            is_valid=is_valid,
            suggested_position_sizing="kelly",
            suggested_params=suggested_params,
        )

    def validate_kelly_fraction(
        self,
        kelly_fraction: float,
        backtest_max_dd: float,
        max_dd_target: float | None = None,
    ) -> dict:
        """Validate a Kelly fraction against max drawdown constraint (D-17).

        D-17: max_kelly_allowed = 2 × max_dd_target / (1 + max_dd_target)

        Args:
            kelly_fraction: Raw Kelly fraction.
            backtest_max_dd: Maximum drawdown observed in backtest.
            max_dd_target: Max acceptable drawdown. Defaults to settings.

        Returns:
            Dict with validation results.
        """
        target = max_dd_target or self._default_max_dd
        max_dd_kelly = 2.0 * target / (1.0 + target)
        constrained = min(kelly_fraction, max_dd_kelly)
        half_kelly = kelly_fraction * 0.5

        return {
            "original_kelly": kelly_fraction,
            "constrained_kelly": constrained,
            "max_dd_kelly": max_dd_kelly,
            "max_dd_target": target,
            "backtest_max_dd": backtest_max_dd,
            "is_valid": constrained >= half_kelly,
            "recommendation": constrained if constrained >= half_kelly else half_kelly,
        }

    def _compute_trade_stats(self, trades: list[dict]) -> tuple[float, float]:
        """Compute win rate and avg win/loss ratio from trade PnL.

        Args:
            trades: List of trade dicts with 'pnl' key.

        Returns:
            Tuple of (win_rate, avg_win_loss_ratio).
        """
        pnls = np.array([t.get("pnl", 0) for t in trades if t.get("pnl") is not None], dtype=np.float64)
        if len(pnls) == 0:
            return 0.5, 1.5

        winning = pnls[pnls > 0]
        losing = pnls[pnls <= 0]

        win_rate = float(len(winning)) / float(len(pnls))
        avg_win = float(np.mean(winning)) if len(winning) > 0 else 0.0
        avg_loss = float(abs(np.mean(losing))) if len(losing) > 0 else 1.0

        avg_win_loss_ratio = avg_win / max(avg_loss, 0.01)
        return win_rate, avg_win_loss_ratio

    def _compute_kelly_fraction(self, win_rate: float, avg_win_loss_ratio: float) -> float:
        """Compute Kelly fraction from win rate and win/loss ratio.

        D-15: f* = win_rate - (1 - win_rate) / avg_win_loss_ratio

        Args:
            win_rate: Probability of winning (0-1).
            avg_win_loss_ratio: Ratio of average win to average loss.

        Returns:
            Kelly fraction clamped to [0, 1].
        """
        q = 1.0 - win_rate
        if avg_win_loss_ratio > 0:
            f_star = win_rate - q / avg_win_loss_ratio
        else:
            f_star = 0.0
        return max(0.0, min(f_star, 1.0))

    def _validate_against_max_dd(
        self,
        kelly: float,
        backtest_max_dd: float,
        max_dd_target: float,
    ) -> float:
        """Constrain Kelly fraction by max drawdown target (D-17).

        max_dd_kelly = 2 × max_dd_target / (1 + max_dd_target)

        Args:
            kelly: Raw Kelly fraction.
            backtest_max_dd: Backtest max drawdown.
            max_dd_target: Target max drawdown.

        Returns:
            Constrained Kelly fraction.
        """
        max_dd_kelly = 2.0 * max_dd_target / (1.0 + max_dd_target)
        return min(kelly, max_dd_kelly)

    def _load_trades(self, backtest_run_id: str) -> list[dict]:
        """Load trades from DuckDB backtest_trades table.

        Args:
            backtest_run_id: Backtest run ID.

        Returns:
            List of trade dicts with 'pnl' key.
        """
        try:
            with get_db(read_only=True) as con:
                result = con.sql(
                    """
                    SELECT pnl, direction, size, entry_price, exit_price
                    FROM backtest_trades
                    WHERE run_id = ?
                    """,
                    params=[backtest_run_id],
                ).fetchdf()

            if result.empty:
                return []

            trades: list[dict] = []
            for _, row in result.iterrows():
                pnl_val = row.get("pnl")
                if pnl_val is not None:
                    trades.append(
                        {
                            "pnl": float(pnl_val),
                            "direction": str(row.get("direction", "Long")),
                            "size": float(row.get("size", 0.0)),
                        }
                    )
            return trades

        except Exception:
            self._log.exception("failed_to_load_trades", backtest_run_id=backtest_run_id)
            return []

    def _empty_recommendation(self, backtest_run_id: str | None) -> KellyRecommendation:
        """Return a no-trade Kelly recommendation with sensible defaults.

        Returns:
            KellyRecommendation with is_valid=False and default sizing.
        """
        return KellyRecommendation(
            backtest_run_id=backtest_run_id,
            is_valid=False,
            suggested_params={
                "risk_per_trade": 0.01,
                "kelly_fraction": self._default_kelly_fraction,
            },
        )

    def _estimate_max_dd(self, trades: list[dict]) -> float:
        """Estimate max drawdown from trade PnL sequence.

        Uses running equity simulation from sequential trade PnL.

        Args:
            trades: List of trade dicts sorted by time.

        Returns:
            Estimated max drawdown as decimal.
        """
        pnls = np.array([t.get("pnl", 0.0) for t in trades], dtype=np.float64)
        if len(pnls) == 0:
            return 0.0

        equity = np.cumsum(pnls)
        if len(equity) == 0 or equity[-1] <= 0:
            return 0.25  # Conservative default

        peak = np.maximum.accumulate(equity)
        drawdown = (peak - equity) / peak
        return float(np.max(drawdown))
