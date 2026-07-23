"""Market regime detection API — elite trader-grade composite market state analysis.

Tracks VIX, risk-on/risk-off dynamics, sector breadth, safe haven flows,
and yield curve signals to produce a single 0-100 Market Regime Score.

Endpoints:
- GET /api/v1/market/regime        — Current market regime snapshot
"""

from __future__ import annotations

from datetime import UTC, datetime
import time
from typing import Any

import pandas as pd
import yfinance as yf
from fastapi import APIRouter
from pydantic import BaseModel

from backend.app.api.schemas import ApiResponse, MetaInfo
from backend.app.core.logging import get_logger

router = APIRouter(prefix="/market", tags=["market"])
log = get_logger("conflu.api.regime")

# ── Macro symbols tracked ──
VIX_SYM = "^VIX"
SPY_SYM = "SPY"
TLT_SYM = "TLT"   # Long-term treasuries (flight to safety)
GLD_SYM = "GLD"   # Gold (inflation hedge / fear)
SHY_SYM = "SHY"   # Short-term treasuries (yield curve comparison)
DXY_SYM = "DX-Y.NYB"  # US Dollar Index

MACRO_SYMBOLS = [VIX_SYM, SPY_SYM, TLT_SYM, GLD_SYM, SHY_SYM, DXY_SYM]

# All 11 sector ETFs for breadth calculation
SECTOR_SYMBOLS = ["XLF", "XLK", "XLV", "XLI", "XLB", "XLE", "XLU", "XLRE", "XLY", "XLP", "XLC"]

# ── Pydantic Models ──


class RegimeIndicator(BaseModel):
    """Individual regime indicator with score and raw value."""
    name: str
    value: float
    score: float  # 0-100 contribution
    weight: float  # Weight in composite
    status: str = "normal"  # normal / warning / alert


class MarketRegimeResponse(BaseModel):
    """Full market regime snapshot."""
    composite_score: float  # 0-100
    regime_label: str
    regime_color: str  # Hex color for UI
    vix: RegimeIndicator
    risk_appetite: RegimeIndicator
    sector_breadth: RegimeIndicator
    safe_haven: RegimeIndicator
    yield_curve: RegimeIndicator
    timestamp: str
    data_fetched_at: str = ""


# ── TTL Cache (timestamp-based, no external deps) ──

import time

_MACRO_CACHE: dict[str, Any] | None = None
_MACRO_CACHE_TIME: float = 0.0
_CACHE_TTL: float = 21600.0  # 6 hours (daily data — changes only at market close)

_SECTOR_BREADTH_CACHE: dict[str, Any] | None = None
_SECTOR_BREADTH_TIME: float = 0.0


def _get_or_fetch_macro() -> dict[str, pd.DataFrame]:
    """Return cached macro data or fetch fresh if TTL expired."""
    global _MACRO_CACHE, _MACRO_CACHE_TIME
    now = time.time()
    if _MACRO_CACHE is None or (now - _MACRO_CACHE_TIME) > _CACHE_TTL:
        log.info("regime_cache_miss", reason="expired" if _MACRO_CACHE else "cold")
        _MACRO_CACHE = _fetch_macro_data()
        _MACRO_CACHE_TIME = now
    return _MACRO_CACHE


def _fetch_macro_data() -> dict[str, pd.DataFrame]:
    """Fetch all macro indicators via yfinance."""
    results: dict[str, pd.DataFrame] = {}
    for sym in MACRO_SYMBOLS:
        try:
            ticker = yf.Ticker(sym)
            df = ticker.history(period="1mo", interval="1d")
            if not df.empty:
                results[sym] = df
            else:
                log.warning("no_macro_data", symbol=sym)
        except Exception:
            log.exception("macro_fetch_failed", symbol=sym)
    return results


def _get_or_fetch_breadth() -> dict[str, Any]:
    """Return cached sector breadth or fetch fresh if TTL expired."""
    global _SECTOR_BREADTH_CACHE, _SECTOR_BREADTH_TIME
    now = time.time()
    if _SECTOR_BREADTH_CACHE is None or (now - _SECTOR_BREADTH_TIME) > _CACHE_TTL:
        _SECTOR_BREADTH_CACHE = _fetch_sector_breadth()
        _SECTOR_BREADTH_TIME = now
    return _SECTOR_BREADTH_CACHE


def _fetch_sector_breadth() -> dict[str, Any]:
    """Quick sector breadth check: return count of sectors with positive 1W return."""
    positive = 0
    total = 0
    for sym in SECTOR_SYMBOLS:
        try:
            ticker = yf.Ticker(sym)
            df = ticker.history(period="1w", interval="1d")
            if len(df) >= 2:
                rtn = (float(df["Close"].iloc[-1]) - float(df["Close"].iloc[0])) / float(df["Close"].iloc[0]) * 100
                if rtn > 0:
                    positive += 1
                total += 1
        except Exception:
            continue

    return {"positive": positive, "total": total}


