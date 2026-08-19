"""Market regime detection — elite trader-grade composite market state analysis.

Pure computation layer (no FastAPI): tracks VIX, risk-on/risk-off dynamics,
sector breadth, safe haven flows, and yield curve signals to produce a single
0-100 Market Regime Score.

Consumed by:
- api/routers/regime.py — HTTP wrapper (thin; only endpoints live there)
- domain/ticker_analysis/orchestrator.py + macro_overlay.py — macro overlay
- infrastructure/professional/morning_brief.py — regime label for the brief
- worker/scheduler.py — regime label via morning brief

This module deliberately lives in `infrastructure/` so the domain and API
layers can both depend on it without the old domain→API circular import.
"""

from __future__ import annotations

from datetime import UTC, datetime
import time
from typing import Any
import asyncio

import pandas as pd
import yfinance as yf
from pydantic import BaseModel

from backend.app.core.logging import get_logger

log = get_logger("conflu.market.regime")

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
# Deliberately long (6h) — regime is a swing-trading indicator measuring
# trailing ~1mo trends. Intraday noise shouldn't flip the label.
# Working 9-5 users check 2-3x/day; 6h cache covers that without stale reads.

_MACRO_CACHE: dict[str, Any] | None = None
_MACRO_CACHE_TIME: float = 0.0
_CACHE_TTL: float = 21600.0  # 6 hours

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
    """Score VIX level and trailing ~1mo trend. Returns (score_0-100, current_value, status).

    Data fetched with period='1mo', so iloc[0] ≈ 21 trading days back.
    This lookback aligns with the swing-trading focus (holds: days to weeks).
    """
    if vix_df is None or vix_df.empty:
        return 50.0, 0.0, "unknown"

    vix = float(vix_df["Close"].iloc[-1])
    vix_start = float(vix_df["Close"].iloc[0]) if len(vix_df) >= 2 else vix
    vix_change_1mo = ((vix - vix_start) / vix_start) * 100

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

    # Adjust for trailing ~1mo trend
    if vix_change_1mo > 20:
        score -= 15  # VIX up big over the month → penalty
        status = "spiking"
    elif vix_change_1mo < -15:
        score += 10  # VIX falling over the month → bonus

    return max(0.0, min(100.0, score)), round(vix, 2), status


def _score_risk_appetite(
    spy_df: pd.DataFrame | None,
    tlt_df: pd.DataFrame | None,
) -> tuple[float, float, str]:
    """Score risk appetite from SPY vs TLT trailing ~1mo performance spread.

    SPY up + TLT flat/down = Risk-On (high score)
    SPY down + TLT up = Risk-Off (low score)
    Data fetched with period='1mo', so iloc[0] ≈ 21 trading days back.
    Returns (score_0-100, spread_value, status).
    """
    if spy_df is None or len(spy_df) < 2:
        return 50.0, 0.0, "unknown"

    spy_close = spy_df["Close"]
    spy_1mo = (float(spy_close.iloc[-1]) - float(spy_close.iloc[0])) / float(spy_close.iloc[0]) * 100
    spy_1d = (float(spy_close.iloc[-1]) - float(spy_close.iloc[-2])) / float(spy_close.iloc[-2]) * 100

    tlt_1mo = 0.0
    if tlt_df is not None and len(tlt_df) >= 2:
        tlt_close = tlt_df["Close"]
        tlt_1mo = (float(tlt_close.iloc[-1]) - float(tlt_close.iloc[0])) / float(tlt_close.iloc[0]) * 100

    # Risk appetite spread: how much SPY outperforms TLT over the trailing month
    spread = spy_1mo - tlt_1mo

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
    """Score safe haven demand from GLD vs SPY trailing ~1mo performance.

    Gold up significantly while SPY down → fear (low score)
    Gold flat/down while SPY up → risk-on (high score)
    Data fetched with period='1mo', so iloc[0] ≈ 21 trading days back.
    Returns (score_0-100, gold_perf_1mo, status).
    """
    if gld_df is None or len(gld_df) < 2:
        return 50.0, 0.0, "unknown"

    gld_close = gld_df["Close"]
    gld_1mo = (float(gld_close.iloc[-1]) - float(gld_close.iloc[0])) / float(gld_close.iloc[0]) * 100

    spy_1mo = 0.0
    if spy_df is not None and len(spy_df) >= 2:
        spy_close = spy_df["Close"]
        spy_1mo = (float(spy_close.iloc[-1]) - float(spy_close.iloc[0])) / float(spy_close.iloc[0]) * 100

    # If gold is up significantly while SPY is down = fear flight
    if gld_1mo > 2 and spy_1mo < -1:
        score = 15.0
        status = "flight_to_safety"
    elif gld_1mo > 1 and spy_1mo < 0:
        score = 30.0
        status = "hedging"
    elif gld_1mo < -1 and spy_1mo > 1:
        score = 85.0
        status = "risk_on"
    elif abs(gld_1mo) < 1:
        score = 65.0
        status = "neutral"
    else:
        # Mixed signals
        score = 50.0
        status = "mixed"

    return score, round(gld_1mo, 2), status


