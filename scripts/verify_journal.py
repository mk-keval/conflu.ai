"""Journal integrity check (D-74) — the pass/fail gate for measurement.

Checks, against the configured journal DB:

1. **Phantom fills** — every filled pending order must have a journal entry
   dated strictly after its signal date (D-73).
2. **Dollar P&L** — every closed forward row's ``pnl_usd`` must equal
   ``shares x (exit - entry) - costs`` (D-74).
3. **Plan provenance** — warns when the gate's R:R and the stored plan's R:R
   disagree; this is the D-74 finding, reported rather than hidden.

Exit code 0 = PASS, 1 = FAIL. Warnings do not fail the run.

    python scripts/verify_journal.py
    python scripts/verify_journal.py --db data/paper_trades.db
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.app.domain.workflow import journal as journal_mod  # noqa: E402
from backend.app.domain.workflow import journal_store  # noqa: E402
from backend.app.domain.workflow import verification as verification_mod  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", help="Override the journal DB path")
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    args = parser.parse_args()

    if args.db:
        journal_store.set_db_path(args.db)
    journal_store.ensure()

    trades = journal_mod.read_rows()
    orders = journal_store.list_pending_orders("all", limit=10_000)
    forward = [row for row in trades if verification_mod.in_forward_sample(row)]

    phantom = verification_mod.find_phantom_fills(trades, orders)
    pnl_bad = verification_mod.find_pnl_mismatches(forward)
    rr_gaps = verification_mod.find_plan_rr_gaps(forward)

    failed = bool(phantom or pnl_bad)
    report = {
        "status": "FAIL" if failed else "PASS",
        "journal": str(journal_store.get_db_path()),
        "rows": {
            "total": len(trades),
            "forward": len(forward),
            "forward_closed": sum(1 for r in forward if r.get("date_closed")),
            "forward_open": sum(1 for r in forward if not r.get("date_closed")),
            "pending_orders": sum(1 for o in orders if o.get("status") == "pending"),
            "filled_orders": sum(1 for o in orders if o.get("status") == "filled"),
        },
        "phantom_fills": phantom,
        "pnl_mismatches": pnl_bad,
        "plan_rr_warnings": rr_gaps,
    }

    if args.json:
        print(json.dumps(report, indent=2, default=str))
        return 1 if failed else 0

    print(f"Journal: {report['journal']}")
    print(
        "Rows: {total} total, {forward} forward ({forward_closed} closed / "
        "{forward_open} open), {pending_orders} pending, {filled_orders} filled".format(
            **report["rows"]
        )
    )
    print()

    print(f"[{'FAIL' if phantom else 'PASS'}] Phantom fills: {len(phantom)}")
    for item in phantom:
        print(f"  - {item['symbol']}: signal {item['signal_date']} -> entry {item['date_entered']} ({item['reason']})")

    print(f"[{'FAIL' if pnl_bad else 'PASS'}] Dollar P&L: {len(pnl_bad)} mismatch(es)")
    for item in pnl_bad:
        print(f"  - {item['symbol']}: stored {item['stored']} vs expected {item['expected']} ({item['reason']})")

    print(f"[WARN] Plan R:R gaps: {len(rr_gaps)}")
    for item in rr_gaps:
        print(
            f"  - {item['symbol']}: gate {item['gate_rr']:.2f} vs stored plan "
            f"{item['plan_rr']:.2f} (gap {item['gap']:+.2f})"
        )

    print()
    print(report["status"])
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
