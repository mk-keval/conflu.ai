# Bundle A — Exit & Gate Geometry (FWD-v0.2)

**Status:** **FROZEN 2026-10-28 (D-77); LIVE 2026-10-29.** Decisions A1–A5 signed
off as recommended. Implemented in `dad6ac8`; the go-live commit flips
`CURRENT_SAMPLE_VERSION` to `v0.2`. The clock starts at the first v0.2 fill.
**Date:** 2026-10-28
**Scope:** P1-6 (exit policy per setup family), P1-7 (gate R:R measured on the
exit that pays), P1-8 (wire or delete the dynamic management plan), P4-15 (use
MFE). This is the design that FWD-v0.2 will trade.
**Out of scope:** Bundle B (regime permission, menu, ranking, sector rotation,
sizing, stops, entry rules). Those stay frozen and are a separate decision.
**Related:** `PIPELINE_AUDIT.md` F5, `D-51` (single exit for v1),
`D-58` (structural targets), `D-74` (measurement), `D-75` (pass bar),
`D-76` (sample versioning), `D-77` (this sign-off),
[`PRE_REGISTRATION-v0.2.md`](PRE_REGISTRATION-v0.2.md).

---

## 1. Why this exists

The v0.1 sample measured a plan whose gate and exit did not agree:

- Targets come from `synthesis._get_structural_targets_long`, which keeps the
  **highest** three structural levels within `1.5 × price`.
- The gate's R:R is measured to the **last** target (`_geometric_rr_long`).
- The exit walker pays the **first** target it touches (`exits.infer_exit`).
- The dynamic plan (`scale_out`, `trail_type`, `trail_activation_r`,
  `move_to_breakeven_at_r`) is computed and then discarded.

CRS is the clean example: gated at **4.32:1**, stored T1 at **11.2R from the
zone midpoint / 27.7R from the actual fill**, reached **+3.72R MFE**, and
stopped at **−1.00R**. The 2.5:1 floor was satisfied by a target the exit was
never going to pay in a normal swing.

D-51 deliberately shipped one exit in v1 because `target_1` was a manufactured
1.0R number and a 30/30/40 blend made `realized_r` ambiguous. It explicitly
said tranche tracking returns in v2 **with target-anchored levels**, not
R-multiples. This is that v2.

---

## 2. Definitions (one definition each)

| Term | Definition |
|---|---|
| **Planned fill** | `entry_low` for a limit order (worst-case planned fill). A next-session gap below the limit fills better; that is recorded in `entry_price`, not assumed by the gate. |
| **Risk (1R)** | `planned_fill − stop_loss`, per share. |
| **T1 / T2 / T3** | Target-anchored structural levels, ascending. T1 is the first exit that pays. |
| **Plan R** | `(T1 − planned_fill) / risk`. This is the gate metric. |
| **Stretch R** | `(T3 − planned_fill) / risk`, reported for context only. |
| **Realized R** | `(vwap_exit − entry_price) / (entry_price − stop_loss)`. With partial exits, `vwap_exit` is the share-weighted average exit price, so this is exactly the share-weighted average leg R. |
| **P&L** | `shares × (vwap_exit − entry_price) − costs`. Costs are the 10 bps fee + 5 bps slippage per side, summed over the entry and every exit leg. Because the rate is constant, `(entry + vwap) × shares × rate` is exactly the sum of the legs. |
| **MFE / MAE** | Maximum favorable / adverse excursion in R over the full hold, ending at the final exit. `MFE capture = realized R / MFE R`. |

The v0.1 rows keep their existing single-exit values. No row is rewritten.

---

## 3. Target hierarchy (P1-6 / P1-7)

### 3.1 Candidate levels

1. Collect structural resistance and swing highs above the planned fill,
   within `1.5 × price`.
2. Add the measured-move projection when price is above all known structure:
   `price + (prior swing range)`, if it is within `1.5 × price`.
3. Deduplicate, sort ascending.
4. Discard levels that are closer than the family's **half-size floor** — a
   level that pays less than that is a speed bump, not an objective.

The old fixed-percentage / ATR-multiple fallback targets are **removed**. A
target must come from structure or a measured move. If neither exists, the
trade is rejected (`no structural objective`). That is the patient choice.

### 3.2 Selection

- **T1** = the first candidate with `half_size_floor ≤ r ≤ max_t1_r`. The
  half-size floor is the gate's CONDITIONAL floor (2.0R trend/breakout, 1.25R
  mean reversion, 1.75R rotation), so a marginal first target can still be
  taken at half size instead of being silently rejected.
- **T2** = the next candidate above T1; blank if none.
- **T3** = the next candidate above T2; blank if none.
- If no candidate is inside the T1 band:
  - all candidates below `half_size_floor` → reject `target too close`;
  - the nearest candidate above `max_t1_r` → reject `target too far`;
  - no candidates at all → reject `no structural objective`.
