# 2026-10-28 — Bundle A Frozen (D-77)

**Branch:** `fix/technical-tab-empty`
**Decision:** [D-77](../DECISIONS/D-77-bundle-a-exit-geometry.md)
**Spec:** [BUNDLE_A_EXIT_GEOMETRY.md](../PAPER_TRADING/BUNDLE_A_EXIT_GEOMETRY.md)
**Pre-registration:** [PRE_REGISTRATION-v0.2.md](../PAPER_TRADING/PRE_REGISTRATION-v0.2.md)

## What was decided

The user signed off on all five Bundle A open decisions as recommended after a
plain-English walkthrough of the CRS failure:

| # | Decision | Frozen choice |
|---|---|---|
| A1 | Gate metric | T1 R from the planned fill, not last-target or blended R |
| A2 | Trend/breakout exits | Trend 1/3+1/3+1/3; breakout 1/2+1/2; BE +1R; 2.0/2.5×ATR trail |
| A3 | Family map | Four families + `unknown`, mapped from `screen_name` |
| A4 | No target in band | Reject (`target too close` / `too far` / `no structural objective`) |
| A5 | Mean reversion | 100% at T1, 10-day time stop, no runner |

One internal inconsistency was found during the walkthrough: the draft's band
minimum (2.5R) made the gate's 2.0–2.5R half-size tier unreachable. The band
minimum is now the half-size floor (2.0R trend/breakout/unknown, 1.25R mean
reversion, 1.75R rotation); the PASS floors are unchanged. The user approved
this fix.

## Why it matters

v0.1's gate measured a target the exit would never pay. CRS: gate 4.32:1,
stored plan 11.89:1, T1 21.2R from the planned entry (27.7R from the fill),
MFE +3.72R, exit −1.00R. The 2.5:1 floor was satisfied by a number unrelated to
the first payout. Bundle A makes the gate, the stored plan and the exit walker
use one level — T1.

## State

- Spec is **FROZEN**; implementation has not started.
- `SCORED_SAMPLE_VERSION = "v0.2"`; `CURRENT_SAMPLE_VERSION = "interim"`.
- No v0.2 row exists. The daily loop still stamps `interim`, never evidence.
- Live journal unchanged: 10 rows, 1 pending (DUK 122.57), 3 forward rows.
- v0.1 rows keep their single-exit values; no row is re-simulated.

## Next

Implement Bundle A: `exit_policy` module, nearest-first target selection,
family gate floors, journal/pending columns, sync wiring, verifier/scorecard,
API/UI, tests. Then go-live: flip `CURRENT_SAMPLE_VERSION`, run the verifier,
start the v0.2 clock at the first fill. H-09 replay is exploratory only.
