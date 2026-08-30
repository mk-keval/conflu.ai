"""Professional TPO Volume Profile — Institutional-grade Market Profile analysis.

This module implements a professional-grade TPO (Time Price Opportunity) Volume Profile
following Market Profile methodology as used by institutional traders (CBOT/CME style).

Key Concepts:
- TPO: Each 30-minute period where price trades is a "Time Price Opportunity"
- RTH: Regular Trading Hours (9:30-16:00 ET) — 13 periods labeled A through M
- Initial Balance (IB): First two periods (A+B) — establishes the day's initial range
- Range Extension: Price moving beyond IB — signals directional conviction
- Single Prints: TPOs occurring only once in a row — indicates weak participation
- Tails/Excess: Single prints at extremes — rejection of price levels
- POC: Point of Control — price with maximum TPOs (fair price)
- VAH/VAL: Value Area High/Low — 70% of TPOs around POC (fair value range)

References:
- Steidlmayer, J.P. "Markets and Market Logic" (1989)
- Dalton, J. "Mind Over Markets" (1991)
- CBOT Market Profile Handbook
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import time, datetime
from typing import Literal
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pandas_ta as ta

# ──────────────────────────────────────────────────────────────
# Constants & Configuration
# ──────────────────────────────────────────────────────────────

ET = ZoneInfo("America/New_York")
RTH_START = time(9, 30)   # 09:30 ET
RTH_END = time(16, 0)     # 16:00 ET
TPO_PERIOD_MINUTES = 30
RTH_PERIODS = 13          # 6.5 hours / 30 min = 13 periods (A-M)
TPO_LETTERS = [chr(ord('A') + i) for i in range(RTH_PERIODS)]  # ['A', 'B', ..., 'M']

# ATR-based binning parameters
ATR_BIN_FACTOR = 0.10     # 10% of daily ATR per bin
MIN_BIN_SIZE = 0.01       # Minimum 1 cent per bin
MAX_BINS_PER_PERIOD = 100 # Cap bins per period for performance

# Value Area: 70% of TPOs (standard Market Profile)
VALUE_AREA_PCT = 0.70

# Composite profile lookback
COMPOSITE_LOOKBACK_DAYS = 10
POC_MIGRATION_SLOPE_THRESHOLD = 0.001  # Slope > 0.001 = up, < -0.001 = down


# ──────────────────────────────────────────────────────────────
# Dataclasses
# ──────────────────────────────────────────────────────────────

@dataclass(slots=True)
class TPOPeriod:
    """A single 30-minute TPO period within RTH.
    
    Attributes:
        letter: Period identifier (A through M for 13 periods)
        start_time: Period start timestamp (ET)
        end_time: Period end timestamp (ET)
        high: Highest price traded during this period
        low: Lowest price traded during this period
        volume: Total volume traded during this period
        tpo_count: Number of price bins touched (TPOs)
        price_bins: Dict mapping price bin center -> TPO count (1 or more if revisited)
    """
    letter: str
    start_time: datetime
    end_time: datetime
    high: float
    low: float
    volume: float
    tpo_count: int = 0
    price_bins: dict[float, int] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate period letter is valid."""
        if self.letter not in TPO_LETTERS:
            raise ValueError(f"Invalid TPO period letter: {self.letter}. Must be A-M.")
    
    @property
    def is_initial_balance(self) -> bool:
        """Whether this period is part of Initial Balance (A or B)."""
        return self.letter in ('A', 'B')
    
    @property
    def range(self) -> float:
        """Price range of this period (high - low)."""
        return self.high - self.low
    
    @property
    def midpoint(self) -> float:
        """Midpoint of this period's range."""
        return (self.high + self.low) / 2


