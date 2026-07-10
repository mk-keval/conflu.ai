# Session Log: Elite Screener Enhancements — Filters, Scoring, Signal Enrichment

**Started:** 2026-07-09
**Branch:** `feature/sector-rotation`
**Base:** `6a273f4` (docs: document sector rotation and screener education features)

## User Prompt
Upgrade the TV screener pipeline with elite trader-grade enhancements: enhanced filters, adaptive regime-aware scoring, and post-TV signal enrichment (RS rating, institutional quality, signal conviction, Wyckoff phase proxy).

---

## Phase 1 — Enhanced FILTER_MAP (56 total)

### Actions
Extended `FILTER_MAP` in `tv_specialist.py` from ~16 to **56 filters** across 7 categories:

**Trend/MA Filters (6 new):**
- `trend_stack`: All MAs aligned (close > SMA20 > SMA50 > SMA200)
- `ema_stack_bullish`: Close > EMA20 > EMA50 > EMA200
- `ema_stack_bearish`: Close < EMA20 < EMA50 < EMA200
- `cross_above_ma`: Close crossed above N-period MA
- `cross_below_ma`: Close crossed below N-period MA
- `bb_breakout`: Close crossed above upper BB

**RSI/Stochastic/MACD (12 new):**
- `rsi_oversold` / `rsi_overbought` / `rsi_in_range`
- `rsi_macd_bullish` / `rsi_macd_bearish`
- `macd_cross_above` / `macd_cross_below`
- `stoch_bullish_cross` / `stoch_bearish_cross` / `stoch_oversold` / `stoch_overbought`
- `cci_oversold` / `cci_overbought`

**Volume (5 new):**
- `rvol_high` / `rvol_low`
- `obv_rising` / `obv_falling`
- `volume_spike`

**Volatility/ATR (5 new):**
- `vwap_band`
- `bb_squeeze` / `bb_squeeze_tight`
- `atr_pct_below`
- `bb_expanding`

**Trend Strength (2 new):**
- `adx_trending` / `adx_rising`

**Pattern (4 new):**
- `inside_bar`
- `vwap_reclaim` / `vwap_reject`

**Fundamental (6 new):**
- `sector_is` / `industry_in`
- `market_cap_gt` / `market_cap_lt`
- `analyst_strongbuy` / `analyst_sell` / `analyst_rating_in`
- `dividend_yield_gt` / `eps_positive` / `pe_max`

**Lazy helpers:** `_and()` / `_or()` for composable multi-filter AND/OR logic.

### Files Modified
- `backend/app/infrastructure/screener/tv_specialist.py`

---

## Phase 2 — 9 New Elite Screen Configs

### Actions
Created 9 new YAML screen templates:

| Screen | Purpose |
|--------|---------|
| `sector-rotation-leader` | Top RS sectors with institutional flow |
| `institutional-accumulation` | Large cap + rising volume + bullish RSI/MACD |
| `rs-leader` | Multi-factor relative strength ranking |
| `high-conviction-stack` | 6+ bullish filters (trend, RSI, ADX, MACD, volume, BB) |
| `bull-flag-continuation` | Pullback to MA support with RSI reset |
| `volatility-expansion` | Broadening BB + ADX trending + volume surge |
| `statistical-mean-reversion` | Oversold RSI + BB lower band touch |
| `earnings-momentum` | EPS positive + analyst strong buy + ADX |
| `short-squeeze` | Oversold + bearish stack + volume spike |

Total templates: **21** (9 new + 12 existing)

### Files Created
- `backend/app/infrastructure/screener/configs/` — 9 new `.yaml` files

---

## Phase 3 — Adaptive Confluence Scorer

### Actions
Added `TVConfluenceScorer.apply_adaptive_weights()` with 4 market regimes:

| Regime | Trend | Momentum | Volume | Volatility | Quality |
|--------|-------|----------|--------|------------|---------|
| `strong_trend` | 30 | 25 | 20 | 10 | 15 |
| `ranging` | 15 | 20 | 20 | 20 | 25 |
| `high_vol` | 15 | 15 | 15 | 35 | 20 |
| `low_vol` | 20 | 25 | 25 | 10 | 20 |

Bonus: RS rating above 60 → +5 weight boost to Quality factor.
Regime-aware `regime_adjusted_total` added to scored output.
Backward compatible when regime=None (legacy weights unchanged).

### Files Modified
- `backend/app/infrastructure/screener/confluence_scorer.py`

---

