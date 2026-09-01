"""Analyst revision tracker (D-46 PR 3).

The elite trader tracks analyst REVISIONS, not just the current consensus.
A target raised from $180 to $200 in 5 days is a much stronger signal
than "consensus is $200." yfinance gives us today's target; we have to
build the history ourselves by snapshotting daily.

This module:
  - records today's target_mean_price after each successful ticker analysis
  - looks back 1d/5d/30d for revisions
  - surfaces a finding when target has been raised (upgrade momentum) or
    lowered (downgrade momentum) by >5% in the lookback window

Storage: DuckDB table `analyst_targets` (see core/database.py).
Threading: callers may invoke from a background thread; uses its own
short-lived connection per call (cheap on DuckDB).
"""

from __future__ import annotations

import datetime as _dt
import logging
import threading
from dataclasses import dataclass, field
from typing import Any

from backend.app.core.database import get_db

log = logging.getLogger(__name__)

# Lock to serialize writes (DuckDB is fine with concurrent reads, but
# we want the snapshot table to be clean)
_write_lock = threading.Lock()


@dataclass
class AnalystRevision:
    """The change in target_mean_price between two snapshots."""
    symbol: str
    snapshot_date: _dt.date
    prev_date: _dt.date | None
    prev_target: float | None
    current_target: float | None
    change_abs: float | None  # current - prev (in $)
    change_pct: float | None  # (current - prev) / prev * 100
    window_days: int
    findings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "snapshot_date": self.snapshot_date.isoformat(),
            "prev_date": self.prev_date.isoformat() if self.prev_date else None,
            "prev_target": self.prev_target,
            "current_target": self.current_target,
            "change_abs": self.change_abs,
            "change_pct": self.change_pct,
            "window_days": self.window_days,
            "findings": self.findings,
        }


def record_today_target(
    symbol: str,
    target_mean_price: float | None,
    target_low_price: float | None = None,
    target_high_price: float | None = None,
    num_analysts: int | None = None,
    consensus_rating: str | None = None,
) -> None:
    """Snapshot today's analyst target for a symbol.

    Called from the orchestrator after a successful ticker analysis. Uses
    UPSERT (INSERT OR REPLACE) so calling twice on the same day is safe.
    """
    if target_mean_price is None:
        return  # nothing to record

    today = _dt.date.today()
    with _write_lock:
        try:
            with get_db() as con:
                con.execute(
                    """
                    INSERT OR REPLACE INTO analyst_targets (
                        symbol, snapshot_date, target_mean_price,
                        target_low_price, target_high_price, num_analysts,
                        consensus_rating, recorded_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    [
                        symbol, today, target_mean_price,
                        target_low_price, target_high_price, num_analysts,
                        consensus_rating,
                    ],
                )
        except Exception:
            log.exception("record_today_target_failed", extra={"symbol": symbol})


def get_latest_snapshot(symbol: str) -> tuple[_dt.date | None, float | None]:
    """Return the (date, target_mean_price) of the most recent snapshot for `symbol`."""
    try:
        with get_db() as con:
            row = con.execute(
                """
                SELECT snapshot_date, target_mean_price
                FROM analyst_targets
                WHERE symbol = ?
                ORDER BY snapshot_date DESC
                LIMIT 1
                """,
                [symbol],
            ).fetchone()
            if row is None:
                return None, None
            return row[0], float(row[1])
    except Exception:
        log.exception("get_latest_snapshot_failed", extra={"symbol": symbol})
        return None, None


def get_revision(
    symbol: str,
    window_days: int = 5,
) -> AnalystRevision | None:
    """Compute the revision between the most recent snapshot and the
    snapshot N days before it (or the oldest available, whichever is newer).

    Returns None if there are < 2 snapshots for the symbol (need history
    to detect a revision).

    window_days: how many days to look back (1d, 5d, 30d).
    """
    try:
        with get_db() as con:
            # D-47: ensure the table exists before querying (in case
            # get_revision is called from a context that didn't run
            # initialize_database — e.g. the catalyst filter on a
            # fresh worktree or test DB).
            con.execute("""
                CREATE TABLE IF NOT EXISTS analyst_targets (
                    symbol VARCHAR NOT NULL,
                    snapshot_date DATE NOT NULL,
                    target_mean_price DOUBLE,
                    target_low_price DOUBLE,
                    target_high_price DOUBLE,
                    num_analysts INTEGER,
                    consensus_rating VARCHAR,
                    recorded_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (symbol, snapshot_date)
                )
            """)
            # Get the latest snapshot
            latest = con.execute(
                """
                SELECT snapshot_date, target_mean_price
                FROM analyst_targets
                WHERE symbol = ?
                ORDER BY snapshot_date DESC
                LIMIT 1
                """,
                [symbol],
            ).fetchone()
            if latest is None:
                return None
            latest_date, latest_target = latest[0], float(latest[1])

            # Get the snapshot closest to (latest_date - window_days).
            # If that snapshot is too old ( > window_days+2), still
            # return it but flag the actual elapsed days.
            target_date = latest_date - _dt.timedelta(days=window_days)
            prior = con.execute(
                """
                SELECT snapshot_date, target_mean_price
                FROM analyst_targets
                WHERE symbol = ? AND snapshot_date <= ?
                ORDER BY snapshot_date DESC
                LIMIT 1
                """,
                [symbol, target_date],
            ).fetchone()
            if prior is None:
                return None
            prior_date, prior_target = prior[0], float(prior[1])

            change_abs = round(latest_target - prior_target, 4)
            change_pct = round((change_abs / prior_target) * 100, 2) if prior_target else None
            actual_days = (latest_date - prior_date).days

            rev = AnalystRevision(
                symbol=symbol,
                snapshot_date=latest_date,
                prev_date=prior_date,
                prev_target=prior_target,
                current_target=latest_target,
                change_abs=change_abs,
                change_pct=change_pct,
                window_days=actual_days,
            )

            # Generate findings (elite trader's interpretation)
            if change_pct is not None:
                if change_pct >= 5.0:
                    rev.findings.append(
                        f"📈 Analyst upgrade: target raised by {change_pct:+.1f}% "
                        f"(${prior_target:.2f} → ${latest_target:.2f}) over {actual_days}d — "
                        f"upgrade momentum, smart money is increasing conviction"
                    )
                elif change_pct <= -5.0:
                    rev.findings.append(
                        f"⚠️ Analyst downgrade: target lowered by {change_pct:+.1f}% "
                        f"(${prior_target:.2f} → ${latest_target:.2f}) over {actual_days}d — "
                        f"downgrade momentum, institutional sentiment deteriorating"
                    )
                else:
                    rev.findings.append(
                        f"📊 Analyst target stable ({change_pct:+.1f}% over {actual_days}d, "
                        f"${prior_target:.2f} → ${latest_target:.2f})"
                    )
            return rev
    except Exception:
        log.exception("get_revision_failed", extra={"symbol": symbol, "window_days": window_days})
        return None


def clear_today_snapshot(symbol: str) -> None:
    """For tests: remove today's snapshot so it can be re-recorded."""
    today = _dt.date.today()
    try:
        with get_db() as con:
            con.execute(
                "DELETE FROM analyst_targets WHERE symbol = ? AND snapshot_date = ?",
                [symbol, today],
            )
    except Exception:
        log.exception("clear_today_snapshot_failed", extra={"symbol": symbol})