# ── Scoring Functions ──


def _score_vix(vix_df: pd.DataFrame | None) -> tuple[float, float, str]:
    """Score VIX level and trend. Returns (score_0-100, current_value, status)."""
    if vix_df is None or vix_df.empty:
        return 50.0, 0.0, "unknown"

    vix = float(vix_df["Close"].iloc[-1])
    vix_5d_ago = float(vix_df["Close"].iloc[0]) if len(vix_df) >= 2 else vix
    vix_change = ((vix - vix_5d_ago) / vix_5d_ago) * 100

    # Base score from VIX level
    if vix < 12:
        score = 90.0
        status = "complacent"
    elif vix < 15:
        score = 75.0
        status = "low_volatility"
    elif vix < 20:
        score = 60.0
        status = "normal"
    elif vix < 25:
        score = 40.0
        status = "elevated"
    elif vix < 35:
        score = 25.0
        status = "fearful"
    else:
        score = 10.0
        status = "panic"

    # Adjust for trend
    if vix_change > 20:
        score -= 15  # VIX spiking up → penalty
        status = "spiking"
    elif vix_change < -15:
        score += 10  # VIX dropping fast → bonus

    return max(0.0, min(100.0, score)), round(vix, 2), status


def _score_risk_appetite(
    spy_df: pd.DataFrame | None,
    tlt_df: pd.DataFrame | None,
) -> tuple[float, float, str]:
    """Score risk appetite from SPY vs TLT performance spread.

    SPY up + TLT flat/down = Risk-On (high score)
    SPY down + TLT up = Risk-Off (low score)
    Returns (score_0-100, spread_value, status).
    """
    if spy_df is None or len(spy_df) < 2:
        return 50.0, 0.0, "unknown"

    spy_close = spy_df["Close"]
    spy_5d = (float(spy_close.iloc[-1]) - float(spy_close.iloc[0])) / float(spy_close.iloc[0]) * 100
    spy_1d = (float(spy_close.iloc[-1]) - float(spy_close.iloc[-2])) / float(spy_close.iloc[-2]) * 100

    tlt_5d = 0.0
    if tlt_df is not None and len(tlt_df) >= 2:
        tlt_close = tlt_df["Close"]
        tlt_5d = (float(tlt_close.iloc[-1]) - float(tlt_close.iloc[0])) / float(tlt_close.iloc[0]) * 100

    # Risk appetite spread: how much SPY outperforms TLT
    spread = spy_5d - tlt_5d

    # Normalize to 0-100: spread of -5 to +15 maps to 0-100
    score = (spread + 5.0) / 20.0 * 100.0
    score = max(0.0, min(100.0, score))

    # Determine status
    if score >= 70:
        status = "risk_on"
    elif score >= 50:
        status = "neutral"
    elif score >= 30:
        status = "cautious"
    else:
        status = "risk_off"

    return round(score, 1), round(spread, 2), status


def _score_safe_haven(
    gld_df: pd.DataFrame | None,
    spy_df: pd.DataFrame | None,
) -> tuple[float, float, str]:
    """Score safe haven demand from GLD performance vs SPY.

    Gold up significantly while SPY down → fear (low score)
    Gold flat/down while SPY up → risk-on (high score)
    Returns (score_0-100, gold_perf_5d, status).
    """
    if gld_df is None or len(gld_df) < 2:
        return 50.0, 0.0, "unknown"

    gld_close = gld_df["Close"]
    gld_5d = (float(gld_close.iloc[-1]) - float(gld_close.iloc[0])) / float(gld_close.iloc[0]) * 100

    spy_5d = 0.0
    if spy_df is not None and len(spy_df) >= 2:
        spy_close = spy_df["Close"]
        spy_5d = (float(spy_close.iloc[-1]) - float(spy_close.iloc[0])) / float(spy_close.iloc[0]) * 100

    # If gold is up significantly while SPY is down = fear flight
    if gld_5d > 2 and spy_5d < -1:
        score = 15.0
        status = "flight_to_safety"
    elif gld_5d > 1 and spy_5d < 0:
        score = 30.0
        status = "hedging"
    elif gld_5d < -1 and spy_5d > 1:
        score = 85.0
        status = "risk_on"
    elif abs(gld_5d) < 1:
        score = 65.0
        status = "neutral"
    else:
        # Mixed signals
        score = 50.0
        status = "mixed"

    return score, round(gld_5d, 2), status


