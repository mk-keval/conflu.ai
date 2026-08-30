"""Validated Breakout Detection Module

This module provides robust breakout detection with multiple confirmation layers
to filter false breakouts — a critical edge for swing/position traders.

Breakout detection is NOT just "price crosses level." A validated breakout requires:
1. Level significance (resistance/support/IB/PDH/PDL/PWH/PWL/BOS)
2. Volume confirmation (breakout candle > 1.5x 20-period average)
3. Follow-through (next 3+ candles continue direction)
4. False breakout rejection (reversal inside range within 5 bars = reject)
5. Retest validation (price returns to broken level, holds, continues)

Confidence Scoring (weights sum to 1.0):
- Volume confirmation: 0.30
- Follow-through: 0.30
- Key level bonus: 0.10
- Retest validation: 0.30

Designed for daily timeframe swing trading (6mo lookback minimum).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal
from enum import Enum

import numpy as np
import pandas as pd


class BreakoutDirection(Enum):
    """Direction of the breakout."""
    LONG = "long"    # Breakout above resistance (bullish)
    SHORT = "short"  # Breakdown below support (bearish)


class BreakoutLevelType(Enum):
    """Type of level that was broken."""
    RESISTANCE = "resistance"           # Swing high cluster resistance
    SUPPORT = "support"                 # Swing low cluster support
    IB_HIGH = "ib_high"                 # Initial Balance high (first 30-60min)
    IB_LOW = "ib_low"                   # Initial Balance low
    PDH = "pdh"                         # Previous Day High
    PDL = "pdl"                         # Previous Day Low
    PWH = "pwh"                         # Previous Week High
    PWL = "pwl"                         # Previous Week Low
    BOS_BULLISH = "bos_bullish"         # Break of Structure - bullish (HH)
    BOS_BEARISH = "bos_bearish"         # Break of Structure - bearish (LL)


class BreakoutStatus(Enum):
    """Validation status of the breakout."""
    VALIDATED = "validated"         # All confirmations passed
    PENDING = "pending"             # Initial break, awaiting follow-through
    FALSE_BREAKOUT = "false_breakout"  # Rejected - reversed inside range
    RETEST_FAILED = "retest_failed"     # Retest occurred but failed to hold
    INSUFFICIENT_DATA = "insufficient_data"  # Not enough bars to evaluate


@dataclass
class BreakoutEvent:
    """
    Represents a validated (or rejected) breakout event.

    This dataclass captures the complete lifecycle of a breakout from initial
    level break through validation or rejection. Each field serves a specific
    analytical purpose for trade decision-making.

    Attributes:
        symbol: Ticker symbol (e.g., "AAPL")
        timestamp: Bar timestamp when breakout occurred (breakout candle close)
        direction: LONG (resistance break) or SHORT (support break)
        level_type: Type of level that was broken
        level_price: Price of the broken level
        breakout_price: Close price of the breakout candle
        breakout_volume: Volume of the breakout candle
        avg_volume_20: 20-period average volume at breakout time
        volume_ratio: breakout_volume / avg_volume_20 (target > 1.5)
        follow_through_bars: Number of consecutive bars continuing direction (target >= 3)
        max_favorable_excursion: Max % move in breakout direction from breakout close
        max_adverse_excursion: Max % move against breakout from breakout close
        retested: Whether price returned to broken level (now flipped S/R)
        retest_price: Price at retest (if occurred)
        retest_held: Whether price held at retest and continued
        bars_to_retest: Bars from breakout to retest (if occurred)
        status: Final validation status
        confidence: Composite score 0.0-1.0 (weights: vol=0.3, follow=0.3, level=0.1, retest=0.3)
        key_level_bonus: Whether level is a "key" level (PDH/PDL/PWH/PWL/BOS = +0.1)
        notes: Human-readable findings for debugging/analysis
    """
    symbol: str
    timestamp: pd.Timestamp
    direction: BreakoutDirection
    level_type: BreakoutLevelType
    level_price: float
    breakout_price: float
    breakout_volume: float
    avg_volume_20: float
    volume_ratio: float
    follow_through_bars: int
    max_favorable_excursion: float
    max_adverse_excursion: float
    retested: bool
    retest_price: float | None
    retest_held: bool | None
    bars_to_retest: int | None
    status: BreakoutStatus
    confidence: float
    key_level_bonus: bool
    notes: list[str] = field(default_factory=list)


# ── Configuration Constants ──

# Volume confirmation threshold
VOLUME_CONFIRMATION_THRESHOLD = 1.5  # breakout candle volume > 1.5x 20-period avg

# Follow-through requirement
MIN_FOLLOW_THROUGH_BARS = 3  # Need 3+ consecutive bars in breakout direction

# False breakout rejection window
FALSE_BREAKOUT_WINDOW = 5  # Reversal inside range within 5 bars = false breakout

# Retest tolerance (price returns to broken level within this %)
RETEST_TOLERANCE_PCT = 0.5  # 0.5% tolerance around broken level

# Max bars to wait for retest
MAX_BARS_TO_RETEST = 20  # Retest must occur within 20 bars

# Confidence scoring weights
WEIGHT_VOLUME = 0.30
WEIGHT_FOLLOW_THROUGH = 0.30
WEIGHT_KEY_LEVEL = 0.10
WEIGHT_RETEST = 0.30

# Key level types that get bonus
KEY_LEVEL_TYPES = {
    BreakoutLevelType.PDH,
    BreakoutLevelType.PDL,
    BreakoutLevelType.PWH,
    BreakoutLevelType.PWL,
    BreakoutLevelType.BOS_BULLISH,
    BreakoutLevelType.BOS_BEARISH,
}


# ── Core Detection Functions ──

def _calculate_atr(ohlcv: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Average True Range."""
    high = ohlcv["High"]
    low = ohlcv["Low"]
    close = ohlcv["Close"]
    
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    return atr


