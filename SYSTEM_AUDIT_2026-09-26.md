# System Audit — Conflu.ai Swing Trading System
**Date:** 2026-09-26  
**Branch:** `fix/technical-tab-empty`  
**Commit:** Latest (includes D-61, D-62, D-63)

---

## Executive Summary

The system has made **significant progress** on gate enforcement, backtesting infrastructure, and elite template deployment. However, **critical gaps remain** that prevent the system from generating reliable, profitable swing trading signals for a working professional without manual intervention.

| Area | Status | Risk |
|------|--------|------|
| Gate Enforcement (Wave-1) | ✅ Implemented | Low |
| Elite Templates (Morning Brief) | ✅ Updated (D-63) | Low |
| Backtest Engine (Main) | ❌ **BROKEN** (vectorbt/plotly) | **Critical** |
| Filter Sweep Backtest | ❌ **BROKEN** | **Critical** |
| Simple Backtest Mode | ⚠️ Partial (uses old endpoint) | **High** |
| R:R Calculation | ⚠️ Fixed but loose tolerance | Medium |
| Trade Execution | ❌ Missing (planning only) | **Critical** |
| Exit Management | ❌ Missing | **Critical** |
| Verification Loop | ❌ Missing | **Critical** |
| Regime Adaptation | ⚠️ Morning Brief only | Medium |

---

## 🔴 Critical Gaps (Must Fix Before Live Use)

### 1. Backtest Engine Completely Broken (CRITICAL)
**File:** `backend/app/infrastructure/backtest/engine.py`  
**Issue:** VectorBT 1.0.0 + Plotly 6.x `scattermapbox` → `scattermap` breaking change  
**Impact:** ALL filter sweep backtests fail → no valid parameter optimization possible  
**Attempted Fixes:** Monkey-patching at lines 24-54 and 147-164 — **FAILED** (template created at import time)  
**Workaround:** LightweightBacktestEngine exists but **not used by filter sweep engine**

### 2. Simple Backtest Mode Uses Broken Endpoint (HIGH)
**File:** `frontend/src/api/backtest.ts` → `runSimpleBacktest()` → `/api/v1/backtest`  
**Issue:** Uses old `BacktestEngine` (vectorbt) not the working `ExternalBacktestEngine`  
**Impact:** Simple backtest results are unreliable/fail

### 3. No Trade Execution Pipeline (CRITICAL)
**Status:** Planning only — no execution layer  
**Missing:**
- Order submission (no broker integration)
- Position entry automation
- Real-time position monitoring
- Self-closing exits (Sec.2E in gate plan — planned, not built)

### 4. No Exit Management (CRITICAL)
**Planned:** "Self-closing exits" (Sec.2E gate plan) — infer fills from daily OHLCV  
**Implemented:** ❌ Nothing  
**Impact:** Paper trades have no exit logic → cannot measure actual R:R or win rate

### 5. Filter Sweep Backtest Blocked (HIGH)
**File:** `backend/app/infrastructure/backtest/filter_sweep_engine.py`  
**Issue:** Uses `LightweightBacktestEngine` but untested; vectorbt engine broken  
**Impact:** No parameter optimization → cannot validate/improve templates

### 6. No Verification/Edge Tracking (CRITICAL)
**Missing:** No expectancy/edge tracking over time  
**Impact:** Cannot know if system actually works → "pure swing trading dynamics" is an assumption, not verified

---

## 🟠 High Priority Gaps

### 7. R:R Consistency Tolerance Too Loose (HIGH)
**File:** `backend/app/domain/workflow/gate.py` line 50  
**Issue:** `RR_CONSISTENCY_TOL = 0.35` (35% tolerance)  
**Impact:** Reported R:R can differ 35% from plan geometry → false PASS on Risk/Reward step

