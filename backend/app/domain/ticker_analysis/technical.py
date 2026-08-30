"""Technical analysis module — evaluates price structure, momentum, and volatility."""

from __future__ import annotations

import math
import time
from typing import Any

import yfinance as yf
import numpy as np
import pandas as pd
import pandas_ta as ta

from backend.app.domain.ticker_analysis.models import TechnicalAnalysis, ChartReadingAnalysis, TimeframeChartReading
from backend.app.domain.ticker_analysis import structure, volume_profile, smc, breakout, mtf_confluence


# ── Swing Detection ──
# Uses 5-bar fractal pattern: high[i] > high[i-1..i-2] and high[i] > high[i+1..i+2]
# For lows: low[i] < low[i-1..i-2] and low[i] < low[i+1..i+2]


def _detect_swings(ohlcv: pd.DataFrame, lookback: int = 5) -> dict[str, list[dict]]:
    """
    Detect swing highs and lows using fractal pattern.
    
    Returns dict with 'highs' and 'lows' lists of dicts: {price, index, timestamp}
    """
    highs = ohlcv["High"].values
    lows = ohlcv["Low"].values
    timestamps = ohlcv.index
    
    swing_highs = []
    swing_lows = []
    
    for i in range(lookback, len(ohlcv) - lookback):
        # Swing high: current high > all highs in lookback window before and after
        is_swing_high = True
        for j in range(1, lookback + 1):
            if highs[i] <= highs[i - j] or highs[i] <= highs[i + j]:
                is_swing_high = False
                break
        
        # Swing low: current low < all lows in lookback window before and after
        is_swing_low = True
        for j in range(1, lookback + 1):
            if lows[i] >= lows[i - j] or lows[i] >= lows[i + j]:
                is_swing_low = False
                break
        
        if is_swing_high:
            swing_highs.append({
                "price": float(highs[i]),
                "index": i,
                "timestamp": timestamps[i]
            })
        if is_swing_low:
            swing_lows.append({
                "price": float(lows[i]),
                "index": i,
                "timestamp": timestamps[i]
            })
    
    return {"highs": swing_highs, "lows": swing_lows}


def _classify_market_structure(swings: dict[str, list[dict]], close: float) -> tuple[str, dict]:
    """
    Classify market structure from swings: bullish (HH/HL), bearish (LH/LL), ranging, transition.
    
    Returns (structure_label, details_dict)
    """
    highs = swings.get("highs", [])
    lows = swings.get("lows", [])
    
    if len(highs) < 2 or len(lows) < 2:
        return "insufficient_data", {"reason": "Not enough swings"}
    
    # Get last 3 highs and lows
    recent_highs = [h["price"] for h in highs[-3:]]
    recent_lows = [l["price"] for l in lows[-3:]]
    
    # Check for HH (higher high)
    hh = recent_highs[-1] > recent_highs[-2] if len(recent_highs) >= 2 else False
    # Check for HL (higher low)
    hl = recent_lows[-1] > recent_lows[-2] if len(recent_lows) >= 2 else False
    # Check for LH (lower high)
    lh = recent_highs[-1] < recent_highs[-2] if len(recent_highs) >= 2 else False
    # Check for LL (lower low)
    ll = recent_lows[-1] < recent_lows[-2] if len(recent_lows) >= 2 else False
    
    details = {
        "recent_highs": recent_highs,
        "recent_lows": recent_lows,
        "hh": hh, "hl": hl, "lh": lh, "ll": ll,
        "last_swing_high": recent_highs[-1] if recent_highs else None,
        "last_swing_low": recent_lows[-1] if recent_lows else None,
    }
    
    if hh and hl:
        return "bullish", details
    elif lh and ll:
        return "bearish", details
    elif (hh and not hl) or (hl and not hh):
        return "transition_bullish", details
    elif (lh and not ll) or (ll and not lh):
        return "transition_bearish", details
    else:
        return "ranging", details


def _find_key_levels(swings: dict[str, list[dict]], ohlcv: pd.DataFrame, 
                     atr_pct: float | None, close: float) -> tuple[list[float], list[float]]:
    """
    Find key resistance and support levels from swing clusters.
    Groups swings within ATR-based tolerance, weights by volume at level.
    """
    highs = swings.get("highs", [])
    lows = swings.get("lows", [])
    
    if not highs and not lows:
        return [], []
    
    # Use ATR for clustering tolerance, fallback to 1.5% of price
    tolerance_pct = atr_pct if atr_pct else 1.5
    tolerance = close * tolerance_pct / 100
    
    def cluster_levels(swing_prices: list[float]) -> list[float]:
        if not swing_prices:
            return []
        
        sorted_prices = sorted(swing_prices)
        clusters = []
        current_cluster = [sorted_prices[0]]
        
        for price in sorted_prices[1:]:
            if abs(price - current_cluster[-1]) <= tolerance:
                current_cluster.append(price)
            else:
                if len(current_cluster) >= 1:
                    clusters.append(float(np.mean(current_cluster)))
                current_cluster = [price]
        
        if current_cluster:
            clusters.append(float(np.mean(current_cluster)))
        
        return clusters
    
    high_prices = [h["price"] for h in highs]
    low_prices = [l["price"] for l in lows]
    
    resistance_levels = cluster_levels(high_prices)
    support_levels = cluster_levels(low_prices)
    
    # Filter to only relevant levels (near current price)
    resistance_levels = [r for r in resistance_levels if r > close * 0.95]
    support_levels = [s for s in support_levels if s < close * 1.05]
    
    return resistance_levels[:5], support_levels[:5]  # Top 5 each


