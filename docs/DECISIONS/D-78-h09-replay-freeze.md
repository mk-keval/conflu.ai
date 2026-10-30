# D-78: H-09 Exploratory Replay Frozen (v0.1 vs v0.2 Geometry)

**Date:** 2026-10-30
**Status:** Accepted — user sign-off on G1–G13 (2026-10-30); design **FROZEN**;
implemented and tested. First full ledger write gated to **2026-11-24**.
**Branch:** `fix/technical-tab-empty`
**Spec:** [`docs/PAPER_TRADING/H09_REPLAY_PLAN.md`](../PAPER_TRADING/H09_REPLAY_PLAN.md)
**Related:** D-71 (screen replay), D-73 (pending fills), D-74 (measurement),
D-75 (pass bar), D-76 (sample versioning), D-77 (Bundle A), Bundle A §7.

## Context

FWD-v0.2 froze a new geometry (D-77): the gate measures **T1 R from the
planned fill**, targets are the nearest structural levels inside a family band
or the trade is rejected, and exits are family-specific. The forward sample
cannot answer whether that geometry is better than v0.1 — it only produces a
new sequence of trades with no counterfactual.

H-09 is the counterfactual exercise: take **one signal stream**, plan and exit
it twice, and compare. It is exploratory by construction. A positive result can
motivate a future pre-registered sample; it cannot validate FWD-v0.2, enter the
scorecard, the D-75 pass bar, the kill rule, `/expectancy`, or any verdict.

## Decision

### One signal stream, two plans

- **Signals:** the D-71 engine's one-position-at-a-time entry list over the
  deployed screen templates. The engine's prices, targets and exits are
  discarded; only its signal dates/symbols survive.
- **Engine constants frozen for H-09:** stop 2.0×ATR, target 3.0×ATR, 15-bar
  cap (`SIGNAL_*` in `replay_rules.py`). The plan stop is separate.
- **Shared geometry (G2), signal-close basis:**

  ```
  entry_low  = C × (1 − max(0.5×ATR/C, 1.5%))
  entry_high = C × (1 + 0.5×width)
  stop_loss  = C − 2.0×ATR
  ```

  where `width = 1 − entry_low/C`. Both arms use this geometry and the D-73
  limit fill (3-session expiry). The stop being signal-close based rather than
  D-71's fill-based stop is a **disclosed deviation**, recorded in the run.

- **Arms differ only in:** target selection, the gate's Plan-R floor, and the
  exit policy.
  - v0.1 arm: highest-three structural targets within 1.5× price, midpoint
    R:R gate, `infer_exit`, 30-calendar-day time stop. It deliberately
    reproduces two live v0.1 quirks: 5c compares the midpoint R:R to entry-low
    geometry, and `infer_exit` checks T2 before T1 inside a bar.
  - v0.2 arm: `exit_policy.select_targets` (nearest structural T1 inside the
    family band, otherwise reject), gate step 5 only, `simulate_exit`. No
    ATR/percentage fallback target: no structural objective means **reject**.

### Population and bookkeeping

- **G1:** rebuild v0.1 on the same fills; D-71's published numbers are a
  reference line, not a row-for-row comparator.
- **G3:** reuse the D-71 entry stream (continuity with the published funnel).
- **G4:** replay only gate step 5 (`evaluate_risk_reward`); steps 1–4 and 6–7
  are not replayable and are recorded as not applied.
- **G5:** flat 1% risk, CONDITIONAL × 0.5, no portfolio caps. R is
  size-independent.
- **G8:** rejected v0.2 plans keep a v0.1 counterfactual exit for the
  rejection-quality table; the primary policy book is accepted trades only.
- **G9:** `max_per_day = 0`; every deduped signal is planned.
- **G11:** family from the live **display name** (`config.name`); the stem map
  is a secondary sensitivity. The three deployed screens that normalize to
  `unknown` (Institutional Trend Follower MTF, Low-Vol Setup Simple,
  Distribution) are reported, not fixed here.
