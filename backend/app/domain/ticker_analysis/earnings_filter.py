#!/usr/bin/env python3
"""Earnings calendar lookup for the screener path.

D-44 (G14 Gap 1): The screener path (POST /api/v1/screen/tv) doesn't
go through the per-ticker orchestrator and therefore doesn't have
access to the EarningsAnalysis module's days_until_earnings field.

D-48 (PR 2): Replaced the hand-curated JSON with a yfinance-backed
implementation. The JSON file is now a *manual override* — if yfinance
gets a date wrong, the user can fix it by adding the ticker to the
file. Otherwise, we fetch from yfinance directly.

Why yfinance over a free API:
  - Already integrated with the rest of the system
  - .info has `earningsTimestampStart` (next earnings) directly
  - Cached by the per-ticker module so the screener doesn't double-fetch
  - No API key required

How it works:
  1. Check the JSON override file (manual fixes)
  2. If not in JSON, check the yfinance info cache (in-process LRU)
  3. If still not cached, call yfinance and cache for 24h
  4. Return (binary_risk, earnings_date) for the 5d window

Safe default: missing/empty/invalid → (False, None) — no false warnings.
"""
from __future__ import annotations

import datetime as _dt
import json
import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yfinance as yf

log = logging.getLogger(__name__)

_CALENDAR_PATH = Path(__file__).resolve().parents[3] / "data" / "earnings_calendar.json"

# In-process cache for yfinance earnings dates.
# Key: (symbol, day_of_year) — invalidate daily so refresh is automatic
# every market open. Value: (timestamp, optional_earnings_date_iso)
_calendar_cache: dict[str, tuple[float, Optional[str]]] = {}
_cache_lock = threading.Lock()
_CACHE_TTL = 86400  # 24h — earnings dates are mostly stable week-to-week


def _load_manual_overrides() -> list[dict]:
    """Load the JSON file (manual overrides for known-wrong yfinance dates)."""
    try:
        mtime = _CALENDAR_PATH.stat().st_mtime
    except FileNotFoundError:
        return []
    with _cache_lock:
        # Reuse the JSON-only cache for the file
        global _manual_cache, _manual_cache_mtime
        if _manual_cache is None or mtime > _manual_cache_mtime:
            try:
                with _CALENDAR_PATH.open() as f:
                    _manual_cache = json.load(f)
                if not isinstance(_manual_cache, list):
                    _manual_cache = []
            except (OSError, json.JSONDecodeError):
                _manual_cache = []
            _manual_cache_mtime = mtime
    return _manual_cache or []


_manual_cache: Optional[list[dict]] = None
_manual_cache_mtime: float = 0.0


def _fetch_yfinance_earnings(symbol: str) -> Optional[str]:
    """Fetch the next earnings date from yfinance. Returns ISO date or None.

    Uses .info['earningsTimestampStart'] (next earnings) first, falling
    back to .info['earningsTimestamp'] (most recent). The two are often
    the same for recently-printed names.

    Cached for 24h per symbol. Caches the result of "no data" too (None)
    so we don't hammer yfinance for tickers that genuinely have no
    scheduled earnings.
    """
    now = time.monotonic()
    with _cache_lock:
        cached = _calendar_cache.get(symbol)
        if cached and (now - cached[0]) < _CACHE_TTL:
            return cached[1]

    # No cached value (or stale). Fetch from yfinance.
    try:
        info = yf.Ticker(symbol).info or {}
    except Exception as exc:
        log.warning("yfinance_earnings_fetch_failed",
                    extra={"symbol": symbol, "error": str(exc)})
        with _cache_lock:
            _calendar_cache[symbol] = (now, None)
        return None

    ts = info.get("earningsTimestampStart") or info.get("earningsTimestamp")
    if not ts:
        with _cache_lock:
            _calendar_cache[symbol] = (now, None)
        return None

    try:
        dt = datetime.fromtimestamp(int(ts), tz=timezone.utc)
        iso = dt.date().isoformat()
    except (ValueError, TypeError, OSError):
        with _cache_lock:
            _calendar_cache[symbol] = (now, None)
        return None

    with _cache_lock:
        _calendar_cache[symbol] = (now, iso)
    return iso


def _days_until(report_date_iso: str) -> int | None:
    """Return the number of calendar days from now to the report date, or None.

    Compares date-to-date (not datetime-to-datetime) so a 0d result
    means "earnings is today" regardless of the user's local time vs UTC.

    Examples (today = 2026-09-01):
      earnings = 2026-09-01 → 0 days (today)
      earnings = 2026-09-03 → 2 days
      earnings = 2026-08-30 → -2 days (already reported)
    """
    try:
        report_date = datetime.fromisoformat(report_date_iso).date()
    except (ValueError, TypeError):
        return None
    today = datetime.now(timezone.utc).date()
    return (report_date - today).days


def get_binary_risk(
    symbol: str,
    window_days: int = 5,
    *,
    allow_yfinance: bool = True,
) -> tuple[bool, Optional[str]]:
    """Return (binary_risk, earnings_date) for the given symbol.

    Resolution order:
      1. Manual override (JSON file) — wins if present
      2. yfinance (cached) — fallback, unless ``allow_yfinance=False``
      3. None — safe default (False, None)

    ``allow_yfinance=False`` is used by batch screener paths: it keeps the
    lookup in-process instead of making one Yahoo request per ticker. The
    deep ticker-analysis path keeps the default fallback.

    binary_risk is True if the symbol reports earnings in the next
    `window_days` calendar days.
    """
    # 1. Manual override
    for entry in _load_manual_overrides():
        if not isinstance(entry, dict):
            continue
        if entry.get("ticker", "").upper() != symbol.upper():
            continue
        rd = entry.get("report_date")
        if not rd:
            continue
        days = _days_until(rd)
        if days is not None and 0 <= days <= window_days:
            return True, rd
        # Manual override exists but earnings is not in window — fall through
        # so yfinance can still flag if its date is different (the override
        # may have been added because yfinance was wrong but for a different date)
        break

    if not allow_yfinance:
        return False, None

    # 2. yfinance
    rd = _fetch_yfinance_earnings(symbol)
    if rd is None:
        return False, None
    days = _days_until(rd)
    if days is None:
        return False, None
    if 0 <= days <= window_days:
        return True, rd
    return False, None


def clear_cache() -> None:
    """For tests: clear the yfinance cache and manual override cache."""
    with _cache_lock:
        _calendar_cache.clear()
    global _manual_cache, _manual_cache_mtime
    _manual_cache = None
    _manual_cache_mtime = 0.0
