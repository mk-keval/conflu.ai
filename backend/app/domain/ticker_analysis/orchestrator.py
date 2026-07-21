"""Ticker Analysis Orchestrator — fetches data, runs modules, returns verdict."""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime, timezone
from typing import Any

import yfinance as yf

from backend.app.core.logging import get_logger
from backend.app.domain.ticker_analysis import (
    earnings,
    fundamentals,
    risk as risk_module,
    sentiment,
    synthesis,
    technical,
    macro_overlay,
)
from backend.app.domain.ticker_analysis.models import (
    EarningsAnalysis,
    FundamentalAnalysis,
    RiskAssessment,
    SentimentAnalysis,
    TechnicalAnalysis,
    TickerAnalysisRequest,
    TickerAnalysisResponse,
    AnalysisVerdict,
)
from backend.app.api.schemas import ApiResponse

log = get_logger("conflu.ticker_analysis")

# Simple in-memory TTL cache for yfinance results
_INFO_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_CACHE_TTL = 300  # 5 minutes

# Macro regime cache
_MACRO_REGIME_CACHE: Any | None = None
_MACRO_REGIME_CACHE_TIME: float = 0.0
_MACRO_REGIME_CACHE_TTL = 3600.0  # 1 hour cache for market regime


async def _fetch_market_regime() -> Any | None:
    """Fetch current market regime, using cache if available."""
    global _MACRO_REGIME_CACHE, _MACRO_REGIME_CACHE_TIME

    # Lazy import to avoid circular import
    from backend.app.api.routers.regime import get_market_regime, MarketRegimeResponse

    now = time.monotonic()
    if _MACRO_REGIME_CACHE is not None and (now - _MACRO_REGIME_CACHE_TIME) < _MACRO_REGIME_CACHE_TTL:
        return _MACRO_REGIME_CACHE

    try:
        # Call the regime endpoint internally
        response: ApiResponse = await get_market_regime()
        if response.data:
            _MACRO_REGIME_CACHE = response.data
            _MACRO_REGIME_CACHE_TIME = now
            return response.data
    except Exception:
        log.exception("macro_regime_fetch_failed")

    return None


def _fetch_info(symbol: str) -> dict[str, Any]:
    """Fetch yfinance info dict with simple in-memory TTL cache.

    Avoids hammering yfinance for the same ticker within the TTL window.
    """
    now = time.time()
    cached = _INFO_CACHE.get(symbol)
    if cached and (now - cached[0]) < _CACHE_TTL:
        log.info("yfinance_cache_hit", symbol=symbol)
        return cached[1]

    log.info("yfinance_fetch", symbol=symbol)
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info or {}
        _INFO_CACHE[symbol] = (now, info)
        return info
    except Exception:
        log.exception("yfinance_fetch_failed", symbol=symbol)
        return {}


def _compute_missing_technicals(symbol: str, tv_data: dict[str, Any]) -> dict[str, Any]:
    """Compute RSI(14), ADX(14), and MACD(12,26,9) from yfinance OHLCV history
    when TV screener data is not available for these fields.

    Uses pandas_ta for accurate, industry-standard computation.
    Also computes SMA20 from the same OHLCV history when TV data doesn't provide it.
    Returns a flat dict with keys RSI, ADX, MACD.macd, MACD.signal, SMA20.
    """
    import pandas as pd  # noqa: PLC0415 — late import, not a hot path
    import pandas_ta as ta  # noqa: PLC0415

    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="6mo")
        if hist is None or len(hist) < 50:
            return {}

        result: dict[str, Any] = {}

        # RSI(14)
        if not tv_data.get("RSI"):
            rsi_series = ta.rsi(hist["Close"], length=14)
            if rsi_series is not None and len(rsi_series) > 0:
                last = rsi_series.iloc[-1]
                if not pd.isna(last):
                    result["RSI"] = round(float(last), 1)

        # ADX(14)
        if not tv_data.get("ADX"):
            adx_df = ta.adx(hist["High"], hist["Low"], hist["Close"], length=14)
            if adx_df is not None and len(adx_df) > 0:
                last = adx_df.iloc[-1]
                adx_val = last.get("ADX_14")
                if adx_val is not None and not pd.isna(adx_val):
                    result["ADX"] = round(float(adx_val), 1)

        # MACD(12,26,9)
        if not tv_data.get("MACD.macd"):
            macd_df = ta.macd(hist["Close"], fast=12, slow=26, signal=9)
            if macd_df is not None and len(macd_df) > 0:
                last = macd_df.iloc[-1]
                macd_line = last.get("MACD_12_26_9")
                macd_sig = last.get("MACDs_12_26_9")
                if macd_line is not None and not pd.isna(macd_line):
                    result["MACD.macd"] = round(float(macd_line), 2)
                if macd_sig is not None and not pd.isna(macd_sig):
                    result["MACD.signal"] = round(float(macd_sig), 2)

        # SMA20 from 20-day average of close
        if not tv_data.get("SMA20") and len(hist) >= 20:
            sma20 = ta.sma(hist["Close"], length=20)
            if sma20 is not None and len(sma20) > 0:
                last = sma20.iloc[-1]
                if not pd.isna(last):
                    result["SMA20"] = round(float(last), 2)

        return result
    except Exception:
        log.warning("technical_data_fallback_failed", symbol=symbol)
        return {}


