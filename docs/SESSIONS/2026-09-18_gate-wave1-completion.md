# Session Log — Gate Wave-1 Completion: 2B/2C/2D/1D/2E/1E + 0A-i Control Study

**Date:** 2026-09-18 · **Branch:** `fix/technical-tab-empty` · **Type:** Wave-1 completion (application code + control study)

**Related:** `docs/DECISIONS/D-56-gate-enforcement-wave1-complete.md`, `docs/SESSIONS/2026-09-18_ungated-cohort-control-study.md`, `docs/DECISIONS/D-53-gate-enforcement-spine-wave1c.md`

---

## Context

D-53 shipped the backend 7-step gate evaluator + verdict wiring. This session completed **every unblocked item remaining in Wave 1** of the approved plan (`.sisyphus/plans/gate-enforcement-spine.md`): **1E** (stop ceiling), **2B** (journal reader), **2C** (real Portfolio Fit), **2D** (risk sizing), **1D** (enforcement in the trade-writing script), **2E** (self-closing exits), and **0A-i** (historical control study). 1H/5d/0A-ii remain deferred per plan (D-51 REV7 / D-52).

## Action taken

All work performed directly in the main session — no delegation (standing user instruction after prior agent 429/timeout failures: "dont assign task to other model, you can finish it yourself").

### 1. Circular-import discovery (prerequisite for everything)

`workflow/gate.py` imports `GateResult`/`GateStepResult` from `ticker_analysis.models`; `ticker_analysis/__init__` eagerly imports `synthesis`, which imports `workflow.gate`. A module importing `workflow.gate` cold hits the cycle mid-init: `ImportError: cannot import name 'build_gate_input'`. **Fix used in all new consumers**: import `backend.app.domain.ticker_analysis` FIRST, then workflow modules (same ordering constraint `test_gate.py` already satisfied).

### 2. 1E — stop ceiling (`workflow/gate.py`)

- `MAX_STOP_DISTANCE_PCT = 10.0` (D-8, set from first principles — not tuned against the voided cohort).
- `evaluate_stop_distance(entry, stop, max_stop_distance_pct=None)` signature preserved (explicit 7.0 in `test_synthesis_geometry.py:32` still passes).
- 5d reward ladder remains deferred but now **surfaces** as an appended CONDITIONAL sub-check when reward geometry exists — a visible hook for 1H; Step 5 can only reach PASS when no reward geometry exists.

### 3. 2B — journal reader (`workflow/journal.py`, new)

- `read_rows`, `read_open_positions`, `read_closed_trades`, `position_size_pct`, `account_value`, `sector_exposure`, `available_capital`.
- Skips TEMPLATE.csv + REJECTIONS.csv; normalizes `""`/`"-"`/`"NA"`/`"nan"` → None; fallback account $100,000.0.
- Verified against the live journal: **`read_open_positions` returns `[]`** (paper-trade directory holds only the template + rejected rows).

### 4. 2C — real Portfolio Fit (`workflow/gate.py`)