@dataclass(slots=True)
class DailyTPOProfile:
    """Complete TPO profile for a single trading day.
    
    Attributes:
        date: Trading date (ET)
        symbol: Ticker symbol
        periods: List of 13 TPOPeriod objects (A-M)
        bin_size: Price bin size used (ATR-based)
        composite_poc: POC from composite profile (if available)
        poc_migration: 'up' | 'down' | 'neutral' from linear regression
    """
    date: datetime
    symbol: str
    periods: list[TPOPeriod]
    bin_size: float
    composite_poc: float | None = None
    poc_migration: Literal['up', 'down', 'neutral'] = 'neutral'
    
    def __post_init__(self):
        """Validate we have all 13 periods."""
        if len(self.periods) != RTH_PERIODS:
            raise ValueError(f"Expected {RTH_PERIODS} periods, got {len(self.periods)}")
        # Sort periods by letter
        self.periods.sort(key=lambda p: p.letter)
    
    @property
    def initial_balance_high(self) -> float:
        """High of Initial Balance (max of periods A and B)."""
        ib_periods = [p for p in self.periods if p.is_initial_balance]
        return max(p.high for p in ib_periods) if ib_periods else 0.0
    
    @property
    def initial_balance_low(self) -> float:
        """Low of Initial Balance (min of periods A and B)."""
        ib_periods = [p for p in self.periods if p.is_initial_balance]
        return min(p.low for p in ib_periods) if ib_periods else 0.0
    
    @property
    def initial_balance_range(self) -> float:
        """Range of Initial Balance (IB High - IB Low)."""
        return self.initial_balance_high - self.initial_balance_low
    
    @property
    def range_extension_up(self) -> float:
        """Price extension above Initial Balance High (0 if none)."""
        day_high = max(p.high for p in self.periods)
        return max(0.0, day_high - self.initial_balance_high)
    
    @property
    def range_extension_down(self) -> float:
        """Price extension below Initial Balance Low (0 if none)."""
        day_low = min(p.low for p in self.periods)
        return max(0.0, self.initial_balance_low - day_low)
    
    @property
    def range_extension_direction(self) -> Literal['up', 'down', 'both', 'none']:
        """Direction of range extension relative to IB."""
        up = self.range_extension_up > 0
        down = self.range_extension_down > 0
        if up and down:
            return 'both'
        elif up:
            return 'up'
        elif down:
            return 'down'
        return 'none'
    
    @property
    def all_price_bins(self) -> dict[float, int]:
        """Aggregate all TPOs across all periods: price_bin -> total TPO count."""
        result: dict[float, int] = {}
        for period in self.periods:
            for price, count in period.price_bins.items():
                result[price] = result.get(price, 0) + count
        return result
    
    @property
    def total_tpos(self) -> int:
        """Total TPO count for the day."""
        return sum(self.all_price_bins.values())
    
    @property
    def poc(self) -> float:
        """Point of Control — price with maximum TPOs."""
        bins = self.all_price_bins
        if not bins:
            return 0.0
        return max(bins.items(), key=lambda x: x[1])[0]
    
    @property
    def vah(self) -> float:
        """Value Area High — top of 70% TPO range around POC."""
        return self._value_area()[1]
    
    @property
    def val(self) -> float:
        """Value Area Low — bottom of 70% TPO range around POC."""
        return self._value_area()[0]
    
    def _value_area(self) -> tuple[float, float]:
        """Calculate Value Area (70% of TPOs around POC).
        
        Returns:
            (VAL, VAH) tuple
        """
        bins = self.all_price_bins
        if not bins:
            return (0.0, 0.0)
        
        poc_price = self.poc
        total_tpos = self.total_tpos
        target_tpos = total_tpos * VALUE_AREA_PCT
        
        # Find POC bin index in sorted prices
        sorted_prices = sorted(bins.keys())
        poc_idx = sorted_prices.index(poc_price)
        
        # Expand outward from POC
        va_low_idx = poc_idx
        va_high_idx = poc_idx
        current_tpos = bins[poc_price]
        
        while current_tpos < target_tpos and (va_low_idx > 0 or va_high_idx < len(sorted_prices) - 1):
            tpos_down = bins[sorted_prices[va_low_idx - 1]] if va_low_idx > 0 else 0
            tpos_up = bins[sorted_prices[va_high_idx + 1]] if va_high_idx < len(sorted_prices) - 1 else 0
            
            # Expand to side with more TPOs (standard Market Profile method)
            if tpos_up >= tpos_down and va_high_idx < len(sorted_prices) - 1:
                va_high_idx += 1
                current_tpos += tpos_up
            elif va_low_idx > 0:
                va_low_idx -= 1
                current_tpos += tpos_down
            else:
                break
        
        val_price = sorted_prices[va_low_idx]
        vah_price = sorted_prices[va_high_idx]
        return (val_price, vah_price)
    
    @property
    def single_prints(self) -> list[tuple[str, float]]:
        """Find single prints — TPOs that occur only once in a period row.
        
        Returns list of (period_letter, price) for single prints.
        These indicate weak participation / potential reversal zones.
        """
        singles: list[tuple[str, float]] = []
        for period in self.periods:
            for price, count in period.price_bins.items():
                if count == 1:
                    singles.append((period.letter, price))
        return singles
    
    @property
    def tails_excess(self) -> dict[str, list[float]]:
        """Identify tails (buying/selling excess) at period extremes.
        
        Tails are single prints at the high/low of a period that are not
        revisited in subsequent periods — indicating rejection.
        
        Returns:
            Dict with 'buying_tails' (at lows) and 'selling_tails' (at highs)
        """
        buying_tails: list[float] = []
        selling_tails: list[float] = []
        
        for i, period in enumerate(self.periods):
            period_prices = set(period.price_bins.keys())
            
            # Check subsequent periods for revisit
            subsequent_prices: set[float] = set()
            for j in range(i + 1, len(self.periods)):
                subsequent_prices.update(self.periods[j].price_bins.keys())
            
            # Buying tail: single print at period low, not revisited
            if period.low in period_prices and period.price_bins[period.low] == 1:
                if period.low not in subsequent_prices:
                    buying_tails.append(period.low)
            
            # Selling tail: single print at period high, not revisited
            if period.high in period_prices and period.price_bins[period.high] == 1:
                if period.high not in subsequent_prices:
                    selling_tails.append(period.high)
        
        return {
            'buying_tails': buying_tails,
            'selling_tails': selling_tails
        }
    
    @property
    def profile_shape(self) -> Literal['P', 'b', 'D', 'B', 'p', 'trend', 'neutral']:
        """Classify daily profile shape (Market Profile terminology).
        
        P = Poor (wide IB, little range extension)
        b = b-shaped (long lower tail, buying tail)
        D = D-shaped (balanced, rotational)
        B = B-shaped (long upper tail, selling tail)
        p = p-shaped (long upper tail, selling excess)
        trend = Trend day (directional, narrow rotation)
        neutral = Neutral day (balanced both sides)
        """
        ib_range = self.initial_balance_range
        day_range = max(p.high for p in self.periods) - min(p.low for p in self.periods)
        
        if day_range == 0:
            return 'neutral'
        
        ib_pct = ib_range / day_range
        tails = self.tails_excess
        re_dir = self.range_extension_direction
        
        # Poor profile: wide IB (>70% of day range), little extension
        if ib_pct > 0.7 and re_dir == 'none':
            return 'P'
        
        # Trend day: narrow IB (<30%), strong directional extension
        if ib_pct < 0.3 and re_dir in ('up', 'down'):
            return 'trend'
        
        # b-shape: buying tail at bottom, extension up
        if tails['buying_tails'] and re_dir == 'up' and not tails['selling_tails']:
            return 'b'
        
        # p-shape: selling tail at top, extension down
        if tails['selling_tails'] and re_dir == 'down' and not tails['buying_tails']:
            return 'p'
        
        # B-shape: selling excess at top (multiple tails)
        if len(tails['selling_tails']) >= 2 and re_dir == 'down':
            return 'B'
        
        # D-shape: balanced, rotational both sides
        if re_dir == 'both' and 0.3 <= ib_pct <= 0.7:
            return 'D'
        
        return 'neutral'
    
    def get_tpo_distribution(self) -> dict[float, int]:
        """Get full TPO distribution for visualization.
        
        Returns:
            Dict mapping price bin center -> TPO count
        """
        return self.all_price_bins


