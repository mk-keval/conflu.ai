"""Smart Money Concepts (SMC) — Institutional Order Flow Analysis.

This module implements core SMC concepts used by institutional traders:
- Order Blocks (OB): Institutional entry zones (last opposite candle before impulse)
- Fair Value Gaps (FVG): Price imbalances that must fill (3-candle gaps)
- Breaker Blocks: Failed OBs that flip bias (confirmed structure shifts)
- Liquidity Mapping: Buy-side/sell-side stops, equal highs/lows, session extremes

TEACHING:
- Smart money leaves footprints — they can't enter all at once.
- OB = where institutions entered aggressively before a strong move.
- FVG = market moved too fast, left a void — price often returns to fill.
- Breaker = failed OB that reverses and breaks opposite = confirmed shift.
- Liquidity = stops = fuel for moves. Institutions hunt liquidity.

References:
- ICT (Inner Circle Trader) methodology
- SMC community standards
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd

# ──────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────

# Impulse move thresholds
MIN_IMPULSE_PCT = 1.5        # Minimum % move to qualify as impulse
MAX_IMPULSE_BARS = 10        # Max bars for impulse to develop

# Volume thresholds
IMPULSE_VOLUME_RATIO = 1.2   # Impulse volume > 1.2x average
FVG_MIDDLE_BODY_PCT = 0.5    # Middle candle body > 0.5% of price
FVG_MIDDLE_VOL_RATIO = 1.5   # Middle candle volume > 1.5x average

# Mitigation
MITIGATION_TOLERANCE_PCT = 0.1  # 0.1% tolerance for mitigation

# ──────────────────────────────────────────────────────────────
# Dataclasses
# ──────────────────────────────────────────────────────────────

@dataclass(slots=True)
class OrderBlock:
    """Order Block — Institutional entry zone.
    
    TEACHING:
    - Bullish OB: Last DOWN candle before a strong UP move (impulse).
      This is where institutions BOUGHT aggressively.
    - Bearish OB: Last UP candle before a strong DOWN move.
      This is where institutions SOLD aggressively.
    
    WHY IT WORKS:
    - Institutions can't enter all at once — they leave footprints.
    - The OB candle represents their "last chance" to enter before price runs.
    - Price OFTEN returns to OB (mitigation) before continuing.
    - Unmitigated OB = higher probability (fresh institutional interest).
    
    VALIDATION RULES:
    1. Impulse move > 1.5% in 3-10 candles
    2. OB candle body should be relatively small (accumulation)
    3. OB should align with swing structure (swing low for bullish OB)
    4. Volume on impulse > average
    """
    type: Literal["bullish_ob", "bearish_ob"]
    top: float              # High of the OB candle
    bottom: float           # Low of the OB candle
    open_price: float       # Open of the OB candle
    close_price: float      # Close of the OB candle
    index: int              # Candle index
    timestamp: pd.Timestamp
    impulsive_move_pct: float  # % move after OB
    impulse_bars: int       # Number of bars for impulse
    impulse_volume_ratio: float  # Volume ratio during impulse
    mitigated: bool = False
    mitigation_index: int | None = None
    mitigation_timestamp: pd.Timestamp | None = None
    strength: float = 0.0   # 0-1 score (impulse strength * volume confirmation)
    
    @property
    def midpoint(self) -> float:
        return (self.top + self.bottom) / 2
    
    @property
    def range_size(self) -> float:
        return self.top - self.bottom


@dataclass(slots=True)
class FairValueGap:
    """Fair Value Gap (FVG) — Price imbalance that must fill.
    
    TEACHING:
    - FVG = 3-candle pattern where candle 1 and 3 don't overlap.
    - Bullish FVG: Candle 1 high < Candle 3 low (gap UP).
    - Bearish FVG: Candle 1 low > Candle 3 high (gap DOWN).
    
    WHY IT WORKS:
    - Market moves too fast — leaves "void" with no trading.
    - Algorithms/institutions TARGET these voids to rebalance.
    - Price OFTEN returns to fill 50% (consequent encroachment) or 100%.
    - FVG in trend direction = high-probability entry.
    - FVG against trend = trap (inducement).
    
    VALIDATION (CRITICAL):
    - Middle candle (candle 2) MUST be impulsive:
      * Large body (> 0.5% of price)
      * High volume (> 1.5x average)
    - Without impulsive middle candle, it's just a gap, not an FVG.
    
    TYPES:
    - Standard FVG: Clean gap, unfilled
    - Consequent Encroachment: Price filled 50% — still valid
    - Inverse FVG: Failed FVG that becomes opposite bias
    """
    type: Literal["bullish_fvg", "bearish_fvg"]
    top: float              # Gap top (candle 1 high for bullish, candle 3 high for bearish)
    bottom: float           # Gap bottom (candle 3 low for bullish, candle 1 low for bearish)
    index: int              # Middle candle index (candle 2)
    timestamp: pd.Timestamp
    size_pct: float         # Gap size as % of price
    middle_body_pct: float  # Middle candle body size %
    middle_volume_ratio: float  # Middle candle volume ratio
    filled: bool = False
    fill_index: int | None = None
    fill_timestamp: pd.Timestamp | None = None
    consequent_encroachment: bool = False  # 50% fill
    
    @property
    def midpoint(self) -> float:
        return (self.top + self.bottom) / 2
    
    @property
    def gap_size(self) -> float:
        return self.top - self.bottom
    
    @property
    def encroachment_level(self) -> float:
        return (self.top + self.bottom) / 2  # 50% level


@dataclass(slots=True)
class BreakerBlock:
    """Breaker Block — Failed Order Block that flips bias.
    
    TEACHING:
    - Breaker Block = Order Block that was MITIGATED (price traded through it)
      but then price REVERSED and broke the other way.
    - The failed OB becomes NEW support/resistance in the OPPOSITE direction.
    - This is a POWERFUL confirmation — structure has shifted.
    
    EXAMPLE:
    - Bullish OB forms at $100. Price returns, breaks BELOW $100 (mitigated).
    - Then price rallies back ABOVE $100 and continues up.
    - The $100 level (failed bearish pressure) becomes BULLISH BREAKER
      (failed bearish pressure becomes support).
    """
    type: Literal["bullish_breaker", "bearish_breaker"]
    original_ob: OrderBlock
    break_index: int
    break_price: float
    break_timestamp: pd.Timestamp
    retest_confirmed: bool = False
    retest_index: int | None = None


@dataclass(slots=True)
class LiquidityLevel:
    """Liquidity Level — Buy-side or sell-side stop clusters.
    
    TEACHING:
    - LIQUIDITY = STOP LOSSES = FUEL FOR MOVES.
    - Buy-side liquidity = stops ABOVE price (shorts' stops, breakout buyers' stops).
    - Sell-side liquidity = stops BELOW price (longs' stops, breakdown sellers' stops).
    - Institutions HUNT liquidity — they push price to trigger stops, then reverse.
    
    KEY LIQUIDITY POOLS (priority order):
    1. Session Highs/Lows (Asian/London/NY) — intraday algorithmic stops
    2. Equal Highs/Lows (intraday) — obvious retail stops
    3. Swing Highs/Lows — structural stops
    4. Prior Day/Week High/Low — institutional reference points
    5. BOS Levels — structure break stops
    6. VWAP Deviations (±2σ, ±3σ) — algorithmic stops
    
    INDUCEMENT:
    - False breakout to grab liquidity BEFORE real move.
    - Price spikes above equal highs → triggers shorts' stops → reverses down.
    """
    price: float
    type: Literal["buy_side", "sell_side"]
    source: Literal["equal_highs", "equal_lows", "swing_high", "swing_low",
                    "pdh", "pdl", "pwh", "pwl", "session_high", "session_low", "bos_level"]
    strength: int  # Number of touches / significance
    timestamp: pd.Timestamp
    timeframe: str = "daily"


# ──────────────────────────────────────────────────────────────
# Core Detection Functions
# ──────────────────────────────────────────────────────────────

def _get_avg_volume(ohlcv: pd.DataFrame, period: int = 20) -> pd.Series:
    return ohlcv["Volume"].rolling(period, min_periods=1).mean()


def _is_impulsive_move(
    ohlcv: pd.DataFrame,
    start_idx: int,
    direction: Literal["up", "down"],
    min_pct: float = MIN_IMPULSE_PCT,
    max_bars: int = MAX_IMPULSE_BARS
) -> tuple[bool, int, float, float]:
    """Check if an impulsive move occurs starting after start_idx.
    
    Returns: (is_impulsive, impulse_bars, move_pct, avg_volume_ratio)
    """
    close = ohlcv["Close"].to_numpy()
    volume = ohlcv["Volume"].to_numpy()
    avg_vol = _get_avg_volume(ohlcv).to_numpy()
    start_price = close[start_idx]
    
    for j in range(start_idx + 1, min(start_idx + max_bars + 1, len(close))):
        move_pct = (close[j] - start_price) / start_price * 100
        
        if direction == "up" and move_pct >= min_pct:
            # Calculate impulse volume
            impulse_vol = volume[start_idx + 1:j + 1].mean()
            avg_vol = avg_vol[start_idx:j + 1].mean()
            vol_ratio = impulse_vol / avg_vol if avg_vol > 0 else 0
            return True, j - start_idx, move_pct, vol_ratio
        elif direction == "down" and -move_pct >= min_pct:
            impulse_vol = volume[start_idx + 1:j + 1].mean()
            avg_vol = avg_vol[start_idx:j + 1].mean()
            vol_ratio = impulse_vol / avg_vol if avg_vol > 0 else 0
            return True, j - start_idx, -move_pct, vol_ratio
    
    return False, 0, 0.0, 0.0


def detect_order_blocks(
    ohlcv: pd.DataFrame,
    real_time: bool = False,
    min_impulse_pct: float = MIN_IMPULSE_PCT,
    lookback: int = 50
) -> list[OrderBlock]:
    """Detect Order Blocks (OB) — Institutional Entry Zones.
    
    TEACHING:
    - Bullish OB: Last DOWN candle before a strong UP move (impulse).
      This is where institutions BOUGHT aggressively.
    - Bearish OB: Last UP candle before a strong DOWN move.
      This is where institutions SOLD aggressively.
    
    WHY IT WORKS:
    - Institutions can't enter all at once — they leave footprints.
    - The OB candle represents their "last chance" to enter before price runs.
    - Price OFTEN returns to OB (mitigation) before continuing.
    - Unmitigated OB = higher probability (fresh institutional interest).
    
    MODES:
    - real_time=False (historical analysis): Lookahead allowed to find impulses
    - real_time=True (live trading): NO lookahead — only confirmed OBs returned
    
    Args:
        ohlcv: DataFrame with OHLCV columns, datetime index
        real_time: If True, only return OBs where impulse is already confirmed
        min_impulse_pct: Minimum % move to qualify as impulse
        lookback: Bars to look back for OB candidates
    
    Returns:
        List of OrderBlock objects
    """
    obs: list[OrderBlock] = []
    close = ohlcv["Close"].to_numpy()
    open_ = ohlcv["Open"].to_numpy()
    high = ohlcv["High"].to_numpy()
    low = ohlcv["Low"].to_numpy()
    volume = ohlcv["Volume"].to_numpy()
    avg_volume = _get_avg_volume(ohlcv).to_numpy()
    
    if real_time:
        # REAL-TIME MODE: Only return OBs where impulse is ALREADY confirmed
        max_idx = len(ohlcv) - 1
        start_idx = max(lookback, max_idx - 100)
    else:
        # HISTORICAL MODE: Full lookahead allowed
        max_idx = len(ohlcv) - 10
        start_idx = lookback
    
    for i in range(start_idx, max_idx):
        # Check for bullish impulse starting after i
        if close[i] < open_[i]:  # Down candle (potential bullish OB)
            is_impulsive, impulse_bars, move_pct, vol_ratio = _is_impulsive_move(
                ohlcv, i, "up", min_impulse_pct
            )
            if is_impulsive and vol_ratio > IMPULSE_VOLUME_RATIO:
                ob = OrderBlock(
                    type="bullish_ob",
                    top=float(high[i]),
                    bottom=float(low[i]),
                    open_price=float(open_[i]),
                    close_price=float(close[i]),
                    index=i,
                    timestamp=ohlcv.index[i],
                    impulsive_move_pct=round(move_pct, 2),
                    impulse_bars=impulse_bars,
                    impulse_volume_ratio=round(vol_ratio, 2),
                    strength=min(1.0, (move_pct / 5.0) * vol_ratio)
                )
                obs.append(ob)
        
        # Check for bearish impulse
        if close[i] > open_[i]:  # Up candle (potential bearish OB)
            is_impulsive, impulse_bars, move_pct, vol_ratio = _is_impulsive_move(
                ohlcv, i, "down", min_impulse_pct
            )
            if is_impulsive and vol_ratio > IMPULSE_VOLUME_RATIO:
                ob = OrderBlock(
                    type="bearish_ob",
                    top=float(high[i]),
                    bottom=float(low[i]),
                    open_price=float(open_[i]),
                    close_price=float(close[i]),
                    index=i,
                    timestamp=ohlcv.index[i],
                    impulsive_move_pct=round(move_pct, 2),
                    impulse_bars=impulse_bars,
                    impulse_volume_ratio=round(vol_ratio, 2),
                    strength=min(1.0, (move_pct / 5.0) * vol_ratio)
                )
                obs.append(ob)
    
    # Check mitigation (historical mode only)
    if not real_time:
        for ob in obs:
            for k in range(ob.index + 1, len(close)):
                if ob.type == "bullish_ob" and low[k] is not None and ob.bottom is not None and low[k] <= ob.bottom + ob.bottom * MITIGATION_TOLERANCE_PCT / 100:
                    ob.mitigated = True
                    ob.mitigation_index = k
                    ob.mitigation_timestamp = ohlcv.index[k]
                    break
                elif ob.type == "bearish_ob" and high[k] is not None and ob.top is not None and high[k] >= ob.top - ob.top * MITIGATION_TOLERANCE_PCT / 100:
                    ob.mitigated = True
                    ob.mitigation_index = k
                    ob.mitigation_timestamp = ohlcv.index[k]
                    break
    
    return obs


def detect_fvg(ohlcv: pd.DataFrame, min_gap_pct: float = 0.1) -> list[FairValueGap]:
    """Detect Fair Value Gaps (FVG) — Price Imbalances.
    
    TEACHING:
    - FVG = 3-candle pattern where candle 1 and 3 don't overlap.
    - Bullish FVG: Candle 1 high < Candle 3 low (gap UP).
    - Bearish FVG: Candle 1 low > Candle 3 high (gap DOWN).
    
    WHY IT WORKS:
    - Market moves too fast — leaves "void" with no trading.
    - Algorithms/institutions TARGET these voids to rebalance.
    - Price OFTEN returns to fill 50% (consequent encroachment) or 100%.
    - FVG in trend direction = high-probability entry.
    - FVG against trend = trap (inducement).
    
    VALIDATION (CRITICAL):
    - Middle candle (candle 2) MUST be impulsive:
      * Large body (> 0.5% of price)
      * High volume (> 1.5x average)
    - Without impulsive middle candle, it's just a gap, not an FVG.
    
    TYPES:
    - Standard FVG: Clean gap, unfilled
    - Consequent Encroachment: Price filled 50% — still valid
    - Inverse FVG: Failed FVG that becomes opposite bias
    
    Args:
        ohlcv: DataFrame with OHLCV columns, datetime index
        min_gap_pct: Minimum gap size as % of price
    
    Returns:
        List of FairValueGap objects
    """
    fvgs: list[FairValueGap] = []
    high = ohlcv["High"].to_numpy()
    low = ohlcv["Low"].to_numpy()
    close = ohlcv["Close"].to_numpy()
    open_ = ohlcv["Open"].to_numpy()
    volume = ohlcv["Volume"].to_numpy()
    avg_volume = _get_avg_volume(ohlcv).to_numpy()
    
    for i in range(1, len(ohlcv) - 1):
        # Middle candle (i) must be impulsive
        middle_body_pct = abs(close[i] - open_[i]) / close[i] * 100
        middle_volume_ratio = volume[i] / avg_volume[i] if avg_volume[i] > 0 else 0
        
        if middle_body_pct < FVG_MIDDLE_BODY_PCT or middle_volume_ratio < FVG_MIDDLE_VOL_RATIO:
            continue  # Middle candle not impulsive enough
        
        # Bullish FVG: Candle i-1 high < Candle i+1 low
        if high[i - 1] < low[i + 1]:
            gap_top = float(low[i + 1])
            gap_bottom = float(high[i - 1])
            size_pct = (gap_top - gap_bottom) / close[i] * 100
            
            if size_pct > min_gap_pct:
                fvg = FairValueGap(
                    type="bullish_fvg",
                    top=gap_top,
                    bottom=gap_bottom,
                    index=i,
                    timestamp=ohlcv.index[i],
                    size_pct=round(size_pct, 2),
                    middle_body_pct=round(middle_body_pct, 2),
                    middle_volume_ratio=round(middle_volume_ratio, 2)
                )
                fvgs.append(fvg)
        
        # Bearish FVG: Candle i-1 low > Candle i+1 high
        if low[i - 1] > high[i + 1]:
            gap_top = float(low[i - 1])
            gap_bottom = float(high[i + 1])
            size_pct = (gap_top - gap_bottom) / close[i] * 100
            
            if size_pct > min_gap_pct:
                fvg = FairValueGap(
                    type="bearish_fvg",
                    top=gap_top,
                    bottom=gap_bottom,
                    index=i,
                    timestamp=ohlcv.index[i],
                    size_pct=round(size_pct, 2),
                    middle_body_pct=round(middle_body_pct, 2),
                    middle_volume_ratio=round(middle_volume_ratio, 2)
                )
                fvgs.append(fvg)
    
    # Check fills
    for fvg in fvgs:
        for k in range(fvg.index + 2, len(close)):
            if fvg.type == "bullish_fvg":
                if low[k] <= fvg.bottom:
                    fvg.filled = True
                    fvg.fill_index = k
                    fvg.fill_timestamp = ohlcv.index[k]
                    break
                elif low[k] <= fvg.encroachment_level:
                    fvg.consequent_encroachment = True
            else:
                if high[k] >= fvg.top:
                    fvg.filled = True
                    fvg.fill_index = k
                    fvg.fill_timestamp = ohlcv.index[k]
                    break
                elif high[k] >= fvg.encroachment_level:
                    fvg.consequent_encroachment = True
    
    return fvgs


def detect_breaker_blocks(obs: list[OrderBlock], ohlcv: pd.DataFrame) -> list[BreakerBlock]:
    """Detect Breaker Blocks — Failed Order Blocks that Flip Bias.
    
    TEACHING:
    - Breaker Block = Order Block that was MITIGATED (price traded through it)
      but then price REVERSED and broke the other way.
    - The failed OB becomes NEW support/resistance in the OPPOSITE direction.
    - This is a POWERFUL confirmation — structure has shifted.
    
    EXAMPLE:
    - Bullish OB forms at $100. Price returns, breaks BELOW $100 (mitigated).
    - Then price rallies back ABOVE $100 and continues up.
    - The $100 level (failed bearish pressure) becomes BULLISH BREAKER
      (failed bearish pressure becomes support).
    
    Args:
        obs: List of OrderBlock from detect_order_blocks()
        ohlcv: DataFrame with OHLCV columns, datetime index
    
    Returns:
        List of BreakerBlock objects
    """
    breakers: list[BreakerBlock] = []
    close = ohlcv["Close"].to_numpy()
    high = ohlcv["High"].to_numpy()
    low = ohlcv["Low"].to_numpy()
    
    for ob in obs:
        if not ob.mitigated:
            continue
            
        # Check if price reverses after mitigation
        if ob.type == "bullish_ob" and ob.top is not None and ob.mitigation_index is not None:
            # Bullish OB was broken down — check for rally back up
            for k in range(ob.mitigation_index + 1, len(close)):
                if close[k] > ob.top:  # Reclaimed the OB
                    # Confirm with follow-through (3 candles)
                    if k + 3 < len(close) and all(close[m] > close[m - 1] for m in range(k + 1, k + 4)):
                        breaker = BreakerBlock(
                            type="bullish_breaker",
                            original_ob=ob,
                            break_index=k,
                            break_price=float(close[k]),
                            break_timestamp=ohlcv.index[k],
                            retest_confirmed=True
                        )
                        breakers.append(breaker)
                    break
        
        elif ob.type == "bearish_ob" and ob.bottom is not None and ob.mitigation_index is not None:
            # Bearish OB was broken up — check for drop back down
            for k in range(ob.mitigation_index + 1, len(close)):
                if close[k] < ob.bottom:
                    if k + 3 < len(close) and all(close[m] < close[m - 1] for m in range(k + 1, k + 4)):
                        breaker = BreakerBlock(
                            type="bearish_breaker",
                            original_ob=ob,
                            break_index=k,
                            break_price=float(close[k]),
                            break_timestamp=ohlcv.index[k],
                            retest_confirmed=True
                        )
                        breakers.append(breaker)
                    break
    
    return breakers


def map_liquidity(
    ohlcv_daily: pd.DataFrame,
    ohlcv_intraday: pd.DataFrame | None,
    ohlcv_weekly: pd.DataFrame | None,
    swings: list,
    bos_events: list
) -> list[LiquidityLevel]:
    """Map Buy-Side and Sell-Side Liquidity.
    
    TEACHING:
    - LIQUIDITY = STOP LOSSES = FUEL FOR MOVES.
    - Buy-side liquidity = stops ABOVE price (shorts' stops, breakout buyers' stops).
    - Sell-side liquidity = stops BELOW price (longs' stops, breakdown sellers' stops).
    - Institutions HUNT liquidity — they push price to trigger stops, then reverse.
    
    KEY LIQUIDITY POOLS (priority order):
    1. Session Highs/Lows (Asian/London/NY) — intraday algorithmic stops
    2. Equal Highs/Lows (intraday) — obvious retail stops
    3. Swing Highs/Lows — structural stops
    4. Prior Day/Week High/Low — institutional reference points
    5. BOS Levels — structure break stops
    6. VWAP Deviations (±2σ, ±3σ) — algorithmic stops
    
    INDUCEMENT:
    - False breakout to grab liquidity BEFORE real move.
    - Price spikes above equal highs → triggers shorts' stops → reverses down.
    
    Args:
        ohlcv_daily: Daily OHLCV
        ohlcv_intraday: Intraday OHLCV (5m/15m) for session highs/lows
        ohlcv_weekly: Weekly OHLCV
        swings: List of SwingPoint from structure.detect_swings()
        bos_events: List of BOSEvent from structure.detect_bos_choch()
    
    Returns:
        List of LiquidityLevel objects
    """
    levels: list[LiquidityLevel] = []
    
    # SESSION HIGHS/LOWS (from intraday data) — HIGHEST PRIORITY
    if ohlcv_intraday is not None and len(ohlcv_intraday) > 0:
        session_high = float(ohlcv_intraday["High"].max())
        session_low = float(ohlcv_intraday["Low"].min())
        levels.append(LiquidityLevel(
            price=session_high,
            type="buy_side",
            source="session_high",
            strength=3,
            timestamp=ohlcv_intraday.index[-1],
            timeframe="intraday"
        ))
        levels.append(LiquidityLevel(
            price=session_low,
            type="sell_side",
            source="session_low",
            strength=3,
            timestamp=ohlcv_intraday.index[-1],
            timeframe="intraday"
        ))
    
    # EQUAL HIGHS/LOWS (use intraday for precision, daily as fallback)
    equal_high_source = ohlcv_intraday if ohlcv_intraday is not None else ohlcv_daily
    equal_low_source = ohlcv_intraday if ohlcv_intraday is not None else ohlcv_daily
    
    high = equal_high_source["High"].to_numpy()
    low = equal_low_source["Low"].to_numpy()
    
    # Equal highs (buy-side)
    for i in range(2, len(high)):
        if abs(high[i] - high[i - 1]) / high[i] < 0.005:  # Within 0.5%
            touches = 2
            if i >= 3 and abs(high[i] - high[i - 2]) / high[i] < 0.005:
                touches = 3
            levels.append(LiquidityLevel(
                price=float(high[i]),
                type="buy_side",
                source="equal_highs",
                strength=touches,
                timestamp=equal_high_source.index[i],
                timeframe="intraday" if ohlcv_intraday is not None else "daily"
            ))
    
    # Equal lows (sell-side)
    for i in range(2, len(low)):
        if abs(low[i] - low[i - 1]) / low[i] < 0.005:
            touches = 2
            if i >= 3 and abs(low[i] - low[i - 2]) / low[i] < 0.005:
                touches = 3
            levels.append(LiquidityLevel(
                price=float(low[i]),
                type="sell_side",
                source="equal_lows",
                strength=touches,
                timestamp=equal_low_source.index[i],
                timeframe="intraday" if ohlcv_intraday is not None else "daily"
            ))
    
    # Swing highs/lows from structure
    for swing in swings:
        if swing.type == "high":
            levels.append(LiquidityLevel(
                price=swing.price,
                type="buy_side",
                source="swing_high",
                strength=swing.strength,
                timestamp=swing.timestamp,
                timeframe="daily"
            ))
        else:
            levels.append(LiquidityLevel(
                price=swing.price,
                type="sell_side",
                source="swing_low",
                strength=swing.strength,
                timestamp=swing.timestamp,
                timeframe="daily"
            ))
    
    # Prior day high/low
    if len(ohlcv_daily) >= 2:
        levels.append(LiquidityLevel(
            price=float(ohlcv_daily["High"].iloc[-2]),
            type="buy_side", source="pdh", strength=2,
            timestamp=ohlcv_daily.index[-2], timeframe="daily"
        ))
        levels.append(LiquidityLevel(
            price=float(ohlcv_daily["Low"].iloc[-2]),
            type="sell_side", source="pdl", strength=2,
            timestamp=ohlcv_daily.index[-2], timeframe="daily"
        ))
    
    # Prior week high/low
    if ohlcv_weekly is not None and len(ohlcv_weekly) >= 2:
        levels.append(LiquidityLevel(
            price=float(ohlcv_weekly["High"].iloc[-2]),
            type="buy_side", source="pwh", strength=3,
            timestamp=ohlcv_weekly.index[-2], timeframe="weekly"
        ))
        levels.append(LiquidityLevel(
            price=float(ohlcv_weekly["Low"].iloc[-2]),
            type="sell_side", source="pwl", strength=3,
            timestamp=ohlcv_weekly.index[-2], timeframe="weekly"
        ))
    
    # BOS levels become liquidity magnets
    for bos in bos_events:
        if bos.type == "bullish_bos":
            levels.append(LiquidityLevel(
                price=bos.structure_level,
                type="buy_side", source="bos_level", strength=3,
                timestamp=bos.break_timestamp, timeframe="daily"
            ))
        else:
            levels.append(LiquidityLevel(
                price=bos.structure_level,
                type="sell_side", source="bos_level", strength=3,
                timestamp=bos.break_timestamp, timeframe="daily"
            ))
    
    return levels


# ──────────────────────────────────────────────────────────────
# Convenience: Full SMC Pipeline
# ──────────────────────────────────────────────────────────────

def run_smc_analysis(
    ohlcv_daily: pd.DataFrame,
    ohlcv_intraday: pd.DataFrame | None,
    ohlcv_weekly: pd.DataFrame | None,
    swings: list,
    bos_events: list,
    real_time: bool = False
) -> dict:
    """Run complete SMC analysis pipeline.
    
    Returns dict with:
    - order_blocks: list[OrderBlock]
    - fair_value_gaps: list[FairValueGap]
    - breaker_blocks: list[BreakerBlock]
    - liquidity_levels: list[LiquidityLevel]
    """
    order_blocks = detect_order_blocks(ohlcv_daily, real_time=real_time)
    fair_value_gaps = detect_fvg(ohlcv_daily)
    breaker_blocks = detect_breaker_blocks(order_blocks, ohlcv_daily)
    liquidity_levels = map_liquidity(
        ohlcv_daily, ohlcv_intraday, ohlcv_weekly, swings, bos_events
    )
    
    return {
        "order_blocks": order_blocks,
        "fair_value_gaps": fair_value_gaps,
        "breaker_blocks": breaker_blocks,
        "liquidity_levels": liquidity_levels
    }