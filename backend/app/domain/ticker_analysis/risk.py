"""Risk assessment module — evaluates portfolio risk and position sizing."""

from __future__ import annotations

import math
from typing import Any

from backend.app.domain.ticker_analysis.models import RiskAssessment

# Default risk parameters
DEFAULT_MAX_RISK_PCT = 1.0  # Risk no more than 1% of portfolio per trade
DEFAULT_ATR_STOP_MULTIPLIER = 2.0  # Stop = 2x ATR from entry


def analyze(data_fields: dict[str, Any], info: dict[str, Any]) -> RiskAssessment:
    """Assess risk and calculate position sizing recommendations.

    Uses TV data for ATR/volatility, yfinance info for beta/overall risk.
    """
    findings: list[str] = []
    score = 0.0
    weight_count = 0

    close = data_fields.get("close") or data_fields.get("Close") or 0
    atr = data_fields.get("ATR")
    mkt_cap = info.get("marketCap") or info.get("market_cap") or 0

    # ── Extreme Micro-Cap / Pump-and-Dump Detection ──
    # Sub-$10M market cap with extreme characteristics is a strong
    # indicator of a pump-and-dump or illiquid penny stock.
    # Use multiple signals: ATR > 20%, price < $1, low dollar volume.
    is_dangerous_microcap = False
    if mkt_cap and 0 < mkt_cap < 10_000_000 and close:
        atr_pct_check = (atr / close * 100) if atr else 0
        # Signal 1: Very low absolute price (< $1) — classic penny stock
        is_penny = close < 1.0
        # Signal 2: Extreme ATR volatility
        is_high_vol = atr_pct_check > 20
        # Signal 3: Very low dollar volume (illiquid)
        volume = data_fields.get("volume") or data_fields.get("Volume") or 0
        dollar_vol = volume * close
        is_illiquid = bool(dollar_vol and dollar_vol < 500_000)

        if is_high_vol:
            findings.append(
                f"🚨 Micro-cap with {atr_pct_check:.0f}% ATR — "
                f"likely pump-and-dump or illiquid, skip"
            )
            score -= 0.8
            is_dangerous_microcap = True
        elif is_penny and is_illiquid:
            findings.append(
                f"🚨 Penny stock (${close:.4f}) with illiquid volume — "
                f"extreme risk of manipulation, avoid"
            )
            score -= 0.8
            is_dangerous_microcap = True
        elif is_penny:
            findings.append(
                f"🚨 Penny stock (${close:.4f}) — sub-$1 micro-cap, "
                f"high risk of total loss"
            )
            score -= 0.5
            is_dangerous_microcap = True
        elif is_illiquid:
            findings.append(
                f"🚨 Micro-cap with extremely low dollar volume "
                f"(${dollar_vol:,.0f}) — significant slippage risk"
            )
            score -= 0.3

    # Track that we checked (for weight_count) — conditional, but signal matters
    if mkt_cap and mkt_cap < 10_000_000:
        weight_count += 1

    # ── Volatility Regime via ATR ──
    volatility_regime = "normal"
    atr_pct = None
    if atr and close:
        atr_pct = atr / close * 100
        if atr_pct < 1.0:
            volatility_regime = "low"
            findings.append(f"📊 Low volatility (ATR {atr_pct:.2f}%) — tighter stops possible")
            score += 0.2
        elif atr_pct < 3.0:
            volatility_regime = "normal"
            findings.append(f"📊 Normal volatility (ATR {atr_pct:.2f}%)")
        elif atr_pct < 5.0:
            volatility_regime = "high"
            findings.append(f"⚠️ High volatility (ATR {atr_pct:.2f}%) — wider stops needed")
            score -= 0.2
        else:
            volatility_regime = "extreme"
            findings.append(f"🚨 Extreme volatility (ATR {atr_pct:.2f}%) — size down significantly")
            score -= 0.4
    weight_count += 1

    # ── Suggested Stop Loss ──
    suggested_stop_pct: float
    if atr and close:
        atr_pct_val = atr / close
        suggested_stop_pct = round(atr_pct_val * DEFAULT_ATR_STOP_MULTIPLIER * 100, 2)
        findings.append(f"🛑 Suggested stop: {suggested_stop_pct}% below entry ({DEFAULT_ATR_STOP_MULTIPLIER}x ATR)")
    else:
        suggested_stop_pct = 5.0  # Default 5% stop when no ATR
        findings.append(f"🛑 Default stop: {suggested_stop_pct}% (no ATR data available)")

    # ── Beta (systematic risk) ──
    beta = info.get("beta")
    if beta is not None:
        if beta > 2.0:
            findings.append(f"⚠️ Beta {beta:.2f} — very high systematic risk (2x+ market swings)")
            score -= 0.3
        elif beta > 1.3:
            findings.append(f"⚠️ Beta {beta:.2f} — high systematic risk")
            score -= 0.1
        elif beta > 0.8:
            findings.append(f"✅ Beta {beta:.2f} — in-line with market")
        elif beta > 0.4:
            findings.append(f"✅ Beta {beta:.2f} — lower than market risk")
            score += 0.1
        else:
            findings.append(f"✅ Beta {beta:.2f} — very low market correlation (defensive)")
            score += 0.2
    weight_count += 1

    # ── Position Sizing (Kelly / Fixed Fraction) ──
    # Simplified Kelly: f* = (probability_of_win * avg_win - probability_of_loss * avg_loss) / avg_win
    # When we don't have a backtest, use fixed fraction based on risk
    suggested_size: float
    risk_per_unit = suggested_stop_pct / 100  # as decimal

    if risk_per_unit > 0:
        # Fixed fraction: maximum position = max_risk / stop_percentage
        suggested_size = round(DEFAULT_MAX_RISK_PCT / risk_per_unit, 1)
        # Default cap
        suggested_size = min(suggested_size, 20.0)
        suggested_size = max(suggested_size, 0.5)
    else:
        suggested_size = 2.0

    # ── Risk-Class-Based Position Sizing Caps ──
    # Different instrument types and market cap ranges warrant different
    # maximum position sizes regardless of what the Kelly formula suggests.
    instrument_type = info.get("instrument_type", "equity")
    mkt_cap = info.get("marketCap") or info.get("market_cap") or 0

    if instrument_type == "spac":
        # SPACs are binary event-driven instruments — never > 3%
        suggested_size = min(suggested_size, 3.0)
        findings.append(f"⚠️ SPAC risk cap: max 3% of portfolio (binary event risk)")
    elif instrument_type == "etf":
        # ETFs are diversified — standard cap applies
        suggested_size = min(suggested_size, 20.0)
    elif instrument_type == "etn":
        # ETNs carry issuer credit risk — cap at 10%
        suggested_size = min(suggested_size, 10.0)
        findings.append(f"⚠️ ETN credit risk cap: max 10% of portfolio")
    elif instrument_type == "bdc":
        # BDCs are levered loan portfolios — cap at 10%
        suggested_size = min(suggested_size, 10.0)
        findings.append(f"⚠️ BDC leverage risk cap: max 10% of portfolio")
    elif instrument_type == "preferred":
        # Preferred stocks are fixed-income hybrids — cap at 10%
        suggested_size = min(suggested_size, 10.0)
        findings.append(f"⚠️ Preferred stock risk cap: max 10% of portfolio (credit/hybrid risk)")

    # OTC/Pink listing penalty — low liquidity, wide spreads, limited disclosure
    exchange = info.get("exchange") or info.get("exchangeCode") or ""
    exchange_upper = exchange.upper() if exchange else ""
    otc_codes = {"OTC", "PNK", "OQB", "OQX", "OTCQX", "OTCQB"}
    is_otc = exchange_upper in otc_codes or exchange_upper.startswith("OTC")
    if is_otc:
        suggested_size = min(suggested_size, 3.0)
        findings.append(f"⚠️ OTC-listed risk cap: max 3% of portfolio (low liquidity, wide spreads)")

    # Market-cap-based position caps don't apply to ETFs/CEFs.
    # Their market cap reflects fund AUM (null for many fund listings),
    # not company size risk. GDX ($30B+ AUM) and TLT ($50B+ AUM) should
    # never get a micro-cap cap.
    if instrument_type not in ("etf", "cef", "preferred"):
        if mkt_cap < 50_000_000:
            # Micro-cap: extreme risk
            suggested_size = min(suggested_size, 2.0)
            findings.append(f"⚠️ Micro-cap risk cap: max 2% of portfolio")
        elif mkt_cap < 300_000_000:
            # Small-cap: higher risk
            suggested_size = min(suggested_size, 5.0)
            findings.append(f"⚠️ Small-cap risk cap: max 5% of portfolio")
        elif mkt_cap < 1_000_000_000:
            # Mid-small-cap
            suggested_size = min(suggested_size, 10.0)
        else:
            # Established companies: standard cap
            suggested_size = min(suggested_size, 15.0)

    # Volatility-based cap override: extreme vol = smaller positions
    if volatility_regime == "extreme":
        suggested_size = min(suggested_size, 3.0)
        findings.append(f"⚠️ Extreme volatility cap: max 3% of portfolio")
    elif volatility_regime == "high":
        suggested_size = min(suggested_size, 8.0)

    findings.append(f"📐 Suggested position: {suggested_size}% of portfolio ({DEFAULT_MAX_RISK_PCT}% risk @ {suggested_stop_pct}% stop)")

    # ── Liquidity Check ──
    volume = data_fields.get("volume") or data_fields.get("Volume") or 0
    mkt_cap = info.get("marketCap") or 0
    if volume and close:
        dollar_volume = volume * close
        if dollar_volume < 1_000_000:
            findings.append("🚨 Very low dollar volume — significant slippage risk")
            score -= 0.5
        elif dollar_volume < 10_000_000:
            findings.append("⚠️ Low liquidity — use limit orders, expect some slippage")
            score -= 0.2
        elif dollar_volume > 100_000_000:
            findings.append("✅ High liquidity — tight spreads, easy execution")
            score += 0.2
    weight_count += 1

    # ── Max Drawdown (from yfinance) ──
    fifty_two_week_low = info.get("fiftyTwoWeekLow")
    fifty_two_week_high = info.get("fiftyTwoWeekHigh")
    if fifty_two_week_low and fifty_two_week_high:
        drawdown = (fifty_two_week_high - fifty_two_week_low) / fifty_two_week_high * 100
        if drawdown > 50:
            findings.append(f"⚠️ 52-week range: {fifty_two_week_low:.2f}–{fifty_two_week_high:.2f} ({drawdown:.0f}% peak-to-trough)")
        else:
            findings.append(f"📊 52-week range: {fifty_two_week_low:.2f}–{fifty_two_week_high:.2f} ({drawdown:.0f}% range)")

    normalised = max(-1.0, min(1.0, score / max(weight_count, 1) * 2))

    return RiskAssessment(
        score=round(normalised, 2),
        volatility_regime=volatility_regime,
        suggested_stop_pct=suggested_stop_pct,
        suggested_position_size_pct=suggested_size,
        max_risk_per_trade_pct=DEFAULT_MAX_RISK_PCT,
        findings=findings,
    )