def _score_pullback_quality(
    ohlcv: pd.DataFrame,
    swings: dict[str, list[dict]],
    structure: str,
    close: float,
    atr_pct: float | None,
    volume_ratio: float | None
) -> tuple[str, float, list[str]]:
    """
    Score pullback quality: A+ to F.
    
    Factors:
    - Depth vs prior swing (shallow = better)
    - Volume dry-up on pullback (lower = better)
    - Time duration (quick = better)
    - RSI reset (oversold reset = better)
    - Structure hold (swing low not broken in uptrend)
    """
    findings = []
    score = 50  # Base
    
    # Get recent swing low (for uptrend pullback) or swing high (for downtrend)
    lows = swings.get("lows", [])
    highs = swings.get("highs", [])
    
    if not lows or not highs:
        return "F", 0, ["Insufficient swing data"]
    
    last_swing_low = lows[-1]["price"]
    last_swing_high = highs[-1]["price"]
    
    # Pullback depth (how far from recent extreme)
    if "bullish" in structure or structure == "transition_bullish":
        # In uptrend, pullback from recent high
        if len(highs) >= 2:
            recent_high = highs[-1]["price"]
            prev_high = highs[-2]["price"]
            depth = (recent_high - close) / recent_high * 100
            
            if depth < 3:
                score += 20
                findings.append(f"📉 Shallow pullback: {depth:.1f}% from high")
            elif depth < 6:
                score += 10
                findings.append(f"📉 Moderate pullback: {depth:.1f}%")
            elif depth < 10:
                score -= 5
                findings.append(f"⚠️ Deep pullback: {depth:.1f}%")
            else:
                score -= 15
                findings.append(f"🚨 Very deep pullback: {depth:.1f}% — structure at risk")
        
        # Volume dry-up
        if volume_ratio is not None:
            if volume_ratio < 0.7:
                score += 15
                findings.append(f"✅ Volume dried up ({volume_ratio:.1f}x avg) — low selling pressure")
            elif volume_ratio < 1.0:
                score += 5
                findings.append(f"📊 Below-average volume on pullback")
            elif volume_ratio > 1.5:
                score -= 10
                findings.append(f"⚠️ High volume on pullback ({volume_ratio:.1f}x) — potential distribution")
        
        # Structure hold: close above prior swing low
        if close > last_swing_low:
            score += 10
            findings.append("✅ Holding above prior swing low — structure intact")
        else:
            score -= 20
            findings.append("🚨 Broke prior swing low — structure broken")
    
    elif "bearish" in structure or structure == "transition_bearish":
        # In downtrend, pullback from recent low (bounce)
        if len(lows) >= 2:
            recent_low = lows[-1]["price"]
            prev_low = lows[-2]["price"]
            depth = (close - recent_low) / recent_low * 100
            
            if depth < 3:
                score += 20
                findings.append(f"📈 Shallow bounce: {depth:.1f}% from low")
            elif depth < 6:
                score += 10
                findings.append(f"📈 Moderate bounce: {depth:.1f}%")
            elif depth < 10:
                score -= 5
                findings.append(f"⚠️ Deep bounce: {depth:.1f}%")
            else:
                score -= 15
                findings.append(f"🚨 Extended bounce: {depth:.1f}% — may resume down")
        
        if volume_ratio is not None:
            if volume_ratio < 0.7:
                score += 15
                findings.append(f"✅ Volume dried up on bounce — weak demand")
            elif volume_ratio > 1.5:
                score -= 10
                findings.append(f"⚠️ High volume on bounce — potential trap")
        
        if close < last_swing_high:
            score += 10
            findings.append("✅ Below prior swing high — downtrend intact")
        else:
            score -= 20
            findings.append("🚨 Broke prior swing high — structure shifting")
    
    # RSI reset bonus
    # (would need RSI passed in, skip for now)
    
    # Time factor: quick pullback = better (would need lookback duration)
    
    # Normalize to 0-100
    score = max(0, min(100, score))
    
    # Letter grade
    if score >= 85:
        grade = "A+"
    elif score >= 75:
        grade = "A"
    elif score >= 65:
        grade = "B"
    elif score >= 55:
        grade = "C"
    elif score >= 45:
        grade = "D"
    else:
        grade = "F"
    
    return grade, round(score, 1), findings