- The selected T1/T2/T3 are stored on the row. The gate and the exit walker
  read those stored levels; they never re-derive them from a different basis.

### 3.3 Family bands

| Family | Screens (by `screen_name`) | half-size floor | full-size (PASS) | max T1 | Time stop |
|---|---|---|---|---|---|
| `trend` | Trend Follower, Trend Follower v2, Trend Leader, Trend Pullback v2, Institutional Trend Follower, Institutional Swing Quality, Institutional Quality v2, Quality Trend + Fundamentals, High-Conviction Stack, Institutional Accumulation | **2.0R** | **2.5R** | **4.0R** | 30d |
| `breakout` | 52-Week Breakout, Bull Flag Continuation, VCP Breakout, Volatility Expansion, Low-Vol Setup | **2.0R** | **2.5R** | **5.0R** | 20d |
| `mean_reversion` | Mean Reversion, Statistical Mean Reversion | **1.25R** | **1.5R** | **2.5R** | 10d |
| `rotation` | `Sector Rotation: *`, `Sector Rotation Holdings` | **1.75R** | **2.0R** | **3.0R** | 15d |
| `unknown` | anything else | 2.0R | 2.5R | 4.0R | 20d |

The half-size floor is exactly the gate's CONDITIONAL floor below; the
full-size column is the PASS floor. This keeps the D1 half-size tier reachable
instead of dead code.

The bands are measured from the **planned fill**, not the zone midpoint. A
zone-midpoint R is still reported for continuity with the ticker page, but it
is not the gate metric.

**Why T1, not a blended R:** T1 is the first exit that actually pays. A blend
of T1/T2/T3 can look good while T1 is unreachable — the exact v0.1 failure. The
stretch levels are reported but cannot rescue a bad T1.

---

## 4. Gate (P1-7)

### 4.1 Step 5d — the floor

| Family | PASS | CONDITIONAL (half size) | FAIL |
|---|---|---|---|
| `trend`, `breakout` | T1 ≥ 2.5R | 2.0R ≤ T1 < 2.5R with T1 ≥ 1.0R | T1 < 2.0R |
| `mean_reversion` | T1 ≥ 1.5R | 1.25R ≤ T1 < 1.5R | T1 < 1.25R |
| `rotation` | T1 ≥ 2.0R | 1.75R ≤ T1 < 2.0R | T1 < 1.75R |
| `unknown` | T1 ≥ 2.5R | 2.0R ≤ T1 < 2.5R with T1 ≥ 1.0R | T1 < 2.0R |

The existing D1 tier (2.0–2.5R, half size) is preserved for trend/breakout and
unknown. Everything else about the seven-step gate is unchanged.

### 4.2 Step 5c — consistency

`_rr_consistency` compares the verdict's reported `risk_reward` (now **Plan R
to T1**) with T1 R recomputed from the planned fill and stored stop, tolerance
`0.15`. A mismatch is CONDITIONAL, never a silent pass.

### 4.3 What changes in the verdict

- `risk_reward` now means **Plan R to T1**, not R:R to the last target.
- `targets[0..2]` are the selected T1/T2/T3, not the highest three levels.
- The trade plan keeps `scale_out` but anchors each leg to a **target price**
  (`T1`, `T2`) and a size fraction, not an arbitrary R multiple.
- `plan_rr` on the journal row is the gate's Plan R (T1, planned-fill basis);
  `target_1_r` is the same number after the fact; `stretch_rr` is T3 R.
  They should agree within tolerance, and the verifier checks it.

---

## 5. Exit policy per family (P1-6 / P1-8)

### 5.1 Legs

| Family | T1 leg | T2 leg | Runner | Notes |
|---|---|---|---|---|
| `trend` | **1/3** at T1 | **1/3** at T2 (if T2 exists) | **1/3** trailed | If T2 is missing, its 1/3 joins the runner (2/3 trailed). |
| `breakout` | **1/2** at T1 | — | **1/2** trailed | T2/T3 are displayed as stretch references; the runner is not capped. |
| `mean_reversion` | **100%** at T1 | — | — | A reversion trade has no runner; the target is the mean. |
| `rotation` | **100%** at T1 | — | — | Unvalidated path (F8); conservative single exit until Bundle B. |
| `unknown` | **100%** at T1 | — | — | Preserves the v0.1 single-exit behavior for anything unmapped. |

### 5.2 Stop management

| Family | Breakeven | Trail |
|---|---|---|
| `trend` | At the close of the first bar whose high ≥ entry + **1.0R**; active next bar | After T1 fills: `max(entry, highest_close_since_entry − 2.0 × ATR14)`, active next bar, never loosens |
| `breakout` | Same, **+1.0R** | After T1 fills: `max(entry, highest_close_since_entry − 2.5 × ATR14)` |
| `mean_reversion` | None (full exit at T1) | None |
| `rotation` | Same, **+1.0R** | None |
| `unknown` | Same, **+1.0R** | None |

