"""Sector rotation API router — tracks relative strength and smart money flow across 11 sector ETFs.

Endpoints:
- GET /api/v1/sector-rotation          — All sectors with 1D/1W performance, RS rankings, flow signals
- GET /api/v1/sector-rotation/history   — Historical rotation data for charts
- GET /api/v1/sector-rotation/{symbol}  — Deep-dive on a single sector ETF
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf
from fastapi import APIRouter
from pydantic import BaseModel

from backend.app.api.schemas import ApiResponse, MetaInfo
from backend.app.core.logging import get_logger

router = APIRouter(prefix="/sector-rotation", tags=["sector-rotation"])
log = get_logger("conflu.api.sector_rotation")

# ── Sector ETF Definitions ──

SECTOR_ETFS: dict[str, dict[str, str]] = {
    "XLF": {
        "name": "Financials",
        "description": "Banks, insurance, brokerages, mortgage finance — sensitive to interest rates and credit cycles.",
    },
    "XLK": {
        "name": "Technology",
        "description": "Software, hardware, semiconductors, IT services — growth-driven, sensitive to innovation cycles.",
    },
    "XLV": {
        "name": "Health Care",
        "description": "Pharma, biotech, medical devices, managed care — defensive growth, regulatory-driven.",
    },
    "XLI": {
        "name": "Industrials",
        "description": "Aerospace, defense, machinery, transportation, infrastructure — cyclical, tied to GDP.",
    },
    "XLB": {
        "name": "Materials",
        "description": "Chemicals, metals, mining, construction materials — commodity-linked, early cycle.",
    },
    "XLE": {
        "name": "Energy",
        "description": "Oil & gas exploration, production, equipment — commodity-driven, inflation hedge.",
    },
    "XLU": {
        "name": "Utilities",
        "description": "Electric, gas, water utilities — defensive high-dividend, bond proxy, rate-sensitive.",
    },
    "XLRE": {
        "name": "Real Estate",
        "description": "REITs — property sectors (residential, commercial, industrial), rate-sensitive dividend plays.",
    },
    "XLY": {
        "name": "Consumer Cyclical",
        "description": "Retail, auto, housing, leisure, media — discretionary spending, economically sensitive.",
    },
    "XLP": {
        "name": "Consumer Staples",
        "description": "Food, beverage, household goods, personal care — defensive, recession-resistant.",
    },
    "XLC": {
        "name": "Communication Services",
        "description": "Telecom, media, entertainment, social media, gaming — convergence of tech and content.",
    },
}

SECTOR_SYMBOLS = list(SECTOR_ETFS.keys())

# ── Pydantic Models ──


class SectorPerformance(BaseModel):
    """Performance metrics for a single sector over specified periods."""
    symbol: str
    name: str
    description: str = ""
    price: float = 0.0
    change_1d: float | None = None
    change_1w: float | None = None
    change_1m: float | None = None
    volume_1d: float = 0.0
    volume_vs_avg: float | None = None  # Volume relative to 20-period average (daily)
    volume_vs_avg_1w: float | None = None  # Volume relative to 5-day rolling avg (weekly)
    relative_strength_1d: float | None = None  # Z-score vs all sectors
    relative_strength_1w: float | None = None
    momentum_score: float | None = None  # Composite 0-100
    trend: str = "neutral"
    flow_signal: str = "neutral"
    flow_strength: float = 0.0  # 0-100
    flow_signal_1w: str = "neutral"
    flow_strength_1w: float = 0.0  # 0-100 (weekly timeframe)


class SectorRotationResponse(BaseModel):
    """Full sector rotation snapshot."""
    sectors: list[SectorPerformance]
    leaders: list[str]  # Top 3 sector symbols
    laggards: list[str]  # Bottom 3 sector symbols
    rotation_phase: str = "unknown"
    market_regime: str = "unknown"
    timestamp: str = ""


class RotationHistoryPoint(BaseModel):
    """Single point in rotation history."""
    date: str
    sector_rankings: dict[str, float]  # symbol → relative_strength


class SectorDetail(BaseModel):
    """Deep-dive data for a single sector ETF."""
    symbol: str
    name: str
    description: str
    performance: SectorPerformance
    price_history: list[dict[str, Any]] = []
    relative_strength_history: list[dict[str, Any]] = []
    components: list[str] = []  # Top holdings


# ── Helper Functions ──

import time

_SECTOR_CACHE: tuple | None = None
_SECTOR_CACHE_TIME: float = 0.0
_SECTOR_CACHE_TTL: float = 300.0  # 5 minutes


def _get_cached_sector_data() -> tuple[pd.DataFrame, dict[str, float], dict[str, float], dict[str, float]]:
    """Return cached sector data or fetch fresh if TTL expired (5 min)."""
    global _SECTOR_CACHE, _SECTOR_CACHE_TIME
    now = time.time()
    if _SECTOR_CACHE is None or (now - _SECTOR_CACHE_TIME) > _SECTOR_CACHE_TTL:
        # log.info("sector_cache_miss", reason="expired" if _SECTOR_CACHE else "cold")
        _SECTOR_CACHE = _fetch_all_sector_data()
        _SECTOR_CACHE_TIME = now
    return _SECTOR_CACHE


def _fetch_all_sector_data() -> tuple[pd.DataFrame, dict[str, float], dict[str, float], dict[str, float]]:
    """Single-pass fetch of all sector ETFs: returns price matrix + volume_ratios + latest_volumes + volume_ratios_1w.

    Returns (price_df, volume_ratios, latest_volumes, volume_ratios_1w).
    price_df columns: timestamp + one column per sector (close prices)
    volume_ratios: {symbol: latest_volume / 20d_avg_volume} (1D)
    latest_volumes: {symbol: latest_volume}
    volume_ratios_1w: {symbol: sum(last_5d_volume) / avg(sum(5d_window))} (1W)
    """
    price_dfs: list[pd.DataFrame] = []
    volume_ratios: dict[str, float] = {}
    latest_volumes: dict[str, float] = {}
    volume_ratios_1w: dict[str, float] = {}

    for sym in SECTOR_SYMBOLS:
        try:
            ticker = yf.Ticker(sym)
            df = ticker.history(period="1mo", interval="1d")
            if df.empty:
                log.warning("no_data_for_sector", symbol=sym)
                continue

            # === 1D Volume Ratio ===
            # Prefer previous completed day's volume if latest candle is partial
            vol_series = df["Volume"]
            vol_full = float(vol_series.iloc[-2]) if len(vol_series) >= 2 else float(vol_series.iloc[-1])
            vol_partial = float(vol_series.iloc[-1])
            vol_avg = float(vol_series.tail(20).mean())

            use_partial = (vol_partial / vol_avg) >= 0.6 if vol_avg > 0 else False
            vol_latest = vol_partial if use_partial else vol_full
            volume_ratios[sym] = vol_latest / vol_avg if vol_avg > 0 else 1.0
            latest_volumes[sym] = vol_latest

            # === 1W Volume Ratio ===
            # Sum last 5 trading days' volume / average of rolling 5-day sums
            vol_values = list(vol_series.astype(float))
            window = 5
            if len(vol_values) >= window + 1:
                weekly_sum = sum(vol_values[-window:])
                rolling_sums = [
                    sum(vol_values[i : i + window])
                    for i in range(len(vol_values) - window)
                ]
                avg_weekly = sum(rolling_sums) / len(rolling_sums)
                volume_ratios_1w[sym] = weekly_sum / avg_weekly if avg_weekly > 0 else 1.0
            else:
                # Fall back to daily ratio scaled
                volume_ratios_1w[sym] = volume_ratios.get(sym, 1.0)

            # Price data
            df = df.reset_index()
            ts_col = "Datetime" if "Datetime" in df.columns else "Date"
            df = df.rename(columns={ts_col: "timestamp", "Close": sym})
            df = df[["timestamp", sym]]
            price_dfs.append(df)
        except Exception:
            log.exception("sector_fetch_failed", symbol=sym)
            volume_ratios[sym] = 1.0
            latest_volumes[sym] = 0.0

    if not price_dfs:
        return pd.DataFrame(), volume_ratios, latest_volumes, volume_ratios_1w

    merged = price_dfs[0]
    for df in price_dfs[1:]:
        merged = merged.merge(df, on="timestamp", how="outer")

    return merged.sort_values("timestamp"), volume_ratios, latest_volumes, volume_ratios_1w


def _compute_returns(df: pd.DataFrame) -> dict[str, dict[str, float | None]]:
    """Compute 1D, 1W, 1M returns for each sector symbol.

    Returns {symbol: {change_1d, change_1w, change_1m}}.
    """
    result: dict[str, dict[str, float | None]] = {}
    for sym in SECTOR_SYMBOLS:
        if sym not in df.columns:
            result[sym] = {"change_1d": None, "change_1w": None, "change_1m": None}
            continue
        prices = df[sym].dropna()
        if len(prices) < 2:
            result[sym] = {"change_1d": None, "change_1w": None, "change_1m": None}
            continue

        latest = prices.iloc[-1]
        result[sym] = {
            "change_1d": ((latest - prices.iloc[-2]) / prices.iloc[-2] * 100) if len(prices) >= 2 else None,
            "change_1w": ((latest - prices.iloc[-7]) / prices.iloc[-7] * 100) if len(prices) >= 7 else None,
            "change_1m": ((latest - prices.iloc[0]) / prices.iloc[0] * 100) if len(prices) >= 2 else None,
        }
    return result


def _compute_relative_strength(
    returns: dict[str, dict[str, float | None]],
    period: str,
) -> dict[str, float | None]:
    """Compute Z-score relative strength for a given period across all sectors.

    positive = sector outperforming average.
    """
    vals: list[float] = []
    sym_map: dict[str, float | None] = {}

    for sym in SECTOR_SYMBOLS:
        v = returns.get(sym, {}).get(period)
        sym_map[sym] = v
        if v is not None:
            vals.append(v)

    if len(vals) < 3:
        return {sym: None for sym in SECTOR_SYMBOLS}

    mean = float(np.mean(vals))
    std = float(np.std(vals))
    if std == 0:
        return {sym: None for sym in SECTOR_SYMBOLS}

    result: dict[str, float | None] = {}
    for sym, v in sym_map.items():
        result[sym] = ((v - mean) / std) if v is not None else None
    return result


def _compute_momentum(rs_1d: float | None, rs_1w: float | None) -> float:
    """Composite momentum score 0-100 from both period relative strengths."""
    score = 50.0
    if rs_1d is not None:
        score += rs_1d * 15  # ±15 per std dev
    if rs_1w is not None:
        score += rs_1w * 25  # ±25 per std dev (higher weight on longer period)
    return max(0.0, min(100.0, score))


def _detect_trend(change_1d: float | None, change_1w: float | None) -> str:
    """Classify trend based on 1D and 1W changes."""
    c1 = change_1d or 0
    c5 = change_1w or 0
    if c5 > 3 and c1 > 0:
        return "bullish"
    if c5 < -3 and c1 < 0:
        return "bearish"
    if c5 > 1 and c1 > -1:
        return "slight_bullish"
    if c5 < -1 and c1 < 1:
        return "slight_bearish"
    return "neutral"


def _compute_flow_signal(
    change_1d: float | None,
    volume_ratio: float | None,
    rs_1d: float | None,
) -> tuple[str, float]:
    """Derive smart-money flow signal from price action + volume + relative strength.

    Outperformance on high volume = smart money inflow (accumulation).
    Underperformance on high volume = smart money outflow (distribution).
    Low-volume moves = noise.
    """
    vol = volume_ratio or 0.0
    chg = change_1d or 0.0
    rs = rs_1d or 0.0

    # Composite flow strength (0-100)
    # Volume amplification + price conviction + relative strength
    # ETF volume ratios can be <1.0 during partial trading days — use lower thresholds
    strength = 0.0
    direction = "neutral"

    if vol >= 0.8 and chg > 0.5 and rs > 0.5:
        # Strong inflow: decent volume, up day, outperforming
        strength = min(100, max(0, vol - 0.5) * 40 + chg * 5 + rs * 15)
        direction = "inflow"
    elif vol >= 0.8 and chg < -0.5 and rs < -0.5:
        # Strong outflow: decent volume, down day, underperforming
        strength = min(100, max(0, vol - 0.5) * 40 + abs(chg) * 5 + abs(rs) * 15)
        direction = "outflow"
    elif vol >= 0.6 and chg > 0.3:
        # Moderate inflow
        strength = min(60, max(0, vol - 0.4) * 30 + chg * 3)
        direction = "inflow"
    elif vol >= 0.6 and chg < -0.3:
        # Moderate outflow
        strength = min(60, max(0, vol - 0.4) * 30 + abs(chg) * 3)
        direction = "outflow"

    return direction, round(strength, 1)


def _determine_rotation_phase(
    sectors: list[SectorPerformance],
    market_regime: str = "unknown",
) -> str:
    """Determine rotation phase using proportional sector presence across cycle groups.

    Replaces old top-3 priority chain with a continuous scoring approach:
    normalizes how many sectors from each phase group appear in the top half
    of 1W relative strength rankings, then applies rules with cross-reference
    to the market regime.

    Mappings corrected from elite trader research (Jun 2026):
    - Financials moved from late → early (rate cuts → credit expansion → loan growth)
    - Tech added to early (recovery beneficiary alongside Consumer Cyclical)
    - Consumer Staples added to defensive (classic recession-resistant)
    - Materials spans early/mid/late (commodity-linked, cycle-dependent)
    """
    # Sector-to-cycle mappings (elite-trader-reviewed)
    EARLY = {"XLF", "XLI", "XLY", "XLK"}  # Financials, Industrials, Consumer Cyclical, Tech
    MID   = {"XLK", "XLI", "XLB", "XLC"}    # Tech, Industrials, Materials, Comm Services
    LATE  = {"XLE", "XLB"}                   # Energy, Materials
    SAFE  = {"XLP", "XLU", "XLV", "XLRE"}    # Staples, Utilities, Health Care, Real Estate

    if not sectors:
        return "unknown"

    # Sort sectors by 1W relative strength (descending)
    sorted_sx = sorted(sectors, key=lambda s: (s.relative_strength_1w or 0), reverse=True)
    n = len(sorted_sx)
    top_half = {s.symbol for s in sorted_sx[:n // 2 + 1]}  # top 5-6 symbols

    def _score(group: set[str]) -> float:
        """Return percentage of this group's sectors found in the top half."""
        return sum(1 for sym in group if sym in top_half) / len(group) * 100

    early = _score(EARLY)
    mid   = _score(MID)
    late  = _score(LATE)
    safe  = _score(SAFE)

    # ── Rule chain ──────────────────────────────────────────────
    # 1) Strong defensive (>60% of safe sectors in the top half) → flight to safety
    if safe >= 60:
        return "defensive_flight"

    # 2) Strong early AND safe not elevated → early cycle
    if early >= 75 and safe < 40:
        return "early_cycle"

    # 3) Strong late (energy + materials) AND not defensive → late cycle
    if late >= 75 and safe < 40:
        return "late_cycle"

    # 4) Strong mid AND not dominantly early → growth leading
    if mid >= 60 and early < 40:
        return "growth_lead"

    # 5) Cross-reference with market regime — flag contradictions
    if market_regime == "broad_market_weakness":
        if early >= 50 or mid >= 50:
            return "divergent"
        if safe >= 40:
            return "defensive_flight"

    # 6) Tiebreaker — pick the strongest score
    scores = [("early_cycle", early), ("growth_lead", mid),
              ("late_cycle", late), ("defensive_flight", safe)]
    best = max(scores, key=lambda x: x[1])

    if best[1] < 30:
        return "neutral"

    return best[0]