def _detect_swings(ohlcv: pd.DataFrame, lookback: int = 5) -> dict[str, list[dict]]:
    """
    Detect swing highs and lows using fractal pattern (5-bar default).
    
    Swing high: high[i] > high[i-1..i-2] AND high[i] > high[i+1..i+2]
    Swing low: low[i] < low[i-1..i-2] AND low[i] < low[i+1..i+2]
    
    Returns dict with 'highs' and 'lows' as lists of {price, index, timestamp}
    """
    highs: np.ndarray = ohlcv["High"].to_numpy(dtype=float)
    lows: np.ndarray = ohlcv["Low"].to_numpy(dtype=float)
    timestamps = ohlcv.index
    
    swing_highs: list[dict] = []
    swing_lows: list[dict] = []
    
    for i in range(lookback, len(ohlcv) - lookback):
        # Swing high
        is_swing_high = True
        for j in range(1, lookback + 1):
            if highs[i] <= highs[i - j] or highs[i] <= highs[i + j]:
                is_swing_high = False
                break
        
        # Swing low
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


def _get_key_levels(
    ohlcv: pd.DataFrame,
    swings: dict[str, list[dict]],
    lookback_days: int = 20
) -> dict[BreakoutLevelType, float]:
    """
    Extract all key reference levels from price data.
    
    Returns dict mapping BreakoutLevelType to price level.
    Only returns levels that exist in the data.
    """
    levels: dict[BreakoutLevelType, float] = {}
    close: float = float(ohlcv["Close"].iloc[-1])
    high_series: pd.Series = ohlcv["High"]
    low_series: pd.Series = ohlcv["Low"]
    
    # 1. Swing-based Resistance/Support (from clustering)
    high_prices = [h["price"] for h in swings.get("highs", [])]
    low_prices = [low_item["price"] for low_item in swings.get("lows", [])]
    
    if high_prices:
        # Most recent significant resistance (closest above current price)
        relevant_highs = [h for h in high_prices if h > close]
        if relevant_highs:
            levels[BreakoutLevelType.RESISTANCE] = min(relevant_highs)
    
    if low_prices:
        # Most recent significant support (closest below current price)
        relevant_lows = [level for level in low_prices if level < close]
        if relevant_lows:
            levels[BreakoutLevelType.SUPPORT] = max(relevant_lows)
    
    # 2. Previous Day High/Low (PDH/PDL)
    if len(ohlcv) >= 2:
        prev_day_high = float(high_series.iloc[-2])
        prev_day_low = float(low_series.iloc[-2])
        levels[BreakoutLevelType.PDH] = prev_day_high
        levels[BreakoutLevelType.PDL] = prev_day_low
    
    # 3. Previous Week High/Low (PWH/PWL) - need weekly data or 5 daily bars
    if len(ohlcv) >= 5:
        week_high = float(high_series.iloc[-5:].max())
        week_low = float(low_series.iloc[-5:].min())
        levels[BreakoutLevelType.PWH] = week_high
        levels[BreakoutLevelType.PWL] = week_low
    
    # 4. Initial Balance (first 30-60 min) - approximated from daily as first hour range
    # For daily data, we approximate IB as the first day's range in lookback
    if len(ohlcv) >= lookback_days:
        ib_high = float(high_series.iloc[-lookback_days])
        ib_low = float(low_series.iloc[-lookback_days])
        levels[BreakoutLevelType.IB_HIGH] = ib_high
        levels[BreakoutLevelType.IB_LOW] = ib_low
    
    # 5. Break of Structure (BOS) - detect from swings
    swing_highs = swings.get("highs", [])
    swing_lows = swings.get("lows", [])
    
    if len(swing_highs) >= 2:
        # Bullish BOS: price breaks above prior swing high
        last_high = swing_highs[-1]["price"]
        prev_high = swing_highs[-2]["price"]
        if close > prev_high:
            levels[BreakoutLevelType.BOS_BULLISH] = prev_high
    
    if len(swing_lows) >= 2:
        # Bearish BOS: price breaks below prior swing low
        last_low = swing_lows[-1]["price"]
        prev_low = swing_lows[-2]["price"]
        if close < prev_low:
            levels[BreakoutLevelType.BOS_BEARISH] = prev_low
    
    return levels