def _detect_acquisition(info: dict[str, Any], tv_data: dict[str, Any]) -> dict[str, Any] | None:
    """Detect if a stock is in a pending acquisition using heuristic signals.

    Checks for the classic "deal-locked" signature:
    - Price pinned within 3% of analyst mean target
    - Ultra-low volatility (ATR < 1%)
    - Near-zero beta (decoupled from market)

    Returns dict with deal data, or None if no acquisition detected.
    """
    price = info.get("currentPrice") or info.get("regularMarketPrice") or tv_data.get("close")
    mean_target = info.get("targetMeanPrice")
    atr = tv_data.get("ATR")
    beta = info.get("beta")
    hi52 = info.get("fiftyTwoWeekHigh")

    if not price or price <= 0:
        return None
    if not mean_target or mean_target <= 0:
        return None

    # Cost of sales / purchase field from yfinance — check for acquisition hint
    # Some tickers have corporate action data indicating M&A
    corp_actions = info.get("corporateActions")
    has_merger_flag = False
    if corp_actions and isinstance(corp_actions, dict):
        for action_type in corp_actions:
            if action_type and "merger" in str(action_type).lower():
                has_merger_flag = True

    # Heuristic 1: Price pinned within 3% of analyst target
    upside_remaining = (mean_target / price - 1) * 100  # positive = still room to target
    price_near_target = abs(upside_remaining) < 3.0 and upside_remaining > 0

    # Heuristic 2: Very low volatility (typical of deal-locked stocks)
    low_vol = False
    atr_pct: float | None = None
    if atr and price:
        atr_pct = atr / price * 100
        low_vol = atr_pct < 1.0

    # Heuristic 3: Near-zero beta (decoupled from market moves)
    low_beta = beta is not None and beta < 0.5

    # Heuristic 4: Price pinned at 52-week high (deal price = high watermark)
    near_52w_high = hi52 and price >= hi52 * 0.97

    # Score the detection signals
    signal_strength = int(price_near_target) + int(low_vol) + int(low_beta) + int(near_52w_high) + int(has_merger_flag)

    if signal_strength >= 3:
        spread_pct = round((mean_target / price - 1) * 100, 2)

        # Determine confidence level:
        #   "confirmed" — all 5 signals OR very tight spread (< 1%) + 3+ signals
        #   "potential" — 3-4 signals without tight spread confirmation
        is_confirmed = (
            signal_strength >= 5
            or (signal_strength >= 3 and spread_pct < 1.0)
        )
        # Additional confirmation: if beta is near-zero AND ATR is very low,
        # the stock is likely under a signed definitive agreement
        has_tight_spread = spread_pct < 1.0
        is_deal_locked = has_tight_spread and (beta is not None and beta < 0.3) and (atr_pct is not None and atr_pct < 0.5)

        confidence = "confirmed" if (is_confirmed or is_deal_locked) else "potential"

        return {
            "offer_price": round(mean_target, 2),
            "spread_pct": spread_pct,
            "upside_remaining": round(upside_remaining, 2),
            "ma_confidence": confidence,
        }

    return None


