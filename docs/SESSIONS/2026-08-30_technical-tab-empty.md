# 2026-08-30 — Ticker Analysis Technical Tab Empty (D-43)

## Summary

Fixed the empty Technical tab on `/ticker/<symbol>`. The Ticker Analysis API
was returning `technical: null` on every request because the orchestrator's
call into the technical module passed kwargs (`daily_ohlcv`, `weekly_ohlcv`,
`intraday_4h_ohlcv`, `intraday_1h_ohlcv`) that the module's signature didn't
accept. The orchestrator's per-module runner swallowed the TypeError, so the
request "succeeded" with an empty payload. This had been broken since the
D-36 commit (Aug 29) — the D-36 "Docker-verified end-to-end" claim was a
false positive because the chart-reading unit tests don't exercise the
orchestrator's call path.

## Reproduction

1. `GET /api/v1/ticker/AAPL/analyze` (POST with body) returned
   `technical: null` while every other module populated.
2. Browser: navigate to `/ticker/AAPL`, click the Technical tab — empty
   `<div></div>` rendered because the JSX gate is
   `{activeTab === 'technical' && data.technical && <TechnicalDetail ... />}`.
3. Docker logs showed the error:
   `{"event": "technical_analysis_failed", "exception": "TypeError: analyze() got an unexpected keyword argument 'daily_ohlcv'"}`

## Root Cause

`backend/app/domain/ticker_analysis/orchestrator.py:545-549` (added in
D-36) passes four OHLCV kwargs to `technical.analyze` so all five analysis
modules can run in parallel without each one re-fetching from yfinance. But
`backend/app/domain/ticker_analysis/technical.py:516` defines the signature
as `(data_fields, symbol, include_weekly, include_intraday)` — those four
OHLCV kwargs are not present. Every call raised TypeError; the
`_run_module` helper at `orchestrator.py:525-535` catches the exception
silently and returns `None`, so `tech` in the orchestrator becomes `None`,
and `technical_payload = tech_daily` (line 665) is also `None`. The
`TickerAnalysisResponse.technical` field is therefore `None`, and the
frontend's gating JSX renders nothing.

## Fix

Updated `technical.analyze` to accept the four OHLCV kwargs (defaulting to
`None` for backward compat). When supplied, the data is used as-is; when
missing, the existing yfinance fetch behavior is preserved. Also removed
two redundant yfinance fetch blocks at the bottom of the function
(they clobbered caller-supplied data with a re-fetch — same root cause as
the D-36 signature gap, just a different layer).

## Verification

- `docker logs conflu-api --since 5m` after fix: no
  `technical_analysis_failed` events.
- `GET /api/v1/ticker/AAPL/analyze`: `technical` is now a dict with
  `daily` and `weekly` keys, both populated with full payload
  (score, ma_alignment, rsi, adx, atr_pct, structure, pullback_quality,
  findings, chart_reading).
- Playwright (`http://localhost:5173/ticker/AAPL`, click Technical tab):
  rendered 2680 chars of content (was 0); shows "Multi-Timeframe Analysis"
  header, score +0.50, Daily + Weekly panels with TREND, MOMENTUM, VOLUME,
  VOLATILITY sections, findings list, "How does this analysis work?" link.
- New regression test `test_technical_orchestrator_integration.py`:
  2 passed (`signature check + end-to-end orchestrator test`).
  Verified the signature test FAILS on the pre-fix code with
  `AssertionError: technical.analyze() is missing kwarg 'daily_ohlcv'...`.

## Out of Scope (separate issues observed)

- `frontend/src/components/ticker-analysis/TickerAnalysisPage.tsx:1108` has
  pre-existing `â–²` / `â–¼` / `â—†` mojibake (sector flow arrows).
  Different corruption pattern from D-42; ftfy did not repair it. Not
  blocking the user's "technical tab empty" report, but worth a separate
  fix.
- `backend/app/domain/ticker_analysis/technical.py` has pre-existing LSP
  warnings about `pandas_ta` API mismatches. Not introduced by this fix.

## Related

- [D-43: Technical tab empty — `analyze()` missing OHLCV kwargs](../DECISIONS/D-43-technical-tab-empty-analyze-kwargs.md)
- Branch: `fix/technical-tab-empty`
- Parent commit (root cause): `b6f45d3 feat(charts): chart-reading fixes + SMC/MTF/structure/volume engine (D-36)`