def _score_yield_curve(
    tlt_df: pd.DataFrame | None,
    shy_df: pd.DataFrame | None,
) -> tuple[float, float, str]:
    """Score yield curve signal from TLT vs SHY relative performance.

    TLT outperforming SHY → flight to long duration (bearish for growth)
    SHY performing inline or TLT underperforming → normal
    Returns (score_0-100, spread_value, status).
    """
    if tlt_df is None or shy_df is None or len(tlt_df) < 2 or len(shy_df) < 2:
        return 50.0, 0.0, "unknown"

    tlt_close = tlt_df["Close"]
    tlt_5d = (float(tlt_close.iloc[-1]) - float(tlt_close.iloc[0])) / float(tlt_close.iloc[0]) * 100

    shy_close = shy_df["Close"]
    shy_5d = (float(shy_close.iloc[-1]) - float(shy_close.iloc[0])) / float(shy_close.iloc[0]) * 100

    spread = tlt_5d - shy_5d

    # TLT significantly outperforming = flight to duration (recession fear)
    if spread > 2:
        score = 20.0
        status = "flattening"
    elif spread > 1:
        score = 35.0
        status = "slight_flattening"
    elif spread < -0.5:
        score = 70.0
        status = "steepening"
    else:
        score = 55.0
        status = "normal"

    return score, round(spread, 2), status


def _score_sector_breadth() -> tuple[float, float, str]:
    """Score from sector breadth — % of sectors with positive 1W return.

    High breadth = broad market participation = healthy
    Low breadth = narrow leadership = fragile
    """
    breadth = _get_or_fetch_breadth()
    total = breadth["total"]
    positive = breadth["positive"]

    pct = (positive / total * 100) if total > 0 else 50.0

    if pct >= 80:
        score = 85.0
        status = "broad_strength"
    elif pct >= 60:
        score = 65.0
        status = "healthy"
    elif pct >= 40:
        score = 45.0
        status = "mixed"
    elif pct >= 20:
        score = 25.0
        status = "narrow"
    else:
        score = 10.0
        status = "broad_weakness"

    return score, round(pct, 1), status


def _composite_to_label(score: float) -> tuple[str, str]:
    """Convert composite score to regime label + hex color."""
    if score >= 80:
        return "Exuberance", "#22c55e"  # green-500
    if score >= 65:
        return "Risk-On", "#4ade80"     # green-400
    if score >= 50:
        return "Neutral", "#facc15"     # yellow-400
    if score >= 35:
        return "Cautious", "#fb923c"    # orange-400
    if score >= 20:
        return "Risk-Off", "#f87171"    # red-400
    return "Crisis", "#dc2626"          # red-600


# ── Route ──


@router.get("/regime")
async def get_market_regime() -> ApiResponse[MarketRegimeResponse]:
    """Get current market regime snapshot with composite score and all sub-indicators."""
    now = datetime.now(UTC)
    start = datetime.now(UTC)

    macro = _get_or_fetch_macro()

    # Score each indicator
    vix_score, vix_value, vix_status = _score_vix(macro.get(VIX_SYM))
    risk_score, risk_spread, risk_status = _score_risk_appetite(
        macro.get(SPY_SYM), macro.get(TLT_SYM)
    )
    safe_score, gold_perf, safe_status = _score_safe_haven(
        macro.get(GLD_SYM), macro.get(SPY_SYM)
    )
    yield_score, yield_spread, yield_status = _score_yield_curve(
        macro.get(TLT_SYM), macro.get(SHY_SYM)
    )
    breadth_score, breadth_pct, breadth_status = _score_sector_breadth()

    # Composite: weighted average with dynamic weights
    # Normal
    weights = {
        "vix": 0.30,
        "risk_appetite": 0.25,
        "sector_breadth": 0.20,
        "safe_haven": 0.15,
        "yield_curve": 0.10,
    }

    # Boost risk_appetite weight when it's extreme (consensus-building)
    if risk_score >= 80 or risk_score <= 20:
        weights["risk_appetite"] = 0.35
        weights["vix"] = 0.25
        weights["sector_breadth"] = 0.15
        weights["safe_haven"] = 0.15
        weights["yield_curve"] = 0.10

    composite = (
        vix_score * weights["vix"]
        + risk_score * weights["risk_appetite"]
        + breadth_score * weights["sector_breadth"]
        + safe_score * weights["safe_haven"]
        + yield_score * weights["yield_curve"]
    )

    regime_label, regime_color = _composite_to_label(composite)

    duration = (datetime.now(UTC) - start).total_seconds() * 1000

    return ApiResponse(
        data=MarketRegimeResponse(
            composite_score=round(composite, 1),
            regime_label=regime_label,
            regime_color=regime_color,
            vix=RegimeIndicator(
                name="VIX",
                value=vix_value,
                score=round(vix_score, 1),
                weight=weights["vix"],
                status=vix_status,
            ),
            risk_appetite=RegimeIndicator(
                name="Risk Appetite",
                value=risk_spread,
                score=round(risk_score, 1),
                weight=weights["risk_appetite"],
                status=risk_status,
            ),
            sector_breadth=RegimeIndicator(
                name="Sector Breadth",
                value=breadth_pct,
                score=round(breadth_score, 1),
                weight=weights["sector_breadth"],
                status=breadth_status,
            ),
            safe_haven=RegimeIndicator(
                name="Safe Haven",
                value=gold_perf,
                score=round(safe_score, 1),
                weight=weights["safe_haven"],
                status=safe_status,
            ),
            yield_curve=RegimeIndicator(
                name="Yield Curve",
                value=yield_spread,
                score=round(yield_score, 1),
                weight=weights["yield_curve"],
                status=yield_status,
            ),
            timestamp=now.isoformat(),
            data_fetched_at=datetime.fromtimestamp(_MACRO_CACHE_TIME, UTC).isoformat(),
        ),
        meta=MetaInfo(request_id="", duration_ms=round(duration, 1)),
    )


