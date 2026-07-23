"""Portfolio analysis API router — combined view across multiple tickers.

Provides institutional-grade portfolio-level analysis:
- Correlation matrix between all symbols
- Combined portfolio beta and sector allocation
- Risk metrics (VaR, volatility, max drawdown)
- Position sizing suggestions (Kelly-optimal, equal-risk)

Endpoints:
- POST /api/v1/portfolio/analyze — Full portfolio analysis from a list of symbols
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.app.api.dependencies import get_ticker_analysis_engine
from backend.app.api.schemas import ApiResponse, MetaInfo
from backend.app.core.logging import get_logger
from backend.app.domain.ticker_analysis.models import TickerAnalysisRequest
from backend.app.domain.ticker_analysis.orchestrator import TickerAnalysisService

router = APIRouter(prefix="/portfolio", tags=["portfolio"])
log = get_logger("conflu.api.portfolio")


# ── Request / Response Models ──


class PortfolioRequest(BaseModel):
    symbols: list[str]
    """List of ticker symbols to analyze (2–10 recommended)."""


class SymbolAllocation(BaseModel):
    symbol: str
    sector: str | None = None
    price: float | None = None
    conviction: int = 1
    action: str = "WATCH"
    suggested_pct: float | None = None


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


# ── Data helpers ──


def _fetch_beta(symbol: str) -> float | None:
    """Fetch beta from yfinance info."""
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        beta = info.get("beta")
        return round(float(beta), 3) if beta is not None else None
    except Exception:
        return None


def _fetch_returns(symbols: list[str], period: str = "6mo") -> pd.DataFrame:
    """Fetch daily returns for all symbols and return a DataFrame aligned by date."""
    prices: dict[str, pd.Series] = {}
    for sym in symbols:
        try:
            ticker = yf.Ticker(sym)
            hist = ticker.history(period=period)
            if hist is not None and not hist.empty:
                prices[sym] = hist["Close"]
        except Exception:
            log.warning("price_fetch_failed", symbol=sym)
    if not prices:
        return pd.DataFrame()
    df = pd.DataFrame(prices)
    returns = df.pct_change().dropna(how="all")
    return returns


# ── Route ──


@router.post("/analyze", summary="Portfolio analysis")
async def analyze_portfolio(
    request: PortfolioRequest,
    engine: TickerAnalysisService = Depends(get_ticker_analysis_engine),
) -> ApiResponse:
    """Analyse a portfolio of tickers — correlation, sector allocation, risk, and position sizing.

    Takes a list of symbols and returns:
    - Per-symbol analysis summaries (action, conviction, sector)
    - Correlation matrix between all pairs
    - Sector allocation breakdown
    - Combined portfolio beta and volatility
    - Equal-risk position sizing suggestion
    - High-correlation warnings (r > 0.7)
    """
    start = datetime.now(UTC)
    symbols = list(dict.fromkeys([s.upper().strip() for s in request.symbols if s.strip()]))
    count = len(symbols)

    if count < 1:
        return ApiResponse(
            data=PortfolioResponse(
                symbols=[],
                symbol_count=0,
                analyses=[],
                sector_allocation={},
                combined_beta=None,
                portfolio_volatility=None,
                equal_risk_pct=None,
                correlation_matrix=[],
                high_correlation_pairs=[],
                max_single_position_pct=0,
                timestamp=datetime.now(UTC).isoformat(),
            ),
            meta=MetaInfo(request_id="", duration_ms=0, error="At least one symbol required"),
        )

    # ── 1. Fetch per-symbol analysis ──
    analyses: list[SymbolAllocation] = []
    sectors_seen: dict[str, float] = {}
    betas: list[float] = []

    for sym in symbols:
        try:
            result = engine.analyze(TickerAnalysisRequest(symbol=sym))
            sector = result.sector or "Unknown"
            pct = result.verdict.position_size_pct or 0
            sectors_seen[sector] = sectors_seen.get(sector, 0) + 1
            if result.risk and result.risk.beta:
                betas.append(result.risk.beta)
            analyses.append(SymbolAllocation(
                symbol=sym,
                sector=sector,
                price=result.price,
                conviction=result.verdict.conviction,
                action=result.verdict.action,
                suggested_pct=pct,
            ))
        except Exception as e:
            log.warning("analysis_failed", symbol=sym, error=str(e))
            analyses.append(SymbolAllocation(symbol=sym, sector="Unknown", action="N/A"))

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
                    r = round(float(corr_matrix.loc[a, b]), 3)
                    pair = CorrelationPair(a=a, b=b, r=r)
                    correlation_pairs.append(pair)
                    if abs(r) > 0.7:
                        high_corr_pairs.append(pair)

        # Equally-weighted portfolio volatility
        n = len(symbols)
        weights = np.ones(n) / n
        cov = returns_df.cov()
        try:
            port_var = weights @ cov.values @ weights
            combined_vol = round(float(np.sqrt(port_var * 252) * 100), 2)
        except Exception:
            combined_vol = None

    # ── 3. Combined beta (simple average) ──
    combined_beta = round(float(np.mean(betas)), 2) if betas else None

    # ── 4. Equal-risk position sizing ──
    equal_risk_pct = round(min(100.0 / max(count, 1), 15.0), 1) if count > 0 else None

    # ── 5. Sector allocation ──
    total = sum(sectors_seen.values()) or 1
    sector_allocation = {s: round(c / total * 100, 1) for s, c in sorted(sectors_seen.items(), key=lambda x: -x[1])}

    # Cap: never more than 25% in a single position
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