def _compute_indicators_from_ohlcv(ohlcv: pd.DataFrame) -> dict[str, Any]:
    """Compute technical indicators from OHLCV DataFrame using pandas_ta."""
    result: dict[str, Any] = {}
    
    try:
        # RSI(14)
        rsi_series = ta.rsi(ohlcv["Close"], length=14)
        if rsi_series is not None and len(rsi_series) > 0:
            last = rsi_series.iloc[-1]
            if not pd.isna(last):
                result["RSI"] = round(float(last), 1)

        # ADX(14)
        adx_df = ta.adx(ohlcv["High"], ohlcv["Low"], ohlcv["Close"], length=14)
        if adx_df is not None and len(adx_df) > 0:
            last = adx_df.iloc[-1]
            adx_val = last.get("ADX_14")
            if adx_val is not None and not pd.isna(adx_val):
                result["ADX"] = round(float(adx_val), 1)

        # MACD(12,26,9)
        macd_df = ta.macd(ohlcv["Close"], fast=12, slow=26, signal=9)
        if macd_df is not None and len(macd_df) > 0:
            last = macd_df.iloc[-1]
            macd_line = last.get("MACD_12_26_9")
            macd_sig = last.get("MACDs_12_26_9")
            if macd_line is not None and not pd.isna(macd_line):
                result["MACD.macd"] = round(float(macd_line), 2)
            if macd_sig is not None and not pd.isna(macd_sig):
                result["MACD.signal"] = round(float(macd_sig), 2)

        # SMA20, SMA50, SMA200
        for length, key in [(20, "SMA20"), (50, "SMA50"), (200, "SMA200")]:
            if len(ohlcv) >= length:
                sma = ohlcv["Close"].rolling(length).mean().iloc[-1]
                if not pd.isna(sma):
                    result[key] = round(float(sma), 2)

        # ATR(14)
        atr_series = ta.atr(ohlcv["High"], ohlcv["Low"], ohlcv["Close"], length=14)
        if atr_series is not None and len(atr_series) > 0:
            last = atr_series.iloc[-1]
            if not pd.isna(last):
                result["ATR"] = round(float(last), 2)

        # Bollinger Bands (20, 2)
        bb_df = ta.bbands(ohlcv["Close"], length=20, std=2)
        if bb_df is not None and len(bb_df) > 0:
            last = bb_df.iloc[-1]
            bb_upper = last.get("BBU_20_2.0")
            bb_lower = last.get("BBL_20_2.0")
            bb_mid = last.get("BBM_20_2.0")
            if bb_upper is not None and not pd.isna(bb_upper):
                result["BB.upper"] = round(float(bb_upper), 2)
            if bb_lower is not None and not pd.isna(bb_lower):
                result["BB.lower"] = round(float(bb_lower), 2)
            if bb_mid is not None and not pd.isna(bb_mid):
                result["BB.mid"] = round(float(bb_mid), 2)

        # Volume ratio (10-day average)
        if len(ohlcv) >= 10:
            avg_vol = ohlcv["Volume"].rolling(10).mean().iloc[-1]
            last_vol = ohlcv["Volume"].iloc[-1]
            if avg_vol and avg_vol > 0:
                result["relative_volume_10d_calc"] = round(float(last_vol / avg_vol), 2)

        # Close price
        result["close"] = round(float(ohlcv["Close"].iloc[-1]), 2)

    except Exception:
        pass
    
    return result


def _fetch_weekly_ohlcv(symbol: str) -> pd.DataFrame | None:
    """Fetch weekly OHLCV from yfinance (2 years of weekly data)."""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="2y", interval="1wk")
        if hist is None or len(hist) < 20:
            return None
        return hist
    except Exception:
        return None


def _fetch_daily_ohlcv(symbol: str) -> pd.DataFrame | None:
    """Fetch daily OHLCV from yfinance (6 months of daily data for swing detection)."""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="6mo", interval="1d")
        if hist is None or len(hist) < 50:
            return None
        return hist
    except Exception:
        return None


def _fetch_intraday_ohlcv(symbol: str, interval: str, period: str = "3mo") -> pd.DataFrame | None:
    """Fetch intraday OHLCV from yfinance (4h/1h)."""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period, interval=interval)
        if hist is None or len(hist) < 50:
            return None
        return hist
    except Exception:
        return None


def _compute_volume_profile_tpo(ohlcv: pd.DataFrame, lookback: int = 20) -> dict[str, Any]:
    """
    Compute Volume Profile (TPO - Time Price Opportunity) from daily bars.
    Approximates volume distribution across price levels using daily bar volume.
    
    Returns dict with:
    - poc: Point of Control (price with highest volume)
    - vah: Value Area High (70% of volume above)
    - val: Value Area Low (70% of volume below)
    - hvn: High Volume Nodes (prices with significant volume)
    - lvn: Low Volume Nodes (price gaps with low volume)
    - distribution: Full price -> volume mapping
    """
    if ohlcv is None or len(ohlcv) < 10:
        return {}
    
    # Use last `lookback` days
    df = ohlcv.tail(lookback).copy()
    
    # Create price bins - use 50 price levels across the range
    price_min = df["Low"].min()
    price_max = df["High"].max()
    price_range = price_max - price_min
    
    if price_range == 0:
        return {}
    
    num_bins = 50
    bin_size = price_range / num_bins
    bins = np.linspace(price_min, price_max, num_bins + 1)
    
    # Distribute volume across price levels for each day
    # Using the typical TPO approximation: distribute volume uniformly across the day's range
    volume_profile = np.zeros(num_bins)
    
    for _, row in df.iterrows():
        day_low = row["Low"]
        day_high = row["High"]
        day_volume = row["Volume"]
        
        if day_high == day_low:
            continue
        
        # Find which bins this day's range covers
        low_idx = max(0, int((day_low - price_min) / bin_size))
        high_idx = min(num_bins - 1, int((day_high - price_min) / bin_size))
        
        # Distribute volume evenly across the bins this day covers
        bins_covered = max(1, high_idx - low_idx + 1)
        vol_per_bin = day_volume / bins_covered
        
        for i in range(low_idx, high_idx + 1):
            volume_profile[i] += vol_per_bin
    
    # Find POC (Point of Control) - highest volume price
    poc_idx = int(np.argmax(volume_profile))
    poc_price = price_min + (poc_idx + 0.5) * bin_size
    
    # Find Value Area (70% of volume)
    total_volume = volume_profile.sum()
    target_volume = total_volume * 0.7
    
    # Expand from POC outward to find VAH/VAL
    va_low_idx = poc_idx
    va_high_idx = poc_idx
    current_volume = volume_profile[poc_idx]
    
    while current_volume < target_volume and (va_low_idx > 0 or va_high_idx < num_bins - 1):
        # Expand to side with higher volume
        vol_down = volume_profile[va_low_idx - 1] if va_low_idx > 0 else 0
        vol_up = volume_profile[va_high_idx + 1] if va_high_idx < num_bins - 1 else 0
        
        if vol_up >= vol_down and va_high_idx < num_bins - 1:
            va_high_idx += 1
            current_volume += vol_up
        elif va_low_idx > 0:
            va_low_idx -= 1
            current_volume += vol_down
        else:
            break
    
    vah_price = price_min + (va_high_idx + 0.5) * bin_size
    val_price = price_min + (va_low_idx + 0.5) * bin_size
    
    # Find HVN (High Volume Nodes) - bins with volume > 1.5x average
    avg_vol = volume_profile[volume_profile > 0].mean() if np.any(volume_profile > 0) else 0
    hvn_threshold = avg_vol * 1.5
    hvn_indices = np.where(volume_profile > hvn_threshold)[0]
    hvn_prices = [price_min + (i + 0.5) * bin_size for i in hvn_indices]
    
    # Find LVN (Low Volume Nodes) - bins with near-zero volume between HVNs
    lvn_indices = np.where((volume_profile > 0) & (volume_profile < avg_vol * 0.2))[0]
    lvn_prices = [price_min + (i + 0.5) * bin_size for i in lvn_indices]
    
    # Build distribution dict
    distribution = {}
    for i, vol in enumerate(volume_profile):
        if vol > 0:
            price = price_min + (i + 0.5) * bin_size
            distribution[round(price, 2)] = round(float(vol), 2)
    
    return {
        "poc": round(poc_price, 2),
        "vah": round(vah_price, 2),
        "val": round(val_price, 2),
        "hvn": [round(p, 2) for p in hvn_prices],
        "lvn": [round(p, 2) for p in lvn_prices],
        "distribution": distribution,
    }


