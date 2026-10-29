# D-75: Pass Bar — Expectancy, Profit Factor, Loss Control

**Date:** 2026-10-28
**Status:** Accepted — user sign-off; docs only
**Branch:** `fix/technical-tab-empty`
**Related:** D-74 (P0 measurement integrity), D-72/D-73 (execution v0.1),
`VISION.md`, `docs/PAPER_TRADING/SCORECARD.md`,
`docs/PAPER_TRADING/PRE_REGISTRATION.md`,
`docs/PAPER_TRADING/FORWARD_TEST_REVIEW.md`

## Context

`VISION.md` carried two definitions of success:

- **Passing bar (line 42):** hit rate > 50% AND average R > 0.5, after ≥ 20
  closed trades.
- **Kill rule (line 43):** expectancy ≤ 0 after 30+ closed trades.

They use different metrics and different thresholds. A 40%-win-rate trend system
with +2R winners has positive expectancy and would fail the pass bar; a
60%-win-rate system with +0.8R winners has a thin edge and would pass it. The
phrase "average R > 0.5" was also ambiguous: per-trade expectancy, or average
winner?

The pre-registration and scorecard flagged the legacy bar as **not applied** and
**awaiting user sign-off** (P0-4 in D-74). No verdict was ever issued under it.
The forward sample has 1 closed trade (CRS, −1.00R), far below the 30-trade
verdict threshold.

The user's stated philosophy is: patience, fewer and better setups, small
controlled losses, larger winners, trailing/profit-taking, capital preservation.
That is a **trend/continuation shape**, not a high-win-rate shape. Encoding
"more winning" as WR > 50% would push the system toward early profit-taking and
cut winners — the opposite of the stated goal.

## Decision

At **30+ closed trades**, the sample passes when all three hold:

1. **Expectancy > 0 after costs** — the primary edge.
2. **Profit factor ≥ 1.3** — gross wins at least 30% larger than gross losses.
3. **Average loss ≤ 1.0R** — losses stay at the stop; no systematic stop
   widening, averaging down, or holding losers.

Win rate, average win, payoff ratio, MFE capture and a bootstrap 95% CI are
**reported, not gated**. A win rate below 50% is acceptable when the winners are
large enough.

**Risk circuit breaker (always in force):**

- Peak-to-trough drawdown **≥ 8R** → stop new entries and review.
- **≥ 12R** → kill.
- Any single loss > 1.5R → execution review (gap or stop failure), not
  automatically a strategy kill.

At 1% risk per trade, 8R is roughly 8% of the account and 12R roughly 12%. If
that is too much pain, lower risk per trade (e.g. 0.5%); the R-based rule stays
the same and the dollar pain scales with size.

**Kill rule (unchanged):** expectancy ≤ 0 after 30+ closed trades, or the 12R
breaker → change the system or stop. "Give it more time" requires a written
reason.

## Why this bar and not WR > 50%

| System | WR | Avg win | Avg loss | Expectancy | PF | Legacy bar | D-75 bar |
|---|---:|---:|---:|---:|---:|---|---|
| Trend follower | 40% | +2.0R | −1.0R | **+0.20R** | 1.33 | ❌ fails WR | ✅ passes |
| Mean reverter | 60% | +0.8R | −1.0R | **+0.08R** | 1.20 | ✅ passes | ❌ fails PF |
| Coin flip | 50% | +1.0R | −1.0R | 0.00R | 1.00 | ❌ fails | ❌ kills |

The first system makes 2.5× the expectancy of the second and would have been
rejected by the old bar. Profit factor is a **shape** requirement, not a
frequency requirement: at 40% WR, PF 1.3 implies roughly 2:1 winners; at 55% WR
it implies roughly 1.06:1. The lower the win rate, the larger the winners must
be — exactly the trade-off the user described.

Average loss ≤ 1.0R is the capital-preservation clause. The stop defines 1R;
slippage and gaps can push a single loss above 1R, but a **systematic** average
above 1R means the system is not honoring its risk.

## Governance — why this is not goalpost-moving

- The legacy bar was explicitly flagged as **not applied** in `SCORECARD.md` and
  `PRE_REGISTRATION.md`; no verdict was issued under it.
- The new bar is activated **before** the 30-trade verdict and is not applied
  retroactively to CRS or any prior row.
- The new bar is **stricter** on loss control (average loss ≤ 1.0R, 8R/12R
  circuit breaker) and on effect size (PF ≥ 1.3) while removing a win-rate
  threshold the intended design would fail.
- The binding kill rule is unchanged.
- No trading decision, target, gate, screen, sizing rule or exit rule changed.

This is recorded in the pre-registration amendment log as a pre-verdict
definition of a flagged, never-applied bar. If the strictest reading is
preferred, the alternative was to void v0.1 and restart with the new bar; that
would cost the sample for a documentation change and was rejected.

## What changed

| File | Change |
|---|---|
| `VISION.md` | Line 42 replaced; risk circuit breaker row added; kill rule references 12R; scorecard location corrected; D-75 amendment note |
| `docs/PAPER_TRADING/SCORECARD.md` | Pass bar and circuit breaker; "not evaluable 1/30" snapshot row |
| `docs/PAPER_TRADING/PRE_REGISTRATION.md` | Pass bar section; 30-trade decision rules; amendment policy/log; open item resolved |
| `docs/PAPER_TRADING/README.md` | Binding rules paragraph |
| `docs/PAPER_TRADING/V2_RISK_GOVERNOR_BLUEPRINT.md` | V2 criteria inherit the D-75 bar |
| `docs/DECISIONS/D-74-p0-measurement-integrity.md` | P0-4 marked resolved; addendum |
| `docs/DECISIONS/index.md`, `docs/index.md`, `INDEX.md` | Index entries |

## What did not change

- No code, schema, migration or test.
- No target, R:R gate, screen, menu, weight, sizing formula, regime permission
  or exit rule.
- The forward sample clock, exclusions, fill rules and kill rule.
- The 3 plan-R:R warnings remain logged.

## Verification

- Docs-only; `python scripts/verify_journal.py` still prints **PASS**
  (0 phantom fills, 0 dollar-P&L mismatches, 3 plan-R:R warnings).
- No legacy "hit rate > 50%" / "avg R > 0.5" references remain in the active
  forward-test documents; historical session logs and D-47/D-50/D-64 are left
  as written.

## Open items

| Item | Status |
|---|---|
| Keep v0.1 or void for FWD-v0.2 (Bundle A: exit/gate geometry) | **Open — Q2** |
| P1-5..P1-8 behavior/design changes | Frozen until the sample decision |
| P2-9 risk field, P2-11 ADV costs, P3-14 universe dating | Measurement backlog |
| P4-16 thesis/counter-case field | Post-sample |