def _analyze_catalyst_bias(info: dict[str, Any], tv_data: dict[str, Any]) -> dict[str, Any]:
    """
    Analyze catalyst bias from news, earnings, and corporate events.
    Returns bias direction and key catalysts for the synthesis engine.
    """
    catalysts = {
        "bias": "neutral",  # bullish / bearish / neutral
        "upcoming_events": [],
        "recent_catalysts": [],
        "earnings_proximity": None,
        "earnings_bias": "neutral",
        "key_findings": [],
    }
    
    # 1. Earnings proximity and bias
    next_earnings = info.get("earningsTimestampStart") or info.get("earningsTimestamp")
    if next_earnings:
        try:
            from datetime import datetime, timezone
            if isinstance(next_earnings, (int, float)):
                earnings_dt = datetime.fromtimestamp(next_earnings, tz=timezone.utc)
            else:
                earnings_dt = datetime.fromisoformat(str(next_earnings).replace("Z", "+00:00"))
            
            days_until = (earnings_dt - datetime.now(timezone.utc)).days
            catalysts["earnings_proximity"] = days_until
            
            if days_until <= 5:
                catalysts["upcoming_events"].append(f"Earnings in {days_until} days")
                # Check recent earnings surprise for bias
                last_surprise = info.get("earningsSurprisePct")
                if last_surprise is not None:
                    if last_surprise > 5:
                        catalysts["earnings_bias"] = "bullish"
                        catalysts["key_findings"].append(f"Last earnings beat by {last_surprise:.1f}% — positive momentum")
                    elif last_surprise < -5:
                        catalysts["earnings_bias"] = "bearish"
                        catalysts["key_findings"].append(f"Last earnings missed by {abs(last_surprise):.1f}% — caution")
                    else:
                        catalysts["earnings_bias"] = "neutral"
            elif days_until <= 14:
                catalysts["upcoming_events"].append(f"Earnings in {days_until} days")
        except Exception:
            pass
    
    # 2. Analyst revisions (proxy via target price vs current)
    target_price = info.get("targetMeanPrice")
    current_price = info.get("currentPrice") or info.get("regularMarketPrice")
    if target_price and current_price and current_price > 0:
        upside = (target_price / current_price - 1) * 100
        if upside > 20:
            catalysts["bias"] = "bullish"
            catalysts["key_findings"].append(f"Analyst target implies {upside:.0f}% upside")
        elif upside < -10:
            catalysts["bias"] = "bearish"
            catalysts["key_findings"].append(f"Analyst target {abs(upside):.0f}% below current price")
    
    # 3. Insider activity
    insider_pct = info.get("heldPercentInsiders")
    if insider_pct is not None:
        insider = insider_pct * 100
        if insider > 20:
            catalysts["key_findings"].append(f"High insider ownership ({insider:.1f}%) — alignment")
        elif insider < 1:
            catalysts["key_findings"].append("Very low insider ownership — minimal alignment")
    
    # 4. Short interest
    short_pct = info.get("shortPercentOfFloat")
    if short_pct is not None:
        si = short_pct * 100
        if si > 30:
            catalysts["bias"] = "bearish"
            catalysts["key_findings"].append(f"Extreme short interest ({si:.1f}%) — squeeze risk")
        elif si > 15:
            catalysts["key_findings"].append(f"Elevated short interest ({si:.1f}%)")
    
    # 5. Check for recent news catalysts from tv_data (if available)
    # This is a placeholder for when news data is passed in
    
    # 6. Dividend events
    div_date = info.get("dividendDate") or info.get("exDividendDate")
    if div_date:
        try:
            if isinstance(div_date, (int, float)):
                div_dt = datetime.fromtimestamp(div_date, tz=timezone.utc)
            else:
                div_dt = datetime.fromisoformat(str(div_date).replace("Z", "+00:00"))
            days_until = (div_dt - datetime.now(timezone.utc)).days
            if 0 <= days_until <= 10:
                catalysts["upcoming_events"].append(f"Ex-dividend in {days_until} days")
        except Exception:
            pass
    
    # Set overall bias based on findings
    bullish_signals = sum(1 for k in catalysts["key_findings"] if any(w in k.lower() for w in ["bullish", "upside", "beat", "positive", "alignment"]))
    bearish_signals = sum(1 for k in catalysts["key_findings"] if any(w in k.lower() for w in ["bearish", "downside", "miss", "caution", "risk", "short interest"]))
    
    if bullish_signals > bearish_signals:
        catalysts["bias"] = "bullish"
    elif bearish_signals > bullish_signals:
        catalysts["bias"] = "bearish"
    
    return catalysts


