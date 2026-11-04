"""Backfill the D-74 measurement fields on existing journal rows.

- ``plan_rr`` / ``target_1_r`` from the stored levels (zone mid, T1/last target).
- ``pnl_gross_usd`` / ``costs_usd`` / ``pnl_usd`` for closed rows from shares.

Dry-run by default; ``--apply`` writes. Never changes entries, exits, stops,
targets, sizing or any decision. Existing rows without ``target_3`` cannot
recover the gate's third level; ``plan_rr`` is then the two-target figure and
the verifier reports the gap honestly.

    python scripts/backfill_p0_measurement.py
    python scripts/backfill_p0_measurement.py --apply
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.app.domain.workflow import journal_store  # noqa: E402
from backend.app.domain.workflow import pnl as pnl_mod  # noqa: E402


def _num(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number


def build_updates(rows: list[sqlite3.Row]) -> list[dict]:
    changes = []
    for row in rows:
        data = dict(row)
        entry = _num(data.get("entry_price"))
        low = _num(data.get("entry_low")) or entry
        high = _num(data.get("entry_high")) or entry
        stop = _num(data.get("stop_loss"))
        targets = [
            level for level in (
                _num(data.get("target_1")),
                _num(data.get("target_2")),
                _num(data.get("target_3")),
            ) if level is not None
        ]
        metrics = pnl_mod.plan_metrics(low, high, stop, targets) or {}

        update = {
            "id": data["id"],
            "symbol": data["symbol"],
            "date_entered": data["date_entered"],
            "plan_rr": metrics.get("plan_rr"),
            "target_1_r": metrics.get("target_1_r"),
        }

        if data.get("date_closed"):
            money = pnl_mod.dollar_pnl(
                entry, data.get("exit_price"), data.get("shares"),
            ) or {}
            update.update({
                "pnl_gross_usd": money.get("pnl_gross_usd"),
                "costs_usd": money.get("costs_usd"),
                "pnl_usd": money.get("pnl_usd"),
                "old_pnl_usd": _num(data.get("pnl_usd")),
            })
        changes.append(update)
    return changes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", help="Override the journal DB path")
    parser.add_argument("--apply", action="store_true", help="Write the updates")
    args = parser.parse_args()

    if args.db:
        journal_store.set_db_path(args.db)
    journal_store.ensure()
    db_path = journal_store.get_db_path()

    con = sqlite3.connect(db_path, timeout=30.0)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute("SELECT * FROM paper_trades ORDER BY date_entered, id").fetchall()
        changes = build_updates(rows)
        print(f"{'Symbol':<8} {'Date':<12} {'plan_rr':>8} {'T1 R':>7} {'pnl old':>10} {'pnl new':>10}")
        print("-" * 62)
        for change in changes:
            old = change.get("old_pnl_usd")
            new = change.get("pnl_usd")
            print(
                f"{change['symbol']:<8} {change['date_entered'][:10]:<12} "
                f"{str(change['plan_rr']):>8} {str(change['target_1_r']):>7} "
                f"{('-' if old is None else f'{old:,.2f}'):>10} "
                f"{('-' if new is None else f'{new:,.2f}'):>10}"
            )
        if not args.apply:
            print("\nDry run — pass --apply to write.")
            return 0
        with con:
            for change in changes:
                if change.get("pnl_usd") is None and change.get("old_pnl_usd") is None:
                    con.execute(
                        "UPDATE paper_trades SET plan_rr=?, target_1_r=? WHERE id=?",
                        (change["plan_rr"], change["target_1_r"], change["id"]),
                    )
                else:
                    con.execute(
                        "UPDATE paper_trades SET plan_rr=?, target_1_r=?, "
                        "pnl_gross_usd=?, costs_usd=?, pnl_usd=? WHERE id=?",
                        (
                            change["plan_rr"], change["target_1_r"],
                            change.get("pnl_gross_usd"), change.get("costs_usd"),
                            change.get("pnl_usd"), change["id"],
                        ),
                    )
        print(f"\nApplied to {len(changes)} row(s).")
        return 0
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