@dataclass(slots=True)
class CompositeTPOProfile:
    """Composite TPO profile aggregating multiple days.
    
    Combines daily profiles to show longer-term value areas and
    POC migration (trend of fair price over time).
    
    Attributes:
        symbol: Ticker symbol
        start_date: First date in composite
        end_date: Last date in composite
        daily_profiles: List of DailyTPOProfile objects
        composite_poc: Composite Point of Control
        composite_vah: Composite Value Area High
        composite_val: Composite Value Area Low
        poc_migration: 'up' | 'down' | 'neutral' (linear regression slope)
        poc_slope: Slope of POC regression line
    """
    symbol: str
    start_date: datetime
    end_date: datetime
    daily_profiles: list[DailyTPOProfile]
    composite_poc: float
    composite_vah: float
    composite_val: float
    poc_migration: Literal['up', 'down', 'neutral']
    poc_slope: float
    
    @property
    def days_in_composite(self) -> int:
        """Number of trading days in composite."""
        return len(self.daily_profiles)
    
    @property
    def poc_prices(self) -> list[float]:
        """List of daily POCs for trend analysis."""
        return [dp.poc for dp in self.daily_profiles]
    
    @property
    def value_area_width(self) -> float:
        """Width of composite value area (VAH - VAL)."""
        return self.composite_vah - self.composite_val


# ──────────────────────────────────────────────────────────────
# Helper Functions
# ──────────────────────────────────────────────────────────────

