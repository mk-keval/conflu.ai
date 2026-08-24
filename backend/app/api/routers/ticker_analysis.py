"""Ticker analysis API router.

Provides programmatic elite-trader-grade analysis of individual tickers,
covering technical indicators, fundamentals, earnings, sentiment, and risk,
with a synthesized actionable verdict (BUY/SELL/HOLD/WATCH).

- POST /api/v1/ticker/{symbol}/analyze  — Full multi-module ticker analysis
- GET  /api/v1/ticker/{symbol}/options  — Options chain from Yahoo Finance
- GET  /api/v1/ticker/{symbol}/options-flow  — Enhanced options flow analysis
- GET  /api/v1/ticker/{symbol}/news     — News/catalyst feed from Yahoo Finance
- GET  /api/v1/ticker/{symbol}/chart    — Intraday chart data from Yahoo Finance
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any, Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, Query

from backend.app.api.dependencies import get_ticker_analysis_engine
from backend.app.api.schemas import ApiResponse, MetaInfo
from backend.app.core.logging import get_logger
from backend.app.domain.ticker_analysis.models import TickerAnalysisRequest
from backend.app.domain.ticker_analysis.orchestrator import TickerAnalysisService

router = APIRouter(prefix="/ticker", tags=["ticker"])
log = get_logger("conflu.api.ticker_analysis")


@router.post(
    "/{symbol}/analyze",
    summary="Full ticker analysis",
    description="Run the complete ticker analysis pipeline — technical, fundamental, earnings, "
    "sentiment, and risk — and return a synthesized verdict (BUY/SELL/HOLD/WATCH) "
    "with entry zone, stop loss, targets, triggers, and thesis.",
    status_code=200,
)
async def analyze_ticker(
    symbol: str,
    request: TickerAnalysisRequest,
    engine: TickerAnalysisService = Depends(get_ticker_analysis_engine),
) -> ApiResponse:
    """Run the full ticker analysis pipeline for a single symbol.

    Uses:
    - yfinance for fundamental/earnings/sentiment data (5-min in-memory cache)
    - TradingView screener for technical data (passed via tv_data)
    - In-memory synthesis engine for verdict generation

    Returns 200 with `TickerAnalysisResponse`-shaped data on success.
    Returns 200 with `error` field if the symbol cannot be resolved.
    """
    log.info("ticker_analysis_requested", symbol=symbol)

    # P3: async entry — pipeline makes blocking upstream calls; running it
    # via to_thread keeps the event loop responsive (D-31 discipline).
    result = await engine.analyze_async(request)

    return ApiResponse(
        data=result.model_dump(mode="json") if hasattr(result, "model_dump") else result,
        meta=MetaInfo(timestamp=datetime.now(UTC).isoformat()),
    )


# ── Yahoo Finance supplemental endpoints ──

import time
import yfinance as yf
from functools import lru_cache

# Simple in-memory TTL cache
_OPTIONS_CACHE: dict[str, tuple[float, dict]] = {}
_NEWS_CACHE: dict[str, tuple[float, list]] = {}
_CHART_CACHE: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 300.0  # 5 minutes


def _get_cached_or_fetch(cache: dict, key: str, fetch_fn):
    now = time.time()
    if key in cache:
        cached_time, data = cache[key]
        if now - cached_time < _CACHE_TTL:
            return data
    data = fetch_fn()
    cache[key] = (now, data)
    return data


@router.get(
    "/{symbol}/options",
    summary="Options chain from Yahoo Finance",
    description="Fetch options chain data including strikes, IV, Greeks, and open interest for a given expiry.",
)
async def get_options_chain(
    symbol: str,
    expiry: Optional[str] = Query(None, description="Expiry date YYYY-MM-DD. Defaults to nearest Friday."),
) -> ApiResponse:
    """Get options chain from Yahoo Finance."""
    def _fetch():
        ticker = yf.Ticker(symbol.upper())
        expiries = ticker.options
        if not expiries:
            return {"error": "No options data available", "symbol": symbol.upper()}
        
        # Use provided expiry or nearest
        target_expiry = expiry or expiries[0]
        if target_expiry not in expiries:
            target_expiry = expiries[0]
        
        try:
            chain = ticker.option_chain(target_expiry)
        except Exception as e:
            log.warning("option_chain_failed", symbol=symbol, expiry=target_expiry, error=str(e))
            return {"error": f"Failed to fetch options chain: {str(e)}", "symbol": symbol.upper()}
        
        def process_contracts(df, opt_type):
            return [
                {
                    "strike": float(row.strike),
                    "lastPrice": float(row.lastPrice) if pd.notna(row.lastPrice) else 0,
                    "bid": float(row.bid) if pd.notna(row.bid) else 0,
                    "ask": float(row.ask) if pd.notna(row.ask) else 0,
                    "impliedVolatility": float(row.impliedVolatility) if pd.notna(row.impliedVolatility) else 0,
                    "volume": int(row.volume) if pd.notna(row.volume) else 0,
                    "openInterest": int(row.openInterest) if pd.notna(row.openInterest) else 0,
                    "delta": float(row.get('delta', 0)) if hasattr(row, 'delta') and pd.notna(row.get('delta')) else None,
                    "gamma": float(row.get('gamma', 0)) if hasattr(row, 'gamma') and pd.notna(row.get('gamma')) else None,
                    "theta": float(row.get('theta', 0)) if hasattr(row, 'theta') and pd.notna(row.get('theta')) else None,
                    "vega": float(row.get('vega', 0)) if hasattr(row, 'vega') and pd.notna(row.get('vega')) else None,
                }
                for _, row in df.iterrows()
            ]
        
        calls = process_contracts(chain.calls, 'call')
        puts = process_contracts(chain.puts, 'put')
        
        # Get spot price
        hist = ticker.history(period="1d")
        spot = float(hist['Close'].iloc[-1]) if not hist.empty else 0
        
        # --- Advanced Metrics ---
        
        # 1. IV Rank (placeholder)
        all_iv = [c['impliedVolatility'] for c in calls if c['impliedVolatility'] > 0] + \
                 [p['impliedVolatility'] for p in puts if p['impliedVolatility'] > 0]
        iv_mean = np.mean(all_iv) if all_iv else 0
        iv_rank = 50
        
        # 2. Max Pain
        def compute_max_pain(calls, puts):
            strikes = sorted(set([c['strike'] for c in calls] + [p['strike'] for p in puts]))
            min_pain = float('inf')
            max_pain_strike = strikes[0] if strikes else 0
            for strike in strikes:
                pain = 0
                for c in calls:
                    if c['strike'] < strike:
                        pain += (strike - c['strike']) * c['openInterest']
                for p in puts:
                    if p['strike'] > strike:
                        pain += (p['strike'] - strike) * p['openInterest']
                if pain < min_pain:
                    min_pain = pain
                    max_pain_strike = strike
            return max_pain_strike
        
        max_pain = compute_max_pain(calls, puts)
        
        # 3. GEX (Gamma Exposure) by strike
        def compute_gex(calls, puts, spot):
            gex_by_strike = {}
            for c in calls:
                if c['gamma'] and c['openInterest'] > 0:
                    gex = c['gamma'] * c['openInterest'] * 100 * spot * 0.01
                    gex_by_strike[c['strike']] = gex_by_strike.get(c['strike'], 0) + gex
            for p in puts:
                if p['gamma'] and p['openInterest'] > 0:
                    gex = -p['gamma'] * p['openInterest'] * 100 * spot * 0.01
                    gex_by_strike[p['strike']] = gex_by_strike.get(p['strike'], 0) + gex
            return gex_by_strike
        
        gex_by_strike = compute_gex(calls, puts, spot)
        total_gex = sum(gex_by_strike.values())
        
        # GEX Flip level
        sorted_strikes = sorted(gex_by_strike.keys())
        gex_flip = None
        for strike in sorted_strikes:
            if gex_by_strike[strike] > 0 and strike > spot:
                gex_flip = strike
                break
        
        # 4. Put/Call Ratio
        total_call_oi = sum(c['openInterest'] for c in calls)
        total_put_oi = sum(p['openInterest'] for p in puts)
        pcr = total_put_oi / total_call_oi if total_call_oi > 0 else 0
        
        # 5. Unusual Volume (volume > 2x OI)
        unusual_calls = [c for c in calls if c['volume'] > 2 * c['openInterest'] and c['openInterest'] > 0]
        unusual_puts = [p for p in puts if p['volume'] > 2 * p['openInterest'] and p['openInterest'] > 0]
        
        # High OI strikes
        high_oi_calls = sorted(calls, key=lambda x: x['openInterest'], reverse=True)[:5]
        high_oi_puts = sorted(puts, key=lambda x: x['openInterest'], reverse=True)[:5]
        
        # Term structure (IV by expiry)
        term_structure = {}
        for exp in expiries[:6]:
            try:
                ch = ticker.option_chain(exp)
                all_iv_t = [c['impliedVolatility'] for c in ch.calls.to_dict('records') if c.get('impliedVolatility', 0) > 0] + \
                           [p['impliedVolatility'] for p in ch.puts.to_dict('records') if p.get('impliedVolatility', 0) > 0]
                if all_iv_t:
                    term_structure[exp] = round(np.mean(all_iv_t), 4)
            except Exception:
                pass
        
        return {
            "symbol": symbol.upper(),
            "expiry": target_expiry,
            "spot": spot,
            "calls": calls,  # Full contracts for frontend table rendering
            "puts": puts,
            "ivRank": iv_rank,
            "ivMean": round(iv_mean, 4),
            "maxPain": max_pain,
            "gammaExposure": round(total_gex, 2),  # Alias for frontend interface
            "gexTotal": round(total_gex, 2),
            "gexFlip": gex_flip,
            "gexByStrike": {str(k): round(v, 2) for k, v in gex_by_strike.items()},
            "putCallRatio": round(pcr, 2),
            "unusualActivity": {
                "calls": [{"strike": c['strike'], "volume": c['volume'], "oi": c['openInterest'], "iv": round(c['impliedVolatility'], 4)} for c in unusual_calls[:10]],
                "puts": [{"strike": p['strike'], "volume": p['volume'], "oi": p['openInterest'], "iv": round(p['impliedVolatility'], 4)} for p in unusual_puts[:10]],
            },
            "keyLevels": {
                "maxPain": max_pain,
                "gexFlip": gex_flip,
                "highOICalls": [{"strike": c['strike'], "oi": c['openInterest']} for c in high_oi_calls],
                "highOIPuts": [{"strike": p['strike'], "oi": p['openInterest']} for p in high_oi_puts],
            },
            "termStructure": term_structure,
            "totalCallOI": total_call_oi,
            "totalPutOI": total_put_oi,
            "availableExpiries": expiries,
        }
    
    data = _get_cached_or_fetch(_OPTIONS_CACHE, f"{symbol}:{expiry}", _fetch)
    return ApiResponse(
        data=data,
        meta=MetaInfo(timestamp=datetime.now(UTC).isoformat()),
    )


@router.get(
    "/{symbol}/options-flow",
    summary="Enhanced options flow analysis",
    description="Compute advanced options metrics: GEX flip levels, max pain magnet, IV rank/percentile, unusual volume, dealer positioning, term structure.",
)
async def get_options_flow(
    symbol: str,
    expiry: Optional[str] = Query(None, description="Expiry date YYYY-MM-DD. Defaults to nearest Friday."),
) -> ApiResponse:
    """Get enhanced options flow analysis with dealer positioning and flow metrics."""
    def _fetch():
        ticker = yf.Ticker(symbol.upper())
        expiries = ticker.options
        if not expiries:
            return {"error": "No options data available", "symbol": symbol.upper()}
        
        target_expiry = expiry or expiries[0]
        if target_expiry not in expiries:
            target_expiry = expiries[0]
        
        try:
            chain = ticker.option_chain(target_expiry)
        except Exception as e:
            log.warning("option_chain_failed", symbol=symbol, expiry=target_expiry, error=str(e))
            return {"error": f"Failed to fetch options chain: {str(e)}", "symbol": symbol.upper()}
        
        def process_contracts(df, opt_type):
            return [
                {
                    "strike": float(row.strike),
                    "lastPrice": float(row.lastPrice) if pd.notna(row.lastPrice) else 0,
                    "bid": float(row.bid) if pd.notna(row.bid) else 0,
                    "ask": float(row.ask) if pd.notna(row.ask) else 0,
                    "impliedVolatility": float(row.impliedVolatility) if pd.notna(row.impliedVolatility) else 0,
                    "volume": int(row.volume) if pd.notna(row.volume) else 0,
                    "openInterest": int(row.openInterest) if pd.notna(row.openInterest) else 0,
                    "delta": float(row.get('delta', 0)) if hasattr(row, 'delta') and pd.notna(row.get('delta')) else None,
                    "gamma": float(row.get('gamma', 0)) if hasattr(row, 'gamma') and pd.notna(row.get('gamma')) else None,
                    "theta": float(row.get('theta', 0)) if hasattr(row, 'theta') and pd.notna(row.get('theta')) else None,
                    "vega": float(row.get('vega', 0)) if hasattr(row, 'vega') and pd.notna(row.get('vega')) else None,
                }
                for _, row in df.iterrows()
            ]
        
        calls = process_contracts(chain.calls, 'call')
        puts = process_contracts(chain.puts, 'put')
        
        # Spot price
        hist = ticker.history(period="1d")
        spot = float(hist['Close'].iloc[-1]) if not hist.empty else 0
        
        # --- Advanced Metrics ---
        
        # 1. IV Rank (simplified - would need historical IV for true rank)
        all_iv = [c['impliedVolatility'] for c in calls if c['impliedVolatility'] > 0] + \
                 [p['impliedVolatility'] for p in puts if p['impliedVolatility'] > 0]
        iv_mean = np.mean(all_iv) if all_iv else 0
        iv_rank = 50  # Placeholder - needs historical IV data
        
        # 2. Max Pain
        def compute_max_pain(calls, puts):
            strikes = sorted(set([c['strike'] for c in calls] + [p['strike'] for p in puts]))
            min_pain = float('inf')
            max_pain_strike = strikes[0] if strikes else 0
            for strike in strikes:
                pain = 0
                for c in calls:
                    if c['strike'] < strike:
                        pain += (strike - c['strike']) * c['openInterest']
                for p in puts:
                    if p['strike'] > strike:
                        pain += (p['strike'] - strike) * p['openInterest']
                if pain < min_pain:
                    min_pain = pain
                    max_pain_strike = strike
            return max_pain_strike
        
        max_pain = compute_max_pain(calls, puts)
        
        # 3. GEX (Gamma Exposure) by strike
        def compute_gex(calls, puts, spot):
            gex_by_strike = {}
            for c in calls:
                if c['gamma'] and c['openInterest'] > 0:
                    gex = c['gamma'] * c['openInterest'] * 100 * spot * 0.01
                    gex_by_strike[c['strike']] = gex_by_strike.get(c['strike'], 0) + gex
            for p in puts:
                if p['gamma'] and p['openInterest'] > 0:
                    gex = -p['gamma'] * p['openInterest'] * 100 * spot * 0.01
                    gex_by_strike[p['strike']] = gex_by_strike.get(p['strike'], 0) + gex
            return gex_by_strike
        
        gex_by_strike = compute_gex(calls, puts, spot)
        total_gex = sum(gex_by_strike.values())
        
        # GEX Flip level (where GEX changes sign)
        sorted_strikes = sorted(gex_by_strike.keys())
        gex_flip = None
        for strike in sorted_strikes:
            if gex_by_strike[strike] > 0 and strike > spot:
                gex_flip = strike
                break
        
        # 4. Put/Call Ratio
        total_call_oi = sum(c['openInterest'] for c in calls)
        total_put_oi = sum(p['openInterest'] for p in puts)
        pcr = total_put_oi / total_call_oi if total_call_oi > 0 else 0
        
        # 5. Unusual Volume (volume > 2x OI)
        unusual_calls = [c for c in calls if c['volume'] > 2 * c['openInterest'] and c['openInterest'] > 100]
        unusual_puts = [p for p in puts if p['volume'] > 2 * p['openInterest'] and p['openInterest'] > 100]
        
        # 6. Dealer Positioning (Net GEX)
        net_gex = total_gex
        dealer_position = "long_gamma" if net_gex > 0 else "short_gamma"
        
        # 7. Key Levels from options
        # Max Pain as support/resistance
        # GEX flip as resistance
        # High OI strikes as magnets
        high_oi_calls = sorted(calls, key=lambda x: x['openInterest'], reverse=True)[:5]
        high_oi_puts = sorted(puts, key=lambda x: x['openInterest'], reverse=True)[:5]
        
        # 8. Term Structure (IV across expiries) - simplified
        term_structure = []
        for exp in expiries[:4]:
            try:
                ch = ticker.option_chain(exp)
                all_iv = [c['impliedVolatility'] for c in process_contracts(ch.calls, 'call') if c['impliedVolatility'] > 0] + \
                         [p['impliedVolatility'] for p in process_contracts(ch.puts, 'put') if p['impliedVolatility'] > 0]
                if all_iv:
                    term_structure.append({"expiry": exp, "iv_mean": round(np.mean(all_iv) * 100, 1)})
            except Exception:
                pass
        
        return {
            "symbol": symbol.upper(),
            "expiry": target_expiry,
            "spot": spot,
            "calls": calls,
            "puts": puts,
            "ivRank": iv_rank,
            "ivMean": round(iv_mean * 100, 1),
            "maxPain": max_pain,
            "maxPainDistancePct": round((max_pain / spot - 1) * 100, 2) if spot else 0,
            "gammaExposure": {
                "total": round(total_gex, 2),
                "byStrike": {str(k): round(v, 2) for k, v in gex_by_strike.items()},
                "flipLevel": gex_flip,
                "dealerPosition": dealer_position,
            },
            "putCallRatio": round(pcr, 2),
            "unusualActivity": {
                "calls": [{"strike": c['strike'], "volume": c['volume'], "oi": c['openInterest'], "iv": c['impliedVolatility']} for c in unusual_calls[:10]],
                "puts": [{"strike": p['strike'], "volume": p['volume'], "oi": p['openInterest'], "iv": p['impliedVolatility']} for p in unusual_puts[:10]],
            },
            "keyLevels": {
                "maxPain": max_pain,
                "gexFlip": gex_flip,
                "highOICalls": [{"strike": c['strike'], "oi": c['openInterest']} for c in high_oi_calls],
                "highOIPuts": [{"strike": p['strike'], "oi": p['openInterest']} for p in high_oi_puts],
            },
            "termStructure": term_structure,
            "totalCallOI": total_call_oi,
            "totalPutOI": total_put_oi,
            "availableExpiries": expiries,
        }
    
    data = _get_cached_or_fetch(_OPTIONS_CACHE, f"{symbol}:{expiry or 'auto'}:flow", _fetch)
    return ApiResponse(
        data=data,
        meta=MetaInfo(timestamp=datetime.now(UTC).isoformat()),
    )


@router.get(
    "/{symbol}/news",
    summary="News/catalyst feed from Yahoo Finance",
    description="Fetch recent news headlines with sentiment scoring for a ticker.",
)
async def get_news(
    symbol: str,
    limit: int = Query(20, ge=1, le=50, description="Number of news items to return"),
) -> ApiResponse:
    """Get news feed from Yahoo Finance with basic sentiment scoring."""
    def _extract_news_item(item: dict) -> dict:
        """Normalize a yfinance news item across schema generations.

        Legacy schema (yfinance < 0.2.50): flat keys — title / link /
        publisher / providerPublishTime.
        Current schema: nested under 'content' — content.title,
        content.clickThroughUrl.url (or content.canonicalUrl.url),
        content.provider.displayName, content.pubTime (ISO-8601).
        Missing URLs are common when Yahoo omits clickThroughUrl; the
        frontend renders those as non-clickable headlines.
        """
        content = item.get("content") if isinstance(item.get("content"), dict) else None

        if content is not None:
            title = content.get("title") or item.get("title", "")
            provider = content.get("provider") or {}
            publisher = (
                provider.get("displayName")
                if isinstance(provider, dict)
                else None
            ) or item.get("publisher", "")
            link = ""
            for url_key in ("clickThroughUrl", "canonicalUrl"):
                url_obj = content.get(url_key)
                if isinstance(url_obj, dict) and url_obj.get("url"):
                    link = url_obj["url"]
                    break
            if not link and isinstance(content.get("url"), str):
                link = content["url"]
            pub_time_raw = content.get("pubTime") or item.get("providerPublishTime", 0)
            timestamp = 0
            date_iso: str | None = None
            if isinstance(pub_time_raw, (int, float)) and pub_time_raw:
                timestamp = int(pub_time_raw)
            elif isinstance(pub_time_raw, str) and pub_time_raw:
                try:
                    timestamp = int(datetime.fromisoformat(
                        pub_time_raw.replace("Z", "+00:00")
                    ).timestamp())
                except ValueError:
                    timestamp = 0
        else:
            title = item.get("title", "")
            publisher = item.get("publisher", "")
            link = item.get("link", "") or ""
            timestamp = int(item.get("providerPublishTime", 0) or 0)
            date_iso = None

        return {
            "title": title,
            "publisher": publisher,
            "link": link,
            "timestamp": timestamp,
            "date": (
                datetime.fromtimestamp(timestamp, UTC).isoformat()
                if timestamp
                else date_iso
            ),
        }

    def _fetch():
        ticker = yf.Ticker(symbol.upper())
        news = ticker.news
        if not news:
            return {"symbol": symbol.upper(), "items": []}
        
        # Simple sentiment keywords
        positive_words = ['beat', 'exceed', 'strong', 'growth', 'record', 'upgrade', 'buy', 'bullish', 
                          'surge', 'rally', 'gain', 'profit', 'revenue', 'partnership', 'approval',
                          'milestone', 'success', 'positive', 'outperform', 'raise', 'increase']
        negative_words = ['miss', 'weak', 'decline', 'drop', 'fall', 'downgrade', 'sell', 'bearish',
                          'loss', 'cut', 'reduce', 'lower', 'warning', 'risk', 'concern', 'fail',
                          'delay', 'negative', 'underperform', 'decrease', 'lawsuit', 'investigation']
        
        def score_sentiment(text):
            text_lower = text.lower()
            pos = sum(1 for w in positive_words if w in text_lower)
            neg = sum(1 for w in negative_words if w in text_lower)
            if pos > neg:
                return "positive"
            elif neg > pos:
                return "negative"
            return "neutral"
        
        items = []
        for raw in news[:limit]:
            normalized = _extract_news_item(raw)
            normalized["sentiment"] = score_sentiment(normalized["title"])
            items.append(normalized)
        
        return {
            "symbol": symbol.upper(),
            "items": items,
            "count": len(items),
        }
    
    data = _get_cached_or_fetch(_NEWS_CACHE, f"{symbol}:{limit}", _fetch)
    return ApiResponse(
        data=data,
        meta=MetaInfo(timestamp=datetime.now(UTC).isoformat()),
    )


@router.get(
    "/{symbol}/chart",
    summary="Intraday chart data from Yahoo Finance",
    description="Fetch intraday OHLCV data for charting. Supports 5m, 15m, 1h, 4h, 1d intervals.",
)
async def get_chart_data(
    symbol: str,
    interval: str = Query("5m", pattern="^(5m|15m|1h|4h|1d)$", description="Time interval"),
    time_range: str = Query("1d", pattern="^(1d|5d|1mo|3mo|6mo|1y|2y|5y|10y|ytd|max)$", description="Time range"),
) -> ApiResponse:
    """Get intraday chart data from Yahoo Finance for Lightweight Charts."""
    def _fetch():
        ticker = yf.Ticker(symbol.upper())
        
        # Map range to period for yfinance
        period_map = {
            "1d": "1d", "5d": "5d", "1mo": "1mo", "3mo": "3mo",
            "6mo": "6mo", "1y": "1y", "2y": "2y", "5y": "5y", "10y": "10y", "ytd": "ytd", "max": "max"
        }
        
        # For intraday intervals, limit range
        use_range = time_range
        if interval in ["5m", "15m", "1h", "4h"] and time_range in ["1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"]:
            # Yahoo only provides 7d for 5m/15m, 60d for 1h, 730d for 4h
            use_range = "5d" if interval in ["5m", "15m"] else "1mo" if interval == "1h" else "3mo"
        
        df = ticker.history(period=use_range, interval=interval)
        
        if df.empty:
            return {"symbol": symbol.upper(), "interval": interval, "range": use_range, "data": []}
        
        df = df.reset_index()
        ts_col = 'Datetime' if 'Datetime' in df.columns else 'Date'
        
        data = []
        for _, row in df.iterrows():
            data.append({
                "time": int(row[ts_col].timestamp()),
                "open": float(row['Open']),
                "high": float(row['High']),
                "low": float(row['Low']),
                "close": float(row['Close']),
                "volume": int(row['Volume']),
            })
        
        return {
            "symbol": symbol.upper(),
            "interval": interval,
            "range": use_range,
            "data": data,
        }
    
    cache_key = f"{symbol}:{interval}:{time_range}"
    data = _get_cached_or_fetch(_CHART_CACHE, cache_key, _fetch)
    return ApiResponse(
        data=data,
        meta=MetaInfo(timestamp=datetime.now(UTC).isoformat()),
    )
