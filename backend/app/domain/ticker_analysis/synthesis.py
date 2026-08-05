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
    TradePlan,
)

# ── Regime weight tables ──
# Each regime maps to weights per module: [tech, fund, earn, sent, risk]
REGIME_WEIGHTS: dict[str, list[float]] = {
    "strong_trend": [0.35, 0.20, 0.10, 0.25, 0.10],
    "ranging":      [0.25, 0.30, 0.20, 0.15, 0.10],
    "high_vol":     [0.20, 0.25, 0.10, 0.10, 0.35],
    "low_vol":      [0.30, 0.20, 0.10, 0.25, 0.15],
}

DEFAULT_WEIGHTS = [0.30, 0.22, 0.12, 0.20, 0.16]


def _calculate_dynamic_rr(
    technical: TechnicalAnalysis | None,
    risk: RiskAssessment | None,
    fundamental: FundamentalAnalysis | None,
    action: str,
) -> float:
    """Calculate dynamic risk/reward ratio based on setup quality.
    
    An elite trader adjusts targets based on:
    - Trend quality (strong trend = wider targets)
    - Volatility regime (low vol = more predictable = wider targets)
    - Fundamental backing (strong fundamentals = more room to run)
    - Action type (counter-trend = tighter targets)
    """
    base_rr = 1.5  # Default 1.5:1
    
    # Trend quality adjustment
    if technical:
        if technical.ma_alignment == "bullish" and technical.adx and technical.adx > 30:
            base_rr += 0.5  # Strong trend = wider targets (2.0:1)
        elif technical.ma_alignment == "bullish" and technical.adx and technical.adx > 20:
            base_rr += 0.3  # Moderate trend (1.8:1)
        elif technical.ma_alignment == "bearish":
            base_rr -= 0.3  # Counter-trend = tighter targets (1.2:1)
        elif technical.macd_status == "bullish" and technical.rsi_regime in ("neutral_bullish", "overbought_warning"):
            base_rr += 0.2  # Momentum aligned (1.7:1)
    
    # Volatility regime adjustment
    if risk:
        if risk.volatility_regime == "low":
            base_rr += 0.2  # Low vol = predictable moves (1.7:1)
        elif risk.volatility_regime == "high":
            base_rr -= 0.2  # High vol = noisy (1.3:1)
        elif risk.volatility_regime == "extreme":
            base_rr -= 0.4  # Extreme vol = very noisy (1.1:1)
    
    # Fundamental quality adjustment
    if fundamental:
        if fundamental.profit_margin and fundamental.profit_margin > 15:
            base_rr += 0.2  # High quality = more room
        if fundamental.revenue_growth_yoy and fundamental.revenue_growth_yoy > 15:
            base_rr += 0.1  # Growth = momentum
        if fundamental.fcf_yield and fundamental.fcf_yield > 5:
            base_rr += 0.1  # Cash generation = support
    
    # Action-specific caps
    if action in ("ACCUMULATE", "WATCH"):
        base_rr = min(base_rr, 2.0)  # Cap for non-BUY actions
    elif action == "BUY":
        base_rr = min(base_rr, 3.0)  # BUY can go up to 3:1
    
    # Floor at 1.0:1
    return round(max(1.0, base_rr), 2)


