"""Unusual options activity detector (D-46 PR 5).

The elite trader watches for unusual options activity — when call volume
is multiple times the open interest, someone is opening new positions
aggressively. Combined with a call/put volume ratio >2, that's a
bullish signal (smart money buying calls, not just covering).

yfinance gives us options chain data via ticker.option_chain() which
returns Calls and Puts DataFrames with volume + openInterest per strike.
We sum across the nearest expiration (most actionable) and check
for the unusual activity signal.

Thresholds:
  - call_volume / put_volume ratio > 2.0  (call buying dominates)
  - call_volume > 1.5x call_open_interest   (new positions, not closing)
  - Same for puts in the opposite direction (bearish signal)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
import yfinance as yf

log = logging.getLogger(__name__)

# Detection thresholds
CALL_PUT_RATIO_THRESHOLD = 2.0  # ratio above this = bullish (or bearish if puts)
VOLUME_OI_RATIO_THRESHOLD = 1.5  # volume > 1.5x OI = new positions
MIN_TOTAL_VOLUME = 1000  # ignore very illiquid names (noise)


@dataclass
class OptionsFlow:
    """Detected unusual options activity."""
    symbol: str
    expiration: str | None
    call_volume: int
    put_volume: int
    call_open_interest: int
    put_open_interest: int
    call_put_volume_ratio: float
    call_volume_oi_ratio: float
    put_volume_oi_ratio: float
    bias: str  # "bullish" / "bearish" / "neutral"
    findings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "expiration": self.expiration,
            "call_volume": self.call_volume,
            "put_volume": self.put_volume,
            "call_open_interest": self.call_open_interest,
            "put_open_interest": self.put_open_interest,
            "call_put_volume_ratio": round(self.call_put_volume_ratio, 2),
            "call_volume_oi_ratio": round(self.call_volume_oi_ratio, 2),
            "put_volume_oi_ratio": round(self.put_volume_oi_ratio, 2),
            "bias": self.bias,
            "findings": self.findings,
        }


def _sum_columns(df: pd.DataFrame, columns: list[str]) -> tuple[int, int]:
    """Sum the (volume, openInterest) for the given columns. Returns 0s on missing/NaN."""
    if df is None or df.empty:
        return 0, 0
    vol = 0
    oi = 0
    if "volume" in columns:
        vol = int(pd.to_numeric(df.get("volume"), errors="coerce").fillna(0).sum())
    if "openInterest" in columns:
        oi = int(pd.to_numeric(df.get("openInterest"), errors="coerce").fillna(0).sum())
    return vol, oi


def detect_unusual_options_activity(symbol: str) -> OptionsFlow | None:
    """Pull the nearest expiration options chain and detect unusual activity.

    Returns None if:
      - yfinance returns no options data
      - Total volume < MIN_TOTAL_VOLUME (too illiquid to be a real signal)
      - No unusual activity (call/put ratio or vol/OI ratio not extreme)

    The nearest expiration is the most actionable — institutions rarely
    trade 6+ months out for a quick swing trade.
    """
    try:
        y = yf.Ticker(symbol)
        if not y.options:
            return None
        # Nearest expiration
        nearest_exp = y.options[0]
        chain = y.option_chain(nearest_exp)
        calls = chain.calls
        puts = chain.puts
    except Exception:
        log.exception("options_fetch_failed", extra={"symbol": symbol})
        return None

    if (calls is None or calls.empty) and (puts is None or puts.empty):
        return None

    cols = ["volume", "openInterest"]
    call_vol, call_oi = _sum_columns(calls, cols)
    put_vol, put_oi = _sum_columns(puts, cols)

    total_vol = call_vol + put_vol
    if total_vol < MIN_TOTAL_VOLUME:
        return None

    # Compute ratios (avoid division by zero)
    call_put_vol_ratio = call_vol / put_vol if put_vol > 0 else float("inf") if call_vol > 0 else 0.0
    call_vol_oi_ratio = call_vol / call_oi if call_oi > 0 else float("inf") if call_vol > 0 else 0.0
    put_vol_oi_ratio = put_vol / put_oi if put_oi > 0 else float("inf") if put_vol > 0 else 0.0

    # Determine bias
    bullish = (
        call_put_vol_ratio > CALL_PUT_RATIO_THRESHOLD
        and call_vol_oi_ratio > VOLUME_OI_RATIO_THRESHOLD
    )
    bearish = (
        call_put_vol_ratio < (1.0 / CALL_PUT_RATIO_THRESHOLD)
        and put_vol_oi_ratio > VOLUME_OI_RATIO_THRESHOLD
    )

    if not bullish and not bearish:
        return None  # not unusual enough

    bias = "bullish" if bullish else "bearish"
    flow = OptionsFlow(
        symbol=symbol,
        expiration=nearest_exp,
        call_volume=call_vol,
        put_volume=put_vol,
        call_open_interest=call_oi,
        put_open_interest=put_oi,
        call_put_volume_ratio=call_put_vol_ratio,
        call_volume_oi_ratio=call_vol_oi_ratio,
        put_volume_oi_ratio=put_vol_oi_ratio,
        bias=bias,
    )
    if bias == "bullish":
        flow.findings.append(
            f"📈 Unusual call activity: {call_vol:,} calls vs {put_vol:,} puts "
            f"(ratio {call_put_vol_ratio:.1f}x), call vol {call_vol_oi_ratio:.1f}x OI "
            f"— smart money opening bullish positions, expiration {nearest_exp}"
        )
    else:
        flow.findings.append(
            f"📉 Unusual put activity: {put_vol:,} puts vs {call_vol:,} calls "
            f"(ratio {1.0/call_put_vol_ratio if call_put_vol_ratio else 0:.1f}x), "
            f"put vol {put_vol_oi_ratio:.1f}x OI — smart money opening bearish "
            f"positions, expiration {nearest_exp}"
        )
    return flow
