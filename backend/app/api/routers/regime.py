"""Market regime detection API — thin HTTP wrapper.

All computation lives in ``backend.app.infrastructure.market.regime`` so the
domain layer (ticker analysis orchestrator, macro overlay) and the professional
layer (morning brief) can consume it without importing from the API layer.

Endpoints:
- GET /api/v1/market/regime        — Current market regime snapshot
- GET /api/v1/market/events        — Upcoming FOMC/CPI/PCE events
- GET /api/v1/market/narrative     — Human-readable market narrative
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter

from backend.app.api.schemas import ApiResponse, MetaInfo
from backend.app.infrastructure.market.regime import (
    get_market_regime_async,
    get_market_regime_sync,
    _get_upcoming_events,
)

# Re-exported for backward compatibility with existing importers.
__all__ = [
    "get_market_regime",
    "get_market_regime_sync",
    "MarketRegimeResponse",
    "RegimeIndicator",
    "compute_market_regime_sync",
]

from backend.app.infrastructure.market.regime import (  # noqa: E402  (re-export)
    MarketRegimeResponse,
    RegimeIndicator,
    compute_market_regime_sync,
)

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/regime")
async def get_market_regime() -> ApiResponse[MarketRegimeResponse]:
    """Get current market regime snapshot with composite score and all sub-indicators."""
    start = datetime.now(UTC)
    data = await get_market_regime_async()

    duration = (datetime.now(UTC) - start).total_seconds() * 1000

    return ApiResponse(
        data=data,
        meta=MetaInfo(request_id="", duration_ms=round(duration, 1)),
    )


@router.get("/events", summary="Upcoming market events")
async def get_market_events() -> ApiResponse:
    """Get upcoming market events — FOMC, CPI, PCE — with countdown in days."""
    events = _get_upcoming_events()
    return ApiResponse(
        data={"events": events, "count": len(events)},
        meta=MetaInfo(timestamp=datetime.now(UTC).isoformat()),
    )


@router.get("/narrative", summary="Market narrative summary")
async def get_market_narrative() -> ApiResponse:
    """Get a human-readable 1-paragraph market narrative summary."""
    try:
        regime_resp = await get_market_regime()
        regime = regime_resp.data if regime_resp else None
    except Exception:
        regime = None
    parts = []
    if regime:
        parts.append(
            f"Market regime is {regime.regime_label} ({regime.composite_score:.0f}/100) "
            f"with VIX at {regime.vix.value:.1f}."
        )
    events = _get_upcoming_events()
    upcoming = [e for e in events if e["days_until"] >= 0][:2]
    for e in upcoming:
        parts.append(f"Next: {e['title']} in {e['days_until']}d.")
    narrative = " ".join(parts) if parts else "Market data currently loading."
    return ApiResponse(
        data={"narrative": narrative, "generated_at": datetime.now(UTC).isoformat()},
        meta=MetaInfo(timestamp=datetime.now(UTC).isoformat()),
    )