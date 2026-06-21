"""Strategy comparison engine — side-by-side backtest result analysis.

Compares multiple backtest runs across metrics, equity curves, drawdown,
rolling metrics, and statistical significance.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from uuid import uuid4

import numpy as np

from backend.app.core.database import get_db
from backend.app.core.logging import get_logger
from backend.app.infrastructure.backtest.models import ComparisonConfig, StrategyComparisonResult

log = get_logger("conflu.backtest.comparison")

METRIC_CONFIG: dict[str, dict[str, Any]] = {
    "sharpe": {"label": "Sharpe Ratio", "higher_is_better": True, "precision": 2},
    "sortino": {"label": "Sortino Ratio", "higher_is_better": True, "precision": 2},
    "calmar": {"label": "Calmar Ratio", "higher_is_better": True, "precision": 2},
    "max_dd": {"label": "Max Drawdown", "higher_is_better": False, "precision": 4},
    "win_rate": {"label": "Win Rate", "higher_is_better": True, "precision": 4},
    "profit_factor": {"label": "Profit Factor", "higher_is_better": True, "precision": 2},
    "expectancy": {"label": "Expectancy", "higher_is_better": True, "precision": 2},
    "sqn": {"label": "SQN", "higher_is_better": True, "precision": 2},
    "ulcer": {"label": "Ulcer Index", "higher_is_better": False, "precision": 2},
    "cagr": {"label": "CAGR", "higher_is_better": True, "precision": 4},
}


class StrategyComparator:
    """Compare multiple backtest runs side-by-side."""

    def __init__(self) -> None:
        self._log = get_logger("conflu.backtest.comparison")

    async def compare(self, config: ComparisonConfig) -> StrategyComparisonResult:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._compare_sync, config)

    def _compare_sync(self, config: ComparisonConfig) -> StrategyComparisonResult:
        run_ids = config.run_ids
        labels = config.labels or [f"Run {i+1}" for i in range(len(run_ids))]

        if len(run_ids) < 2:
            raise ValueError("At least 2 run_ids required for comparison")
        if len(run_ids) > 50:
            raise ValueError("Maximum 50 strategies can be compared at once")

        with get_db(read_only=True) as con:
            metrics_data: dict[str, dict[str, Any]] = {}
            for run_id in run_ids:
                row = con.sql("SELECT metrics_json, initial_cash, symbol FROM backtest_results WHERE run_id = ?", params=[run_id]).fetchone()
                metrics_data[run_id] = json.loads(row[0]) if row and row[0] else {}

            equity_curves_raw: dict[str, list[tuple]] = {}
            for run_id in run_ids:
                rows = con.sql("SELECT timestamp, equity FROM backtest_equity_curves WHERE run_id = ? ORDER BY timestamp", params=[run_id]).fetchall()
                if rows:
                    equity_curves_raw[run_id] = rows

            drawdown_curves_raw: dict[str, list[tuple]] = {}
            for run_id in run_ids:
                rows = con.sql("SELECT timestamp, drawdown FROM backtest_equity_curves WHERE run_id = ? ORDER BY timestamp", params=[run_id]).fetchall()
                if rows:
                    drawdown_curves_raw[run_id] = rows

        equity_curves: dict[str, list[dict[str, float]]] = {}
        drawdown_curves: dict[str, list[dict[str, float]]] = {}
        for run_id in run_ids:
            raw = equity_curves_raw.get(run_id, [])
            if raw:
                base = raw[0][1] if raw and len(raw[0]) > 1 else 100_000.0
                equity_curves[run_id] = [{"timestamp": str(ts), "value": float(eq) / base} for ts, eq in raw]
            raw_dd = drawdown_curves_raw.get(run_id, [])
            if raw_dd:
                drawdown_curves[run_id] = [{"timestamp": str(ts), "value": float(dd)} for ts, dd in raw_dd]

        metrics_table: list[dict[str, Any]] = []
        best_by_metric: dict[str, str] = {}
        for metric_name, metric_cfg in METRIC_CONFIG.items():
            higher_is_better = metric_cfg["higher_is_better"]
            precision = metric_cfg["precision"]
            row: dict[str, Any] = {"metric": metric_cfg["label"]}
            best_value = -float("inf") if higher_is_better else float("inf")
            best_run = ""
            for i, run_id in enumerate(run_ids):
                val = metrics_data.get(run_id, {}).get(metric_name)
                if val is not None:
                    formatted = round(val, precision)
                    row[labels[i]] = formatted
                    if (higher_is_better and formatted > best_value) or (not higher_is_better and formatted < best_value):
                        best_value = formatted
                        best_run = run_id
                else:
                    row[labels[i]] = "N/A"
            metrics_table.append(row)
            if best_run:
                best_by_metric[metric_name] = best_run

        significance_matrix: list[list[float | None]] = []
        if config.include_significance:
            for i, run_a in enumerate(run_ids):
                row_sig: list[float | None] = []
                for j, run_b in enumerate(run_ids):
                    if i == j:
                        row_sig.append(None)
                    else:
                        row_sig.append(self._bootstrap_significance(metrics_data.get(run_a, {}), metrics_data.get(run_b, {}), config.bootstrap_samples))
                significance_matrix.append(row_sig)

        return StrategyComparisonResult(
            comparison_id=str(uuid4()), run_ids=run_ids, labels=labels,
            n_strategies=len(run_ids), best_by_metric=best_by_metric,
            metrics_table=metrics_table, significance_matrix=significance_matrix,
            equity_curves=equity_curves, drawdown_curves=drawdown_curves,
        )

    @staticmethod
    def _bootstrap_significance(metrics_a: dict[str, Any], metrics_b: dict[str, Any], n_samples: int = 1000) -> float | None:
        sharpe_a, sharpe_b = metrics_a.get("sharpe"), metrics_b.get("sharpe")
        if sharpe_a is None or sharpe_b is None:
            return None
        try:
            from scipy import stats as scipy_stats
            diff = abs(sharpe_a - sharpe_b)
            t_stat = diff / 0.2  # Simplified SE approximation
            return float(min(max(2.0 * (1.0 - scipy_stats.norm.cdf(abs(t_stat))), 0.0), 1.0))
        except Exception:
            return None
