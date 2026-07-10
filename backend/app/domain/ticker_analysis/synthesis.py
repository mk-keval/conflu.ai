"""Synthesis engine — combines all analysis modules into an actionable verdict."""

from __future__ import annotations

from typing import Any

from backend.app.domain.ticker_analysis.models import (
    AnalysisVerdict,
    EarningsAnalysis,
    FundamentalAnalysis,
    RiskAssessment,
    SentimentAnalysis,
    TechnicalAnalysis,
)

# ── Regime weight tables ──
# Each regime maps to weights per module: [tech, fund, earn, sent, risk]
REGIME_WEIGHTS: dict[str, list[float]] = {
    "strong_trend": [0.35, 0.20, 0.10, 0.25, 0.10],
    "ranging":      [0.25, 0.30, 0.20, 0.15, 0.10],
    "high_vol":     [0.20, 0.25, 0.10, 0.10, 0.35],
    "low_vol":      [0.30, 0.20, 0.10, 0.25, 0.15],
}

DEFAULT_WEIGHTS = [0.25, 0.25, 0.15, 0.20, 0.15]


def synthesise(
    technical: TechnicalAnalysis | None,
    fundamental: FundamentalAnalysis | None,
    earnings: EarningsAnalysis | None,
    sentiment: SentimentAnalysis | None,
    risk: RiskAssessment | None,
    price: float | None,
    regime: str | None = None,
    tv_data: dict[str, Any] | None = None,
) -> AnalysisVerdict:
    """Combine all module outputs into a final actionable verdict.

    Args:
        technical: Technical analysis result (or None if unavailable).
        fundamental: Fundamental analysis result.
        earnings: Earnings analysis result.
        sentiment: Sentiment analysis result.
        risk: Risk assessment result.
        price: Current price for entry/stop/target calculations.
        regime: Market regime for adaptive weighting (None = default).
        tv_data: Raw TV data fields for computing levels.

    Returns:
        AnalysisVerdict with final action, conviction, and trade details.
    """
    # ── 1. Collect scores ──
    modules = [
        ("technical", technical.score if technical else 0, technical.findings if technical else []),
        ("fundamental", fundamental.score if fundamental else 0, fundamental.findings if fundamental else []),
        ("earnings", earnings.score if earnings else 0, earnings.findings if earnings else []),
        ("sentiment", sentiment.score if sentiment else 0, sentiment.findings if sentiment else []),
        ("risk", risk.score if risk else 0, risk.findings if risk else []),
    ]

    scores = [m[1] for m in modules]
    all_findings: list[str] = []
    all_red_flags: list[str] = []
    buy_triggers: list[str] = []
    sell_triggers: list[str] = []

    for name, score, module_findings in modules:
        for f in module_findings:
            if f.startswith("🚨") or f.startswith("⚠️"):
                all_red_flags.append(f)

    for f in all_findings:
        if f.startswith("⚠️") or f.startswith("🚨"):
            all_red_flags.append(f)

    # ── 2. Apply regime-based weights ──
    weights = REGIME_WEIGHTS.get(regime if regime else "", DEFAULT_WEIGHTS)

    # Only weight modules that actually ran (non-None). A module with
    # score=0.0 may be a legitimate neutral analysis (all indicators
    # balanced) rather than "no data" — we still want its neutral opinion
    # counted. Modules that never ran (None from exception) are excluded
    # so their zero doesn't drag the average down.
    analysis_objs = [technical, fundamental, earnings, sentiment, risk]
    available = [(s, w) for s, w, obj in zip(scores, weights, analysis_objs) if obj is not None]
    if available:
        avail_scores, avail_weights = zip(*available)
        total_w = sum(avail_weights)
        if total_w > 0:
            normalized_weights = [w / total_w for w in avail_weights]
            weighted_score = sum(s * nw for s, nw in zip(avail_scores, normalized_weights))
        else:
            weighted_score = 0.0
    else:
        weighted_score = 0.0

    # ── 3. Check dealbreakers ──
    dealbreakers: list[str] = []

    # Earnings miss > 30%
    if earnings and earnings.last_surprise_pct is not None and earnings.last_surprise_pct < -30:
        dealbreakers.append(f"Earnings miss of {abs(earnings.last_surprise_pct):.0f}% — significant earnings failure")
        weighted_score -= 0.3

    # Micro-cap with no profitability
    if fundamental:
        mc = fundamental.market_cap or 0
        if mc < 50_000_000 and (fundamental.profit_margin is None or fundamental.profit_margin < 5):
            dealbreakers.append("Micro-cap with thin/no profitability — high risk of total loss")
            weighted_score -= 0.3

    # Cash burn rate — FCF loss exceeds 30% of market cap annually (LCID/RIVN risk)
    if fundamental and fundamental.fcf_yield is not None and fundamental.fcf_yield < -30:
        burn_pct = abs(fundamental.fcf_yield)
        dealbreakers.append(f"Free cash flow burn of {burn_pct:.0f}% of market cap — cash runway critical")
        weighted_score -= 0.5

    # Triple-negative combo: negative margins + negative FCF + extreme P/E
    # Catches deep value traps (INTC-style) where each individual signal alone
    # might not be enough but together they paint a clear picture.
    if fundamental:
        margin_bad = fundamental.profit_margin is not None and fundamental.profit_margin < 0
        fcf_bad = fundamental.fcf_yield is not None and fundamental.fcf_yield < 0
        pe_bad = fundamental.pe_ratio is not None and (
            fundamental.pe_ratio > 50 or fundamental.pe_ratio < 0
        )
        if margin_bad and fcf_bad and pe_bad:
            dealbreakers.append(
                "Negative margins, negative cash flow, and extreme valuation — "
                "multiple distress signals, avoid until turnaround visible"
            )
            weighted_score -= 0.5
            # Floor weighted_score so it cannot escape AVOID territory
            weighted_score = min(weighted_score, -0.5)

    # Extreme RSI overbought + no strong fundamental backing
    if technical and technical.rsi is not None and technical.rsi > 85:
        fund_score = fundamental.score if fundamental else 0
        if fund_score < 0.3:
            dealbreakers.append(f"RSI {technical.rsi:.0f} (extreme) without strong fundamental support")
            weighted_score -= 0.2

    # Extreme micro-cap / pump-and-dump / penny stock (detected in risk module)
    if risk:
        for f in risk.findings:
            if any(kw in f.lower() for kw in ["pump-and-dump", "size near zero", "penny stock", "manipulation"]):
                dealbreakers.append("Extreme micro-cap or penny stock with dangerous characteristics — avoid")
                weighted_score -= 0.5
                break

    # Extreme RSI anomaly — statistical outlier requiring investigation
    if technical and technical.rsi is not None:
        if technical.rsi < 10:
            dealbreakers.append(f"RSI {technical.rsi:.0f} — statistical outlier, investigate catalyst before acting")
            weighted_score -= 0.2
        elif technical.rsi > 95:
            dealbreakers.append(f"RSI {technical.rsi:.0f} — statistical outlier, likely unsustainable move")
            weighted_score -= 0.2

    # Extreme volatility
    if risk and risk.volatility_regime == "extreme":
        dealbreakers.append("Extreme volatility regime — widen stops significantly or skip")
        weighted_score -= 0.2

    # ── 4. Map score to action ──
    base_action: str
    conviction: int
    dealbreaker_active = len(dealbreakers) > 0

    if weighted_score >= 0.7 and not dealbreaker_active:
        base_action = "BUY"
        conviction = min(10, 6 + int((weighted_score - 0.7) * 15))
    elif weighted_score >= 0.5 and not dealbreaker_active:
        base_action = "ACCUMULATE"
        conviction = 4 + int((weighted_score - 0.5) * 10)
    elif weighted_score >= 0.3 and not dealbreaker_active:
        base_action = "ACCUMULATE"
        conviction = 2 + int((weighted_score - 0.3) * 12)
    elif weighted_score >= 0.1:
        base_action = "WATCH"
        conviction = 2 + int((weighted_score - 0.1) * 10) if weighted_score > 0 else 2
        conviction = min(conviction, 4)
    elif weighted_score > -0.1:
        base_action = "HOLD" if not dealbreaker_active else "WATCH"
        conviction = 3
    elif weighted_score > -0.3:
        base_action = "HOLD"
        conviction = 4 + int(abs(weighted_score) * 10)
        conviction = min(conviction, 6)
    elif weighted_score > -0.5:
        base_action = "REDUCE"
        conviction = 5 + int(abs(weighted_score) * 10)
        conviction = min(conviction, 8)
    else:
        base_action = "AVOID"
        conviction = min(10, 7 + int(abs(weighted_score) * 6))

    conviction = max(1, min(10, conviction))
    action = base_action

    # ── 5. Generate triggers ──
    # Technical triggers
    if technical:
        if technical.rsi_regime == "overbought":
            sell_triggers.append(f"Sell if RSI drops below 50 (momentum failure). Buy on pullback to RSI 40-50 zone.")
        elif technical.rsi_regime in ("oversold", "neutral_bearish"):
            buy_triggers.append(f"Watch for RSI crossing above 50 (momentum reversal confirmation).")
        if technical.ma_alignment == "bullish":
            buy_triggers.append("Trend is up — buy on pullbacks to rising MA support (SMA20 or SMA50).")
        elif technical.ma_alignment == "bearish":
            sell_triggers.append("Trend is down — avoid longs until MA stack realigns bullishly.")

    # Fundamental triggers
    if fundamental:
        if fundamental.revenue_growth_yoy is not None and fundamental.revenue_growth_yoy < 3:
            buy_triggers.append("Need next quarter revenue growth to accelerate above 3% YoY to confirm thesis.")
        if fundamental.pe_ratio and fundamental.pe_ratio > 30:
            sell_triggers.append("Premium P/E requires consistent earnings beats to sustain. Miss → re-rate lower.")

    # Earnings triggers
    if earnings:
        if earnings.last_surprise_pct is not None and earnings.last_surprise_pct < 0:
            buy_triggers.append(f"Become constructive after next earnings beat > 3%.")
        elif earnings.last_surprise_pct is not None and earnings.last_surprise_pct > 10:
            sell_triggers.append("Watch for deceleration in earnings surprise — tough comps ahead.")

    # Sentiment triggers
    if sentiment:
        if sentiment.insider_status == "selling":
            sell_triggers.append("Insider selling is a caution signal. Wait for insider buying or at least neutral before initiating.")
        if sentiment.short_interest_pct is not None and sentiment.short_interest_pct > 15:
            buy_triggers.append("High short interest + improving fundamentals = potential squeeze catalyst.")

    # ── 6. Calculate entry zone, stop, targets ──
    entry_low = None
    entry_high = None
    stop_loss = None
    targets: list[float] = []
    rr = None

    if price and price > 0:
        close = price
        atr = None
        if tv_data:
            atr = tv_data.get("ATR") or tv_data.get("atr")

        if risk and risk.suggested_stop_pct > 0:
            stop_pct = risk.suggested_stop_pct / 100
        elif atr:
            # Fallback: 2x ATR from price
            stop_pct = (atr * 2) / close if close and atr else 0.05
        else:
            stop_pct = 0.05

        # Entry zone: current price for buy, or 2-5% below
        if action in ("BUY", "ACCUMULATE", "WATCH"):
            if technical and technical.rsi_regime in ("overbought", "overbought_warning"):
                # Don't chase — suggest pullback entry
                drawdown_target = stop_pct * 1.5
                entry_low = round(close * (1 - drawdown_target), 2)
                entry_high = round(close, 2)
            else:
                entry_low = round(close * 0.98, 2)
                entry_high = round(close * 1.01, 2)

        stop_loss = round(close * (1 - max(stop_pct, 0.02)), 2)

        # Targets: 1.5x R and 3x R
        if stop_loss > 0:
            risk_per_share = (entry_high or close) - stop_loss if (entry_high or close) > stop_loss else stop_loss * 0.1
            t1 = round((entry_high or close) + risk_per_share * 1.5, 2)
            t2 = round((entry_high or close) + risk_per_share * 3.0, 2)
            targets = [t1, t2]

            # Risk/reward to first target
            rr = round(1.5, 2)

    # ── 7. Generate thesis ──
    thesis = _generate_thesis(action, weighted_score, modules, dealbreakers, regime)

    return AnalysisVerdict(
        action=action,
        conviction=conviction,
        entry_zone_low=entry_low,
        entry_zone_high=entry_high,
        stop_loss=stop_loss,
        targets=targets,
        risk_reward=rr,
        position_size_pct=risk.suggested_position_size_pct if risk else 0,
        key_red_flags=dealbreakers + [f for f in all_red_flags if f not in dealbreakers][:5],
        buy_triggers=buy_triggers[:3],
        sell_triggers=sell_triggers[:3],
        thesis=thesis,
    )


