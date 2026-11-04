"""Expectancy tracking per template/regime (plan Sec.2E verification).

Tracks rolling expectancy, win rate, profit factor per template/regime
combination. Minimum n=30 trades before "elite" badge is awarded.

Uses the paper-trade journal CSV as the single source of truth.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.app.domain.workflow import exit_policy as exit_policy_mod
from backend.app.domain.workflow import journal as journal_mod
from backend.app.domain.workflow import pnl as pnl_mod
from backend.app.domain.workflow import sample as sample_mod


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


def in_forward_sample(row: dict[str, Any]) -> bool:
    """False for voided rows and rows explicitly excluded from the scorecard."""
    if str(row.get("voided") or "0").strip().lower() in {"1", "true", "yes"}:
        return False
    return str(row.get("exclude_from_stats") or "0").strip().lower() not in {
        "1", "true", "yes",
    }


def in_sample_version(row: dict[str, Any], version: str | None) -> bool:
    """True when the row belongs to ``version`` (None = any version)."""
    if version is None:
        return True
    return sample_mod.normalize_sample_version(row.get("sample_version")) == version


def in_scored_sample(row: dict[str, Any]) -> bool:
    """True only for rows that count toward the canonical scorecard (D-76)."""
    return in_forward_sample(row) and sample_mod.is_scored_version(row.get("sample_version"))


def compute_expectancy_per_template_regime(
    trades_dir: Path | str | None = None,
    min_trades: int = ELITE_MIN_TRADES,
    *,
    sample_version: str | None = sample_mod.SCORED_SAMPLE_VERSION,
) -> dict[str, ExpectancyMetrics]:
    """Compute expectancy metrics grouped by (template, regime).
    
    Args:
        trades_dir: Directory containing journal CSV files
        min_trades: Minimum trades required for elite status
        sample_version: Scored sample version (default), or None for all rows
        
    Returns:
        Dict keyed by "template|regime" with ExpectancyMetrics
    """
    rows = [
        r for r in journal_mod.read_closed_trades(trades_dir)
        if in_forward_sample(r) and in_sample_version(r, sample_version)
    ]
    
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
    *,
    sample_version: str | None = sample_mod.SCORED_SAMPLE_VERSION,
) -> list[ExpectancyMetrics]:
    """Get all template/regime combinations that have achieved elite status.
    
    Elite = n >= min_trades AND expectancy > 0
    """
    all_metrics = compute_expectancy_per_template_regime(
        trades_dir, min_trades, sample_version=sample_version,
    )
    return [
        m for m in all_metrics.values()
        if m.is_elite
    ]


def get_template_regime_performance(
    template: str,
    regime: str | None = None,
    trades_dir: Path | str | None = None,
    *,
    sample_version: str | None = sample_mod.SCORED_SAMPLE_VERSION,
) -> ExpectancyMetrics | None:
    """Get expectancy metrics for a specific template (and optional regime)."""
    all_metrics = compute_expectancy_per_template_regime(
        trades_dir, sample_version=sample_version,
    )
    
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
    *,
    sample_version: str | None = sample_mod.SCORED_SAMPLE_VERSION,
) -> dict[str, Any] | None:
    """Compute rolling expectancy over the last N trades for a symbol/template/regime.
    
    Returns dict with rolling metrics or None if insufficient data.
    """
    rows = [
        r for r in journal_mod.read_closed_trades(trades_dir)
        if in_forward_sample(r) and in_sample_version(r, sample_version)
    ]
    
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


def find_phantom_fills(
    trades: list[dict[str, Any]],
    orders: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """D-73 invariant: a journal entry must be strictly after its signal date.

    ``trades`` are journal rows, ``orders`` are pending-order rows (any status).
    A filled order with no matching journal entry is also a violation: the
    order says it filled, but the journal cannot show the position.
    """
    entries: dict[tuple[str, str], dict[str, Any]] = {}
    for row in trades:
        if not in_forward_sample(row):
            continue
        key = (
            str(row.get("symbol") or "").strip().upper(),
            str(row.get("date_entered") or "")[:10],
        )
        entries[key] = row

    violations: list[dict[str, Any]] = []
    for order in orders:
        if str(order.get("status") or "").lower() != "filled":
            continue
        symbol = str(order.get("symbol") or "").strip().upper()
        signal = str(order.get("signal_date") or "")[:10]
        filled_on = str(order.get("status_date") or "")[:10]
        row = entries.get((symbol, filled_on))
        if row is None:
            violations.append({
                "symbol": symbol,
                "signal_date": signal,
                "date_entered": None,
                "reason": "filled order has no journal entry",
            })
            continue
        entered = str(row.get("date_entered") or "")[:10]
        if entered <= signal:
            violations.append({
                "symbol": symbol,
                "signal_date": signal,
                "date_entered": entered,
                "reason": "entry is not strictly after the signal date",
            })
    return violations


def find_pnl_mismatches(
    trades: list[dict[str, Any]],
    tolerance: float = 0.02,
) -> list[dict[str, Any]]:
    """Closed forward rows whose stored dollars disagree with the canonical math."""
    mismatches: list[dict[str, Any]] = []
    for row in trades:
        if not in_forward_sample(row) or not row.get("date_closed"):
            continue
        expected = pnl_mod.dollar_pnl(
            row.get("entry_price"), row.get("exit_price"), row.get("shares"),
        )
        if expected is None:
            continue
        stored = row.get("pnl_usd")
        try:
            stored_f = float(stored)
        except (TypeError, ValueError):
            mismatches.append({
                "symbol": row.get("symbol"), "stored": stored,
                "expected": expected["pnl_usd"], "reason": "missing pnl_usd",
            })
            continue
        if abs(stored_f - expected["pnl_usd"]) > tolerance:
            mismatches.append({
                "symbol": row.get("symbol"), "stored": round(stored_f, 2),
                "expected": expected["pnl_usd"], "reason": "pnl_usd != shares x price move - costs",
            })
    return mismatches


def find_plan_rr_gaps(
    trades: list[dict[str, Any]],
    tolerance: float = 0.10,
) -> list[dict[str, Any]]:
    """Rows where the gate's R:R and the stored plan's R:R disagree.

    This is a warning, not a failure: the gate ran on the verdict's levels,
    the journal stores the levels the exits will use. D-74 records both so the
    gap is visible instead of being mistaken for agreement.
    """
    gaps: list[dict[str, Any]] = []
    for row in trades:
        if not in_forward_sample(row):
            continue
        gate = journal_mod._as_float(row.get("risk_reward_planned"))
        plan = journal_mod._as_float(row.get("plan_rr"))
        if gate is None or plan is None:
            continue
        if abs(gate - plan) > tolerance:
            gaps.append({
                "symbol": row.get("symbol"),
                "sample_version": sample_mod.normalize_sample_version(
                    row.get("sample_version")
                ),
                "gate_rr": round(gate, 2),
                "plan_rr": round(plan, 2),
                "gap": round(gate - plan, 2),
            })
    return gaps


_EXIT_LEG_REASONS = {
    "stop", "target_1", "target_2", "trail", "time_stop", "scale_out",
}


def find_exit_leg_issues(
    trades: list[dict[str, Any]],
    tolerance: float = 0.02,
) -> list[dict[str, Any]]:
    """D-77 exit integrity: legs exist, sum to 100%, and match the stored exit.

    A v0.2 row closes with weighted legs. The stored ``exit_price`` must be the
    size-weighted leg VWAP and ``realized_r`` the size-weighted leg R, otherwise
    the journal reports a number the fills do not support. v0.1 rows are exempt
    (single exit, no legs), but any stored legs are validated wherever present.
    """
    issues: list[dict[str, Any]] = []
    for row in trades:
        if not in_forward_sample(row):
            continue
        raw = row.get("exit_legs")
        if raw in (None, ""):
            if row.get("date_closed") and row.get("setup_family"):
                issues.append({
                    "symbol": row.get("symbol"),
                    "date_closed": row.get("date_closed"),
                    "reason": "closed family row has no exit legs",
                })
            continue
        try:
            legs = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError):
            issues.append({
                "symbol": row.get("symbol"),
                "reason": "exit_legs is not valid JSON",
            })
            continue
        if not isinstance(legs, list) or not legs:
            issues.append({
                "symbol": row.get("symbol"),
                "reason": "exit_legs is empty",
            })
            continue

        total_pct = 0.0
        weighted_price = 0.0
        weighted_r = 0.0
        malformed = False
        for leg in legs:
            if not isinstance(leg, dict):
                malformed = True
                break
            try:
                price = float(leg.get("price"))
                pct = float(leg.get("size_pct"))
                r_mult = float(leg.get("r"))
            except (TypeError, ValueError):
                malformed = True
                break
            if str(leg.get("reason") or "") not in _EXIT_LEG_REASONS:
                malformed = True
                break
            total_pct += pct
            weighted_price += price * pct
            weighted_r += r_mult * pct
        if malformed:
            issues.append({
                "symbol": row.get("symbol"),
                "reason": "exit_legs contains a malformed leg",
            })
            continue
        if abs(total_pct - 100.0) > 0.05:
            issues.append({
                "symbol": row.get("symbol"),
                "reason": f"exit legs sum to {total_pct:.2f}% (expected 100%)",
            })
        if total_pct <= 0:
            continue
        vwap = weighted_price / total_pct
        weighted_r_avg = weighted_r / total_pct
        exit_price = journal_mod._as_float(row.get("exit_price"))
        realized_r = journal_mod._as_float(row.get("realized_r"))
        if exit_price is not None and abs(vwap - exit_price) > tolerance:
            issues.append({
                "symbol": row.get("symbol"),
                "reason": (
                    f"exit_price {exit_price:.2f} != leg VWAP {vwap:.2f}"
                ),
            })
        if realized_r is not None and abs(weighted_r_avg - realized_r) > tolerance:
            issues.append({
                "symbol": row.get("symbol"),
                "reason": (
                    f"realized_r {realized_r:.2f} != weighted leg R "
                    f"{weighted_r_avg:.2f}"
                ),
            })
    return issues


def find_family_issues(
    trades: list[dict[str, Any]],
    orders: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """D-77 provenance: scored rows/orders carry a family; v0.1 rows never do.

    New rows always carry a family (including ``unknown``). Existing v0.1 rows
    keep NULL and are never retro-labeled — a family on a v0.1 row means history
    was rewritten under new rules.
    """
    issues: list[dict[str, Any]] = []
    for row in trades:
        version = sample_mod.normalize_sample_version(row.get("sample_version"))
        family = exit_policy_mod.normalize_family(row.get("setup_family"))
        if version == sample_mod.SCORED_SAMPLE_VERSION and family is None:
            issues.append({
                "symbol": row.get("symbol"),
                "date_entered": row.get("date_entered"),
                "sample_version": version,
                "setup_family": row.get("setup_family"),
                "reason": "scored row has no valid setup_family",
            })
        elif version == sample_mod.SAMPLE_VERSION_V01 and row.get("setup_family"):
            issues.append({
                "symbol": row.get("symbol"),
                "date_entered": row.get("date_entered"),
                "sample_version": version,
                "setup_family": row.get("setup_family"),
                "reason": "v0.1 row carries a setup_family (retro-labeled history)",
            })
    for order in orders:
        version = sample_mod.normalize_sample_version(order.get("sample_version"))
        family = exit_policy_mod.normalize_family(order.get("setup_family"))
        if version == sample_mod.SCORED_SAMPLE_VERSION and family is None:
            issues.append({
                "symbol": order.get("symbol"),
                "signal_date": order.get("signal_date"),
                "sample_version": version,
                "setup_family": order.get("setup_family"),
                "reason": "scored pending order has no valid setup_family",
            })
        elif version == sample_mod.SAMPLE_VERSION_V01 and order.get("setup_family"):
            issues.append({
                "symbol": order.get("symbol"),
                "signal_date": order.get("signal_date"),
                "sample_version": version,
                "setup_family": order.get("setup_family"),
                "reason": "v0.1 pending order carries a setup_family",
            })
    return issues


def find_sample_version_issues(
    trades: list[dict[str, Any]],
    orders: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """D-76 invariants: every row has a known version and fills inherit it.

    A filled pending order and the journal row it created must carry the same
    version. Otherwise a trade can silently move between samples — for example
    an ``interim`` order scored as ``v0.2``.
    """
    issues: list[dict[str, Any]] = []

    for row in trades:
        if sample_mod.normalize_sample_version(row.get("sample_version")) is None:
            issues.append({
                "symbol": row.get("symbol"),
                "date_entered": row.get("date_entered"),
                "sample_version": row.get("sample_version"),
                "reason": "unknown sample_version",
            })

    entries = {
        (
            str(row.get("symbol") or "").strip().upper(),
            str(row.get("date_entered") or "")[:10],
        ): row
        for row in trades
    }
    for order in orders:
        order_version = sample_mod.normalize_sample_version(order.get("sample_version"))
        if order_version is None:
            issues.append({
                "symbol": order.get("symbol"),
                "signal_date": order.get("signal_date"),
                "sample_version": order.get("sample_version"),
                "reason": "unknown pending-order sample_version",
            })
            continue
        if str(order.get("status") or "").lower() != "filled":
            continue
        key = (
            str(order.get("symbol") or "").strip().upper(),
            str(order.get("status_date") or "")[:10],
        )
        row = entries.get(key)
        if row is None:
            continue  # the phantom-fill check owns the missing-row case
        row_version = sample_mod.normalize_sample_version(row.get("sample_version"))
        if row_version != order_version:
            issues.append({
                "symbol": order.get("symbol"),
                "signal_date": order.get("signal_date"),
                "order_version": order_version,
                "row_version": row_version,
                "reason": "filled order and journal row versions differ",
            })
    return issues


__all__ = [
    "ELITE_MIN_TRADES",
    "ExpectancyMetrics",
    "in_forward_sample",
    "in_sample_version",
    "in_scored_sample",
    "compute_expectancy_per_template_regime",
    "get_elite_templates",
    "get_template_regime_performance",
    "compute_rolling_expectancy",
    "find_phantom_fills",
    "find_pnl_mismatches",
    "find_plan_rr_gaps",
    "find_sample_version_issues",
]