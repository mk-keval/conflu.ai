# Pipeline Audit — Screener → Gate → Exit

**Date:** 2026-10-19
**Type:** Read-only audit of the deployed decision pipeline (code + config + journal). No
code or DB changes were made.
**Scope:** regime detection → screen selection → morning brief → gate enforcement →
sizing → journal → exit sync.
**Method:** traced the live code paths, read the deployed regime/screen config, and
inspected `data/paper_trades.db` (read-only queries). Cross-checked against the replay /
what-if artifacts from the same date.
**Code state:** branch `fix/technical-tab-empty`, HEAD `8001ea5` (all committed).

> **Update — execution v0.1 applied (2026-10-19):** the user approved the recommended
> pre-sample option. F1 (screen/confluence/regime attribution), F2 (sector persistence +
> real 30% cap), F3 (persist and execute the plan's calendar-day time stop), and the
> legacy-row exclusion in F4 are now implemented. F5 (target hierarchy / R:R measured on
> the exit target) was **not** changed — it stays review item A. The 3 pre-instrumentation
> rows (NTNX/WBD/NVDA) are flagged `exclude_from_stats=1` but remain open and visible.
> See §6 for the change list.

---

## TL;DR

The pipeline is genuinely wired end-to-end — the gate is **not** decorative. But the
system that is actually running is materially weaker than the system described in the
docs/config, for five reasons:

1. **Choppy days run trend screens.** The mean-reversion screens are effectively
   benched: `ranging` is unreachable, and the `choppy` menu is
   bull-flag + trend-pullback + low-vol — exactly the combination the 2-month replay
   measured as the worst. This is a *design* gap, not a bug.
2. **The R/R gate is measured to the furthest target, while exits pay the first
   target.** The 2.5:1 floor is therefore non-binding, and the first target in the live
   book is **~8–11R away**. A plan can pass the gate and still be unreachable.
3. **The live exit loop has no time stop.** The verdict computes `max_hold_days`
   (20/30/60), the journal has no such column, and the exit walker receives `None`.
   Trades can stay open indefinitely if neither the stop nor a distant target hits.
4. **Four bookkeeping fields are broken** (template/screen, confluence, sector,
   max_hold). This disables the sector-exposure cap and makes the per-screen forward
   table (review item C) impossible.
5. **There is no regime permission, no cross-screen ranking, and no per-day entry
   cap.** The book is filled in screen order until the 8-position cap.

**Consequence for the forward test:** it can measure the *deployed* system, but not the
replay system, and not per screen. The measurement plumbing should be fixed before the
sample starts (no trading-decision changes). The exit/target defects are the first
review decisions, because they define what counts as a win.

---

## 1. What the pipeline actually does

| Step | Where | Actual behavior |
|---|---|---|
| Regime | `infrastructure/market/regime.py` | Composite 0–100 → 6 labels (`Exuberance … Crisis`), pure score thresholds (no hysteresis). |
| Label → key | `professional/morning_brief.py:59-66` | Only **4 keys** are ever produced: `strong_trend`, `neutral`, `choppy`, `high_vol`. **`ranging` is never emitted.** |
| Screen selection | `professional/regime_selector.py:296-329` | Top-3 primaries by weight; the weakest slot is replaced by the highest-weight `defensive`. |
| Choppy menu | `config/regime_screens.yaml:44-49` | `bull-flag-continuation` (85), `trend-pullback-v2` (80), `low-vol-setup` (65, defensive). |
| Ranging menu | `config/regime_screens.yaml:51-55` | `statistical-mean-reversion`, `mean-reversion`, … — **dead code** (no label maps here). |
| Screens | `infrastructure/screener/tv_engine.py` | TV discovery (≤500 matches) → elite enrichment → confluence score, sorted **descending within a screen** (`:188`) → top 500. |
| Brief | `professional/morning_brief.py:184-244` | Takes the **top 9 per screen**, de-duplicates across sections, adds a 4th **sector-rotation** section (top 3 holdings of the leading sector ETF, scored by a bespoke yfinance function). |
| Candidate filter | `api/routers/workflow.py:494-503` | Every brief ticker with `conviction >= min_conviction` (default **5**). The brief's conviction is a **3-level** elite signal: high=8, medium=5, low=3 → default 5 passes “medium” and therefore almost everything not “low”. |
| Per-candidate work | `workflow.py:510-548` | Full ticker analysis (45 s timeout each), gate evaluation, sizing, upsert. **No cross-screen rank, no daily cap, no regime check.** |
| Gate | `domain/workflow/gate.py` | 7 steps: liquidity, structure, positioning, catalyst, R/R, portfolio fit, conviction. Hard FAIL rejects; CONDITIONAL is **accepted at half size**. |
| Gate caps | `gate.py:45-47` | `MAX_OPEN_POSITIONS = 8`; duplicate-symbol rule; `SECTOR_EXPOSURE_LIMIT_PCT = 30` (by planned size). |
| R/R floor | `gate.py:302-396` | PASS at ≥2.5, CONDITIONAL at ≥2.0 **if r1 ≥ 1.0**. Measured on the **reported** R/R (to the last target), not T1. |
| Sizing | `domain/workflow/sizing.py` | `size% = 1% risk / stop distance`, hard cap 25%, floor 0.5%; CONDITIONAL → ×0.5. |
| Journal | `domain/workflow/journal_store.py` | SQLite `data/paper_trades.db`; entries, rejections, runs. |
| Exits | `domain/workflow/exits.py` | Stop first (gap-aware), then **T2**, then **T1**, then time stop *if `max_hold_days` is supplied*. Full exit — no scaling, no trail. |
| Exit sync | `workflow.py:802-833` | Reads `target_1/2` and `max_hold_days` from the journal row. |

The replay mirrors the screen mix (`backtest/replay.py:110-187`) but not the gate, the
brief ranking, the 4th sector screen, the structural targets, or the live exit rules.
It uses ATR stop 2.0 / target 3.0 / **15-bar max hold**.

---

## 2. Findings

### P0 — Measurement integrity (fix before the forward sample; no decision change)

#### F1. No screen attribution in live rows
- **Evidence:** `workflow.py:662-668` reads `confluence_score` and `screen_name` from
  the **verdict** (`v`), not from the brief ticker; the verdict has neither field
  (`AnalysisVerdict` has `extra="forbid"` and no such keys). The CLI path
  (`backend/scripts/paper_trade_from_brief.py:348-370`) does not write `template` at
  all. All 3 open rows have `template = NULL`, `confluence_count = 0`.
- **Impact:** review item C (per-screen forward confirmation) cannot be built. The
  journal cannot say which screen produced a winner.
- **Class:** bug — pure bookkeeping.
- **Fix sketch:** pass the brief ticker through `_build_row` and store
  `screen_name`/`confluence_score` (and the regime used) on every row and rejection.
- **Status (2026-10-19): FIXED.** Both the router and CLI now take screen/confluence
  from the brief ticker and store the market regime from the brief. Rejections carry
  `template`/`regime` columns. A regression test covers the router path.

#### F2. Sector is never stored → the 30% sector cap is dead
- **Evidence:** `_build_row` takes `sector = v.get("sector", "")`
  (`workflow.py:624`), but `AnalysisVerdict` has **no sector field** (it is on
  `TickerAnalysisResponse`, one level up). All 3 open rows have `sector = NULL`.
  `evaluate_portfolio_fit` compares journal sectors to the candidate sector
  (`gate.py:452-465`); with `None` vs `""` nothing ever matches.
- **Impact:** five correlated names can enter as “different sectors”; the one
  portfolio-level concentration control that exists does nothing.
- **Class:** bug (also a real risk-control gap).
- **Fix sketch:** populate sector from the analysis **response**, persist it, and add
  a regression test that two same-sector entries trip the cap.
- **Status (2026-10-19): FIXED.** `_build_row` reads the response sector in both paths;
  the sector check uses the unhalved risk-based size (upper bound). Tests cover the
  router cap and the CLI cap.

#### F3. `max_hold_days` is never persisted
- **Evidence:** the plan computes it (`synthesis.py:1801-1807`: 20/30/60 days), but
  the `paper_trades` schema has no such column (`journal_store.py` schema), no writer
  stores it, and `workflow.py:808` reads a missing key → `None`. `exits.infer_exit`
  therefore has no time stop.
- **Impact:** the live exit rules differ from the documented plan and from the replay;
  trades with distant targets can remain open forever, so the 30-closed-trade trigger
  may never arrive and `mfe_r` is never recorded for them.
- **Class:** bug (execution/measurement).
- **Fix sketch:** add the column + migration, write it at entry, read it in both exit
  paths. Wiring it changes outcomes — decide explicitly (see §3).
- **Status (2026-10-19): FIXED (execution v0.1).** `max_hold_days` is stored at entry
  and both exit paths now execute it. The plan's value is **calendar days**; the exit
  walker counts trading bars, so a `hold_limit_bars` helper converts the cutoff to the
  first session on/after the calendar date. Existing rows have no value (the 3 legacy
  rows are excluded from stats). This is the one approved behavior change.

#### F4. No forward run has been logged yet
- **Evidence:** `workflow_runs = 0`, `rejections = 0`; 3 open rows from 2026-10-05/06.
  Those rows carry values inconsistent with the current plan geometry (e.g. planned
  R/R 55.2, 134.5, 8.06 with targets 20–83% away) — they predate the current
  instrumentation and are not a clean forward sample.
- **Impact:** the forward clock has not visibly started in the journal of record.
- **Class:** operations.
- **Fix sketch:** decide explicitly whether to keep the 3 rows as “legacy/out-of-sample”
  or archive them; then run the daily after-close button and confirm a `workflow_runs`
  row appears.
- **Status (2026-10-19): APPLIED.** The 3 rows are flagged `exclude_from_stats=1`
  (visible/open; skipped by expectancy and rolling metrics). `workflow_runs` now has its
  first row: run id 1, 1 accepted (PM), 4 rejected, 0 exits. The sample clock is running.

### P1 — Behavior defects (review decisions; do not change mid-sample)

#### F5. Target geometry: the first target is ~8–11R away; the gate’s R/R metric is not what the exit pays
- **Evidence:** live targets come from `synthesis._get_structural_targets_long`
  (`synthesis.py:81-153`): it keeps the **highest 3** structural levels within
  `1.5 × price`, including swing highs from the full 2-year window. `risk_reward` is
  computed to the **last** target (`_geometric_rr_long`, `:156-171`), and the gate
  checks that number (`gate.py:302-396`). The exit walker pays the **first** target it
  touches (`exits.py:120-137`). Stored open rows:
  - NTNX: entry 67.74, stop 65.92, **T1 82.89 (+8.2R)**, planned R/R 55.2
  - WBD: entry 29.87, stop 27.60, **T1 54.62 (+10.9R)**, planned R/R 134.5
  - NVDA: entry 220.45, stop 207.89, **T1 390.24 (+8.1R)**, planned R/R 8.06
- **Impact:** the 2.5:1 gate is trivially satisfied by a far target; the plan that is
  actually executable (T1) is 8–11R away. Most trades should be expected to stop out
  or sit open. This is the live analogue of the “1.05R winners” problem — but in the
  opposite direction.
- **Class:** design (target selection) + bug (decision metric ≠ exit metric).
- **Fix sketch:** choose the nearest meaningful resistance as T1 (cap at a sane swing
  distance, e.g. 2–4R); compute the gate R/R on the level the exit will pay; optionally
  scale out at T1 and let a runner go to T2/trail. One coherent hierarchy.
- **Status (2026-10-19): OPEN — review item A.** Explicitly deferred; the sample will
  measure the current targets/R:R gate. Do not change mid-sample.

#### F6. Choppy serves continuation; mean reversion is benched; `ranging` is unreachable
- **Evidence:** `morning_brief.py:59-66` (4 keys only), `regime_screens.yaml:44-55`,
  `regime_selector.py:296-329`. The choppy menu is bull-flag / trend-pullback /
  low-vol. `mean-reversion` appears **only** under `ranging`; `statistical-mean-reversion`
  only as a neutral defensive and loses the choppy defensive slot to low-vol (65 > 60).
- **Impact:** the replay put 242 of 371 trades (65%) and **94% of the dollar loss** in
  choppy sessions; every deployed choppy screen lost ≈ −0.35R. The what-ifs show a
  mean-reversion-only chop menu is ≈ flat gross (−0.015R) — not a profit machine, but
  the correct battlefield. The live config does the opposite.
- **Class:** design (playbook).
- **Fix sketch:** rebuild the choppy menu around the only chop-flat screen; make
  `ranging` reachable (or delete it); re-tune weights to the corrected validation,
  not the superseded D-61 stats (already flagged in `regime_screens.yaml:15-22`).

#### F7. No permission, no cross-screen rank, no daily cap
- **Evidence:** enforce has no regime input (`workflow.py:471-600`); candidates are
  every brief ticker above the coarse conviction floor, in section order; only the
  8-position book cap limits entries. `min_conviction=5` passes “medium”.
- **Impact:** on a bad day the system can still fill the book; the ranking that exists
  (confluence, within screen) is discarded at the decision step; the 4th sector section
  is included regardless of regime.
- **Class:** design (permission + selection).
- **Fix sketch:** a permission state (normal/reduced/stand-aside) driven by regime;
  a cross-screen ranking (confluence + RS + catalyst) with top-N/day; a daily entry
  cap; gate the sector section on regime.

#### F8. The 4th “sector rotation” screen is unvalidated and bypasses the templates
- **Evidence:** `morning_brief.py:207-230`, `_score_holding_sync` (`:458-515`). It buys
  the leading sector ETF’s top holdings at market with a 2–8% stop and 2R/3R targets,
  using its own scoring; it is not in the replay and not in the template validation.
- **Impact:** up to 3 live candidates/day come from a strategy with no backtest and no
  forward attribution (F1 makes it unmeasurable).
- **Class:** design (selection) + measurement.
- **Fix sketch:** tag it (F1), then either validate it or remove it from the decision
  path until it earns a slot.

#### F9. Regime label has no hysteresis or transition handling
- **Evidence:** `regime.py:350-362` maps the composite score to a label by fixed
  thresholds (50/65); no previous-state smoothing in the module.
- **Impact:** a score oscillating around 65 flips the menu day to day; the book can
  accumulate a mix of regime playbooks with no coherent thesis.
- **Class:** design (permission).
- **Fix sketch:** require 2–3 consecutive days (or a buffer band) before changing
  state; treat transitions as “reduce/stand aside”, not “switch menu”.

#### F10. Portfolio risk is only a count and a (dead) sector cap
- **Evidence:** `gate.py:45-47`, `sizing.py:29-32`. No portfolio heat (sum of open
  risk), no daily/weekly loss limit, no correlation beyond the sector string, no
  regime-based size multiplier.
- **Impact:** 8 positions × 1% = up to 8% account risk if stops are hit together;
  correlated positions can stack (F2).
- **Class:** design (size).
- **Fix sketch:** heat cap (e.g. 3–4% open risk), daily loss limit, sector/correlation
  cap that actually works, regime size multiplier (1.0 / 0.5 / 0).

---

## 3. What this means for the forward test

1. **Do not change the strategy before the trigger** — the guardrail in
   `FORWARD_TEST_REVIEW.md` still holds.
2. **Measurement plumbing is now fixed** (F1–F3, execution v0.1): screen, confluence,
   sector, regime and `max_hold_days` are recorded on entries (and screen/regime on
   rejections). The sector cap is real. These record decisions the system already makes;
   they do not change which trades are taken. Review items A (MFE) and C (per-screen)
   are now answerable.
3. **The 3 legacy rows are explicitly out-of-sample** (F4): flagged
   `exclude_from_stats=1`; they stay open and visible but never enter expectancy,
   rolling metrics or the 30-trade scorecard.
4. **The approved exit change is the time stop only** (F3): it now executes the plan's
   calendar-day limit. The target hierarchy and R/R metric (F5) were deliberately left
   untouched — they are the first review decision, not a pre-sample change.
5. **Then run the one-click after-close daily** and verify a `workflow_runs` row each
   day. The first run is the sample start. If a run is missed, leave the gap (no
   backfill).

Until (2)–(4) are decided, the forward journal can still accumulate — but label it
“pre-instrumentation” and do not use it for the kill rule.

---

## 4. Prioritized fix list, mapped to the four dials

| Priority | Fix | Dial | Behavior change? | Status (2026-10-19) |
|---|---|---|---|---|
| P0 | Store screen/template, confluence, regime on every row + rejection (F1) | measurement | no | **Applied** |
| P0 | Persist sector; make the 30% sector cap real; add test (F2) | size | only if cap binds | **Applied** |
| P0 | Persist `max_hold_days`; wire it into exit sync + CLI (F3) | exit | **yes** | **Applied** (calendar-day) |
| P0 | Decide legacy 3 rows; start logging runs (F4) | ops | no | **Applied** (legacy flagged; first run pending) |
| P1 | Coherent target hierarchy: T1 = nearest meaningful level; gate R/R on the exit level; scale-out/trail as one design (F5) | exit | **yes** | **Open — review A** |
| P1 | Rebuild choppy menu; make `ranging` reachable or delete; re-weight to corrected validation (F6) | playbook | **yes** | Open — review B |
| P1 | Permission state + cross-screen ranking + daily entry cap (F7) | permission | **yes** | Open — review B |
| P1 | Tag/validate/remove the sector-rotation 4th screen (F8) | selection | **yes** | Open — review C/D |
| P2 | Regime hysteresis / transition state (F9) | permission | **yes** | Open |
| P2 | Portfolio heat + daily loss limit + real correlation cap (F10) | size | **yes** | Open |

The original P0 items (F1–F4) are done. A second P0 pass (F11–F13, §8) found and fixed
three measurement defects; P0 is now defined by `scripts/verify_journal.py` printing
`PASS`. P1/P2 are review decisions; doing them mid-sample restarts the sample.

---

## 5. Not verified / open questions

- Whether the **frontend** “Run After-Close” button times out on a full brief (~30
  candidates × up to 45 s each). The candidate count is unbounded by design; if the UI
  request times out, runs may be missed. The first run (2026-10-19, run id 1)
  completed via the same endpoint without a timeout.
- Whether `max_hold_days` was ever intended to be stored — **resolved 2026-10-19**:
  yes, it is stored and executed as calendar days (execution v0.1). The target
  hierarchy/R:R metric remains the open decision (F5).
- Whether the 3 legacy rows came from an older builder; their planned R/R values are
  not reproducible from their stored targets. Treat them as legacy.
- The sector-rotation scorer’s actual edge is unknown (never backtested or forward-tagged).

---

## Appendix — journal evidence (read-only)

```
Audit-time snapshot (2026-10-19, before execution v0.1):
paper_trades: 3 open, 0 closed  (all 3 now exclude_from_stats=1)
  NTNX  2026-10-05  entry 67.74  stop 65.92  T1 82.89  T2 83.36  RR 55.22  CONDITIONAL  sector NULL  template NULL
  WBD   2026-10-05  entry 29.87  stop 27.60  T1 54.62  T2 —      RR 134.50 CONDITIONAL  sector NULL  template NULL
  NVDA  2026-10-06  entry 220.45 stop 207.89 T1 390.24 T2 —      RR 8.06   CONDITIONAL  sector NULL  template NULL
rejections: 0
workflow_runs: 0

Post-run state (2026-10-19, run id 1):
paper_trades: 4 open, 0 closed  (3 legacy excluded + PM)
  PM    2026-10-19  entry 185.97 stop 183.19 T1 205.99 T2 297.73 CONDITIONAL 12.5%
         sector Consumer Defensive  template Sector Rotation Holdings  regime Neutral
         confluence 4  max_hold_days 30  T1 ≈7.2R
rejections: 4  (PG/WMT conviction; SG/XERS no entry geometry)
workflow_runs: 1

Schema after execution v0.1:
  paper_trades: + max_hold_days INTEGER, + exclude_from_stats INTEGER DEFAULT 0
  rejections:   + template TEXT, + regime TEXT
```

Code references are line numbers at HEAD `8001ea5` (before the v0.1 changes). No files
were modified by this audit except this report and the two doc links noted in the commit.

---

## 6. Execution v0.1 — applied changes (2026-10-19)

User decision: **measurement + time stop**, then start the forward sample. Targets and
the R/R gate untouched.

| Area | Change | Files |
|---|---|---|
| Attribution | Router + CLI take `screen_name`/`confluence_score` from the brief ticker; store market `regime`; rejections store `template`/`regime` | `api/routers/workflow.py`, `scripts/paper_trade_from_brief.py`, `journal_store.py` |
| Sector | Read from the analysis **response**; persist on entries; sector check uses the unhalved risk-based size | same |
| Time stop | Persist `max_hold_days`; `exits.hold_limit_bars` converts calendar days to the first session on/after the cutoff; both exit paths execute it | `journal_store.py`, `exits.py`, router/CLI |
| Legacy rows | `exclude_from_stats=1` for NTNX/WBD/NVDA; expectancy + rolling metrics filter them | `journal_store.py`, `verification.py` |
| Migration | Idempotent `ALTER TABLE` for existing DBs (trades + rejections) | `journal_store.py` |
| Tests | Attribution (router + CLI), sector cap (router + CLI), time-stop conversion, exclusion filter, schema round-trip | `backend/tests/` (51 focused tests pass; frontend typecheck + touched UI tests pass) |

Not changed: target selection, R:R gate semantics, screen menus, regime permission,
sizing, entry ranking. Those are review items A–D.

**Sample clock:** started on the first `run_close` (2026-10-19, run id 1: 1 accepted,
4 rejected, 0 exits). Do not backfill
missed days. The 3 legacy rows do not count toward the 30 closed trades. The first live
entry (PM) has T1 ≈7.2R and T2 ≈40R — the target-geometry gap (F5) is present in the
sample by design and is review item A.

**Superseded by D-73 (2026-10-21):** the sample clock above is void. The first four
entries were after-close phantom fills and the clock restarts at the first actual T+1
fill.

---

## 7. Execution correction — pending orders / T+1 fills (2026-10-21, D-73)

The first check of the live journal against actual session OHLC found four impossible
fills. The signal is produced **after** the close; `_build_row` stored `entry_zone_low`
as `entry_price` and `upsert_entry` wrote it immediately, so there was no fill event and
no timing check.

| Row | Signal | Booked | Session low | Session close | What was wrong |
|---|---|---|---|---|---|
| PM | 2026-10-19 | 185.97 | 199.35 | — | price never traded near the entry |
| AMGN | 2026-10-20 | 406.02 | 425.11 | — | price never traded near the entry |
| CCK | 2026-10-20 | 112.46 | 106.09 | 114.17 | same-day fill after the signal (look-ahead) |
| MMM | 2026-10-20 | 168.80 | 162.13 | 171.37 | same-day fill after the signal (look-ahead) |

CCK/MMM closed inside their zones, but the system could not have bought them: the signal
did not exist until after the session. Every same-day fill is look-ahead by construction.

### What changed

| Area | Change | Files |
|---|---|---|
| Order state | `pending_orders` table (one active order per symbol); accepted after-close signals are queued, not booked | `journal_store.py` |
| Fill timing | only bars strictly after `signal_date` and up to the run date; limit at open/limit, MOO inside `entry_high`, cancel through stop / above cap, 3-session expiry | `pending.py`, `pending_service.py` |
| Same-session exits | fill bar low ≤ stop → close at stop (−1R); targets on the fill bar ignored (conservative intrabar order) | `pending.py` |
| Book impact | pending orders reserve capital, a slot, sector exposure and the symbol; fills re-size shares capped by planned notional **and** planned dollar risk | `journal.py`, `pending.py`, router/CLI |
| Invalid rows | PM/AMGN/CCK/MMM `voided=1`, `exclude_from_stats=1`, evidence in `void_reason`; visible, not positions, not scored | `scripts/void_invalid_forward_entries.py` |
| Visibility | `/pending-orders`, pending panel + `void` badge in the Journal tab; CSV export/import preserves the void flag | router, `JournalTab.tsx`, `journal_store.py` |
| CLI parity | fill → pending enforce → exits; `--fill-pending`, `--order-type`, `--expiry-sessions` | `paper_trade_from_brief.py` |

**Not changed:** targets, R:R gate, screens, regime permission, sizing formula. Pending
orders are a measurement correction, not a strategy change.

**Verification:** pure fill-rule tests (same-day bar ignored, limit/MOO, gap-through-stop,
expiry, share cap, same-session stop); store tests (active-order uniqueness, void
visibility/exclusion, capital reservation, export round-trip); endpoint tests (T+1 fill,
signal-day ignored, expiry, same-session stop, `/journal/open`); frontend typecheck +
JournalTab tests.

**Live state after the correction (2026-10-21):** 4 voided rows retained; 3 legacy rows still
open/excluded; 0 pending; 0 valid forward fills. The next after-close run creates pending
orders; the first possible fill is the next session. The forward clock starts there.

---

## 8. D-74 measurement addendum (2026-10-28) — three more P0 defects

The audit above classified F1–F4 as the P0 measurement set and they were applied. A
second pass through the live journal after the first valid fills found three additional
P0 defects that the original audit did not cover. They are **measurement only**; none of
them changes a trading decision.

### F11. Dollar P&L was R × notional, not R × risk

- **Evidence:** the exit sync computed `pnl_usd = realized_r × account_value ×
  position_size_pct/100`. `position_size_pct` is a notional allocation (capped at 25%,
  halved for CONDITIONAL), not the dollar risk. CRS stored **−$1,624.99**; the actual
  trade was 5.84 shares × $4.31 stop distance = **−$25.17 gross**, **−$30.01 net**.
- **Impact:** every dollar P&L in the journal was overstated by the position-size
  factor (54× on CRS). R was unaffected.
- **Class:** measurement bug.
- **Status (2026-10-28): FIXED (D-74).** Canonical `pnl.py` computes gross from shares,
  costs from 15 bps per side, net = gross − costs. `pnl_gross_usd` and `costs_usd` are
  stored separately.

### F12. The gate's R:R and the journal's stored plan did not reconcile

- **Evidence:** the gate checks `v["risk_reward"]`; the journal stored
  `risk_reward_planned` from that value and executed `target_1` / `target_2`. The third
  target was never persisted. Verifier output after the first fills: CRS gate 4.32 vs
  stored plan 11.89; IOSP 6.15 vs 3.99; SF 6.47 vs 4.36.
- **Impact:** the number the gate accepted and the number the exit walker could pay were
  not the same geometry. IOSP/SF are consistent with a missing `target_3`; CRS is not
  (the gate's value is *lower*), so the gate's field itself can be stale.
- **Class:** measurement/provenance + a known design gap (F5, review A).
- **Status (2026-10-28): PARTIALLY FIXED (D-74).** `target_3`, `plan_rr` and
  `target_1_r` are now stored going forward; `risk_reward_planned` remains the gate's
  reported number. The verifier **warns** on every gap. The gate semantics themselves
  are unchanged — reconciling them would change decisions and is review A.

### F13. Live dollars were gross while backtests were net

- **Evidence:** the replay/validation convention is 10 bps fee + 5 bps slippage per
  side (D-71); the live path had no cost deduction.
- **Impact:** live and simulated dollar P&L were not comparable.
- **Class:** measurement bug.
- **Status (2026-10-28): FIXED (D-74).** `pnl_usd` is net; `pnl_gross_usd` and
  `costs_usd` are explicit. `realized_r` stays gross, matching the backtest convention.

### Verification and artifacts

- `python scripts/verify_journal.py` → **PASS**: 0 phantom fills, 0 dollar-P&L
  mismatches, 3 plan-R:R warnings.
- `python scripts/scorecard.py` → 1 closed, expectancy −1.00R, net −$30.01, MFE gap
  +4.72R.
- Pre-backfill backup: `data/backups/paper_trades_20261028T230900Z.db`.
- Decision record: `docs/DECISIONS/D-74-p0-measurement-integrity.md`.
- Scorecard: `docs/PAPER_TRADING/SCORECARD.md`; pre-registration:
  `docs/PAPER_TRADING/PRE_REGISTRATION.md`.

**Not changed:** targets, R:R gate, screens, sizing, regime permission, exit rules or
the sample clock. F11–F13 are arithmetic and provenance, not strategy.

### Live state at the addendum (2026-10-28)

3 valid fills (SF 2026-10-22, IOSP 2026-10-23, CRS 2026-10-26); 1 closed (CRS −1.00R,
MFE +3.72R); 2 open; 1 pending (DUK, signal 2026-10-26, 3rd eligible session
2026-10-29); 7 runs; 40 rejections. The four phantom rows and three legacy rows remain
excluded.