def _is_rth(timestamp: pd.Timestamp | datetime) -> bool:
    """Check if timestamp falls within Regular Trading Hours (9:30-16:00 ET)."""
    if isinstance(timestamp, pd.Timestamp):
        ts = timestamp.tz_convert(ET) if timestamp.tz else timestamp.tz_localize(ET)
    else:
        ts = timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=ET)
    
    t = ts.time()
    return RTH_START <= t < RTH_END


def _get_tpo_period_index(timestamp: pd.Timestamp | datetime) -> int | None:
    """Get TPO period index (0-12 for A-M) for a timestamp within RTH.
    
    Returns None if outside RTH.
    """
    if not _is_rth(timestamp):
        return None
    
    if isinstance(timestamp, pd.Timestamp):
        ts = timestamp.tz_convert(ET) if timestamp.tz else timestamp.tz_localize(ET)
    else:
        ts = timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=ET)
    
    # Minutes since 9:30
    minutes_since_open = (ts.hour - 9) * 60 + ts.minute - 30
    period_idx = minutes_since_open // TPO_PERIOD_MINUTES
    
    if 0 <= period_idx < RTH_PERIODS:
        return period_idx
    return None


def _compute_atr_based_bin_size(ohlcv: pd.DataFrame, lookback: int = 14) -> float:
    """Compute price bin size as 10% of daily ATR(14).
    
    Args:
        ohlcv: Daily OHLCV DataFrame
        lookback: ATR lookback period (default 14)
    
    Returns:
        Bin size in price units (minimum 1 cent, capped for max bins)
    """
    if len(ohlcv) < lookback:
        return MIN_BIN_SIZE
    
    atr_series = ta.atr(high=ohlcv["High"], low=ohlcv["Low"], close=ohlcv["Close"], length=lookback)
    if atr_series is None or len(atr_series) == 0:
        return MIN_BIN_SIZE
    
    last_atr = atr_series.iloc[-1]
    if pd.isna(last_atr) or last_atr <= 0:
        return MIN_BIN_SIZE
    
    bin_size = float(last_atr) * ATR_BIN_FACTOR
    return max(MIN_BIN_SIZE, bin_size)


def _create_price_bins(period_high: float, period_low: float, bin_size: float) -> np.ndarray:
    """Create price bin centers for a period's range.
    
    Args:
        period_high: Period high price
        period_low: Period low price
        bin_size: Size of each price bin
    
    Returns:
        Array of bin center prices covering the period's range
    """
    if period_high <= period_low or bin_size <= 0:
        return np.array([])
    
    # Number of bins needed, capped
    num_bins = int(np.ceil((period_high - period_low) / bin_size))
    num_bins = min(num_bins, MAX_BINS_PER_PERIOD)
    
    # Adjust bin size to fit exactly
    actual_bin_size = (period_high - period_low) / num_bins
    
    # Bin centers: start at low + bin_size/2
    centers = period_low + actual_bin_size / 2 + np.arange(num_bins) * actual_bin_size
    return centers


# ──────────────────────────────────────────────────────────────
# Main Computation Function
# ──────────────────────────────────────────────────────────────

