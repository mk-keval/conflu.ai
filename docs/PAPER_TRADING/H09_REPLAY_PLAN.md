# H-09 — Exploratory Replay Plan (v0.1 vs v0.2 Geometry)

**Status:** **FROZEN** — signed off as D-78 on 2026-10-30. Implemented and
tested; the first full ledger write is gated to **2026-11-24** (36-day data
horizon). Any later change is a new exploratory design, not an amendment.
**Date:** 2026-10-29
**Scope:** Bundle A §7 (H-09): does the v0.2 geometry improve the same signal
stream, or does it just reject more trades?
**Related:** [D-71](../DECISIONS/D-71-two-month-paper-replay.md),
[D-73](../DECISIONS/D-73-pending-orders-t1-fills.md),
[D-74](../DECISIONS/D-74-p0-measurement-integrity.md),
[D-75](../DECISIONS/D-75-pass-bar-expectancy-profit-factor.md),
[D-76](../DECISIONS/D-76-forward-sample-versioning.md),
[D-77](../DECISIONS/D-77-bundle-a-exit-geometry.md),
[BUNDLE_A_EXIT_GEOMETRY.md](BUNDLE_A_EXIT_GEOMETRY.md) §7,
[PRE_REGISTRATION-v0.2.md](PRE_REGISTRATION-v0.2.md).

> **Non-evidence label.** H-09 is exploratory. It never enters the forward
> scorecard, the D-75 pass bar, the kill rule, `/expectancy`, or any v0.2
> verdict. A positive result may inform a future sample version; it cannot
> validate FWD-v0.2. The ledger it writes is marked
> `rules_version='v0.2'` **and** `evidence_label='exploratory_h09_not_evidence'`.

---

## 1. Question

**Primary:** on the same signal stream, does the v0.2 geometry — nearest
structural T1 inside the family band, family Plan-R floor, family multi-leg
exit — produce a better trade population than the v0.1 geometry, or does it
mostly reject trades?

**Sub-questions the run must answer:**

1. **Exit-only delta:** holding the fill set fixed, does the v0.2 exit beat the
   v0.1 exit?
2. **Policy delta:** does the v0.2 gate produce a better book than the v0.1
   gate?
3. **Rejection quality:** what would the signals v0.2 rejects have done under
   v0.1 rules? Are the rejects the bad trades, or is v0.2 discarding good ones?
4. **Cost of the change:** how many trades are lost to target rejection,
   limit expiry and gap-through-stop cancellation, and what is the fill rate?

**What it cannot answer:** exact live-brief performance. The screen replay
cannot reconstruct TradingView ranking, confluence counts, catalysts, earnings
checks, liquidity filters, portfolio caps, or the live `entry_low` branch
selection. Those gaps are listed in §12 and are not hidden.

---

## 2. Frozen inputs (same as D-71)

