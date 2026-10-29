# D-77: Bundle A — Exit & Gate Geometry Frozen for FWD-v0.2

**Date:** 2026-10-28
**Status:** Accepted — user sign-off on A1–A5 (2026-10-28); spec **FROZEN**;
implementation in progress. No v0.2 row exists until the go-live commit.
**Branch:** `fix/technical-tab-empty`
**Spec:** [`docs/PAPER_TRADING/BUNDLE_A_EXIT_GEOMETRY.md`](../PAPER_TRADING/BUNDLE_A_EXIT_GEOMETRY.md)
**Related:** D-51 (single exit for v1), D-58 (structural targets), D-74
(measurement), D-75 (pass bar), D-76 (sample versioning), `PIPELINE_AUDIT.md`
F5.

## Context

FWD-v0.1 was closed for verdict purposes (D-76) because the design it measured
was internally incoherent:

- Targets came from `synthesis._get_structural_targets_long`, which keeps the
  **highest** three structural levels within `1.5 × price`.
- The gate measured R:R to the **last** target.
- The exit walker paid the **first** target it touched.
- The dynamic plan (`scale_out`, `trail_type`, `trail_activation_r`,
  `move_to_breakeven_at_r`) was computed and then discarded.

CRS is the concrete failure. The gate recorded **4.32:1**, the stored plan
recomputed **11.89:1** to the second target, and the first target sat **21.2R**
from the planned entry (**27.7R** from the actual fill). The trade reached
**+3.72R** MFE and stopped at **−1.00R**. The 2.5:1 floor was satisfied by a
number that had nothing to do with the first payout.

D-51 deliberately shipped one exit in v1 because `target_1` was a manufactured
1.0R number and a 30/30/40 blend made `realized_r` ambiguous. It explicitly
allowed target-anchored tranche tracking in v2. This is that v2.

## Decision

Bundle A changes four things — target selection, the gate metric, the exit
policy, and the recorded fields — and nothing else. Screens, regime permission,
ranking, sizing, stops and entry rules stay frozen (Bundle B).

### A1 — the gate measures T1 from the planned fill

```
Plan R = (T1 − entry_low) / (entry_low − stop_loss)
```

`entry_low` is the worst price the limit order agrees to pay; the gate runs
before a fill exists, so using the actual fill would be hindsight. `stretch_rr`
(T3 R) is recorded for context but cannot rescue a bad T1.

Rejected: blended T1/T2/runner R (a runner can hide an unreachable T1 — the
same bug in a new costume) and last-target R:R (the v0.1 defect).

### A2 — family-specific exits

| Family | T1 leg | T2 leg | Runner | Breakeven | Trail |
|---|---|---|---|---|---|
| `trend` | 1/3 | 1/3 (joins runner if T2 missing) | 1/3 | +1R close | 2.0×ATR14 after T1 |
| `breakout` | 1/2 | — | 1/2 | +1R close | 2.5×ATR14 after T1 |
| `mean_reversion` | 100% | — | — | none | none |
| `rotation` | 100% | — | — | +1R close | none |
| `unknown` | 100% | — | — | +1R close | none |

Time stops: trend 30 calendar days, breakout 20, mean reversion 10, rotation 15,
unknown 20. The trail is `max(entry, highest_close_since_entry − k×ATR)`, never
loosens, and falls back to `2 × initial risk` when ATR is missing. Stop wins
same-bar ties; breakeven activates at the close and is live next bar; the entry
bar is excluded. These conventions match v0.1's conservative walker.

Rejected: one 1/2-at-T1 rule for all families (loses the second structural
objective and makes trend/breakout indistinguishable) and a single exit (no
runner, P1-6/P1-8 become no-ops).

### A3 — four families plus `unknown`

`trend`, `breakout`, `mean_reversion`, `rotation`, `unknown`, mapped from
`screen_name`. `unknown` preserves the v0.1 single exit for anything unmapped;
it is the honest default, not a bucket for new behavior.

Rejected: one policy for every long setup (a reversion snap-back and a 52-week
breakout have opposite hold profiles).

### A4 — no target in the band means reject

Bands (half-size floor / full-size / max): trend 2.0 / 2.5 / 4.0R; breakout
2.0 / 2.5 / 5.0R; mean reversion 1.25 / 1.5 / 2.5R; rotation 1.75 / 2.0 / 3.0R;
unknown 2.0 / 2.5 / 4.0R. The band minimum is the gate's CONDITIONAL floor, so
the D1 half-size tier remains reachable. Rejections are explicit: `target too
close`, `target too far`, `no structural objective`.

Rejected: an ATR/measured-move fallback at ~3R. It reintroduces a manufactured
level, the exact thing D-58 removed, and makes the gate test a number that is
not on the chart.

### A5 — mean reversion exits fully at T1

