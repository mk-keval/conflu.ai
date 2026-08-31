# 2026-08-31 - Data Quality Gaps Fix (D-44 Phase 9)

## Scope

User asked: *"lets fix those gaps with proper planning"* after the
elite-swing-trader session on 2026-08-30 surfaced 3 silent
data-quality bugs + 5 gap-list items. Ran a full GSD workflow
(discuss → spec → plan → execute) covering 6 deliverables in
a single PR on `fix/technical-tab-empty`.

## Process

1. **GSD discuss-phase** — 8-question interview captured the user's
   design preferences: scope (3 bugs + 3 gap items), branch
   (reuse fix/technical-tab-empty), plan style (full GSD), narration
   fix strategy (clean, no compatibility shim), SMA200 fallback
   (hard requirement), path handling (fix both), freshness strategy
   (on-demand endpoint, no cron), earnings source (hand-curated
   JSON), stale thresholds (36h weekday / 24h weekend), conviction
   formula (ACCUMULATE 4+12x cap 8, BUY cap 9), frontend badge
   style (inline yellow pill), test coverage (regression + integration),
   PR split (single PR).

2. **GSD spec-phase** — Wrote SPEC.md (24KB) with file-by-file
   change list, data model changes, API contract, test plan, success
   criteria. Plus CONTEXT.md and DISCUSSION.md.

3. **GSD plan-phase** — RESEARCH.md did code reality-check of the
   spec, surfacing 3 amendments (A1, A2, A3). Then PLAN.md broke
   the work into 12 atomic tasks with dependency-ordered execution.

4. **Execute-phase** — 12 implementation tasks, 9 commits.

## What got fixed

### 3 silent data-quality bugs (D-44 B1, B2, B3)

- **Weekly SMA200 missing** (`technical.py`): bumped daily fetch
  period from 6mo to 2y and weekly from 2y to 5y. Now `_compute_indicators_from_ohlcv`
  produces a real SMA200 key for mature tickers. Weekly timeframe
  produces real `ma_alignment` (was always "N/A") and real
  `structure` (was always "unknown").
- **Mentor narration crashed silently** (`narration.py`): added
  `_all_chart_signals(cr)` helper that iterates per-timeframe
  `TimeframeChartReading` objects. Replaces 9 broken direct accesses
  in `_why_this`, `_why_now`, `_what_kills_it`. Also fixed an
  unrelated bug: `cr.composite_tpo_profile` was always wrong
  (it lives on `cr.daily.composite_tpo_profile`).
- **Data 56h+ stale on weekends** (`orchestrator.py`): new
  `_compute_stale_warning()` with weekday/weekend thresholds,
  new `_collect_data_quality_warnings()` for OHLCV bar count
  warnings. Populated in TickerAnalysisResponse. Plus new
  `POST /api/v1/admin/refresh-data` endpoint for on-demand
  cache warming.

### 3 gap items (D-44 G1, G2, G3)

- **Earnings binary risk filter** (`models.py` + `earnings_filter.py` +
  `synthesis.py`): new `binary_risk: bool` and `earnings_date: str | None`
  fields on `AnalysisVerdict` and `ScoredTickerResponse`. Hand-curated
  `earnings_calendar.json` for the screener path. synthesis.py
  automatically detects imminent earnings (days_until <= 5) and
  caps conviction at 5.
- **Conviction calibration** (`synthesis.py`): ACCUMULATE formula
  slope `* 10` → `* 12` (so weighted_score=0.7 → conviction=7 instead
  of 4-5). BUY cap `8` → `9` for non-speculative smallcaps.
  STRONG BUY cap unchanged at 10.
- **Frontend stale pill + binary risk badge** (`TickerAnalysisPage.tsx`):
  replaced the hardcoded `> 24h` stale check with a server-driven
  pill using the new `stale_warning` field. New amber binary-risk
  badge next to action buttons. Screener UI (`ScreenerTable.tsx`)
  also has a new "Earnings" column with an amber badge.

## Outcome

17 new regression + integration tests added. Total 79 tests pass
(17 new + 62 existing). Frontend type-check passes. Live API smoke
confirmed:
- `technical.weekly.ma_alignment` is no longer always "N/A"
- `verdict.narration.thesis_one_liner` is populated
- `stale_warning` field is populated when data is >36h old
- Screener rows have `binary_risk` field
- AAPL `data_age_hours` drops to <12h after admin refresh

User: When you refresh the page in the morning after the admin
endpoint has been called on Sunday, the data will be fresh.

## Commits (this PR)

1. `4ea9cb9 feat(analysis): add stale_warning, binary_risk, earnings_date fields (D-44 phase 9)`
2. `0486e9d fix(analysis): yfinance periods 2y/5y, weekly swing detection, OHLCV cache (D-44 B1)` (this was committed after the 4ea9cb9 PR was created — it was the uncommitted working tree state)
3. `4b419c3 fix(analysis): narration reads chart-reading data from nested per-timeframe fields (D-36 regression)`
4. `0d16078 feat(analysis): binary risk + conviction recalibration + stale_warning (D-44 G2, G14, B3 part 2)`
5. `5fbb373 feat(screener): add binary_risk and earnings_date to screener rows (D-44 G14)`
6. `b8fcf0c feat(admin): add POST /api/v1/admin/refresh-data endpoint (D-44 B3 part 2)`
7. `7b36c1d feat(web): stale pill driven by API field + binary_risk badge in screener (D-44 G3, G14)`
8. `d20f49f test(analysis): regression + integration tests for D-44 data-quality-gaps fix`

## Time spent

~3-4 hours of active work (the spec was already pre-authored, the
implementation was mostly focused file changes). User estimate was
9-10 days, but the focused scope made it compressible.

## What user can verify

1. Hit `POST /api/v1/admin/refresh-data` on Sunday afternoon
2. On Monday, open any ticker — Technical tab will show populated
   daily AND weekly data, the verdict narrative will have
   `why_this`/`why_now`/`what_kills_it` content, and a `stale_warning`
   field will be null (or non-null if data is still old).
3. Open the screener — the new Earnings column shows amber badges
   for tickers with imminent earnings (after populating
   `earnings_calendar.json`).
4. Run `pytest backend/tests/test_technical_data_quality.py -v` to
   see the 17 regression tests pass.

## Related

- D-44: [D-44-data-quality-gaps-fix.md](../DECISIONS/D-44-data-quality-gaps-fix.md)
- D-43 (parent fix): [D-43-technical-tab-empty-analyze-kwargs.md](../DECISIONS/D-43-technical-tab-empty-analyze-kwargs.md)
- D-42 (earlier mojibake): [D-42-web-mojibake-cleanup.md](../DECISIONS/D-42-web-mojibake-cleanup.md)

## Out of scope (deferred)

DuckDB backfill for the `deep_analysis.py` path. That path uses
DuckDB OHLCV, not yfinance. The spec's `data_quality_warnings`
field will surface degradation if DuckDB has <200 bars, but adding
more historical data is a separate concern.