## Phase 4 — EliteSignalProcessor (Post-TV Enrichment)

### Actions
New `EliteSignalProcessor` class at `elite_signal.py` with 6 enrichment dimensions:

1. **RS Rating (1-99):** Multi-factor relative strength percentile across all ranked tickers (price change, volatility-adjusted return, volume trend, ADX strength, consensus score)
2. **Institutional Quality (0-100):** Market cap, volume liquidity, analyst consensus, dividend quality
3. **Signal Conviction (high/medium/low):** Combines RS rating + quality + factor alignment (no factor conflicts → high)
4. **Wyckoff Phase Proxy (accumulation/markup/distribution/markdown):** Price trend + volume trend combination heuristic
5. **Factor Conflict Detection:** Flags divergences between trend/momentum/volume factors
6. **Regime tag passthrough**

### Files Created
- `backend/app/infrastructure/screener/elite_signal.py`

---

## Phase 5 — TV Engine Integration

### Actions
Wired EliteSignalProcessor into `TVScreenerEngine`:
- `screen()` now runs enrichment after confluence scoring
- `screen_multi_tf()` also runs enrichment on intersected results
- Each scored ticker gets an `elite` dict with enrichment data

### Files Modified
- `backend/app/infrastructure/screener/tv_engine.py`

---

## Phase 6 — API & Frontend Integration

### Actions
1. Added `EliteEnrichment` Pydantic model to `tv_models.py` (rs_rating, inst_quality, signal_conviction, wyckoff_phase, factor_conflicts)
2. Wired through `_build_scored_response()` in `tv_screener.py` router
3. Added `TVEliteEnrichment` TypeScript interface in `screener.ts`
4. Added 3 new sortable columns to `ScreenerTable.tsx`:
   - **RS Rtg** (`rs_rating`) — Color-coded 1-99 score (green ≥80, blue ≥60, yellow ≥40, red <40)
   - **Inst Q** (`inst_qual`) — Color-coded 0-100 institutional quality score
   - **Conv** (`conviction`) — Color-coded dot + label (green=high, yellow=medium, red=low)

### Files Modified
- `backend/app/infrastructure/screener/tv_models.py`
- `backend/app/api/routers/tv_screener.py`
- `frontend/src/types/screener.ts`
- `frontend/src/components/screener/ScreenerTable.tsx`

---

## Files Modified (All Phases)
| File | Phase | Type |
|------|-------|------|
| `backend/app/infrastructure/screener/tv_specialist.py` | 1 | Modified |
| `backend/app/infrastructure/screener/configs/` (9 YAML) | 2 | Created |
| `backend/app/infrastructure/screener/confluence_scorer.py` | 3 | Modified |
| `backend/app/infrastructure/screener/elite_signal.py` | 4 | Created |
| `backend/app/infrastructure/screener/tv_engine.py` | 5 | Modified |
| `backend/app/infrastructure/screener/tv_models.py` | 6 | Modified |
| `backend/app/api/routers/tv_screener.py` | 6 | Modified |
| `frontend/src/types/screener.ts` | 6 | Modified |
| `frontend/src/components/screener/ScreenerTable.tsx` | 6 | Modified |

## Verification
- **Frontend:** `tsc && vite build` — Passes clean ✅
- **Backend Python imports:** ✅
  - FILTER_MAP: 56 filters loaded ✅
  - EliteSignalProcessor import + instantiation ✅
  - TVConfluenceScorer with 4 regimes ✅
  - 21 screen templates loaded ✅
  - TVScreenEngine import ✅
- **Sortable columns:** rs_rating, inst_qual, conviction — all wired in COL_RENDERERS + sorting switch ✅

## Next Steps
- Add test coverage for EliteSignalProcessor (unit tests)
- Add test coverage for adaptive regime scoring
- Add frontend column toggle UI for new elite columns (they're non-alwaysOn)
- Consider integrating Wyckoff phase into screener filter logic
- Consider caching EliteSignalProcessor results per screen cycle

## Key Design Decisions
- **Post-TV enrichment** keeps TradingView as pure data provider — enrichment is stateless, computed client-side per response
- **RS rating is relative** (percentile within current screen results), not absolute — same ticker can have different RS rating in different screen contexts
- **Conviction = RS + quality + conflict check** — high conviction means top RS, high inst quality, and zero factor conflicts
- **Wyckoff phase is a proxy** — true Wyckoff analysis requires multi-timeframe bar-by-bar volume analysis
