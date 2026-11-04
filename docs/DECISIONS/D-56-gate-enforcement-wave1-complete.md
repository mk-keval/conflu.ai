# D-56: Gate Enforcement Spine — Wave-1 Completion (1E/2B/2C/2D/1D/2E) + 0A-i Control Study

Date: 2026-09-18
Status: Accepted (extends D-53 — completes every unblocked item in the gate-enforcement spine's Wave 1; Wave 2 = V6 → 1H → 5d remains, blocked by the R:R source fix D-52)

## Context

D-53 shipped the backend gate evaluator (7-step `gate.py`) and verdict wiring
in `synthesis.synthesise()`. This session completes the rest of the approved
plan's Wave 1 — the items the plan marked "NOT blocked — build now" (Sec.8):
**1E** (stop ceiling + 5d stub surfacing), **2B** (journal reader), **2C**
(real Portfolio Fit), **2D** (risk-based sizing — MUST precede 1D), **1D**
(enforcement in the script that writes trades), **2E** (auto exits). It also
delivers **0A-i**, the strongest available action per the plan: a read-only
control study that *measures* R18/R19/R20 over the 31 voided rows instead of
asserting them from code-reading.

Prior constraints honored:

- **1H/5d remain deferred** (D-51 REV7, D-52 reserved): the R:R reward ladder
  and the counterfactual 0A-ii wait for the `synthesis.py` source fix.
- **Circular import** discovered and resolved: `workflow/gate.py:35` imports
  `GateResult/GateStepResult` from `ticker_analysis.models`, and
  `ticker_analysis/__init__` eagerly imports `synthesis` → `workflow.gate`.
  Any module importing `workflow.gate` cold hits the cycle mid-init
  (`ImportError: cannot import name 'build_gate_input'`). Fix used everywhere
  (script + tests): import `backend.app.domain.ticker_analysis` FIRST, then
  workflow modules — the same ordering constraint test_gate.py already used.
- **Empty-journal portfolio fit**: `evaluate_portfolio_fit` returns honest
  CONDITIONAL on `not positions` (protects the synthesis path where
  `open_positions` is absent — R12). For the SCRIPT path a *verified* empty
  book is clear, so the script emits its own PASSing Step 6 with an explicit
  note ("book is verified clear") instead of laundering the gate module's
  data-gap CONDITIONAL. `gate.py` itself is untouched by this nuance.
- **D-53's honest-degradation contract**: no false-PASS; unknown/missing
  serialized gate → CONDITIONAL, never PASS.
- **D-8 stop ceiling = 10%** (`MAX_STOP_DISTANCE_PCT`), set from first
  principles, NOT tuned against the voided cohort (plan Sec.9).
- **D-51 schema**: 29-column TEMPLATE.csv is the single source of truth;
  `REJECTIONS.csv` header `date_seen,symbol,sector,action,conviction,
  failed_step,gate_verdict,reason,notes`.

## Decision

1. **1E — stop-distance ceiling + 5d surfacing (`workflow/gate.py`)**:
   `MAX_STOP_DISTANCE_PCT = 10.0`. `evaluate_stop_distance` keeps its
   signature `(entry, stop, max_stop_distance_pct=None)` — the explicit 7.0
   in `test_synthesis_geometry.py:32` still passes. Stop wider than the
   ceiling → hard FAIL even when R:R ≥ 2.5 (the BULL 22.8%-stop case must
   fail). The 5d reward ladder (2.5 floor) remains stubbed but now surfaces
   as an appended CONDITIONAL sub-check whenever reward geometry exists —
   so 1H has a visible hook and Step 5 can only reach PASS when no reward
   geometry exists.
2. **2B — journal reader (`workflow/journal.py`, new)**: `read_rows`,
   `read_open_positions`, `read_closed_trades`, `position_size_pct`,
   `account_value`, `sector_exposure`, `available_capital`. Skips
   TEMPLATE.csv and REJECTIONS.csv; normalizes `""`/`"-"`/`"NA"`/`"nan"` →
   None; fallback account value $100,000.0.
3. **2C — real Portfolio Fit (`workflow/gate.py`)**: `MAX_OPEN_POSITIONS = 8`,
   `SECTOR_EXPOSURE_LIMIT_PCT = 30.0` (includes the candidate's size), and
   duplicate-symbol rules (planned add at a NEW stop → CONDITIONAL; market
   add into unchanged stop → hard FAIL). `GateInput` + `build_gate_input`
   extended with `sector` / `entry_type` / `position_size_pct` /
   `open_positions`. The synthesis path stays honest CONDITIONAL when no
   open book is provided.
4. **2D — risk-based sizing (`workflow/sizing.py`, new)**:
   `compute_position_size_pct(entry, stop, gate_verdict=None, *,
   cap=25.0, risk_budget_pct=1.0)` with `RISK_BUDGET_PCT = 1.0`,
   `MAX_POSITION_SIZE_PCT = 25.0`, `MIN_SIZE_PCT = 0.5`. CONDITIONAL
   verdict → size halves. Degenerate geometry (stop ≥ entry, no stop) →
   ValueError (the caller rejects the setup).
5. **1D — enforcement in `paper_trade_from_brief.py` (REWRITTEN)**: the
   script that writes the paper trades now enforces the gate:
   - Reuses the verdict's ATTACHED gate (steps 1-5, 7 — computed
     backend-side with tv_data that never leaves the server), re-evaluates
     ONLY Step 6 (Portfolio Fit) against `journal.read_open_positions()`,
     recomputes the overall via `compute_gate`.
   - **PASS** → full-size row (`entry_type=initial`); **CONDITIONAL** →
     size ×0.5 + `gate_verdict` + first-conditional `gate_failed_step`;
     **FAIL** → row appended to `docs/paper_trades/REJECTIONS.csv`, no trade;
     **blank/absent stop** → always REJECT (`failed_step=stop_loss`).
   - `--dry-run` is the DEFAULT; `--apply` persists. `--sync-exits` backfills
     exits on open rows via `_fetch_daily_ohlcv` + `exits.infer_exit` and
     patches the dated CSV (dry-run by default too). `--regime-only` removed
     (R8). `GATE_VERSION = "1D-enforcement"`.
   - R7: normalized 0-5 confluence stored in `confluence_count` AND the raw
     0-100 appended to `notes` ("raw confluence 83/100").
   - Sizing via `compute_position_size_pct` (replaces the old
     `position_size_pct or 5.0` heuristic); `account_value` read from the
     journal default, not from the verdict.
6. **2E — auto exits (`workflow/exits.py`, new)**: `infer_exit(bars, *,
   entry, stop, targets=None, max_hold_days=None) -> ExitFill` with the
   conservative same-bar rule (stop beats target, worse of the two fills is
   recorded and flagged `ambiguous`). `mfe_r`/`mae_r` in R units; `as_bars`
   normalizes yfinance tuples/dicts; `ExitFill.as_row()` maps to the D-51
   exit columns.
7. **0A-i — control study (`backend/scripts/control_study_voided_cohort.py`,
   new)**: read-only over the 7 archived bypass CSVs (31 rows, untouched —
   D-50). Two halves:
   - **Manufacture detector (offline)**: recomputes implied R:R from the
     recorded tuple and classifies per R25 — *manufactured* (R20 fingerprint
     `t1 == entry + risk·1.0`, or the R18 heuristic grid pair), *structural*
     (never assignable from the 12-column schema — reported 0 by
     construction), *indeterminate* (no signature; structural vs manufacture
     indistinguishable without the entry basis). **Measured result over the
     31 rows: 4 manufactured — PAGP, LNG, CVX×2 — exactly reproducing the
     audit's R25 reading.** Also computes the stop-distance distribution
     (7/30 rows exceed the 10% ceiling; 5 widest = GWRE 30.61 / BULL 22.82 /
     TARS 20.9 / SLDE 17.94 / INTC 17.4) and the sizing check (29/31 violate
     the 5% blueprint cap; 0 exceed the 2D 25% cap).
   - **Exit replay (`--backfill-exits`, network)**: runs the Sec.2E
     inferencer over each row from fetched OHLCV and reports win rate /
     expectancy / profit factor / per-row realized_R, marking unresolvable
     rows explicitly. **Measured: 14/31 resolved (win rate 85.7%,
     expectancy +1.31 R, profit factor 10.2), 17 unresolvable** — the
     unresolvables are the cohort rows at the edge of the 2y OHLCV window
     whose exits were not reached in the available bars (e.g. BULL, PAGP,
     ZETA, GNW, INVX, GWRE, TARS, NVDA, MU, INTC, T, VZ-no-geometry). These
     are the *ungated* cohort's numbers — the counterfactual comparison
     (0A-ii: gate-PASS vs full cohort) stays blocked until 1H per the plan.
   - Report written to `docs/SESSIONS/2026-09-18_ungated-cohort-control-study.md`.
   - Acceptance criteria checked: all rows have an inferred exit or are
     explicitly marked unresolvable ✓; read-only — archive byte-for-byte
     unchanged ✓; n=31 caveat stated on every headline number ✓.
8. **Tests**: new `test_paper_trade_from_brief.py` (5: PASS-full-size,
   FAIL→rejection, blank-stop→rejection, CONDITIONAL→halved size 10.0 +
   gate_failed_step, sector-exposure ceiling→rejection) and
   `test_control_study_voided_cohort.py` (13: detector classification,
   fingerprint helpers, cohort stats). Combined relevant suite: **79 passed
   in ~2s** (gate 17 + synth-geometry 20 + journal 6 + sizing 6 + exits 12 +
   script 5 + control-study 13).

## Consequences

- The paper-trade script can no longer write a trade without the gate's
  blessing: PASS full / CONDITIONAL half / FAIL → REJECTIONS.csv, and a
  blank stop always rejects. The bypass path the audit voided is permanently
  closed.
- The measurement loop closes: every accepted row carries `exit_price`/
  `exit_reason`/`date_closed` (2E) and every run can resync open rows via
  `--sync-exits` — expectancy becomes computable without a database.
- The R:R source defect is now MEASURED, not just asserted: 4/31 rows carry
  the manufactured-pair fingerprint; 27/31 are R25-indeterminate (structural
  firing indistinguishable from manufacture). This is the pre-fix baseline
  for 1H — the pre-fix numbers above must NOT be read as edge evidence.
- 0A-i's exit-replay numbers are the *ungated* cohort's outcome; they do NOT
  validate the gate (0A-ii is blocked until 1H). The n=31 caveat applies to
  every headline.
- Deferred (unchanged): 1H source fix (D-52), 5d floor, D1 activation,
  0A-ii, D4 frontend gate renderer, 2C.4 correlation gate, campaign-level R
  aggregation. No commits created. No API routes or architecture changed.

## Verification

- `python backend/scripts/paper_trade_from_brief.py --help` runs (all flags).
- `--sync-exits` on an empty journal prints "No open journal rows to sync."
- `control_study_voided_cohort.py` offline: detector reproduces R25 (4
  manufactured: PAGP, LNG, CVX×2; 27 indeterminate; 0 structural).
- `control_study_voided_cohort.py --backfill-exits`: 14 resolved / 17
  unresolvable, report written.
- 79 relevant tests pass; LSP clean on `gate.py`, `journal.py`, `sizing.py`,
  `exits.py`, `paper_trade_from_brief.py`, `control_study_voided_cohort.py`
  and their tests (pre-existing orchestrator.py / script-import LSP noise
  unchanged). No commits created. No delegation used (user instructed
  self-completion).

See [2026-09-18 control study](../SESSIONS/2026-09-18_ungated-cohort-control-study.md)
and [2026-09-18 wave-1 session log](../SESSIONS/2026-09-18_gate-wave1-completion.md).