If ATR14 is missing at entry, the trail distance is `2 × (entry − stop)` —
always available, and never tighter than the initial risk.

### 5.3 Time stop

The family time stop is a **calendar-day** limit, converted to the first
session on/after the cutoff (the existing `hold_limit_bars` behavior). At the
time stop, exit all remaining shares at that bar's close. The synthesis
`max_hold_days` is overridden by the family value for v0.2; the row records
which value was used.

### 5.4 Simulation order (one function, one convention)

For each bar after the entry bar, in this order:

1. **Active stop** (original, breakeven, or trail): gap through → fill at the
   open (worse); touched → fill at the stop. A bar that touches both the stop
   and a target is **ambiguous and the stop wins**, same as v0.1.
2. **T1 limit** (if not yet filled): fill the T1 fraction at T1.
3. **T2 limit** (if any): fill the T2 fraction at T2.
4. **Time stop** at the close: exit the remainder.

Activation rules:

- Breakeven is evaluated at the **close** of the bar that first reaches the
  trigger; the stop is at entry from the next bar. This avoids guessing the
  intrabar sequence.
- The trail is activated after T1 fills and is updated at each close. It is a
  stop order at the trail level; a gap below it fills at the open.
- A gap above a target fills at the target (conservative convention, same as
  v0.1). The MFE still records the gap.
- The entry bar's excursion is excluded, same as v0.1 (D-74/R4). Partial exits
  never occur on the entry bar.

### 5.5 What is recorded

- `exit_legs`: JSON list of `{date, price, shares, size_pct, reason}`.
- `exit_price`: share-weighted average of the legs.
- `realized_r`: weighted average R (exactly the canonical formula above).
- `exit_reason`: `scale_out` when there is more than one leg; otherwise the
  single leg's reason (`target_1`, `target_2`, `trail`, `stop`, `time_stop`).
- `pnl_usd`, `pnl_gross_usd`, `costs_usd`: canonical `pnl.dollar_pnl` on the
  weighted average exit and total shares (exactly equal to the leg sum).
- `mfe_r`, `mae_r`: full hold, as today.
- `plan_adherence`: 1.0 when every planned leg fired as designed; 0.5 when a
  trail/time stop closed the remainder; 0.0 when a stop or manual action
  overrode the plan.

---

## 6. Data model changes

| Table | Column | Purpose |
|---|---|---|
| `paper_trades` | `setup_family TEXT` | `trend` / `breakout` / `mean_reversion` / `rotation` / `unknown`; drives the exit policy. |
| `paper_trades` | `exit_legs TEXT` | JSON audit trail for partial exits. |
| `paper_trades` | `stretch_rr REAL` | T3 R from the planned fill, context only. |
| `paper_trades` | `atr_at_entry REAL` | Trail distance; if missing, the fallback is `2 × risk`. |
| `pending_orders` | `setup_family TEXT` | Inherited by the filled journal row. |
| `pending_orders` | `atr_at_entry REAL` | Same. |

Existing rows keep `setup_family=NULL` (pre-family, single exit) and
`exit_legs=NULL`; new rows always carry a family, including `unknown`. A NULL
family is the honest marker for "this row predates the family policy" and is
never re-simulated. The migration is additive; no existing value changes.

`plan_rr` is redefined as **Plan R to T1** (planned-fill basis). For v0.1 rows
it keeps its historical value; the scorecard and verifier only compare rows
within the same sample version.

---

## 7. Replay H-09 (exploratory, not evidence)

**Question:** does the v0.2 geometry improve the same signal stream, or does it
just reject more trades?

**Design:**

- Same window, universe and cost model as the 2-month replay (D-71).
- Same signal generation and screen menu as v0.1; only the target selection,
  gate floor and exit policy change.
- Entry: next-session fill using the D-73 rules (limit at `entry_low`, cancel
  if the open is through the stop, no same-bar fill). This is stricter than
  the current replay's next-open entry; it matches the live execution model.
- Exit: the same `exit_policy.simulate_exit` used live, with daily bars.
- Store in `replay_runs` / `replay_trades` with `rules_version='v0.2'`.
- Run **once** after the spec is frozen. It is exploratory (H-09): it may
  inform a future version, but it is never confirmatory evidence for FWD-v0.2
  and never enters the forward scorecard.
- Report: signals, fills, rejections, expectancy, PF, average loss, MFE
  capture, exit-reason mix, and the v0.1-vs-v0.2 delta on the same signals.

---

## 8. Freeze and go-live protocol

