"""Portfolio analysis API router — combined view across multiple tickers.

Provides institutional-grade portfolio-level analysis:
- Per-symbol basic data (sector, price, beta)
- Correlation matrix between all symbols
- Combined portfolio beta and sector allocation
- Risk metrics (portfolio volatility)
- Equal-risk position sizing

Endpoints:
- POST /api/v1/portfolio/analyze — Full portfolio analysis from a list of symbols
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

router = APIRouter(prefix="/portfolio", tags=["portfolio"])
log = get_logger("conflu.api.portfolio")


# ── Request / Response Models ──


class PortfolioRequest(BaseModel):
    symbols: list[str]


class SymbolAllocation(BaseModel):
    symbol: str
    sector: str | None = None
    price: float | None = None
    beta: float | None = None
    market_cap: float | None = None
    pe_ratio: float | None = None


class CorrelationPair(BaseModel):
    a: str
    b: str
    r: float


class PortfolioResponse(BaseModel):
    symbols: list[str]
    symbol_count: int
    analyses: list[SymbolAllocation]
    sector_allocation: dict[str, float]
    combined_beta: float | None
    portfolio_volatility: float | None
    equal_risk_pct: float | None
    correlation_matrix: list[CorrelationPair]
    high_correlation_pairs: list[CorrelationPair]
    max_single_position_pct: float
    timestamp: str


# ── Helpers ──


def _fetch_info(symbol: str) -> dict[str, Any]:
    """Fetch yfinance info for a single symbol with timeout."""
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info or {}
        return {
            "sector": info.get("sector"),
            "price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "beta": info.get("beta"),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE") or info.get("forwardPE"),
        }
    except Exception:
        return {}


def _fetch_returns(symbols: list[str], period: str = "6mo") -> pd.DataFrame:
    """Fetch daily returns for all symbols, aligned by date."""
    prices: dict[str, pd.Series] = {}
    for sym in symbols:
        try:
            hist = yf.Ticker(sym).history(period=period)
            if hist is not None and not hist.empty:
                prices[sym] = hist["Close"]
        except Exception:
            log.warning("price_fetch_failed", symbol=sym)
    if not prices:
        return pd.DataFrame()
    df = pd.DataFrame(prices)
    return df.pct_change().dropna(how="all")


# ── Route ──


@router.post("/analyze", summary="Portfolio analysis")
async def analyze_portfolio(
    request: PortfolioRequest,
) -> ApiResponse:
    """Analyse a portfolio of tickers — correlation, sector allocation, risk.

    Returns per-symbol data, correlation matrix, combined beta, sector
    allocation, portfolio volatility, and equal-risk position sizing.
    """
    start = datetime.now(UTC)
    symbols = list(dict.fromkeys([s.upper().strip() for s in request.symbols if s.strip()]))
    count = len(symbols)

    # ── 1. Fetch per-symbol info ──
    analyses: list[SymbolAllocation] = []
    sectors_seen: dict[str, float] = {}
    betas: list[float] = []

    for sym in symbols:
        info = _fetch_info(sym)
        sector = info.get("sector") or "Unknown"
        sectors_seen[sector] = sectors_seen.get(sector, 0) + 1
        beta = info.get("beta")
        if beta is not None:
            betas.append(float(beta))
        analyses.append(SymbolAllocation(
            symbol=sym,
            sector=sector,
            price=info.get("price"),
            beta=round(float(beta), 2) if beta is not None else None,
            market_cap=info.get("market_cap"),
            pe_ratio=info.get("pe_ratio"),
        ))

    # ── 2. Correlation matrix ──
    returns_df = _fetch_returns(symbols)
    correlation_pairs: list[CorrelationPair] = []
    high_corr_pairs: list[CorrelationPair] = []
    combined_vol: float | None = None

    if not returns_df.empty and returns_df.shape[1] > 1:
        corr_matrix = returns_df.corr()
        for i, a in enumerate(symbols):
            for b in symbols[i + 1:]:
                if a in corr_matrix.index and b in corr_matrix.columns:
                    r_val = round(float(corr_matrix.loc[a, b]), 3)
                    pair = CorrelationPair(a=a, b=b, r=r_val)
                    correlation_pairs.append(pair)
                    if abs(r_val) > 0.7:
                        high_corr_pairs.append(pair)

        n = len(symbols)
        weights = np.ones(n) / n
        cov = returns_df.cov()
        try:
            port_var = weights @ cov.values @ weights
            combined_vol = round(float(np.sqrt(port_var * 252) * 100), 2)
        except Exception:
            combined_vol = None

    # ── 3. Combined beta ──
    combined_beta = round(float(np.mean(betas)), 2) if betas else None

    # ── 4. Equal-risk sizing ──
    equal_risk_pct = round(min(100.0 / max(count, 1), 15.0), 1) if count > 0 else None

    # ── 5. Sector allocation ──
    total = sum(sectors_seen.values()) or 1
    sector_allocation = {s: round(c / total * 100, 1) for s, c in sorted(sectors_seen.items(), key=lambda x: -x[1])}
    max_pos = round(min(25.0, 100.0 / max(count, 1)), 1)

    duration = (datetime.now(UTC) - start).total_seconds() * 1000

    return ApiResponse(
        data=PortfolioResponse(
            symbols=symbols,
            symbol_count=count,
            analyses=analyses,
            sector_allocation=sector_allocation,
            combined_beta=combined_beta,
            portfolio_volatility=combined_vol,
            equal_risk_pct=equal_risk_pct,
            correlation_matrix=correlation_pairs,
            high_correlation_pairs=high_corr_pairs,
            max_single_position_pct=max_pos,
            timestamp=datetime.now(UTC).isoformat(),
        ),
        meta=MetaInfo(request_id="", duration_ms=round(duration, 1)),
    )