| Input | Frozen value | Source |
|---|---|---|
| Signal window | **2026-08-20 → 2026-10-19** (D-71's 42 sessions) — see §11/G10 for the data-horizon gate | D-71 §Evidence |
| Universe | `config/replay_universe_sp500.txt` **exactly as at the D-71 run**; no `--refresh-universe` | D-71 §3 |
| Usable names | `filter_usable` (daily ≥200 bars, hourly ≥100 bars) | `replay_data.py` |
| Screens | `load_screen_mix()` from `config/regime_screens.yaml` at the run commit; no weight/menu changes | `replay.py:load_screen_mix` |
| Regime | `historical_regime_map` as-of each signal close | `replay.py` |
| Signal generation | the D-71 engine's entry stream: `ExternalBacktestEngine.run_backtest` with **signal-engine** params `stop_atr_mult=2.0`, `target_atr_mult=3.0`, `max_hold_bars=15` (its prices/exits are discarded) | `external_backtest.py:_run_simulation` |
| Regime gate + dedupe | unchanged: one entry per `(signal_date, symbol)`, highest-priority screen wins, others in `also_signaled_by` | `replay.py` |
| Day cap | `max_per_day = 0` (keep every deduped signal) | D-71 |
| Costs | canonical `pnl.dollar_pnl`: 10 bps fee + 5 bps slippage per side on entry+exit notional | `pnl.py`; D-74/D-77 |
| Sizing | 1% risk on a $100,000 account; CONDITIONAL × 0.5; no portfolio caps | D-71 §5 + D-77 §4 |
| Data | daily ~760d, hourly ~200d, cache `.cache/replay/`; `--refresh-data` only if the cache does not cover the window | `replay_data.py` |

Run metadata records the SHA-256 of the universe file and
`config/regime_screens.yaml`, the cache `meta.json`, the actual data range per
side, and the requested vs effective window. A run that cannot produce those
hashes is not accepted.

**Why the signal engine params are frozen separately:** they define the signal
*stream*. The H-09 plan/exit params (below) must not change how many signals
exist, or the two arms would no longer be compared on the same signals.

---

## 3. The two arms

Both arms see the **identical** signal list, the **identical** shared geometry
(entry zone, stop, ATR), the **identical** fill decisions, the **identical**
costs and sizing. They differ only in target selection, gate floor, and exit
policy — the Bundle A change.

### 3.1 Shared geometry (both arms)

Computed from the **signal bar** (the close that triggered the screen), with no
future data:

```
C = signal-bar close
A = ATR14 at the signal bar

width_pct   = max(0.5 × A / C, 0.015)          # live default zone width, 1.5% floor
entry_low   = round(C × (1 − width_pct), 2)    # planned fill (D-73 limit)
entry_high  = round(C × (1 + 0.5 × width_pct), 2)
stop        = round(C − 2.0 × A, 2)            # live 2×ATR fallback, signal-close basis
```

Require `entry_low > stop > 0`; otherwise the signal is `invalid geometry`
(no order). A missing/non-finite ATR is also `invalid geometry`.

**Why the close basis for the stop:** the live plan's stop is
`close × (1 − max(suggested_stop_pct, 2%))`, with `2×ATR/close` as the
fallback (`synthesis.py:1496-1504`), i.e. it is signal-close based, not
fill-based. D-71's engine used fill-based ATR stops; H-09 freezes the
close-based version for both arms and discloses the difference. The planned
risk is therefore `entry_low − stop ≈ (2.0 − width/ATR) × A`, not exactly
2×A; the row records the actual risk.

### 3.2 Arm V01 — the rebuilt v0.1 rules

| Piece | Rule | Code |
|---|---|---|
| Targets | highest 3 structural levels in `(close, 1.5×close]`; measured-move projection; ATR fallback `close+2/3/4×ATR`; fixed fallback 8/15/25% | mirror of `synthesis._get_structural_targets_long` (`synthesis.py:83-155`) in the replay rules module |
| Gate | production step 5 with `setup_family=None` and `risk_reward = (last_target − midpoint)/(midpoint − stop)`; PASS ≥2.5, CONDITIONAL 2.0–2.5 with first target ≥1R, FAIL below. `_rr_consistency` still compares that midpoint RR to the **entry-low** geometry, exactly as live; some v0.1 plans will be CONDITIONAL on 5c. Reproduce it; do not "fix" it. | `gate.evaluate_risk_reward` (`gate.py:341-389`) |
| Exit | `exits.infer_exit` on the stored 3 targets; stop first; T2 before T1 within a bar (the v0.1 walker's order); time stop at the close (30 calendar days converted to a bar count with `hold_limit_bars`, as the live sync does); **no** breakeven or trail | `exits.infer_exit` (`exits.py:110-186`); `workflow.py:1197` |
| Time stop | `v01_max_hold_days = 30` (live swing default, `synthesis.py:1960-1962`) | frozen param |
| Target rejection | none (the ATR/percentage fallback always supplies a target) | — |

This is a reconstruction of the **v0.1 rules on replay geometry**, not a replay
of the live v0.1 journal. It is the honest apples-to-apples comparator.

### 3.3 Arm V02 — the frozen Bundle A rules

| Piece | Rule | Code |
|---|---|---|
| Family | `family_for_screen(brief.screen_name)` — the **display name**, exactly as the live brief passes it (`morning_brief.py:200,312`) | `exit_policy.family_for_screen` |
| Candidates | `collect_candidates(price=close, key_resistance, swing_highs, swing_lows)` — levels above close, ≤1.5×close; measured move when above all structure | `exit_policy.collect_candidates` |
| Targets | `select_targets(entry_low, stop, family, candidates)`; nearest level inside `[half_size_floor, max_t1_r]`; T2/T3 = next levels; no level in band → reject `target too close` / `target too far` / `no structural objective` | `exit_policy.select_targets` |
| Plan R | `(T1 − entry_low)/(entry_low − stop)`; `stretch_rr` = T3 R | `selection.t1_r` / `stretch_r` |
| Gate | production step 5 with `setup_family=family`, `risk_reward=plan_rr`; PASS = family full floor, CONDITIONAL = half-size tier, FAIL below; 5a stop-distance and 5c consistency included | `gate.evaluate_risk_reward` |
| Exit | same-session stop first; then `simulate_exit` with the family policy: trend 1/3 T1 + 1/3 T2 + 1/3 trailed, breakout 1/2 T1 + 1/2 trailed, MR/rotation/unknown 100% at T1; BE at +1R close; 2.0×/2.5×ATR trail; calendar time stop | `exit_policy.simulate_exit` |
| Target rejection | yes, before the order; no fill counterfactual in the primary book | — |

**Family-map reality check.** Live passes the display name. Running the
deployed menu through `family_for_screen(config.name)` today yields:

| Screen (stem) | Display name | Family |
|---|---|---|
| `52week-breakout` | 52-Week Breakout | breakout |
| `bull-flag-continuation` | Bull Flag Continuation | breakout |
| `volatility-expansion` | Volatility Expansion | breakout |
| `institutional-swing-quality` | Institutional Swing Quality | trend |
| `volume-trend-accumulation` | Institutional Accumulation | trend |
| `trend-follower-v2` | trend-follower-v2 | trend |
| `trend-pullback-v2` | trend-pullback-v2 | trend |
| `mean-reversion` | Mean Reversion | mean_reversion |
| `statistical-mean-reversion` | Statistical Mean Reversion | mean_reversion |
| `institutional-trend-follower-mtf` | Institutional Trend Follower (Multi-Timeframe) | **unknown** |
| `low-vol-setup` | Low-Vol Setup Simple | **unknown** |
| `distribution` | Distribution | **unknown** |

The MTF and Simple `unknown` results are **live behavior**, not replay
bugs: the code's family sets contain `institutional trend follower mtf` and
`low vol setup`, which the display names do not normalize to. `Distribution`
is expected to be unmapped (no family in the v0.2 table). H-09 must mirror
live, not fix it. The run reports the family mix and repeats the key aggregates
with a **stem-based sensitivity map** (secondary, clearly labelled "if the
display-name gap were closed"). Any actual map fix is a post-H-09 decision for
a new sample version, never a mid-sample edit.

### 3.4 Fill model (D-73, shared)

- `pending.evaluate_order` on bars **strictly after** `signal_date`,
  `expires_after_sessions = 3`.
- `limit = entry_low`; fill at `min(open, limit)`; cancel if the bar opens at or
  below the stop; **no same-day fill**.
- Same-session stop: if the fill bar's low ≤ stop, close at the stop that day,
  one full leg, `−1R` before costs; same-session targets are ignored
  (`pending.same_bar_stop` / `pending.stop_exit`).
- The fill decision is shared, so both arms have the **same fills**. Rejected
  plans are still fill-simulated **as a counterfactual only** (§7), never in the
  primary book.

---

## 4. Signal → plan pipeline

1. **Signal stream.** For each deployed template and symbol, run the D-71
   engine exactly as today. Keep only `(signal_date, symbol, template,
   regime, rank, weight, rvol)`. Discard the engine's entry/exit prices.
   The engine's one-open-trade-at-a-time rule is therefore part of the frozen
   signal definition.
2. **Regime gate.** Keep signals whose template is selected in the regime of
   their `signal_date` (unchanged).
3. **Dedupe.** One entry per `(signal_date, symbol)`, highest screen rank wins;
   record the others.
4. **Geometry.** Load the daily frame truncated at `signal_date`; compute
   `C`, `A`, `entry_low`, `entry_high`, `stop` (§3.1). Missing ATR or
   `entry_low ≤ stop` → `invalid geometry`.
5. **Structural levels.** On the same truncated frame:
   `technical._detect_swings(frame, lookback=5)` and
   `technical._find_key_levels(swings, frame, atr_pct, close)`; flatten
   `swing_highs`/`swing_lows` to floats. No TradingView resistance is
   available; the candidate pool is OHLCV-only.
6. **Fill.** `pending.evaluate_order` on the post-signal bars (§3.4).
7. **Arm V01 plan.** Targets, gate, exit (§3.2).
8. **Arm V02 plan.** Family, targets, gate, exit (§3.3).
9. **Accounting.** Both arms, same formulas (§5).

The signal close `C` is the close of the signal bar, not the next open. The
regime is computed through that close, matching the live pre-market brief that
acts on the next session.

---

## 5. Accounting (one definition each)

| Term | Definition | Code |
|---|---|---|
| Entry | actual fill price (`min(open, limit)` or gap fill) | `pending.evaluate_order` |
| Risk (1R) | `entry_price − stop_loss` per share, using the **actual fill** | `exit_policy` / `infer_exit` |
| Realized R | `(vwap_exit − entry_price)/(entry_price − stop_loss)`; multi-leg R is the share-weighted leg average | `ExitSimulation.as_exit_columns`, legs |
| Exit price | share-weighted VWAP of the legs | `simulate_exit` |
| P&L | `pnl.dollar_pnl(entry_price, exit_price, shares)` — gross, costs, net | `pnl.py` |
| Costs | 10 bps fee + 5 bps slippage per side, on entry+exit notional | `dollar_pnl` |
| MFE / MAE | full-hold excursion in R, entry bar excluded | `simulate_exit` / `infer_exit` |
| MFE capture | `realized_r / mfe_r`, `None` when `mfe_r ≤ 0` | computed |
| Plan adherence | 1.0 all planned legs fired, 0.5 trail/time stop on the remainder, 0.0 stop | `exit_policy._plan_adherence` |
| `entry_low` / `entry_high` | the planned zone; `entry_price` is the fill, never the zone low | row fields |

`risk_pct` is 1.0 for PASS and 0.5 for CONDITIONAL; `shares = (risk_pct/100 ×
100_000)/(fill − stop)`. R is size-independent, so the primary expectancy is
unaffected by the CONDITIONAL halving; dollar P&L is not.

D-71's replay rebuilt P&L by slipping the entry and exit prices and then
charging fees. The canonical `dollar_pnl` charges the combined 15 bps on both
prices instead. Same cost model, slightly different arithmetic; H-09 uses the
canonical formula for both arms so the delta is clean. The published D-71
numbers are therefore a **reference line**, not a row-for-row comparator.

**Open trades at the data edge:** if a trade has not exited by the last
available bar, close it at that bar's close (`eod`), as D-71 did. Report the
`eod` count separately and include it in the primary aggregate only when the
data horizon covers the family's maximum time stop (§11/G10). A run that cannot
cover the horizon writes its ledger only with `--allow-censored`, and the
summary labels it `censored`.

---

## 6. Funnel and reports

### 6.1 Funnel (every signal counted exactly once)

```
signals_raw                  engine entry stream (all templates/symbols)
  → regime_gated             template selected in that day's regime
  → deduped                  one per (signal_date, symbol)
  → geometry_valid           ATR present, entry_low > stop
  → orders                   geometry_valid (both arms place the same order)
      → filled               D-73 limit fill
      → cancelled_gap        opened at/below the stop before a fill
      → expired              no fill in 3 sessions
```

`orders`/`filled` are computed for every geometry-valid signal so the
exit-only and rejection analyses have the same fills. The **primary policy
book** only counts plans the arm's gate accepts; a rejected plan's fill is a
counterfactual, never a traded row.

For each arm:

```
filled
  → v0.1: gated_out (step-5 FAIL) | accepted (PASS/CONDITIONAL)
  → v0.2: rejected (target too close / too far / no objective / invalid)
          | gated_out (step-5 FAIL) | accepted (PASS/CONDITIONAL)
accepted → closed | eod
```

A reconciliation check asserts the counts add up; any signal that falls through
is a hard failure, not a rounding note.

### 6.2 Delta tables

1. **Exit-only (paired fills):** signals where both arms produced a plan and a
   fill. v0.1 exit vs v0.2 exit, same entry, same stop, same costs.
   Report `n_paired`, expectancy R, PF R, avg win/loss R, MFE capture, exit mix.
2. **Policy book:** each arm's accepted trades (PASS + CONDITIONAL; FAIL out).
   Report the same metrics plus net $ and total costs.
3. **Rejection quality:** on the set v0.2 rejects, the v0.1 arm's counterfactual
   expectancy; on the set v0.2 accepts but v0.1 rejects, the v0.2 expectancy.
   This is the direct answer to "does it just reject more trades?"
4. **Sensitivity:** primary display-name family map vs stem-based map (§3.3).
   Secondary, not the primary conclusion.
5. **Descriptive cuts:** per family, per template, per regime, exit-reason mix,
   fill/cancel/expiry/same-session-stop rates, average hold, MFE gap.

Every table carries `n`; below 30 closed trades a cell is labelled
"descriptive only". No pass/fail verdict is attached to any H-09 number.

### 6.3 Artifact

`docs/backtests/h09_replay_<timestamp>.json` with:

```json
{
  "meta": {"rules_version": "v0.2", "evidence_label": "exploratory_h09_not_evidence",
           "window_requested": {...}, "window_effective": {...},
           "universe_sha256": "...", "screens_sha256": "...", "cache_meta": {...}},
  "funnel": {...},
  "arms": {"v01": {...run summary...}, "v02": {...run summary...}},
  "delta": {"exit_only": {...}, "policy": {...}, "rejection_quality": {...}},
  "rows": {"v02": [...], "v01_counterfactual": [...]}
}
```

The artifact is the full audit trail; the DB ledger stores the v0.2 rows only.

---

## 7. Storage changes (additive)

### `replay_runs`

Add `rules_version TEXT` and keep the rest. `metadata_json` gains:

- `evidence_label = "exploratory_h09_not_evidence"`
- `window_requested`, `window_effective`, `data_horizon`
- `universe_sha256`, `screens_sha256`, `cache_meta`
- `signal_engine = {stop_atr: 2.0, target_atr: 3.0, max_hold_bars: 15}`
- `funnel` and `delta` summaries
- `family_map` (display name → family) and `unknown_screens`
- `caveats` (updated §12 text)

### `replay_trades`

Additive columns for the v0.2 ledger:

| Column | Purpose |
|---|---|
| `rules_version TEXT` | `'v0.2'` |
| `setup_family TEXT` | trend / breakout / mean_reversion / rotation / unknown |
| `entry_low REAL`, `entry_high REAL` | planned zone; `entry_price` remains the actual fill |
| `target_2 REAL`, `target_3 REAL` | stored T2/T3 (T1 is `target_1`) |
| `plan_rr REAL`, `target_1_r REAL`, `stretch_rr REAL` | Plan R provenance |
| `atr_at_entry REAL` | trail distance / audit |
| `gate_verdict TEXT`, `gate_note TEXT` | PASS / CONDITIONAL / FAIL and the step-5 note |
| `mfe_r REAL`, `mae_r REAL`, `plan_adherence REAL` | trade quality |
| `exit_legs TEXT` | JSON legs `{date, price, shares, size_pct, reason, r}` |

Migration: additive `ALTER TABLE ... ADD COLUMN` with the same
`duplicate column name` tolerance as `journal_store._migrate` (API server + CLI
can race). Existing D-71 replay rows keep NULLs and are never rewritten. The
store is single-file (`data/paper_trades.db`), separate from `paper_trades`
(D-68).

`replace_run` keeps its "a replay replaces the previous replay" semantics:
H-09 replaces the D-71 ledger. The D-71 JSON artifact
(`docs/backtests/replay_20261019_202541.json`) remains the published record.
`latest_run()` exposes `rules_version`; the API passes it through. No frontend
change is required — the Journal replay table ignores unknown fields.

**Non-evidence guard:** no code path writes replay rows into `paper_trades`,
`/expectancy`, the scorecard or the verifier. The label is carried in the run
metadata and every row's `notes` starts with
`SIMULATED REPLAY (H-09, not forward evidence)`.

---

## 8. Code map

| File | Change |
|---|---|
| `backend/app/infrastructure/backtest/replay_rules.py` **(new)** | Pure helpers: `PlanGeometry`, `build_geometry`, `structural_levels` (swing/key-level as-of), `v01_targets` (mirror), `v01_gate`, `v02_plan`, `apply_fill`, `simulate_v01_exit`, `simulate_v02_exit`, `accounting`, funnel dataclasses |
| `backend/app/infrastructure/backtest/replay.py` | `ReplayParams` gains `rules_version`, `window_start`, `window_end`, `entry_zone_atr_mult`, `min_zone_pct`, `fill_expiry_sessions`, `v01_max_hold_days`; the existing `stop_atr_mult` becomes the **plan** stop (default 2.0) and the signal engine gets frozen `signal_stop_atr_mult=2.0`, `signal_target_atr_mult=3.0`, `signal_max_hold_bars=15`; explicit window; per-candidate arm evaluation; v0.2 rows; summary/funnel/delta |
| `backend/app/domain/workflow/replay_store.py` | `rules_version` + the `replay_trades` columns, tolerant migration, `latest_run` field |
| `run_paper_replay.py` | `--rules-version`, `--window-start`, `--window-end`, `--entry-zone-atr`, `--min-zone-pct`, `--expiry-sessions`, `--allow-censored`; artifact with both arms; v0.2 ledger |
| `backend/scripts/verify_replay.py` **(new)** | Ledger integrity: leg/VWAP/R/P&L, plan-R provenance, family, rules_version, funnel reconciliation, no forward-table rows |
| `backend/tests/test_replay_rules.py` **(new)** | Pure geometry/targets/gate/exit tests + parity tests against `synthesis._get_structural_targets_long`, `gate.evaluate_risk_reward`, `exits.infer_exit` |
| `backend/tests/test_replay.py` | Existing D-71 tests pinned to `rules_version='v0.1'`; new v0.2 path tests |
| `backend/tests/test_replay_h09.py` **(new)** | End-to-end synthetic run: same signals across arms, funnel reconciliation, delta keys, store round-trip |
| `docs/DECISIONS/D-78-h09-replay-freeze.md` **(new, after sign-off)** | Records the frozen replay rules and the non-evidence label |
| `docs/PAPER_TRADING/README.md`, `docs/DECISIONS/index.md` | Index links |
| `docs/SESSIONS/2026-10-29_h09-replay.md` | Run record after the actual run |

**No live-code behavior change.** `exit_policy`, `gate`, `synthesis`,
`pending`, `pnl` and the journal are imported, not edited. The only shared-code
touch is a test-only parity guard against their private helpers; if a future
edit changes them, the parity test fails loudly.

---

## 9. Tests

**Unit (pure)**

- `build_geometry`: ATR branch, 1.5% floor branch, rounding, `entry_low > stop`,
  missing/invalid ATR, zero/negative prices.
- Structural levels: as-of truncation (no future bars), swing lookback, key
  level clustering, measured move, 1.5× cap.
- `v01_targets`: highest-3 truncation, dedupe, ATR fallback, fixed-% fallback,
  parity with `synthesis._get_structural_targets_long` on the same inputs.
- `v01_gate`: PASS/CONDITIONAL/FAIL branches and 5a/5c behavior; parity with
  `gate.evaluate_risk_reward` where the inputs overlap.
- `v02_plan`: nearest-in-band, half-floor boundary, max-cap rejection, no-level
  rejection, T2/T3 gaps, family map for all deployed display names.
- Fill: limit at open, limit touch, gap-through-stop cancel, expiry, no
  same-day fill, same-session stop.
- Exit: T1-only, T1+T2, trend runner trail, breakout T1+trail, MR full exit,
  BE activation next bar, gap through stop/trail, same-bar stop-vs-target
  ambiguity (stop wins), time stop, missing-ATR fallback, entry-bar exclusion.
- Accounting: weighted exit, weighted R, `dollar_pnl` equals the leg sum, costs
  per leg, MFE capture `None` when MFE ≤ 0.

**Integration**

- Synthetic two-symbol run: identical signal list across arms; v0.2 row fields
  (`family`, `entry_low`, `plan_rr`, `gate_verdict`, `exit_legs`); rejection
  recorded; funnel adds up; delta keys present.
- Store: migrate an old `replay_trades` table, insert/read v0.2 rows, idempotent
  re-run, `rules_version` round-trip, old rows untouched.
- Determinism: two injected-data runs with the same params produce identical
  rows and summaries (timestamps excluded).
- Non-evidence: the replay store writes nothing to `paper_trades`; the scorecard
  and verifier see zero added rows.

**Regression**

- The 8 existing D-71 replay tests pass with `rules_version='v0.1'`.
- Full backend suite: expect only the known pre-existing, date-sensitive
  failures (`test_insider_cluster.py` — 1–4 depending on the calendar,
  `test_earnings_filter_missing_file_safe_default`), reproduced at `HEAD`.
- `ruff` clean on touched files; frontend unaffected (no UI change).

---

## 10. Run procedure and acceptance

1. **Sign-off + freeze commit:** this plan, D-78, and the constants in
   `ReplayParams`; record the plan hash.
2. **Implement + tests:** focused suites green; full suite only the known
   pre-existing failures; `verify_replay.py` green on synthetic fixtures.
3. **Dry run twice:** `python run_paper_replay.py --rules-version v0.2
   --window-start 2026-08-20 --window-end 2026-10-19 --no-write`; diff the two
   JSON artifacts excluding `generated_at`. Byte-identical rows required.
   (`--no-write` may dry-run the full window before the data horizon; the
   36-day gate applies only to a writing run.)
4. **Write once:** the real run writes the ledger and the artifact.
   `python backend/scripts/verify_replay.py` (defaults to the latest run;
   `--artifact` cross-checks the JSON).
5. **Record:** session log with the funnel, both arm summaries, the deltas, the
   family mix, the 3 `unknown` screens, and the explicit non-evidence label.
6. **Stop:** no follow-up tuning from the H-09 result. Any change is a new
   pre-registered version, not an H-09 amendment.

**Acceptance criteria (all must hold):**

- Every funnel count reconciles; no signal is counted twice or dropped silently.
- Every v0.2 ledger row has: `rules_version='v0.2'`, a family, `stop <
  entry_price ≤ entry_high` (a gap-down fill may be **below** `entry_low`; the
  fill is recorded, not the limit), `stop < entry_low`, `target_1 > entry_low`,
  `plan_rr` within the family band, an allowed `exit_reason`, and (multi-leg)
  legs summing to 100% with weighted R = `realized_r` and `dollar_pnl` = leg sum.
- `verify_replay.py` PASS; zero rows added to `paper_trades`; the scorecard's
  scored set is unchanged by the replay (it reads `paper_trades` only).
- The artifact contains the universe/screen hashes, cache metadata, requested
  vs effective window, data horizon, funnel, both arm summaries and the deltas.
- The two dry runs are identical.
- The run is labelled exploratory in the DB, the artifact, the session log and
  the decision record.

**Data-horizon gate (see G10).** A run is accepted only when the daily data
extends at least **36 calendar days past `window_end`**: up to 3 sessions
(≈5–6 calendar days) for the limit to fill or expire, plus the longest family
time stop (30 calendar days) measured from the entry date. Today (2026-10-29)
the full D-71 window (ends 2026-10-19) does **not** qualify; the earliest
fully-resolved run of that window is **2026-11-24**. Running earlier requires
`--allow-censored`, which labels `eod` rows and excludes them from the primary
aggregate.

---

## 11. Decisions needed before coding

Each item has a recommended default. Sign-off means "accept the default" or
state the alternative.

| # | Decision | Recommended default | Alternative / why it matters |
|---|---|---|---|
| **G1** | What is the v0.1 comparator? | **Rebuild live v0.1 rules on the same fills** (highest-3 targets, last-target RR gate, `infer_exit`, 30-day cap). D-71's published run is a reference line, not the comparator. | Compare only to the D-71 aggregate. Cheaper, but not apples-to-apples (different entry model, targets and exits). |
| **G2** | Entry zone and stop basis | `entry_low = C × (1 − max(0.5×ATR/C, 1.5%))`, `stop = C − 2×ATR` (live default width + live 2×ATR fallback, signal-close basis). | Use D-71's fill-based stop (`entry_low − 2×ATR`). Closer to D-71, further from live. |
| **G3** | Signal set | **Reuse the D-71 engine's entry stream** (one open trade at a time per template/symbol); discard its prices/exits. Identical signals across arms and continuity with the published funnel. | Raw screen mask + a cooldown. More signals, but invents a new signal rule and diverges from D-71. |
| **G4** | Gate scope | **Step 5 only** (5a stop distance, 5b, 5c consistency, 5d family/last-target floor) via `gate.evaluate_risk_reward`. Steps 1–4, 6–7 are not replayable and are recorded as "not applied". | 5d only. Narrower, but not the gate the live plan actually passes. |
| **G5** | Sizing / portfolio | Flat 1% risk; CONDITIONAL × 0.5; no 8-position/30% sector/duplicate caps. R stats are size-independent. | Full portfolio simulation. Out of scope and would add a new source of divergence. |
| **G6** | Which arm goes in `replay_trades`? | **v0.2 only**, `rules_version='v0.2'`; v0.1 arm + deltas in the run summary/artifact. | Both arms with an `arm` column + Journal toggle. More useful UI, more code; the D-71 ledger is replaced either way. |
| **G7** | Trades still open at the data edge | Close at the last close (`eod`), report separately; primary aggregate only when the 36-day horizon is covered. | Exclude censored trades. Biases toward resolved outcomes; rejected. |
| **G8** | Fill counterfactuals for rejected plans | **Yes, for analysis only**: shared fills let the exit-only table use the same fills; the primary policy book contains accepted trades only. | No counterfactuals. Loses the "does v0.2 reject the bad ones?" answer. |
| **G9** | Day cap | `max_per_day = 0` (every deduped signal). | Cap per day. Changes the population; not D-71 parity. |
| **G10** | Window dates and run timing | **Freeze D-71's 2026-08-20 → 2026-10-19 and run after 2026-11-24** so every family stop resolves (3-session expiry + 30-day stop). | **(a)** Shift the 60-day window earlier (e.g. 2026-07-30 → 2026-09-28) and run now; different regime mix. **(b)** Run the D-71 window now with `--allow-censored`; newest signals are truncated. |
| **G11** | Family name source | **Display name** (`config.name`), exactly as the live brief. Report all three `unknown` screens (MTF and Simple are display-name gaps; Distribution is expected) and run a stem-based sensitivity. | Use the stem. More screens get a family, but it diverges from live. |
| **G12** | Replay ledger coexistence | H-09 **replaces** the D-71 ledger (replay tables are disposable); the D-71 JSON artifact remains. | Keep multiple runs with a `run_kind` column + UI selector. New schema/UI work; not needed for H-09. |
| **G13** | v0.1 time stop | **30 calendar days** (live swing default). | D-71's 15-bar cap. Closer to the published replay, but not live v0.1. |

Smaller defaults, no sign-off needed unless you object: `risk_pct=1.0`,
`account_value=100_000`, `fill_expiry_sessions=3`, `entry_zone_atr_mult=0.5`,
`min_zone_pct=1.5`, `stop_atr_mult=2.0`, `v01_max_hold_days=30`.

---

## 12. Risks and known biases

1. **Not the live brief.** No TradingView ranking, confluence, catalysts,
   earnings/liquidity checks, portfolio caps or the live `entry_low` branch
   selection (MA proximity, overbought). Only step 5 of the gate is replayed.
2. **Survivorship bias.** The universe is today's S&P 500 snapshot (D-71
   caveat); delisted/removed names are absent.
3. **Signal stream is inherited.** The engine's one-position-at-a-time rule
   and 15-bar ATR walker determine which signals exist. Both arms share it, so
   the delta is clean, but the absolute numbers are not the live signal rate.
4. **Structural levels are OHLCV-only.** Live also uses TradingView resistance;
   the candidate pool is narrower and the target mix will differ.
5. **Entry zone is the default branch.** Real live plans often use the MA or
   overbought branch; the replay uses the 0.5×ATR / 1.5% default only.
6. **Stop basis changed vs D-71.** Signal-close 2×ATR instead of fill-based.
   This changes R geometry and therefore which trades pass the family floor;
   it is disclosed, not hidden.
7. **Family-map gaps.** Three deployed screens map to `unknown` under the live
   display-name path (MTF, Low-Vol Simple, Distribution). This is live
   behavior; H-09 reports it and runs a stem-based sensitivity. It is a
   candidate for a future version, not an H-09 fix.
8. **Censoring at the data edge.** Running before 2026-11-24 truncates the
   newest 30-day trades; the primary aggregate refuses that unless explicitly
   allowed and labelled.
9. **Multiple comparisons.** One window, one universe, several cuts. Any
   positive result is a hypothesis for a new pre-registered sample, not
   evidence.
10. **The v0.1 arm is a reconstruction.** It applies live v0.1 rules to replay
    geometry; it is not the live v0.1 journal and will not reproduce its rows.
    Two v0.1 quirks are reproduced deliberately: 5c compares the midpoint RR to
    the entry-low geometry, and `infer_exit` checks T2 before T1 within a bar.

---

## 13. Out of scope

- Bundle B (regime permission, menu, ranking, sector rotation, sizing, stops,
  entry rules).
- Any change to `exit_policy`, `gate`, `synthesis`, `pending`, `pnl`, the
  journal schema, the scorecard or the verifier behavior.
- Frontend changes. The replay table ignores the new fields; a v0.1/v0.2 toggle
  is a separate piece of work (G6 alternative).
- Re-simulating v0.1 forward rows. They keep NULL family and are never
  re-decided (D-76/D-77).
- Fixing the family-map display-name gaps. Report, don't fix (G11).

---

## 14. Sign-off record

| Item | Choice | Date / by |
|---|---|---|
| G1 v0.1 comparator | Rebuild live v0.1 rules on the same fills | 2026-10-30 — user sign-off (D-78) |
| G2 entry/stop basis | Signal-close zone + stop: `entry_low = C × (1 − max(0.5×ATR/C, 1.5%))`, `entry_high = C × (1 + 0.5×width)`, `stop = C − 2×ATR` | 2026-10-30 — user sign-off (D-78) |
| G3 signal set | Reuse the D-71 engine's entry stream (one open trade at a time) | 2026-10-30 — user sign-off (D-78) |
| G4 gate scope | Step 5 only via `gate.evaluate_risk_reward` | 2026-10-30 — user sign-off (D-78) |
| G5 sizing | Flat 1% risk; CONDITIONAL × 0.5; no portfolio caps | 2026-10-30 — user sign-off (D-78) |
| G6 ledger arm | v0.2 only; v0.1 arm and deltas in summary/artifact | 2026-10-30 — user sign-off (D-78) |
| G7 open trades | Close at the last close (`eod`); exclude from primary when censored | 2026-10-30 — user sign-off (D-78) |
| G8 counterfactuals | Yes, analysis only: v0.1 fills/exits for rejected v0.2 plans | 2026-10-30 — user sign-off (D-78) |
| G9 day cap | `max_per_day = 0` | 2026-10-30 — user sign-off (D-78) |
| G10 window/timing | Freeze 2026-08-20 → 2026-10-19; full run after 2026-11-24 | 2026-10-30 — user sign-off (D-78) |
| G11 family source | Display name + stem sensitivity; report the three unknowns | 2026-10-30 — user sign-off (D-78) |
| G12 ledger coexistence | Replace the D-71 ledger; keep the D-71 JSON artifact | 2026-10-30 — user sign-off (D-78) |
| G13 v0.1 time stop | 30 calendar days | 2026-10-30 — user sign-off (D-78) |

Once signed off, this document becomes **FROZEN** (D-78) and the constants in
`ReplayParams` are the implementation contract. Any later change is a new
exploratory design, not an amendment.
