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

    async def score_discovery(self, result: TVDiscoveryResult, direction: str = "long") -> list[dict]:
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

            score = self.scorer.score(row, direction=direction)
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

        scored = await self.score_discovery(result, direction=config.direction)
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
        Multi-timeframe screen: run per-TF, weight scores by TF, aggregate.

        Replaces strict intersection (all-or-nothing) with weighted stacking
        so a ticker that matches 2 of 3 timeframes still gets partial credit.
        Each timeframe contributes its confluence score * TF weight to the total.
        """
        from dataclasses import replace

        start = time.monotonic()

        results = await self.specialist.discover_multi_tf(config)

        if not results:
            return {"screen_name": config.name, "total_matches": 0, "results": []}

        # ── TF weight map ──
        # Longer timeframes carry more weight (trend confirmation > noise).
        # Normalized so weights always sum to 1.0 regardless of which TFs present.
        TF_WEIGHTS = {"1D": 0.50, "4h": 0.25, "1W": 0.25, "2h": 0.15, "30m": 0.10}

        tfs = [r.timeframe for r in results]
        raw_weights = {tf: TF_WEIGHTS.get(tf, 1.0 / len(tfs)) for tf in tfs}
        total = sum(raw_weights.values())
        weights = {tf: w / total for tf, w in raw_weights.items()}
        tf_map = {r.timeframe: r for r in results}

        # ── Collect unique tickers across ALL timeframes ──
        all_tickers: set[str] = set()
        for r in results:
            all_tickers.update(r.tickers)

        if not all_tickers:
            return {"screen_name": config.name, "total_matches": 0, "results": []}

        import pandas as pd

        scored: list[dict] = []

        for ticker in all_tickers:
            tf_scores: list[tuple[str, float, int, object]] = []  # (tf, weight, raw_score, score_obj)
            primary_row: pd.Series | None = None

            for tf in tfs:
                r = tf_map[tf]
                if ticker in r.tickers and r.raw_data is not None:
                    rows = r.raw_data[r.raw_data["ticker"].str.split(":").str[-1] == ticker]
                    if not rows.empty:
                        row = rows.iloc[0]
                        score = self.scorer.score(row, direction=config.direction)
                        tf_scores.append((tf, weights[tf], score.total, score))
                        if primary_row is None:
                            primary_row = row

            if not tf_scores or primary_row is None:
                continue

            # Weighted aggregate score
            weighted_total = int(round(sum(w * s for _, w, s, _ in tf_scores)))

            # Skip tickers below minimum threshold
            if weighted_total < 30:
                continue

            # Use primary TF (first matched) for entry/stop/targets/breakdown
            primary_score = tf_scores[0][3]
            combined_score = replace(
                primary_score,
                total=weighted_total,
                rating=self.scorer._rating(weighted_total),
            )

            # Build per-TF breakdown for transparency
            mtf_breakdown_raw = []
            for tf in tfs:
                r = tf_map[tf]
                matched = ticker in r.tickers
                matched_info = {"weight": round(weights[tf], 2), "matched": False, "score": 0}
                for _tf, _w, _s, _sc in tf_scores:
                    if _tf == tf:
                        matched_info = {"weight": round(weights[tf], 2), "matched": True, "score": _s}
                        break
                mtf_breakdown_raw.append({
                    "timeframe": tf,
                    **matched_info,
                })

            scored.append({
                "symbol": ticker,
                "tv_data": primary_row.to_dict(),
                "confluence": combined_score,
                "mtf_breakdown": mtf_breakdown_raw,
            })

        scored.sort(key=lambda x: x["confluence"].total, reverse=True)

        return {
            "screen_name": config.name,
            "total_matches": len(scored),
            "execution_ms": round((time.monotonic() - start) * 1000),
            "timeframes": tfs,
            "results": scored,
        }

    async def deep_analyze(
        self,
        symbol: str,
        timeframe: str = "1D",
        tv_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Stage 3: On-demand deep analysis for a single ticker.
        Fetches OHLCV, computes indicators, runs backtest, risk.
        Falls back to TV-screener data when OHLCV is unavailable.
        """
        from backend.app.infrastructure.analysis.deep_analysis import DeepAnalysisOrchestrator
        from backend.app.infrastructure.screener.confluence_scorer import TVConfluenceScorer
        import pandas as pd

        orchestrator = DeepAnalysisOrchestrator()
        result = await orchestrator.analyze(symbol, timeframe)

        has_ohlcv = result.ohlcv is not None and not result.ohlcv.empty if hasattr(result, 'ohlcv') else False

        # If OHLCV analysis returned zeros and TV data is available,
        # fall back to the TV confluence scorer (which only needs TV columns).
        if not has_ohlcv and tv_data is not None:
            self.log.info("deep_analysis_ohlcv_missing", symbol=symbol, fallback="tv_data")
            tv_row = pd.Series(tv_data)
            score = self.scorer.score(tv_row)
            response = {
                "symbol": result.symbol,
                "timeframe": result.timeframe,
                "timestamp": result.timestamp.isoformat() if hasattr(result.timestamp, 'isoformat') else str(result.timestamp),
                "confluence_score": result.confluence_score,
                "entry": result.entry,
                "stop_loss": result.stop_loss,
                "targets": result.targets,
                "backtest": result.backtest,
                "risk": result.risk,
                "has_ohlcv": False,
                "tv_fallback": {
                    "confluence_score": score.total,
                    "breakdown": score.breakdown,
                    "entry": score.entry,
                    "stop_loss": score.stop_loss,
                    "targets": score.targets,
                    "risk_reward": score.risk_reward,
                    "rating": score.rating,
                },
            }
            # Override zeros with TV-based values when OHLCV has nothing
            if result.confluence_score == 0 and result.entry == 0:
                response["entry"] = score.entry
                response["stop_loss"] = score.stop_loss
                response["targets"] = score.targets
                response["confluence_score"] = float(score.total)
            return response

        return {
            "symbol": result.symbol,
            "timeframe": result.timeframe,
            "timestamp": result.timestamp.isoformat() if hasattr(result.timestamp, 'isoformat') else str(result.timestamp),
            "confluence_score": result.confluence_score,
            "entry": result.entry,
            "stop_loss": result.stop_loss,
            "targets": result.targets,
            "backtest": result.backtest,
            "risk": result.risk,
            "has_ohlcv": has_ohlcv,
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
