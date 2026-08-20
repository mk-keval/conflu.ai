"""Macro Overlay — Applies market regime adjustments to individual ticker verdicts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.app.domain.ticker_analysis.models import AnalysisVerdict


@dataclass
class MacroAdjustment:
    """Adjustments to apply based on market regime."""
    stop_multiplier: float = 1.0      # Multiply stop distance
    position_size_multiplier: float = 1.0  # Multiply position size
    conviction_adjustment: int = 0    # Add/subtract from conviction
    quality_bias_boost: float = 0.0   # Boost to quality/fundamental weight
    skip_trade: bool = False          # Skip trade entirely
    notes: list[str] = field(default_factory=list)


# Market regime thresholds (VIX-based)
VIX_PANIC = 60      # Crisis / panic
VIX_FEARFUL = 35    # Fearful
VIX_ELEVATED = 25   # Elevated
VIX_NORMAL_HIGH = 20  # Normal high
VIX_NORMAL = 15     # Normal
VIX_LOW = 12        # Low / complacent


def get_macro_adjustment(
    vix: float,
    composite_score: float,
    risk_appetite_score: float,
    sector_breadth_pct: float,
    safe_haven_score: float,
    weighted_score: float,
    verdict: AnalysisVerdict,
) -> MacroAdjustment:
    """
    Calculate macro adjustments for a ticker based on market regime.
    
    Args:
        vix: Current VIX level
        composite_score: Market regime composite score (0-100)
        risk_appetite_score: Risk appetite score (0-100)
        sector_breadth_pct: Sector breadth percentage (0-100)
        safe_haven_score: Safe haven score (0-100)
        weighted_score: Ticker's weighted composite score (-1 to 1)
        verdict: Current ticker verdict
    
    Returns:
        MacroAdjustment with adjustments to apply
    """
    adj = MacroAdjustment()
    
    # ── VIX-based adjustments ──
    if vix >= VIX_PANIC:  # >= 60: Crisis / Panic
        adj.stop_multiplier = 1.5          # Wider stops
        adj.position_size_multiplier = 0.5  # Half position size
        adj.conviction_adjustment = -2      # Lower conviction
        adj.quality_bias_boost = 0.3        # Strong quality bias
        adj.notes.append(f"VIX {vix:.0f} (panic): 50% size, 1.5x stops, -2 conviction, quality bias")
        
    elif vix >= VIX_FEARFUL:  # 35-60: Fearful
        adj.stop_multiplier = 1.3
        adj.position_size_multiplier = 0.65
        adj.conviction_adjustment = -1
        adj.quality_bias_boost = 0.2
        adj.notes.append(f"VIX {vix:.0f} (fearful): 65% size, 1.3x stops, -1 conviction")
        
    elif vix >= VIX_ELEVATED:  # 25-35: Elevated
        adj.stop_multiplier = 1.2
        adj.position_size_multiplier = 0.8
        adj.conviction_adjustment = -1
        adj.notes.append(f"VIX {vix:.0f} (elevated): 80% size, 1.2x stops, -1 conviction")
        
    elif vix >= VIX_NORMAL_HIGH:  # 20-25: Normal-high
        adj.stop_multiplier = 1.1
        adj.position_size_multiplier = 0.9
        adj.notes.append(f"VIX {vix:.0f} (elevated-normal): 90% size, 1.1x stops")
        
    elif vix <= VIX_LOW:  # <= 12: Complacent
        # Slightly more aggressive, but cap at 1.1x position size
        adj.position_size_multiplier = 1.1
        adj.stop_multiplier = 0.9
        adj.notes.append(f"VIX {vix:.0f} (complacent): 1.1x size, 0.9x stops")
    
    # ── Composite score adjustments ──
    if composite_score <= 20:  # Crisis
        adj.position_size_multiplier *= 0.7
        adj.conviction_adjustment -= 1
        adj.notes.append("Composite crisis: further -30% size, -1 conviction")
    elif composite_score <= 35:  # Risk-off
        adj.position_size_multiplier *= 0.85
        adj.notes.append("Composite risk-off: -15% size")
    elif composite_score >= 80:  # Exuberance
        adj.stop_multiplier *= 1.1
        adj.notes.append("Composite exuberance: wider stops")
    
    # ── Risk appetite adjustments ──
    if risk_appetite_score <= 20:  # Strong risk-off
        adj.position_size_multiplier *= 0.8
        adj.quality_bias_boost += 0.15
        adj.notes.append("Risk-off: -20% size, quality bias")
    elif risk_appetite_score >= 80:  # Strong risk-on
        adj.position_size_multiplier *= 1.1
        adj.notes.append("Risk-on: +10% size")
    
    # ── Sector breadth ──
    if sector_breadth_pct <= 20:  # Broad weakness
        adj.position_size_multiplier *= 0.85
        adj.conviction_adjustment -= 1
        adj.notes.append("Narrow breadth: -15% size, -1 conviction")
    elif sector_breadth_pct >= 80:  # Broad strength
        adj.position_size_multiplier *= 1.1
        adj.notes.append("Broad breadth: +10% size")
    
    # ── Safe haven demand ──
    if safe_haven_score <= 20:  # Flight to safety
        adj.position_size_multiplier *= 0.8
        adj.quality_bias_boost += 0.2
        adj.notes.append("Flight to safety: -20% size, quality bias")
    
    # ── Ticker-specific: Beta adjustment ──
    # High beta stocks get more macro sensitivity
    # This would need the ticker's beta, which we don't have here
    # Could be added later by passing beta
    
    # ── Skip trade logic ──
    # In extreme panic with negative score, skip entirely
    if vix >= VIX_PANIC and weighted_score < -0.2:
        adj.skip_trade = True
        adj.notes.append("Panic VIX + negative score: skip trade")
    
    # Clamp multipliers
    adj.stop_multiplier = max(0.5, min(2.0, adj.stop_multiplier))
    adj.position_size_multiplier = max(0.2, min(1.5, adj.position_size_multiplier))
    adj.conviction_adjustment = max(-5, min(3, adj.conviction_adjustment))
    
    return adj


def apply_macro_adjustment(verdict: AnalysisVerdict, adjustment: MacroAdjustment) -> AnalysisVerdict:
    """Apply macro adjustment to a verdict, returning modified verdict."""
    if adjustment.skip_trade:
        return AnalysisVerdict(
            action="SKIP",
            conviction=1,
            entry_zone_low=None,
            entry_zone_high=None,
            stop_loss=None,
            targets=[],
            risk_reward=None,
            position_size_pct=0,
            key_red_flags=["Macro skip: " + "; ".join(adjustment.notes)] if adjustment.notes else ["Macro skip"],
            buy_triggers=[],
            sell_triggers=["Macro regime unfavorable — do not trade"],
            thesis="Trade skipped due to extreme macro regime. " + "; ".join(adjustment.notes),
        )
    
    # Adjust stop loss
    if verdict.stop_loss is not None and verdict.entry_zone_high is not None:
        entry = verdict.entry_zone_high
        stop_dist = abs(entry - verdict.stop_loss)
        new_stop_dist = stop_dist * adjustment.stop_multiplier
        if verdict.action in ("BUY", "ACCUMULATE", "WATCH"):
            new_stop = entry - new_stop_dist
        else:
            new_stop = entry + new_stop_dist
        verdict.stop_loss = round(new_stop, 2)
    
    # Adjust targets (keep same R:R ratio)
    if verdict.stop_loss is not None and verdict.targets:
        entry = verdict.entry_zone_high
        if entry and verdict.stop_loss:
            risk_per_share = abs(entry - verdict.stop_loss)
            new_targets = []
            for i, target in enumerate(verdict.targets):
                target_dist = abs(target - entry)
                rr = target_dist / risk_per_share if risk_per_share > 0 else 1.5
                new_target_dist = risk_per_share * rr
                if target > entry:
                    new_targets.append(round(entry + new_target_dist, 2))
                else:
                    new_targets.append(round(entry - new_target_dist, 2))
            verdict.targets = new_targets
    
    # Adjust position size
    if verdict.position_size_pct > 0:
        new_size = verdict.position_size_pct * adjustment.position_size_multiplier
        verdict.position_size_pct = round(max(0.5, min(new_size, 25.0)), 1)
    
    # Adjust conviction
    new_conviction = adjustment.conviction_adjustment + verdict.conviction
    verdict.conviction = max(1, min(10, new_conviction))
    
    # Add macro notes to thesis
    if adjustment.notes:
        macro_note = "Macro: " + "; ".join(adjustment.notes)
        verdict.thesis = macro_note + " | " + verdict.thesis
    
    # Add quality bias note if boosted
    if adjustment.quality_bias_boost > 0:
        verdict.key_red_flags.append(
            f"Macro quality bias: favor high-quality names (boost +{adjustment.quality_bias_boost:.0%})"
        )
    
    return verdict


# ── Convenience function for integration ──
def get_market_regime_adjustment(verdict: AnalysisVerdict, tv_data: dict[str, Any] | None = None) -> MacroAdjustment:
    """
    Fetch market regime and calculate adjustment for a ticker verdict.
    
    This function fetches the current market regime from the regime endpoint
    and calculates appropriate adjustments.
    """
    # Import here to avoid circular imports
    from backend.app.infrastructure.market.regime import get_market_regime_async, MarketRegimeResponse
    
    # Call the regime computation internally
    import asyncio
    
    async def _get_regime() -> MarketRegimeResponse:
        return await get_market_regime_async()
    
    try:
        # Run async in sync context
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    regime = loop.run_until_complete(_get_regime())
    
    return get_macro_adjustment(
        vix=regime.vix.value,
        composite_score=regime.composite_score,
        risk_appetite_score=regime.risk_appetite.score,
        sector_breadth_pct=regime.sector_breadth.value,
        safe_haven_score=regime.safe_haven.score,
        weighted_score=0,  # Would need to pass from verdict
        verdict=verdict,
    )