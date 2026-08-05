# Session: TV Screener Verification & Doc Correction

**Date**: 2026-07-31
**Branch**: fix/elite-trader-gaps
**Type**: Investigation + documentation-only changes (no code modified)

## Context

Investigated what the `tradingview-screener` library actually provides vs what the app needs, to answer whether DuckDB/OHLCV can be replaced with direct TVScreener + Yahoo Finance calls. Findings revealed several stale/incorrect claims in `.claude/skills/tvscreener-specialist/SKILL.md` and `docs/DECISIONS/0004-tradingview-screener-data.md`. Corrected both after live-verifying against the installed library (v3.2.0) and the TradingView scanner API.

## Key Investigation Findings

- Library returns **one current snapshot row per symbol** — **no historical data** (maintainer-confirmed; use `tvdatafeed`/yfinance for history).
- DuckDB `ohlcv` is already TV-fed incrementally (current bar per timeframe per poll) — live charts/ticker analysis already bypass DuckDB via yfinance.
- **Live-verified** (2026-07-31, `scanner.tradingview.com/america/scan`): `OBV`, `supertrend`, `supertrend.up`, `supertrend.down` return `None` — unknown columns are silently accepted (HTTP 200). `EMA20`, `BB.upper`, `RSI`, `relative_volume_10d_calc` return real values.
- `q.set_property("interval", ...)` **is valid** in v3.2.0 (`set_property` sets `self.query[key]`); there is no `scan_interval` property — multi-timeframe is per-column via `|INTERVAL` pipe suffix (`col("RSI|1W")`, `col("close|240")`).
- Valid TV interval codes: `1,5,15,30,60,120,240,1W,1M` (no suffix = 1D). Config labels must be mapped (`"1m"→"1"`, `"1h"→"60"`, `"4h"→"240"`).
- Data delayed **900s (15 min)** unauthenticated; streaming with TradingView session cookies (`get_scanner_data(cookies=...)`, free account suffices).
- **No documented rate limit**; library has no retry/backoff (app-side in `scanner.py`); default row range `[0, 50]`, no auto-pagination.

## Files Changed (exactly 2)

- `.claude/skills/tvscreener-specialist/SKILL.md`
- `docs/DECISIONS/0004-tradingview-screener-data.md`

## Changes

### SKILL.md
- **Column registry**: removed `OBV` and `supertrend*` (live-verified `None`); added warning note on silently-accepted unknown columns + case-sensitivity.
- **Timeframe matrix**: documented valid interval codes + config label mapping; `set_property("interval")` confirmed valid; added per-column `|INTERVAL` multi-TF syntax.
- **Rate limits table**: replaced invented "~30 req/min" / "100 symbols max batch" with verified facts (no documented limit, 15-min delay unauth / streaming w/ cookies, app-side retry, `[0,50]` default range).
- **Limitations table**: corrected "single timeframe per query" (pipe suffix enables multi-TF in one query), 15-min delay w/ cookies workaround, silent `None` warning.

### ADR-004
- Corrected "Built-in retry logic" → retry/backoff/circuit-breaker is **app-side** (`scanner.py`); the library has none.
- Added consequences: **no historical data** (DuckDB accumulates only as fast as ingestion polls), 15-min delay unauth / streaming via cookies.
- Added mitigation: validate columns against TradingView field registry (unknown → silent `None`).

## Not Changed (deliberately)
- `docs/DECISIONS/index.md` — ADR-004 record updated in place, no new ADR.
- No code files touched (investigation constraint respected).
- Index formats table (S&P 500/Nasdaq 100/Russell 2000) — not independently verified this session.

## Follow-up Recommendation
- Verify `tv_specialist.py`'s interval label→code mapping for `"1m"/"5m"/"1h"/"4h"` (config defaults) — ensure they map to TV codes `1/5/60/240` before relying on multi-timeframe screening.
- Consider `get_scanner_data(cookies=...)` for real-time streaming if 15-min delay becomes a problem.