The earlier plan said "flip `CURRENT_SAMPLE_VERSION` and
`SCORED_SAMPLE_VERSION` in the freeze commit." That is unsafe: if the daily
loop creates a row between the freeze and the code going live, the row is
stamped `v0.2` but traded under the old rules.

Corrected sequence:

1. **Spec freeze commit** — this document becomes `FROZEN`; set
   `SCORED_SAMPLE_VERSION = "v0.2"` (the scorecard now expects v0.2).
   **Keep `CURRENT_SAMPLE_VERSION = "interim"`.** No row is v0.2 yet.
2. **Implementation commits** — `exit_policy`, synthesis target selection,
   gate, journal columns, sync, verifier, tests. The daily loop may continue;
   every new row is still `interim` and never evidence.
3. **Go-live commit** — set `CURRENT_SAMPLE_VERSION = "v0.2"`, update the
   pre-registration with the freeze date and "first fill TBD", and run the
   verifier. The v0.2 clock starts at the **first fill after this commit**.
4. **H-09 replay** — after go-live, exploratory only.

**Executed 2026-10-29:** implementation landed as `dad6ac8` (213 focused tests
and the verifier passed); this go-live commit sets `CURRENT_SAMPLE_VERSION =
"v0.2"`. First v0.2 fill: TBD. No v0.2 row existed before this commit.

This preserves the rule that a row is traded under the version it is stamped
with.

---

## 9. Test plan

**Unit**

- Target selection: nearest-first, skip sub-min levels, T1 band, max cap,
  no-target rejection, measured-move fallback, T2/T3 gaps.
- Gate: Plan R to T1 from planned fill; PASS/CONDITIONAL/FAIL per family;
  consistency mismatch; old "last target" path removed.
- Exit simulation: T1-only, T1+T2, runner trail, breakeven activation, gap
  through stop/trail, same-bar stop-vs-target ambiguity, time stop, missing
  ATR fallback, entry-bar exclusion.
- Accounting: weighted exit price, weighted R, leg-sum P&L equals vwap P&L,
  costs per leg.
- Versioning: v0.1 rows keep single exits; `unknown` family uses single exit;
  pending fills inherit family/ATR.

**Integration**

- `_build_row` stores family, T1/T2/T3, plan R, stretch R, ATR.
- Pending fill creates a v0.2 row with the same family and ATR.
- `sync_exits` writes `exit_legs`, weighted exit, weighted R, net P&L.
- `verify_journal.py` fails on a leg/vwap/R mismatch and on a plan-R gap.
- `scorecard.py` uses the weighted `realized_r`; D-75 pass bar unchanged.

**Regression**

- The 81 focused journal/pending/verification/scorecard/endpoint tests.
- A v0.1 fixture still produces the historical single-exit values.
- No v0.1 row is re-simulated by the new exit policy.

---

## 10. Sign-off — decisions resolved 2026-10-28 (D-77)

All five were approved as recommended. They are now frozen; changing any of
them requires a new sample version, not an amendment to this one.

| # | Decision | Frozen choice | Rejected alternative and why |
|---|---|---|---|
| A1 | Gate metric | **T1 R from the planned fill** — `(T1 − entry_low) / (entry_low − stop)` | A blended T1/T2/runner R lets a runner inflate the score while T1 is unreachable — the CRS failure in a new costume. Last-target R:R is the v0.1 defect. |
| A2 | Trend/breakout exits | **Trend 1/3 at T1 + 1/3 at T2 + 1/3 trailed; breakout 1/2 at T1 + 1/2 trailed; BE at +1R; 2.0× / 2.5×ATR trail** | A single 1/2-at-T1 rule loses the second structural objective and makes trend and breakout indistinguishable in the scorecard. A single exit abandons the runner and makes P1-6/P1-8 a no-op. |
| A3 | Family map | **Four families + `unknown`** (`trend`, `breakout`, `mean_reversion`, `rotation`) | One policy for all long setups ignores that a reversion snap-back and a 52-week breakout have opposite hold profiles. `unknown` preserves the v0.1 single exit for unmapped screens. |
| A4 | No target in band | **Reject the trade** — `target too close` / `target too far` / `no structural objective` | An ATR/measured-move fallback at ~3R reintroduces a manufactured level, the exact thing D-58 removed, and makes the gate test a number not visible on the chart. |
| A5 | Mean reversion | **Full exit at T1; 10-day time stop; no runner** | Partial + trail treats a reversion trade like a trend and exposes the remainder to the reversion failing after T1. |

**Freeze record.** Signed off by the user on 2026-10-28 after reviewing A1–A5
with the CRS case (`gate 4.32`, T1 `27.7R` from the fill, MFE `+3.72R`, exit
`−1.00R`). No code behavior changed before this sign-off. The implementation
landing under this spec is tracked by D-77; v0.2 remains unpopulated until the
go-live commit.
