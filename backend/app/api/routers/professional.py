"""Professional Mode API router — simplified workflow endpoints for working professionals.

Endpoints:
- GET  /professional/morning-brief         — Daily morning brief
- GET  /professional/verdict/{symbol}       — One-click simplified verdict
- POST /professional/watchlist/analyze     — Batch watchlist analysis
- GET  /professional/education/{metric}    — Plain-English metric explanation
- GET  /professional/position-size         — Position size calculator
- GET  /professional/alerts/preferences    — Get alert preferences
- PUT  /professional/alerts/preferences    — Update alert preferences
- GET  /professional/alerts                — Recent in-app alerts
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from backend.app.api.schemas import ApiResponse, MetaInfo
from backend.app.core.logging import get_logger
from backend.app.infrastructure.professional.alert_service import AlertService
from backend.app.infrastructure.professional.education import EducationService
from backend.app.infrastructure.professional.models import (
    AlertPreferences,
    EducationRequest,
    EducationResponse,
    MorningBriefRequest,
    MorningBriefResponse,
    PositionSizeRequest,
    PositionSizeResponse,
    SimplifiedVerdictResponse,
    WatchlistAnalyzeRequest,
    WatchlistAnalyzeResponse,
    WatchlistItemResponse,
    WatchlistRefreshResponse,
    WatchlistTickersUpdate,
)
from backend.app.infrastructure.professional.morning_brief import MorningBriefService
from backend.app.infrastructure.professional.position_sizer import PositionSizer
from backend.app.infrastructure.professional.watchlist_service import (
    WatchlistService,
    get_watchlist_service,
)

log = get_logger("conflu.api.professional")

router = APIRouter(prefix="/professional", tags=["professional-mode"])

# ── Singleton service instances ──────────────────────────────────────
_education_service: EducationService | None = None
_alert_service: AlertService | None = None
_position_sizer: PositionSizer | None = None
_morning_brief_service: MorningBriefService | None = None


def _get_education_service() -> EducationService:
    global _education_service
    if _education_service is None:
        _education_service = EducationService()
    return _education_service


def _get_alert_service() -> AlertService:
    global _alert_service
    if _alert_service is None:
        _alert_service = AlertService()
    return _alert_service


def _get_position_sizer() -> PositionSizer:
    global _position_sizer
    if _position_sizer is None:
        _position_sizer = PositionSizer()
    return _position_sizer


def _get_morning_brief_service() -> MorningBriefService:
    global _morning_brief_service
    if _morning_brief_service is None:
        _morning_brief_service = MorningBriefService()
    return _morning_brief_service


# ═══════════════════════════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════════════════════════


@router.get("/morning-brief", response_model=ApiResponse[MorningBriefResponse])
async def get_morning_brief(
    regime: str | None = Query(None, description="Regime override (auto-detect if null)"),
) -> ApiResponse[MorningBriefResponse]:
    """Generate the daily morning brief.

    Returns regime badge, market internals, sector rotation, and
    top 9 tickers (3 per regime-matched screen) with pre-market quotes.
    """
    start = time.monotonic()
    log.info("morning_brief_requested", regime_override=regime)

    try:
        service = _get_morning_brief_service()
        brief = await service.generate_morning_brief(regime_override=regime)
        duration = (time.monotonic() - start) * 1000
        return ApiResponse(
            data=brief,
            meta=MetaInfo(
                request_id="",
                duration_ms=round(duration, 1),
                timestamp=datetime.now(UTC).isoformat(),
            ),
        )
    except Exception as e:
        log.exception("morning_brief_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Morning brief generation failed: {str(e)}")


@router.get("/verdict/{symbol}", response_model=ApiResponse[SimplifiedVerdictResponse])
async def get_simplified_verdict(symbol: str) -> ApiResponse[SimplifiedVerdictResponse]:
    """Get a one-click simplified verdict for a single ticker.

    Calls TickerAnalysisService.analyze() internally and extracts
    the essential info a working professional needs to make a decision.
    """
    start = time.monotonic()
    log.info("simplified_verdict_requested", symbol=symbol.upper())

    try:
        from backend.app.domain.ticker_analysis.models import TickerAnalysisRequest
        from backend.app.domain.ticker_analysis.orchestrator import TickerAnalysisService

        engine = TickerAnalysisService()
        result = await engine.analyze_async(TickerAnalysisRequest(symbol=symbol.upper()))

        # Extract position size context
        pos_size: dict[str, Any] | None = None
        if result.risk and result.price:
            pos_size = {
                "suggested_position_pct": result.risk.suggested_position_size_pct,
                "stop_pct": result.risk.suggested_stop_pct,
            }

        verdict = SimplifiedVerdictResponse(
            symbol=result.symbol,
            action=result.verdict.action if result.verdict else "N/A",
            conviction=result.verdict.conviction if result.verdict else 1,
            verdict_summary=result.verdict.thesis if result.verdict else "",
            key_metrics={
                "price": result.price,
                "change_pct": result.change_pct,
                "sector": result.sector,
                "rsi": result.technical.rsi if result.technical else None,
                "atr_pct": result.technical.atr_pct if result.technical else None,
            },
            entry_zone=(
                f"{result.verdict.entry_zone_low:.2f} - {result.verdict.entry_zone_high:.2f}"
                if result.verdict and result.verdict.entry_zone_low and result.verdict.entry_zone_high
                else "N/A"
            ),
            stop_loss=result.verdict.stop_loss if result.verdict and result.verdict.stop_loss is not None else 0.0,
            targets=result.verdict.targets if result.verdict else [],
            position_size=pos_size,
            max_hold_days=result.verdict.trade_plan.max_hold_days
                if result.verdict and result.verdict.trade_plan and result.verdict.trade_plan.max_hold_days
                else None,
            education=[],
        )

        duration = (time.monotonic() - start) * 1000
        return ApiResponse(
            data=verdict,
            meta=MetaInfo(
                request_id="",
                duration_ms=round(duration, 1),
                timestamp=datetime.now(UTC).isoformat(),
            ),
        )
    except Exception as e:
        log.exception("simplified_verdict_failed", symbol=symbol, error=str(e))
        raise HTTPException(status_code=500, detail=f"Verdict failed: {str(e)}")


@router.post("/watchlist/analyze", response_model=ApiResponse[WatchlistAnalyzeResponse])
async def analyze_watchlist(
    request: WatchlistAnalyzeRequest,
) -> ApiResponse[WatchlistAnalyzeResponse]:
    """Batch-analyze a watchlist of tickers in parallel.

    For each symbol, calls the simplified verdict endpoint and returns
    a summary verdict + position size.
    """
    start = time.monotonic()
    log.info("watchlist_analyze_requested", symbols=request.symbols)

    try:
        from backend.app.domain.ticker_analysis.models import TickerAnalysisRequest
        from backend.app.domain.ticker_analysis.orchestrator import TickerAnalysisService

        engine = TickerAnalysisService()
        items: list[WatchlistItemResponse] = []

        for sym in request.symbols:
            try:
                result = await engine.analyze_async(TickerAnalysisRequest(symbol=sym.upper()))
                pos_size_dict = None
                if result.risk and result.price:
                    pos_size_dict = {
                        "suggested_pct": result.risk.suggested_position_size_pct,
                        "stop_pct": result.risk.suggested_stop_pct,
                    }
                items.append(
                    WatchlistItemResponse(
                        symbol=sym.upper(),
                        verdict=result.verdict.action if result.verdict else "N/A",
                        conviction=result.verdict.conviction if result.verdict else 1,
                        position_size=pos_size_dict,
                        # P1.5 earnings-proximity chip (data already analyzed).
                        days_to_earnings=(
                            result.earnings.days_until_earnings
                            if result.earnings is not None
                            else None
                        ),
                    )
                )
            except Exception as e:
                log.warning("watchlist_item_failed", symbol=sym, error=str(e))
                items.append(
                    WatchlistItemResponse(
                        symbol=sym.upper(),
                        verdict="ERROR",
                        conviction=0,
                        position_size=None,
                    )
                )

        duration = (time.monotonic() - start) * 1000
        return ApiResponse(
            data=WatchlistAnalyzeResponse(items=items),
            meta=MetaInfo(
                request_id="",
                duration_ms=round(duration, 1),
                timestamp=datetime.now(UTC).isoformat(),
            ),
        )
    except Exception as e:
        log.exception("watchlist_analyze_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Watchlist analysis failed: {str(e)}")


# ── D-49: Persistent watchlist + click-to-update ─────────────────────


@router.get("/watchlist/persistent", response_model=ApiResponse[dict])
async def get_persistent_watchlist() -> ApiResponse[dict]:
    """Get the current persistent watchlist + last-known verdicts.

    Returns:
        {symbols: [...], last_verdicts: {symbol: {action, conviction, recorded_at}}, last_refresh: iso}
    """
    svc = get_watchlist_service()
    return ApiResponse(
        data={
            "symbols": svc.get_watchlist(),
            "last_verdicts": svc.get_all_last_verdicts(),
            "last_refresh": svc.get_last_refresh_time(),
        },
        meta=MetaInfo(
            request_id="",
            duration_ms=0,
            timestamp=datetime.now(UTC).isoformat(),
        ),
    )


@router.post("/watchlist/persistent", response_model=ApiResponse[dict])
async def add_to_persistent_watchlist(
    request: WatchlistTickersUpdate,
) -> ApiResponse[dict]:
    """Add tickers to the persistent watchlist.

    Body: {symbols: ["AAPL", "NVDA", ...]}
    Returns: {symbols: [...]}  — full watchlist after.
    """
    svc = get_watchlist_service()
    symbols = svc.add_tickers(request.symbols)
    return ApiResponse(
        data={"symbols": symbols},
        meta=MetaInfo(
            request_id="",
            duration_ms=0,
            timestamp=datetime.now(UTC).isoformat(),
        ),
    )


@router.delete("/watchlist/persistent/{symbol}", response_model=ApiResponse[dict])
async def remove_from_persistent_watchlist(symbol: str) -> ApiResponse[dict]:
    """Remove a ticker from the persistent watchlist."""
    svc = get_watchlist_service()
    symbols = svc.remove_ticker(symbol)
    return ApiResponse(
        data={"symbols": symbols},
        meta=MetaInfo(
            request_id="",
            duration_ms=0,
            timestamp=datetime.now(UTC).isoformat(),
        ),
    )


@router.post("/watchlist/persistent/refresh", response_model=ApiResponse[WatchlistRefreshResponse])
async def refresh_persistent_watchlist() -> ApiResponse[WatchlistRefreshResponse]:
    """Click-to-update: re-analyze all watchlist tickers, log verdict changes.

    Side effects:
      - records the new verdict as the last-known for each symbol
      - returns a list of verdict_changes (action or conviction moved by >=2)
      - the user sees the changes in the response, so they know to investigate
    """
    from concurrent.futures import ThreadPoolExecutor
    from backend.app.domain.ticker_analysis.models import TickerAnalysisRequest
    from backend.app.domain.ticker_analysis.orchestrator import TickerAnalysisService

    start = time.monotonic()
    svc = get_watchlist_service()
    symbols = svc.get_watchlist()
    if not symbols:
        raise HTTPException(status_code=400, detail="Watchlist is empty — add tickers first")

    engine = TickerAnalysisService()

    def _analyze_sync(symbol: str) -> tuple[str, Any | None, str | None]:
        """Run a single ticker analysis synchronously (in a worker thread)."""
        try:
            result = engine.analyze(TickerAnalysisRequest(symbol=symbol))
            return symbol, result, None
        except Exception as exc:
            return symbol, None, str(exc)

    # Parallelize via ThreadPoolExecutor. Each analyze() is network-bound
    # (yfinance), so 4 workers is enough. 6 tickers: ~10s serial → ~3s parallel.
    new_verdicts: dict[str, dict[str, Any]] = {}
    items: list[WatchlistItemResponse] = []
    with ThreadPoolExecutor(max_workers=4, thread_name_prefix="wl-refresh") as pool:
        futures = [pool.submit(_analyze_sync, s) for s in symbols]
        for fut in futures:
            sym, result, err = fut.result()
            if err or result is None:
                log.warning("watchlist_refresh_item_failed", symbol=sym, error=err)
                items.append(WatchlistItemResponse(
                    symbol=sym, verdict="ERROR", conviction=0, position_size=None,
                ))
                continue
            if result.verdict:
                new_verdicts[sym] = {
                    "action": result.verdict.action,
                    "conviction": result.verdict.conviction,
                }
                pos_size_dict = None
                if result.risk and result.price:
                    pos_size_dict = {
                        "suggested_pct": result.risk.suggested_position_size_pct,
                        "stop_pct": result.risk.suggested_stop_pct,
                    }
                items.append(WatchlistItemResponse(
                    symbol=sym,
                    verdict=result.verdict.action,
                    conviction=result.verdict.conviction,
                    position_size=pos_size_dict,
                    days_to_earnings=(
                        result.earnings.days_until_earnings
                        if result.earnings is not None
                        else None
                    ),
                ))

    # Detect verdict changes
    verdict_changes = svc.record_verdicts(new_verdicts)
    svc.set_last_refresh(verdict_changes)

    log.info("watchlist_refreshed", tickers=len(symbols), changes=len(verdict_changes))
    return ApiResponse(
        data=WatchlistRefreshResponse(
            refresh_time=svc.get_last_refresh_time() or datetime.now(UTC).isoformat(),
            tickers=items,
            verdict_changes=verdict_changes,
        ),
        meta=MetaInfo(
            request_id="",
            duration_ms=round((time.monotonic() - start) * 1000, 1),
            timestamp=datetime.now(UTC).isoformat(),
        ),
    )


@router.get("/education/{metric}", response_model=ApiResponse[EducationResponse])
async def get_education(
    metric: str,
    symbol: str | None = Query(None, description="Optional symbol for context"),
    value: str | None = Query(None, description="Metric value to explain"),
) -> ApiResponse[EducationResponse]:
    """Get a plain-English explanation of a financial metric.

    Falls back to static template explanations for 20 core metrics.
    Accepts metric name variations (e.g., 'pe_ratio', 'P/E', 'pe').
    """
    start = time.monotonic()

    value_str = value or "N/A"
    service = _get_education_service()
    explanation = service.explain(metric, value_str, symbol=symbol)

    duration = (time.monotonic() - start) * 1000
    return ApiResponse(
        data=explanation,
        meta=MetaInfo(
            request_id="",
            duration_ms=round(duration, 1),
            timestamp=datetime.now(UTC).isoformat(),
        ),
    )


@router.get("/position-size", response_model=ApiResponse[PositionSizeResponse])
async def calculate_position_size(
    symbol: str = Query(..., description="Ticker symbol"),
    account_equity: float = Query(..., description="Total account equity"),
    entry: float = Query(..., description="Planned entry price"),
    stop_loss: float = Query(..., description="Stop loss price"),
    conviction: str = Query("medium", description="Conviction level: high/medium/low"),
) -> ApiResponse[PositionSizeResponse]:
    """Calculate position size using conviction-adjusted Kelly.

    Uses the formula: position_size = min(kelly_base, position_cap, sector_cap)
    where kelly_base = equity × risk_pct × conviction_mult / risk_per_share.
    """
    start = time.monotonic()

    try:
        request = PositionSizeRequest(
            symbol=symbol.upper(),
            account_equity=account_equity,
            entry=entry,
            stop_loss=stop_loss,
            conviction=conviction.lower(),
        )
        sizer = _get_position_sizer()
        result = sizer.calculate(request)

        duration = (time.monotonic() - start) * 1000
        return ApiResponse(
            data=result,
            meta=MetaInfo(
                request_id="",
                duration_ms=round(duration, 1),
                timestamp=datetime.now(UTC).isoformat(),
            ),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.exception("position_size_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Position size calculation failed: {str(e)}")


@router.get("/alerts/preferences", response_model=ApiResponse[AlertPreferences])
async def get_alert_preferences(
    email: str = Query("default@trader.com", description="User email"),
) -> ApiResponse[AlertPreferences]:
    """Get alert notification preferences for the current user."""
    start = time.monotonic()
    service = _get_alert_service()
    prefs = service.get_preferences(email)
    duration = (time.monotonic() - start) * 1000
    return ApiResponse(
        data=prefs,
        meta=MetaInfo(
            request_id="",
            duration_ms=round(duration, 1),
            timestamp=datetime.now(UTC).isoformat(),
        ),
    )


@router.put("/alerts/preferences", response_model=ApiResponse[AlertPreferences])
async def update_alert_preferences(
    email: str = Query("default@trader.com", description="User email"),
    email_morning_brief: bool = Query(True),
    email_stop_hit: bool = Query(True),
    push_stop_hit: bool = Query(True),
    push_target_hit: bool = Query(True),
    email_earnings_alert: bool = Query(True),
    email_regime_change: bool = Query(True),
    email_weekly_review: bool = Query(False),
) -> ApiResponse[AlertPreferences]:
    """Update alert notification preferences."""
    start = time.monotonic()
    prefs = AlertPreferences(
        email_morning_brief=email_morning_brief,
        email_stop_hit=email_stop_hit,
        push_stop_hit=push_stop_hit,
        push_target_hit=push_target_hit,
        email_earnings_alert=email_earnings_alert,
        email_regime_change=email_regime_change,
        email_weekly_review=email_weekly_review,
    )
    service = _get_alert_service()
    service.update_preferences(email, prefs)
    duration = (time.monotonic() - start) * 1000
    return ApiResponse(
        data=prefs,
        meta=MetaInfo(
            request_id="",
            duration_ms=round(duration, 1),
            timestamp=datetime.now(UTC).isoformat(),
        ),
    )


@router.get("/alerts", response_model=ApiResponse[list[dict]])
async def list_alerts(
    limit: int = Query(20, ge=1, le=100, description="Max alerts to return"),
) -> ApiResponse[list[dict]]:
    """Return recent in-app alerts (stop hits, target hits, regime changes)."""
    start = time.monotonic()
    service = _get_alert_service()
    alerts = service.get_recent_alerts(limit=limit)
    duration = (time.monotonic() - start) * 1000
    return ApiResponse(
        data=alerts,
        meta=MetaInfo(
            request_id="",
            duration_ms=round(duration, 1),
            timestamp=datetime.now(UTC).isoformat(),
        ),
    )