def compute_professional_tpo(
    intraday_ohlcv: pd.DataFrame,
    daily_ohlcv: pd.DataFrame | None = None,
    symbol: str = "UNKNOWN",
    lookback_days: int = COMPOSITE_LOOKBACK_DAYS
) -> DailyTPOProfile | tuple[DailyTPOProfile, CompositeTPOProfile]:
    """Compute Professional TPO Volume Profile from intraday data.
    
    This is the main entry point. It takes 30-minute intraday bars,
    filters to RTH, builds 13 TPO periods (A-M), computes ATR-based
    price bins, and derives all Market Profile metrics.
    
    Args:
        intraday_ohlcv: DataFrame with 30-min bars, must have DatetimeIndex (tz-aware or naive)
                        Columns: Open, High, Low, Close, Volume
        daily_ohlcv: Optional daily OHLCV for ATR calculation and composite profile.
                     If None, uses intraday data resampled to daily.
        symbol: Ticker symbol for labeling
        lookback_days: Days to include in composite profile (default 10)
    
    Returns:
        DailyTPOProfile for the last day in intraday_ohlcv,
        or tuple of (DailyTPOProfile, CompositeTPOProfile) if daily_ohlcv provided
        with sufficient history.
    
    Example:
        >>> # Fetch 30-min data from yfinance
        >>> ticker = yf.Ticker("SPY")
        >>> intraday = ticker.history(period="1mo", interval="30m")
        >>> daily = ticker.history(period="3mo", interval="1d")
        >>> profile, composite = compute_professional_tpo(intraday, daily, "SPY")
        >>> print(f"POC: {profile.poc}, VAH: {profile.vah}, VAL: {profile.val}")
        >>> print(f"Composite POC Migration: {composite.poc_migration}")
    """
    if intraday_ohlcv is None or len(intraday_ohlcv) == 0:
        raise ValueError("intraday_ohlcv cannot be empty")
    
    # Ensure DatetimeIndex
    if not isinstance(intraday_ohlcv.index, pd.DatetimeIndex):
        raise ValueError("intraday_ohlcv must have DatetimeIndex")
    
    # Convert to ET if timezone-aware, otherwise assume ET
    if intraday_ohlcv.index.tz is not None:
        intraday_et = intraday_ohlcv.tz_convert(ET)
    else:
        intraday_et = intraday_ohlcv.tz_localize(ET)
    
    # Filter to RTH only
    rth_mask = intraday_et.index.to_series().apply(_is_rth)
    rth_data = intraday_et[rth_mask].copy()
    
    if len(rth_data) == 0:
        raise ValueError("No RTH data found in intraday_ohlcv")
    
    # Get the last trading date in the data
    last_date = rth_data.index[-1].date()

    # Filter to just the last trading day's RTH data
    day_mask = rth_data.index.to_series().dt.date == last_date
    day_data = rth_data[day_mask].copy()
    
    if len(day_data) == 0:
        raise ValueError(f"No RTH data for last date: {last_date}")
    
    # ─── Build 13 TPO Periods (A-M) ───
    periods: list[TPOPeriod] = []
    
    for period_idx in range(RTH_PERIODS):
        period_start = datetime.combine(last_date, RTH_START).replace(tzinfo=ET)
        period_start += pd.Timedelta(minutes=period_idx * TPO_PERIOD_MINUTES)
        period_end = period_start + pd.Timedelta(minutes=TPO_PERIOD_MINUTES)
        
        # Filter bars in this period
        period_mask = (day_data.index >= period_start) & (day_data.index < period_end)
        period_bars = day_data[period_mask]
        
        if len(period_bars) == 0:
            # No trades in this period — create empty period
            # Use previous period's close or interpolate
            prev_close = periods[-1].price_bins if periods else None
            if periods:
                # Use midpoint of previous period as estimate
                est_price = periods[-1].midpoint
            else:
                # First period empty — use day's first available price
                est_price = float(day_data["Close"].iloc[0])
            
            period = TPOPeriod(
                letter=TPO_LETTERS[period_idx],
                start_time=period_start,
                end_time=period_end,
                high=est_price,
                low=est_price,
                volume=0.0,
                tpo_count=0,
                price_bins={}
            )
            periods.append(period)
            continue
        
        # Aggregate period stats
        period_high = float(period_bars["High"].max())
        period_low = float(period_bars["Low"].min())
        period_volume = float(period_bars["Volume"].sum())
        
        # We'll compute price bins after determining bin_size
        periods.append(TPOPeriod(
            letter=TPO_LETTERS[period_idx],
            start_time=period_start,
            end_time=period_end,
            high=period_high,
            low=period_low,
            volume=period_volume,
            tpo_count=0,  # Filled later
            price_bins={}  # Filled later
        ))
    
    # ─── Compute ATR-based Bin Size ───
    if daily_ohlcv is not None and len(daily_ohlcv) >= 14:
        # Ensure daily_ohlcv is in ET
        if isinstance(daily_ohlcv.index, pd.DatetimeIndex):
            if daily_ohlcv.index.tz is not None:
                daily_et = daily_ohlcv.tz_convert(ET)
            else:
                daily_et = daily_ohlcv.tz_localize(ET)
        else:
            daily_et = daily_ohlcv
        
        bin_size = _compute_atr_based_bin_size(daily_et)
    else:
        # Fallback: compute ATR from intraday resampled to daily
        daily_resampled = intraday_et.resample('1D').agg({
            'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum'
        }).dropna()
        bin_size = _compute_atr_based_bin_size(daily_resampled)
    
    # ─── Assign Price Bins to Each Period ───
    for period in periods:
        if period.volume == 0:
            period.tpo_count = 0
            period.price_bins = {}
            continue
        
        bin_centers = _create_price_bins(period.high, period.low, bin_size)
        if len(bin_centers) == 0:
            period.tpo_count = 0
            period.price_bins = {}
            continue
        
        # Each bin gets 1 TPO (standard TPO counting)
        # If you want volume-weighted TPOs, multiply by volume per bin
        period.price_bins = {round(float(c), 2): 1 for c in bin_centers}
        period.tpo_count = len(bin_centers)
    
    # ─── Build Daily Profile ───
    day_dt = datetime.combine(last_date, time(0, 0)).replace(tzinfo=ET)
    daily_profile = DailyTPOProfile(
        date=day_dt,
        symbol=symbol,
        periods=periods,
        bin_size=bin_size
    )
    
    # ─── Compute Composite Profile if daily history available ───
    if daily_ohlcv is not None and len(daily_ohlcv) >= lookback_days:
        composite = _build_composite_profile(
            daily_ohlcv=daily_ohlcv,
            intraday_ohlcv=intraday_et,
            symbol=symbol,
            lookback_days=lookback_days
        )
        # Update daily profile with composite info
        daily_profile.composite_poc = composite.composite_poc
        daily_profile.poc_migration = composite.poc_migration
        return daily_profile, composite
    
    return daily_profile