# ── Synchronous wrapper for internal use ──
def get_market_regime_sync() -> MarketRegimeResponse | None:
    """Synchronous wrapper to fetch market regime for internal use."""
    import asyncio
    
    async def _get_regime() -> MarketRegimeResponse | None:
        try:
            response: ApiResponse = await get_market_regime()
            return response.data
        except Exception:
            log.exception("macro_regime_fetch_failed")
            return None
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(_get_regime())


# ── Market Events ──

MARKET_EVENTS_CACHE: list[dict] | None = None
MARKET_EVENTS_CACHE_TIME: float = 0.0
EVENTS_CACHE_TTL = 86400  # 24 hours


def _get_upcoming_events() -> list[dict]:
    """Return upcoming market events (FOMC, CPI, PCE, earnings season)."""
    global MARKET_EVENTS_CACHE, MARKET_EVENTS_CACHE_TIME
    now = datetime.now(UTC)
    if MARKET_EVENTS_CACHE and (time.time() - MARKET_EVENTS_CACHE_TIME) < EVENTS_CACHE_TTL:
        return MARKET_EVENTS_CACHE

    year = now.year
    today = now.date()
    events: list[dict] = []

    # FOMC meetings (2026 schedule)
    fomc_dates = [
        "2026-01-28", "2026-03-18", "2026-05-06", "2026-06-17",
        "2026-07-29", "2026-09-16", "2026-11-04", "2026-12-16",
    ]
    for d_str in fomc_dates:
        from datetime import date
        d = date.fromisoformat(d_str)
        days_until = (d - today).days
        events.append({
            "date": d_str,
            "title": "FOMC Meeting",
            "description": "Federal Reserve interest rate decision" + (" + press conference" if d.month in (3, 6, 9, 12) else ""),
            "days_until": days_until,
            "importance": "high",
        })

    # Recent CPI releases and upcoming CPI
    cpi_dates = [
        "2026-01-15", "2026-02-14", "2026-03-16", "2026-04-15",
        "2026-05-15", "2026-06-12", "2026-07-15", "2026-08-14",
        "2026-09-15", "2026-10-15", "2026-11-16", "2026-12-15",
    ]
    for d_str in cpi_dates:
        from datetime import date
        d = date.fromisoformat(d_str)
        days_until = (d - today).days
        if -5 <= days_until <= 90:
            events.append({
                "date": d_str,
                "title": "CPI Report",
                "description": "Consumer Price Index",
                "days_until": days_until,
                "importance": "high",
            })

    # PCE releases
    pce_dates = [
        "2026-01-30", "2026-02-27", "2026-03-28", "2026-04-29",
        "2026-05-29", "2026-06-26", "2026-07-30", "2026-08-28",
        "2026-09-29", "2026-10-30", "2026-11-27", "2026-12-30",
    ]
    for d_str in pce_dates:
        from datetime import date
        d = date.fromisoformat(d_str)
        days_until = (d - today).days
        if -5 <= days_until <= 90:
            events.append({
                "date": d_str,
                "title": "PCE Inflation",
                "description": "Personal Consumption Expenditures",
                "days_until": days_until,
                "importance": "medium",
            })

    events.sort(key=lambda e: e["days_until"])
    events = [e for e in events if e["days_until"] >= 0][:10]

    MARKET_EVENTS_CACHE = events
    MARKET_EVENTS_CACHE_TIME = time.time()
    return events


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