class TickerAnalysisService:
    """Elite-trader-grade ticker analysis service.

    Combines TV screener data with yfinance fundamentals to produce
    a complete analysis across technical, fundamental, earnings,
    sentiment, and risk dimensions with a final actionable verdict.
    """

    def __init__(self) -> None:
        self.log = get_logger("conflu.ticker_analysis.service")
        self.log = get_logger("conflu.ticker_analysis.service")

    def analyze(self, request: TickerAnalysisRequest) -> TickerAnalysisResponse:
        """Run full analysis on a ticker."""
        start = time.monotonic()
        symbol = request.symbol.upper()

        # ── 1. Gather data ──
        tv_data: dict[str, Any] = request.tv_data or {}
        info: dict[str, Any] = _fetch_info(symbol)

        # Guard: if yfinance returned an empty/404 response (WBA-style delisted
        # ticker), short-circuit with a synthetic empty-data verdict rather than
        # running all modules on zero data and getting a misleading result.
        has_core_data = bool(
            info.get("currentPrice")
            or info.get("regularMarketPrice")
            or info.get("shortName")
            or info.get("longName")
            or info.get("sector")
        )
        if not has_core_data:
            return TickerAnalysisResponse(
                symbol=symbol,
                price=0,
                sector=None,
                technical=TechnicalAnalysis(score=0.0, ma_alignment="N/A", rsi_regime="N/A", adx_verdict="N/A", volatility_regime="N/A", findings=[]),
                fundamental=FundamentalAnalysis(score=0.0, findings=[]),
                earnings=EarningsAnalysis(score=0.0, findings=[]),
                sentiment=SentimentAnalysis(score=0.0, findings=[]),
                risk=RiskAssessment(score=0.0, volatility_regime="N/A", suggested_stop_pct=5.0, suggested_position_size_pct=0.0, findings=[]),
                verdict=AnalysisVerdict(
                    action="N/A",
                    conviction=1,
                    key_red_flags=["No data available for symbol — ticker may be delisted or invalid"],
                    thesis=f"No data returned from yfinance for {symbol}. The symbol may be delisted, invalid, or temporarily unavailable.",
                ),
                execution_ms=0,
            )

        # Merge TV data fields into info context
        if tv_data and not info.get("currentPrice"):
            info["currentPrice"] = tv_data.get("close") or tv_data.get("Close")
        if tv_data and not info.get("sector"):
            info["sector"] = tv_data.get("sector")

        # Fallback: populate tv_data with yfinance-derived SMA values when
        # TV screener data doesn't provide them. The technical module needs
        # SMA20/SMA50/SMA200 for MA alignment and price-vs-MA analysis.
        #
        # SMA50 = fiftyDayAverage (yfinance's 50d SMA)
        # SMA200 = twoHundredDayAverage (yfinance's 200d SMA)
        # SMA20 is computed from yfinance 6mo OHLCV history below.
        close_yf = info.get("currentPrice") or info.get("regularMarketPrice") or tv_data.get("close")
        if close_yf:
            if not tv_data.get("close"):
                tv_data["close"] = close_yf
            if not tv_data.get("SMA50"):
                fda = info.get("fiftyDayAverage")
                if fda:
                    tv_data["SMA50"] = fda
            if not tv_data.get("SMA200"):
                tda = info.get("twoHundredDayAverage")
                if tda:
                    tv_data["SMA200"] = tda
            # Price vs 52w range as an approximate BB position (only when tv_data has no close)
            hi52 = info.get("fiftyTwoWeekHigh")
            lo52 = info.get("fiftyTwoWeekLow")
            if hi52 and lo52 and hi52 > lo52 and not tv_data.get("bb_position"):
                if close_yf >= hi52 * 0.97:
                    tv_data["bb_position"] = "above_upper"
                elif close_yf <= lo52 * 1.03 + (hi52 - lo52) * 0.1:
                    tv_data["bb_position"] = "below_lower"
                else:
                    tv_data["bb_position"] = "inside"

        # Fallback ATR: compute from yfinance daily history when no TV ATR is
        # available. This gives the risk module a data-driven stop loss instead
        # of a generic 5% default. Uses pure Python (no numpy dependency).
        if not tv_data.get("ATR") and (info.get("currentPrice") or info.get("regularMarketPrice")):
            try:
                ticker_yf = yf.Ticker(symbol)
                hist = ticker_yf.history(period="1mo")
                if hist is not None and len(hist) >= 7:
                    high = hist["High"].tolist()
                    low = hist["Low"].tolist()
                    close_hist = hist["Close"].tolist()
                    tr_vals = []
                    for i in range(len(hist)):
                        hl = high[i] - low[i]
                        hc = abs(high[i] - (close_hist[i - 1] if i > 0 else close_hist[i]))
                        lc = abs(low[i] - (close_hist[i - 1] if i > 0 else close_hist[i]))
                        tr_vals.append(max(hl, hc, lc))
                    atr_val = sum(tr_vals) / len(tr_vals)
                    if atr_val > 0:
                        tv_data["ATR"] = round(atr_val, 2)
            except Exception:
                self.log.warning("atr_fallback_failed", symbol=symbol)

        # ── Technical indicator fallback + cross-reference ──
        # Always compute RSI/ADX/MACD/SMA20 from yfinance OHLCV history via
        # pandas_ta. When TV data provides these fields, we keep TV values
        # (more current from the screener), but cross-reference for
        # discrepancies. When TV data is missing, the yfinance computed
        # values fill in the gap.
        computed = _compute_missing_technicals(symbol, tv_data)

        # Populate missing fields from yfinance-computed data
        for key in ("RSI", "ADX", "MACD.macd", "MACD.signal", "SMA20"):
            if not tv_data.get(key) and computed.get(key):
                tv_data[key] = computed[key]

        # Cross-reference RSI/ADX: log + reconcile when discrepancy > 5 points
        for key in ("RSI", "ADX"):
            tv_val = tv_data.get(key)
            yf_val = computed.get(key)
            if tv_val and yf_val and abs(tv_val - yf_val) > 5:
                self.log.warning(
                    "technical_indicator_discrepancy",
                    symbol=symbol,
                    indicator=key,
                    tv_value=round(tv_val, 1),
                    yf_value=round(yf_val, 1),
                    diff=round(abs(tv_val - yf_val), 1),
                    msg=f"{key} mismatch: TV={tv_val:.1f}, YF={yf_val:.1f} (diff={abs(tv_val - yf_val):.1f})",
                )
                # For RSI, use the more conservative (higher when >50, lower when <50)
                # to avoid false neutrality when the true reading is extreme
                if key == "RSI":
                    if tv_val > 50 and yf_val > tv_val:
                        tv_data[key] = yf_val  # Uptick to the higher reading
                    elif tv_val < 50 and yf_val < tv_val:
                        tv_data[key] = yf_val  # Downtick to the lower reading

        price = info.get("currentPrice") or info.get("regularMarketPrice") or tv_data.get("close") or tv_data.get("Close") or 0
        change = tv_data.get("change")
        sector = info.get("sector") or tv_data.get("sector")

        # ── 2. Run analysis modules ──
        tech: TechnicalAnalysis | dict[str, TechnicalAnalysis] | None = None
        fund: FundamentalAnalysis | None = None
        earn: EarningsAnalysis | None = None
        sent: SentimentAnalysis | None = None
        risk: RiskAssessment | None = None

        try:
            # Include weekly technical analysis for multi-timeframe perspective
            tech = technical.analyze(tv_data, symbol=symbol, include_weekly=True)
        except Exception:
            self.log.exception("technical_analysis_failed", symbol=symbol)

        # Extract daily technical for synthesis (use daily if dict, else use as-is)
        tech_daily = tech["daily"] if isinstance(tech, dict) else tech

        try:
            fund = fundamentals.analyze(info)
            # Pass instrument type to risk module via info dict
            if fund:
                info["instrument_type"] = fund.instrument_type
        except Exception:
            self.log.exception("fundamental_analysis_failed", symbol=symbol)

        try:
            earn = earnings.analyze(info)
        except Exception:
            self.log.exception("earnings_analysis_failed", symbol=symbol)

        try:
            sent = sentiment.analyze(info)
        except Exception:
            self.log.exception("sentiment_analysis_failed", symbol=symbol)

        try:
            risk = risk_module.analyze(tv_data, info)
        except Exception:
            self.log.exception("risk_analysis_failed", symbol=symbol)

        # ── 2b. M&A Detection ──
        # Heuristic: if price is pinned near analyst target with ultra-low volatility
        # and near-zero beta, the stock is likely in a pending acquisition.
        # When detected, switch to merger arb analysis mode.
        ma_data = _detect_acquisition(info, tv_data)
        if ma_data:
            tv_data["ma_offer_price"] = ma_data["offer_price"]
            tv_data["ma_spread_pct"] = ma_data["spread_pct"]
            tv_data["ma_upside_remaining"] = ma_data["upside_remaining"]
            tv_data["ma_confidence"] = ma_data.get("ma_confidence", "potential")

        # ── 2c. Catalyst Bias Analysis ──
        # Analyze earnings, analyst revisions, insider activity, short interest, etc.
        catalyst_bias = _analyze_catalyst_bias(info, tv_data)
        tv_data["catalyst_bias"] = catalyst_bias
        tv_data["catalyst_findings"] = catalyst_bias.get("key_findings", [])
        tv_data["catalyst_bias_direction"] = catalyst_bias.get("bias", "neutral")

        # ── 3. Synthesise verdict ──
        verdict: AnalysisVerdict = synthesis.synthesise(
            technical=tech_daily,
            fundamental=fund,
            earnings=earn,
            sentiment=sent,
            risk=risk,
            price=price,
            regime=request.regime,
            tv_data=tv_data,
        )

        # ── 3b. Apply macro regime overlay ──
        try:
            from backend.app.api.routers.regime import get_market_regime_sync
            regime = get_market_regime_sync()
            if regime:
                from backend.app.domain.ticker_analysis.macro_overlay import get_macro_adjustment, apply_macro_adjustment
                # Calculate weighted score from verdict action/conviction for macro overlay
                action_to_score = {
                    "BUY": 0.8, "ACCUMULATE": 0.4, "WATCH": 0.1, 
                    "HOLD": -0.1, "REDUCE": -0.4, "AVOID": -0.8
                }
                weighted_score = action_to_score.get(verdict.action, 0.0)
                adjustment = macro_overlay.get_macro_adjustment(
                    vix=regime.vix.value,
                    composite_score=regime.composite_score,
                    risk_appetite_score=regime.risk_appetite.score,
                    sector_breadth_pct=regime.sector_breadth.value,
                    safe_haven_score=regime.safe_haven.score,
                    weighted_score=weighted_score,
                    verdict=verdict,
                )
                verdict = macro_overlay.apply_macro_adjustment(verdict, adjustment)
                log.info("macro_overlay_applied", symbol=symbol, adjustment=adjustment.notes)
        except Exception:
            self.log.exception("macro_overlay_failed", symbol=symbol)

        # ── 4. Build response ──
        duration_ms = round((time.monotonic() - start) * 1000)

        # Data freshness: yfinance provides market time; fall back to analysis time
        now_utc = datetime.now(UTC)
        analysis_ts = now_utc.isoformat()
        data_age_hours: float | None = None
        mkt_time = info.get("regularMarketTime") or info.get("marketTime")
        if mkt_time:
            try:
                if isinstance(mkt_time, (int, float)):
                    market_dt = datetime.fromtimestamp(mkt_time, tz=UTC)
                    data_age_hours = round((now_utc - market_dt).total_seconds() / 3600, 1)
            except (ValueError, OSError):
                pass

        return TickerAnalysisResponse(
            symbol=symbol,
            price=price,
            change_pct=change,
            sector=sector,
            technical=tech_daily,
            fundamental=fund,
            earnings=earn,
            sentiment=sent,
            risk=risk,
            verdict=verdict,
            execution_ms=duration_ms,
            analysis_timestamp=analysis_ts,
            data_age_hours=data_age_hours,
            data_sources={
                "technical_daily": "TV Screener + yfinance (6mo daily)",
                "technical_weekly": "yfinance (2y weekly)",
                "fundamental": "yfinance info",
                "sentiment": "yfinance info",
                "earnings": "yfinance info",
            },
        )
