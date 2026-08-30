# Phase 1: Elite Chart Reading Implementation Plan (P0)

**Objective:** Transform conflu.ai from retail indicator stack → institutional-grade chart reading  
**Timeline:** 4-6 weeks  
**Branch:** feat/swing-parity-upgrade → feat/phase1-chart-reading  

---

## Overview: What We're Building & Why It Matters

| Feature | What It Is | Why Elite Traders Use It | Teaching Goal |
|---------|------------|--------------------------|---------------|
| **BOS/CHoCH** | Break of Structure / Change of Character | Identifies trend continuation vs reversal with precision | "Structure tells you WHERE; BOS/CHoCH tells you WHEN" |
| **Professional TPO** | Time-Price Opportunity (30-min periods) | Real volume profile — not daily-bar approximation | "Volume at price = institutional footprint" |
| **Order Blocks (OB)** | Last opposite candle before impulsive move | Institutional entry zones (where smart money entered) | "OB = footprint of big money" |
| **Fair Value Gaps (FVG)** | 3-candle price imbalances | Market MUST fill gaps — high-probability entries | "Nature abhors a vacuum — price returns to fill" |
| **Breaker Blocks** | Failed OB that flips bias | Confirmed structure shift — high conviction | "Broken structure becomes new structure" |
| **Liquidity Mapping** | Buy/sell-side stops, equal highs/lows | Predicts stop hunts, inducement, target zones | "Liquidity is the fuel for moves" |
| **Validated Breakouts** | Volume + follow-through + retest confirmation | Filters false breakouts (retail trap) | "Breakout without volume = trap" |

---

## 1. BOS/CHoCH Detection (`technical/structure.py`)

### Algorithm Specification

```python
# technical/structure.py (NEW FILE)

from dataclasses import dataclass
from typing import Literal
import numpy as np
import pandas as pd

@dataclass
class SwingPoint:
    price: float
    index: int
    timestamp: pd.Timestamp
    type: Literal["high", "low"]
    strength: int  # Number of bars on each side (fractal strength)

@dataclass
class BOSEvent:
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
    type: Literal["bullish_choch", "bearish_choch"]
    bos_event: BOSEvent
    confirmation_price: float
    confirmation_index: int
    pullback_depth_pct: float  # How deep the pullback was
    structure_shift_confirmed: bool

def detect_swings(ohlcv: pd.DataFrame, lookback: int = 5) -> list[SwingPoint]:
    """
    Detect swing highs/lows using fractal pattern.
    
    TEACHING: A swing high is a candle higher than `lookback` candles
    on BOTH sides. Same for swing low. This is market structure —
    the footprints of supply/demand.
    
    Stronger swings (higher lookback) = more significant levels.
    """
    highs = ohlcv["High"].values
    lows = ohlcv["Low"].values
    timestamps = ohlcv.index
    
    swings = []
    
    for i in range(lookback, len(ohlcv) - lookback):
        # Swing high
        is_swing_high = all(highs[i] > highs[i-j] and highs[i] > highs[i+j] 
                           for j in range(1, lookback+1))
        
        # Swing low
        is_swing_low = all(lows[i] < lows[i-j] and lows[i] < lows[i+j] 
                          for j in range(1, lookback+1))
        
        if is_swing_high:
            swings.append(SwingPoint(
                price=highs[i], index=i, timestamp=timestamps[i],
                type="high", strength=lookback
            ))
        if is_swing_low:
            swings.append(SwingPoint(
                price=lows[i], index=i, timestamp=timestamps[i],
                type="low", strength=lookback
            ))
    
    return swings


def detect_bos_choch(
    ohlcv: pd.DataFrame,
    swings: list[SwingPoint],
    volume_threshold: float = 1.5,
    follow_through_bars: int = 3,
    max_lookahead: int = 50
) -> tuple[list[BOSEvent], list[CHoCHEvent], str]:
    """
    Detect Break of Structure (BOS) and Change of Character (CHoCH) — O(n) single-pass.
    
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
    """
    if len(swings) < 2:
        return [], [], "insufficient_data"
    
    close = ohlcv["Close"].values
    high = ohlcv["High"].values
    low = ohlcv["Low"].values
    volume = ohlcv["Volume"].values
    avg_volume = pd.Series(volume).rolling(20).mean().values
    
    # Build active swing levels (unbroken) - only the MOST RECENT of each type
    # Structure is defined by the last swing high and last swing low
    active_swing_high: SwingPoint | None = None
    active_swing_low: SwingPoint | None = None
    
    for swing in swings:
        if swing.type == "high":
            active_swing_high = swing
        else:
            active_swing_low = swing
    
    if not active_swing_high or not active_swing_low:
        return [], [], "insufficient_structure"
    
    bos_events = []
    choch_events = []
    current_structure = "neutral"
    
    # Track which levels have been broken (to avoid double-counting)
    broken_highs = set()
    broken_lows = set()
    
    # Single pass through price candles
    for i in range(len(close)):
        current_close = close[i]
        current_volume = volume[i]
        current_avg_vol = avg_volume[i] if i < len(avg_volume) and not pd.isna(avg_volume[i]) and avg_volume[i] > 0 else 0
        
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
            
            # Check follow-through
            ft = True
            for k in range(1, min(follow_through_bars + 1, len(close) - i)):
                if close[i + k] <= close[i + k - 1]:
                    ft = False
                    break
            
            if ft:
                bos = BOSEvent(
                    type="bullish_bos",
                    break_price=current_close,
                    break_index=i,
                    break_timestamp=ohlcv.index[i],
                    structure_level=active_swing_high.price,
                    volume_confirmed=True,
                    volume_ratio=vol_ratio,
                    follow_through=ft
                )
                bos_events.append(bos)
                broken_highs.add(active_swing_high.price)
                current_structure = "bullish"
                
                # This high is now broken — find next swing high as new active
                # (In practice, swings list is chronological; we'd need next swing)
                # For now, mark broken and don't re-detect
        
        # Check bearish BOS: close breaks below active swing LOW
        elif (active_swing_low and 
              active_swing_low.index < i and 
              current_close < active_swing_low.price and
              active_swing_low.price not in broken_lows and
              volume_confirmed):
            
            ft = True
            for k in range(1, min(follow_through_bars + 1, len(close) - i)):
                if close[i + k] >= close[i + k - 1]:
                    ft = False
                    break
            
            if ft:
                bos = BOSEvent(
                    type="bearish_bos",
                    break_price=current_close,
                    break_index=i,
                    break_timestamp=ohlcv.index[i],
                    structure_level=active_swing_low.price,
                    volume_confirmed=True,
                    volume_ratio=vol_ratio,
                    follow_through=ft
                )
                bos_events.append(bos)
                broken_lows.add(active_swing_low.price)
                current_structure = "bearish"
    
    # Detect CHoCH: BOS + pullback to broken level + continuation
    for bos in bos_events:
        if bos.type == "bullish_bos":
            # Pullback to broken resistance (now support)
            for j in range(bos.break_index + 1, min(bos.break_index + 30, len(close))):
                if low[j] <= bos.structure_level * 1.005:  # Near broken level
                    # Check hold + continuation (3 candles up)
                    if j + 3 < len(close):
                        if all(close[k] > close[k-1] for k in range(j+1, j+4)):
                            pullback_depth = (bos.break_price - close[j]) / bos.break_price * 100
                            choch = CHoCHEvent(
                                type="bullish_choch",
                                bos_event=bos,
                                confirmation_price=close[j+3],
                                confirmation_index=j+3,
                                pullback_depth_pct=pullback_depth,
                                structure_shift_confirmed=True
                            )
                            choch_events.append(choch)
                            break
        
        elif bos.type == "bearish_bos":
            # Pullback to broken support (now resistance)
            for j in range(bos.break_index + 1, min(bos.break_index + 30, len(close))):
                if high[j] >= bos.structure_level * 0.995:
                    if j + 3 < len(close):
                        if all(close[k] < close[k-1] for k in range(j+1, j+4)):
                            pullback_depth = (close[j] - bos.break_price) / bos.break_price * 100
                            choch = CHoCHEvent(
                                type="bearish_choch",
                                bos_event=bos,
                                confirmation_price=close[j+3],
                                confirmation_index=j+3,
                                pullback_depth_pct=pullback_depth,
                                structure_shift_confirmed=True
                            )
                            choch_events.append(choch)
                            break
    
    return bos_events, choch_events, current_structure
```