def synthesise(
    technical: TechnicalAnalysis | None,
    fundamental: FundamentalAnalysis | None,
    earnings: EarningsAnalysis | None,
    sentiment: SentimentAnalysis | None,
    risk: RiskAssessment | None,
    price: float | None,
    regime: str | None = None,
    tv_data: dict[str, Any] | None = None,
    technical_weekly: TechnicalAnalysis | None = None,
) -> AnalysisVerdict:
    """Combine all module outputs into a final actionable verdict.

    Args:
        technical: Technical analysis result (daily, or None if unavailable).
        fundamental: Fundamental analysis result.
        earnings: Earnings analysis result.
        sentiment: Sentiment analysis result.
        risk: Risk assessment result.
        price: Current price for entry/stop/target calculations.
        regime: Market regime for adaptive weighting (None = default).
        tv_data: Raw TV data fields for computing levels.
        technical_weekly: Weekly technical analysis for multi-timeframe alignment.

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
    avail_scores: tuple[float, ...] = ()
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

    # ── 2a. Module coherence adjustment ──
    # When modules disagree (high variance in scores), reduce conviction.
    # When they agree (low variance), boost conviction.
    # This prevents muddled setups (e.g., perfect technical + weak fundamental)
    # from scoring the same as clean setups where all modules align.
    if len(avail_scores) >= 3:
        score_range = max(avail_scores) - min(avail_scores)
        if score_range > 1.5:
            # Major disagreement: penalize
            coherence_penalty = 0.08 * (score_range / 2.0)
            weighted_score -= min(coherence_penalty, 0.2)
            all_findings.append(f"⚠️ Module disagreement: scores range {min(avail_scores):.2f}–{max(avail_scores):.2f} "
                                f"({score_range:.2f}) — conviction reduced")
        elif score_range < 0.3 and weighted_score > 0.3:
            # Strong agreement on a positive setup: small bonus
            weighted_score += 0.05
            all_findings.append(f"✅ Module agreement: all scores within {score_range:.2f} — conviction confirmed")

    # ── 2b. Multi-timeframe alignment ──
    # Weekly trend is the primary filter for swing trading. A daily signal against
    # the weekly trend (e.g., daily bounce on weekly downtrend) gets penalized —
    # those bounces are traps. A daily pullback in a weekly uptrend is a healthy
    # entry opportunity and receives a small bonus.
    if technical_weekly and technical:
        weekly_alignment = technical_weekly.ma_alignment
        daily_structure = technical.structure or "neutral"
        daily_alignment = technical.ma_alignment

        if weekly_alignment == "bullish":
            if daily_alignment == "bullish":
                # Bullish alignment on both timeframes — strongest signal
                weighted_score += 0.08
                all_findings.append("📈 Multi-timeframe: bullish weekly + bullish daily — strong trend alignment")
            elif daily_structure in ("bearish", "transition"):
                # Daily pullback in weekly uptrend — healthy entry opportunity
                weighted_score += 0.03
                all_findings.append("📊 Multi-timeframe: bullish weekly, daily pullback — swing entry opportunity")
        elif weekly_alignment == "bearish":
            if daily_alignment == "bearish":
                # Bearish on both — confirm downside
                weighted_score -= 0.10
                all_findings.append("📉 Multi-timeframe: bearish weekly + bearish daily — strong downside alignment")
            elif daily_alignment == "bullish" or daily_structure == "bullish":
                # Daily bounce in weekly downtrend — trap, penalize
                weighted_score -= 0.15
                all_findings.append("⚠️ Multi-timeframe: bearish weekly, daily bounce — likely counter-trend trap, avoid longs")
        # If weekly is mixed/ranging → no adjustment (weekly provides no clear signal)

    # ── 3. Check dealbreakers ──
    dealbreakers: list[str] = []

    # ── 3a. Volume-Price Divergence ──
    # Rising volume + falling price = distribution (bearish)
    # Rising volume + rising price = accumulation (bullish)
    # This catches distribution risk even when MA alignment looks bullish
    if tv_data:
        tv_close = tv_data.get("close") or tv_data.get("Close")
        tv_volume = tv_data.get("volume") or tv_data.get("Volume")
        prev_close = tv_data.get("prev_close") or tv_data.get("prevClose")
        avg_volume = tv_data.get("volume_avg_50") or tv_data.get("VolumeAvg50")
        change_pct = tv_data.get("change")
        if change_pct is None and tv_close and prev_close:
            change_pct = ((tv_close / prev_close) - 1) * 100
        
        # Detect distribution: price down on elevated volume
        if (tv_close is not None and tv_volume is not None 
                and avg_volume is not None and avg_volume > 0):
            vol_ratio = tv_volume / avg_volume
            if vol_ratio > 1.5 and change_pct is not None and change_pct < -2:
                dist_severity = "heavy" if vol_ratio > 2.5 else "moderate"
                dealbreakers.append(
                    f"⚠️ {dist_severity.title()} distribution risk: {change_pct:+.1f}% drop on "
                    f"{vol_ratio:.1f}× avg volume ({tv_volume:,.0f} vs {avg_volume:,.0f} avg) — "
                    "institutional selling pressure"
                )
                weighted_score -= 0.3 if vol_ratio > 2.5 else 0.15
            # Detect accumulation: price up on elevated volume
            elif vol_ratio > 1.5 and change_pct is not None and change_pct > 2:
                all_findings.append(
                    f"📊 Accumulation signal: {change_pct:+.1f}% gain on "
                    f"{vol_ratio:.1f}× avg volume — institutional buying"
                )
                weighted_score += 0.1

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

    # Micro-cap with critical illiquidity — dollar volume < $100K makes it
    # impossible to execute meaningful positions without moving the market
    if tv_data:
        dollar_vol = tv_data.get("dollar_volume") or tv_data.get("DollarVolume")
        if dollar_vol is not None and dollar_vol < 100_000:
            dealbreakers.append(
                f"Dollar volume ${dollar_vol:,.0f} — critically illiquid. "
                "Cannot execute meaningful positions without moving price 10%+."
            )
            weighted_score -= 0.5

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
            # ── Trajectory weighting: is this a high-growth turnaround? ──
            # Pre-profit growth companies (e.g., oncology, biotech, SaaS) have
            # negative margins + negative FCF + extreme P/E BY DEFINITION during
            # their growth phase. Don't apply the full dealbreaker penalty.
            rev_growth = fundamental.revenue_growth_yoy
            is_high_growth_turnaround = (
                rev_growth is not None
                and rev_growth > 15  # strong revenue growth
                and fundamental.market_cap is not None
                and fundamental.market_cap > 50_000_000  # not a micro-cap
            )
            if is_high_growth_turnaround:
                # Reduced penalty: trajectory matters, not just point-in-time
                dealbreakers.append(
                    f"Negative margins and cash flow, but high revenue growth "
                    f"({rev_growth:.0f}% YoY) suggests pre-profit growth stage "
                    f"rather than terminal decline — monitor trajectory"
                )
                weighted_score -= 0.25  # Reduced from 0.5
                # Don't floor at -0.5 — allow recovery if other modules are bullish
            else:
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

    # Extreme P/E — valuation dislocation regardless of other factors
    if fundamental and fundamental.pe_ratio is not None and fundamental.pe_ratio > 100:
        dealbreakers.append(f"P/E {fundamental.pe_ratio:.0f} — extreme valuation dislocation, multiple compression risk")
        weighted_score -= 0.4

    # Extreme volatility
    if risk and risk.volatility_regime == "extreme":
        dealbreakers.append("Extreme volatility regime — widen stops significantly or skip")
        weighted_score -= 0.2

    # ── Catalyst Bias Adjustment ──
    # Integrate catalyst bias from orchestrator (earnings proximity, analyst revisions, etc.)
    if tv_data and "catalyst_bias" in tv_data:
        catalyst_bias = tv_data["catalyst_bias"]
        if isinstance(catalyst_bias, dict):
            bias = catalyst_bias.get("bias", "neutral")
            score = catalyst_bias.get("score", 0)
            notes = catalyst_bias.get("notes", [])
            
            # Apply catalyst score to weighted_score
            weighted_score += score * 0.05  # Scale factor
            
            # Add notes to dealbreakers if negative
            if score <= -3:
                dealbreakers.append(f"Catalyst bias negative: {', '.join(notes[:2])}")
            elif score >= 3:
                # Positive catalyst - reduce penalty or add to thesis
                pass
            
            # Add catalyst notes to all_findings for transparency
            for note in notes:
                all_findings.append(f"📰 Catalyst: {note}")

    # ── 3a. Development-Stage Company Override ──
    # Companies with no revenue, negative earnings, or pre-profit clinical
    # stage should not be evaluated using standard equity metrics.
    # Their value is driven by binary outcomes (pipeline, trials, resource discovery).
    if fundamental and fundamental.lifecycle_stage != "operating" and fundamental.instrument_type not in ("spac", "etf", "cef", "etn", "mutual_fund", "preferred"):
        stage_labels = {
            "clinical_stage": "Clinical-stage biotechnology",
            "pre_revenue": "Pre-revenue technology",
            "development": "Development-stage company",
            "distressed": "Distressed company",
            "cash_shell": "Cash shell",
        }
        stage_label = stage_labels.get(fundamental.lifecycle_stage, "Development-stage company")

        # Different conviction/action based on stage severity
        if fundamental.lifecycle_stage in ("clinical_stage", "pre_revenue"):
            # Development-stage with potential upside but binary risk
            return AnalysisVerdict(
                action="WATCH",
                conviction=3,
                entry_zone_low=None,
                entry_zone_high=None,
                stop_loss=None,
                targets=[],
                risk_reward=None,
                position_size_pct=0,
                key_red_flags=[
                    f"{stage_label} — no operating revenue, no meaningful P/E or margins. "
                    "Value driven by binary pipeline/milestone outcomes. Standard equity "
                    "analysis (P/E, margins, FCF) does not apply. Evaluate cash runway, "
                    "milestone catalysts, and probability-adjusted potential instead."
                ],
                buy_triggers=[
                    "Only position after positive catalyst (trial data, product launch, "
                    "partnership) — do not buy purely on valuation."
                ],
                sell_triggers=[
                    "Sell on trial failure, funding gap, or missed milestone timeline.",
                    "Monitor cash runway quarterly — if < 12 months, de-risk position.",
                ],
                thesis=f"{stage_label} — no operating revenue. Standard fundamental "
                       "metrics (P/E, margins, FCF yield) are not applicable. Value "
                       "derived from pipeline, milestones, and cash runway. This is "
                       f"a {fundamental.lifecycle_stage.replace('_', ' ')} investment "
                       "with binary outcome risk. Position with strict size limits.",
            )
        else:
            # Generic development / distressed — lower conviction
            return AnalysisVerdict(
                action="WATCH",
                conviction=2,
                entry_zone_low=None,
                entry_zone_high=None,
                stop_loss=None,
                targets=[],
                risk_reward=None,
                position_size_pct=0,
                key_red_flags=[
                    f"{stage_label} — no operating revenue or earnings. "
                    "Standard equity analysis does not apply. Binary outcome risk. "
                    "Evaluate based on cash runway and development milestones."
                ],
                buy_triggers=[],
                sell_triggers=[
                    "Sell on missed milestones or funding gaps.",
                    "Monitor cash runway — less than 12 months requires capital raise risk.",
                ],
                thesis=f"{stage_label} with no operating revenue. Standard valuation "
                       "metrics are not meaningful. Position based on milestone thesis "
                       "with strict size limits and catalyst-based exit plan.",
            )

    # ── 3b. Extreme Short Interest / Squeeze Override ──
    # When short interest exceeds 30% of float, normal fundamental and technical
    # analysis breaks down. Squeeze dynamics (gamma, covering, FOMO) dominate
    # price action. The stock's behavior becomes detached from its fundamentals.
    # Skip for fund instruments — short interest in CEFs/ETFs reflects arbitrage
    # or hedging activity, not directional bearish sentiment.
    fund_types = {"etf", "cef", "etn", "mutual_fund", "preferred"}
    is_fund_inst = fundamental and fundamental.instrument_type in fund_types
    if sentiment and sentiment.short_interest_pct is not None and sentiment.short_interest_pct > 30 and not is_fund_inst:
        squeeze_thesis = (
            f"⚠️ Short interest is {sentiment.short_interest_pct:.1f}% of float — "
            "extremely elevated. Normal fundamental and technical analysis is "
            "unreliable under squeeze dynamics. Price action may be driven by "
            "short covering, gamma pressure, and retail/social sentiment rather "
            "than company fundamentals. Treat as a speculative squeeze event, "
            "not an investment thesis."
        )
        return AnalysisVerdict(
            action="WATCH",
            conviction=3,
            entry_zone_low=None,
            entry_zone_high=None,
            stop_loss=None,
            targets=[],
            risk_reward=None,
            position_size_pct=0,
            key_red_flags=[squeeze_thesis],
            buy_triggers=[
                "Only enter if short interest is still climbing AND price is breaking "
                "above key resistance with volume confirmation.",
                "Use tight stops — squeeze can reverse violently when covering completes.",
            ],
            sell_triggers=[
                "Exit immediately if short interest drops sharply (covering complete).",
                "Sell if daily volume drops below 50% of average — momentum fading.",
                f"Set stop-loss at recent swing low — if SI drops below 20%, reassess.",
            ],
            thesis=squeeze_thesis,
        )

    # ── 3c. M&A / Acquisition Override ──
    # If the stock is in a pending acquisition, switch to merger arb analysis.
    # Detected by orchestrator via price-pinning, low-vol, and near-zero-beta heuristic.
    td = tv_data or {}
    ma_offer = td.get("ma_offer_price")
    if ma_offer is not None:
        ma_confidence = td.get("ma_confidence", "potential")
        ma_spread = td.get("ma_spread_pct", 0)
        ma_spread_str = f"{ma_spread:+.2f}%" if ma_spread else "N/A"

        if ma_confidence == "confirmed":
            # Confirmed deal via signed definitive agreement — merger arb mode
            deal_thesis = (
                f"Signed definitive acquisition agreement at ${ma_offer:.2f}/share. "
                f"Upside remaining: {ma_spread_str}. "
                "This is a merger arbitrage position, not a directional equity trade. "
                "Entry/stop/target levels from standard analysis do not apply — "
                "the stock is capped at the offer price. Evaluate deal risk "
                "(regulatory approval, shareholder vote, financing) to size position."
            )
            return AnalysisVerdict(
                action="BUY",
                conviction=8,
                entry_zone_low=None,
                entry_zone_high=None,
                stop_loss=None,
                targets=[round(float(ma_offer), 2)],
                risk_reward=None,
                position_size_pct=0,
                key_red_flags=[deal_thesis],
                buy_triggers=[
                    "Deal spread provides near-risk-free return to offer price.",
                    "Hold through close for deal consideration.",
                ],
                sell_triggers=[
                    "Sell immediately if deal faces regulatory/approval issues.",
                    f"If stock exceeds ${ma_offer:.2f}, the deal spread may widen — reassess.",
                ],
                thesis=deal_thesis,
            )
        else:
            # Potential M&A detected via heuristics (price-pinning + low-vol + low-beta)
            deal_thesis = (
                f"⚠️ Potential acquisition target at ${ma_offer:.2f}/share. "
                f"Upside remaining: {ma_spread_str}. "
                "This is NOT a confirmed deal — detected via heuristic signals "
                "(price pinned near analyst target, unusually low volatility, "
                "near-zero beta). Treat as speculation. Standard analysis may "
                "not apply if a deal is imminent."
            )
            return AnalysisVerdict(
                action="WATCH",
                conviction=5,
                entry_zone_low=None,
                entry_zone_high=None,
                stop_loss=None,
                targets=[round(float(ma_offer), 2)],
                risk_reward=None,
                position_size_pct=0,
                key_red_flags=[deal_thesis],
                buy_triggers=[
                    "Monitor for news of definitive agreement. Only position after signed deal.",
                ],
                sell_triggers=[
                    "Sell if volatility returns (false signal — no deal).",
                    f"Take profits if stock approaches ${ma_offer:.2f} before deal confirmation.",
                ],
                thesis=deal_thesis,
            )

    # ── 3d. Treasury Asset Company Override ──
    # Bitcoin treasury companies (e.g., MPLT, MSTR) derive value from their
    # primary reserve asset, not from operating earnings. Standard fundamental
    # analysis (P/E, margins, growth rates) is misleading for these instruments.
    is_treasury_asset = fundamental is not None and fundamental.asset_category == "treasury_asset"
    if is_treasury_asset:
        return AnalysisVerdict(
            action="WATCH",
            conviction=3,
            entry_zone_low=None,
            entry_zone_high=None,
            stop_loss=None,
            targets=[],
            risk_reward=None,
            position_size_pct=0,
            key_red_flags=[
                "Bitcoin/treasury asset company — value derived from primary reserve "
                "asset (BTC), not operating earnings. Standard P/E/margin analysis "
                "does not apply. Evaluate based on BTC holdings per share and "
                "premium/discount to NAV."
            ],
            buy_triggers=[],
            sell_triggers=[
                "Monitor BTC holdings per share dilution (equity issuance for BTC buys).",
                "Track premium/discount to NAV — wide premium increases downside risk.",
            ],
            thesis="Bitcoin treasury company — value tracks primary reserve asset (BTC) "
                   "rather than operating earnings. Standard equity metrics (P/E, margins, "
                   "growth) are not applicable. Position based on BTC thesis, not company "
                   "fundamentals. Use position sizing limits from risk module.",
        )

    # ── 3e. ETF / CEF / ETN / Preferred Override ──
    # Exchange-traded funds, closed-end funds, exchange-traded notes, and
    # preferred stocks are not individual equities. Standard fundamental analysis
    # (P/E, margins, growth rates) doesn't apply.
    fund_inst_type: str | None = fundamental.instrument_type if fundamental else None
    is_fund_instrument = fund_inst_type in ("etf", "cef", "etn", "mutual_fund", "preferred")
    if is_fund_instrument:
        fund_type_label = {
            "etf": "ETF", "cef": "Closed-End Fund",
            "etn": "ETN", "mutual_fund": "Mutual Fund",
        }.get(fund_inst_type or "", "Fund")
        thesis_parts = [
            f"{fund_type_label} — not an individual equity.",
        ]
        if fund_inst_type == "etn":
            thesis_parts.append(
                "ETNs carry issuer credit risk in addition to underlying index exposure. "
                "Standard equity metrics (P/E, margins, growth) do not apply."
            )
        elif fund_inst_type == "cef":
            thesis_parts.append(
                "CEFs can trade at premiums/discounts to NAV. Distribution yield and "
                "discount/premium history are the relevant metrics, not P/E or earnings growth."
            )
        else:
            thesis_parts.append(
                "Fund performance tracks its underlying holdings. Evaluate the fund's "
                "sector exposure, expense ratio, and tracking error — not individual "
                "equity metrics."
            )
        thesis_parts.append(
            "This instrument is not suitable for the equity-focused ticker analysis and "
            "should be evaluated using fund-specific tools instead."
        )
        return AnalysisVerdict(
            action="WATCH",
            conviction=2,
            entry_zone_low=None,
            entry_zone_high=None,
            stop_loss=None,
            targets=[],
            risk_reward=None,
            position_size_pct=0,
            key_red_flags=[
                f"{fund_type_label} detected — this is not a single equity. "
                "Standard stock analysis metrics (P/E, margins, growth) do not apply. "
                "Remove from equity screeners for accurate results."
            ],
            buy_triggers=[],
            sell_triggers=[],
            thesis=" ".join(thesis_parts),
        )

    # ── 3f. SPAC override ──
    # Pre-deal SPACs have no operating business — standard fundamental analysis
    # doesn't apply. Override with SPAC-specific framework.
    is_spac = fundamental is not None and fundamental.instrument_type == "spac"
    if is_spac:
        return AnalysisVerdict(
            action="WATCH",
            conviction=3,
            entry_zone_low=None,
            entry_zone_high=None,
            stop_loss=None,
            targets=[],
            risk_reward=None,
            position_size_pct=0,
            key_red_flags=[
                "Pre-deal SPAC — no operating business. Tracks trust value (~$10). "
                "Binary outcome: either acquires target (volatile post-deal) or liquidates."
            ],
            buy_triggers=[],
            sell_triggers=[],
            thesis="Pre-deal SPAC (blank-check company). No operating business, no revenue, "
                   "no earnings to analyze. Value derived from trust account (~$10/share). "
                   "WATCH as speculative event-driven instrument: evaluate any announced "
                   "target independently. Position size strictly limited — see risk module.",
        )

    # ── 4. Map score to action ──
    base_action: str
    conviction: int
    dealbreaker_active = len(dealbreakers) > 0

    # Major dealbreakers block positive actions entirely
    major_dealbreakers = [
        d for d in dealbreakers 
        if any(kw in d.lower() for kw in ["earnings miss", "micro-cap", "illiquid", "cash burn", "triple-negative", "pump-and-dump", "size near zero", "penny stock", "manipulation"])
    ]
    has_major_dealbreaker = len(major_dealbreakers) > 0
    # Minor dealbreakers (extreme RSI, extreme P/E, extreme vol) only penalize score
    # but don't block BUY/ACCUMULATE

    if weighted_score >= 0.75 and not has_major_dealbreaker:
        base_action = "STRONG BUY"
        conviction = min(10, 8 + int((weighted_score - 0.75) * 20))
    elif weighted_score >= 0.55 and not has_major_dealbreaker:
        base_action = "BUY"
        conviction = min(10, 6 + int((weighted_score - 0.55) * 15))
    elif weighted_score >= 0.40 and not has_major_dealbreaker:
        base_action = "ACCUMULATE"
        conviction = 4 + int((weighted_score - 0.40) * 10)
    elif weighted_score >= 0.20 and not has_major_dealbreaker:
        base_action = "ACCUMULATE"
        conviction = 2 + int((weighted_score - 0.20) * 12)
    elif weighted_score >= 0.10:
        base_action = "WATCH"
        conviction = 2 + int((weighted_score - 0.10) * 10) if weighted_score > 0 else 2
        conviction = min(conviction, 4)
    elif weighted_score >= 0.0:
        # Scores 0-10%: very weak positive — still WATCH but minimum conviction
        # (was previously lumped with > -0.10 giving c:2)
        base_action = "WATCH"
        conviction = 1
    elif weighted_score > -0.15:
        # Scores -15% to 0%: mildly negative → HOLD
        base_action = "HOLD"
        conviction = 2
    elif weighted_score > -0.4:
        # Scores -40% to -15%: moderately negative → REDUCE
        base_action = "REDUCE"
        conviction = 5 + int(abs(weighted_score) * 10)
        conviction = min(conviction, 8)
    else:
        # Scores below -40%: clearly bearish → AVOID
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

        # Entry zone: dynamic adjustment based on MA proximity and price position.
        # If price is near MA support, the zone includes current price.
        # If price is extended above MAs, suggest pullback entry only.
        # This prevents stale "buy at current" entries when the stock has already run.
        if action in ("BUY", "ACCUMULATE", "WATCH"):
            sma20 = tv_data.get("SMA20") if tv_data else None
            sma50 = tv_data.get("SMA50") if tv_data else None
            nearest_ma = None
            for ma in [sma20, sma50]:
                if ma and ma > 0:
                    if nearest_ma is None or abs(close - ma) < abs(close - nearest_ma):
                        nearest_ma = ma
            
            price_vs_ma_pct = ((close / nearest_ma) - 1) * 100 if nearest_ma else 0
            
            # Check for RSI overbought
            is_overbought = technical and technical.rsi_regime in ("overbought", "overbought_warning")
            
            if is_overbought:
                # Overbought — always suggest a pullback
                drawdown_target = stop_pct * 1.5
                entry_low = round(close * (1 - drawdown_target), 2)
                entry_high = round(close, 2)
            elif nearest_ma and price_vs_ma_pct > 5:
                # Extended above nearest MA — wait for pullback to MA
                pullback_target = max(stop_pct * 1.5, price_vs_ma_pct * 0.5 / 100)
                entry_low = round(close * (1 - pullback_target), 2)
                entry_high = round(close * (1 - price_vs_ma_pct * 0.3 / 100), 2)
                if entry_low > round(nearest_ma * 0.98, 2):
                    entry_low = round(nearest_ma * 0.98, 2)
            elif nearest_ma and abs(price_vs_ma_pct) < 3:
                # Near MA support — current price is valid entry
                # Zone width: 0.5x ATR (min 1.5% price range for tight-range stocks)
                entry_width = max(technical.atr_pct / 100 * 0.5 if technical and technical.atr_pct else 0.015, 0.015)
                entry_low = round(close * (1 - entry_width), 2)
                entry_high = round(close * (1 + entry_width * 0.5), 2)
            else:
                # Default zone — ATR-adaptive width (min 1.5% for low-vol stocks)
                entry_width = max(technical.atr_pct / 100 * 0.5 if technical and technical.atr_pct else 0.015, 0.015)
                entry_low = round(close * (1 - entry_width), 2)
                entry_high = round(close * (1 + entry_width * 0.5), 2)

        stop_loss = round(close * (1 - max(stop_pct, 0.02)), 2)

        # Dynamic R:R based on setup quality
        rr = _calculate_dynamic_rr(technical, risk, fundamental, action)

        # Targets: 1st target at 1x R, 2nd at dynamic R:R
        if stop_loss > 0:
            risk_per_share = (entry_high or close) - stop_loss if (entry_high or close) > stop_loss else stop_loss * 0.1
            t1 = round((entry_high or close) + risk_per_share * 1.0, 2)
            t2 = round((entry_high or close) + risk_per_share * rr, 2)
            targets = [t1, t2]

    # ── 7. Verdict Consistency Cross-check ──
    # AVOID/REDUCE should never have trading levels — contradictory signals.
    if action in ("AVOID", "REDUCE"):
        entry_low = None
        entry_high = None
        stop_loss = None
        targets = []
        rr = None
        position_size = 0.0
        buy_triggers = []
    else:
        position_size = risk.suggested_position_size_pct if risk else 0

    # Conviction-based position size caps: lower conviction = smaller max position
    # This prevents taking large positions on low-conviction setups
    # Caps are generous at reasonable conviction levels; only very low conviction gets restrictive
    conviction_caps = {
        1: 10.0, 2: 10.0, 3: 10.0, 4: 12.0, 5: 15.0,
        6: 18.0, 7: 20.0, 8: 22.0, 9: 25.0, 10: 25.0
    }
    if conviction in conviction_caps:
        cap = conviction_caps[conviction]
        if position_size > cap:
            all_findings.append(f"⚠️ Position size {position_size:.1f}% capped to {cap}% (conviction {conviction}/10)")
            position_size = cap

    # Meme/retail stock position cap: elevated short interest + high beta
    # + bearish technicals = dangerous combination for retail-driven volatility.
    # Detected stocks get capped at 5% regardless of what the risk model suggests.
    if position_size > 5.0 and action not in ("AVOID", "REDUCE"):
        is_meme_candidate = (
            sentiment is not None
            and sentiment.short_interest_pct is not None and sentiment.short_interest_pct > 10
            and sentiment.beta is not None and sentiment.beta > 1.5
        )
        has_bearish_technicals = (
            technical is not None
            and technical.ma_alignment == "bearish"
        )
        has_negative_margins = (
            fundamental is not None
            and fundamental.profit_margin is not None and fundamental.profit_margin < -5
        )
        if is_meme_candidate and (has_bearish_technicals or has_negative_margins):
            position_size = min(position_size, 5.0)

    # BUY/ACCUMULATE should have minimum conviction of 3
    if action in ("BUY", "ACCUMULATE") and conviction < 3:
        conviction = 3

    # ── Conviction Calibration ──
    # AVOID/REDUCE: cap at 8 — no automated system should express c:9 or c:10
    # conviction on a bearish call. Reserve 9-10 for near-certain BUY setups.
    if action in ("AVOID", "REDUCE"):
        conviction = min(conviction, 8)

    # BUY/ACCUMULATE: cap at 8 for speculative/pre-profit small caps
    if action in ("BUY", "ACCUMULATE") and fundamental:
        mcap = fundamental.market_cap or 0
        is_pre_profit = fundamental.pe_ratio is None or fundamental.pe_ratio < 0
        if mcap < 1_000_000_000 and is_pre_profit:
            conviction = min(conviction, 8)

    # ── 8. Generate trade plan ──
    trade_plan = _generate_trade_plan(
        action=action,
        conviction=conviction,
        technical=technical,
        fundamental=fundamental,
        risk=risk,
        price=price,
        entry_low=entry_low,
        entry_high=entry_high,
        stop_loss=stop_loss,
        targets=targets,
        rr=rr,
        position_size=position_size,
        technical_weekly=technical_weekly,
    )

    # ── 9. Generate thesis ──
    thesis = _generate_thesis(action, weighted_score, modules, dealbreakers, regime)

    return AnalysisVerdict(
        action=action,
        conviction=conviction,
        entry_zone_low=entry_low,
        entry_zone_high=entry_high,
        stop_loss=stop_loss,
        targets=targets,
        risk_reward=rr,
        position_size_pct=position_size,
        trade_plan=trade_plan,
        key_red_flags=dealbreakers + [f for f in all_red_flags if f not in dealbreakers][:5],
        buy_triggers=buy_triggers[:3],
        sell_triggers=sell_triggers[:3],
        thesis=thesis,
    )


def _generate_trade_plan(
    action: str,
    conviction: int,
    technical: TechnicalAnalysis | None,
    fundamental: FundamentalAnalysis | None,
    risk: RiskAssessment | None,
    price: float | None,
    entry_low: float | None,
    entry_high: float | None,
    stop_loss: float | None,
    targets: list[float],
    rr: float | None,
    position_size: float,
    technical_weekly: TechnicalAnalysis | None = None,
) -> TradePlan | None:
    """Generate a dynamic trade management plan based on setup quality and market structure."""
    if action in ("AVOID", "REDUCE") or not price:
        return None
    
    plan = TradePlan()
    
    # Determine ATR for trailing
    atr_mult = 2.0
    if risk and risk.suggested_stop_pct > 0:
        atr_mult = 2.0  # Default 2x ATR
    
    # Scale-in plan: split entry into 2-3 tranches
    if entry_low and entry_high:
        plan.scale_in = [
            {"price": entry_high, "size_pct": round(position_size * 0.5, 1), "reason": "Initial entry at upper zone"},
            {"price": round(entry_low + (entry_high - entry_low) * 0.3, 2), "size_pct": round(position_size * 0.3, 1), "reason": "Add on pullback to lower zone"},
            {"price": entry_low, "size_pct": round(position_size * 0.2, 1), "reason": "Final add at lower zone"},
        ]
    
    # Scale-out plan based on R:R
    # All levels must be strictly >= 1.0R so breakeven activates before any partial exit.
    if rr and rr > 0:
        mid_r = max(round(1.0 + (rr - 1.0) * 0.5, 1), 1.1)  # Midpoint between 1R and full R (min 1.1)
        plan.scale_out = [
            {"r_multiple": 1.0, "size_pct": round(position_size * 0.3, 1), "reason": "Take 30% at 1R — secure base and move stop to breakeven"},
            {"r_multiple": mid_r, "size_pct": round(position_size * 0.3, 1), "reason": f"Take 30% at {mid_r}R — intermediate target"},
            {"r_multiple": rr, "size_pct": round(position_size * 0.4, 1), "reason": f"Final 40% at full target ({rr}R)"},
        ]
    
    # Trailing stop configuration
    if technical and technical.ma_alignment == "bullish":
        plan.trail_type = "structure"
        plan.trail_value = 1.0  # Trail below key MAs
        plan.trail_activation_r = 1.0
        plan.notes.append("Trail below rising SMA20/SMA50 structure")
    elif risk and risk.volatility_regime == "high":
        plan.trail_type = "atr"
        plan.trail_value = 2.5
        plan.trail_activation_r = 1.5
        plan.notes.append("Wide ATR trail for high volatility")
    else:
        plan.trail_type = "atr"
        plan.trail_value = 2.0
        plan.trail_activation_r = 1.0
    
    # Breakeven rule
    plan.move_to_breakeven_at_r = 1.0
    plan.notes.append("Move stop to breakeven at 1R")
    
    # Time-based exit
    # Every trade needs a max hold — prevents indefinite drift for once-a-day traders
    if technical and technical.ma_alignment == "bearish":
        plan.max_hold_days = 20
        plan.notes.append("Counter-trend: max 20-day hold")
    elif fundamental and fundamental.lifecycle_stage in ("development", "clinical_stage"):
        plan.max_hold_days = 60
        plan.notes.append("Development stage: catalyst-driven, max 60-day hold")
    elif action in ("BUY", "ACCUMULATE", "STRONG BUY"):
        plan.max_hold_days = 30
        plan.notes.append("Swing trade: max 30-day hold — re-evaluate thesis at expiry")
    
    # Risk caps
    plan.max_position_pct = min(10.0, position_size * 1.5)
    plan.daily_loss_limit_pct = 2.0
    
    # Conviction-based notes
    if conviction >= 8:
        plan.notes.append("High conviction — full position justified")
    elif conviction >= 5:
        plan.notes.append("Moderate conviction — standard position")
    else:
        plan.notes.append("Low conviction — reduced position")
    
    # Structure-based trailing
    if technical and technical.key_support:
        plan.trail_type = "structure"
        plan.trail_value = 0.0  # Will use key support levels
        plan.notes.append(f"Trail below key support at {technical.key_support[0]:.2f}")
    
    return plan


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
