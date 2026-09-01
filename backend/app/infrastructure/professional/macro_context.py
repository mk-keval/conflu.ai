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

# yfinance returns sector names like "Technology", "Financial Services",
# "Consumer Cyclical", "Consumer Defensive" (note: NOT "Consumer Staples").
# We map them to the SPDR sector ETF that tracks each GICS sector.
# Real estate and biotech/financial subsectors get sub-sector ETFs
# (XLRE / XBI / KRE) where the SPDR is too broad.
_SECTOR_TO_ETF: dict[str, str] = {
    "Energy": "XLE",
    "Energy Minerals": "XLE",
    "Oil & Gas": "XLE",
    "Financial Services": "XLF",
    "Banks": "KRE",        # regional banks — sub-ETF since XLF is too broad
    "Insurance": "XLF",
    "Capital Markets": "XLF",
    "Health Care": "XLV",
    "Healthcare": "XLV",
    "Biotechnology": "XBI",  # sub-ETF since XLV mixes pharma + biotech
    "Pharmaceutical": "XLV",
    "Medical": "XLV",
    "Medical Devices": "XLV",
    "Technology": "XLK",
    "Information Technology": "XLK",
    "Software": "XLK",
    "Semiconductors": "XLK",
    "Communication Services": "XLC",
    "Telecommunications": "XLC",
    "Media": "XLC",
    "Consumer Cyclical": "XLY",
    "Consumer Discretionary": "XLY",
    "Automobiles": "XLY",
    "Retail": "XLY",
    "Hotels & Entertainment": "XLY",
    "Consumer Defensive": "XLP",
    "Consumer Staples": "XLP",
    "Beverages": "XLP",
    "Food": "XLP",
    "Household Products": "XLP",
    "Industrials": "XLI",
    "Aerospace & Defense": "ITA",  # sub-ETF (defense is a huge theme)
    "Transportation": "IYT",       # sub-ETF (railways + airlines)
    "Construction": "XHB",         # sub-ETF (homebuilders)
    "Machinery": "XLI",
    "Materials": "XLB",
    "Basic Materials": "XLB",
    "Metals & Mining": "XME",      # sub-ETF
    "Chemicals": "XLB",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "REITs": "XLRE",
}


def sector_to_etf(sector: str | None) -> str | None:
    """Map a yfinance sector string to the right SPDR/select-sector ETF.

    Returns None if the sector is unknown or not a US-equity sector.
    """
    if not sector:
        return None
    return _SECTOR_TO_ETF.get(sector)


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


# ── Sector-relative RS (D-46 PR 2) ──────────────────────────────────────
# An elite trader asks: "is this stock confirming the sector, or fighting it?"
# A name can look good on its own (RS vs SPY positive) but actually be
# LAGGING its sector — meaning the sector is carrying it. That's a weak
# signal. The opposite — outperforming the sector — is the elite trader's
# strongest confirmation that institutional money is targeting this name.

# Short-window cache for sector ETF prices (separate from macro context)
_sector_cache: dict[str, tuple[float, pd.DataFrame | None]] = {}
_SECTOR_CACHE_TTL = 300.0  # 5 minutes — sector data moves slower than VIX


def _fetch_sector_etf_history(etf: str) -> pd.DataFrame | None:
    """Cached yfinance history for a sector ETF (6mo daily for 1M and 3M windows)."""
    cached = _sector_cache.get(etf)
    now = time.monotonic()
    if cached is not None:
        cached_at, data = cached
        if (now - cached_at) < _SECTOR_CACHE_TTL:
            return data
    try:
        data = yf.Ticker(etf).history(period="6mo", interval="1d")
        if data is None or data.empty:
            return None
    except Exception:
        return None
    _sector_cache[etf] = (now, data)
    return data


def clear_sector_cache() -> None:
    """For tests: clear the sector ETF cache."""
    _sector_cache.clear()