### Integration Points

| File | Change |
|------|--------|
| `technical.py` | Import `detect_bos_choch`, call in `_analyze_timeframe()` after swing detection |
| `models.py` | Add `BOSEvent`, `CHoCHEvent` to `TechnicalAnalysis` model |
| `narration.py` | Add `_why_this` entries for BOS/CHoCH detection |
| `synthesis.py` | Use BOS/CHoCH for entry timing and conviction |

### Teaching Content for Education System

```json
{
  "metric": "bos_bullish",
  "label": "Bullish Break of Structure",
  "lesson": "Price closed above a significant swing high WITH volume. This confirms buyers are in control and the uptrend is continuing. The broken resistance often becomes new support.",
  "deep_dive": "A valid BOS requires: (1) Clear swing high structure, (2) Candle close above it, (3) Volume > 1.5x average, (4) 3-candle follow-through. Without volume, it's a trap.",
  "related": ["choch_bullish", "order_block", "pullback_quality"]
}
```

---

## 2. Professional TPO Volume Profile (`technical/volume_profile.py`)

### Algorithm Specification

```python
# technical/volume_profile.py (NEW FILE)

from dataclasses import dataclass
from typing import Literal
import numpy as np
import pandas as pd

@dataclass
class TPOPeriod:
    """Single 30-minute TPO period"""
    period_letter: str  # A, B, C... (13 periods in RTH)
    timestamp: pd.Timestamp
    high: float
    low: float
    close: float
    volume: float
    tpo_price_levels: list[float]  # Prices where TPOs printed

@dataclass
class DailyTPOProfile:
    """One day's developing TPO profile"""
    date: pd.Timestamp
    periods: list[TPOPeriod]
    ib_high: float | None      # Initial Balance high (periods A-B)
    ib_low: float | None       # Initial Balance low
    ib_mid: float | None       # IB midpoint
    range_extension_up: bool
    range_extension_down: bool
    poc: float                 # Point of Control (most TPOs)
    vah: float                 # Value Area High (70% TPOs)
    val: float                 # Value Area Low
    single_prints: list[float] # Prices with single TPO (rejection)
    tail_excess: list[float]   # Single prints at extremes

@dataclass
class CompositeTPOProfile:
    """Multi-day composite profile for context"""
    profiles: list[DailyTPOProfile]
    composite_poc: float
    composite_vah: float
    composite_val: float
    poc_migration: Literal["up", "down", "stable"]
    developing_poc: float      # Current day's POC

def compute_professional_tpo(
    ohlcv_30m: pd.DataFrame,
    lookback_days: int = 10,
    rth_start: str = "09:30",
    rth_end: str = "16:00"
) -> tuple[list[DailyTPOProfile], CompositeTPOProfile]:
    """
    Compute professional TPO Volume Profile using 30-minute periods.
    
    TEACHING:
    - TPO = Time Price Opportunity. Each 30-min period gets a letter (A-O).
    - Where price spends TIME = where volume ACCUMULATED.
    - POC = price with most TPOs = fair price (most accepted).
    - Value Area = 70% of TPOs = where price is "fair".
    - Initial Balance (IB) = first 2 periods (1 hour) = day's foundation.
    - Range Extension = price moves beyond IB with conviction.
    - Single Prints = prices visited once = REJECTION (thin liquidity).
    - Tails/Excess = single prints at extremes = violent rejection.
    
    THIS IS NOT THE SAME AS VOLUME PROFILE:
    - TPO counts TIME at price (each period = 1 TPO per price)
    - Volume Profile counts VOLUME at price
    - Institutions use BOTH. TPO shows acceptance, Volume shows aggression.
    
    PERFORMANCE: Uses ATR-based price binning to avoid OOM on volatile stocks.
    Bin size = 10% of daily ATR (min 1 cent, max 100 bins per period).
    """
    
    # Filter to RTH only
    ohlcv_30m = ohlcv_30m.between_time(rth_start, rth_end)
    
    # Group by date
    daily_groups = ohlcv_30m.groupby(ohlcv_30m.index.date)
    
    daily_profiles = []
    period_letters = [chr(ord('A') + i) for i in range(13)]  # A-M for 6.5 hrs
    
    def _get_price_bins(low: float, high: float, atr: float | None = None) -> np.ndarray:
        """Generate price bins — ATR-based to avoid OOM on wide ranges."""
        if atr and atr > 0:
            bin_size = max(0.01, atr * 0.1)  # 10% of ATR, min 1 cent
        else:
            price_range = high - low
            bin_size = max(0.01, price_range / 100)  # Max 100 bins
        return np.arange(low, high + bin_size, bin_size)
    
    for date, day_data in daily_groups:
        if len(day_data) < 5:  # Need minimum periods
            continue
            
        periods = []
        
        # Compute daily ATR for binning
        day_atr = (day_data["High"] - day_data["Low"]).mean()
        
        # Build TPO distribution for the day
        tpo_distribution: dict[float, int] = {}
        
        for idx, (ts, row) in enumerate(day_data.iterrows()):
            if idx >= 13:  # Only first 13 periods (RTH)
                break
                
            period = TPOPeriod(
                period_letter=period_letters[idx],
                timestamp=ts,
                high=row["High"],
                low=row["Low"],
                close=row["Close"],
                volume=row["Volume"],
                tpo_price_levels=[]
            )
            
            # Distribute TPOs across price range using ATR-based bins
            bins = _get_price_bins(row["Low"], row["High"], day_atr)
            for p in bins:
                price_key = round(p, 2)
                tpo_distribution[price_key] = tpo_distribution.get(price_key, 0) + 1
            period.tpo_price_levels = [round(p, 2) for p in bins]
            periods.append(period)
        
        # Initial Balance = Periods A & B (first hour)
        ib_high = max(day_data.iloc[0]["High"], day_data.iloc[1]["High"]) if len(day_data) > 1 else None
        ib_low = min(day_data.iloc[0]["Low"], day_data.iloc[1]["Low"]) if len(day_data) > 1 else None
        ib_mid = (ib_high + ib_low) / 2 if ib_high and ib_low else None
        
        # Range Extension
        day_high = day_data["High"].max()
        day_low = day_data["Low"].min()
        range_ext_up = day_high > ib_high if ib_high else False
        range_ext_down = day_low < ib_low if ib_low else False
        
        # Find POC (most TPOs)
        if tpo_distribution:
            poc = max(tpo_distribution, key=tpo_distribution.get)
            
            # Value Area (70% of TPOs)
            total_tpos = sum(tpo_distribution.values())
            target = total_tpos * 0.7
            
            # Expand from POC outward
            sorted_prices = sorted(tpo_distribution.keys())
            poc_idx = sorted_prices.index(poc)
            
            va_low_idx = poc_idx
            va_high_idx = poc_idx
            current_tpos = tpo_distribution[poc]
            
            while current_tpos < target and (va_low_idx > 0 or va_high_idx < len(sorted_prices) - 1):
                vol_down = tpo_distribution[sorted_prices[va_low_idx - 1]] if va_low_idx > 0 else 0
                vol_up = tpo_distribution[sorted_prices[va_high_idx + 1]] if va_high_idx < len(sorted_prices) - 1 else 0
                
                if vol_up >= vol_down and va_high_idx < len(sorted_prices) - 1:
                    va_high_idx += 1
                    current_tpos += vol_up
                elif va_low_idx > 0:
                    va_low_idx -= 1
                    current_tpos += vol_down
                else:
                    break
            
            vah = sorted_prices[va_high_idx]
            val = sorted_prices[va_low_idx]
            
            # Single prints (rejection)
            single_prints = [p for p, cnt in tpo_distribution.items() if cnt == 1]
            
            # Tails/Excess (single prints at extremes)
            tail_excess = [p for p in single_prints 
                          if p >= vah or p <= val]
        else:
            poc = vah = val = day_data["Close"].iloc[-1]
            single_prints = []
            tail_excess = []
        
        profile = DailyTPOProfile(
            date=pd.Timestamp(date),
            periods=periods,
            ib_high=ib_high,
            ib_low=ib_low,
            ib_mid=ib_mid,
            range_extension_up=range_ext_up,
            range_extension_down=range_ext_down,
            poc=poc,
            vah=vah,
            val=val,
            single_prints=single_prints,
            tail_excess=tail_excess
        )
        daily_profiles.append(profile)
    
    # Build composite profile
    if daily_profiles:
        # Aggregate TPOs across all days
        composite_tpos: dict[float, int] = {}
        for dp in daily_profiles:
            for period in dp.periods:
                for p in period.tpo_price_levels:
                    composite_tpos[p] = composite_tpos.get(p, 0) + 1
        
        if composite_tpos:
            composite_poc = max(composite_tpos, key=composite_tpos.get)
            
            # Composite Value Area
            total = sum(composite_tpos.values())
            target = total * 0.7
            sorted_p = sorted(composite_tpos.keys())
            poc_idx = sorted_p.index(composite_poc)
            
            cl, ch = poc_idx, poc_idx
            curr = composite_tpos[composite_poc]
            while curr < target and (cl > 0 or ch < len(sorted_p) - 1):
                vd = composite_tpos[sorted_p[cl-1]] if cl > 0 else 0
                vu = composite_tpos[sorted_p[ch+1]] if ch < len(sorted_p)-1 else 0
                if vu >= vd and ch < len(sorted_p)-1:
                    ch += 1; curr += vu
                elif cl > 0:
                    cl -= 1; curr += vd
                else: break
            
            composite_vah = sorted_p[ch]
            composite_val = sorted_p[cl]
        else:
            composite_poc = composite_vah = composite_val = daily_profiles[-1].poc
        
        # POC Migration (5-10 day lookback, not 3)
        if len(daily_profiles) >= 5:
            recent_pocs = [dp.poc for dp in daily_profiles[-10:]]  # 10 days
            # Linear regression slope for migration direction
            x = np.arange(len(recent_pocs))
            slope = np.polyfit(x, recent_pocs, 1)[0]
            if slope > 0.001:
                poc_migration = "up"
            elif slope < -0.001:
                poc_migration = "down"
            else:
                poc_migration = "stable"
        else:
            poc_migration = "stable"
        
        composite = CompositeTPOProfile(
            profiles=daily_profiles,
            composite_poc=composite_poc,
            composite_vah=composite_vah,
            composite_val=composite_val,
            poc_migration=poc_migration,
            developing_poc=daily_profiles[-1].poc if daily_profiles else 0
        )
    else:
        composite = CompositeTPOProfile(
            profiles=[],
            composite_poc=0, composite_vah=0, composite_val=0,
            poc_migration="stable", developing_poc=0
        )
    
    return daily_profiles, composite
```