def _detect_market_regime(sectors: list[SectorPerformance]) -> str:
    """Detect overall market regime based on sector breadth."""
    bullish = sum(1 for s in sectors if s.relative_strength_1d is not None and s.relative_strength_1d > 0)
    bearish = sum(1 for s in sectors if s.relative_strength_1d is not None and s.relative_strength_1d < -0.5)

    total = len([s for s in sectors if s.relative_strength_1d is not None])
    if total == 0:
        return "unknown"

    if bullish >= total * 0.6:
        return "broad_market_strength"
    if bearish >= total * 0.5:
        return "broad_market_weakness"
    return "mixed"


def _build_sector_performances(
    df: pd.DataFrame,
    volume_ratios: dict[str, float],
    latest_volumes: dict[str, float],
    volume_ratios_1w: dict[str, float],
) -> list[SectorPerformance]:
    """Shared pipeline used by BOTH the rotation snapshot and the focus verdict so
    every surface renders byte-identical sector numbers from one cache."""
    returns = _compute_returns(df)

    rs_1d = _compute_relative_strength(returns, "change_1d")
    rs_1w = _compute_relative_strength(returns, "change_1w")

    sectors: list[SectorPerformance] = []
    for sym in SECTOR_SYMBOLS:
        info = SECTOR_ETFS.get(sym, {"name": sym, "description": ""})

        prices = df[sym].dropna() if sym in df.columns else pd.Series(dtype=float)
        price = float(prices.iloc[-1]) if len(prices) > 0 else 0.0

        r = returns.get(sym, {"change_1d": None, "change_1w": None, "change_1m": None})
        rs1 = rs_1d.get(sym)
        rs5 = rs_1w.get(sym)
        vol_ratio = volume_ratios.get(sym, 1.0)
        vol_latest = latest_volumes.get(sym, 0.0)
        mom = _compute_momentum(rs1, rs5)

        perf = SectorPerformance(
            symbol=sym,
            name=info["name"],
            description=info["description"],
            price=round(price, 2),
            change_1d=r.get("change_1d"),
            change_1w=r.get("change_1w"),
            change_1m=r.get("change_1m"),
            volume_1d=round(float(vol_latest), 0),
            volume_vs_avg=round(float(vol_ratio), 2),
            volume_vs_avg_1w=round(float(volume_ratios_1w.get(sym, 1.0)), 2),
            relative_strength_1d=round(rs1, 3) if rs1 is not None else None,
            relative_strength_1w=round(rs5, 3) if rs5 is not None else None,
            momentum_score=round(mom, 1),
            trend=_detect_trend(r.get("change_1d"), r.get("change_1w")),
            flow_signal="neutral",
            flow_strength=0,
        )

        flow_dir, flow_str = _compute_flow_signal(
            perf.change_1d, perf.volume_vs_avg, perf.relative_strength_1d
        )
        perf.flow_signal = flow_dir
        perf.flow_strength = flow_str

        # Weekly flow signal
        flow_1w_dir, flow_1w_str = _compute_flow_signal(
            perf.change_1w, perf.volume_vs_avg_1w, perf.relative_strength_1w
        )
        perf.flow_signal_1w = flow_1w_dir
        perf.flow_strength_1w = flow_1w_str

        sectors.append(perf)

    return sectors


