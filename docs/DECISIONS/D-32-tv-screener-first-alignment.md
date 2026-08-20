# D-32: TV Screener-First Alignment — DuckDB Optional, IndicatorCache Retired

**Status:** Accepted
**Date:** 2026-08-16

## Context

Architecture review (5 parallel audits) surfaced a misalignment between intent, code, and docs around the role of DuckDB and the indicator cache:

1. The project was intended to be **TradingView Screener-first** — live discovery/scoring with no OHLCV dependency (ADR-004) — not a traditional "fetch huge data overnight, precompute indicators" system.
2. Docs (ADR-001, ARCHITECTURE.md) read as if DuckDB were a primary store; code confirmed it is **not load-bearing**: charts, indicators, ticker analysis, regime, sector rotation, and Morning Brief all fetch live from TradingView / Yahoo Finance.
3. A DuckDB `indicator_values` table (939K rows) + `IndicatorCache` + `refresh_indicator_cache` Celery task (D-23) represented the **exact "precompute indicators" pattern** that was deliberately avoided — and the write path was broken (task called nonexistent methods).

## Decision

1. **DuckDB is optional and non-load-bearing.** It stores historical OHLCV for on-demand backtest/risk only. It is never on the discovery/screening/scoring/analysis path. If DuckDB data is missing or stale, all core features must continue to work (they already do — they never read it).
2. **Retire the indicator-cache precompute path (D-23).** Indicators are computed on-demand from live yfinance OHLCV via `data.py` (pandas-ta). Delete/stop the `refresh_indicator_cache` task and the `IndicatorCache` reads; leave any legacy rows inert and do not restore the write path.
3. **Fix the TV-first core first.** The highest-leverage fixes are the live-path bugs: `deep_analyze` include flags dropped, per-request `TVScreenEngine` defeating cache/rate-limiter, tradingview-screener 3.2.0 `where2` regression, Morning Brief verdict mapping, and the `/health/ready` + backtest table-name bugs.
4. **Docs reflect this stance.** ADR-001 and ARCHITECTURE.md updated to state TV-first + optional DuckDB explicitly.

## Consequences

- **Positive:** Architecture, code, and docs are aligned: "live TV-first smart system," not a batch ETL platform.
- **Positive:** Removing the broken indicator-cache job removes a failing task from the Celery schedule.
- **Positive:** Fixing the TV-first core improves real UX (screener results breadth, cache/rate-limit effectiveness, Morning Brief verdicts).
- **Risk:** Deep analysis (backtest/risk) may have stale/missing data if DuckDB is not populated — acceptable, as it is an optional on-demand feature; the UI should not block on its unavailability.
- **Risk:** Retiring D-23 means the `/api/v1/data/indicators` endpoints remain the only chart-indicator source — they already are; no frontend reads `indicator_values`.