### Integration Points

| File | Change |
|------|--------|
| `technical.py` | Import, call in `analyze()` with 30m data, add to `TechnicalAnalysis` |
| `models.py` | Add `DailyTPOProfile`, `CompositeTPOProfile` fields to `TechnicalAnalysis` |
| `narration.py` | Add TPO insights to `_why_this` (POC, VA, IB, migration) |
| `synthesis.py` | Use POC/VA for targets, IB for stops, migration for bias |

### Data Requirements

| Requirement | Details |
|-------------|---------|
| **Timeframe** | 30-minute OHLCV (RTH only: 9:30-16:00 ET) |
| **History** | Minimum 10 days (130 periods) for composite |
| **Source** | yfinance supports 30m for 60 days; Polygon.io for longer |

### Teaching Content

```json
{
  "metric": "tpo_poc",
  "label": "Point of Control (TPO)",
  "lesson": "The price where price spent the most TIME during the session. This is the 'fair price' — where buyers and sellers agreed most. Price gravitates toward POC.",
  "deep_dive": "POC migration tells you trend: rising POC = accumulation, falling POC = distribution. Current price vs POC: above = premium (sell zone), below = discount (buy zone).",
  "related": ["tpo_vah", "tpo_val", "tpo_ib", "tpo_migration"]
}
```

---

## 3. Smart Money Concepts (`technical/smc.py`)

### Algorithm Specification