# ── Routes ───────────────────────────────────────────────────────────────


@router.get("")
async def get_sector_rotation() -> ApiResponse[SectorRotationResponse]:
    """Get current sector rotation snapshot with 1D/1W performance, RS rankings, and smart money flow signals."""
    start = datetime.now(UTC)

    df, volume_ratios, latest_volumes, volume_ratios_1w = _get_cached_sector_data()
    if df.empty or len(df.columns) < 2:
        log.warning("sector_rotation_no_data")
        return ApiResponse(
            data=SectorRotationResponse(
                sectors=[],
                leaders=[],
                laggards=[],
                rotation_phase="unknown",
                market_regime="unknown",
                timestamp=start.isoformat(),
            ),
            meta=MetaInfo(request_id="", duration_ms=0),
        )

    sectors = _build_sector_performances(df, volume_ratios, latest_volumes, volume_ratios_1w)

    # Sort by momentum for leaders/laggards
    sorted_by_mom = sorted(sectors, key=lambda s: s.momentum_score or 0, reverse=True)
    leaders = [s.symbol for s in sorted_by_mom[:3]]
    laggards = [s.symbol for s in sorted_by_mom[-3:]]

    market_regime = _detect_market_regime(sectors)
    rotation_phase = _determine_rotation_phase(sectors, market_regime=market_regime)

    duration = (datetime.now(UTC) - start).total_seconds() * 1000

    return ApiResponse(
        data=SectorRotationResponse(
            sectors=sectors,
            leaders=leaders,
            laggards=laggards,
            rotation_phase=rotation_phase,
            market_regime=market_regime,
            timestamp=start.isoformat(),
        ),
        meta=MetaInfo(request_id="", duration_ms=round(duration, 1)),
    )