- `MAX_OPEN_POSITIONS = 8`, `SECTOR_EXPOSURE_LIMIT_PCT = 30.0` (incl. candidate's size), duplicate-symbol rules: planned add at a NEW stop → CONDITIONAL; market add into unchanged stop → hard FAIL.
- `GateInput`/`build_gate_input` extended with `sector`/`entry_type`/`position_size_pct`/`open_positions`.
- Synthesis path stays honest CONDITIONAL when no open book is provided (R12).

### 5. 2D — risk sizing (`workflow/sizing.py`, new)

- `compute_position_size_pct(entry, stop, gate_verdict=None, *, cap=25.0, risk_budget_pct=1.0)`; `RISK_BUDGET_PCT=1.0`, `MAX_POSITION_SIZE_PCT=25.0`, `MIN_SIZE_PCT=0.5`; CONDITIONAL verdict → size halves; degenerate geometry → ValueError.

### 6. 1D — enforcement in `paper_trade_from_brief.py` (REWRITTEN, ~550 lines, `GATE_VERSION="1D-enforcement"`)

- Reuses the verdict's ATTACHED gate (steps 1-5, 7 — computed backend-side), re-evaluates ONLY Step 6 (Portfolio Fit) via `journal.read_open_positions()`, recomputes overall via `compute_gate`.
- **PASS** → full-size row (`entry_type=initial`); **CONDITIONAL** → size ×0.5 + `gate_verdict` + first-conditional `gate_failed_step`; **FAIL** → REJECTIONS.csv, no trade; **blank/absent stop → always REJECT** (`failed_step=stop_loss`).
- `--dry-run` default ON; `--apply` persists. `--sync-exits` backfills open rows via `_fetch_daily_ohlcv` + `exits.infer_exit` (dry-run default too). `--regime-only` removed (R8).
- R7: normalized 0-5 in `confluence_count` AND raw 0-100 in `notes` ("raw confluence 83/100").
- Verified: `--sync-exits` on empty journal prints "No open journal rows to sync."
- 5 new tests (`test_paper_trade_from_brief.py`): PASS-full-size, FAIL→rejection, blank-stop→rejection, CONDITIONAL→halved 10.0 + `gate_failed_step`, sector-exposure ceiling→rejection.

### 7. 2E — auto exits (`workflow/exits.py`, new)

- `infer_exit(bars, *, entry, stop, targets=None, max_hold_days=None) -> ExitFill` — conservative same-bar rule (stop beats target; worse of two fills recorded + flagged `ambiguous`); `mfe_r`/`mae_r` in R units; `as_bars` normalizes yfinance tuples/dicts; `ExitFill.as_row()` maps to the D-51 exit columns; 12 tests.

### 8. 0A-i — control study (`backend/scripts/control_study_voided_cohort.py`, new, 601 lines)

Read-only over the 7 archived bypass CSVs (31 rows; archive byte-for-byte untouched — D-50):

- **Manufacture detector (offline)**: recomputes implied R:R from the recorded tuple, classifies per R25 via the R20 fingerprint (`t1 == entry + risk·1.0`) and the R18 heuristic grid. **Result: 4 manufactured (PAGP, LNG, CVX×2 — exact R25 reproduction), 0 structural (never assignable from the 12-col schema — by construction), 27 indeterminate.**
- **Stop-distance distribution**: n=30, min 3.72%, mean 9.43%, max 30.61%; **7/30 exceed the 10% ceiling** (GWRE 30.61 / BULL 22.82 / TARS 20.9 / SLDE 17.94 / INTC 17.4); 29/31 violate the blueprint's 5% cap; 0 exceed the 2D 25% cap.
- **Exit replay (`--backfill-exits`)**: 14/31 resolved (win rate 85.7%, expectancy +1.31 R, profit factor 10.2); **17 explicitly marked unresolvable** (2026-09 entries at the edge of the 2y OHLCV window). These are the *ungated* cohort's numbers — 0A-ii (gate-PASS counterfactual) stays blocked until 1H.
- Report: `docs/SESSIONS/2026-09-18_ungated-cohort-control-study.md`.
- 13 tests (`test_control_study_voided_cohort.py`); one assertion corrected during the run (CVX t2=2.2R is off the round grid — non-round heuristic result, not provable from the tuple; R20's 1.0R is the proof that fires).

## Verification

- **79 passed** (combined relevant suite: gate 17 + synth-geometry 20 + journal 6 + sizing 6 + exits 12 + paper-trade-from-brief 5 + control-study 13).
- LSP clean on all changed/new source files (orchestrator.py noise + sys.path-bootstrap script-import warnings are pre-existing/expected — pytest resolves them).
- Git status: session changes are additive/new (workflow/, tests, script, report); pre-existing dirty files (models.py, technical.py, synthesis.py, etc.) not from this session.
- No commits created. No API routes or architecture changed. No delegation used.

## Files created/changed

- `backend/app/domain/workflow/gate.py` (1E/2C), `journal.py` (2B, new), `sizing.py` (2D, new), `exits.py` (2E, new)
- `backend/scripts/paper_trade_from_brief.py` (1D rewrite), `backend/scripts/control_study_voided_cohort.py` (0A-i, new)
- `backend/tests/test_paper_trade_from_brief.py`, `test_control_study_voided_cohort.py` (new)
- `docs/SESSIONS/2026-09-18_ungated-cohort-control-study.md` (0A-i report, new)
- `docs/DECISIONS/D-56-gate-enforcement-wave1-complete.md` (new), plan header + item markers (DONE)
- `docs/DECISIONS/index.md`, `docs/index.md`, `INDEX.md` refreshed

## Next

- **Blocked until 1H (D-52)**: 5d R:R floor, 0A-ii gate-verdict tagging, D1 activation, gate throughput estimates.
- **Wave 2**: V6 recon → 1H source fix in `synthesis.py` → 5d.
- **Pending user approval**: D4 (frontend gate renderer — `gate.ts` becomes a renderer of backend results).