```python
# technical/smc.py (NEW FILE)

from dataclasses import dataclass
from typing import Literal
import numpy as np
import pandas as pd

@dataclass
class OrderBlock:
    type: Literal["bullish_ob", "bearish_ob"]
    top: float      # High of the OB candle
    bottom: float   # Low of the OB candle
    index: int      # Candle index
    timestamp: pd.Timestamp
    impulsive_move_pct: float  # % move after OB
    mitigated: bool = False
    mitigation_index: int | None = None
    strength: float = 0.0      # 0-1 score

@dataclass
class FairValueGap:
    type: Literal["bullish_fvg", "bearish_fvg"]
    top: float      # Gap top (candle 1 high for bullish, candle 3 high for bearish)
    bottom: float   # Gap bottom (candle 3 low for bullish, candle 1 low for bearish)
    index: int      # Middle candle index (candle 2)
    timestamp: pd.Timestamp
    size_pct: float # Gap size as % of price
    filled: bool = False
    fill_index: int | None = None
    consequent_encroachment: bool = False  # 50% fill

@dataclass
class BreakerBlock:
    type: Literal["bullish_breaker", "bearish_breaker"]
    original_ob: OrderBlock
    break_index: int
    break_price: float
    retest_confirmed: bool = False

@dataclass
class LiquidityLevel:
    price: float
    type: Literal["buy_side", "sell_side"]
    source: Literal["equal_highs", "equal_lows", "swing_high", "swing_low", 
                    "pdh", "pdl", "pwh", "pwl", "session_high", "session_low"]
    strength: int  # Number of touches
    timestamp: pd.Timestamp

def detect_order_blocks(
    ohlcv: pd.DataFrame,
    swings: list,
    min_impulse_pct: float = 1.5,
    lookback: int = 50,
    real_time: bool = False
) -> list[OrderBlock]:
    """
    Detect Order Blocks (OB) — Institutional Entry Zones.
    
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
    
    MODES:
    - real_time=False (historical analysis): Lookahead allowed to find impulses
    - real_time=True (live trading): NO lookahead — only confirmed OBs returned
    """
    obs = []
    close = ohlcv["Close"].values
    open_ = ohlcv["Open"].values
    high = ohlcv["High"].values
    low = ohlcv["Low"].values
    volume = ohlcv["Volume"].values
    avg_volume = pd.Series(volume).rolling(20).mean().values
    
    if real_time:
        # REAL-TIME MODE: Only return OBs where impulse is ALREADY confirmed
        # Scan backward from current candle
        max_idx = len(ohlcv) - 1  # Current (incomplete) candle excluded
        start_idx = max(lookback, max_idx - 100)
    else:
        # HISTORICAL MODE: Full lookahead allowed
        max_idx = len(ohlcv) - 10  # Leave room for impulse
        start_idx = lookback
    
    for i in range(start_idx, max_idx):
        # Check for bullish impulse starting after i
        if close[i] < open_[i]:  # Down candle (potential bullish OB)
            # Look ahead for impulsive up move
            for j in range(i+1, min(i+10, len(close))):
                move_pct = (close[j] - close[i]) / close[i] * 100
                if move_pct >= min_impulse_pct:
                    # Found impulse! Check volume on impulse candles
                    impulse_volume = volume[i+1:j+1].mean()
                    if impulse_volume > avg_volume[i] * 1.2:
                        ob = OrderBlock(
                            type="bullish_ob",
                            top=high[i],
                            bottom=low[i],
                            index=i,
                            timestamp=ohlcv.index[i],
                            impulsive_move_pct=move_pct,
                            strength=min(1.0, move_pct / 5.0)
                        )
                        obs.append(ob)
                    break
        
        # Check for bearish impulse
        if close[i] > open_[i]:  # Up candle (potential bearish OB)
            for j in range(i+1, min(i+10, len(close))):
                move_pct = (close[i] - close[j]) / close[i] * 100
                if move_pct >= min_impulse_pct:
                    impulse_volume = volume[i+1:j+1].mean()
                    if impulse_volume > avg_volume[i] * 1.2:
                        ob = OrderBlock(
                            type="bearish_ob",
                            top=high[i],
                            bottom=low[i],
                            index=i,
                            timestamp=ohlcv.index[i],
                            impulsive_move_pct=move_pct,
                            strength=min(1.0, move_pct / 5.0)
                        )
                        obs.append(ob)
                    break
    
    # Check mitigation (historical mode only — in real-time, mitigation hasn't happened yet)
    if not real_time:
        for ob in obs:
            for k in range(ob.index + 1, len(close)):
                if ob.type == "bullish_ob" and low[k] <= ob.bottom:
                    ob.mitigated = True
                    ob.mitigation_index = k
                    break
                elif ob.type == "bearish_ob" and high[k] >= ob.top:
                    ob.mitigated = True
                    ob.mitigation_index = k
                    break
    
    return obs


def detect_fvg(ohlcv: pd.DataFrame, min_gap_pct: float = 0.1) -> list[FairValueGap]:
    """
    Detect Fair Value Gaps (FVG) — Price Imbalances.
    
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
    - Middle candle (candle 2) MUST be impulsive: large body + high volume
    - Without impulsive middle candle, it's just a gap, not an FVG
    
    TYPES:
    - Standard FVG: Clean gap, unfilled
    - Consequent Encroachment: Price filled 50% — still valid
    - Inverse FVG: Failed FVG that becomes opposite bias
    """
    fvgs = []
    high = ohlcv["High"].values
    low = ohlcv["Low"].values
    close = ohlcv["Close"].values
    open_ = ohlcv["Open"].values
    volume = ohlcv["Volume"].values
    avg_volume = pd.Series(volume).rolling(20).mean().values
    
    for i in range(1, len(ohlcv) - 1):
        # Middle candle (i) must be impulsive
        middle_body_pct = abs(close[i] - open_[i]) / close[i] * 100
        middle_volume_ratio = volume[i] / avg_volume[i] if avg_volume[i] > 0 else 0
        
        if middle_body_pct < 0.5 or middle_volume_ratio < 1.5:
            continue  # Middle candle not impulsive enough
        
        # Bullish FVG: Candle i-1 high < Candle i+1 low
        if high[i-1] < low[i+1]:
            gap_top = low[i+1]
            gap_bottom = high[i-1]
            size_pct = (gap_top - gap_bottom) / close[i] * 100
            
            if size_pct > min_gap_pct:
                fvg = FairValueGap(
                    type="bullish_fvg",
                    top=gap_top,
                    bottom=gap_bottom,
                    index=i,
                    timestamp=ohlcv.index[i],
                    size_pct=size_pct
                )
                fvgs.append(fvg)
        
        # Bearish FVG: Candle i-1 low > Candle i+1 high
        if low[i-1] > high[i+1]:
            gap_top = low[i-1]
            gap_bottom = high[i+1]
            size_pct = (gap_top - gap_bottom) / close[i] * 100
            
            if size_pct > min_gap_pct:
                fvg = FairValueGap(
                    type="bearish_fvg",
                    top=gap_top,
                    bottom=gap_bottom,
                    index=i,
                    timestamp=ohlcv.index[i],
                    size_pct=size_pct
                )
                fvgs.append(fvg)
    
    # Check fills
    for fvg in fvgs:
        for k in range(fvg.index + 2, len(close)):
            if fvg.type == "bullish_fvg":
                if low[k] <= fvg.bottom:
                    fvg.filled = True
                    fvg.fill_index = k
                    break
                elif low[k] <= (fvg.top + fvg.bottom) / 2:
                    fvg.consequent_encroachment = True
            else:
                if high[k] >= fvg.top:
                    fvg.filled = True
                    fvg.fill_index = k
                    break
                elif high[k] >= (fvg.top + fvg.bottom) / 2:
                    fvg.consequent_encroachment = True
    
    return fvgs


def detect_breaker_blocks(obs: list[OrderBlock], ohlcv: pd.DataFrame) -> list[BreakerBlock]:
    """
    Detect Breaker Blocks — Failed Order Blocks that Flip Bias.
    
    TEACHING:
    - Breaker Block = Order Block that was MITIGATED (price traded through it)
      but then price REVERSED and broke the other way.
    - The failed OB becomes NEW support/resistance in the OPPOSITE direction.
    - This is a POWERFUL confirmation — structure has shifted.
    
    EXAMPLE:
    - Bullish OB forms at $100. Price returns, breaks BELOW $100 (mitigated).
    - Then price rallies back ABOVE $100 and continues up.
    - The $100 level (failed bullish OB) is now a BEARISH BREAKER —
      but wait, price went UP through it! So it becomes a BULLISH BREAKER
      (failed bearish pressure becomes support).
    """
    breakers = []
    close = ohlcv["Close"].values
    high = ohlcv["High"].values
    low = ohlcv["Low"].values
    
    for ob in obs:
        if not ob.mitigated:
            continue
            
        # Check if price reverses after mitigation
        if ob.type == "bullish_ob":
            # Bullish OB was broken down — check for rally back up
            for k in range(ob.mitigation_index + 1, len(close)):
                if close[k] > ob.top:  # Reclaimed the OB
                    # Confirm with follow-through
                    if k + 3 < len(close) and all(close[m] > close[m-1] for m in range(k+1, k+4)):
                        breaker = BreakerBlock(
                            type="bullish_breaker",
                            original_ob=ob,
                            break_index=k,
                            break_price=close[k],
                            retest_confirmed=True
                        )
                        breakers.append(breaker)
                    break
        
        elif ob.type == "bearish_ob":
            # Bearish OB was broken up — check for drop back down
            for k in range(ob.mitigation_index + 1, len(close)):
                if close[k] < ob.bottom:
                    if k + 3 < len(close) and all(close[m] < close[m-1] for m in range(k+1, k+4)):
                        breaker = BreakerBlock(
                            type="bearish_breaker",
                            original_ob=ob,
                            break_index=k,
                            break_price=close[k],
                            retest_confirmed=True
                        )
                        breakers.append(breaker)
                    break
    
    return breakers


def map_liquidity(
    ohlcv_daily: pd.DataFrame,
    ohlcv_intraday: pd.DataFrame | None,  # 5m/15m for session highs/lows
    ohlcv_weekly: pd.DataFrame | None,
    swings: list,
    bos_events: list
) -> list[LiquidityLevel]:
    """
    Map Buy-Side and Sell-Side Liquidity.
    
    TEACHING:
    - LIQUIDITY = STOP LOSSES = FUEL FOR MOVES.
    - Buy-side liquidity = stops ABOVE price (shorts' stops, breakout buyers' stops).
    - Sell-side liquidity = stops BELOW price (longs' stops, breakdown sellers' stops).
    - Institutions HUNT liquidity — they push price to trigger stops, then reverse.
    
    KEY LIQUIDITY POOLS (in priority order):
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
    levels = []
    
    # SESSION HIGHS/LOWS (from intraday data) — HIGHEST PRIORITY
    if ohlcv_intraday is not None and len(ohlcv_intraday) > 0:
        # Group by session (simplified: assume NY session 9:30-16:00 ET)
        # In production, use proper session detection
        session_high = ohlcv_intraday["High"].max()
        session_low = ohlcv_intraday["Low"].min()
        levels.append(LiquidityLevel(
            price=session_high,
            type="buy_side",
            source="session_high",
            strength=3,
            timestamp=ohlcv_intraday.index[-1]
        ))
        levels.append(LiquidityLevel(
            price=session_low,
            type="sell_side",
            source="session_low",
            strength=3,
            timestamp=ohlcv_intraday.index[-1]
        ))
    
    # EQUAL HIGHS/LOWS (intraday if available, else daily)
    # Use intraday for precision, daily as fallback
    equal_high_source = ohlcv_intraday if ohlcv_intraday is not None else ohlcv_daily
    equal_low_source = ohlcv_intraday if ohlcv_intraday is not None else ohlcv_daily
    
    high = equal_high_source["High"].values
    low = equal_low_source["Low"].values
    
    # Equal highs (buy-side)
    for i in range(2, len(high)):
        if abs(high[i] - high[i-1]) / high[i] < 0.005:  # Within 0.5%
            touches = 2
            if i >= 3 and abs(high[i] - high[i-2]) / high[i] < 0.005:
                touches = 3
            levels.append(LiquidityLevel(
                price=high[i],
                type="buy_side",
                source="equal_highs",
                strength=touches,
                timestamp=equal_high_source.index[i]
            ))
    
    # Equal lows (sell-side)
    for i in range(2, len(low)):
        if abs(low[i] - low[i-1]) / low[i] < 0.005:
            touches = 2
            if i >= 3 and abs(low[i] - low[i-2]) / low[i] < 0.005:
                touches = 3
            levels.append(LiquidityLevel(
                price=low[i],
                type="sell_side",
                source="equal_lows",
                strength=touches,
                timestamp=equal_low_source.index[i]
            ))
    
    # Swing highs/lows from structure
    for swing in swings:
        if swing.type == "high":
            levels.append(LiquidityLevel(
                price=swing.price,
                type="buy_side",
                source="swing_high",
                strength=swing.strength,
                timestamp=swing.timestamp
            ))
        else:
            levels.append(LiquidityLevel(
                price=swing.price,
                type="sell_side",
                source="swing_low",
                strength=swing.strength,
                timestamp=swing.timestamp
            ))
    
    # Prior day high/low
    if len(ohlcv_daily) >= 2:
        levels.append(LiquidityLevel(
            price=ohlcv_daily["High"].iloc[-2],
            type="buy_side", source="pdh", strength=2,
            timestamp=ohlcv_daily.index[-2]
        ))
        levels.append(LiquidityLevel(
            price=ohlcv_daily["Low"].iloc[-2],
            type="sell_side", source="pdl", strength=2,
            timestamp=ohlcv_daily.index[-2]
        ))
    
    # Prior week high/low
    if ohlcv_weekly is not None and len(ohlcv_weekly) >= 2:
        levels.append(LiquidityLevel(
            price=ohlcv_weekly["High"].iloc[-2],
            type="buy_side", source="pwh", strength=3,
            timestamp=ohlcv_weekly.index[-2]
        ))
        levels.append(LiquidityLevel(
            price=ohlcv_weekly["Low"].iloc[-2],
            type="sell_side", source="pwl", strength=3,
            timestamp=ohlcv_weekly.index[-2]
        ))
    
    # BOS levels become liquidity magnets
    for bos in bos_events:
        if bos.type == "bullish_bos":
            levels.append(LiquidityLevel(
                price=bos.structure_level,
                type="buy_side", source="bos_level", strength=3,
                timestamp=bos.break_timestamp
            ))
        else:
            levels.append(LiquidityLevel(
                price=bos.structure_level,
                type="sell_side", source="bos_level", strength=3,
                timestamp=bos.break_timestamp
            ))
    
    return levels
```

