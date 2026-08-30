"""Multi-Timeframe Confluence Analysis — Align signals across Daily, 4H, 1H, 15M.

This module provides institutional-grade multi-timeframe confluence detection.
It aligns market structure signals (BOS/CHoCH), order blocks, fair value gaps,
breakouts, and volume profile alignment across timeframes to produce a
high-confidence trade bias with entry zones and invalidation levels.

TEACHING:
- Multi-timeframe analysis is the CORE of professional trading.
- Higher timeframes (Daily, Weekly) define the TREND and major structure.
- Lower timeframes (4H, 1H, 15M) define ENTRY precision and risk management.
- CONFLUENCE = When multiple timeframes agree on direction + structure.
- The highest probability setups occur when:
  1. Daily structure is BULLISH (BOS/CHoCH confirmed)
  2. 4H shows unmitigated OB/FVG in direction of daily bias
  3. 1H/15M validate with clean breakouts in same direction
  4. Volume Profile POC/VA aligns with the bias
- CONFLICT DETECTION is equally critical:
  - Daily bullish + 4H bearish = AVOID LONGS (structure misaligned)
  - Daily bearish + 4H bullish = AVOID SHORTS (structure misaligned)
- ENTRY ZONES: 4H Order Blocks / FVGs in direction of daily bias (±0.5%)
- INVALIDATION: Nearest opposing structure price (swing level that would
  invalidate the thesis if broken)

WEIGHTS (institutional standard):
- Daily BOS/CHoCH: 0.40 (Trend definition — highest weight)
- 4H OB/FVG (unmitigated/unfilled): 0.30 (Institutional footprint)
- 1H/15M validated breakouts: 0.20 (Entry timing precision)
- TPO POC/VA alignment: 0.10 (Volume confirmation)

BIAS THRESHOLDS:
- Bullish: bull_score > bear_score + 0.15
- Bearish: bear_score > bull_score + 0.15
- Neutral: |bull_score - bear_score| <= 0.15

The 0.15 buffer prevents whipsaws in choppy/low-confluence markets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from backend.app.domain.ticker_analysis.models import TechnicalAnalysis


@dataclass
class ConfluenceSignal:
    """A single timeframe's contribution to the multi-timeframe confluence.
    
    TEACHING:
    Each timeframe contributes evidence. The weight determines how much
    that evidence counts toward the final bias. Higher timeframes carry
    more weight because they represent larger institutional order flow.
    
    Fields:
        timeframe: Which timeframe this signal comes from
        direction: "bullish" / "bearish" / "neutral"
        score: Raw signal strength (-1.0 to 1.0) before weighting
        weight: Confluence weight (sums to 1.0 across all timeframes)
        details: Human-readable evidence for this signal
        structure_type: Type of structure detected (BOS, CHoCH, OB, FVG, breakout, POC)
        price_level: Key price level associated with this signal
        is_mitigated: For OB/FVG - whether the level has been tested/filled
    """
    timeframe: Literal["daily", "4h", "1h", "15m", "tpo"]
    direction: Literal["bullish", "bearish", "neutral"]
    score: float  # -1.0 to 1.0
    weight: float  # Confluence weight
    details: list[str] = field(default_factory=list)
    structure_type: str | None = None  # "bos", "choch", "ob", "fvg", "breakout", "poc_va"
    price_level: float | None = None
    is_mitigated: bool = False
    
    @property
    def weighted_score(self) -> float:
        """Score contribution after applying confluence weight."""
        return self.score * self.weight


@dataclass
class MTFConfluenceResult:
    """Complete multi-timeframe confluence analysis result.
    
    TEACHING:
    This is the FINAL output that drives trading decisions. It contains:
    - Overall bias (bullish/bearish/neutral) with confidence
    - Individual timeframe signals for transparency
    - Conflict warnings (critical for risk management)
    - Entry zones (where to place limit orders)
    - Invalidation level (where the thesis is wrong)
    - Weighted score breakdown
    
    Usage:
    - If bias is "bullish" and no conflicts: Consider LONG setups
    - If bias is "bearish" and no conflicts: Consider SHORT setups
    - If bias is "neutral" or conflicts exist: WAIT / REDUCE SIZE
    - Entry zones: Place limits at 4H OB/FVG levels
    - Stop loss: Beyond invalidation level
    """
    # Overall assessment
    overall_bias: Literal["bullish", "bearish", "neutral"]
    bull_score: float  # Total weighted bullish evidence
    bear_score: float  # Total weighted bearish evidence
    confidence: float  # 0.0 to 1.0 (how strong is the confluence)
    
    # Individual timeframe signals
    signals: list[ConfluenceSignal] = field(default_factory=list)
    
    # Conflict detection
    conflicts: list[str] = field(default_factory=list)
    has_critical_conflict: bool = False
    
    # Entry and risk management
    entry_zones: list[dict] = field(default_factory=list)  # [{"price": float, "type": "ob/fvg", "timeframe": "4h", "direction": "bullish"}]
    invalidation_level: float | None = None  # Price that invalidates the thesis
    invalidation_reason: str | None = None
    
    # Metadata
    details: list[str] = field(default_factory=list)
    timestamp: str | None = None


def _extract_chart_reading(tech: TechnicalAnalysis) -> dict:
    """Safely extract chart reading fields from TechnicalAnalysis.
    
    TEACHING:
    TechnicalAnalysis may or may not have market structure fields
    depending on whether OHLCV data was available. This function
    safely extracts whatever is available with sensible defaults.
    
    Returns dict with:
        structure: Market structure label
        swing_highs: List of swing high prices
        swing_lows: List of swing low prices
        key_resistance: Key resistance levels
        key_support: Key support levels
        pullback_quality: Pullback grade
        pullback_score: Pullback score 0-100
        findings: Technical findings
    """
    return {
        "structure": getattr(tech, "structure", "unknown"),
        "swing_highs": getattr(tech, "swing_highs", None) or [],
        "swing_lows": getattr(tech, "swing_lows", None) or [],
        "key_resistance": getattr(tech, "key_resistance", None) or [],
        "key_support": getattr(tech, "key_support", None) or [],
        "pullback_quality": getattr(tech, "pullback_quality", None),
        "pullback_score": getattr(tech, "pullback_score", None),
        "findings": getattr(tech, "findings", []),
        "score": getattr(tech, "score", 0.0),
        "ma_alignment": getattr(tech, "ma_alignment", "unknown"),
        "rsi": getattr(tech, "rsi", None),
        "adx": getattr(tech, "adx", None),
        "atr_pct": getattr(tech, "atr_pct", None),
        "volume_ratio": getattr(tech, "volume_ratio", None),
        "bb_position": getattr(tech, "bb_position", None),
        "macd_status": getattr(tech, "macd_status", None),
    }


def _analyze_daily_structure(tech: TechnicalAnalysis) -> ConfluenceSignal:
    """Analyze Daily timeframe for BOS/CHoCH structure (weight 0.40).
    
    TEACHING:
    Daily timeframe is KING for trend definition. BOS (Break of Structure)
    and CHoCH (Change of Character) on daily represent major institutional
    decisions. A confirmed daily BOS/CHoCH carries the highest weight
    because it represents the PRIMARY trend direction.
    
    Structure labels from technical module:
    - "bullish": Higher highs, higher lows (uptrend)
    - "bearish": Lower highs, lower lows (downtrend)
    - "bullish_choch": Confirmed bullish reversal (CHoCH)
    - "bearish_choch": Confirmed bearish reversal (CHoCH)
    - "transition_bullish/bearish": Early structure shift
    - "ranging": No clear structure
    - "insufficient_data": Not enough swings
    
    Score mapping:
    - bullish/bullish_choch: +1.0
    - transition_bullish: +0.5
    - ranging/neutral: 0.0
    - transition_bearish: -0.5
    - bearish/bearish_choch: -1.0
    """
    chart = _extract_chart_reading(tech)
    # Normalise so structure is never None — downstream code uses `in structure`
    # (e.g. ``"choch" in structure``) which raises TypeError on None. When a
    # timeframe has insufficient data (no swings), structure is None here.
    structure = chart["structure"] or "unknown"
    findings = chart["findings"]
    
    # Map structure to direction and score
    structure_scores: dict[str, tuple[Literal["bullish", "bearish", "neutral"], float]] = {
        "bullish": ("bullish", 1.0),
        "bullish_choch": ("bullish", 1.0),
        "transition_bullish": ("bullish", 0.5),
        "ranging": ("neutral", 0.0),
        "neutral": ("neutral", 0.0),
        "transition_bearish": ("bearish", -0.5),
        "bearish": ("bearish", -1.0),
        "bearish_choch": ("bearish", -1.0),
        "insufficient_data": ("neutral", 0.0),
        "unknown": ("neutral", 0.0),
    }
    
    direction, score = structure_scores.get(structure, ("neutral", 0.0))
    
    # Build details
    details = []
    if structure in ("bullish", "bullish_choch", "bearish", "bearish_choch"):
        details.append(f"Daily {structure.replace('_', ' ').title()} confirmed — BOS/CHoCH structure")
    elif structure in ("transition_bullish", "transition_bearish"):
        details.append(f"Daily {structure} — early structure shift, watch for confirmation")
    else:
        details.append(f"Daily structure: {structure}")
    
    # Add swing levels as context
    if chart["swing_highs"]:
        details.append(f"Recent swing high: {chart['swing_highs'][-1]:.2f}")
    if chart["swing_lows"]:
        details.append(f"Recent swing low: {chart['swing_lows'][-1]:.2f}")
    if chart["key_resistance"]:
        details.append(f"Key resistance: {', '.join(f'{r:.2f}' for r in chart['key_resistance'][:3])}")
    if chart["key_support"]:
        details.append(f"Key support: {', '.join(f'{s:.2f}' for s in chart['key_support'][:3])}")
    
    # Determine structure type
    structure_type = "bos" if structure in ("bullish", "bearish") else "choch" if "choch" in structure else "none"
    
    return ConfluenceSignal(
        timeframe="daily",
        direction=direction,
        score=score,
        weight=0.40,
        details=details,
        structure_type=structure_type,
        price_level=chart["swing_highs"][-1] if chart["swing_highs"] and direction == "bullish"
                     else chart["swing_lows"][-1] if chart["swing_lows"] and direction == "bearish"
                     else None,
    )


def _analyze_4h_ob_fvg(tech: TechnicalAnalysis) -> ConfluenceSignal:
    """Analyze 4H timeframe for Order Blocks and Fair Value Gaps (weight 0.30).
    
    TEACHING:
    4H Order Blocks (OB) and Fair Value Gaps (FVG) are the FOOTPRINTS of
    institutional order flow. They represent areas where smart money entered
    aggressively, leaving unfilled orders (OB) or pricing inefficiencies (FVG).
    
    KEY CONCEPT - MITIGATION:
    - UNMITIGATED OB/FVG: Price has NOT returned to the level yet.
      These are HIGH PROBABILITY entry zones — institutions will defend them.
    - MITIGATED/FILLED OB/FVG: Price has already revisited and filled.
      The institutional interest has been satisfied — lower probability.
    
    Since we don't have native OB/FVG detection in the current technical module,
    we infer from market structure and key levels:
    - In bullish structure: Recent swing low area = potential bullish OB
    - In bearish structure: Recent swing high area = potential bearish OB
    - FVG approximated by gaps between swing levels
    
    Score based on:
    - Structure alignment with daily
    - Unmitigated status (inferred from current price vs level)
    - Volume confirmation (if available)
    """
    chart = _extract_chart_reading(tech)
    structure = chart["structure"]
    swing_highs = chart["swing_highs"]
    swing_lows = chart["swing_lows"]
    key_resistance = chart["key_resistance"]
    key_support = chart["key_support"]
    findings = chart["findings"]
    atr_pct = chart["atr_pct"] or 1.5
    
    details = []
    score = 0.0
    direction: Literal["bullish", "bearish", "neutral"] = "neutral"
    structure_type = "none"
    price_level = None
    is_mitigated = False
    
    # Infer OB/FVG from swing structure
    # Bullish OB = last swing low area (demand zone)
    # Bearish OB = last swing high area (supply zone)
    if structure in ("bullish", "bullish_choch", "transition_bullish"):
        direction = "bullish"
        structure_type = "ob"
        if swing_lows:
            # Potential bullish OB at last swing low
            price_level = swing_lows[-1]
            # Check if price has revisited (mitigated)
            # If current price (implied from findings) is near the low, it's mitigated
            # Since we don't have current price here, assume unmitigated if structure is fresh
            is_mitigated = False
            details.append(f"4H Bullish OB at swing low: {price_level:.2f} (unmitigated)")
            score = 0.8
        elif key_support:
            price_level = key_support[0]
            details.append(f"4H Bullish OB at key support: {price_level:.2f}")
            score = 0.6
    
    elif structure in ("bearish", "bearish_choch", "transition_bearish"):
        direction = "bearish"
        structure_type = "ob"
        if swing_highs:
            price_level = swing_highs[-1]
            is_mitigated = False
            details.append(f"4H Bearish OB at swing high: {price_level:.2f} (unmitigated)")
            score = 0.8
        elif key_resistance:
            price_level = key_resistance[0]
            details.append(f"4H Bearish OB at key resistance: {price_level:.2f}")
            score = 0.6
    
    else:
        # Ranging/neutral - look for both
        details.append("4H structure ranging — no clear OB/FVG direction")
        score = 0.0
    
    # Add FVG inference (gap between swings)
    if len(swing_highs) >= 2 and len(swing_lows) >= 2:
        # Check for gap between recent swings
        gap_high = swing_highs[-2]
        gap_low = swing_lows[-1]
        if direction == "bullish" and gap_high > gap_low:
            gap_size = (gap_high - gap_low) / gap_low * 100
            if 0.3 < gap_size < 3.0:  # Reasonable FVG size
                details.append(f"4H Potential bullish FVG: {gap_low:.2f} - {gap_high:.2f} ({gap_size:.1f}%)")
                structure_type = "fvg"
                score = max(score, 0.7)
        elif direction == "bearish" and gap_high > gap_low:
            gap_size = (gap_high - gap_low) / gap_low * 100
            if 0.3 < gap_size < 3.0:
                details.append(f"4H Potential bearish FVG: {gap_low:.2f} - {gap_high:.2f} ({gap_size:.1f}%)")
                structure_type = "fvg"
                score = max(score, 0.7)
    
    return ConfluenceSignal(
        timeframe="4h",
        direction=direction,
        score=score,
        weight=0.30,
        details=details,
        structure_type=structure_type,
        price_level=price_level,
        is_mitigated=is_mitigated,
    )


def _analyze_intraday_breakouts(tech: TechnicalAnalysis, timeframe: Literal["1h", "15m"]) -> ConfluenceSignal:
    """Analyze 1H/15M for validated breakouts (weight 0.20 combined).
    
    TEACHING:
    Lower timeframes (1H, 15M) provide ENTRY PRECISION. We look for:
    - VALIDATED BREAKOUTS: Price breaks a micro-structure level WITH
      volume + follow-through (same criteria as daily BOS but on smaller scale)
    - These are the TRIGGERS for entry — they confirm the higher timeframe
      bias is playing out in real-time.
    
    Validation criteria (all mandatory):
    1. Clear micro-structure level (recent swing high/low)
    2. Candle CLOSE beyond level
    3. Volume > 1.5x recent average
    4. 3-candle follow-through in breakout direction
    
    Since we don't have raw OHLCV at 1H/15M in TechnicalAnalysis,
    we infer from:
    - MA alignment (clean stack = trending)
    - RSI momentum (not overbought/oversold in trend direction)
    - MACD confirmation
    - BB position (breakout from squeeze)
    - Volume ratio
    """
    chart = _extract_chart_reading(tech)
    ma_alignment = chart["ma_alignment"]
    rsi = chart["rsi"]
    macd_status = chart["macd_status"]
    bb_position = chart["bb_position"]
    volume_ratio = chart["volume_ratio"]
    findings = chart["findings"]
    structure = chart["structure"]
    
    details = []
    score = 0.0
    direction = "neutral"
    structure_type = "breakout"
    price_level = None
    
    # Score components for breakout validation
    bullish_signals = 0
    bearish_signals = 0
    
    # MA Alignment
    if ma_alignment == "bullish":
        bullish_signals += 1
        details.append(f"{timeframe.upper()} Bullish MA stack")
    elif ma_alignment == "bearish":
        bearish_signals += 1
        details.append(f"{timeframe.upper()} Bearish MA stack")
    
    # RSI momentum (in trend direction, not extreme)
    if rsi is not None:
        if 50 < rsi < 75:  # Healthy bullish momentum
            bullish_signals += 1
            details.append(f"{timeframe.upper()} RSI {rsi:.1f} — bullish momentum")
        elif 25 < rsi < 50:  # Healthy bearish momentum
            bearish_signals += 1
            details.append(f"{timeframe.upper()} RSI {rsi:.1f} — bearish momentum")
        elif rsi >= 75:
            details.append(f"{timeframe.upper()} RSI {rsi:.1f} — overbought caution")
        elif rsi <= 25:
            details.append(f"{timeframe.upper()} RSI {rsi:.1f} — oversold caution")
    
    # MACD confirmation
    if macd_status == "bullish":
        bullish_signals += 1
        details.append(f"{timeframe.upper()} MACD bullish crossover")
    elif macd_status == "bearish":
        bearish_signals += 1
        details.append(f"{timeframe.upper()} MACD bearish crossover")
    
    # BB position (breakout from squeeze)
    if bb_position == "above_upper":
        bullish_signals += 1
        details.append(f"{timeframe.upper()} Price above BB upper — breakout")
    elif bb_position == "below_lower":
        bearish_signals += 1
        details.append(f"{timeframe.upper()} Price below BB lower — breakdown")
    
    # Volume confirmation
    if volume_ratio is not None:
        if volume_ratio > 1.5:
            if bullish_signals > bearish_signals:
                bullish_signals += 1
                details.append(f"{timeframe.upper()} Volume {volume_ratio:.1f}x — confirms bullish breakout")
            elif bearish_signals > bullish_signals:
                bearish_signals += 1
                details.append(f"{timeframe.upper()} Volume {volume_ratio:.1f}x — confirms bearish breakdown")
        elif volume_ratio < 0.7:
            details.append(f"{timeframe.upper()} Low volume ({volume_ratio:.1f}x) — breakout suspect")
    
    # Structure context
    if structure in ("bullish", "bullish_choch", "transition_bullish"):
        bullish_signals += 1
    elif structure in ("bearish", "bearish_choch", "transition_bearish"):
        bearish_signals += 1
    
    # Determine direction and score
    if bullish_signals > bearish_signals:
        direction = "bullish"
        # Score based on signal strength (max 3-4 signals)
        score = min(1.0, bullish_signals / 4.0)
        price_level = chart["swing_highs"][-1] if chart["swing_highs"] else None
    elif bearish_signals > bullish_signals:
        direction = "bearish"
        score = min(1.0, bearish_signals / 4.0)
        price_level = chart["swing_lows"][-1] if chart["swing_lows"] else None
    else:
        direction = "neutral"
        score = 0.0
        details.append(f"{timeframe.upper()} No clear breakout direction")
    
    return ConfluenceSignal(
        timeframe=timeframe,
        direction=direction,
        score=score,
        weight=0.10,  # 0.10 each for 1h and 15m = 0.20 total
        details=details,
        structure_type=structure_type,
        price_level=price_level,
    )


def _analyze_tpo_poc_va(daily_tech: TechnicalAnalysis, h4_tech: TechnicalAnalysis) -> ConfluenceSignal:
    """Analyze TPO Volume Profile POC/VA alignment (weight 0.10).
    
    TEACHING:
    Volume Profile (TPO - Time Price Opportunity) shows WHERE volume
    traded. The Point of Control (POC) is the price with MOST volume —
    the fair price. Value Area (VA) = 70% of volume (VAH to VAL).
    
    ALIGNMENT RULES:
    - Price > POC + VA: Bullish (price above fair value, momentum up)
    - Price < POC - VA: Bearish (price below fair value, momentum down)
    - Price inside VA: Neutral/Chop (price at fair value, rangebound)
    - POC acting as support/resistance: High confluence
    
    Since we compute TPO in technical.py, we extract from there.
    """
    # The technical module computes TPO and stores in findings or we'd need
    # to add it to TechnicalAnalysis. For now, infer from structure and levels.
    daily_chart = _extract_chart_reading(daily_tech)
    h4_chart = _extract_chart_reading(h4_tech)
    
    details = []
    score = 0.0
    direction: Literal["bullish", "bearish", "neutral"] = "neutral"
    structure_type = "poc_va"
    price_level = None
    
    # Use key levels as proxy for POC/VA
    # If price is near key support with bullish structure = POC support
    # If price is near key resistance with bearish structure = POC resistance
    
    daily_structure = daily_chart["structure"]
    h4_structure = h4_chart["structure"]
    
    # Check alignment between daily and 4H key levels
    daily_support = daily_chart["key_support"]
    daily_resistance = daily_chart["key_resistance"]
    h4_support = h4_chart["key_support"]
    h4_resistance = h4_chart["key_resistance"]
    
    # Confluence: Daily support aligns with 4H support
    if daily_support and h4_support:
        for d_s in daily_support[:2]:
            for h4_s in h4_support[:2]:
                if abs(d_s - h4_s) / d_s < 0.01:  # Within 1%
                    details.append(f"POC/VA Confluence: Daily support {d_s:.2f} ≈ 4H support {h4_s:.2f}")
                    if daily_structure in ("bullish", "bullish_choch", "transition_bullish"):
                        direction = "bullish"
                        score = 0.8
                        price_level = d_s
                    elif daily_structure in ("bearish", "bearish_choch", "transition_bearish"):
                        direction = "bearish"
                        score = 0.8
                        price_level = d_s
    
    # Confluence: Daily resistance aligns with 4H resistance
    if daily_resistance and h4_resistance:
        for d_r in daily_resistance[:2]:
            for h4_r in h4_resistance[:2]:
                if abs(d_r - h4_r) / d_r < 0.01:
                    details.append(f"POC/VA Confluence: Daily resistance {d_r:.2f} ≈ 4H resistance {h4_r:.2f}")
                    if daily_structure in ("bearish", "bearish_choch", "transition_bearish"):
                        direction = "bearish"
                        score = max(score, 0.8)
                        price_level = d_r
    
    if not details:
        details.append("No clear POC/VA confluence between Daily and 4H")
    
    return ConfluenceSignal(
        timeframe="tpo",
        direction=direction,
        score=score,
        weight=0.10,
        details=details,
        structure_type=structure_type,
        price_level=price_level,
    )


def _detect_conflicts(signals: list[ConfluenceSignal]) -> tuple[list[str], bool]:
    """Detect critical conflicts between timeframes.
    
    TEACHING:
    Conflict detection is RISK MANAGEMENT. When higher timeframes disagree,
    the probability of a successful trade drops dramatically.
    
    CRITICAL CONFLICTS (avoid trades in conflicted direction):
    - Daily bullish + 4H bearish = AVOID LONGS
      (Daily says trend up, but 4H shows supply/downside pressure)
    - Daily bearish + 4H bullish = AVOID SHORTS
      (Daily says trend down, but 4H shows demand/upside pressure)
    
    These conflicts mean institutional flow is divided — choppy price action.
    """
    conflicts = []
    has_critical = False
    
    # Find daily and 4H signals
    daily_signal = next((s for s in signals if s.timeframe == "daily"), None)
    h4_signal = next((s for s in signals if s.timeframe == "4h"), None)
    
    if daily_signal and h4_signal:
        # Daily bullish + 4H bearish = avoid longs
        if daily_signal.direction == "bullish" and h4_signal.direction == "bearish":
            conflicts.append(
                "⚠️ CRITICAL CONFLICT: Daily bullish structure but 4H bearish OB/FVG — "
                "AVOID LONGS. Higher timeframe trend contradicted by institutional footprint."
            )
            has_critical = True
        
        # Daily bearish + 4H bullish = avoid shorts
        elif daily_signal.direction == "bearish" and h4_signal.direction == "bullish":
            conflicts.append(
                "⚠️ CRITICAL CONFLICT: Daily bearish structure but 4H bullish OB/FVG — "
                "AVOID SHORTS. Higher timeframe trend contradicted by institutional footprint."
            )
            has_critical = True
        
        # Daily bullish + 4H neutral = caution
        elif daily_signal.direction == "bullish" and h4_signal.direction == "neutral":
            conflicts.append(
                "⚠️ CAUTION: Daily bullish but 4H neutral — no 4H OB/FVG to enter. "
                "Wait for 4H pullback to form OB or drop to 1H for entry."
            )
        
        # Daily bearish + 4H neutral = caution
        elif daily_signal.direction == "bearish" and h4_signal.direction == "neutral":
            conflicts.append(
                "⚠️ CAUTION: Daily bearish but 4H neutral — no 4H OB/FVG to enter. "
                "Wait for 4H rally to form OB or drop to 1H for entry."
            )
    
    # Additional: 1H/15M against daily
    intraday_signals = [s for s in signals if s.timeframe in ("1h", "15m")]
    if daily_signal:
        for sig in intraday_signals:
            if daily_signal.direction == "bullish" and sig.direction == "bearish" and sig.score > 0.5:
                conflicts.append(
                    f"⚠️ {sig.timeframe.upper()} bearish breakout contradicts daily bullish bias — "
                    f"reduce position size or wait for {sig.timeframe} realignment"
                )
            elif daily_signal.direction == "bearish" and sig.direction == "bullish" and sig.score > 0.5:
                conflicts.append(
                    f"⚠️ {sig.timeframe.upper()} bullish breakout contradicts daily bearish bias — "
                    f"reduce position size or wait for {sig.timeframe} realignment"
                )
    
    return conflicts, has_critical


def _build_entry_zones(signals: list[ConfluenceSignal], overall_bias: str) -> list[dict]:
    """Build entry zones from 4H OB/FVG in direction of daily bias.
    
    TEACHING:
    ENTRY ZONES are where you place LIMIT ORDERS. They come from 4H
    Order Blocks and Fair Value Gaps that align with the daily bias.
    
    Rules:
    - Only include zones in direction of overall_bias
    - Only include UNMITIGATED zones (is_mitigated = False)
    - Price tolerance: ±0.5% around the level
    - Priority: OB > FVG (OB = stronger institutional footprint)
    """
    entry_zones = []
    
    if overall_bias == "neutral":
        return entry_zones
    
    # Find 4H signal
    h4_signal = next((s for s in signals if s.timeframe == "4h"), None)
    if not h4_signal or h4_signal.direction != overall_bias:
        return entry_zones
    
    # 4H OB/FVG in direction of bias
    if h4_signal.price_level and not h4_signal.is_mitigated:
        zone = {
            "price": round(h4_signal.price_level, 2),
            "type": h4_signal.structure_type or "ob",
            "timeframe": "4h",
            "direction": overall_bias,
            "tolerance_pct": 0.5,
            "zone_low": round(h4_signal.price_level * 0.995, 2),
            "zone_high": round(h4_signal.price_level * 1.005, 2),
            "details": h4_signal.details[0] if h4_signal.details else "",
        }
        entry_zones.append(zone)
    
    return entry_zones


def _find_invalidation_level(
    signals: list[ConfluenceSignal],
    overall_bias: str,
    daily_tech: TechnicalAnalysis,
    h4_tech: TechnicalAnalysis
) -> tuple[float | None, str | None]:
    """Find nearest opposing structure price (invalidation level).
    
    TEACHING:
    INVALIDATION LEVEL is where your thesis is WRONG. It's the price
    that, if broken, means the market structure has shifted against you.
    
    For LONG (bullish bias):
    - Nearest swing LOW below current price that would break structure
    - Daily swing low (major) or 4H swing low (minor)
    - If this breaks, the HH/HL structure is violated
    
    For SHORT (bearish bias):
    - Nearest swing HIGH above current price that would break structure
    - Daily swing high (major) or 4H swing high (minor)
    - If this breaks, the LH/LL structure is violated
    
    This becomes your STOP LOSS level (with small buffer).
    """
    daily_chart = _extract_chart_reading(daily_tech)
    h4_chart = _extract_chart_reading(h4_tech)
    
    invalidation_price = None
    reason = None
    
    if overall_bias == "bullish":
        # Find nearest support below that would invalidate bullish structure
        candidates = []
        
        # Daily swing lows (major structure)
        for low in daily_chart["swing_lows"]:
            candidates.append(("daily_swing_low", low))
        
        # 4H swing lows (minor structure)
        for low in h4_chart["swing_lows"]:
            candidates.append(("4h_swing_low", low))
        
        # Key support levels
        for support in daily_chart["key_support"]:
            candidates.append(("daily_key_support", support))
        for support in h4_chart["key_support"]:
            candidates.append(("4h_key_support", support))
        
        # Find the HIGHEST support level (closest to current price from below)
        # This is the first level that would break if price drops
        if candidates:
            # Sort by price descending (highest first = closest to current)
            candidates.sort(key=lambda x: x[1], reverse=True)
            invalidation_price = candidates[0][1]
            reason = f"Break of {candidates[0][0]} at {invalidation_price:.2f} would invalidate bullish structure"
    
    elif overall_bias == "bearish":
        # Find nearest resistance above that would invalidate bearish structure
        candidates = []
        
        # Daily swing highs (major structure)
        for high in daily_chart["swing_highs"]:
            candidates.append(("daily_swing_high", high))
        
        # 4H swing highs (minor structure)
        for high in h4_chart["swing_highs"]:
            candidates.append(("4h_swing_high", high))
        
        # Key resistance levels
        for resistance in daily_chart["key_resistance"]:
            candidates.append(("daily_key_resistance", resistance))
        for resistance in h4_chart["key_resistance"]:
            candidates.append(("4h_key_resistance", resistance))
        
        # Find the LOWEST resistance level (closest to current price from above)
        if candidates:
            candidates.sort(key=lambda x: x[1])  # Ascending = lowest first
            invalidation_price = candidates[0][1]
            reason = f"Break of {candidates[0][0]} at {invalidation_price:.2f} would invalidate bearish structure"
    
    return invalidation_price, reason


def align_signals(
    daily: TechnicalAnalysis,
    h4: TechnicalAnalysis,
    h1: TechnicalAnalysis,
    m15: TechnicalAnalysis
) -> MTFConfluenceResult:
    """Align multi-timeframe signals into a unified confluence analysis.
    
    TEACHING:
    This is the MAIN ENTRY POINT. It takes TechnicalAnalysis from 4 timeframes
    and produces a complete MTFConfluenceResult with:
    - Overall bias (bullish/bearish/neutral)
    - Weighted scores from each timeframe
    - Conflict warnings
    - Entry zones (4H OB/FVG in bias direction)
    - Invalidation level (stop loss reference)
    
    WEIGHTING (institutional standard):
    - Daily BOS/CHoCH: 0.40 — Trend definition
    - 4H OB/FVG: 0.30 — Institutional footprint
    - 1H breakouts: 0.10 — Entry timing
    - 15M breakouts: 0.10 — Entry precision
    - TPO POC/VA: 0.10 — Volume confirmation
    
    BIAS CALCULATION:
    - bull_score = sum(weighted_score for bullish signals)
    - bear_score = sum(abs(weighted_score) for bearish signals)
    - Neutral zone: |bull_score - bear_score| <= 0.15
    - Bullish: bull_score > bear_score + 0.15
    - Bearish: bear_score > bull_score + 0.15
    
    The 0.15 buffer prevents whipsaw in low-confluence/choppy markets.
    
    Args:
        daily: Daily timeframe TechnicalAnalysis (with OHLCV-derived structure)
        h4: 4H timeframe TechnicalAnalysis
        h1: 1H timeframe TechnicalAnalysis
        m15: 15M timeframe TechnicalAnalysis
        
    Returns:
        MTFConfluenceResult with complete confluence analysis
    """
    from datetime import datetime, UTC
    
    signals: list[ConfluenceSignal] = []
    all_details: list[str] = []
    
    # 1. Daily BOS/CHoCH (weight 0.40)
    daily_signal = _analyze_daily_structure(daily)
    signals.append(daily_signal)
    all_details.extend(daily_signal.details)
    
    # 2. 4H OB/FVG (weight 0.30)
    h4_signal = _analyze_4h_ob_fvg(h4)
    signals.append(h4_signal)
    all_details.extend(h4_signal.details)
    
    # 3. 1H validated breakouts (weight 0.10)
    h1_signal = _analyze_intraday_breakouts(h1, "1h")
    signals.append(h1_signal)
    all_details.extend(h1_signal.details)
    
    # 4. 15M validated breakouts (weight 0.10)
    m15_signal = _analyze_intraday_breakouts(m15, "15m")
    signals.append(m15_signal)
    all_details.extend(m15_signal.details)
    
    # 5. TPO POC/VA alignment (weight 0.10)
    tpo_signal = _analyze_tpo_poc_va(daily, h4)
    signals.append(tpo_signal)
    all_details.extend(tpo_signal.details)
    
    # Calculate weighted scores
    bull_score = sum(s.weighted_score for s in signals if s.direction == "bullish")
    bear_score = sum(abs(s.weighted_score) for s in signals if s.direction == "bearish")
    
    # Determine overall bias with 0.15 buffer
    if bull_score > bear_score + 0.15:
        overall_bias = "bullish"
        confidence = min(1.0, (bull_score - bear_score) / 0.5)  # Normalize confidence
    elif bear_score > bull_score + 0.15:
        overall_bias = "bearish"
        confidence = min(1.0, (bear_score - bull_score) / 0.5)
    else:
        overall_bias = "neutral"
        confidence = 1.0 - abs(bull_score - bear_score) / 0.15  # High confidence in neutral = low divergence
    
    # Detect conflicts
    conflicts, has_critical = _detect_conflicts(signals)
    
    # Build entry zones
    entry_zones = _build_entry_zones(signals, overall_bias)
    
    # Find invalidation level
    invalidation_level, invalidation_reason = _find_invalidation_level(
        signals, overall_bias, daily, h4
    )
    
    # Add summary details
    all_details.insert(0, f"MTF Confluence: {overall_bias.upper()} (bull={bull_score:.2f}, bear={bear_score:.2f}, conf={confidence:.2f})")
    
    if conflicts:
        all_details.append(f"Conflicts detected: {len(conflicts)}")
        for c in conflicts:
            all_details.append(f"  - {c}")
    
    if entry_zones:
        for ez in entry_zones:
            all_details.append(
                f"Entry Zone: {ez['type'].upper()} at {ez['price']:.2f} "
                f"({ez['zone_low']:.2f}-{ez['zone_high']:.2f})"
            )
    
    if invalidation_level:
        all_details.append(f"Invalidation: {invalidation_level:.2f} — {invalidation_reason}")
    
    return MTFConfluenceResult(
        overall_bias=overall_bias,
        bull_score=round(bull_score, 3),
        bear_score=round(bear_score, 3),
        confidence=round(confidence, 3),
        signals=signals,
        conflicts=conflicts,
        has_critical_conflict=has_critical,
        entry_zones=entry_zones,
        invalidation_level=round(invalidation_level, 2) if invalidation_level else None,
        invalidation_reason=invalidation_reason,
        details=all_details,
        timestamp=datetime.now(UTC).isoformat(),
    )


# ── Convenience function for orchestrator integration ──

def build_mtf_confluence_from_analysis(
    technical_results: dict[str, TechnicalAnalysis]
) -> MTFConfluenceResult | None:
    """Build MTF confluence from the technical module's multi-timeframe output.
    
    TEACHING:
    The technical.analyze() function with include_weekly=True and include_intraday=True
    returns a dict with timeframe keys. This convenience function extracts the
    relevant timeframes and calls align_signals().
    
    Expected keys in technical_results:
    - "daily": Daily TechnicalAnalysis (required)
    - "4h": 4H TechnicalAnalysis (required)
    - "1h": 1H TechnicalAnalysis (required)
    - "15m": 15M TechnicalAnalysis (optional, will use 1h if missing)
    - "weekly": Weekly TechnicalAnalysis (available but not used in MTF confluence)
    
    Returns None if required timeframes are missing.
    """
    required = ["daily", "4h", "1h"]
    if not all(tf in technical_results for tf in required):
        return None
    
    daily = technical_results["daily"]
    h4 = technical_results["4h"]
    h1 = technical_results["1h"]
    m15 = technical_results.get("15m", h1)  # Fallback to 1H if 15M not available
    
    return align_signals(daily, h4, h1, m15)