100% at T1, 10-day time stop, no runner. The edge is the snap-back to the mean;
once price returns, there is no defined reason to hold, and a runner would
expose the remainder to the reversion failing.

### Consistency fix during sign-off

The draft's band table said minimum T1 was 2.5R while the gate allowed 2.0–2.5R
at half size — a dead tier. The user approved lowering the band minimum to the
conditional floor. The PASS floors are unchanged (2.5R trend/breakout/unknown,
1.5R mean reversion, 2.0R rotation).

## What is recorded

New `paper_trades` columns: `setup_family`, `exit_legs` (JSON audit trail),
`stretch_rr`, `atr_at_entry`. New `pending_orders` columns: `setup_family`,
`atr_at_entry`. Filled orders inherit family and ATR.

`exit_price` is the share-weighted average of the legs; `realized_r` is exactly
the share-weighted average leg R under the canonical formula; `pnl_usd` is the
canonical net `pnl.dollar_pnl` on the weighted exit and total shares, which
equals the leg sum because the cost rate is constant. `exit_reason` is
`scale_out` for multi-leg exits, otherwise the single leg's reason.
`plan_adherence` is 1.0 when every planned leg fired, 0.5 when a trail/time stop
closed the remainder, 0.0 when a stop or manual action overrode the plan.

Existing rows keep `setup_family=NULL` and `exit_legs=NULL`; a NULL family is
the marker for "pre-family, single exit" and is never re-simulated. The
migration is additive.

## Versioning and freeze protocol

D-76 already sets `SCORED_SAMPLE_VERSION = "v0.2"`. `CURRENT_SAMPLE_VERSION`
stays `"interim"` through implementation, so no row can be stamped v0.2 while
traded under v0.1 rules. The go-live commit flips it to `"v0.2"` only after the
implementation tests and `verify_journal.py` pass. The v0.2 clock starts at the
first fill after that commit.

The H-09 replay uses the same `exit_policy.simulate_exit`, the D-73 entry model
and `rules_version='v0.2'`, runs **once** after the freeze, and is exploratory:
it never enters the forward scorecard and is never confirmatory evidence.

## Consequences

- Fewer accepted trades, especially `target too far`. That is intended
  selectivity, not a regression.
- The ticker page's R:R number changes meaning to "to the first target"; it will
  look smaller and more honest. `stretch_rr` keeps the far target visible.
- More implementation surface: a pure exit simulator, family mapping, schema,
  pending inheritance, verifier and scorecard updates. The simulator is shared
  by live sync and H-09 so the rules cannot drift.
- Partial exits make `realized_r` a weighted average by construction. The
  verifier checks leg price/size sums against the stored weighted values.
- v0.1 rows are untouched. No past decision is re-decided under v0.2.

## Implementation checklist

1. `backend/app/domain/workflow/exit_policy.py`: family map, bands, target
   selection, pure multi-leg simulator, accounting.
2. `synthesis.py`: nearest-first target selection within the family band;
   target-anchored `scale_out`/trail/BE/time stop; `risk_reward` = T1 R.
3. `gate.py`: Plan R to T1 from `entry_low`; family floors; consistency check
   against T1; `setup_family` in `GateInput`.
4. `journal_store.py`: columns + migration; insert/update for family, stretch,
   ATR, legs; weighted exit fields.
5. `pending.py` + workflow router: inherit family/ATR on fill; write the new
   fields on the row.
6. `workflow.py` sync: use `simulate_exit` for family rows, keep `infer_exit`
   for v0.1/NULL-family rows; write legs and weighted accounting.
7. `verification.py`: leg/vwap/R/P&L consistency and per-version plan-R checks.
8. `scorecard.py`: weighted R is already the canonical field; add a family
   breakdown and keep the D-75 bar unchanged.
9. API models + UI badges for family/legs; regenerate OpenAPI types.
10. Tests: target selection, gate floors, simulator branches, accounting,
    schema/pending inheritance, sync integration, verifier, v0.1 regression.
11. Go-live: flip `CURRENT_SAMPLE_VERSION`, update the v0.2 pre-registration
    with the go-live date and "first fill TBD", run the verifier.

## Sign-off

The user reviewed A1–A5 with the CRS arithmetic, approved all five as
recommended, and approved the consistency fix (band minimum = half-size floor).
No code behavior changed before this sign-off.

## Alternatives rejected (summary)

| Alternative | Why rejected |
|---|---|
| Last-target gate R:R | The v0.1 defect; approves exits the walker will not pay. |
| Blended plan R | A runner can mask an unreachable first target. |
| One exit at T1 for all | No runner; gives up the right tail the pass bar depends on. |
| One policy for all families | Reversion and breakout have opposite hold profiles. |
| ATR fallback target | Manufactured level; D-58 removed exactly this. |
| Mean-reversion runner | The edge is the snap-back; holding past it is a different trade. |