@router.get("/history")
async def get_rotation_history() -> ApiResponse[list[RotationHistoryPoint]]:
    """Get historical sector rotation rankings for charting."""
    start = datetime.now(UTC)

    df, _volume_ratios, _latest_volumes, _volume_ratios_1w = _get_cached_sector_data()
    if df.empty or len(df.columns) < 2:
        return ApiResponse(data=[], meta=MetaInfo(request_id="", duration_ms=0))

    history: list[RotationHistoryPoint] = []
    # Compute rolling relative strength at each point
    for i in range(6, len(df)):
        window = df.iloc[: i + 1]
        rankings: dict[str, float] = {}
        for sym in SECTOR_SYMBOLS:
            col = window[sym].dropna()
            if len(col) >= 2:
                chg = (col.iloc[-1] - col.iloc[-2]) / col.iloc[-2] * 100
                rankings[sym] = round(chg, 2)
            else:
                rankings[sym] = 0.0

        ts = str(window["timestamp"].iloc[-1])
        history.append(RotationHistoryPoint(date=ts, sector_rankings=rankings))

    duration = (datetime.now(UTC) - start).total_seconds() * 1000

    return ApiResponse(
        data=history,
        meta=MetaInfo(request_id="", duration_ms=round(duration, 1)),
    )


