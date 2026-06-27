# TV Engine — Orchestrates TV Screener discovery + local deep analysis
"""
Two-stage screening:
Stage 1: TV Server discovery (instant, 12K+ symbols)
Stage 2: Local deep analysis (on-demand for matched tickers)

Rate limited (25 req/min) and cached (60s TTL) to stay within TV free tier.
"""

from __future__ import annotations

import time
from typing import Any

from backend.app.infrastructure.screener.tv_specialist import TVScreenerSpecialist, TVDiscoveryResult
from backend.app.infrastructure.screener.confluence_scorer import TVConfluenceScorer, ConfluenceScore
from backend.app.infrastructure.screener.tv_rate_limiter import TVRateLimiter
from backend.app.infrastructure.screener.tv_cache import TVCache
from backend.app.infrastructure.screener.configs import ScreenConfig
from backend.app.core.logging import get_logger

log = get_logger("conflu.screener.tv_engine")


class TVScreenEngine:
    """
    Two-stage screening engine:
    1. TV Discovery (instant, server-side — rate limited + cached)
    2. Confluence Scoring (from TV data only)
    3. Deep Analysis (on-demand, local OHLCV + backtest + risk)
    """

    def __init__(self) -> None:
        self.specialist = TVScreenerSpecialist()
        self.scorer = TVConfluenceScorer()
        self.rate_limiter = TVRateLimiter(max_rate=25, interval=60.0, burst=5)
        self.cache = TVCache(ttl=60.0, maxsize=50)
        self.log = get_logger("conflu.screener.tv_engine")

    async def discover(self, config: ScreenConfig, limit: int = 500) -> TVDiscoveryResult:
        """
        Stage 1: Run screen on TradingView server.
        Cached + rate limited.
        """
        cache_key = self.cache.make_key(config, limit)

        # Check cache first
        cached = self.cache.get(cache_key)
        if cached is not None:
            self.log.info("cache_hit", screen=config.name, key=cache_key)
            return cached

        # Rate limit + discover
        async with self.rate_limiter:
            result = await self.specialist.discover(config)

        # Cache result if non-empty
        if result.raw_data is not None:
            self.cache.set(cache_key, result)

        self.log.info(
            "discover_complete",
            screen=config.name,
            matches=result.total_matches,
            ms=result.execution_ms,
        )
        return result

    async def discover_multi_tf(self, config: ScreenConfig) -> list[TVDiscoveryResult]:
        """Multi-timeframe discovery: run per-TF, return all results."""
        return await self.specialist.discover_multi_tf(config)

    async def score_discovery(self, result: TVDiscoveryResult) -> list[dict]:
        """
        Score all discovered tickers using TV Confluence Scorer.
        Returns list of scored tickers sorted by confluence (desc).
        """
        if result.raw_data is None:
            return []

        scored: list[dict] = []
        for _, row in result.raw_data.iterrows():
            ticker = row["ticker"].split(":")[-1]
            if ticker not in result.tickers:
                continue

            score = self.scorer.score(row)
            scored.append({
                "symbol": ticker,
                "tv_data": row.to_dict(),
                "confluence": score,
            })

        scored.sort(key=lambda x: x["confluence"].total, reverse=True)
        return scored

    async def screen(self, config: ScreenConfig, limit: int = 500) -> dict[str, Any]:
        """
        Complete Stage 1: Discover + Score.
        Returns ranked tickers with confluence scores from TV data ONLY.
        No OHLCV, no database, no backtest.
        """
        start = time.monotonic()

        result = await self.discover(config, limit=limit)
        if result.raw_data is None:
            return {
                "screen_name": config.name,
                "total_matches": 0,
                "execution_ms": round((time.monotonic() - start) * 1000),
                "timeframe": config.timeframes[0] if config.timeframes else "1D",
                "results": [],
            }

        scored = await self.score_discovery(result)
        timeframe = config.timeframes[0] if config.timeframes else "1D"

        return {
            "screen_name": config.name,
            "total_matches": result.total_matches,
            "execution_ms": round((time.monotonic() - start) * 1000),
            "timeframe": timeframe,
            "results": scored[:limit],
        }

    async def screen_multi_tf(self, config: ScreenConfig) -> dict[str, Any]:
        """
        Multi-timeframe screen: run per-TF, intersect tickers, score.
        """
        start = time.monotonic()

        results = await self.specialist.discover_multi_tf(config)

        if not results:
            return {"screen_name": config.name, "total_matches": 0, "results": []}

        intersected = set.intersection(*[set(r.tickers) for r in results])
        if not intersected:
            return {"screen_name": config.name, "total_matches": 0, "results": []}

        # Combine raw data from all timeframes for intersected tickers
        combined_rows = []
        for r in results:
            if r.raw_data is not None:
                for _, row in r.raw_data.iterrows():
                    ticker = row["ticker"].split(":")[-1]
                    if ticker in intersected:
                        combined_rows.append(row)

        if not combined_rows:
            return {"screen_name": config.name, "total_matches": 0, "results": []}

        import pandas as pd
        combined_df = pd.DataFrame(combined_rows)

        scored = []
        for _, row in combined_df.iterrows():
            ticker = row["ticker"].split(":")[-1]
            score = self.scorer.score(row)
            scored.append({
                "symbol": ticker,
                "tv_data": row.to_dict(),
                "confluence": score,
            })

        scored.sort(key=lambda x: x["confluence"].total, reverse=True)

        return {
            "screen_name": config.name,
            "total_matches": len(intersected),
            "execution_ms": round((time.monotonic() - start) * 1000),
            "timeframes": [r.timeframe for r in results],
            "results": scored,
        }

    async def deep_analyze(self, symbol: str, timeframe: str = "1D") -> dict[str, Any]:
        """
        Stage 3: On-demand deep analysis for a single ticker.
        Fetches OHLCV, computes indicators, runs backtest, risk.
        """
        from backend.app.infrastructure.analysis.deep_analysis import DeepAnalysisOrchestrator

        orchestrator = DeepAnalysisOrchestrator()
        result = await orchestrator.analyze(symbol, timeframe)

        return {
            "symbol": result.symbol,
            "timeframe": result.timeframe,
            "timestamp": result.timestamp.isoformat(),
            "confluence_score": result.confluence_score,
            "entry": result.entry,
            "stop_loss": result.stop_loss,
            "targets": result.targets,
            "backtest": result.backtest,
            "risk": result.risk,
        }

    def cache_stats(self) -> dict[str, Any]:
        """Return cache statistics for monitoring."""
        return self.cache.stats()

    def rate_limiter_stats(self) -> dict[str, Any]:
        """Return rate limiter statistics."""
        return {
            "tokens": round(self.rate_limiter.tokens, 1),
            "total_blocked": self.rate_limiter.total_blocked,
        }