@dataclass
class SectorRelativeRS:
    """Stock's relative strength vs its sector ETF.

    positive rs_vs_sector_1m = stock is OUTPERFORMING its sector over 1M
    negative rs_vs_sector_1m = stock is LAGGING its sector (looks strong in
                                isolation but the sector is doing the work)
    """
    sector_etf: str | None
    stock_return_1m_pct: float | None
    sector_return_1m_pct: float | None
    rs_vs_sector_1m_pct: float | None
    stock_return_3m_pct: float | None
    sector_return_3m_pct: float | None
    rs_vs_sector_3m_pct: float | None
    findings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _window_return(history: pd.DataFrame, days: int) -> float | None:
    """% return over the last `days` trading days. None if insufficient data."""
    if history is None or len(history) < days + 1:
        return None
    try:
        prev = float(history["Close"].iloc[-(days + 1)])
        last = float(history["Close"].iloc[-1])
        if prev == 0:
            return None
        return (last / prev - 1) * 100
    except Exception:
        return None


def compute_sector_relative_rs(
    symbol: str,
    sector: str | None,
    stock_history: pd.DataFrame | None,
) -> SectorRelativeRS:
    """Compute the stock's RS vs its sector ETF over 1M and 3M windows.

    Args:
        symbol: ticker (only used for findings text)
        sector: yfinance sector name (e.g. "Technology")
        stock_history: pre-fetched OHLCV for the stock (1y daily, or None)

    Returns: SectorRelativeRS with both windows + human-readable findings.
    """
    etf = sector_to_etf(sector)
    result = SectorRelativeRS(
        sector_etf=etf,
        stock_return_1m_pct=None, sector_return_1m_pct=None, rs_vs_sector_1m_pct=None,
        stock_return_3m_pct=None, sector_return_3m_pct=None, rs_vs_sector_3m_pct=None,
        findings=[],
    )

    if not etf:
        result.findings.append(
            f"⚠️ Unknown sector '{sector}' — cannot compute sector-relative RS"
        )
        return result

    sector_hist = _fetch_sector_etf_history(etf)
    if sector_hist is None:
        result.findings.append(f"⚠️ Sector ETF {etf} data unavailable")
        return result

    # Stock returns (1M = ~21 trading days, 3M = ~63)
    if stock_history is not None and len(stock_history) >= 64:
        result.stock_return_1m_pct = _window_return(stock_history, 21)
        result.stock_return_3m_pct = _window_return(stock_history, 63)
    # Sector returns
    if len(sector_hist) >= 64:
        result.sector_return_1m_pct = _window_return(sector_hist, 21)
        result.sector_return_3m_pct = _window_return(sector_hist, 63)

    # Compute relative RS
    if result.stock_return_1m_pct is not None and result.sector_return_1m_pct is not None:
        result.rs_vs_sector_1m_pct = round(
            result.stock_return_1m_pct - result.sector_return_1m_pct, 2
        )
    if result.stock_return_3m_pct is not None and result.sector_return_3m_pct is not None:
        result.rs_vs_sector_3m_pct = round(
            result.stock_return_3m_pct - result.sector_return_3m_pct, 2
        )

    # Generate findings — the elite trader's interpretation
    if result.rs_vs_sector_1m_pct is not None:
        if result.rs_vs_sector_1m_pct >= 5.0:
            result.findings.append(
                f"📈 Sector-relative RS: {symbol} outperforming {etf} by "
                f"+{result.rs_vs_sector_1m_pct:.1f}% over 1M — "
                f"institutional bid, elite trader's strongest confirmation"
            )
        elif result.rs_vs_sector_1m_pct <= -5.0:
            result.findings.append(
                f"⚠️ Sector-relative RS: {symbol} lagging {etf} by "
                f"{result.rs_vs_sector_1m_pct:.1f}% over 1M — "
                f"sector is carrying the stock, weak confirmation"
            )
        else:
            result.findings.append(
                f"📊 Sector-relative RS: {symbol} tracking {etf} (RS "
                f"{result.rs_vs_sector_1m_pct:+.1f}% over 1M)"
            )

    if result.rs_vs_sector_3m_pct is not None and abs(result.rs_vs_sector_3m_pct) >= 8.0:
        if result.rs_vs_sector_3m_pct > 0:
            result.findings.append(
                f"📈 3M outperformance: {symbol} +{result.rs_vs_sector_3m_pct:.1f}% vs {etf}"
            )
        else:
            result.findings.append(
                f"⚠️ 3M underperformance: {symbol} {result.rs_vs_sector_3m_pct:.1f}% vs {etf}"
            )

    return result
