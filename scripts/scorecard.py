"""Canonical forward scorecard (D-74, D-76) — one page, one filter, one R definition.

Reads only the journal of record (`data/paper_trades.db`). The **scored** sample
is the rows tagged with the current scored version (D-76); v0.1 and interim rows
are reported as reference, never folded into the verdict.

Definitions (do not fork them elsewhere):

- ``realized_r`` = (exit - entry) / (entry - stop), gross of costs.
- ``pnl_usd``    = shares x (exit - entry) - 10 bps fees - 5 bps slippage/side.
- Expectancy     = mean(realized_r) over closed scored trades.
- Win rate       = trades with realized_r > 0 / closed scored trades.
- Profit factor  = sum(winning R) / abs(sum(losing R)).
- MFE gap        = mean(mfe_r - realized_r); positive means profit left on the table.
- Drawdown       = peak-to-trough cumulative R over closed scored trades.
- Pass bar (D-75) = expectancy > 0 AND profit factor >= 1.3 AND avg loss <= 1.0R
  at 30+ closed trades. Win rate is reported, not gated.

    python scripts/scorecard.py
    python scripts/scorecard.py --json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.app.domain.workflow import journal as journal_mod  # noqa: E402
from backend.app.domain.workflow import journal_store  # noqa: E402
from backend.app.domain.workflow import sample as sample_mod  # noqa: E402
from backend.app.domain.workflow import verification as verification_mod  # noqa: E402

MIN_SAMPLE = 30
PASS_PROFIT_FACTOR = 1.3
PASS_AVG_LOSS_R = 1.0
REVIEW_DRAWDOWN_R = 8.0
KILL_DRAWDOWN_R = 12.0
TIME_TRIGGER_DAYS = 42


def _float(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number


def _closed_rows(rows: list[dict]) -> list[dict]:
    return [
        row for row in rows
        if row.get("date_closed") and _float(row.get("realized_r")) is not None
    ]


def _max_drawdown_r(rows: list[dict]) -> float:
    """Peak-to-trough cumulative R, chronological by close date."""
    ordered = sorted(
        rows,
        key=lambda row: (
            str(row.get("date_closed") or ""),
            str(row.get("symbol") or ""),
        ),
    )
    equity = peak = worst = 0.0
    for row in ordered:
        equity += _float(row.get("realized_r")) or 0.0
        peak = max(peak, equity)
        worst = max(worst, peak - equity)
    return round(worst, 4)


def _metrics(rows: list[dict]) -> dict:
    """Canonical closed-trade metrics for one set of rows."""
    r_values = [_float(row.get("realized_r")) for row in rows]
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
        for row in rows
        if _float(row.get("mfe_r")) is not None and _float(row.get("realized_r")) is not None
    ]

    return {
        "n": n,
        "expectancy_r": round(expectancy, 4) if expectancy is not None else None,
        "win_rate": round(win_rate, 4) if win_rate is not None else None,
        "profit_factor": round(profit_factor, 4) if profit_factor is not None else None,
        "avg_win_r": round(avg_win, 4) if avg_win is not None else None,
        "avg_loss_r": round(avg_loss, 4) if avg_loss is not None else None,
        "total_r": round(sum(r_values), 4),
        "pnl_usd_net": round(sum(_float(row.get("pnl_usd")) or 0.0 for row in rows), 2),
        "pnl_usd_gross": round(sum(_float(row.get("pnl_gross_usd")) or 0.0 for row in rows), 2),
        "costs_usd": round(sum(_float(row.get("costs_usd")) or 0.0 for row in rows), 2),
        "mfe_gap_r": round(statistics.fmean(mfe_gaps), 4) if mfe_gaps else None,
        "max_drawdown_r": _max_drawdown_r(rows),
    }


def _kill_rule(n: int, expectancy: float | None) -> str:
    if n >= MIN_SAMPLE and expectancy is not None and expectancy <= 0:
        return "KILL — expectancy <= 0 at n>=30"
    if n >= MIN_SAMPLE:
        return "SURVIVES — expectancy > 0 at n>=30"
    return f"NOT YET — {n}/{MIN_SAMPLE} closed"


def _pass_bar(n: int, head: dict) -> str:
    if n < MIN_SAMPLE:
        return f"not evaluable — {n}/{MIN_SAMPLE} closed"
    reasons: list[str] = []
    if head["expectancy_r"] is None or head["expectancy_r"] <= 0:
        reasons.append("expectancy <= 0")
    if head["profit_factor"] is not None and head["profit_factor"] < PASS_PROFIT_FACTOR:
        reasons.append(f"profit factor < {PASS_PROFIT_FACTOR}")
    if head["avg_loss_r"] is not None and abs(head["avg_loss_r"]) > PASS_AVG_LOSS_R:
        reasons.append(f"average loss > {PASS_AVG_LOSS_R}R")
    return "PASS" if not reasons else "FAIL — " + ", ".join(reasons)


def _drawdown_status(drawdown: float) -> str:
    if drawdown >= KILL_DRAWDOWN_R:
        return f"KILL — {drawdown:.2f}R >= {KILL_DRAWDOWN_R:.0f}R"
    if drawdown >= REVIEW_DRAWDOWN_R:
        return f"REVIEW — {drawdown:.2f}R >= {REVIEW_DRAWDOWN_R:.0f}R"
    return f"CLEAR — {drawdown:.2f}R < {REVIEW_DRAWDOWN_R:.0f}R"


def _time_trigger(first_fill: str | None) -> str:
    if first_fill:
        try:
            return (date.fromisoformat(first_fill[:10]) + timedelta(days=TIME_TRIGGER_DAYS)).isoformat()
        except ValueError:
            pass
    return f"{TIME_TRIGGER_DAYS} days after the first scored fill"


def build_scorecard() -> dict:
    journal_store.ensure()
    rows = journal_mod.read_rows()
    forward = [row for row in rows if verification_mod.in_forward_sample(row)]
    scored = [
        row for row in forward
        if sample_mod.is_scored_version(row.get("sample_version"))
    ]
    closed = _closed_rows(scored)
    open_rows = [row for row in scored if not row.get("date_closed")]
    all_orders = journal_store.list_pending_orders("all", limit=10_000)
    pending = [
        order for order in all_orders
        if str(order.get("status") or "").lower() == "pending"
        and sample_mod.is_scored_version(order.get("sample_version"))
    ]

    head = _metrics(closed)
    n = head["n"]

    per_template = verification_mod.compute_expectancy_per_template_regime(min_trades=1)
    groups = [metrics.to_dict() for metrics in per_template.values()]
    groups.sort(key=lambda item: (-item["n_trades"], item["template"]))

    first_fill = min(
        (str(row.get("date_entered"))[:10] for row in scored if row.get("date_entered")),
        default=None,
    )

    references = []
    for version in sample_mod.SAMPLE_VERSIONS:
        version_rows = [
            row for row in rows
            if sample_mod.normalize_sample_version(row.get("sample_version")) == version
        ]
        version_forward = [
            row for row in version_rows if verification_mod.in_forward_sample(row)
        ]
        version_closed = _closed_rows(version_forward)
        version_pending = [
            order for order in all_orders
            if sample_mod.normalize_sample_version(order.get("sample_version")) == version
            and str(order.get("status") or "").lower() == "pending"
        ]
        references.append({
            "version": version,
            "scored": version == sample_mod.SCORED_SAMPLE_VERSION,
            "label": sample_mod.SAMPLE_VERSION_LABELS.get(version, ""),
            "closed": len(version_closed),
            "open": sum(1 for row in version_forward if not row.get("date_closed")),
            "pending": len(version_pending),
            "headline": _metrics(version_closed),
        })

    return {
        "generated_from": str(journal_store.get_db_path()),
        "sample": {
            "scored_version": sample_mod.SCORED_SAMPLE_VERSION,
            "first_fill": first_fill,
            "time_trigger": _time_trigger(first_fill),
            "min_sample": MIN_SAMPLE,
            "forward_rows": len(scored),
            "closed": n,
            "open": len(open_rows),
            "pending": len(pending),
            "kill_rule": _kill_rule(n, head["expectancy_r"]),
            "pass_bar": _pass_bar(n, head),
            "drawdown": _drawdown_status(head["max_drawdown_r"]),
        },
        "headline": head,
        "per_template_regime": groups,
        "reference_versions": references,
    }


def print_scorecard(card: dict) -> None:
    sample = card["sample"]
    head = card["headline"]
    print(f"Scorecard — {card['generated_from']}")
    print(
        f"Scored sample: {sample['scored_version']} | first fill {sample['first_fill']} | "
        f"trigger {sample['min_sample']} closed or {sample['time_trigger']}"
    )
    print(
        f"Closed {sample['closed']} / open {sample['open']} / pending {sample['pending']}"
    )
    print(f"Kill rule: {sample['kill_rule']}")
    print(f"Pass bar (D-75): {sample['pass_bar']}")
    print(f"Drawdown: {sample['drawdown']}")
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
        print("No closed scored trades yet.")
    else:
        print(f"{'Template':<38} {'Regime':<14} {'n':>4} {'ExpR':>7} {'WR':>7} {'PF':>6}")
        print("-" * 82)
        for item in card["per_template_regime"]:
            pf = f"{item['profit_factor']:.2f}" if item["profit_factor"] is not None else "-"
            print(
                f"{item['template'][:38]:<38} {item['regime'][:14]:<14} "
                f"{item['n_trades']:>4} {item['expectancy_r']:>7.3f} "
                f"{item['win_rate']:>6.1%} {pf:>6}"
            )
    print()
    print("Other samples (reference only, never scored)")
    print(f"{'Version':<10} {'Closed':>7} {'Open':>5} {'Pend':>5} {'ExpR':>8} {'WR':>7}  Status")
    print("-" * 96)
    for item in card["reference_versions"]:
        if item["scored"]:
            continue
        h = item["headline"]
        exp = f"{h['expectancy_r']:>8.2f}" if h["expectancy_r"] is not None else f"{'-':>8}"
        wr = f"{h['win_rate']:>6.1%}" if h["win_rate"] is not None else f"{'-':>7}"
        print(
            f"{item['version']:<10} {item['closed']:>7} {item['open']:>5} "
            f"{item['pending']:>5} {exp} {wr}  {item['label']}"
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