def _check_volume_confirmation(
    ohlcv: pd.DataFrame,
    breakout_idx: int,
    lookback: int = 20
) -> tuple[float, float, float, bool]:
    """
    Check volume confirmation for breakout candle.
    
    Returns: (breakout_volume, avg_volume_20, volume_ratio, confirmed)
    """
    if breakout_idx < lookback:
        # Not enough history for 20-period average
        vol = float(ohlcv["Volume"].iloc[breakout_idx])
        return vol, vol, 1.0, False
    
    breakout_volume = float(ohlcv["Volume"].iloc[breakout_idx])
    avg_volume_20 = float(ohlcv["Volume"].iloc[breakout_idx - lookback:breakout_idx].mean())
    
    if avg_volume_20 == 0:
        return breakout_volume, avg_volume_20, 0.0, False
    
    volume_ratio = breakout_volume / avg_volume_20
    confirmed = volume_ratio >= VOLUME_CONFIRMATION_THRESHOLD
    
    return breakout_volume, avg_volume_20, volume_ratio, confirmed


def _check_follow_through(
    ohlcv: pd.DataFrame,
    breakout_idx: int,
    direction: BreakoutDirection,
    min_bars: int = MIN_FOLLOW_THROUGH_BARS
) -> tuple[int, float, float]:
    """
    Check follow-through: count consecutive bars continuing breakout direction.
    
    Returns: (follow_through_bars, max_favorable_excursion, max_adverse_excursion)
    """
    if breakout_idx >= len(ohlcv) - 1:
        return 0, 0.0, 0.0
    
    breakout_close = float(ohlcv["Close"].iloc[breakout_idx])
    follow_through = 0
    max_fav = 0.0
    max_adv = 0.0
    
    for i in range(breakout_idx + 1, len(ohlcv)):
        close = float(ohlcv["Close"].iloc[i])
        pct_change = (close - breakout_close) / breakout_close * 100
        
        if direction == BreakoutDirection.LONG:
            if close > breakout_close:
                follow_through += 1
                max_fav = max(max_fav, pct_change)
            else:
                max_adv = min(max_adv, pct_change)  # negative
                break  # Follow-through broken
        else:  # SHORT
            if close < breakout_close:
                follow_through += 1
                max_fav = max(max_fav, -pct_change)  # positive for favorable
            else:
                max_adv = max(max_adv, pct_change)  # positive adverse
                break
        
        # Cap at reasonable lookforward
        if i - breakout_idx >= 20:
            break
    
    return follow_through, max_fav, abs(max_adv)