### Integration Points

| File | Change |
|------|--------|
| `technical.py` | Import all SMC functions, call in `_analyze_timeframe()` |
| `models.py` | Add `OrderBlock`, `FairValueGap`, `BreakerBlock`, `LiquidityLevel` to `TechnicalAnalysis` |
| `narration.py` | Add SMC insights to `_why_this` / `_what_kills_it` |
| `synthesis.py` | Use OB/FVG for entry zones, liquidity for targets/stops |

---

## 4. Validated Breakout Detection (`technical/breakout.py`)

### Algorithm Specification

```python
# technical/breakout.py (NEW FILE)

from dataclasses import dataclass
from typing import Literal
import numpy as np
import pandas as pd

@dataclass
class BreakoutEvent:
    type: Literal["bullish_breakout", "bearish_breakout"]
    level: float              # Level that was broken
    level_type: str           # "resistance", "support", "ib_high", "ib_low", "pdh", "pdl"
    breakout_price: float
    breakout_index: int
    breakout_timestamp: pd.Timestamp
    breakout_volume_ratio: float
    follow_through_confirmed: bool
    follow_through_bars: int
    retest_confirmed: bool = False
    retest_price: float | None = None
    retest_index: int | None = None
    false_breakout: bool = False
    confidence: float = 0.0   # 0-1 score

def detect_validated_breakouts(
    ohlcv: pd.DataFrame,
    key_levels: dict,  # {"resistance": [...], "support": [...], "ib_high": ..., etc.}
    bos_events: list,
    volume_threshold: float = 1.5,
    min_follow_through: int = 3,
    retest_tolerance_pct: float = 0.5
) -> list[BreakoutEvent]:
    """
    Detect and VALIDATE breakouts with institutional criteria.
    
    TEACHING:
    - Most breakouts FAIL (70%+). Retail traders chase every break.
    - Institutions VALIDATE before committing:
      1. VOLUME: Breakout candle > 1.5x average (real participation)
      2. FOLLOW-THROUGH: Next 3+ candles continue direction (momentum)
      3. RETEST: Price returns to broken level (now flipped S/R) and HOLDS
      4. NO FALSE BREAK: Quick reversal back inside range = trap
    
    LEVEL TYPES THAT MATTER:
    - Resistance/Support from swing clusters
    - Initial Balance High/Low (TPO)
    - Prior Day High/Low (PDH/PDL)
    - Prior Week High/Low (PWH/PWL)
    - BOS levels (structure breaks)
    - VWAP deviations
    
    SCORING:
    - Volume confirmed: +0.3
    - Follow-through: +0.3
    - Retest held: +0.3
    - Key level (PDH/PWH): +0.1
    Total > 0.7 = High confidence tradeable breakout
    """
    breakouts = []
    close = ohlcv["Close"].values
    high = ohlcv["High"].values
    low = ohlcv["Low"].values
    volume = ohlcv["Volume"].values
    avg_volume = pd.Series(volume).rolling(20).mean().values
    
    # Collect all levels to watch
    watch_levels = []
    for level in key_levels.get("resistance", []):
        watch_levels.append((level, "resistance", "buy_side"))
    for level in key_levels.get("support", []):
        watch_levels.append((level, "support", "sell_side"))
    
    if "ib_high" in key_levels and key_levels["ib_high"]:
        watch_levels.append((key_levels["ib_high"], "ib_high", "buy_side"))
    if "ib_low" in key_levels and key_levels["ib_low"]:
        watch_levels.append((key_levels["ib_low"], "ib_low", "sell_side"))
    if "pdh" in key_levels and key_levels["pdh"]:
        watch_levels.append((key_levels["pdh"], "pdh", "buy_side"))
    if "pdl" in key_levels and key_levels["pdl"]:
        watch_levels.append((key_levels["pdl"], "pdl", "sell_side"))
    
    # Add BOS levels
    for bos in bos_events:
        if bos.type == "bullish_bos":
            watch_levels.append((bos.structure_level, "bos_resistance", "buy_side"))
        else:
            watch_levels.append((bos.structure_level, "bos_support", "sell_side"))
    
    # Scan for breakouts
    broken_levels = set()  # Track already-broken levels
    
    for i in range(20, len(close) - min_follow_through):
        current_close = close[i]
        current_volume = volume[i]
        current_avg = avg_volume[i] if i < len(avg_volume) and not pd.isna(avg_volume[i]) else np.mean(volume[max(0,i-20):i])
        
        if current_avg == 0:
            continue
            
        vol_ratio = current_volume / current_avg
        
        for level_price, level_type, liquidity_side in watch_levels:
            level_key = f"{level_type}_{level_price:.2f}"
            
            if level_key in broken_levels:
                continue
            
            # Bullish breakout: close breaks above resistance
            if level_type in ("resistance", "ib_high", "pdh", "pwh", "bos_resistance") and current_close > level_price:
                if vol_ratio >= volume_threshold:
                    # Check follow-through
                    ft = True
                    ft_bars = 0
                    for k in range(1, min_follow_through + 1):
                        if i + k < len(close) and close[i+k] > close[i+k-1]:
                            ft_bars += 1
                        else:
                            ft = False
                            break
                    
                    if ft:
                        # Check for false breakout (quick reversal)
                        false_bo = False
                        for k in range(1, 6):
                            if i + k < len(close) and close[i+k] < level_price:
                                false_bo = True
                                break
                        
                        if not false_bo:
                            confidence = 0.0
                            confidence += 0.3  # Volume
                            confidence += 0.3  # Follow-through
                            if level_type in ("pdh", "pwh", "bos_resistance"):
                                confidence += 0.1  # Key level
                            
                            bo = BreakoutEvent(
                                type="bullish_breakout",
                                level=level_price,
                                level_type=level_type,
                                breakout_price=current_close,
                                breakout_index=i,
                                breakout_timestamp=ohlcv.index[i],
                                breakout_volume_ratio=vol_ratio,
                                follow_through_confirmed=True,
                                follow_through_bars=ft_bars,
                                false_breakout=False,
                                confidence=confidence
                            )
                            breakouts.append(bo)
                            broken_levels.add(level_key)
            
            # Bearish breakout: close breaks below support
            elif level_type in ("support", "ib_low", "pdl", "pwl", "bos_support") and current_close < level_price:
                if vol_ratio >= volume_threshold:
                    ft = True
                    ft_bars = 0
                    for k in range(1, min_follow_through + 1):
                        if i + k < len(close) and close[i+k] < close[i+k-1]:
                            ft_bars += 1
                        else:
                            ft = False
                            break
                    
                    if ft:
                        false_bo = False
                        for k in range(1, 6):
                            if i + k < len(close) and close[i+k] > level_price:
                                false_bo = True
                                break
                        
                        if not false_bo:
                            confidence = 0.0
                            confidence += 0.3
                            confidence += 0.3
                            if level_type in ("pdl", "pwl", "bos_support"):
                                confidence += 0.1
                            
                            bo = BreakoutEvent(
                                type="bearish_breakout",
                                level=level_price,
                                level_type=level_type,
                                breakout_price=current_close,
                                breakout_index=i,
                                breakout_timestamp=ohlcv.index[i],
                                breakout_volume_ratio=vol_ratio,
                                follow_through_confirmed=True,
                                follow_through_bars=ft_bars,
                                false_breakout=False,
                                confidence=confidence
                            )
                            breakouts.append(bo)
                            broken_levels.add(level_key)
    
    # Check retests for confirmed breakouts
    for bo in breakouts:
        if bo.type == "bullish_breakout":
            for j in range(bo.breakout_index + 1, len(close)):
                # Retest = price returns to broken level (now support)
                if abs(low[j] - bo.level) / bo.level <= retest_tolerance_pct / 100:
                    # Check if it holds and continues up
                    if j + 2 < len(close) and close[j+2] > close[j+1] > close[j]:
                        bo.retest_confirmed = True
                        bo.retest_price = low[j]
                        bo.retest_index = j
                        bo.confidence += 0.3
                    break
        else:
            for j in range(bo.breakout_index + 1, len(close)):
                if abs(high[j] - bo.level) / bo.level <= retest_tolerance_pct / 100:
                    if j + 2 < len(close) and close[j+2] < close[j+1] < close[j]:
                        bo.retest_confirmed = True
                        bo.retest_price = high[j]
                        bo.retest_index = j
                        bo.confidence += 0.3
                    break
    
    return breakouts
```