def _build_composite_profile(
    daily_ohlcv: pd.DataFrame,
    intraday_ohlcv: pd.DataFrame,
    symbol: str,
    lookback_days: int
) -> CompositeTPOProfile:
    """Build composite profile from last N trading days.
    
    Args:
        daily_ohlcv: Daily OHLCV DataFrame (tz-aware ET)
        intraday_ohlvc: Intraday 30-min data (tz-aware ET)
        symbol: Ticker symbol
        lookback_days: Number of days to include
    
    Returns:
        CompositeTPOProfile
    """
    # Get last N trading days
    daily_dates = daily_ohlcv.index.to_series().dt.date[-lookback_days:]
    
    daily_profiles: list[DailyTPOProfile] = []
    
    for day_date in daily_dates:
        # Filter intraday to this day's RTH
        day_mask = intraday_ohlcv.index.date == day_date
        day_intraday = intraday_ohlcv[day_mask]
        
        rth_mask = day_intraday.index.to_series().apply(_is_rth)
        day_rth = day_intraday[rth_mask]
        
        if len(day_rth) == 0:
            continue
        
        # Build periods for this day (same logic as main function)
        periods: list[TPOPeriod] = []
        
        for period_idx in range(RTH_PERIODS):
            period_start = datetime.combine(day_date, RTH_START).replace(tzinfo=ET)
            period_start += pd.Timedelta(minutes=period_idx * TPO_PERIOD_MINUTES)
            period_end = period_start + pd.Timedelta(minutes=TPO_PERIOD_MINUTES)
            
            period_mask = (day_rth.index >= period_start) & (day_rth.index < period_end)
            period_bars = day_rth[period_mask]
            
            if len(period_bars) == 0:
                est_price = periods[-1].midpoint if periods else float(day_rth["Close"].iloc[0])
                period = TPOPeriod(
                    letter=TPO_LETTERS[period_idx],
                    start_time=period_start,
                    end_time=period_end,
                    high=est_price,
                    low=est_price,
                    volume=0.0,
                    tpo_count=0,
                    price_bins={}
                )
                periods.append(period)
                continue
            
            period_high = float(period_bars["High"].max())
            period_low = float(period_bars["Low"].min())
            period_volume = float(period_bars["Volume"].sum())
            
            periods.append(TPOPeriod(
                letter=TPO_LETTERS[period_idx],
                start_time=period_start,
                end_time=period_end,
                high=period_high,
                low=period_low,
                volume=period_volume,
                tpo_count=0,
                price_bins={}
            ))
        
        # Bin size for this day (use daily ATR from daily_ohlcv up to this day)
        day_daily = daily_ohlcv[daily_ohlcv.index.date <= day_date]
        day_bin_size = _compute_atr_based_bin_size(day_daily)
        
        # Assign bins
        for period in periods:
            if period.volume == 0:
                continue
            bin_centers = _create_price_bins(period.high, period.low, day_bin_size)
            if len(bin_centers) > 0:
                period.price_bins = {round(float(c), 2): 1 for c in bin_centers}
                period.tpo_count = len(bin_centers)
        
        day_dt = datetime.combine(day_date, time(0, 0)).replace(tzinfo=ET)
        daily_profiles.append(DailyTPOProfile(
            date=day_dt,
            symbol=symbol,
            periods=periods,
            bin_size=day_bin_size
        ))
    
    if len(daily_profiles) < 2:
        # Not enough data for composite
        latest = daily_profiles[0] if daily_profiles else None
        if latest:
            return CompositeTPOProfile(
                symbol=symbol,
                start_date=latest.date,
                end_date=latest.date,
                daily_profiles=daily_profiles,
                composite_poc=latest.poc,
                composite_vah=latest.vah,
                composite_val=latest.val,
                poc_migration='neutral',
                poc_slope=0.0
            )
        raise ValueError("Insufficient data for composite profile")
    
    # ─── Aggregate all TPOs across days for composite ───
    composite_bins: dict[float, int] = {}
    for dp in daily_profiles:
        for price, count in dp.all_price_bins.items():
            composite_bins[price] = composite_bins.get(price, 0) + count
    
    # Composite POC
    composite_poc = max(composite_bins.items(), key=lambda x: x[1])[0] if composite_bins else 0.0
    
    # Composite Value Area (70%)
    total_tpos = sum(composite_bins.values())
    target_tpos = total_tpos * VALUE_AREA_PCT
    
    sorted_prices = sorted(composite_bins.keys())
    poc_idx = sorted_prices.index(composite_poc)
    
    va_low_idx = poc_idx
    va_high_idx = poc_idx
    current_tpos = composite_bins[composite_poc]
    
    while current_tpos < target_tpos and (va_low_idx > 0 or va_high_idx < len(sorted_prices) - 1):
        tpos_down = composite_bins[sorted_prices[va_low_idx - 1]] if va_low_idx > 0 else 0
        tpos_up = composite_bins[sorted_prices[va_high_idx + 1]] if va_high_idx < len(sorted_prices) - 1 else 0
        
        if tpos_up >= tpos_down and va_high_idx < len(sorted_prices) - 1:
            va_high_idx += 1
            current_tpos += tpos_up
        elif va_low_idx > 0:
            va_low_idx -= 1
            current_tpos += tpos_down
        else:
            break
    
    composite_val = sorted_prices[va_low_idx]
    composite_vah = sorted_prices[va_high_idx]
    
    # ─── POC Migration via Linear Regression ───
    poc_prices = [dp.poc for dp in daily_profiles]
    x = np.arange(len(poc_prices))
    y = np.array(poc_prices)
    
    # Linear regression: y = mx + b
    slope, intercept = np.polyfit(x, y, 1)
    
    if slope > POC_MIGRATION_SLOPE_THRESHOLD:
        poc_migration: Literal['up', 'down', 'neutral'] = 'up'
    elif slope < -POC_MIGRATION_SLOPE_THRESHOLD:
        poc_migration = 'down'
    else:
        poc_migration = 'neutral'
    
    return CompositeTPOProfile(
        symbol=symbol,
        start_date=daily_profiles[0].date,
        end_date=daily_profiles[-1].date,
        daily_profiles=daily_profiles,
        composite_poc=composite_poc,
        composite_vah=composite_vah,
        composite_val=composite_val,
        poc_migration=poc_migration,
        poc_slope=float(slope)
    )