def _score_yield_curve(
    tlt_df: pd.DataFrame | None,
    shy_df: pd.DataFrame | None,
) -> tuple[float, float, str]:
    """Score yield curve signal from TLT vs SHY trailing ~1mo relative performance.

    TLT outperforming SHY → flight to long duration (bearish for growth)
    SHY performing inline or TLT underperforming → normal
    Data fetched with period='1mo', so iloc[0] ≈ 21 trading days back.
    Returns (score_0-100, spread_value, status).
    """
    if tlt_df is None or shy_df is None or len(tlt_df) < 2 or len(shy_df) < 2:
        return 50.0, 0.0, "unknown"

    tlt_close = tlt_df["Close"]
    tlt_1mo = (float(tlt_close.iloc[-1]) - float(tlt_close.iloc[0])) / float(tlt_close.iloc[0]) * 100

    shy_close = shy_df["Close"]
    shy_1mo = (float(shy_close.iloc[-1]) - float(shy_close.iloc[0])) / float(shy_close.iloc[0]) * 100

    spread = tlt_1mo - shy_1mo

    # TLT significantly outperforming over the month = flight to duration (recession fear)
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


# ── Core computation ──


def compute_market_regime_sync() -> MarketRegimeResponse | None:
    """Compute the market regime snapshot synchronously.

    Pure-sync implementation of the regime endpoint. The actual computation
    (fetch, score, weight, label) never awaits — only the HTTP wrapper does.
    This lets internal callers (e.g. morning brief) reuse the exact same logic
    without event-loop gymnastics.
    """
    try:
        now = datetime.now(UTC)
        start = datetime.now(UTC)

        macro = _get_or_fetch_macro()

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

        weights = {
            "vix": 0.30,
            "risk_appetite": 0.25,
            "sector_breadth": 0.20,
            "safe_haven": 0.15,
            "yield_curve": 0.10,
        }

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

        return MarketRegimeResponse(
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
        )
    except Exception:
        log.exception("market_regime_compute_failed")
        return None


def _unknown_regime(timestamp: str | None = None) -> MarketRegimeResponse:
    """Fallback regime snapshot used when computation fails (matches the old router behavior)."""
    return MarketRegimeResponse(
        composite_score=0.0,
        regime_label="unknown",
        regime_color="#facc15",
        vix=RegimeIndicator(name="VIX", value=0, score=0, weight=0, status="unknown"),
        risk_appetite=RegimeIndicator(name="Risk Appetite", value=0, score=0, weight=0, status="unknown"),
        sector_breadth=RegimeIndicator(name="Sector Breadth", value=0, score=0, weight=0, status="unknown"),
        safe_haven=RegimeIndicator(name="Safe Haven", value=0, score=0, weight=0, status="unknown"),
        yield_curve=RegimeIndicator(name="Yield Curve", value=0, score=0, weight=0, status="unknown"),
        timestamp=timestamp or datetime.now(UTC).isoformat(),
    )


async def get_market_regime_async() -> MarketRegimeResponse:
    """Return the current regime snapshot (never raises; falls back to 'unknown').

    compute_market_regime_sync performs blocking yfinance fetches, so it runs in
    a worker thread to keep the event loop responsive.
    """
    data = await asyncio.to_thread(compute_market_regime_sync)
    return data if data is not None else _unknown_regime()


# ── Synchronous wrapper for internal use ──
def get_market_regime_sync() -> MarketRegimeResponse | None:
    """Synchronous wrapper to fetch market regime for internal use."""
    return compute_market_regime_sync()


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