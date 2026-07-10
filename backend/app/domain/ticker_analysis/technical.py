"""Technical analysis module — evaluates price structure, momentum, and volatility."""

from __future__ import annotations

import math
from typing import Any

from backend.app.domain.ticker_analysis.models import TechnicalAnalysis


def analyze(data_fields: dict[str, Any]) -> TechnicalAnalysis:
    """Analyse technical indicators from TV screener data.

    Expects keys like: close, RSI, ADX, ATR, SMA20, SMA50, SMA200,
    EMA20, EMA50, EMA200, VWAP, BB.upper, BB.lower, volume,
    relative_volume_10d_calc, change, MACD.macd, MACD.signal.
    """
    findings: list[str] = []
    score = 0.0
    weight_count = 0

    close = data_fields.get("close") or data_fields.get("Close") or 0

    # ── 1. Trend: MA Alignment ──
    # Try SMA first (yfinance fallback), then EMA (TV data) — TV selects EMA20/50/200
    sma20 = data_fields.get("SMA20") or data_fields.get("EMA20")
    sma50 = data_fields.get("SMA50") or data_fields.get("EMA50")
    sma200 = data_fields.get("SMA200") or data_fields.get("EMA200")

    if all(v is not None and not (isinstance(v, float) and math.isnan(v)) for v in [sma20, sma50, sma200]):
        if sma20 > sma50 > sma200 and close > sma20:
            ma_alignment = "bullish"
            findings.append(f"✅ Bullish MA stack: SMA20 ({sma20:.2f}) > SMA50 ({sma50:.2f}) > SMA200 ({sma200:.2f})")
            score += 1.0
        elif sma20 < sma50 < sma200 and close < sma20:
            ma_alignment = "bearish"
            findings.append(f"⚠️ Bearish MA stack: SMA20 ({sma20:.2f}) < SMA50 ({sma50:.2f}) < SMA200 ({sma200:.2f})")
            score -= 0.8
        else:
            ma_alignment = "mixed"
            findings.append(f"📊 Mixed MA alignment — SMAs not in clean order (SMA20={sma20:.2f}, SMA50={sma50:.2f}, SMA200={sma200:.2f})")
            score -= 0.1
        weight_count += 1
    else:
        ma_alignment = "N/A"

    # ── 2. Price vs key MAs ──
    above_mas = 0
    total_mas = 0
    for ma_key in ["SMA20", "SMA50", "SMA200", "EMA20", "EMA50", "EMA200"]:
        val = data_fields.get(ma_key)
        if val is not None and not (isinstance(val, float) and math.isnan(val)) and close:
            total_mas += 1
            if close > val:
                above_mas += 1

    if total_mas >= 3:
        pct_above = above_mas / total_mas
        if pct_above >= 0.8:
            score += 0.5
            findings.append(f"✅ Price above {above_mas}/{total_mas} key MAs — strong uptrend")
        elif pct_above <= 0.3:
            score -= 0.5
            findings.append(f"⚠️ Price below {total_mas - above_mas}/{total_mas} key MAs — distribution")
        else:
            findings.append(f"📊 Price above {above_mas}/{total_mas} key MAs — mixed trend")
        weight_count += 1

    # ── 3. RSI ──
    rsi = data_fields.get("RSI")
    rsi_regime = "neutral"
    if rsi is not None and not (isinstance(rsi, float) and math.isnan(rsi)):
        # Extreme RSI outlier — statistical anomaly, not a typical signal
        if rsi < 10:
            rsi_regime = "oversold"
            score -= 0.3  # Statistical outlier, likely data issue or catalyst-driven crash
            findings.append(f"🚨 RSI {rsi:.1f} — extreme oversold outlier, investigate catalyst before acting")
        elif rsi > 95:
            rsi_regime = "overbought"
            score -= 0.3  # Statistical outlier, unsustainable
            findings.append(f"🚨 RSI {rsi:.1f} — extreme overbought outlier, likely unsustainable move")
        elif rsi < 30:
            rsi_regime = "oversold"
            score += 0.4  # Potential bounce setup
            findings.append(f"📉 RSI {rsi:.1f} — oversold territory, watch for reversal")
        elif rsi < 45:
            rsi_regime = "neutral_bearish"
            findings.append(f"📊 RSI {rsi:.1f} — bearish-neutral, lacking momentum")
        elif rsi < 55:
            rsi_regime = "neutral"
            findings.append(f"📊 RSI {rsi:.1f} — neutral, no directional edge")
        elif rsi < 70:
            rsi_regime = "neutral_bullish"
            score += 0.3
            findings.append(f"✅ RSI {rsi:.1f} — healthy bullish zone (55-70)")
        elif rsi < 80:
            rsi_regime = "overbought_warning"
            score -= 0.1
            findings.append(f"⚠️ RSI {rsi:.1f} — approaching overbought, extended")
        else:
            rsi_regime = "overbought"
            score -= 0.4
            findings.append(f"🚨 RSI {rsi:.1f} — overbought, high risk of pullback")
        weight_count += 1
    else:
        rsi_regime = "N/A"

    # ── 4. ADX (trend strength) ──
    adx = data_fields.get("ADX")
    adx_verdict = "N/A"
    if adx is not None and not (isinstance(adx, float) and math.isnan(adx)):
        if adx < 20:
            adx_verdict = "weak"
            score += 0.1  # Range-bound, no trend
            findings.append(f"📊 ADX {adx:.1f} — weak trend, range-bound market")
        elif adx < 30:
            adx_verdict = "moderate"
            score += 0.2
            findings.append(f"✅ ADX {adx:.1f} — moderate trend developing")
        elif adx < 45:
            adx_verdict = "strong"
            score += 0.3
            findings.append(f"✅ ADX {adx:.1f} — strong trending conditions")
        else:
            adx_verdict = "extreme"
            score -= 0.1  # Could be climax / exhaustion
            findings.append(f"⚠️ ADX {adx:.1f} — extreme trend, watch for exhaustion")
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
            findings.append(f"📊 ATR {atr_pct}% — low volatility environment")
        elif atr_pct < 3.0:
            volatility_regime = "normal"
            findings.append(f"📊 ATR {atr_pct}% — normal volatility")
        elif atr_pct < 5.0:
            volatility_regime = "high"
            score -= 0.2
            findings.append(f"⚠️ ATR {atr_pct}% — high volatility, wider stops needed")
        else:
            volatility_regime = "extreme"
            score -= 0.4
            findings.append(f"🚨 ATR {atr_pct}% — extreme volatility, size down")
        weight_count += 1

    # ── 6. Volume / relative volume ──
    rel_vol = data_fields.get("relative_volume_10d_calc")
    volume_ratio = rel_vol
    if rel_vol is not None:
        if rel_vol > 2.5:
            findings.append(f"✅ Volume {rel_vol:.1f}x avg — massive accumulation / interest")
            score += 0.3
        elif rel_vol > 1.5:
            findings.append(f"✅ Volume {rel_vol:.1f}x avg — above-average participation")
            score += 0.2
        elif rel_vol > 0.7:
            findings.append(f"📊 Volume {rel_vol:.1f}x avg — normal activity")
        else:
            findings.append(f"⚠️ Volume {rel_vol:.1f}x avg — low interest, illiquid")
            score -= 0.2
        weight_count += 1

    # ── 7. Bollinger Band position ──
    bb_upper = data_fields.get("BB.upper")
    bb_lower = data_fields.get("BB.lower")
    bb_position = None
    if all(v is not None for v in [bb_upper, bb_lower]) and close:
        if close > bb_upper:
            bb_position = "above_upper"
            findings.append(f"⚠️ Price above BB upper band ({bb_upper:.2f}) — extended, potential mean reversion")
        elif close < bb_lower:
            bb_position = "below_lower"
            score += 0.2
            findings.append(f"📈 Price below BB lower band ({bb_lower:.2f}) — potential bounce setup")
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
        findings=findings,
    )
