"""Persistent watchlist service (D-49 PR 1).

The watchlist was previously a frontend-only Zustand store — adding
to the watchlist in the UI didn't persist to the backend, so verdict
change tracking wasn't possible.

This module adds a simple in-process watchlist service that:
  - stores a single watchlist per session (or per "user" — for now
    we have one global watchlist; multi-user is a future PR)
  - re-analyzes all tickers when the user clicks "Update"
  - compares new verdicts to the last-known verdict
  - emits an alert via AlertService if a verdict changed

In-process storage (no DuckDB table) — per the user's preference to
avoid overhead. The watchlist resets on server restart, but the alerts
emit at refresh time so the user still sees what changed.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Optional

log = logging.getLogger(__name__)


class WatchlistService:
    """In-process watchlist + verdict-change detector.

    Stores:
      - watchlist: list of symbols (the user's tickers)
      - last_verdict: dict[symbol, {"action": str, "conviction": int, "recorded_at": iso}]
      - last_refresh: ISO timestamp of the most recent refresh

    All operations are thread-safe via a single lock.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._watchlist: list[str] = []
        self._last_verdict: dict[str, dict[str, Any]] = {}
        self._last_refresh: str | None = None
        self._last_refresh_alerts: list[dict[str, Any]] = []  # alerts from the most recent refresh

    # ── Watchlist CRUD ──────────────────────────────────────────────

    def get_watchlist(self) -> list[str]:
        with self._lock:
            return list(self._watchlist)

    def add_tickers(self, symbols: list[str]) -> list[str]:
        """Add tickers to the watchlist. Returns the current watchlist after."""
        with self._lock:
            for sym in symbols:
                s = sym.strip().upper()
                if s and s not in self._watchlist:
                    self._watchlist.append(s)
            return list(self._watchlist)

    def remove_ticker(self, symbol: str) -> list[str]:
        with self._lock:
            s = symbol.strip().upper()
            if s in self._watchlist:
                self._watchlist.remove(s)
            self._last_verdict.pop(s, None)  # clear stale verdict data
            return list(self._watchlist)

    def clear(self) -> None:
        with self._lock:
            self._watchlist.clear()
            self._last_verdict.clear()
            self._last_refresh = None
            self._last_refresh_alerts.clear()

    # ── Verdict tracking ────────────────────────────────────────────

    def get_last_verdict(self, symbol: str) -> dict[str, Any] | None:
        with self._lock:
            return self._last_verdict.get(symbol.upper())

    def get_all_last_verdicts(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return dict(self._last_verdict)

    def record_verdicts(self, new_verdicts: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        """Compare new verdicts to the last-known verdict for each symbol.

        Returns a list of verdict-change alerts (empty list if no changes).
        Each alert is a dict ready for AlertService:
          {
            "symbol": str,
            "from_action": str | None,
            "to_action": str,
            "from_conviction": int | None,
            "to_conviction": int,
            "timestamp": iso,
          }
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        alerts: list[dict[str, Any]] = []
        with self._lock:
            for sym, new_v in new_verdicts.items():
                sym_u = sym.upper()
                old = self._last_verdict.get(sym_u)
                old_action = old.get("action") if old else None
                old_conv = old.get("conviction") if old else None
                new_action = new_v.get("action")
                new_conv = new_v.get("conviction")
                # Detect a change: action changed OR conviction moved >= 2
                if (
                    old_action is not None
                    and (old_action != new_action or abs(int(new_conv or 0) - int(old_conv or 0)) >= 2)
                ):
                    alerts.append({
                        "symbol": sym_u,
                        "from_action": old_action,
                        "to_action": new_action,
                        "from_conviction": int(old_conv or 0),
                        "to_conviction": int(new_conv or 0),
                        "timestamp": now_iso,
                    })
                # Update last-known
                self._last_verdict[sym_u] = {
                    "action": new_action,
                    "conviction": new_conv,
                    "recorded_at": now_iso,
                }
        return alerts

    def get_last_refresh_alerts(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._last_refresh_alerts)

    def get_last_refresh_time(self) -> str | None:
        with self._lock:
            return self._last_refresh

    def set_last_refresh(
        self,
        alerts: list[dict[str, Any]],
        refresh_time: str | None = None,
    ) -> None:
        with self._lock:
            self._last_refresh_alerts = list(alerts)
            self._last_refresh = refresh_time or datetime.now(timezone.utc).isoformat()


# ── Module-level singleton ────────────────────────────────────────────

_watchlist_service: WatchlistService | None = None
_service_lock = threading.Lock()


def get_watchlist_service() -> WatchlistService:
    """Get the module-level singleton watchlist service."""
    global _watchlist_service
    with _service_lock:
        if _watchlist_service is None:
            _watchlist_service = WatchlistService()
    return _watchlist_service