# ──────────────────────────────────────────────────────────────
# Convenience Functions
# ──────────────────────────────────────────────────────────────

def compute_tpo_from_yfinance(
    symbol: str,
    intraday_period: str = "1mo",
    intraday_interval: str = "30m",
    daily_period: str = "3mo"
) -> DailyTPOProfile | tuple[DailyTPOProfile, CompositeTPOProfile]:
    """Convenience function to fetch data from yfinance and compute TPO profile.
    
    Args:
        symbol: Ticker symbol
        intraday_period: Period for intraday data (e.g., "1mo", "3mo")
        intraday_interval: Interval for intraday data (must be "30m")
        daily_period: Period for daily data (e.g., "3mo", "6mo")
    
    Returns:
        DailyTPOProfile or (DailyTPOProfile, CompositeTPOProfile)
    """
    import yfinance as yf
    
    ticker = yf.Ticker(symbol)
    
    # Fetch intraday
    intraday = ticker.history(period=intraday_period, interval=intraday_interval)
    if intraday is None or len(intraday) == 0:
        raise ValueError(f"No intraday data for {symbol}")
    
    # Fetch daily
    daily = ticker.history(period=daily_period, interval="1d")
    if daily is None or len(daily) == 0:
        raise ValueError(f"No daily data for {symbol}")
    
    return compute_professional_tpo(intraday, daily, symbol)


