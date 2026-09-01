"""Lightweight macro context for ticker analysis.

Pulls VIX, SPY/QQQ close, dollar index, and the leading/lagging sector
ETFs on demand with a 60s in-memory TTL cache. Independent of the
morning-brief service to avoid circular dependencies and unnecessary
fan-out (the morning brief computes ~50 fields; we need ~5).

This is the "what's the market doing RIGHT NOW" layer that an elite
trader holds in their head when sizing and validating any trade.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from typing import Any

import yfinance as yf


# Symbols we pull — same set the morning brief's MarketInternals uses
_INDICES = {
    "vix": "^VIX",
    "spy": "SPY",
    "qqq": "QQQ",
    "dxy": "DX-Y.NYB",
}

# Sector ETFs — used to compute "is my sector leading or lagging"
_SECTOR_ETFS = [
    "XLE", "XLF", "XLV", "XLY", "XLP", "XLI", "XLB", "XLK",
    "XLU", "XBI", "XHB", "XRT",
]


@dataclass
class MacroContext:
    """Lightweight market snapshot — what the elite trader knows before
    placing a trade.

    All fields optional so a partial yfinance outage doesn't kill the
    ticker verdict (the verdict just shows less context).
    """
    timestamp: float = field(default_factory=time.time)
    vix: float | None = None           # < 15 = calm, 15-20 = normal, 20-30 = elevated, > 30 = fear
    spy_close: float | None = None
    qqq_close: float | None = None
    dxy: float | None = None            # dollar index (rising = risk-off, falling = risk-on)
    spy_change_1d_pct: float | None = None  # today's move
    qqq_change_1d_pct: float | None = None
    sector_1d_pct: dict[str, float] = field(default_factory=dict)
    # Sorted: best sector first, worst last
    leading_sector: str | None = None
    leading_sector_1d_pct: float | None = None
    lagging_sector: str | None = None
    lagging_sector_1d_pct: float | None = None
    # Convenience flag — derived from VIX
    risk_regime: str = "unknown"  # "calm" / "normal" / "elevated" / "fear"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ── 60s TTL cache (process-local) ──
_cached: MacroContext | None = None
_cached_at: float = 0.0
_CACHE_TTL = 60.0  # seconds


def _fetch_one(symbol: str) -> float | None:
    """Last close for a single index/ETF. Returns None on failure."""
    try:
        h = yf.Ticker(symbol).history(period="5d", interval="1d")
        if h is None or h.empty:
            return None
        return float(h["Close"].iloc[-1])
    except Exception:
        return None


def _pct_change(symbol: str) -> float | None:
    """1-day % change for an index/ETF."""
    try:
        h = yf.Ticker(symbol).history(period="5d", interval="1d")
        if h is None or len(h) < 2:
            return None
        prev = float(h["Close"].iloc[-2])
        last = float(h["Close"].iloc[-1])
        if prev == 0:
            return None
        return (last / prev - 1) * 100
    except Exception:
        return None


def _classify_vix(vix: float | None) -> str:
    if vix is None:
        return "unknown"
    if vix < 15:
        return "calm"
    if vix < 20:
        return "normal"
    if vix < 30:
        return "elevated"
    return "fear"


def get_macro_context(force_refresh: bool = False) -> MacroContext:
    """Return a fresh (or cached) macro context. Cached for 60s by default.

    Lazy and forgiving: if any single fetch fails, the field is None
    and the rest of the context is still useful. The ticker verdict
    should treat None fields as "no signal" — not as a negative.
    """
    global _cached, _cached_at
    now = time.monotonic()
    if not force_refresh and _cached is not None and (now - _cached_at) < _CACHE_TTL:
        return _cached

    ctx = MacroContext()
    # VIX + indices
    ctx.vix = _fetch_one(_INDICES["vix"])
    ctx.spy_close = _fetch_one(_INDICES["spy"])
    ctx.qqq_close = _fetch_one(_INDICES["qqq"])
    ctx.dxy = _fetch_one(_INDICES["dxy"])
    ctx.spy_change_1d_pct = _pct_change(_INDICES["spy"])
    ctx.qqq_change_1d_pct = _pct_change(_INDICES["qqq"])
    ctx.risk_regime = _classify_vix(ctx.vix)

    # Sector ETFs — find leader and lagger
    sector_pcts: dict[str, float] = {}
    for etf in _SECTOR_ETFS:
        pct = _pct_change(etf)
        if pct is not None:
            sector_pcts[etf] = pct
    ctx.sector_1d_pct = sector_pcts
    if sector_pcts:
        leader = max(sector_pcts, key=lambda k: sector_pcts[k])
        lagger = min(sector_pcts, key=lambda k: sector_pcts[k])
        ctx.leading_sector = leader
        ctx.leading_sector_1d_pct = sector_pcts[leader]
        ctx.lagging_sector = lagger
        ctx.lagging_sector_1d_pct = sector_pcts[lagger]

    _cached = ctx
    _cached_at = now
    return ctx


def clear_cache() -> None:
    """For tests: force the next call to refetch."""
    global _cached, _cached_at
    _cached = None
    _cached_at = 0.0
