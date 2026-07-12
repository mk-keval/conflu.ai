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

    # Extreme volatility
    if risk and risk.volatility_regime == "extreme":
        dealbreakers.append("Extreme volatility regime — widen stops significantly or skip")
        weighted_score -= 0.2

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

    # ── 8. Generate thesis ──
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