def _check_false_breakout(
    ohlcv: pd.DataFrame,
    breakout_idx: int,
    direction: BreakoutDirection,
    level_price: float,
    window: int = FALSE_BREAKOUT_WINDOW
) -> bool:
    """
    Check if breakout is a false breakout (quick reversal back inside range).
    
    False breakout = price reverses back inside the level within `window` bars.
    """
    if breakout_idx >= len(ohlcv) - 1:
        return False
    
    breakout_close = float(ohlcv["Close"].iloc[breakout_idx])
    
    for i in range(breakout_idx + 1, min(breakout_idx + window + 1, len(ohlcv))):
        close = float(ohlcv["Close"].iloc[i])
        
        if direction == BreakoutDirection.LONG:
            # False if price closes back below the broken resistance
            if close < level_price:
                return True
        else:
            # False if price closes back above the broken support
            if close > level_price:
                return True
    
    return False


def _check_retest(
    ohlcv: pd.DataFrame,
    breakout_idx: int,
    direction: BreakoutDirection,
    level_price: float,
    tolerance_pct: float = RETEST_TOLERANCE_PCT,
    max_bars: int = MAX_BARS_TO_RETEST
) -> tuple[bool, float | None, bool | None, int | None]:
    """
    Check for retest of broken level (now flipped S/R).
    
    Retest = price returns to broken level within tolerance, holds, continues.
    
    Returns: (retested, retest_price, retest_held, bars_to_retest)
    """
    if breakout_idx >= len(ohlcv) - 1:
        return False, None, None, None
    
    breakout_close = float(ohlcv["Close"].iloc[breakout_idx])
    tolerance = level_price * tolerance_pct / 100
    
    for i in range(breakout_idx + 1, min(breakout_idx + max_bars + 1, len(ohlcv))):
        low = float(ohlcv["Low"].iloc[i])
        high = float(ohlcv["High"].iloc[i])
        close = float(ohlcv["Close"].iloc[i])
        
        if direction == BreakoutDirection.LONG:
            # Retest: price comes down to broken resistance (now support)
            if low <= level_price + tolerance and low >= level_price - tolerance:
                retest_price = close
                # Check if held: close above level after retest
                retest_held = close > level_price
                bars_to_retest = i - breakout_idx
                return True, retest_price, retest_held, bars_to_retest
        else:
            # Retest: price comes up to broken support (now resistance)
            if high >= level_price - tolerance and high <= level_price + tolerance:
                retest_price = close
                # Check if held: close below level after retest
                retest_held = close < level_price
                bars_to_retest = i - breakout_idx
                return True, retest_price, retest_held, bars_to_retest
    
    return False, None, None, None


def _calculate_confidence(
    volume_confirmed: bool,
    volume_ratio: float,
    follow_through_bars: int,
    key_level_bonus: bool,
    retested: bool,
    retest_held: bool | None
) -> float:
    """
    Calculate composite confidence score (0.0 - 1.0).
    
    Weights:
    - Volume: 0.30 (scaled by volume_ratio, capped at 2.0x)
    - Follow-through: 0.30 (scaled by bars, capped at 5 bars)
    - Key level bonus: 0.10 (binary)
    - Retest: 0.30 (only if retested AND held)
    """
    # Volume score: ratio / 2.0, capped at 1.0
    vol_score = min(volume_ratio / 2.0, 1.0) if volume_confirmed else 0.0
    
    # Follow-through score: bars / 5, capped at 1.0
    follow_score = min(follow_through_bars / 5.0, 1.0)
    
    # Key level bonus
    key_score = 1.0 if key_level_bonus else 0.0
    
    # Retest score: only counts if retested AND held
    retest_score = 1.0 if (retested and retest_held) else 0.0
    
    confidence = (
        WEIGHT_VOLUME * vol_score +
        WEIGHT_FOLLOW_THROUGH * follow_score +
        WEIGHT_KEY_LEVEL * key_score +
        WEIGHT_RETEST * retest_score
    )
    
    return round(confidence, 3)


def _determine_status(
    volume_confirmed: bool,
    follow_through_bars: int,
    is_false_breakout: bool,
    retested: bool,
    retest_held: bool | None
) -> BreakoutStatus:
    """Determine final validation status."""
    if is_false_breakout:
        return BreakoutStatus.FALSE_BREAKOUT
    
    if retested and retest_held is False:
        return BreakoutStatus.RETEST_FAILED
    
    if volume_confirmed and follow_through_bars >= MIN_FOLLOW_THROUGH_BARS:
        if retested and retest_held:
            return BreakoutStatus.VALIDATED
        elif not retested:
            return BreakoutStatus.PENDING  # Validated but no retest yet
        else:
            return BreakoutStatus.VALIDATED  # Retested and held
    
    if not volume_confirmed or follow_through_bars < MIN_FOLLOW_THROUGH_BARS:
        return BreakoutStatus.PENDING
    
    return BreakoutStatus.INSUFFICIENT_DATA


