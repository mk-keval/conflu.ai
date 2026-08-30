"""Market Structure Analysis — BOS/CHoCH Detection.

Institutional-grade market structure detection for trend continuation and reversal.

TEACHING:
- Market structure = swing highs/lows forming Higher Highs (HH), Higher Lows (HL),
  Lower Highs (LH), Lower Lows (LL). This is the FOUNDATION of price action.
- BOS (Break of Structure): Price CLOSES beyond a significant swing level WITH volume.
  This is TREND CONTINUATION — the trend is showing strength.
- CHoCH (Change of Character): BOS + pullback to broken level (now flipped S/R) +
  continuation in NEW direction. This is TREND REVERSAL — structure has shifted.
- VOLUME CONFIRMATION IS MANDATORY: Breakout candle volume > 1.5x 20-period average.
  Without volume, it's likely a false break (retail trap).
- FOLLOW-THROUGH: Next 3 candles must continue in breakout direction.
  Confirms momentum, not just a spike.
- ALGORITHM: Single O(n) pass through price tracking ACTIVE (unbroken) swing levels.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd


@dataclass
class SwingPoint:
    """A single swing high or low point in market structure.
    
    TEACHING:
    - Swing High: Candle higher than `lookback` candles on BOTH sides.
    - Swing Low: Candle lower than `lookback` candles on BOTH sides.
    - Stronger swings (higher lookback) = more significant levels.
    - These are the FOOTPRINTS of supply/demand — institutional order flow.
    """
    price: float
    index: int
    timestamp: pd.Timestamp
    type: Literal["high", "low"]
    strength: int  # Number of bars on each side (fractal strength)


@dataclass
class BOSEvent:
    """Break of Structure event — trend continuation signal.
    
    TEACHING:
    - Bullish BOS: Close breaks above swing HIGH with volume + follow-through.
      Trend continues UP. Broken resistance becomes new support.
    - Bearish BOS: Close breaks below swing LOW with volume + follow-through.
      Trend continues DOWN. Broken support becomes new resistance.
    - VALIDATION REQUIREMENTS (all mandatory):
      1. Clear swing level structure exists
      2. Candle CLOSE beyond level (wick doesn't count)
      3. Volume > 1.5x 20-period average (institutional participation)
      4. 3-candle follow-through in breakout direction (momentum)
    """
    type: Literal["bullish_bos", "bearish_bos"]
    break_price: float
    break_index: int
    break_timestamp: pd.Timestamp
    structure_level: float  # The swing high/low that was broken
    volume_confirmed: bool
    volume_ratio: float
    follow_through: bool  # Next 3 candles continue direction
    retest_confirmed: bool = False
    retest_index: int | None = None


@dataclass
class CHoCHEvent:
    """Change of Character event — trend reversal signal.
    
    TEACHING:
    - CHoCH = BOS + pullback that HOLDS at broken level + continuation.
    - This is the SMOKING GUN for trend reversal.
    - Process:
      1. BOS occurs (structure breaks)
      2. Price pulls back to the BROKEN level (now flipped S/R)
      3. Price HOLDS and continues in NEW direction (3 candles)
    - Pullback depth matters: shallow pullback (<50% of move) = stronger reversal.
    - Deep pullback (>50%) = weaker, could be complex correction.
    """
    type: Literal["bullish_choch", "bearish_choch"]
    bos_event: BOSEvent
    confirmation_price: float
    confirmation_index: int
    pullback_depth_pct: float  # How deep the pullback was (% from break price)
    structure_shift_confirmed: bool


def detect_swings(ohlcv: pd.DataFrame, lookback: int = 5) -> list[SwingPoint]:
    """Detect swing highs/lows using fractal pattern — O(n) single pass.
    
    TEACHING:
    A swing high is a candle higher than `lookback` candles
    on BOTH sides. Same for swing low. This is market structure —
    the footprints of supply/demand.
    
    Stronger swings (higher lookback) = more significant levels.
    Default lookback=5 gives 5-bar fractals (2 bars each side minimum).
    
    Args:
        ohlcv: DataFrame with OHLCV columns, datetime index
        lookback: Number of bars on each side for fractal detection (default 5)
        
    Returns:
        List of SwingPoint objects (chronological order)
    """
    highs: np.ndarray = ohlcv["High"].to_numpy()
    lows: np.ndarray = ohlcv["Low"].to_numpy()
    timestamps = ohlcv.index
    
    swings: list[SwingPoint] = []
    
    for i in range(lookback, len(ohlcv) - lookback):
        # Swing high: current high > all highs in lookback window before and after
        is_swing_high = all(
            highs[i] > highs[i - j] and highs[i] > highs[i + j]
            for j in range(1, lookback + 1)
        )
        
        # Swing low: current low < all lows in lookback window before and after
        is_swing_low = all(
            lows[i] < lows[i - j] and lows[i] < lows[i + j]
            for j in range(1, lookback + 1)
        )
        
        if is_swing_high:
            swings.append(SwingPoint(
                price=float(highs[i]),
                index=i,
                timestamp=timestamps[i],
                type="high",
                strength=lookback
            ))
        if is_swing_low:
            swings.append(SwingPoint(
                price=float(lows[i]),
                index=i,
                timestamp=timestamps[i],
                type="low",
                strength=lookback
            ))
    
    return swings


def detect_bos_choch(
    ohlcv: pd.DataFrame,
    swings: list[SwingPoint],
    volume_threshold: float = 1.5,
    follow_through_bars: int = 3,
    max_lookahead: int = 50
) -> tuple[list[BOSEvent], list[CHoCHEvent], str]:
    """Detect Break of Structure (BOS) and Change of Character (CHoCH) — O(n) single-pass.
    
    TEACHING:
    - BOS: Price CLOSES beyond a significant swing level WITH volume.
      This is trend CONTINUATION — the trend is showing strength.
    - CHoCH: BOS + pullback that holds + continuation in NEW direction.
      This is trend REVERSAL — structure has fundamentally shifted.
    
    VOLUME CONFIRMATION IS MANDATORY:
    - Breakout candle volume > 1.5x 20-period average
    - Without volume, it's likely a false break (retail trap)
    
    FOLLOW-THROUGH:
    - Next 3 candles must continue in breakout direction
    - Confirms momentum, not just a spike
    
    RETEST (for CHoCH):
    - Price returns to broken level (now flipped S/R)
    - Holds and continues — confirms the structure shift
    
    ALGORITHM: Single pass through price tracking ACTIVE (unbroken) swing levels.
    When a level is broken with volume + follow-through, it's a BOS.
    The broken level is removed from active set (structure has shifted).
    
    Args:
        ohlcv: DataFrame with OHLCV columns, datetime index
        swings: List of SwingPoint from detect_swings()
        volume_threshold: Volume ratio threshold for confirmation (default 1.5x)
        follow_through_bars: Number of candles for follow-through (default 3)
        max_lookahead: Max bars to look ahead for CHoCH confirmation (default 50)
        
    Returns:
        Tuple of (bos_events, choch_events, current_structure)
    """
    if len(swings) < 2:
        return [], [], "insufficient_data"
    
    close: np.ndarray = ohlcv["Close"].to_numpy()
    high: np.ndarray = ohlcv["High"].to_numpy()
    low: np.ndarray = ohlcv["Low"].to_numpy()
    volume: np.ndarray = ohlcv["Volume"].to_numpy()
    avg_volume: np.ndarray = pd.Series(volume).rolling(20, min_periods=1).mean().to_numpy()
    
    # Build active swing levels (unbroken) - only the MOST RECENT of each type
    # Structure is defined by the last swing high and last swing low
    active_swing_high: SwingPoint | None = None
    active_swing_low: SwingPoint | None = None
    
    for swing in swings:
        if swing.type == "high":
            active_swing_high = swing
        else:
            active_swing_low = swing
    
    bos_events: list[BOSEvent] = []
    choch_events: list[CHoCHEvent] = []
    current_structure = "neutral"
    
    # Track which levels have been broken (to avoid double-counting)
    broken_highs = set()
    broken_lows = set()
    
    # Active swing levels - updated dynamically as we iterate
    # Only swings with index < i are considered "formed" and active
    active_swing_high: SwingPoint | None = None
    active_swing_low: SwingPoint | None = None
    
    # Pre-compute swings by index for quick lookup
    swings_by_index = {s.index: s for s in swings}
    
    # Single pass through price candles
    for i in range(len(close)):
        # Update active swings: any swing at index i becomes active for future candles
        if i in swings_by_index:
            swing = swings_by_index[i]
            if swing.type == "high":
                active_swing_high = swing
            else:
                active_swing_low = swing
        
        current_close = float(close[i])
        current_volume = float(volume[i])
        current_avg_vol = float(avg_volume[i]) if i < len(avg_volume) and not np.isnan(avg_volume[i]) and avg_volume[i] > 0 else 0.0
        
        if current_avg_vol == 0:
            continue
            
        vol_ratio = current_volume / current_avg_vol
        volume_confirmed = vol_ratio >= volume_threshold
        
        # Check bullish BOS: close breaks above active swing HIGH
        if (active_swing_high and
            active_swing_high.index < i and
            current_close > active_swing_high.price and
            active_swing_high.price not in broken_highs and
            volume_confirmed):
            
            # Check follow-through: next N candles continue UP
            ft = True
            for k in range(1, min(follow_through_bars + 1, len(close) - i)):
                if close[i + k] <= close[i + k - 1]:
                    ft = False
                    break
            
            if ft:
                bos = BOSEvent(
                    type="bullish_bos",
                    break_price=float(current_close),
                    break_index=i,
                    break_timestamp=ohlcv.index[i],
                    structure_level=active_swing_high.price,
                    volume_confirmed=True,
                    volume_ratio=round(vol_ratio, 2),
                    follow_through=ft
                )
                bos_events.append(bos)
                broken_highs.add(active_swing_high.price)
                current_structure = "bullish"
                
                # This high is now broken — structure has shifted
                # In a full implementation, we'd find the next unbroken swing high
                # For now, mark broken and don't re-detect on same level
        
        # Check bearish BOS: close breaks below active swing LOW
        elif (active_swing_low and
              active_swing_low.index < i and
              current_close < active_swing_low.price and
              active_swing_low.price not in broken_lows and
              volume_confirmed):
            
            # Check follow-through: next N candles continue DOWN
            ft = True
            for k in range(1, min(follow_through_bars + 1, len(close) - i)):
                if close[i + k] >= close[i + k - 1]:
                    ft = False
                    break
            
            if ft:
                bos = BOSEvent(
                    type="bearish_bos",
                    break_price=float(current_close),
                    break_index=i,
                    break_timestamp=ohlcv.index[i],
                    structure_level=active_swing_low.price,
                    volume_confirmed=True,
                    volume_ratio=round(vol_ratio, 2),
                    follow_through=ft
                )
                bos_events.append(bos)
                broken_lows.add(active_swing_low.price)
                current_structure = "bearish"
    
    # Detect CHoCH: BOS + pullback to broken level + continuation
    for bos in bos_events:
        if bos.type == "bullish_bos":
            # Pullback to broken resistance (now support)
            # Look within max_lookahead bars after BOS
            search_end = min(bos.break_index + max_lookahead, len(close))
            for j in range(bos.break_index + 1, search_end):
                # Price touches near broken level (within 0.5% tolerance)
                if float(low[j]) <= bos.structure_level * 1.005:
                    # Check hold + continuation (3 candles up from pullback low)
                    if j + follow_through_bars < len(close):
                        continuation = all(
                            float(close[k]) > float(close[k - 1])
                            for k in range(j + 1, j + follow_through_bars + 1)
                        )
                        if continuation:
                            pullback_depth = (bos.break_price - float(close[j])) / bos.break_price * 100
                            choch = CHoCHEvent(
                                type="bullish_choch",
                                bos_event=bos,
                                confirmation_price=float(close[j + follow_through_bars]),
                                confirmation_index=j + follow_through_bars,
                                pullback_depth_pct=round(pullback_depth, 2),
                                structure_shift_confirmed=True
                            )
                            choch_events.append(choch)
                            # Mark the BOS as having retest confirmed
                            bos.retest_confirmed = True
                            bos.retest_index = j
                            break

        elif bos.type == "bearish_bos":
            # Pullback to broken support (now resistance)
            search_end = min(bos.break_index + max_lookahead, len(close))
            for j in range(bos.break_index + 1, search_end):
                # Price touches near broken level (within 0.5% tolerance)
                if float(high[j]) >= bos.structure_level * 0.995:
                    # Check hold + continuation (3 candles down from pullback high)
                    if j + follow_through_bars < len(close):
                        continuation = all(
                            float(close[k]) < float(close[k - 1])
                            for k in range(j + 1, j + follow_through_bars + 1)
                        )
                        if continuation:
                            pullback_depth = (float(close[j]) - bos.break_price) / bos.break_price * 100
                            choch = CHoCHEvent(
                                type="bearish_choch",
                                bos_event=bos,
                                confirmation_price=float(close[j + follow_through_bars]),
                                confirmation_index=j + follow_through_bars,
                                pullback_depth_pct=round(pullback_depth, 2),
                                structure_shift_confirmed=True
                            )
                            choch_events.append(choch)
                            bos.retest_confirmed = True
                            bos.retest_index = j
                            break
    
    return bos_events, choch_events, current_structure


def classify_structure_from_bos_choch(
    bos_events: list[BOSEvent],
    choch_events: list[CHoCHEvent],
    current_price: float
) -> tuple[str, dict]:
    """Classify current market structure from BOS/CHoCH events.
    
    TEACHING:
    - Most recent CHoCH determines BIAS (reversal has higher weight)
    - Most recent BOS determines MOMENTUM (continuation)
    - If both exist, CHoCH wins (reversal trumps continuation)
    - Structure labels: "bullish", "bearish", "bullish_choch", "bearish_choch", "neutral"
    """
    details: dict = {
        "bos_count": len(bos_events),
        "choch_count": len(choch_events),
        "last_bos": None,
        "last_choch": None,
    }
    
    if not bos_events and not choch_events:
        return "neutral", details
    
    # Get most recent events
    if bos_events:
        last_bos = bos_events[-1]
        details["last_bos"] = {
            "type": last_bos.type,
            "price": last_bos.break_price,
            "level": last_bos.structure_level,
            "volume_ratio": last_bos.volume_ratio,
            "timestamp": str(last_bos.break_timestamp),
        }
    
    if choch_events:
        last_choch = choch_events[-1]
        details["last_choch"] = {
            "type": last_choch.type,
            "price": last_choch.confirmation_price,
            "pullback_depth_pct": last_choch.pullback_depth_pct,
            "timestamp": str(last_choch.bos_event.break_timestamp),
        }
        # CHoCH overrides BOS — reversal trumps continuation
        return last_choch.type.replace("_choch", ""), details
    
    # No CHoCH, use last BOS
    if bos_events:
        last_bos = bos_events[-1]
        return last_bos.type.replace("_bos", ""), details
    
    return "neutral", details