### 8. Stop Distance Ceiling Policy Not Configured (HIGH)
**File:** `backend/app/domain/workflow/gate.py` line 39, 115-117  
**Issue:** `MAX_STOP_DISTANCE_PCT = 10.0` but `evaluate_stop_distance` returns CONDITIONAL when `max_stop_distance_pct is None`  
**Gate Input:** `max_stop_distance_pct` never passed → Step 5a/5b always CONDITIONAL

### 9. Positioning Step Always CONDITIONAL (HIGH)
**File:** `backend/app/domain/workflow/gate.py` line 209-237  
**Issue:** Short interest, institutional ownership, options flow **not wired** → Step 3 always CONDITIONAL

### 10. Catalyst Bias Not Always Available (MEDIUM)
**File:** `backend/app/domain/workflow/gate.py` line 240-257  
**Issue:** `catalyst_bias_direction` only from orchestrator; may be missing

### 11. Portfolio Fit Step Limited (MEDIUM)
**File:** `backend/app/domain/workflow/gate.py` line 398+  
**Issue:** Only checks position count and sector exposure; no correlation check, no account risk check

### 12. Simple Backtest Results Don't Include Trades/Equity (HIGH)
**File:** `frontend/src/api/backtest.ts` `SimpleBacktestResponse`  
**Issue:** `trades: []`, `equity_curve: []` always empty — backend doesn't populate them

---

## 🟡 Medium Priority Gaps

### 11. Morning Brief Sector Screen Uses ETF Holdings (Quality Concern)
**File:** `backend/app/infrastructure/professional/morning_brief.py` line 210-228  
**Issue:** 4th screen uses ETF top holdings scored with custom yfinance logic, not TV screener

### 12. No Regime Adaptation in Workflow (MEDIUM)
**Workflow Page:** Shows regime but doesn't auto-filter/suggest templates like Morning Brief

### 13. No Real-time Data in Workflow (MEDIUM)
**Workflow Page:** Watchlist analysis runs on demand, not streaming

### 14. No Intraday Exit Monitoring (MEDIUM)
**Planned:** Self-closing exits from daily OHLCV (Sec.2E)  
**Implemented:** ❌

### 15. No Correlation Check in Portfolio Fit (MEDIUM)
**File:** `backend/app/domain/workflow/gate.py` `evaluate_portfolio_fit`

### 15. No Trade Journal Edge Tracking (MEDIUM)
**Journal:** CSV-based, no expectancy/win rate tracking over time

---

## 🟢 Lower Priority / Already Fixed

| Item | Status |
|------|--------|
| `_calculate_dynamic_rr` (manufactured targets) | ✅ **REMOVED** |
| Targets from structure (1H fix) | ✅ **IMPLEMENTED** |
| `_enforce_plan_geometry_invariants` | ✅ **IMPLEMENTED** |
| Gate enforcement (Wave-1) | ✅ **IMPLEMENTED** |
| Elite templates in Morning Brief | ✅ **UPDATED** (D-63) |
| Simple Backtest UI | ✅ **IMPLEMENTED** (D-62) |
| Elite template deployment | ✅ **D-61** |

---

## 📋 Recommended Fix Priority Order

### Week 1: Fix Backtesting Foundation
1. **Fix LightweightBacktestEngine** — complete implementation, test against known signals
2. **Wire Filter Sweep → LightweightBacktestEngine** — replace vectorbt
3. **Fix Simple Backtest** → use `ExternalBacktestEngine` instead of old endpoint
4. **Run initial sweeps** on elite templates to validate parameters

### Week 2: Fix R:R & Gate Integrity
1. **Tighten `RR_CONSISTENCY_TOL`** from 0.35 → 0.15
2. **Wire `MAX_STOP_DISTANCE_PCT`** into gate input pipeline
3. **Fix stop distance ceiling** — make it PASS/FAIL not CONDITIONAL

### Week 3: Execution Pipeline
1. **Implement self-closing exits** (Sec.2E) — infer exits from daily OHLCV
2. **Add exit execution** to paper trade script (`--sync-exits --apply`)
3. **Add position tracking** — open positions with stops/targets