# ── Public API ──

def detect_validated_breakouts(
    ohlcv: pd.DataFrame,
    symbol: str = "UNKNOWN",
    volume_threshold: float = VOLUME_CONFIRMATION_THRESHOLD,
    min_follow_through: int = MIN_FOLLOW_THROUGH_BARS,
    false_breakout_window: int = FALSE_BREAKOUT_WINDOW,
    retest_tolerance_pct: float = RETEST_TOLERANCE_PCT,
    max_bars_to_retest: int = MAX_BARS_TO_RETEST,
    lookback_swings: int = 5,
    lookback_levels: int = 20
) -> list[BreakoutEvent]:
    """
    Detect and validate breakouts of key levels in OHLCV data.
    
    This is the main entry point for breakout detection. It scans the provided
    OHLCV data for breakouts of all key levels (resistance, support, IB high/low,
    PDH/PDL, PWH/PWL, BOS levels) and applies a multi-layer validation framework.
    
    Validation Pipeline:
    1. Identify all key reference levels from price structure
    2. For each level, detect if/when price broke it (on close)
    3. Apply volume confirmation (> threshold x 20-period avg)
    4. Check follow-through (N+ consecutive bars in direction)
    5. Check for false breakout (reversal inside within window)
    6. Check for retest validation (return to flipped level, hold, continue)
    7. Calculate composite confidence score
    
    Args:
        ohlcv: DataFrame with columns ['Open', 'High', 'Low', 'Close', 'Volume'],
               indexed by datetime. Minimum 50 bars recommended.
        symbol: Ticker symbol for labeling events
        volume_threshold: Volume ratio required for confirmation (default 1.5x)
        min_follow_through: Minimum consecutive bars for follow-through (default 3)
        false_breakout_window: Bars to check for false breakout rejection (default 5)
        retest_tolerance_pct: % tolerance around level for retest (default 0.5%)
        max_bars_to_retest: Max bars to wait for retest (default 20)
        lookback_swings: Fractal lookback for swing detection (default 5)
        lookback_levels: Lookback for IB/PDH/PDL/PWH/PWL levels (default 20)
    
    Returns:
        List of BreakoutEvent objects, sorted by timestamp (newest first).
        Each event contains full validation details and confidence score.
    
    Example:
        >>> events = detect_validated_breakouts(daily_ohlcv, "AAPL")
        >>> for e in events:
        ...     if e.status == BreakoutStatus.VALIDATED and e.confidence > 0.7:
        ...         print(f"HIGH CONFIDENCE: {e.direction.value} break of {e.level_type.value} at {e.level_price:.2f}")
    
    Teaching Notes:
        - Volume confirmation is the PRIMARY filter: most false breakouts lack volume
        - Follow-through prevents "one-bar wonder" breakouts that immediately reverse
        - False breakout check catches "fakeouts" — price spikes level but closes back inside
        - Retest validation is the GOLD STANDARD: a successful retest of flipped S/R
          dramatically increases win rate (this is where "breakout traders" make money)
        - Confidence score combines all factors — use > 0.7 for high conviction
        - Key levels (PDH/PDL/PWH/PWL/BOS) get a bonus because they're watched by
          more participants = more reliable when broken
    """
    # Override module-level constants if provided
    global VOLUME_CONFIRMATION_THRESHOLD, MIN_FOLLOW_THROUGH_BARS
    global FALSE_BREAKOUT_WINDOW, RETEST_TOLERANCE_PCT, MAX_BARS_TO_RETEST
    
    VOLUME_CONFIRMATION_THRESHOLD = volume_threshold
    MIN_FOLLOW_THROUGH_BARS = min_follow_through
    FALSE_BREAKOUT_WINDOW = false_breakout_window
    RETEST_TOLERANCE_PCT = retest_tolerance_pct
    MAX_BARS_TO_RETEST = max_bars_to_retest
    
    if ohlcv is None or len(ohlcv) < 30:
        return []
    
    # Ensure we have required columns
    required_cols = ["Open", "High", "Low", "Close", "Volume"]
    if not all(col in ohlcv.columns for col in required_cols):
        raise ValueError(f"OHLCV must contain columns: {required_cols}")
    
    # Detect swings for structure-based levels
    swings = _detect_swings(ohlcv, lookback=lookback_swings)
    
    # Get all key levels
    key_levels = _get_key_levels(ohlcv, swings, lookback_days=lookback_levels)
    
    if not key_levels:
        return []
    
    events: list[BreakoutEvent] = []
    
    # Scan each bar for breakouts (start from lookback_levels to have volume avg)
    start_idx = max(lookback_levels, lookback_swings * 2)
    
    for level_type, level_price in key_levels.items():
        # Determine breakout direction based on level type
        if level_type in {
            BreakoutLevelType.RESISTANCE,
            BreakoutLevelType.IB_HIGH,
            BreakoutLevelType.PDH,
            BreakoutLevelType.PWH,
            BreakoutLevelType.BOS_BULLISH,
        }:
            direction = BreakoutDirection.LONG
        else:
            direction = BreakoutDirection.SHORT
        
        # Scan for breakout: close crosses level
        for i in range(start_idx, len(ohlcv)):
            close = float(ohlcv["Close"].iloc[i])
            prev_close = float(ohlcv["Close"].iloc[i - 1])
            
            # Check for breakout on this bar
            broke = False
            if direction == BreakoutDirection.LONG:
                # Long breakout: close above level, previous close at or below
                if close > level_price and prev_close <= level_price:
                    broke = True
            else:
                # Short breakdown: close below level, previous close at or above
                if close < level_price and prev_close >= level_price:
                    broke = True
            
            if not broke:
                continue
            
            # We have a breakout candidate at index i
            # Run validation pipeline
            
            # 1. Volume confirmation
            breakout_vol, avg_vol_20, vol_ratio, vol_confirmed = _check_volume_confirmation(
                ohlcv, i, lookback=20
            )
            
            # 2. Follow-through
            follow_bars, max_fav, max_adv = _check_follow_through(
                ohlcv, i, direction, min_follow_through
            )
            
            # 3. False breakout check
            is_false = _check_false_breakout(
                ohlcv, i, direction, level_price, false_breakout_window
            )
            
            # 4. Retest check (only if not false breakout)
            retested = False
            retest_price = None
            retest_held = None
            bars_to_retest = None
            
            if not is_false:
                retested, retest_price, retest_held, bars_to_retest = _check_retest(
                    ohlcv, i, direction, level_price, retest_tolerance_pct, max_bars_to_retest
                )
            
            # 5. Key level bonus
            key_bonus = level_type in KEY_LEVEL_TYPES
            
            # 6. Confidence score
            confidence = _calculate_confidence(
                vol_confirmed, vol_ratio, follow_bars, key_bonus, retested, retest_held
            )
            
            # 7. Determine status
            status = _determine_status(
                vol_confirmed, follow_bars, is_false, retested, retest_held
            )
            
            # Build notes
            notes = []
            notes.append(f"Broke {level_type.value} at {level_price:.2f} (close: {close:.2f})")
            if vol_confirmed:
                notes.append(f"✅ Volume confirmed: {vol_ratio:.1f}x avg")
            else:
                notes.append(f"⚠️ Low volume: {vol_ratio:.1f}x avg (need >{volume_threshold}x)")
            notes.append(f"Follow-through: {follow_bars} bars (need >={min_follow_through})")
            if is_false:
                notes.append(f"❌ FALSE BREAKOUT: Reversed inside within {false_breakout_window} bars")
            if retested:
                if retest_held:
                    notes.append(f"✅ Retest held at {retest_price:.2f} ({bars_to_retest} bars later)")
                else:
                    notes.append(f"❌ Retest failed at {retest_price:.2f}")
            else:
                notes.append("⏳ No retest yet")
            if key_bonus:
                notes.append(f"🎯 Key level bonus ({level_type.value})")
            notes.append(f"Confidence: {confidence:.2f}")
            
            event = BreakoutEvent(
                symbol=symbol,
                timestamp=ohlcv.index[i],
                direction=direction,
                level_type=level_type,
                level_price=level_price,
                breakout_price=close,
                breakout_volume=breakout_vol,
                avg_volume_20=avg_vol_20,
                volume_ratio=round(vol_ratio, 2),
                follow_through_bars=follow_bars,
                max_favorable_excursion=round(max_fav, 2),
                max_adverse_excursion=round(max_adv, 2),
                retested=retested,
                retest_price=round(retest_price, 2) if retest_price else None,
                retest_held=retest_held,
                bars_to_retest=bars_to_retest,
                status=status,
                confidence=confidence,
                key_level_bonus=key_bonus,
                notes=notes,
            )
            
            events.append(event)
            
            # Skip ahead to avoid duplicate detection on same level
            # (breakout confirmed or rejected, move to next potential breakout)
            break
    
    # Sort by timestamp descending (newest first)
    events.sort(key=lambda e: e.timestamp, reverse=True)
    
    return events


