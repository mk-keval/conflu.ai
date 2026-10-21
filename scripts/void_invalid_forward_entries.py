"""Void the four phantom after-close fills (D-73).

The 2026-10-19/20 entries were booked at prices that never traded. They stay in
the journal for the audit trail but are no longer positions and never enter the
forward scorecard. This script is idempotent: run it as often as needed.

    python scripts/void_invalid_forward_entries.py
    python scripts/void_invalid_forward_entries.py --db data/paper_trades.db
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.app.domain.workflow import journal_store  # noqa: E402

# (entry date, symbol, evidence from the actual session bars)
INVALID_FILLS: list[tuple[str, str, str]] = [
    (
        "2026-10-19", "PM",
        "phantom after-close fill: $185.97 never traded that session (low $199.35)",
    ),
    (
        "2026-10-20", "AMGN",
        "phantom after-close fill: $406.02 never traded that session (low $425.11)",
    ),
    (
        "2026-10-20", "CCK",
        "after-close signal booked at $112.46; same-day fill is look-ahead "
        "(session low $106.09, close $114.17)",
    ),
    (
        "2026-10-20", "MMM",
        "after-close signal booked at $168.80; same-day fill is look-ahead "
        "(session low $162.13, close $171.37)",
    ),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", help="Override the configured journal DB path")
    args = parser.parse_args()

    if args.db:
        journal_store.set_db_path(Path(args.db))
    journal_store.ensure()

    for date_entered, symbol, reason in INVALID_FILLS:
        changed = journal_store.void_trade(date_entered, symbol, reason)
        state = "voided" if changed else "unchanged (already void or absent)"
        print(f"  {date_entered} {symbol:<5} {state}")

    rows = journal_store.fetch_rows()
    voided = [r for r in rows if str(r.get("voided") or "0") == "1"]
    active_open = [
        r for r in rows
        if not r.get("date_closed") and str(r.get("voided") or "0") != "1"
    ]
    print(
        f"\n{len(voided)} voided row(s) kept visible; "
        f"{len(active_open)} active open position(s)."
    )
    for row in active_open:
        print(f"  open: {row.get('date_entered')} {row.get('symbol')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
