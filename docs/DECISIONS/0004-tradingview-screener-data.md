# ADR-004: TradingView Screener for Market Data

**Status:** Accepted
**Date:** 2026-06-18

## Context
Need a free, reliable market data source covering equities, crypto, forex, commodities, and indices without paid API subscriptions.

## Decision
Use tradingview-screener Python library as the primary market data source with async chunked fetching, rate limiting, and retry logic.

## Consequences
- **Positive**: Free access to 5000+ symbols across multiple asset classes, no API key needed
- **Negative**: Unofficial API, no SLA, potential breaking changes
- **Mitigation**: Built-in retry logic with exponential backoff, data validation pipeline, Parquet caching