def filter_validated_breakouts(
    events: list[BreakoutEvent],
    min_confidence: float = 0.5,
    statuses: list[BreakoutStatus] | None = None
) -> list[BreakoutEvent]:
    """
    Filter breakout events by confidence and status.
    
    Args:
        events: List of BreakoutEvent from detect_validated_breakouts()
        min_confidence: Minimum confidence score (0.0-1.0)
        statuses: Allowed statuses (default: VALIDATED only)
    
    Returns:
        Filtered list of BreakoutEvent
    """
    if statuses is None:
        statuses = [BreakoutStatus.VALIDATED]
    
    return [
        e for e in events
        if e.confidence >= min_confidence and e.status in statuses
    ]


def get_latest_breakout(
    ohlcv: pd.DataFrame,
    symbol: str = "UNKNOWN",
    **kwargs
) -> BreakoutEvent | None:
    """
    Get the most recent validated breakout (convenience function).
    
    Returns the newest BreakoutEvent with status VALIDATED, or None if none exist.
    """
    events = detect_validated_breakouts(ohlcv, symbol, **kwargs)
    validated = filter_validated_breakouts(events, min_confidence=0.0, statuses=[BreakoutStatus.VALIDATED])
    return validated[0] if validated else None


# ── Example Usage & Testing ──

