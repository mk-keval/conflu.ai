# D-36: Chart-Reading Instrumental Fixes — Populated Return Value + MTF Confluence + Structure-None Robustness

**Status:** Accepted
**Date:** 2026-08-28
**Branch:** feat/swing-parity-upgrade
**Evidence:** Docker-verified end-to-end (realistic populated TechnicalAnalysis objects through `_build_chart_reading_analysis`); 572 backend tests pass; lsp zero-error on all touched trees.

## Context

During swing-parity phase-1 (institutional chart reading), the chart-reading path had three defects that silently degraded the output a user would receive:

1. **Empty return value.** `_build_chart_reading_analysis()` returned a freshly-constructed `ChartReadingAnalysis()` instead of the populated object it had just built — so `daily/weekly/h4/h1`, `mtf_confluence`, and all chart-reading fields were discarded and every `TechnicalAnalysis.chart_reading` came back structurally empty even though the computation ran fine.
2. **MTF confluence never surfaced.** `mtf_confluence` was left as `None`, so downstream consumers (`synthesis._generate_trade_plan`) that read `mtf.get("conflicts")` / `mtf.get("entry_zones")` could not act on multi-timeframe confluence.
3. **Structure-`None` crash.** `mtf_confluence._analyze_daily_structure` did `"choch" in structure` where `structure` could legitimately be `None` (tickers with insufficient swing data) → `TypeError: argument of type 'NoneType' is not iterable` at runtime — a real production path.

## Decision

- `_build_chart_reading_analysis(..., timeframe_results=None)` now **returns the populated `chart_reading`** (all four timeframes + MTF). The `analyze()` call site (technical.py ~L569) passes the per-timeframe `results` dict in.
- New `_serialize_mtf_result(mtf)` helper converts an `MTFConfluenceResult` dataclass → plain JSON-safe dict (keys: `overall_bias`, `bull_score`, `bear_score`, `confidence`, `signals`, `conflicts`, `has_critical_conflict`, `entry_zones`, `invalidation_level`, `invalidation_reason`, `details`, `timestamp`; `signals` serialized as list-of-dicts) so it survives JSON and downstream `.get()` consumers.
- `mtf_confluence.py` `_analyze_daily_structure` normalizes `structure = chart["structure"] or "unknown"` — always a string, so `"choch" in structure` is safe. (Other `structure in (tuple)` checks were already None-safe.)

## Consequences

- **Positive:** Verified end-to-end in the container — `timeframes_analyzed=['daily','weekly','4h','1h']`, all populated, `mtf_confluence` non-None with `overall_bias='bullish'`, `entry_zones` populated, `signals` length 5, JSON serialization clean. Degenerate all-None structure no longer crashes (returns `neutral`).
- **Positive:** 572 backend tests pass; 121/121 pass across all chart-reading/technical/narration/models modules; lsp zero errors on technical.py, mtf_confluence.py, synthesis.py, models.py, orchestrator.py, narration.py. Remaining 2 model-test failures + 2 errors are pre-existing/environmental (config `.env` precedence, missing frontend `bands-cases.json` fixture), unrelated to chart reading.
- **Risk (environmental note):** `pytest` requires `-o asyncio_mode=auto` in this container (pyproject auto mode not picked up from mounted config) — not a code issue.
- **Risk (pre-existing, not fixed here):** `volume_profile.py` LSP shows pandas_ta `atr`/`rsi` typing false-positives; runtime is correct (covered by passing tests).

## Files Touched
- `backend/app/domain/ticker_analysis/technical.py` (return + `_serialize_mtf_result` + call site)
- `backend/app/domain/ticker_analysis/mtf_confluence.py` (structure-`None` normalization)
