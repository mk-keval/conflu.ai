#!/usr/bin/env python3
"""Earnings calendar lookup for the screener path.

D-44 (G14 Gap 1): The screener path (POST /api/v1/screen/tv) doesn't
go through the per-ticker orchestrator and therefore doesn't have
access to the EarningsAnalysis module's days_until_earnings field.
Instead, this module reads from a hand-curated JSON file
(backend/app/data/earnings_calendar.json) that the user maintains.

The file shape:
  [
    {"ticker": "AAPL", "report_date": "2026-10-30", "session": "after-close"},
    ...
  ]

Missing file or empty list => all tickers return binary_risk=False
(safe default — no false warnings).
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_CALENDAR_PATH = Path(__file__).resolve().parents[3] / "data" / "earnings_calendar.json"

_calendar_cache: Optional[list[dict]] = None
_calendar_cache_mtime: float = 0.0
_cache_lock = threading.Lock()


def _load_calendar() -> list[dict]:
    """Load the earnings calendar from disk, with a small TTL cache."""
    global _calendar_cache, _calendar_cache_mtime
    try:
        mtime = _CALENDAR_PATH.stat().st_mtime
    except FileNotFoundError:
        return []
    with _cache_lock:
        if _calendar_cache is None or mtime > _calendar_cache_mtime:
            try:
                with _CALENDAR_PATH.open() as f:
                    _calendar_cache = json.load(f)
                if not isinstance(_calendar_cache, list):
                    _calendar_cache = []
            except (OSError, json.JSONDecodeError):
                _calendar_cache = []
            _calendar_cache_mtime = mtime
    return _calendar_cache or []


def _days_until(report_date_iso: str) -> int | None:
    """Return the number of calendar days from now to the report date, or None."""
    try:
        report_dt = datetime.fromisoformat(report_date_iso).replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None
    now = datetime.now(timezone.utc)
    delta = report_dt - now
    return delta.days


def get_binary_risk(symbol: str, window_days: int = 5) -> tuple[bool, Optional[str]]:
    """Return (binary_risk, earnings_date) for the given symbol.

    binary_risk is True if the symbol reports earnings in the next
    `window_days` calendar days. earnings_date is the ISO date string
    if known, else None.

    Safe default (False, None) when the calendar file is missing or
    malformed — no false warnings.
    """
    calendar = _load_calendar()
    if not calendar:
        return False, None
    for entry in calendar:
        if not isinstance(entry, dict):
            continue
        if entry.get("ticker", "").upper() != symbol.upper():
            continue
        report_date = entry.get("report_date")
        if not report_date:
            continue
        days = _days_until(report_date)
        if days is None:
            continue
        if 0 <= days <= window_days:
            return True, report_date
    return False, None
