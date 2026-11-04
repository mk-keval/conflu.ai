# D-44: Data Quality Gaps Fix

**Status:** Accepted
**Date:** 2026-08-31
**Branch:** fix/technical-tab-empty

---

## Why this exists

The user ran an elite-swing-trader exercise against conflu.ai on Aug 31, 2026
(D-43 was the prior fix for an unrelated tab-empty bug). Manual investigation
surfaced 3 silent data-quality bugs and 5 gap-list items that made the
system's signals unreliable for capital allocation. Per the user's
request ("lets fix those gaps with proper planning"), this D-44 record
covers the 6 changes shipped in a single PR on the existing
`fix/technical-tab-empty` branch.

## What was broken

### Bug 1: Weekly technical signals were mostly fake

`_fetch_daily_ohlcv` used `period="6mo"` (~125 daily bars) and
`_fetch_weekly_ohlcv` used `period="2y"` (~105 weekly bars). Both
are <200, so `_compute_indicators_from_ohlcv` never produced an
`SMA200` key. The downstream MA-stack comparison did
`all(sma20, sma50, sma200)` which always returned False, so
`ma_alignment` was permanently `"N/A"` and `structure` was
`"unknown"`. An elite trader who saw `ma_alignment: N/A` on every
weekly bar correctly concluded the weekly trend signal was
unreliable — they were right.

### Bug 2: Mentor narration crashed on every ticker

`narration.py` accessed flat attributes like `cr.bos_events`,
`cr.choch_events`, etc. The D-36 chart-reading refactor nested
those under per-timeframe `TimeframeChartReading` objects. The
orchestrator's try/except silently swallowed the AttributeError,
so `why_this`, `why_now`, `what_kills_it`, `thesis_one_liner` were
always empty in the API response. The headline mentor-narration
feature has been silently dead since D-36.

### Bug 3: 56+ hour stale data on weekends

Every `data_age_hours: 56.4` on the live API. yfinance only refreshes
on market hours; there's no scheduled refresh on weekends. ESTC
rallied 22% post Q1 FY27 beat (Aug 27) but the system still quoted
$99.91 (Friday close) when the actual price was ~$103.

## What we changed

Single PR on `fix/technical-tab-empty`, 9 commits + planning artifacts:

| Bug / Gap | File | Change |
|---|---|---|
| Bug 1 (weekly SMA200) | `technical.py` | `_fetch_daily_ohlcv`: `period="2y"` (was 6mo). `_fetch_weekly_ohlcv`: `period="5y"` (was 2y). |
| Bug 1 (weekly swing) | `technical.py:_analyze_timeframe` | Swing detection now dispatches to daily/weekly/4h/1h based on timeframe using the already-passed OHLCV parameter. |
| Bug 1 (OHLCV cache) | `technical.py` | New module-level `_OHLCV_CACHE` (dict, TTL 6h) + `_cached_yfinance_fetch()` wrapper. Pre-warmed via `POST /api/v1/admin/refresh-data`. |
| Bug 2 (narration) | `narration.py` | New `_all_chart_signals(cr)` helper that iterates per-timeframe `TimeframeChartReading` and yields (tf, kind, event) tuples. Replaces 9 broken direct accesses. Fixed also a separate bug: `cr.composite_tpo_profile` was always wrong (it lives on `cr.daily.composite_tpo_profile`). |
| Bug 3 (stale) | `orchestrator.py` | New `_compute_stale_warning(data_quality_warnings, data_age_hours, now)` (24h weekend / 36h weekday). New `_collect_data_quality_warnings(daily_ohlcv, weekly_ohlcv)` (warns when <200 bars). Populated in `TickerAnalysisResponse` build. |
| Bug 3 (refresh endpoint) | `api/routers/admin.py` (new) | `POST /api/v1/admin/refresh-data` with optional `{symbols: [...]}` body. Defaults to ~50-ticker S&P 500 watchlist. Pre-warms the OHLCV cache. |
| Gap 1 (binary risk) | `models.py` | Added `binary_risk: bool`, `earnings_date: str | None` to `AnalysisVerdict` and `ScoredTickerResponse`. |
| Gap 1 (screener) | `earnings_filter.py` (new) | Reads hand-curated `backend/app/data/earnings_calendar.json` with mtime-based caching. `get_binary_risk(symbol, window_days=5) -> (bool, str | None)`. Safe default `(False, None)` on missing/malformed file. |
| Gap 1 (synthesis) | `synthesis.py` | When `earnings.days_until_earnings <= 5`, sets `binary_risk=True`, `earnings_date`, caps conviction at 5, appends a dealbreaker. |
| Gap 2 (conviction) | `synthesis.py` | ACCUMULATE formula slope `* 10` → `* 12` (so weighted_score=0.7 → conviction=7). BUY cap `8` → `9` for non-speculative smallcaps. |
| Gap 3 (frontend) | `TickerAnalysisPage.tsx` | Stale pill now driven by `stale_warning` field (was hardcoded `> 24h`). Binary-risk badge shown next to action buttons. |
| Gap 3 (screener UI) | `ScreenerTable.tsx` | New "Earnings" column. Renders amber badge with date when `binary_risk=true`. |
| Tests | `tests/test_technical_data_quality.py` (new) | 17 regression + integration tests, all 79 (17 new + 62 existing) pass. |

## Success criteria

1. `POST /api/v1/ticker/AAPL/analyze` → `technical.weekly.ma_alignment != "N/A"` (was: always "N/A")
2. `verdict.narration.thesis_one_liner` is non-empty (was: always empty)
3. After `POST /api/v1/admin/refresh-data`, `data_age_hours < 12h` (was: always 56.4h on weekends)
4. `stale_warning` populated when data > threshold (was: never populated)
5. Screener shows `binary_risk: true` for imminent earnings (was: never)
6. ACCUMULATE w/ weighted_score=0.7 returns conviction=7-8 (was: 4-5)
7. All 79 tests pass; frontend type-checks; live API smoke confirmed

## Estimated effort

~9-10 days planned → ~6-7 hours actual in 11 commits (most of the
work was focused file changes, well-scoped by the spec).

## Out of scope (deferred)

DuckDB backfill for the `deep_analysis.py` path (uses DuckDB OHLCV,
not yfinance). Documented in PLAN.md as a separate concern.