def analyze(data_fields: dict[str, Any], symbol: str | None = None, include_weekly: bool = False, include_intraday: bool = False) -> TechnicalAnalysis | dict[str, TechnicalAnalysis]:
    """Analyse technical indicators from TV screener data.
    
    Args:
        data_fields: TV screener data (daily timeframe)
        symbol: Optional symbol to fetch weekly/intraday data from yfinance
        include_weekly: If True, also fetch and analyze weekly timeframe
        include_intraday: If True, also fetch and analyze 4h/1h timeframes
        
    Returns:
        TechnicalAnalysis for daily, or dict with timeframe keys if include_weekly/intraday=True
    """
    start_time = time.time()
    
    # Fetch OHLCV data needed for advanced chart reading (only for daily with symbol)
    daily_ohlcv = None
    weekly_ohlcv = None
    intraday_4h_ohlcv = None
    intraday_1h_ohlcv = None
    
    if symbol:
        daily_ohlcv = _fetch_daily_ohlcv(symbol)
        if include_weekly:
            weekly_ohlcv = _fetch_weekly_ohlcv(symbol)
        if include_intraday:
            intraday_4h_ohlcv = _fetch_intraday_ohlcv(symbol, "4h", "3mo")
            intraday_1h_ohlcv = _fetch_intraday_ohlcv(symbol, "1h", "1mo")
    
    # Analyze daily timeframe from TV data (with OHLCV for advanced chart reading)
    daily_result = _analyze_timeframe(data_fields, "daily", symbol, daily_ohlcv, weekly_ohlcv, intraday_4h_ohlcv, intraday_1h_ohlcv)
    
    results = {"daily": daily_result}
    
    # Also run analysis for other timeframes if requested
    if include_weekly:
        weekly_ohlcv = _fetch_weekly_ohlcv(symbol) if symbol else None
        if weekly_ohlcv is not None:
            weekly_fields = _compute_indicators_from_ohlcv(weekly_ohlcv)
            results["weekly"] = _analyze_timeframe(weekly_fields, "weekly", None, weekly_ohlcv)
    
    if include_intraday:
        ohlcv_4h = _fetch_intraday_ohlcv(symbol, "4h", "3mo") if symbol else None
        if ohlcv_4h is not None:
            fields_4h = _compute_indicators_from_ohlcv(ohlcv_4h)
            results["4h"] = _analyze_timeframe(fields_4h, "4h", None, ohlcv_4h)
        
        ohlcv_1h = _fetch_intraday_ohlcv(symbol, "1h", "1mo") if symbol else None
        if ohlcv_1h is not None:
            fields_1h = _compute_indicators_from_ohlcv(ohlcv_1h)
            results["1h"] = _analyze_timeframe(fields_1h, "1h", None, ohlcv_1h)
    
    # Build ChartReadingAnalysis for daily (only when we have OHLCV data)
    if isinstance(daily_result, TechnicalAnalysis) and daily_ohlcv is not None:
        chart_reading = _build_chart_reading_analysis(daily_ohlcv, weekly_ohlcv, intraday_4h_ohlcv, intraday_1h_ohlcv, daily_result, results)
        if hasattr(daily_result, 'chart_reading'):
            daily_result.chart_reading = chart_reading
    
    computation_time = int((time.time() - start_time) * 1000)
    if hasattr(daily_result, 'findings'):
        daily_result.findings.append(f"⏱️ Technical analysis completed in {computation_time}ms")
    
    if len(results) == 1:
        return daily_result
    return results