### Integration Points

| File | Change |
|------|--------|
| `technical.py` | Import, call in `_analyze_timeframe()` after levels + BOS |
| `models.py` | Add `ChartReadingAnalysis` sub-model with all new fields; `TechnicalAnalysis.chart_reading` |
| `narration.py` | Add breakout to `_why_now` (catalyst) |
| `synthesis.py` | Use validated breakouts for conviction boost (already has `breakout_confirmed` logic) |

---

## Integration Summary: Files to Modify

### New Files (4)
```
backend/app/domain/ticker_analysis/
├── structure.py          # BOS/CHoCH detection
├── volume_profile.py     # Professional TPO
├── smc.py                # Order Blocks, FVG, Breakers, Liquidity
└── breakout.py           # Validated Breakout Detection
```

### Existing Files to Modify (6)
```
backend/app/domain/ticker_analysis/
├── technical.py          # Import & call new modules in _analyze_timeframe()
├── models.py             # Add ChartReadingAnalysis sub-model; TechnicalAnalysis.chart_reading
├── synthesis.py          # Use new signals for entries/stops/targets/conviction
├── narration.py          # Add teaching explanations for new concepts
├── orchestrator.py       # Fetch 30m/5m/15m data from Polygon.io
└── mtf_confluence.py     # NEW: Multi-timeframe signal alignment
```

---

## Data Infrastructure Requirements (BLOCKER — Must Resolve First)

