# ADR-004: TradingView Screener for Market Data

**Status:** Accepted
**Date:** 2026-06-18

## Context
Need a free, reliable market data source covering equities, crypto, forex, commodities, and indices without paid API subscriptions.

## Decision
Use tradingview-screener Python library as the primary market data source with async chunked fetching, rate limiting, and retry logic.

## Consequences
- **Positive**: Free access to 5000+ symbols across multiple asset classes, no API key needed
- **Positive**: Discovery/screening is fast (<2s for 12K+ symbols) and supports per-column multi-timeframe via `|INTERVAL` suffixes (v3.2+)
- **Negative**: Unofficial API, no SLA, potential breaking changes
- **Negative**: **No historical data** — the scanner returns one current snapshot per symbol. DuckDB history accumulates only as fast as ingestion polls (1 bar per timeframe per cycle), so deep historical analysis must come from yfinance/tvdatafeed
- **Negative**: Data is **delayed ~15 min (900s)** unauthenticated; streaming real-time requires TradingView session cookies (free account sufficient) via `get_scanner_data(cookies=...)`
- **Mitigation**: Retry/backoff/circuit-breaker is implemented **app-side** in `scanner.py` (the library itself has none), plus data validation pipeline and Parquet caching
- **Mitigation**: Unknown columns are silently accepted and return `None` (HTTP 200) — validate requested columns against the TradingView field registry before relying on values (see `.claude/skills/tvscreener-specialist/SKILL.md`)
