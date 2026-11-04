# D-51: Paper-Trade Schema v2 (29 columns) + Gate Sequencing — Ship Enforcement Now, Defer the R:R Floor

**Status:** Accepted
**Date:** 2026-09-16
**Branch:** `fix/technical-tab-empty`
**Amends:** D-50 (`docs/DECISIONS/D-50-paper-trade-exit-capture-schema.md`) — schema section and one headline statistic
**Plan:** `.sisyphus/plans/gate-enforcement-spine.md` (Sec.12 D5/D9/D1, Sec.4 REV7, Sec.8)
**Evidence:** `docs/SESSIONS/2026-09-16_paper-trade-evidence-audit.md`, `docs/SESSIONS/2026-09-16_gate-enforcement-spine-planning.md`

## Context

D-50 approved a 21-column exit-capture schema and restarted the measurement loop. Three
findings arrived after that record was written, all of which change it:

1. **The R:R contract is broken at the source (R18-R26).** `synthesis.py` picks a
   *desired* ratio first (`_calculate_dynamic_rr`, `:30-82`) and then places T2 wherever
   that ratio lands (`:1466` `t2 = round((entry_high or close) + risk_per_share * rr, 2)`).
   `target_1` is hardcoded at exactly 1.0R (`:1465`). The engine *declares* reward-to-risk;
   it does not *measure* it. Any gate step that consumes the resulting number would be
   validating a value authored by the subsystem it exists to police.
2. **D-50's headline statistic measured the wrong target.** D-50 (line 27-28) states
   *"Only 2/30 (7%) reach the 2.5:1 R:R floor (median 1.53)"*. That figure was computed on
   a **T1 basis**: `rr1 = (target_1 - entry)/(entry - stop)`. The blueprint's 2.5 floor is
   specified **at Target 2**. Re-derived from the archived cohort: T2 basis median 2.20,
   **11/30 (37%)** at or above 2.5.
3. **Neither number answers the selectivity question.** The cohort's targets were
   *engineered* to clear R:R >= 2.0 (the geometry invariant aims at exactly that bar, and
   `_get_structural_targets_long` keeps the **farthest** three levels,
   `sorted(set(...))[-3:]`, `:178`). The distribution therefore measures the **repair
   mechanism's success rate**, not setup quality. The plan's earlier
   "~93% rejection => 1-2 trades/week" throughput estimate is **withdrawn as unknowable**
   until the source is fixed.

Separately, a feasibility probe of the archived cohort showed the entry dates span
2026-09-03 to 2026-09-15: **oldest 13 days, median 11, and zero rows at or beyond 20
calendar days**. Swing holds run for weeks, so essentially every row is unresolved. **No
edge evidence exists, and none can exist until trades are actually recorded.**

## Decision

**1. Schema v2: 29 columns (21 ENTRY + 8 EXIT).** D-50's 21 columns are extended by
seven entry-provenance fields plus a version tag, and `shares` moves from the outcome
group to the entry group where it belongs.