| Feature | Required Data | Current Source | Gap | Resolution |
|---------|---------------|----------------|-----|------------|
| BOS/CHoCH | 15m/30m/1h/4h/daily | yfinance (limited) | Need reliable intraday | **Polygon.io REQUIRED** |
| Professional TPO | 30m RTH (9:30-16:00) | yfinance 30m (60 days) | Need >6 months for composite | **Polygon.io REQUIRED** |
| Order Blocks/FVG | 5m/15m/30m | yfinance (1m only 7 days) | Need 1-3 months history | **Polygon.io REQUIRED** |
| Breakouts | All timeframes | Partial | Need consistent intraday | **Polygon.io REQUIRED** |

**BLOCKER RESOLUTION:** Polygon.io integration is **Phase 1.0 deliverable** (Week 0), not a future decision. All chart reading modules depend on it.

**Acceptance Criteria Addition:** "Polygon.io client integrated, 2+ years 5m/15m/30m/1h data verified for parity tickers (ADBE, MELI, BULL, KURA, MSTR)."

---

## New Module: Multi-Timeframe Confluence (`technical/mtf_confluence.py`)

### Algorithm Specification

```python
# technical/mtf_confluence.py (NEW FILE)

from dataclasses import dataclass
from typing import Literal
from backend.app.domain.ticker_analysis.models import TechnicalAnalysis

@dataclass
class ConfluenceSignal:
    timeframe: str
    signal_type: Literal["bos", "choch", "ob", "fvg", "breakout", "tpo_poc"]
    direction: Literal["bullish", "bearish"]
    strength: float  # 0-1
    price: float
    description: str

@dataclass
class MTFConfluenceResult:
    overall_bias: Literal["bullish", "bearish", "neutral"]
    confidence: float  # 0-1
    bullish_signals: list[ConfluenceSignal]
    bearish_signals: list[ConfluenceSignal]
    conflicts: list[str]  # e.g., "Daily bullish, 4h bearish"
    entry_zones: list[tuple[float, float]]  # (low, high) price zones
    invalidation_level: float | None

def align_signals(
    daily: TechnicalAnalysis | None,
    h4: TechnicalAnalysis | None,
    h1: TechnicalAnalysis | None,
    m15: TechnicalAnalysis | None
) -> MTFConfluenceResult:
    """
    Align signals across timeframes for institutional-grade confluence.
    
    TEACHING:
    - HTF (Daily/Weekly) sets the BIAS
    - MTF (4h) defines the STRUCTURE & ENTRY ZONES
    - LTF (1h/15m) provides the TRIGGER
    
    RULES:
    1. Daily structure (BOS/CHoCH) = PRIMARY bias
    2. 4h OB/FVG in direction of daily bias = ENTRY ZONE
    3. 1h/15m breakout/FVG/retest = TRIGGER
    4. Conflicting signals = reduce confidence, don't trade
    
    SCORING:
    - Daily BOS/CHoCH: weight 0.4
    - 4h OB/FVG: weight 0.3
    - 1h/15m breakout/trigger: weight 0.2
    - TPO POC/VA alignment: weight 0.1
    
    Returns structured result for synthesis.py to consume.
    """
    bullish_signals = []
    bearish_signals = []
    conflicts = []
    
    # Helper to extract chart_reading safely
    def get_cr(ta: TechnicalAnalysis | None):
        return ta.chart_reading if ta and ta.chart_reading else None
    
    daily_cr = get_cr(daily)
    h4_cr = get_cr(h4)
    h1_cr = get_cr(h1)
    m15_cr = get_cr(m15)
    
    # 1. DAILY BIAS (weight 0.4)
    if daily_cr:
        # BOS/CHoCH on daily
        for bos in daily_cr.bos_events:
            sig = ConfluenceSignal(
                timeframe="daily",
                signal_type="bos",
                direction="bullish" if bos.type == "bullish_bos" else "bearish",
                strength=0.4 * min(1.0, bos.volume_ratio / 2.0),
                price=bos.structure_level,
                description=f"Daily {bos.type.replace('_', ' ')} at {bos.structure_level:.2f}"
            )
            if sig.direction == "bullish":
                bullish_signals.append(sig)
            else:
                bearish_signals.append(sig)
        
        for choch in daily_cr.choch_events:
            sig = ConfluenceSignal(
                timeframe="daily",
                signal_type="choch",
                direction="bullish" if choch.type == "bullish_choch" else "bearish",
                strength=0.4,
                price=choch.bos_event.structure_level,
                description=f"Daily {choch.type.replace('_', ' ')} confirmed"
            )
            if sig.direction == "bullish":
                bullish_signals.append(sig)
            else:
                bearish_signals.append(sig)
    
    # 2. 4H ENTRY ZONES (weight 0.3)
    if h4_cr:
        for ob in h4_cr.order_blocks:
            if not ob.mitigated:  # Unmitigated = higher probability
                sig = ConfluenceSignal(
                    timeframe="4h",
                    signal_type="ob",
                    direction="bullish" if ob.type == "bullish_ob" else "bearish",
                    strength=0.3 * ob.strength,
                    price=(ob.top + ob.bottom) / 2,
                    description=f"4h unmitigated {ob.type.replace('_', ' ')}"
                )
                if sig.direction == "bullish":
                    bullish_signals.append(sig)
                else:
                    bearish_signals.append(sig)
        
        for fvg in h4_cr.fair_value_gaps:
            if not fvg.filled:
                sig = ConfluenceSignal(
                    timeframe="4h",
                    signal_type="fvg",
                    direction="bullish" if fvg.type == "bullish_fvg" else "bearish",
                    strength=0.3 * min(1.0, fvg.size_pct * 10),
                    price=(fvg.top + fvg.bottom) / 2,
                    description=f"4h unfilled {fvg.type.replace('_', ' ')}"
                )
                if sig.direction == "bullish":
                    bullish_signals.append(sig)
                else:
                    bearish_signals.append(sig)
    
    # 3. 1H/15M TRIGGERS (weight 0.2)
    for tf_name, tf_cr in [("1h", h1_cr), ("15m", m15_cr)]:
        if tf_cr:
            for bo in tf_cr.breakout_events:
                if bo.confidence > 0.5:
                    sig = ConfluenceSignal(
                        timeframe=tf_name,
                        signal_type="breakout",
                        direction="bullish" if bo.type == "bullish_breakout" else "bearish",
                        strength=0.2 * bo.confidence,
                        price=bo.level,
                        description=f"{tf_name} validated breakout of {bo.level_type}"
                    )
                    if sig.direction == "bullish":
                        bullish_signals.append(sig)
                    else:
                        bearish_signals.append(sig)
    
    # 4. TPO ALIGNMENT (weight 0.1)
    if daily_cr and daily_cr.composite_tpo_profile:
        comp = daily_cr.composite_tpo_profile
        current_price = daily_cr.composite_tpo_profile.developing_poc  # Approximation
        if comp.poc_migration == "up" and current_price < comp.composite_poc:
            bullish_signals.append(ConfluenceSignal(
                timeframe="daily",
                signal_type="tpo_poc",
                direction="bullish",
                strength=0.1,
                price=comp.composite_poc,
                description=f"Composite POC migration up, price at discount"
            ))
        elif comp.poc_migration == "down" and current_price > comp.composite_poc:
            bearish_signals.append(ConfluenceSignal(
                timeframe="daily",
                signal_type="tpo_poc",
                direction="bearish",
                strength=0.1,
                price=comp.composite_poc,
                description=f"Composite POC migration down, price at premium"
            ))
    
    # Calculate overall bias
    bull_score = sum(s.strength for s in bullish_signals)
    bear_score = sum(s.strength for s in bearish_signals)
    
    if bull_score > bear_score + 0.15:
        overall_bias = "bullish"
        confidence = min(1.0, (bull_score - bear_score) / (bull_score + bear_score + 0.01))
    elif bear_score > bull_score + 0.15:
        overall_bias = "bearish"
        confidence = min(1.0, (bear_score - bull_score) / (bull_score + bear_score + 0.01))
    else:
        overall_bias = "neutral"
        confidence = 0.0
    
    # Detect conflicts
    if daily_cr and h4_cr:
        daily_bull = any(s.direction == "bullish" for s in bullish_signals if s.timeframe == "daily")
        daily_bear = any(s.direction == "bearish" for s in bearish_signals if s.timeframe == "daily")
        h4_bull = any(s.direction == "bullish" for s in bullish_signals if s.timeframe == "4h")
        h4_bear = any(s.direction == "bearish" for s in bearish_signals if s.timeframe == "4h")
        
        if daily_bull and h4_bear:
            conflicts.append("Daily bullish bias, 4h bearish signals — avoid longs")
        if daily_bear and h4_bull:
            conflicts.append("Daily bearish bias, 4h bullish signals — avoid shorts")
    
    # Entry zones (from 4h OB/FVG in direction of daily bias)
    entry_zones = []
    if overall_bias == "bullish":
        for s in bullish_signals:
            if s.timeframe == "4h" and s.signal_type in ("ob", "fvg"):
                zone_low = s.price * 0.995
                zone_high = s.price * 1.005
                entry_zones.append((zone_low, zone_high))
    elif overall_bias == "bearish":
        for s in bearish_signals:
            if s.timeframe == "4h" and s.signal_type in ("ob", "fvg"):
                zone_low = s.price * 0.995
                zone_high = s.price * 1.005
                entry_zones.append((zone_low, zone_high))
    
    # Invalidation level (nearest opposing structure)
    invalidation = None
    if overall_bias == "bullish" and bearish_signals:
        invalidation = min(s.price for s in bearish_signals)
    elif overall_bias == "bearish" and bullish_signals:
        invalidation = max(s.price for s in bullish_signals)
    
    return MTFConfluenceResult(
        overall_bias=overall_bias,
        confidence=confidence,
        bullish_signals=bullish_signals,
        bearish_signals=bearish_signals,
        conflicts=conflicts,
        entry_zones=entry_zones,
        invalidation_level=invalidation
    )
```