def _build_timeframe_chart_reading(
    ohlcv: pd.DataFrame,
    timeframe: str,
    include_tpo: bool = False,
    weekly_ohlcv: pd.DataFrame | None = None,
    daily_ohlcv: pd.DataFrame | None = None,
    intraday_4h_ohlcv: pd.DataFrame | None = None,
    intraday_1h_ohlcv: pd.DataFrame | None = None
) -> TimeframeChartReading:
    """Build chart reading analysis for a single timeframe."""
    from backend.app.domain.ticker_analysis.models import TimeframeChartReading
    from backend.app.domain.ticker_analysis import structure, volume_profile, smc, breakout
    
    tf_reading = TimeframeChartReading(timeframe=timeframe)
    tf_reading.timeframes_analyzed = [timeframe]
    
    try:
        # 1. Market Structure (BOS/CHoCH)
        swings = structure.detect_swings(ohlcv)
        bos_events, choch_events, structure_label = structure.detect_bos_choch(ohlcv, swings)
        tf_reading.bos_events = [
            {"type": e.type, "break_price": e.break_price, "break_index": e.break_index, 
             "break_timestamp": str(e.break_timestamp), "structure_level": e.structure_level,
             "volume_confirmed": e.volume_confirmed, "volume_ratio": e.volume_ratio,
             "follow_through": e.follow_through, "retest_confirmed": e.retest_confirmed,
             "retest_index": e.retest_index}
            for e in bos_events
        ]
        tf_reading.choch_events = [
            {"type": e.type, "bos_event": {"type": e.bos_event.type, "structure_level": e.bos_event.structure_level},
             "confirmation_price": e.confirmation_price, "confirmation_index": e.confirmation_index,
             "pullback_depth_pct": e.pullback_depth_pct, "structure_shift_confirmed": e.structure_shift_confirmed}
            for e in choch_events
        ]
        tf_reading.structure_label = structure_label
        
        # 2. Volume Profile TPO (only for daily timeframe)
        if include_tpo and ohlcv is not None:
            tpo_daily, tpo_composite = volume_profile.compute_professional_tpo(ohlcv)
            tf_reading.tpo_profiles = [
                {"date": str(p.date), "poc": p.poc, "vah": p.vah, "val": p.val,
                 "ib_high": p.ib_high, "ib_low": p.ib_low, "ib_mid": p.ib_mid,
                 "range_extension_up": p.range_extension_up, "range_extension_down": p.range_extension_down,
                 "single_prints": p.single_prints, "tail_excess": p.tail_excess}
                for p in tpo_daily
            ]
            if tpo_composite:
                tf_reading.composite_tpo_profile = {
                    "composite_poc": tpo_composite.composite_poc,
                    "composite_vah": tpo_composite.composite_vah,
                    "composite_val": tpo_composite.composite_val,
                    "poc_migration": tpo_composite.poc_migration,
                    "developing_poc": tpo_composite.developing_poc
                }
        
        # 3. Smart Money Concepts
        # For liquidity mapping, we need higher timeframe data
        weekly_for_smc = weekly_ohlcv if timeframe == "daily" else None
        daily_for_smc = daily_ohlcv if timeframe in ("4h", "1h") else None
        intraday_for_smc = intraday_4h_ohlcv if timeframe == "1h" else None
        
        smc_results = smc.run_smc_analysis(
            ohlcv, 
            intraday_for_smc,  # intraday for session highs/lows
            weekly_for_smc,    # weekly for PWH/PWL
            [], []  # swings and bos_events will be passed from context if needed
        )
        tf_reading.order_blocks = [
            {"type": ob.type, "top": ob.top, "bottom": ob.bottom, "index": ob.index,
             "timestamp": str(ob.timestamp), "impulsive_move_pct": ob.impulsive_move_pct,
             "impulse_bars": ob.impulse_bars, "impulse_volume_ratio": ob.impulse_volume_ratio,
             "mitigated": ob.mitigated, "mitigation_index": ob.mitigation_index,
             "strength": ob.strength}
            for ob in smc_results["order_blocks"]
        ]
        tf_reading.fair_value_gaps = [
            {"type": fvg.type, "top": fvg.top, "bottom": fvg.bottom, "index": fvg.index,
             "timestamp": str(fvg.timestamp), "size_pct": fvg.size_pct,
             "filled": fvg.filled, "consequent_encroachment": fvg.consequent_encroachment}
            for fvg in smc_results["fair_value_gaps"]
        ]
        tf_reading.breaker_blocks = [
            {"type": bb.type, "break_index": bb.break_index, "break_price": bb.break_price,
             "break_timestamp": str(bb.break_timestamp), "retest_confirmed": bb.retest_confirmed}
            for bb in smc_results["breaker_blocks"]
        ]
        tf_reading.liquidity_levels = [
            {"price": lvl.price, "type": lvl.type, "source": lvl.source,
             "strength": lvl.strength, "timestamp": str(lvl.timestamp)}
            for lvl in smc_results["liquidity_levels"]
        ]
        
    except Exception as e:
        tf_reading.data_quality_warnings.append(f"Chart reading error: {str(e)}")
    
    return tf_reading


