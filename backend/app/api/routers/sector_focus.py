"""Sector Focus API — prescriptive weekly sector hunt verdicts.

Endpoint:
- GET /api/v1/sectors/focus — FOCUS/WATCH/AVOID verdicts fused from the same
  cached sector data that powers the Sector Rotation page (single snapshot,
  byte-identical numbers across surfaces).
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

import pandas as pd
import yfinance as yf
from fastapi import APIRouter

from backend.app.api.schemas import ApiResponse, MetaInfo
from backend.app.core.logging import get_logger
from backend.app.domain.sector_focus.service import (
    build_sector_focus_snapshot,
    entry_to_dict,
)
router = APIRouter(prefix="/sectors", tags=["sector-focus"])
log = get_logger("conflu.api.sector_focus")

_SPY_CACHE: tuple[float, float | None] | None = None
_SPY_CACHE_TTL = 300.0


def _get_spy_change_1w() -> float | None:
    """SPY 1W return for the absolute-vs-market FOCUS gate (own 5-min cache)."""
    global _SPY_CACHE
    now = time.time()
    if _SPY_CACHE is not None and (now - _SPY_CACHE[0]) < _SPY_CACHE_TTL:
        return _SPY_CACHE[1]
    value: float | None = None
    try:
        hist = yf.Ticker("SPY").history(period="1mo", interval="1d")
        closes: pd.Series = hist["Close"].dropna() if not hist.empty else pd.Series(dtype=float)
        if len(closes) >= 7 and float(closes.iloc[-7]) != 0:
            value = round(
                (float(closes.iloc[-1]) - float(closes.iloc[-7])) / float(closes.iloc[-7]) * 100,
                3,
            )
    except Exception:
        log.exception("spy_fetch_failed")
        value = None
    _SPY_CACHE = (now, value)
    return value


@router.get("/focus")
async def get_sector_focus() -> ApiResponse[dict]:
    """Weekly sector hunt verdicts: max N FOCUS sectors by regime, WATCH tier,
    explicit AVOID list. Shares the rotation endpoint's cached data so numbers
    match across surfaces."""
    start = datetime.now(UTC)

    from backend.app.api.routers.sector_rotation import (
        _build_sector_performances,
        _get_cached_sector_data,
    )

    df, volume_ratios, latest_volumes, volume_ratios_1w = _get_cached_sector_data()
    if df.empty or len(df.columns) < 2:
        log.warning("sector_focus_no_data")
        return ApiResponse(data={}, meta=MetaInfo(request_id="", duration_ms=0))

    perfs = _build_sector_performances(df, volume_ratios, latest_volumes, volume_ratios_1w)
    flow_map = {p.symbol: p.flow_strength_1w for p in perfs}
    spy_change = _get_spy_change_1w()

    snap = build_sector_focus_snapshot(
        df=df,
        volume_ratios_1w=volume_ratios_1w,
        flow_strength_1w_by_symbol=flow_map,
        spy_change_1w=spy_change,
        now=start,
    )
    duration = (datetime.now(UTC) - start).total_seconds() * 1000

    payload = snap.to_dict()
    payload["leaders_laggards_context"] = {
        "rotation_phase": "see /sector-rotation",
        "note": "Daily moves are noise; this card ranks the weekly horizon.",
    }
    # Keep the raw entries out of the wire payload; tiers carry everything.
    payload.pop("entries", None)
    payload["all_entries"] = [entry_to_dict(e) for e in snap.entries]

    return ApiResponse(
        data=payload,
        meta=MetaInfo(request_id=snap.snapshot_id, duration_ms=round(duration, 1)),
    )