### Integration Points

| File | Change |
|------|--------|
| `technical.py` | Import `align_signals`, call in `analyze()` after all timeframe analyses |
| `models.py` | Add `MTFConfluenceResult` to `TechnicalAnalysis` or separate field |
| `synthesis.py` | Use `entry_zones`, `invalidation_level`, `conflicts` for trade plan |
| `narration.py` | Add MTF confluence to `_why_this` |

---

## Testing Strategy

### Unit Tests (Per Module)

```python
# tests/test_structure.py
def test_bos_detection_bullish():
    # Create synthetic uptrend with clear swing highs
    # Verify BOS detected at correct level with volume confirmation
    
def test_choch_detection_bearish_to_bullish():
    # Create downtrend → BOS up → pullback hold → continuation
    # Verify CHoCH detected

def test_bos_requires_volume():
    # Same price action, low volume → NO BOS

# tests/test_volume_profile.py
def test_tpo_poc_calculation():
    # Known TPO distribution → verify POC
    
def test_initial_balance():
    # First 2 periods define IB correctly

def test_poc_migration():
    # 3 days rising POC → "up"

# tests/test_smc.py
def test_bullish_ob_detection():
    # Down candle → 3% impulse up → OB detected
    
def test_fvg_bullish():
    # Candle 1 high < Candle 3 low → FVG detected

def test_breaker_block():
    # Mitigated OB → reversal → breaker confirmed

# tests/test_breakout.py
def test_validated_breakout_bullish():
    # Resistance + volume + follow-through → breakout
    
def test_false_breakout_rejected():
    # Break then quick reversal → false_breakout=True
```

### Integration Tests

```python
# tests/test_technical_integration.py
def test_full_technical_analysis_pipeline():
    # Run analyze() with all new modules
    # Verify all new fields populated in TechnicalAnalysis
    
def test_multi_timeframe_signals():
    # Daily BOS + 4h OB + 1h FVG alignment → high conviction
```

### Regression Fixtures

- Use parity replay tickers (ADBE, MELI, BULL, KURA, MSTR)
- Lock expected BOS/CHoCH/TPO/SMC outputs
- Run before every commit

---

## Education Integration Plan

For each new concept, add to `frontend/src/content/education.json`:

| Concept | Metric Key | Lesson Sections Needed |
|---------|------------|------------------------|
| BOS/CHoCH | `bos_bullish`, `bos_bearish`, `choch_bullish`, `choch_bearish` | Definition, Identification, Volume rule, Follow-through, Retest, Trading |
| TPO | `tpo_poc`, `tpo_vah`, `tpo_val`, `tpo_ib`, `tpo_migration`, `tpo_single_prints` | TPO vs Volume Profile, POC meaning, Value Area, Initial Balance, Range Extension, Migration |
| Order Blocks | `order_block_bullish`, `order_block_bearish` | Definition, Identification, Mitigation, Unmitigated vs Mitigated, Trading |
| FVG | `fvg_bullish`, `fvg_bearish`, `fvg_consequent_encroachment` | Definition, Types, Fill rates, Consequent Encroachment, Trading |
| Breaker Blocks | `breaker_block_bullish`, `breaker_block_bearish` | Definition, Failed OB logic, Confirmation, Trading |
| Liquidity | `liquidity_buy_side`, `liquidity_sell_side`, `liquidity_inducement` | Buy/Sell side, Sources, Stop hunts, Inducement, Trading |
| Breakouts | `breakout_validated`, `breakout_false` | Validation criteria, Volume, Follow-through, Retest, False breakouts |
| MTF Confluence | `mtf_bias`, `mtf_confidence`, `mtf_conflicts`, `mtf_entry_zones` | HTF bias, MTF entry zones, LTF triggers, Conflict resolution, Confluence scoring |

---

## Acceptance Criteria (Phase 1 Gate)

| Criterion | Target |
|-----------|--------|
| All 5 new modules import without error | ✅ |
| `technical.analyze()` returns all new fields populated | ✅ |
| Unit tests: 100% pass (structure, volume_profile, smc, breakout, mtf_confluence) | ✅ |
| Integration test: full pipeline runs < 10s | ✅ |
| Parity replay: ADBE/MELI/BULL show BOS/CHoCH/TPO/SMC/MTF signals | ✅ |
| Narration includes new concept explanations | ✅ |
| Education tooltips work for all new metrics | ✅ |
| No LSP errors, no type errors | ✅ |
| detect_changes shows only expected symbols affected | ✅ |
| **Polygon.io data verified for parity tickers** | ✅ |

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| yfinance 30m data gaps | Graceful degradation — skip TPO if < 10 days |
| Computation time | Cache TPO composite (1hr TTL), async computation |
| False SMC signals | Require confluence (OB + FVG + structure) for high confidence |
| Over-complex narration | Cap `_why_this` at 4 items, prioritize strongest signals |
| Data dependency | Feature flag `ENABLE_ADVANCED_CHART_READING` for gradual rollout |

---

## Next Steps After Phase 1

1. **Phase 2 (P1):** Wyckoff phases, Liquidity heatmaps (MTF confluence engine ✅ DONE in Phase 1)
2. **Phase 3 (P2):** Anchored VWAPs, Volume Delta, Composite profiles
3. **Validation Layer:** Walk-forward backtests on all signal types
4. **Execution Layer:** Automated alerts, portfolio risk, performance attribution

---

*Plan v1.0 — Ready for Momus review before implementation begins*