- **G7:** trades open at the data edge close at the last close (`eod`); they
  are excluded from the primary aggregate and shown in an all-accepted view.

### Window, horizon and write gate

- **G10:** the window is frozen at **2026-08-20 → 2026-10-19** (D-71's window).
- A writing run requires daily data extending **36 calendar days past
  `window_end`**: up to 3 sessions for the limit fill plus the longest family
  stop (30 calendar days). The earliest full run is **2026-11-24**.
- Dry runs may run earlier. An early write requires `--allow-censored`; the run
  then stores `metadata.write_consent` and the verifier accepts it, while `eod`
  rows remain excluded from the primary aggregate.
- The CLI refuses to write when: horizon < 36 days without consent, frozen
  design constants deviate, or the window is not the frozen one. The JSON
  artifact is still written and the process exits 2.

### Ledger (G6, G12)

- Only the **v0.2 accepted** arm is stored in `replay_trades`
  (`rules_version='v0.2'`); both arms and the deltas live in the run summary
  and the JSON artifact.
- H-09 **replaces** the D-71 replay ledger (the replay tables are disposable);
  the D-71 JSON artifact remains.
- The ledger is marked `evidence_label='exploratory_h09_not_evidence'` in the
  DB metadata, the artifact, the report output and the session log.
- No `paper_trades` row is written. The replay cannot touch the forward
  scorecard.

### Implementation

- `backend/app/infrastructure/backtest/replay_rules.py` — pure geometry,
  structural levels, both plans, the D-73 fill, same-session stop, exits and
  canonical accounting. Production `gate`, `pending`, `exits`, `exit_policy`
  and `pnl` are imported, never edited.
- `backend/app/infrastructure/backtest/replay.py` — `rules_version` branch,
  daily-only H-09 fetch, frozen signal engine, explicit window, data-horizon
  metadata, `_run_h09`, funnel reconciliation, arm summaries, deltas and
  design provenance.
- `backend/app/domain/workflow/replay_store.py` — additive migration
  (`rules_version`, family/plan/exit/cost columns); legacy runs read as
  `v0.1`.
- `run_paper_replay.py` — `--rules-version v0.2`, frozen window defaults, the
  write gate, arm report, artifact.
- `backend/scripts/verify_replay.py` — the ledger pass/fail gate (geometry,
  legs→VWAP→R, canonical dollars, sizing, Plan-R provenance and family band,
  funnel/summary reconciliation, no `paper_trades` leakage, optional artifact
  cross-check).
- `backend/tests/test_replay_rules.py` (35 tests) and
  `backend/tests/test_replay_h09.py` (8 tests).

## Verification

- Focused suites: `test_replay.py` + `test_replay_rules.py` +
  `test_replay_h09.py` → **51 passed**.
- `ruff` clean on all touched files.
- The full suite retains only the pre-existing failures already present at
  `HEAD`: `test_earnings_filter_missing_file_safe_default` and the date-sensitive
  `test_insider_cluster.py` cases (their fixtures are built relative to today, so
  the count drifts between 1 and 4; none touch replay). Latest run:
  **1066 passed, 2 failed**.
- Live behavior is untouched: no change to `exit_policy`, `gate`, `synthesis`,
  `pending`, `pnl`, the journal schema, the scorecard or the forward samples.

## Consequences

- H-09 answers "does v0.2 reject bad trades or just reject trades?" and "does
  the exit beat v0.1 on the same fills?" — as a **hypothesis**, one window, one
  universe, several cuts.
- Any change to geometry, signal stream, window or rules after this record is
  a **new exploratory design**, not an H-09 amendment. No mid-sample tuning.
- The family-map gaps remain live behavior. Fixing them is a future version,
  not part of this replay.
- The earliest full run is 2026-11-24. Until then the only permitted write is
  an explicitly consented, censored run.