def _generate_thesis(
    action: str,
    score: float,
    modules: list[tuple[str, float, list[str]]],
    dealbreakers: list[str],
    regime: str | None,
) -> str:
    """Generate a concise one-paragraph thesis from all evidence."""
    parts: list[str] = []

    if action == "BUY":
        parts.append(f"Bullish setup with conviction score {score:.0%}.")
    elif action == "ACCUMULATE":
        parts.append(f"Moderately bullish (score {score:.0%}). Build position on pullbacks.")
    elif action == "AVOID":
        parts.append(f"Bearish outlook (score {score:.0%}). Avoid until conditions improve.")
    elif action == "REDUCE":
        parts.append(f"Moderately bearish (score {score:.0%}). Reduce position size or tighten stops.")
    elif action == "WATCH":
        parts.append(f"Mixed signals (score {score:.0%}). Monitoring for setup to develop.")
    else:
        parts.append(f"Neutral outlook (score {score:.0%}). No strong directional edge.")

    # Top positive signal
    pos_findings = [f for _, _, flist in modules for f in flist if f.startswith("✅") or f.startswith("💰")]
    neg_findings = [f for _, _, flist in modules for f in flist if f.startswith("🚨") or f.startswith("⚠️")]

    if pos_findings:
        parts.append(f"Bull case: {pos_findings[0][2:] if pos_findings[0].startswith(('✅ ', '💰 ')) else pos_findings[0]}.")
    if neg_findings and action in ("WATCH", "AVOID", "HOLD"):
        parts.append(f"Bear case: {neg_findings[0][2:] if neg_findings[0].startswith(('🚨 ', '⚠️ ')) else neg_findings[0]}.")

    # Promote dividend yield to bull case when it's the strongest signal
    if action in ("WATCH", "HOLD") and pos_findings:
        div_findings = [f for f in pos_findings if "dividend" in f.lower()]
        non_div_pos = [f for f in pos_findings if "dividend" not in f.lower()]
        if div_findings and not any("margin" in f.lower() or "growth" in f.lower() for f in non_div_pos):
            # If the only positives are dividend-related, lead with that
            pass  # Will naturally use dividend finding since it's the first/only positive

    if regime:
        parts.append(f"Market regime: {regime.replace('_', ' ').title()}.")

    if dealbreakers:
        parts.append(f"⚠️ Dealbreaker: {dealbreakers[0]}")

    return " ".join(parts)