### Week 4: Verification Loop
1. **Add expectancy tracking** — per-template, per-regime, rolling
2. **Add regime-performance dashboard** — Morning Brief + Workflow
3. **Add edge verification** — minimum n=30 trades before template promotion

---

## 🚫 Non-Negotiable Requirements for "Elite Trader" Quality

Before a working professional can use this system to "take trades, make profits like an elite trader, no gaps, no false positive, no emotions":

1. ✅ **Gate enforcement** — backend-owned, honest CONDITIONAL
2. ✅ **Elite templates** — >55% WR, >1.5 PF, ≥10 trades
3. ✅ **Targets from structure** — 1H fix implemented
4. ❌ **Validated backtests** — sweep engine must work
5. ❌ **Exit execution** — self-closing exits from OHLCV
6. ❌ **Edge verification** — expectancy tracking per template/regime
7. ❌ **R:R integrity** — tight consistency tolerance (≤0.15)
8. ❌ **Stop ceiling enforced** — not CONDITIONAL
8. ❌ **Positioning data wired** — Step 3 must be real
9. ❌ **Edge verification per regime** — expectancy by regime
10. ❌ **Minimum sample size** — n≥30 before template promotion

---

## 📝 Files Requiring Changes

### Critical (Week 1-2)
| File | Change |
|------|--------|
| `backend/app/infrastructure/backtest/filter_sweep_engine.py` | Use `LightweightBacktestEngine` instead of vectorbt |
| `frontend/src/api/backtest.ts` | `runSimpleBacktest` → call `ExternalBacktestEngine` endpoint |
| `backend/app/domain/workflow/gate.py` | `RR_CONSISTENCY_TOL = 0.15`; wire `max_stop_distance_pct` |
| `backend/app/infrastructure/backtest/external_backtest.py` | Ensure `_run_simulation` returns trades + equity curve |

### High (Week 2-3)
| File | Change |
|------|--------|
| `backend/app/domain/workflow/gate.py` | Wire positioning data (D-46); tighten RR tolerance |
| `backend/scripts/paper_trade_from_brief.py` | Add `--sync-exits --apply` implementation |
| `backend/app/domain/workflow/exits.py` | **NEW** — self-closing exit inference from OHLCV |
| `frontend/src/components/workflow/WorkflowPage.tsx` | Add regime-based template suggestions |

### Medium (Week 4+)
| File | Change |
|------|--------|
| `backend/app/domain/workflow/journal.py` | Add expectancy/edge tracking per template |
| `frontend/src/components/professional/MorningBriefPage.tsx` | Add regime-performance panel |
| `backend/app/domain/workflow/verification.py` | **NEW** — edge verification per template/regime |

---

## ✅ Verification Checklist Before "Go Live"

- [ ] Filter sweep runs 5 presets × 10 symbols × 3 regimes = 150 backtests successfully
- [ ] All 12 elite templates show >55% WR, >1.5 PF in sweeps
- [ ] Simple backtest returns trades + equity curve for any template/symbol/date
- [ ] Gate Step 3 (Positioning) returns PASS/FAIL (not CONDITIONAL)
- [ ] Gate Step 5a/5b (Stop Distance) returns PASS/FAIL (not CONDITIONAL)
- [ ] Gate RR consistency tolerance ≤ 0.15
- [ ] Paper trade script `--sync-exits --apply` infers exits from OHLCV
- [ ] Paper trade journal tracks expectancy per template/regime
- [ ] Morning Brief shows regime-specific template performance
- [ ] Workflow page suggests templates based on current regime
- [ ] Minimum 30 trades per template before "elite" badge
- [ ] Expectancy > 0 verified over rolling 30-trade window

---

*Document created: 2026-09-26*  
*Audit branch: `fix/technical-tab-empty`*  
*Reference sessions: 2026-09-16 through 2026-09-26*