# TV Engine — Orchestrates TV Screener discovery + local deep analysis
"""
Two-stage screening:
Stage 1: TV Server discovery (instant, 12K+ symbols)
Stage 2: Local deep analysis (on-demand for matched tickers)

Rate limited (25 req/min) and cached (60s TTL) to stay within TV free tier.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import pandas as pd

from backend.app.infrastructure.screener.tv_specialist import TVScreenerSpecialist, TVDiscoveryResult
from backend.app.infrastructure.screener.confluence_scorer import TVConfluenceScorer, ConfluenceScore
from backend.app.infrastructure.screener.tv_rate_limiter import TVRateLimiter
from backend.app.infrastructure.screener.tv_circuit_breaker import TVCircuitBreaker
from backend.app.infrastructure.screener.tv_cache import TVCache
from backend.app.infrastructure.screener.configs import ScreenConfig
from backend.app.core.logging import get_logger

log = get_logger("conflu.screener.tv_engine")


def _detect_probable_fund(item: dict) -> tuple[bool, str | None]:
    """Heuristic fund detection from TV data alone.

    ETFs/CEFs/ETNs often show as "Miscellaneous" sector with no EPS
    and no market cap in TV data. This is a lightweight check that
    flags probable funds at screener time (no yfinance call needed).
    The definitive check happens in ticker analysis (fundamentals.py)
    using yfinance quoteType/fundFamily/morningstar fields.
    """
    tv_row = item.get("tv_data", {})
    sector = (tv_row.get("sector") or "").strip()
    tv_eps = tv_row.get("earnings_per_share_diluted_ttm")
    tv_mcap = tv_row.get("market_cap_basic", 0)
    has_fund_data = not sector or sector == "Miscellaneous"
    has_no_eps = not tv_eps or tv_eps == 0 or tv_eps == "-"
    has_no_mcap = not tv_mcap or tv_mcap == 0
    if has_fund_data and has_no_eps and has_no_mcap:
        return True, (
            f"Miscellaneous sector with no EPS and no market cap — "
            f"likely an ETF/CEF/fund, not an individual equity"
        )
    return False, None


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
        # Circuit breaker: auto-disables speculative multi-screen fan-out
        # (P1.2 flag consumer) when upstream call volume exceeds 20/60s.
        self.circuit_breaker = TVCircuitBreaker(max_calls=20, window_seconds=60.0)
        self._refresh_tasks: set[asyncio.Task[None]] = set()
        self._inflight_refreshes: set[str] = set()
        self.log = get_logger("conflu.screener.tv_engine")

    async def discover(self, config: ScreenConfig, limit: int = 500) -> TVDiscoveryResult:
        """
        Stage 1: Run screen on TradingView server.
        Cached + rate limited + stale-while-revalidate.

        Cache policy:
        - fresh hit (< ttl): serve immediately
        - stale hit (ttl..stale_ttl): serve immediately AND schedule a
          background refresh — prefer stale-with-freshness-label over
          provider hammering
        - miss: rate-limited synchronous discovery; only non-empty results
          are cached (empty results are valid answers but never sticky).
        """
        cache_key = self.cache.make_key(config, limit)

        value, is_stale = self.cache.get_with_freshness(cache_key)
        if value is not None:
            if is_stale:
                self.log.info("stale_hit_refreshing", screen=config.name, key=cache_key)
                self._schedule_refresh(cache_key, config, limit)
            else:
                self.log.info("cache_hit", screen=config.name, key=cache_key)
            return value

        result = await self._rate_limited_discover(config)

        # Cache result only when non-empty (non-None AND non-empty DataFrame).
        # Empty discoveries must NOT be cached — they would be served as sticky
        # zero-match responses for 60s, masking transient upstream failures
        # (e.g. broken filter compilation returning 0 rows).
        if result.raw_data is not None and not result.raw_data.empty:
            self.cache.set(cache_key, result)
        else:
            self.log.info(
                "empty_discovery_not_cached",
                screen=config.name,
                matches=result.total_matches,
                key=cache_key,
            )

        self.log.info(
            "discover_complete",
            screen=config.name,
            matches=result.total_matches,
            ms=result.execution_ms,
        )
        return result

    async def _rate_limited_discover(self, config: ScreenConfig) -> TVDiscoveryResult:
        """Run one TV discovery under the rate limiter, recording the call."""
        async with self.rate_limiter:
            self.circuit_breaker.record_call()
            return await self.specialist.discover(config)

    def _schedule_refresh(self, cache_key: str, config: ScreenConfig, limit: int) -> None:
        """Schedule a background refresh for a stale cache entry (deduped)."""
        if cache_key in self._inflight_refreshes:
            return

        task: asyncio.Task[None] = asyncio.create_task(self._refresh(cache_key, config, limit))
        self._refresh_tasks.add(task)
        task.add_done_callback(self._refresh_tasks.discard)

    async def _refresh(self, cache_key: str, config: ScreenConfig, limit: int) -> None:
        """Background stale-while-revalidate refresh; never raises."""
        self._inflight_refreshes.add(cache_key)
        try:
            result = await self._rate_limited_discover(config)
            if result.raw_data is not None and not result.raw_data.empty:
                self.cache.set(cache_key, result)
                self.log.info("background_refresh_complete", screen=config.name, key=cache_key)
            else:
                # Keep serving the stale entry rather than replacing a good
                # cached state with an empty one.
                self.log.info(
                    "background_refresh_empty_kept_stale",
                    screen=config.name,
                    key=cache_key,
                    matches=result.total_matches,
                )
        except Exception as exc:  # noqa: BLE001 — background task must never propagate
            log.error("background_refresh_failed", screen=config.name, error=str(exc))
        finally:
            self._inflight_refreshes.discard(cache_key)

    async def discover_multi_tf(self, config: ScreenConfig) -> list[TVDiscoveryResult]:
        """Multi-timeframe discovery: run per-TF, return all results."""
        results = await self.specialist.discover_multi_tf(config)
        # Account each returned timeframe as one upstream call so the
        # circuit breaker sees true volume from multi-TF fan-out too.
        for _ in results:
            self.circuit_breaker.record_call()
        return results

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
        Complete Stage 1: Discover + Enrich + Score.
        Returns ranked tickers with confluence scores + elite signal enrichment.
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

        return await self._finalize_screen(config, result, start=start, limit=limit)

    async def _finalize_screen(
        self,
        config: ScreenConfig,
        result: TVDiscoveryResult,
        *,
        start: float,
        limit: int = 500,
    ) -> dict[str, Any]:
        """Shared post-discovery pipeline: elite enrichment + confluence scoring."""
        if result.raw_data is None:
            return {
                "screen_name": config.name,
                "total_matches": 0,
                "execution_ms": round((time.monotonic() - start) * 1000),
                "timeframe": config.timeframes[0] if config.timeframes else "1D",
                "results": [],
            }

        # ── Elite signal enrichment (post-TV, no OHLCV needed) ──
        from backend.app.infrastructure.screener.elite_signal import EliteSignalProcessor

        esp = EliteSignalProcessor()
        enrichments = esp.enrich(
            result.raw_data,
            direction=config.direction,
            regime=None,  # set by caller if known, or passed via config
        )

        scored = await self.score_discovery(result, direction=config.direction)
        timeframe = config.timeframes[0] if config.timeframes else "1D"

        # Attach enrichment data to each scored ticker
        for item in scored:
            sym = item["symbol"]
            e = enrichments.get(sym, {})
            item["elite"] = {
                "rs_rating": e.get("rs_rating", 50),
                "inst_quality": e.get("inst_quality", 50),
                "signal_conviction": e.get("signal_conviction", "low"),
                "wyckoff_phase": e.get("wyckoff_phase"),
                "factor_conflicts": e.get("factor_conflicts", []),
            }

            # ── Heuristic fund detection from TV data ──
            pf_flag, pf_reason = _detect_probable_fund(item)
            item["probable_fund"] = pf_flag
            item["probable_fund_reason"] = pf_reason

        return {
            "screen_name": config.name,
            "total_matches": result.total_matches,
            "execution_ms": round((time.monotonic() - start) * 1000),
            "timeframe": timeframe,
            "results": scored[:limit],
        }

    async def screen_batch(
        self, configs: list[ScreenConfig], limit: int = 500
    ) -> list[dict[str, Any] | Exception]:
        """Screen multiple templates for one discovery cycle.

        One-Snapshot-Multi-Screen path (P1.2), gated by:
        - feature flag ``settings.screen.snapshot_multi_screen`` (default OFF)
        - circuit breaker: open breaker ⇒ legacy per-template discovery

        The snapshot itself flows through the engine cache with
        stale-while-revalidate; per-template results are derived locally at
        zero upstream cost. Templates whose local masking fails closed fall
        back to legacy ``screen()`` individually.

        Response schema is IDENTICAL to
        ``await asyncio.gather(*[self.screen(c) ...], return_exceptions=True)``
        — per-item dicts, with Exceptions in place of failed screens.
        Additive-only mandate holds.
        """
        from backend.app.core.config import settings
        from backend.app.infrastructure.screener.snapshot_engine import (
            SnapshotMultiScreenEngine,
            build_base_config,
        )

        if not configs:
            return []

        async def _fallback_single(cfg: ScreenConfig) -> dict[str, Any] | Exception:
            try:
                return await self.screen(cfg, limit=limit)
            except Exception as exc:  # noqa: BLE001 — caller handles per-item failures
                return exc

        use_snapshot = (
            settings.screen.snapshot_multi_screen and not self.circuit_breaker.is_open()
        )
        if not use_snapshot:
            # Mirror legacy gather semantics: per-item exceptions, not raises.
            legacy = [_fallback_single(config) for config in configs]
            return list(await asyncio.gather(*legacy))

        start = time.monotonic()
        base_config = build_base_config(configs, size=settings.screen.snapshot_size)
        snapshot_engine = SnapshotMultiScreenEngine(
            self.specialist, size=settings.screen.snapshot_size
        )

        # Snapshot participates in the SWR cache like any discovery.
        cache_key = self.cache.make_key(base_config, settings.screen.snapshot_size)
        cached, is_stale = self.cache.get_with_freshness(cache_key)
        snapshot_df: pd.DataFrame | None = None
        if cached is not None and not is_stale:
            snapshot_df = getattr(cached, "raw_data", None)
            self.log.info("snapshot_cache_hit", key=cache_key)
        elif cached is not None and is_stale:
            snapshot_df = getattr(cached, "raw_data", None)
            self.log.info("snapshot_stale_hit_refreshing", key=cache_key)

        if snapshot_df is None or snapshot_df.empty:
            snapshot_df = await snapshot_engine.fetch_snapshot(configs)
            if snapshot_df is None or snapshot_df.empty:
                # Hard fallback: never serve silently-empty states.
                self.log.warning("snapshot_fetch_empty_falling_back_legacy")
                return list(await asyncio.gather(*[self.screen(c, limit=limit) for c in configs]))

            result = TVDiscoveryResult(
                screen_name=base_config.name,
                total_matches=len(snapshot_df),
                tickers=snapshot_df["ticker"].str.split(":").str[-1].unique().tolist()
                if "ticker" in snapshot_df.columns
                else [],
                execution_ms=round((time.monotonic() - start) * 1000),
                raw_data=snapshot_df,
                timeframe="1D",
            )
            self.cache.set(cache_key, result)

        local_results = snapshot_engine.discover_all_local(snapshot_df, configs)

        out: list[dict[str, Any] | Exception] = []
        for config in configs:
            local = local_results.get(config.name)
            if local is None:
                # Fail-closed template → legacy discovery just for this one.
                out.append(await _fallback_single(config))
                continue
            out.append(await self._finalize_screen(config, local, start=start, limit=limit))
        return out

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
            tf_scores: list[tuple[str, float, int, ConfluenceScore]] = []  # (tf, weight, raw_score, score_obj)
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

        # ── Elite signal enrichment on primary TF data ──
        from backend.app.infrastructure.screener.elite_signal import EliteSignalProcessor

        esp = EliteSignalProcessor()
        # Use the primary timeframe result for enrichment
        primary_tf = tfs[0] if tfs else "1D"
        primary_result = next((r for r in results if r.timeframe == primary_tf), results[0] if results else None)
        if primary_result and primary_result.raw_data is not None:
            enrichments = esp.enrich(
                primary_result.raw_data,
                direction=config.direction,
            )
            for item in scored:
                sym = item["symbol"]
                e = enrichments.get(sym, {})
                item["elite"] = {
                    "rs_rating": e.get("rs_rating", 50),
                    "inst_quality": e.get("inst_quality", 50),
                    "signal_conviction": e.get("signal_conviction", "low"),
                    "wyckoff_phase": e.get("wyckoff_phase"),
                    "factor_conflicts": e.get("factor_conflicts", []),
                }
                # ── Heuristic fund detection from TV data ──
                pf_flag, pf_reason = _detect_probable_fund(item)
                item["probable_fund"] = pf_flag
                item["probable_fund_reason"] = pf_reason

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
        include_backtest: bool = True,
        include_risk: bool = True,
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
        result = await orchestrator.analyze(
            symbol, timeframe, include_backtest=include_backtest, include_risk=include_risk
        )

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
            "circuit_breaker": self.circuit_breaker.stats(),
        }
