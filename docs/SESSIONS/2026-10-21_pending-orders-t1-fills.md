# 2026-10-21 — Pending Orders + T+1 Fills (D-73)

**Decision:** D-73 (pending orders, no same-day paper fills)
**Branch:** `fix/technical-tab-empty`
**Status:** Implemented; sample reset; first possible fill is T+1 after the next
after-close run.

## Why

The forward sample's first four entries were checked against actual session bars and none
were tradeable:

| Row | Signal | Booked | Session low | Verdict |
|---|---|---|---|---|
| PM | 2026-10-19 | 185.97 | 199.35 | phantom |
| AMGN | 2026-10-20 | 406.02 | 425.11 | phantom |
| CCK | 2026-10-20 | 112.46 | 106.09 | after-close look-ahead |
| MMM | 2026-10-20 | 168.80 | 162.13 | after-close look-ahead |

The cause: `_build_row` stored the zone low as the entry price and the journal wrote it
immediately after the close. There was no fill event, so the system could "buy" at a price
that never traded.

## What changed

- **Pending orders** (`pending_orders` table, one active per symbol). A signal after the
  close becomes a limit order at `entry_low` (default) or an optional MOO order.
- **T+1 fills only.** Eligible bars are strictly after `signal_date` and up to the run
  date. A limit fills at the open when gapped below the limit (but above the stop), or at
  the limit when touched. MOO fills only at the next open inside `entry_high`. A gap
  through the stop cancels; unfilled orders expire after 3 sessions.
- **Conservative same-session exit.** If the fill bar's low touches the stop, the trade
  closes at the stop that day (−1R). Same-session targets are ignored because the
  intrabar order is unknowable.
- **Sizing intent preserved.** Shares are capped by both planned notional and planned
  dollar risk; a worse MOO fill never risks more than the plan.
- **Book reservation.** Pending orders count for capital, position slots, sector exposure
  and duplicate-symbol checks.
- **Voiding.** PM/AMGN/CCK/MMM are `voided=1`, `exclude_from_stats=1`, with the evidence
  in `void_reason`. They stay visible in the journal/export, are not positions, and never
  enter the scorecard. Legacy NTNX/WBD/NVDA remain open/excluded as before.
- **CLI parity (local, git-ignored).** `backend/scripts/paper_trade_from_brief.py` now
  fills → queues pending → exits; added `--fill-pending`, `--order-type`,
  `--expiry-sessions`. The live loop uses the API; this script is an operator
  convenience and is ignored by repo policy (`backend/scripts/`).
- **UI.** Journal tab shows a pending-orders panel and a `void` badge; voided rows are
  de-emphasised but visible.

## Tests

- `backend/tests/test_pending.py` — 15 pure fill-rule tests (same-day bar ignored,
  limit/MOO, gap-through-stop, expiry, future bars, DataFrame normalization, share cap,
  same-session stop).
- `backend/tests/test_journal_db.py` — active-order uniqueness, guarded status
  transitions, void visibility/exclusion, capital reservation, export/import void flag.
- `backend/tests/test_workflow_endpoints.py` — T+1 fill, signal-day ignored, expiry,
  same-session stop, `/journal/open` pending/voided behavior.
- Frontend typecheck + JournalTab helper tests (15).
- Focused backend suites: journal/workflow/exits/verification/gate/sizing/CLI all pass.

## Live state

- 7 journal rows: 3 legacy open/excluded (NTNX/WBD/NVDA), 4 voided (PM/AMGN/CCK/MMM).
- 0 pending orders, 0 valid forward fills.
- `workflow_runs` ids 1–2 retained as history; their accepted lists are not rewritten.
- Sample clock: starts at the first actual fill, not at run 1.

## Next

1. Run the after-close one-go on 2026-10-21 → pending orders only.
2. Confirm on the next session that fills use actual T+1 bars and that no journal entry
   shares its pending order's signal date.
3. Track fill rate, expiry vs cancel, and same-session stop rate as execution diagnostics.
4. Keep targets/R:R/screens/sizing frozen until the review trigger (30 closed scored
   trades or ~2026-12-03 from the first actual fill).