if __name__ == "__main__":
    # Generate sample data for demonstration
    import yfinance as yf
    
    print("=" * 60)
    print("VALIDATED BREAKOUT DETECTION - DEMO")
    print("=" * 60)
    
    # Fetch real data
    ticker = yf.Ticker("AAPL")
    hist = ticker.history(period="6mo", interval="1d")
    
    if hist is not None and len(hist) > 50:
        print(f"\nAnalyzing {len(hist)} bars of AAPL daily data...")
        print(f"Date range: {hist.index[0].date()} to {hist.index[-1].date()}")
        print(f"Current price: ${hist['Close'].iloc[-1]:.2f}")
        
        # Detect breakouts
        events = detect_validated_breakouts(hist, "AAPL")
        
        print(f"\nDetected {len(events)} breakout events:")
        print("-" * 60)
        
        for event in events[:10]:  # Show top 10
            status_icon = {
                BreakoutStatus.VALIDATED: "✅",
                BreakoutStatus.PENDING: "⏳",
                BreakoutStatus.FALSE_BREAKOUT: "❌",
                BreakoutStatus.RETEST_FAILED: "🔴",
                BreakoutStatus.INSUFFICIENT_DATA: "❓",
            }.get(event.status, "?")
            
            dir_icon = "📈" if event.direction == BreakoutDirection.LONG else "📉"
            
            print(f"\n{status_icon} {dir_icon} {event.timestamp.date()} | "
                  f"{event.direction.value.upper()} break of {event.level_type.value}")
            print(f"   Level: ${event.level_price:.2f} | Breakout: ${event.breakout_price:.2f}")
            print(f"   Vol: {event.volume_ratio:.1f}x | Follow: {event.follow_through_bars} bars | "
                  f"MFE: {event.max_favorable_excursion:.1f}% | MAE: {event.max_adverse_excursion:.1f}%")
            print(f"   Retest: {'Yes' if event.retested else 'No'} "
                  f"({'Held' if event.retest_held else 'Failed' if event.retested else 'N/A'})")
            print(f"   Status: {event.status.value} | Confidence: {event.confidence:.2f}")
            for note in event.notes:
                print(f"   - {note}")
        
        # Show validated only
        validated = filter_validated_breakouts(events, min_confidence=0.6)
        print(f"\n{'='*60}")
        print(f"VALIDATED (confidence >= 0.6): {len(validated)} events")
        for e in validated:
            print(f"  {e.timestamp.date()} | {e.direction.value} {e.level_type.value} @ ${e.level_price:.2f} | "
                  f"Conf: {e.confidence:.2f}")
    else:
        print("Could not fetch data for demo")