@router.get("/{symbol}")
async def get_sector_detail(symbol: str) -> ApiResponse[SectorDetail | None]:
    """Get detailed data for a specific sector ETF including price history and RS history."""
    sym = symbol.upper()
    if sym not in SECTOR_ETFS:
        return ApiResponse(data=None, meta=MetaInfo(request_id="", duration_ms=0))

    start = datetime.now(UTC)
    info = SECTOR_ETFS[sym]

    # Fetch price + volume
    try:
        ticker = yf.Ticker(sym)
        hist = ticker.history(period="3mo", interval="1d")
    except Exception:
        log.exception("sector_detail_fetch_failed", symbol=sym)
        return ApiResponse(data=None, meta=MetaInfo(request_id="", duration_ms=0))

    if hist.empty:
        return ApiResponse(data=None, meta=MetaInfo(request_id="", duration_ms=0))

    hist = hist.reset_index()
    ts_col = "Datetime" if "Datetime" in hist.columns else "Date"

    price_history: list[dict[str, Any]] = []
    for _, row in hist.iterrows():
        price_history.append({
            "date": str(getattr(row, ts_col, "")),
            "close": float(row["Close"]) if "Close" in row else 0,
            "volume": float(row["Volume"]) if "Volume" in row else 0,
        })

    # Build performance from full data
    df, _vol_ratios, _latest_vols, _vol_ratios_1w = _get_cached_sector_data()
    returns = _compute_returns(df) if not df.empty else {}
    rs_1d = _compute_relative_strength(returns, "change_1d") if returns else {}
    rs_1w = _compute_relative_strength(returns, "change_1w") if returns else {}

    r = returns.get(sym, {})
    latest_close = float(hist["Close"].iloc[-1]) if "Close" in hist.columns else 0
    vol_latest = float(hist["Volume"].iloc[-1]) if "Volume" in hist.columns else 0
    vol_avg = float(hist["Volume"].tail(20).mean()) if len(hist) >= 20 else 1

    perf = SectorPerformance(
        symbol=sym,
        name=info["name"],
        description=info["description"],
        price=round(latest_close, 2),
        change_1d=r.get("change_1d"),
        change_1w=r.get("change_1w"),
        change_1m=r.get("change_1m"),
        volume_1d=round(float(vol_latest), 0),
        volume_vs_avg=round(float(vol_latest / vol_avg), 2) if vol_avg > 0 else None,
        relative_strength_1d=round(float(rs_1d.get(sym) or 0), 3) if rs_1d.get(sym) is not None else None,
        relative_strength_1w=round(float(rs_1w.get(sym) or 0), 3) if rs_1w.get(sym) is not None else None,
        momentum_score=round(_compute_momentum(rs_1d.get(sym), rs_1w.get(sym)), 1),
        trend=_detect_trend(r.get("change_1d"), r.get("change_1w")),
        flow_signal="neutral",
        flow_strength=0,
    )

    duration = (datetime.now(UTC) - start).total_seconds() * 1000

    return ApiResponse(
        data=SectorDetail(
            symbol=sym,
            name=info["name"],
            description=info["description"],
            performance=perf,
            price_history=price_history,
            relative_strength_history=[],
            components=[],
        ),
        meta=MetaInfo(request_id="", duration_ms=round(duration, 1)),
    )