def format_profile_summary(profile: DailyTPOProfile) -> str:
    """Format a human-readable summary of the daily TPO profile."""
    lines = [
        f"═══ TPO Volume Profile: {profile.symbol} ({profile.date.strftime('%Y-%m-%d')}) ═══",
        f"Bin Size: ${profile.bin_size:.4f}  |  Total TPOs: {profile.total_tpos}",
        "",
        f"📍 POC (Point of Control):      ${profile.poc:.2f}",
        f"📊 VAH (Value Area High):       ${profile.vah:.2f}",
        f"📊 VAL (Value Area Low):        ${profile.val:.2f}",
        f"📈 Value Area Width:            ${profile.vah - profile.val:.2f} ({(profile.vah - profile.val)/profile.poc*100:.1f}%)",
        "",
        f"🔵 Initial Balance (A-B):       ${profile.initial_balance_low:.2f} - ${profile.initial_balance_high:.2f}",
        f"   IB Range:                    ${profile.initial_balance_range:.2f}",
        f"   Range Extension:             {profile.range_extension_direction.upper()}",
        f"     ↑ Above IB:                ${profile.range_extension_up:.2f}" if profile.range_extension_up > 0 else "     ↑ Above IB:                None",
        f"     ↓ Below IB:                ${profile.range_extension_down:.2f}" if profile.range_extension_down > 0 else "     ↓ Below IB:                None",
        "",
        f"🎯 Profile Shape:               {profile.profile_shape}",
        "",
        "📋 Periods (A-M):"
    ]
    
    for period in profile.periods:
        ib_marker = " [IB]" if period.is_initial_balance else ""
        lines.append(
            f"  {period.letter}: ${period.low:.2f}-${period.high:.2f} "
            f"| Vol: {period.volume:,.0f} | TPOs: {period.tpo_count}{ib_marker}"
        )
    
    tails = profile.tails_excess
    if tails['buying_tails'] or tails['selling_tails']:
        lines.append("")
        lines.append("🦻 Tails / Excess:")
        if tails['buying_tails']:
            lines.append(f"  Buying Tails (support):     {[f'${p:.2f}' for p in tails['buying_tails']]}")
        if tails['selling_tails']:
            lines.append(f"  Selling Tails (resistance): {[f'${p:.2f}' for p in tails['selling_tails']]}")
    
    singles = profile.single_prints
    if singles:
        lines.append(f"\n⚡ Single Prints (weak participation): {len(singles)} total")
        # Show only extremes
        sorted_singles = sorted(singles, key=lambda x: x[1])
        if len(sorted_singles) > 6:
            lines.append(f"  Low:  {[f'{p[0]}@{p[1]:.2f}' for p in sorted_singles[:3]]}")
            lines.append(f"  High: {[f'{p[0]}@{p[1]:.2f}' for p in sorted_singles[-3:]]}")
        else:
            lines.append(f"  {[f'{p[0]}@{p[1]:.2f}' for p in sorted_singles]}")
    
    return "\n".join(lines)


def format_composite_summary(composite: CompositeTPOProfile) -> str:
    """Format a human-readable summary of the composite TPO profile."""
    lines = [
        f"═══ Composite TPO Profile: {composite.symbol} ({composite.start_date.strftime('%Y-%m-%d')} to {composite.end_date.strftime('%Y-%m-%d')}) ═══",
        f"Days in Composite: {composite.days_in_composite}",
        "",
        f"📍 Composite POC:              ${composite.composite_poc:.2f}",
        f"📊 Composite VAH:              ${composite.composite_vah:.2f}",
        f"📊 Composite VAL:              ${composite.composite_val:.2f}",
        f"📈 Composite VA Width:         ${composite.value_area_width:.2f} ({(composite.value_area_width/composite.composite_poc*100):.1f}%)",
        "",
        f"📈 POC Migration:              {composite.poc_migration.upper()} (slope: {composite.poc_slope:.6f})",
        "",
        "📅 Daily POCs:"
    ]
    
    for i, (dp, poc) in enumerate(zip(composite.daily_profiles, composite.poc_prices)):
        date_str = dp.date.strftime('%m/%d')
        shape = dp.profile_shape
        lines.append(f"  {date_str}: ${poc:.2f} [{shape}]")
    
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────
# Module Exports
# ──────────────────────────────────────────────────────────────

__all__ = [
    # Dataclasses
    "TPOPeriod",
    "DailyTPOProfile",
    "CompositeTPOProfile",
    # Main function
    "compute_professional_tpo",
    # Convenience
    "compute_tpo_from_yfinance",
    "format_profile_summary",
    "format_composite_summary",
    # Constants
    "RTH_START",
    "RTH_END",
    "TPO_PERIOD_MINUTES",
    "RTH_PERIODS",
    "TPO_LETTERS",
    "VALUE_AREA_PCT",
]