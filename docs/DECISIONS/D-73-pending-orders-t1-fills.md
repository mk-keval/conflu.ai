# D-73: Pending Orders + T+1 Fills — No Same-Day Paper Fills

**Date:** 2026-10-21
**Status:** Accepted — implemented; sample reset; clock restarts at the first actual fill
**Branch:** `fix/technical-tab-empty`
**Related:** D-72 (execution v0.1), D-68 (SQLite journal), D-71 (two-month replay),
`docs/PAPER_TRADING/FORWARD_TEST_REVIEW.md`, `docs/PAPER_TRADING/PIPELINE_AUDIT.md`

## Context

D-72 started the forward sample after the 2026-10-19 after-close run. On 2026-10-21 the
journal was checked against actual session OHLC and four of the first four entries were
impossible fills:

| Row | Signal date | Booked | Actual session low | What happened |
|---|---|---|---|---|
| PM | 2026-10-19 | 185.97 | 199.35 | price never traded near the entry |
| AMGN | 2026-10-20 | 406.02 | 425.11 | price never traded near the entry |
| CCK | 2026-10-20 | 112.46 | 106.09 | fill booked same day, after the signal |
| MMM | 2026-10-20 | 168.80 | 162.13 | fill booked same day, after the signal |

The cause was structural, not a data glitch: `_build_row` stored `entry_zone_low` as
`entry_price` and `upsert_entry` wrote it immediately, with no fill event or timing. The
signal is produced **after** the close, so a same-day fill is always look-ahead. CCK and
MMM did close inside their zones, but the system could not have bought them at those
prices — the signal did not exist until after the session.

This is a measurement error in execution v0.1. It is not a reason to change targets,
R:R, screens, sizing, or regime permission. The sample cannot produce trustworthy
evidence while phantom fills are possible.

## Decision

Replace same-day booking with a pending-order model, matching a live broker:

1. **After-close signal → pending order.** Accepted gate rows are written to
   `pending_orders`, not `paper_trades`.
2. **Limit is the default.** The limit is `entry_low` (the bottom of the desired zone).
   A limit fills only when a later bar trades at or below it:
   - open at/below the limit and above the stop → fill at the open (better price);
   - open above the limit but the low touches the limit → fill at the limit;
   - open at/below the stop → cancel (the setup gapped through the risk).
3. **MOO is optional.** A market-on-open order fills at the next open only when the open
   is inside the entry zone (`<= entry_high`); opening above the zone cancels — no chase.
   Opening at/below the stop also cancels.
4. **T+1 only.** Only bars strictly after `signal_date` are eligible. The signal day's
   bar can never fill the order. The run date caps the bars so future data is ignored.
5. **Expiry after 3 sessions.** An unfilled order expires after three eligible sessions
   (actual bars; holidays do not consume one). `expires_after_sessions` is configurable.
6. **Same-session stop, no same-session target.** If the fill bar's low touches the
   stop, the trade is closed at the stop that day (−1R). If the fill bar also touched a
   target, it is ignored: the intrabar order is unknowable, and the conservative outcome
   wins. Later exits use `infer_exit` from the next bar.
7. **Sizing is unchanged in intent.** The size % was computed for the desired zone
   entry. The fill recomputes shares capped by both the planned notional and the planned
   dollar risk, so a worse MOO fill (still inside the zone) never risks more than the
   plan; a better limit fill risks less.
8. **Pending orders reserve the book.** They count for the position-count cap, duplicate
   symbol checks, sector exposure, and available capital. A new signal cannot duplicate a
   symbol that is already waiting to fill.
9. **Void, do not delete.** The four invalid rows are marked
   `voided=1`, `exclude_from_stats=1` with the evidence in `void_reason`. They remain
   visible in the journal and export. They are not positions and never enter the
   scorecard. No retroactive pending orders are created for them.
10. **Sample resets.** The forward clock starts at the first **actual fill** (T+1 after an
    after-close signal). Run ids 1–2 remain as history; their accepted lists are not
    rewritten.

Execution v0.1 remains otherwise frozen: targets, R:R gate, screens, sizing rules and
regime permission are untouched.

## Implementation

- `backend/app/domain/workflow/pending.py` — pure fill rules: `evaluate_order`,
  `normalize_bars`, `build_filled_row`, `planned_shares`, `same_bar_stop`, `stop_exit`.
- `backend/app/domain/workflow/pending_service.py` — DB-aware service shared by the API
  and CLI: create orders, process fills, expire/cancel, apply same-session stops.
- `backend/app/domain/workflow/journal_store.py` — `pending_orders` table (partial unique
  index: one active order per symbol), `voided`/`void_reason`, `void_trade`, pending CRUD,
  void-preserving export/import.
- `backend/app/api/routers/workflow.py` — enforce processes fills **before** today's
  signals; accepts become pending orders; `/pending-orders`; `/journal/open` includes
  pending; voided rows excluded from positions.
- `backend/scripts/paper_trade_from_brief.py` — local (git-ignored) CLI parity: fill,
  enforce as pending, exits; `--fill-pending`, `--order-type`, `--expiry-sessions`.
  The live loop uses the API; this script is an operator convenience.
- `frontend/src/components/workflow/JournalTab.tsx` — pending-orders panel and `void`
  badge; voided rows remain visible but are visually de-emphasised.
- `scripts/void_invalid_forward_entries.py` — idempotent live-DB void of PM/AMGN/CCK/MMM.

## Tests

- Pure: same-day bar never fills; limit at open/limit; gap-through-stop cancel; 3-session
  expiry; MOO fill/cancel; future bars ignored; DataFrame normalization; share cap;
  same-session stop.
- Store: one active order per symbol; guarded status transitions; voided visible but not
  open/scored; pending reserves capital; export/import preserves the void flag.
- Endpoints: T+1 fill is booked at the actual price; signal-day touch is ignored; expiry;
  same-session stop; `/journal/open` excludes voided and includes pending.
- Frontend: typecheck and the JournalTab helper tests.

## Consequences

- **Honest but slower.** Some orders will never fill. That is the point: a live account
  does not get a fill because the plan wanted one. Fill rate becomes a first-class
  diagnostic.
- **Conservative understatement.** Same-day targets are ignored, so a few trades may show
  less profit than an idealized intrabar path. This protects the sample from optimism.
- **More state.** Pending orders are a second book-keeping surface, but one active order
  per symbol and guarded transitions keep re-runs idempotent.
- **The old rows are not evidence.** The pre-correction run-1 narrative is retained only
  as history; the forward scorecard starts from the first real fill.