| # | Column | Group | Why |
|---|---|---|---|
| 1 | `date_entered` | ENTRY | unchanged |
| 2 | `symbol` | ENTRY | unchanged |
| 3 | `sector` | ENTRY | unchanged (Portfolio Fit / concentration) |
| 4 | `action` | ENTRY | unchanged |
| 5 | **`entry_type`** | ENTRY | **new** — market / limit / stop; how the fill was obtained |
| 6 | `entry_price` | ENTRY | unchanged |
| 7 | `stop_loss` | ENTRY | unchanged |
| 8 | `target_1` | ENTRY | unchanged (but see R20: currently hardcoded 1.0R) |
| 9 | `target_2` | ENTRY | unchanged |
| 10 | `position_size_pct` | ENTRY | unchanged |
| 11 | **`account_value`** | ENTRY | **new** — makes `pnl_usd` computable; its absence is why the old record could not price anything |
| 12 | `shares` | ENTRY | **moved** from the outcome group — size is an *entry* fact, not an exit fact |
| 13 | `confluence_count` | ENTRY | unchanged |
| 14 | `signal_at_entry` | ENTRY | unchanged |
| 15 | **`gate_verdict`** | ENTRY | **new** — PASS / CONDITIONAL / FAIL as recorded at entry |
| 16 | **`gate_failed_step`** | ENTRY | **new** — which step killed or conditioned it |
| 17 | **`entry_low`** | ENTRY | **new** — the entry zone's lower bound; **without it neither R:R basis is reconstructable** (R22/R25) |
| 18 | **`entry_high`** | ENTRY | **new** — required to check the engine's own `entry_high`-based target construction (`:1464`) against the midpoint geometric measurement (`:194`) |
| 19 | **`risk_reward_planned`** | ENTRY | **new** — the R:R the plan *claimed* at entry, so it can be compared with what actually happened |
| 20 | **`gate_version`** | ENTRY | **new** — see decision 3 |
| 21 | `notes` | ENTRY | unchanged |
| 22 | `date_closed` | EXIT | unchanged |
| 23 | `exit_price` | EXIT | unchanged |
| 24 | `exit_reason` | EXIT | unchanged |
| 25 | `realized_r` | EXIT | unchanged |
| 26 | `pnl_usd` | EXIT | unchanged (now computable, via `account_value`) |
| 27 | `mfe_r` | EXIT | unchanged |
| 28 | `mae_r` | EXIT | unchanged |
| 29 | `plan_adherence` | EXIT | unchanged — process metric, not success metric |

**R25 was the decisive reason for the provenance block.** The archived CSV recorded
`entry_price`/`stop_loss`/`target_1`/`target_2` but not `entry_low`/`entry_high`, nor
which code path produced `rr`. Only 4/30 rows showed the mechanical `rr1 == 1.00`
signature (PAGP, LNG, CVX x2); the other 26 were inconsistent with *either* construction
rule, meaning the structural repair had fired and was **indistinguishable from
manufacture in the data**. We could not audit our own plans without writing a script to
reverse-engineer them. That must never be true again.

The change is **additive**: `docs/paper_trades/TEMPLATE.csv` is written with
`csv.DictWriter` against its own header, so every pre-existing key is still present and
the seven new fields simply arrive empty on any legacy row.

**2. `target_1` / scale-out: single exit for v1 (D9).** `target_1` is a fixed 1.0R
multiple carrying zero chart information (R20), and the scale-out schedule is anchored to
that same manufactured number (`:1701`, `:1734`). Worse, a 30/30/40 tranche blend breaks
the definition of `realized_r` *and* can exit 30% of the position at a "1R" level that
contradicts the plan's own declared targets. For v1 there is **one target, one stop, and
one exit price**, so `realized_r = (exit_price - entry_price) / (entry_price - stop_loss)`
is exactly true. `trade_plan.scale_out` becomes **advisory/display-only**. Tranche
tracking returns in v2, with **target-anchored** levels rather than R-multiples.

**3. Sequencing: ship enforcement now, defer the R:R floor (REV7).** This reverses the
plan's original ordering, which held enforcement until the R:R contract was fixed. The
gate ships in Wave 1 with the three tests that do not depend on the broken contract:

| Test | Checks | Needs 1H? |
|---|---|---|
| **5a** stop ceiling — `abs(entry - stop)/entry <= MAX_STOP_DISTANCE_PCT` | entry, stop | **no** |
| **5b** stop on the correct side + risk > 0 (catches the VZ blank stop) | entry, stop | **no** |
| **5c** consistency assertion — `abs((target - entry_basis)/(entry_basis - stop) - rr) <= tol` | the reported tuple's self-agreement | **no** |
| **5d** reward ladder — PASS at `r2 >= 2.5`, CONDITIONAL at `r2 >= 2.0 and r1 >= 1.0` | target_1, target_2 | **yes — deferred** |

**The reasoning for shipping now.** The binding constraint is *elapsed time*, not
analysis: the archived cohort's oldest row is 13 days old and no row has reached 20, so
the measurement loop cannot produce a single edge number yet. Every week spent waiting
for the source fix is a week added before the first honest expectancy figure. Waiting
would buy exactly one test (5d) and cost weeks of clock.