def _build_chart_reading_analysis(
    daily_ohlcv: pd.DataFrame,
    weekly_ohlcv: pd.DataFrame | None,
    intraday_4h_ohlcv: pd.DataFrame | None,
    intraday_1h_ohlcv: pd.DataFrame | None,
    daily_result: TechnicalAnalysis,
    timeframe_results: dict[str, TechnicalAnalysis] | None = None
) -> ChartReadingAnalysis:
    """Build comprehensive chart reading analysis from all timeframes.

    Per-timeframe signal blocks (BOS/CHoCH, TPO, SMC, breakouts) are built for
    every timeframe that has OHLCV data. Multi-timeframe confluence is then
    computed from the full set of TechnicalAnalysis results (daily/4h/1h) so the
    synthesized trade plan can leverage entry zones, invalidation, and conflicts.

    ``timeframe_results`` is the dict produced by ``analyze()`` (keys: daily,
    weekly, 4h, 1h) holding already-computed TechnicalAnalysis objects. When
    provided, it populates ``chart_reading.mtf_confluence``.
    """
    from backend.app.domain.ticker_analysis.models import ChartReadingAnalysis
    from backend.app.domain.ticker_analysis import mtf_confluence
    
    chart_reading = ChartReadingAnalysis()
    chart_reading.timeframes_analyzed = []
    
    # Build per-timeframe chart reading
    if daily_ohlcv is not None:
        chart_reading.daily = _build_timeframe_chart_reading(
            daily_ohlcv, "daily", include_tpo=True,
            weekly_ohlcv=weekly_ohlcv, daily_ohlcv=daily_ohlcv,
            intraday_4h_ohlcv=intraday_4h_ohlcv, intraday_1h_ohlcv=intraday_1h_ohlcv
        )
        chart_reading.timeframes_analyzed.append("daily")
    
    if weekly_ohlcv is not None:
        chart_reading.weekly = _build_timeframe_chart_reading(
            weekly_ohlcv, "weekly", include_tpo=False,
            weekly_ohlcv=None, daily_ohlcv=daily_ohlcv,
            intraday_4h_ohlcv=intraday_4h_ohlcv, intraday_1h_ohlcv=intraday_1h_ohlcv
        )
        chart_reading.timeframes_analyzed.append("weekly")
    
    if intraday_4h_ohlcv is not None:
        chart_reading.h4 = _build_timeframe_chart_reading(
            intraday_4h_ohlcv, "4h", include_tpo=False,
            weekly_ohlcv=weekly_ohlcv, daily_ohlcv=daily_ohlcv,
            intraday_4h_ohlcv=None, intraday_1h_ohlcv=intraday_1h_ohlcv
        )
        chart_reading.timeframes_analyzed.append("4h")
    
    if intraday_1h_ohlcv is not None:
        chart_reading.h1 = _build_timeframe_chart_reading(
            intraday_1h_ohlcv, "1h", include_tpo=False,
            weekly_ohlcv=weekly_ohlcv, daily_ohlcv=daily_ohlcv,
            intraday_4h_ohlcv=None, intraday_1h_ohlcv=None
        )
        chart_reading.timeframes_analyzed.append("1h")
    
    # Build MTF Confluence (combines all timeframes)
    try:
        if timeframe_results:
            mtf_result = mtf_confluence.build_mtf_confluence_from_analysis(timeframe_results)
            if mtf_result is not None:
                chart_reading.mtf_confluence = _serialize_mtf_result(mtf_result)
    except Exception as e:
        chart_reading.data_quality_warnings.append(f"MTF confluence error: {str(e)}")
    
    return chart_reading


def _serialize_mtf_result(mtf: Any) -> dict:
    """Serialize an MTFConfluenceResult dataclass into a JSON-safe dict.

    The ``ChartReadingAnalysis.mtf_confluence`` field and downstream consumers
    (e.g. synthesis.py) expect a dict with at least ``conflicts`` and
    ``entry_zones`` keys.
    """
    signals = [
        {
            "timeframe": getattr(s, "timeframe", None),
            "direction": getattr(s, "direction", None),
            "score": getattr(s, "score", None),
            "weight": getattr(s, "weight", None),
            "details": getattr(s, "details", []),
            "structure_type": getattr(s, "structure_type", None),
            "price_level": getattr(s, "price_level", None),
            "is_mitigated": getattr(s, "is_mitigated", None),
        }
        for s in (getattr(mtf, "signals", None) or [])
    ]
    return {
        "overall_bias": getattr(mtf, "overall_bias", None),
        "bull_score": getattr(mtf, "bull_score", None),
        "bear_score": getattr(mtf, "bear_score", None),
        "confidence": getattr(mtf, "confidence", None),
        "signals": signals,
        "conflicts": list(getattr(mtf, "conflicts", None) or []),
        "has_critical_conflict": getattr(mtf, "has_critical_conflict", False),
        "entry_zones": list(getattr(mtf, "entry_zones", None) or []),
        "invalidation_level": getattr(mtf, "invalidation_level", None),
        "invalidation_reason": getattr(mtf, "invalidation_reason", None),
        "details": list(getattr(mtf, "details", None) or []),
        "timestamp": getattr(mtf, "timestamp", None),
    }


