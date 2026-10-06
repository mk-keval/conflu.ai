"""Expectancy tracking per template/regime (plan Sec.2E verification).

Tracks rolling expectancy, win rate, profit factor per template/regime
combination. Minimum n=30 trades before "elite" badge is awarded.

Uses the paper-trade journal CSV as the single source of truth.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.app.domain.workflow import journal as journal_mod


ELITE_MIN_TRADES = 30
DEFAULT_TRADES_DIR = journal_mod.DEFAULT_TRADES_DIR


@dataclass
class ExpectancyMetrics:
    """Rolling expectancy metrics for a template/regime combination."""
    
    template: str
    regime: str
    n_trades: int
    win_rate: float
    expectancy_r: float
    profit_factor: float | None
    avg_r: float
    avg_win_r: float
    avg_loss_r: float
    max_win_r: float
    max_loss_r: float
    total_r: float
    is_elite: bool
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "template": self.template,
            "regime": self.regime,
            "n_trades": self.n_trades,
            "win_rate": round(self.win_rate, 4),
            "expectancy_r": round(self.expectancy_r, 4),
            "profit_factor": round(self.profit_factor, 2) if self.profit_factor else None,
            "avg_r": round(self.avg_r, 4),
            "avg_win_r": round(self.avg_win_r, 4),
            "avg_loss_r": round(self.avg_loss_r, 4),
            "max_win_r": round(self.max_win_r, 4),
            "max_loss_r": round(self.max_loss_r, 4),
            "total_r": round(self.total_r, 4),
            "is_elite": self.is_elite,
            "elite_min_trades": ELITE_MIN_TRADES,
        }


def _normalize_template(name: str) -> str:
    """Normalize template name for grouping."""
    return (name or "Unknown").strip() or "Unknown"


def _normalize_regime(name: str) -> str:
    """Normalize regime name for grouping."""
    return (name or "Unknown").strip() or "Unknown"


def compute_expectancy_per_template_regime(
    trades_dir: Path | str | None = None,
    min_trades: int = ELITE_MIN_TRADES,
) -> dict[str, ExpectancyMetrics]:
    """Compute expectancy metrics grouped by (template, regime).
    
    Args:
        trades_dir: Directory containing journal CSV files
        min_trades: Minimum trades required for elite status
        
    Returns:
        Dict keyed by "template|regime" with ExpectancyMetrics
    """
    rows = journal_mod.read_closed_trades(trades_dir)
    
    # Group by template + regime
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        template = _normalize_template(row.get("template") or "")
        regime = _normalize_regime(row.get("regime") or "")
        key = f"{template}|{regime}"
        groups[key].append(row)
    
    results: dict[str, ExpectancyMetrics] = {}
    
    for key, group_rows in groups.items():
        template, regime = key.split("|", 1)
        
        # Filter rows with valid realized_r
        valid_rows = [
            r for r in group_rows
            if r.get("realized_r") is not None
        ]
        
        n_trades = len(valid_rows)
        if n_trades == 0:
            continue
        
        # Compute metrics
        r_values = [float(r["realized_r"]) for r in valid_rows]
        wins = [r for r in r_values if r > 0]
        losses = [r for r in r_values if r < 0]
        
        win_rate = len(wins) / n_trades if n_trades > 0 else 0.0
        expectancy = sum(r_values) / n_trades if n_trades > 0 else 0.0
        
        gross_profit = sum(wins) if wins else 0.0
        gross_loss = abs(sum(losses)) if losses else 0.0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else None
        
        avg_r = expectancy
        avg_win_r = sum(wins) / len(wins) if wins else 0.0
        avg_loss_r = sum(losses) / len(losses) if losses else 0.0
        max_win_r = max(wins) if wins else 0.0
        max_loss_r = min(losses) if losses else 0.0
        total_r = sum(r_values)
        
        is_elite = n_trades >= min_trades and expectancy > 0
        
        results[key] = ExpectancyMetrics(
            template=template,
            regime=regime,
            n_trades=n_trades,
            win_rate=win_rate,
            expectancy_r=expectancy,
            profit_factor=profit_factor,
            avg_r=avg_r,
            avg_win_r=avg_win_r,
            avg_loss_r=avg_loss_r,
            max_win_r=max_win_r,
            max_loss_r=max_loss_r,
            total_r=total_r,
            is_elite=is_elite,
        )
    
    return results


def get_elite_templates(
    trades_dir: Path | str | None = None,
    min_trades: int = ELITE_MIN_TRADES,
) -> list[ExpectancyMetrics]:
    """Get all template/regime combinations that have achieved elite status.
    
    Elite = n >= min_trades AND expectancy > 0
    """
    all_metrics = compute_expectancy_per_template_regime(trades_dir, min_trades)
    return [
        m for m in all_metrics.values()
        if m.is_elite
    ]


def get_template_regime_performance(
    template: str,
    regime: str | None = None,
    trades_dir: Path | str | None = None,
) -> ExpectancyMetrics | None:
    """Get expectancy metrics for a specific template (and optional regime)."""
    all_metrics = compute_expectancy_per_template_regime(trades_dir)
    
    template_norm = _normalize_template(template)
    regime_norm = _normalize_regime(regime) if regime else None
    
    for key, metrics in all_metrics.items():
        if metrics.template == template_norm:
            if regime_norm is None or metrics.regime == regime_norm:
                return metrics
    return None


def compute_rolling_expectancy(
    symbol: str | None = None,
    template: str | None = None,
    regime: str | None = None,
    window: int = 30,
    trades_dir: Path | str | None = None,
) -> dict[str, Any] | None:
    """Compute rolling expectancy over the last N trades for a symbol/template/regime.
    
    Returns dict with rolling metrics or None if insufficient data.
    """
    rows = journal_mod.read_closed_trades(trades_dir)
    
    # Filter rows
    filtered = rows
    if symbol:
        filtered = [r for r in filtered if (r.get("symbol") or "").upper() == symbol.upper()]
    if template:
        template_norm = _normalize_template(template)
        filtered = [r for r in filtered if _normalize_template(r.get("template") or "") == template_norm]
    if regime:
        regime_norm = _normalize_regime(regime)
        filtered = [r for r in filtered if _normalize_regime(r.get("regime") or "") == regime_norm]
    
    # Sort by date_entered (most recent first)
    filtered.sort(key=lambda r: r.get("date_entered") or "", reverse=True)
    
    # Take last N trades
    window_rows = filtered[:window]
    
    valid_rows = [r for r in window_rows if r.get("realized_r") is not None]
    n = len(valid_rows)
    
    if n == 0:
        return None
    
    r_values = [float(r["realized_r"]) for r in valid_rows]
    wins = [r for r in r_values if r > 0]
    losses = [r for r in r_values if r < 0]
    
    win_rate = len(wins) / n
    expectancy = sum(r_values) / n
    gross_profit = sum(wins) if wins else 0.0
    gross_loss = abs(sum(losses)) if losses else 0.0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else None
    
    return {
        "symbol": symbol,
        "template": template,
        "regime": regime,
        "window": n,
        "win_rate": round(win_rate, 4),
        "expectancy_r": round(expectancy, 4),
        "profit_factor": round(profit_factor, 2) if profit_factor else None,
        "total_r": round(sum(r_values), 4),
    }


__all__ = [
    "ELITE_MIN_TRADES",
    "ExpectancyMetrics",
    "compute_expectancy_per_template_regime",
    "get_elite_templates",
    "get_template_regime_performance",
    "compute_rolling_expectancy",
]