**And 5d is not the test that catches the worst case.** The worst row in the entire
cohort is **BULL**: it had the *best* R:R to T2 (4.60) **and** a 22.8% stop. A reward
ladder passes it. Only **5a** fails it — and 5a ships today. The broader claim that wide
stops were the cheapest way to manufacture R:R was also **corrected by measurement**: of
the six highest-T2-R:R rows, only BULL fails a 10% ceiling (PSX 3.71 @ 4.6%, PSX 3.69 @
4.7%, DOCU 3.66 @ 6.5%, LRCX 3.19 @ 5.7%, MU 3.17 @ 6.5% all pair tight stops with high
R:R). The ceiling is a **targeted outlier guard over roughly five rows**, not a mass
filter.

**4. `gate_version` exists to make the deferral survivable.** Because the gate will be
active for part of the sample's life with only three of four Step-5 tests, the resulting
sample is **heterogeneous by construction**. `gate_version` records which gate was in
force at entry so the two eras can be segmented out and never silently averaged
together.

**5. D1 is approved in principle but deferred in activation.** Both tiers are accepted —
PASS at `r2 >= 2.5` at full size, CONDITIONAL at `r2 >= 2.0` with `r1 >= 1.0` at half
size. But `r2` is precisely the field the source fix must make honest, so the tier logic
cannot be activated before it. Until then, Step 5 runs 5a/5b/5c and the output must state
**"R:R floor not yet active; rate unknown until the R:R source fix lands"** rather than
quoting any forecast.

## Consequences

**Benefits**
- The measurement loop can start now instead of after an unbounded source fix.
- `entry_low`/`entry_high`/`risk_reward_planned`/`gate_version` make every future plan
  auditable without reverse-engineering, closing R25 permanently.
- `account_value` makes `pnl_usd` computable, closing a defect carried since the first
  record.
- Single exit makes `realized_r` exactly true rather than approximately true.
- The worst observed row (BULL) is caught by a test that ships in Wave 1.

**Costs / risks**
- **The sample becomes heterogeneous** (pre-/post-`gate_version`). Mitigated by the
  column itself; the risk is that someone averages across it anyway.
- **`pnl_usd`, `mfe_r`, `mae_r`, `plan_adherence` remain hand-populated** until exit
  tooling exists. If Step 4 is skipped again, the loop silently reopens — still the
  single biggest ongoing risk (unchanged from D-50).
- **The R:R floor is not enforced for the first weeks of the new sample.** Accepted
  explicitly, because the alternative is recording nothing at all.
- **`target_1` is still written into the CSV while being untrustworthy** (R20). It is
  retained for continuity and because `risk_reward_planned` now lets a reviewer detect
  the 1.0R signature directly.
- **The voided cohort remains voided.** Nothing here rehabilitates the 31 archived rows,
  and no threshold may be tuned against them.

**Corrections carried into D-50**
- D-50's headline "2/30 (7%)" is **T1-based**; the T2-based figure is **11/30 (37%)**;
  **neither is a selectivity measure**. D-50 carries an amendment note pointing here.
- D-50's "29/31 rows violate the 5% single-name cap" is **understated in precision**: R21
  found there is **no enforced cap at all** — four conflicting values exist
  (`TradePlan.max_position_pct = 10.0`, inert; `conviction_caps` up to `0.25`, effective;
  `paper_trading_validator.py:139 = 0.20`; `professional/models.py:217 = 0.05`), and the
  README's "5%" matches none of them. Sizing is a Wave-1 item (2D) precisely because the
  cap it was supposed to enforce does not exist.

**Renumbering:** the plan previously projected **D-51** for the R:R source fix (phase 1H).
That record moves to **D-52**; this schema + sequencing decision takes D-51.

## Files

- `docs/paper_trades/TEMPLATE.csv` — rewritten to 29 columns (21 ENTRY + 8 EXIT)
- `docs/DECISIONS/D-50-paper-trade-exit-capture-schema.md` — amendment notice + statistic correction
- `docs/DECISIONS/index.md` — D-51 added
- `.sisyphus/plans/gate-enforcement-spine.md` — Sec.4 REV7, Sec.5 §1E test table, Sec.8 waves, Sec.12 D1/D5/D9 rows, front-matter banner
- `docs/SESSIONS/2026-09-16_gate-enforcement-spine-planning.md` — decision + verification passes
- `INDEX.md`, `docs/index.md` — refreshed

No application source code was modified by this decision.
