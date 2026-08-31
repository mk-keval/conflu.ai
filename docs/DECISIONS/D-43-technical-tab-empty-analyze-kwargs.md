# D-43: Ticker Analysis Technical Tab Empty — `technical.analyze()` Missing OHLCV Kwargs

**Status:** Accepted
**Date:** 2026-08-30

## Context

The user reported the Technical tab on the Ticker Analysis page was completely
empty. Inspecting the live API (`POST /api/v1/ticker/AAPL/analyze`) showed
`technical: null` on every response, while all other modules (fundamental,
earnings, sentiment, risk) returned populated payloads. The frontend gates the
tab on `data.technical` being truthy (`TickerAnalysisPage.tsx:1576`):
`{activeTab === 'technical' && data.technical && <TechnicalDetail ... />}`, so
when the API returns `null`, the JSX short-circuits and renders an empty
`<div></div>`.

## Root Cause

The D-36 commit (`b6f45d3 feat(charts): chart-reading fixes + SMC/MTF/...`)
added pre-fetched OHLCV kwargs to the orchestrator's call into the technical
module — the design was: orchestrator pre-fetches daily/weekly/intraday OHLCV
once and passes them in so all 5 analysis modules can run in parallel
without each one re-hitting yfinance.

Concretely, `orchestrator.py:545-549` calls:
```python
_run_module, "technical", technical.analyze,
    tv_data, symbol=symbol, include_weekly=True,
    daily_ohlcv=daily_ohlcv, weekly_ohlcv=weekly_ohlcv,
    intraday_4h_ohlcv=intraday_4h_ohlcv, intraday_1h_ohlcv=intraday_1h_ohlcv
```

But `technical.py:516` defines:
```python
def analyze(data_fields, symbol=None, include_weekly=False, include_intraday=False)
```

The kwargs `daily_ohlcv`, `weekly_ohlcv`, `intraday_4h_ohlcv`, `intraday_1h_ohlcv`
are not in the signature, so every call raised
`TypeError: analyze() got an unexpected keyword argument 'daily_ohlcv'`.
The orchestrator's `_run_module` helper swallows the exception and returns
`None` (with a `technical_analysis_failed` log), so the request *succeeded*
with `technical=null` and nobody noticed.

The D-36 commit message claims "Docker-verified end-to-end; 572 backend tests
pass; 121/121 chart-reading modules", but the chart-reading module tests run
in isolation and don't go through the orchestrator's call path. The unit
suite passed; the integration path was broken silently. **Every Ticker
Analysis request since D-36 (Aug 29) returned `technical=null`.**

## Decision

Update `technical.analyze()`'s signature to accept the four pre-fetched OHLCV
kwargs. When supplied by the caller, the data is used as-is; when missing,
the function falls back to its existing yfinance fetch behavior. This:

1. **Fixes the immediate TypeError** so the technical module returns a real
   payload and the frontend's Technical tab populates.
2. **Honors the orchestrator's parallel pre-fetch** by skipping the
   duplicate yfinance fetch when data is already supplied (removes the
   wasted calls that D-36 inadvertently introduced).
3. **Preserves backward compat** — the kwargs default to `None` so any
   other caller (e.g. unit tests, future direct invocations) keeps working
   without supplying the OHLCV frames.

Also added a regression test
(`backend/tests/test_technical_orchestrator_integration.py`) with two
checks:
- A signature check that fails at import time if any of the four OHLCV
  kwargs disappears from `analyze()`.
- An end-to-end check that asserts the orchestrator passes those kwargs
  through and that the resulting response has `technical` populated.

Both tests verified the original D-36 bug reproduces if the signature fix
is reverted.

## Consequences

- Technical tab on `/ticker/<symbol>` now shows Daily and Weekly panels
  (TREND, MOMENTUM, VOLUME, VOLATILITY) plus findings list and chart
  reading (BOS, CHoCH, order blocks, fair value gaps, liquidity,
  breakouts) — restoring the pre-D-36 user experience.
- The duplicate yfinance call is gone: orchestrator pre-fetches once,
  the module reuses it. Saves 4 round-trips to Yahoo per request on
  default timeframes.
- D-36's "Docker-verified end-to-end" claim is no longer accurate; the
  D-43 docstring on the regression test references both D-36 and D-43
  for traceability.

## Follow-up (resolved in subsequent session)

Both items originally flagged as "out of scope" in this D-43 record were
addressed in the same feature branch on 2026-08-30:

- `â–²` / `â–¼` / `â—†` mojibake on `TickerAnalysisPage.tsx:1108`
  (sector flow arrows) — the corruption was a CP1252 round-trip with a
  single-byte bit-flip on the DOWN-arrow's middle byte (0x96 → 0x93)
  that ftfy could not reverse. Hand-decoded to original intent:
  `▲` (U+25B2) / `▼` (U+25BC) / `◆` (U+25C6).
- Pre-existing pandas_ta / NAType LSP warnings on
  `backend/app/domain/ticker_analysis/technical.py` — added
  `# type: ignore[attr-defined]` for the pandas_ta dispatcher entry
  points (runtime-verified, type stubs are stale), added explicit
  `np.ndarray`/`float` annotations to narrow NAType warnings in
  `_detect_swings` and the MA-stack comparison, and made the
  `volume_profile.compute_professional_tpo` consumer handle both
  return shapes (single object vs. tuple) safely.
