"""Canonical forward scorecard (D-74) — one page, one filter, one R definition.

Reads only the journal of record (`data/paper_trades.db`) and applies the
forward-sample filter (closed, not voided, not `exclude_from_stats`).

Definitions (do not fork them elsewhere):

- ``realized_r`` = (exit - entry) / (entry - stop), gross of costs.
- ``pnl_usd``    = shares x (exit - entry) - 10 bps fees - 5 bps slippage/side.
- Expectancy     = mean(realized_r) over closed forward trades.
- Win rate       = trades with realized_r > 0 / closed forward trades.
- Profit factor  = sum(winning R) / abs(sum(losing R)).
- MFE gap        = mean(mfe_r - realized_r); positive means profit left on the table.

    python scripts/scorecard.py
    python scripts/scorecard.py --json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.app.domain.workflow import journal as journal_mod  # noqa: E402
from backend.app.domain.workflow import journal_store  # noqa: E402
from backend.app.domain.workflow import verification as verification_mod  # noqa: E402

MIN_SAMPLE = 30
TIME_TRIGGER = "2026-12-03"


def _float(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number


def build_scorecard() -> dict:
    journal_store.ensure()
    rows = journal_mod.read_rows()
    forward = [row for row in rows if verification_mod.in_forward_sample(row)]
    closed = [
        row for row in forward
        if row.get("date_closed") and _float(row.get("realized_r")) is not None
    ]
    open_rows = [row for row in forward if not row.get("date_closed")]
    pending = journal_store.list_pending_orders("pending", limit=10_000)

    r_values = [_float(row.get("realized_r")) for row in closed]
    r_values = [value for value in r_values if value is not None]
    wins = [value for value in r_values if value > 0]
    losses = [value for value in r_values if value < 0]
    n = len(r_values)

    expectancy = statistics.fmean(r_values) if r_values else None
    win_rate = len(wins) / n if n else None
    profit_factor = (
        sum(wins) / abs(sum(losses)) if wins and losses else None
    )
    avg_win = statistics.fmean(wins) if wins else None
    avg_loss = statistics.fmean(losses) if losses else None

    mfe_gaps = [
        _float(row.get("mfe_r")) - _float(row.get("realized_r"))
        for row in closed
        if _float(row.get("mfe_r")) is not None and _float(row.get("realized_r")) is not None
    ]

    dollars_net = sum(_float(row.get("pnl_usd")) or 0.0 for row in closed)
    dollars_gross = sum(_float(row.get("pnl_gross_usd")) or 0.0 for row in closed)
    costs = sum(_float(row.get("costs_usd")) or 0.0 for row in closed)

    per_template = verification_mod.compute_expectancy_per_template_regime(min_trades=1)
    groups = [
        metrics.to_dict() for metrics in per_template.values()
    ]
    groups.sort(key=lambda item: (-item["n_trades"], item["template"]))

    if n >= MIN_SAMPLE and expectancy is not None and expectancy <= 0:
        kill = "KILL — expectancy <= 0 at n>=30"
    elif n >= MIN_SAMPLE:
        kill = "PASS so far — expectancy > 0 at n>=30"
    else:
        kill = f"NOT YET — {n}/{MIN_SAMPLE} closed"

    first_fill = min(
        (str(row.get("date_entered"))[:10] for row in forward if row.get("date_entered")),
        default=None,
    )

    return {
        "generated_from": str(journal_store.get_db_path()),
        "sample": {
            "first_fill": first_fill,
            "time_trigger": TIME_TRIGGER,
            "min_sample": MIN_SAMPLE,
            "forward_rows": len(forward),
            "closed": n,
            "open": len(open_rows),
            "pending": len(pending),
            "kill_rule": kill,
        },
        "headline": {
            "expectancy_r": round(expectancy, 4) if expectancy is not None else None,
            "win_rate": round(win_rate, 4) if win_rate is not None else None,
            "profit_factor": round(profit_factor, 4) if profit_factor is not None else None,
            "avg_win_r": round(avg_win, 4) if avg_win is not None else None,
            "avg_loss_r": round(avg_loss, 4) if avg_loss is not None else None,
            "total_r": round(sum(r_values), 4),
            "pnl_usd_net": round(dollars_net, 2),
            "pnl_usd_gross": round(dollars_gross, 2),
            "costs_usd": round(costs, 2),
            "mfe_gap_r": round(statistics.fmean(mfe_gaps), 4) if mfe_gaps else None,
        },
        "per_template_regime": groups,
    }


def print_scorecard(card: dict) -> None:
    sample = card["sample"]
    head = card["headline"]
    print(f"Scorecard — {card['generated_from']}")
    print(
        f"Sample: first fill {sample['first_fill']} | trigger {sample['min_sample']} closed "
        f"or {sample['time_trigger']} | closed {sample['closed']} / open {sample['open']} / "
        f"pending {sample['pending']}"
    )
    print(f"Kill rule: {sample['kill_rule']}")
    print()
    print(f"Expectancy: {head['expectancy_r']} R   Win rate: {head['win_rate']}")
    print(
        f"Profit factor: {head['profit_factor']}   Avg win/loss: "
        f"{head['avg_win_r']} / {head['avg_loss_r']} R   Total: {head['total_r']} R"
    )
    print(
        f"Dollars: net {head['pnl_usd_net']} | gross {head['pnl_usd_gross']} | "
        f"costs {head['costs_usd']}   MFE gap: {head['mfe_gap_r']} R"
    )
    print()
    if not card["per_template_regime"]:
        print("No closed forward trades yet.")
        return
    print(f"{'Template':<38} {'Regime':<14} {'n':>4} {'ExpR':>7} {'WR':>7} {'PF':>6}")
    print("-" * 82)
    for item in card["per_template_regime"]:
        pf = f"{item['profit_factor']:.2f}" if item["profit_factor"] is not None else "-"
        print(
            f"{item['template'][:38]:<38} {item['regime'][:14]:<14} "
            f"{item['n_trades']:>4} {item['expectancy_r']:>7.3f} "
            f"{item['win_rate']:>6.1%} {pf:>6}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    args = parser.parse_args()
    card = build_scorecard()
    if args.json:
        print(json.dumps(card, indent=2))
    else:
        print_scorecard(card)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