def _analyze_timeframe(data_fields: dict[str, Any], timeframe: str, symbol: str | None = None, 
                       daily_ohlcv: pd.DataFrame | None = None,
                       weekly_ohlcv: pd.DataFrame | None = None,
                       intraday_4h_ohlcv: pd.DataFrame | None = None,
                       intraday_1h_ohlcv: pd.DataFrame | None = None) -> TechnicalAnalysis:
    """Analyze technical indicators for a specific timeframe."""
    findings: list[str] = []
    score = 0.0
    weight_count = 0

    close = data_fields.get("close") or data_fields.get("Close") or 0
    
    # ── Market Structure Analysis (fetch OHLCV for swing detection) ──
    structure = "unknown"
    structure_details: dict = {}
    swings = {"highs": [], "lows": []}
    key_resistance: list[float] = []
    key_support: list[float] = []
    pullback_quality = "unknown"
    pullback_score = 0.0
    
    # Fetch OHLCV for swing detection (daily timeframe with symbol)
    if timeframe == "daily" and symbol:
        daily_ohlcv = _fetch_daily_ohlcv(symbol)
        if daily_ohlcv is not None:
            swings = _detect_swings(daily_ohlcv)
            structure, structure_details = _classify_market_structure(swings, close)
            key_resistance, key_support = _find_key_levels(swings, daily_ohlcv, 
                                                            data_fields.get("ATR") / close * 100 if data_fields.get("ATR") and close else None,
                                                            close)
            
            # Pullback quality
            atr = data_fields.get("ATR")
            atr_pct = (atr / close * 100) if atr and close else None
            rel_vol = data_fields.get("relative_volume_10d_calc")
            pullback_quality, pullback_score, pb_findings = _score_pullback_quality(
                daily_ohlcv, swings, structure, close, atr_pct, rel_vol
            )
            findings.extend(pb_findings)
        else:
            structure = "unknown"
            structure_details = {"reason": "No OHLCV data available"}
    
    # If we couldn't get OHLCV, use MA alignment as proxy
    if structure == "unknown":
        # We'll determine from MA alignment later
        structure = "unknown"
        structure_details = {}

    # ── 1. Trend: MA Alignment ──
    # For weekly, use SMA keys; for daily, try SMA then EMA
    if timeframe == "weekly":
        sma20 = data_fields.get("SMA20")
        sma50 = data_fields.get("SMA50")
        sma200 = data_fields.get("SMA200")
    else:
        sma20 = data_fields.get("SMA20") or data_fields.get("EMA20")
        sma50 = data_fields.get("SMA50") or data_fields.get("EMA50")
        sma200 = data_fields.get("SMA200") or data_fields.get("EMA200")

    ma_alignment = "N/A"
    if all(v is not None and not (isinstance(v, float) and math.isnan(v)) for v in [sma20, sma50, sma200]):
        if sma20 > sma50 > sma200 and close > sma20:
            ma_alignment = "bullish"
            findings.append(f"✅ {timeframe.capitalize()} Bullish MA stack: SMA20 ({sma20:.2f}) > SMA50 ({sma50:.2f}) > SMA200 ({sma200:.2f})")
            score += 1.0
        elif sma20 < sma50 < sma200 and close < sma20:
            ma_alignment = "bearish"
            findings.append(f"⚠️ {timeframe.capitalize()} Bearish MA stack: SMA20 ({sma20:.2f}) < SMA50 ({sma50:.2f}) < SMA200 ({sma200:.2f})")
            score -= 0.8
        else:
            ma_alignment = "mixed"
            findings.append(f"📊 {timeframe.capitalize()} Mixed MA alignment — SMAs not in clean order")
            score -= 0.1
        weight_count += 1

    # ── 2. Price vs key MAs ──
    above_mas = 0
    total_mas = 0
    ma_keys = ["SMA20", "SMA50", "SMA200"] if timeframe == "weekly" else ["SMA20", "SMA50", "SMA200", "EMA20", "EMA50", "EMA200"]
    for ma_key in ma_keys:
        val = data_fields.get(ma_key)
        if val is not None and not (isinstance(val, float) and math.isnan(val)) and close:
            total_mas += 1
            if close > val:
                above_mas += 1

    if total_mas >= 3:
        pct_above = above_mas / total_mas
        if pct_above >= 0.8:
            score += 0.5
            findings.append(f"✅ {timeframe.capitalize()} Price above {above_mas}/{total_mas} key MAs — strong uptrend")
        elif pct_above <= 0.3:
            score -= 0.5
            findings.append(f"⚠️ {timeframe.capitalize()} Price below {total_mas - above_mas}/{total_mas} key MAs — distribution")
        else:
            findings.append(f"📊 {timeframe.capitalize()} Price above {above_mas}/{total_mas} key MAs — mixed trend")
        weight_count += 1

    # ── 3. RSI ──
    rsi = data_fields.get("RSI")
    rsi_regime = "neutral"
    if rsi is not None and not (isinstance(rsi, float) and math.isnan(rsi)):
        if rsi < 10:
            rsi_regime = "oversold"
            score -= 0.3
            findings.append(f"🚨 {timeframe.capitalize()} RSI {rsi:.1f} — extreme oversold outlier")
        elif rsi > 95:
            rsi_regime = "overbought"
            score -= 0.3
            findings.append(f"🚨 {timeframe.capitalize()} RSI {rsi:.1f} — extreme overbought outlier")
        elif rsi < 30:
            rsi_regime = "oversold"
            score += 0.4
            findings.append(f"📉 {timeframe.capitalize()} RSI {rsi:.1f} — oversold, watch for reversal")
        elif rsi < 45:
            rsi_regime = "neutral_bearish"
            findings.append(f"📊 {timeframe.capitalize()} RSI {rsi:.1f} — bearish-neutral")
        elif rsi < 55:
            rsi_regime = "neutral"
            findings.append(f"📊 {timeframe.capitalize()} RSI {rsi:.1f} — neutral")
        elif rsi < 70:
            rsi_regime = "neutral_bullish"
            score += 0.3
            findings.append(f"✅ {timeframe.capitalize()} RSI {rsi:.1f} — healthy bullish zone")
        elif rsi < 80:
            rsi_regime = "overbought_warning"
            score -= 0.1
            findings.append(f"⚠️ {timeframe.capitalize()} RSI {rsi:.1f} — approaching overbought")
        else:
            rsi_regime = "overbought"
            score -= 0.4
            findings.append(f"🚨 {timeframe.capitalize()} RSI {rsi:.1f} — overbought, high pullback risk")
        weight_count += 1
    else:
        rsi_regime = "N/A"

    # ── 4. ADX (trend strength) ──
    adx = data_fields.get("ADX")
    adx_verdict = "N/A"
    if adx is not None and not (isinstance(adx, float) and math.isnan(adx)):
        if adx < 20:
            adx_verdict = "weak"
            score += 0.1
            findings.append(f"📊 {timeframe.capitalize()} ADX {adx:.1f} — weak trend")
        elif adx < 30:
            adx_verdict = "moderate"
            score += 0.2
            findings.append(f"✅ {timeframe.capitalize()} ADX {adx:.1f} — moderate trend")
        elif adx < 45:
            adx_verdict = "strong"
            score += 0.3
            findings.append(f"✅ {timeframe.capitalize()} ADX {adx:.1f} — strong trend")
        else:
            adx_verdict = "extreme"
            score -= 0.1
            findings.append(f"⚠️ {timeframe.capitalize()} ADX {adx:.1f} — extreme, watch exhaustion")
        weight_count += 1

    # ── 5. ATR (volatility) ──
    atr = data_fields.get("ATR")
    atr_pct = None
    volatility_regime = "normal"
    if atr and close:
        atr_pct = round(atr / close * 100, 2)
        if atr_pct < 1.0:
            volatility_regime = "low"
            score += 0.1
            findings.append(f"📊 {timeframe.capitalize()} ATR {atr_pct}% — low volatility")
        elif atr_pct < 3.0:
            volatility_regime = "normal"
            findings.append(f"📊 {timeframe.capitalize()} ATR {atr_pct}% — normal volatility")
        elif atr_pct < 5.0:
            volatility_regime = "high"
            score -= 0.2
            findings.append(f"⚠️ {timeframe.capitalize()} ATR {atr_pct}% — high volatility")
        else:
            volatility_regime = "extreme"
            score -= 0.4
            findings.append(f"🚨 {timeframe.capitalize()} ATR {atr_pct}% — extreme volatility")
        weight_count += 1

    # ── 6. Volume / relative volume ──
    rel_vol = data_fields.get("relative_volume_10d_calc")
    volume_ratio = rel_vol
    if rel_vol is not None:
        if rel_vol > 2.5:
            findings.append(f"✅ {timeframe.capitalize()} Volume {rel_vol:.1f}x avg — massive interest")
            score += 0.3
        elif rel_vol > 1.5:
            findings.append(f"✅ {timeframe.capitalize()} Volume {rel_vol:.1f}x avg — above average")
            score += 0.2
        elif rel_vol > 0.7:
            findings.append(f"📊 {timeframe.capitalize()} Volume {rel_vol:.1f}x avg — normal")
        else:
            findings.append(f"⚠️ {timeframe.capitalize()} Volume {rel_vol:.1f}x avg — low interest")
            score -= 0.2
        weight_count += 1

    # ── 7. Bollinger Band position ──
    bb_upper = data_fields.get("BB.upper")
    bb_lower = data_fields.get("BB.lower")
    bb_position = None
    if all(v is not None for v in [bb_upper, bb_lower]) and close:
        if close > bb_upper:
            bb_position = "above_upper"
            findings.append(f"⚠️ {timeframe.capitalize()} Price above BB upper ({bb_upper:.2f}) — extended")
        elif close < bb_lower:
            bb_position = "below_lower"
            score += 0.2
            findings.append(f"📈 {timeframe.capitalize()} Price below BB lower ({bb_lower:.2f}) — bounce setup")
        else:
            bb_position = "inside"
        weight_count += 1

    # ── 8. MACD ──
    macd_line = data_fields.get("MACD.macd")
    macd_signal = data_fields.get("MACD.signal")
    macd_status = None
    if macd_line is not None and macd_signal is not None:
        if macd_line > macd_signal:
            macd_status = "bullish"
            score += 0.2
        else:
            macd_status = "bearish"
            score -= 0.2
        weight_count += 1

    # ── Normalise score ──
    normalised = max(-1.0, min(1.0, score / weight_count * 3 if weight_count else 0))

    # Convert swings to price lists for output
    swing_highs = [h["price"] for h in swings.get("highs", [])]
    swing_lows = [l["price"] for l in swings.get("lows", [])]

    return TechnicalAnalysis(
        score=round(normalised, 2),
        ma_alignment=ma_alignment,
        rsi=round(rsi, 1) if rsi is not None and not (isinstance(rsi, float) and math.isnan(rsi)) else None,
        rsi_regime=rsi_regime,
        adx=round(adx, 1) if adx is not None and not (isinstance(adx, float) and math.isnan(adx)) else None,
        adx_verdict=adx_verdict,
        atr_pct=atr_pct,
        volatility_regime=volatility_regime,
        volume_ratio=round(volume_ratio, 2) if volume_ratio is not None else None,
        bb_position=bb_position,
        macd_status=macd_status,
        # Market structure fields
        structure=structure,
        swing_highs=swing_highs if swing_highs else None,
        swing_lows=swing_lows if swing_lows else None,
        key_resistance=key_resistance if key_resistance else None,
        key_support=key_support if key_support else None,
        pullback_quality=pullback_quality if pullback_quality != "unknown" else None,
        pullback_score=pullback_score if pullback_score > 0 else None,
        findings=findings,
    )
