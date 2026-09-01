"""Tests for the analyst revision tracker (D-46 PR 3).

The elite trader watches for analyst REVISIONS, not just the current
target. A target raised from $180 to $200 in 5 days is a much stronger
signal than 'consensus is $200.' We track this by snapshotting today's
target after each ticker analysis and looking up the revision on the
next request.

These tests use an in-memory DuckDB and a monkeypatched get_db so they
don't depend on the live database file.
"""

from __future__ import annotations

import datetime as _dt
import sys
from typing import Any
from unittest.mock import patch, MagicMock

import duckdb
import pytest

from backend.app.infrastructure import analyst_revisions


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def in_memory_db(monkeypatch):
    """Replace get_db() with an in-memory DuckDB connection.

    The DDL is applied fresh on each test so the analyst_targets table
    is always present.
    """
    # Create a fresh in-memory connection
    conn = duckdb.connect(":memory:")
    # Apply the DDL inline (mirror core/database.py)
    conn.execute("""
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

    # Patch get_db to return a context manager that yields our conn
    from contextlib import contextmanager

    @contextmanager
    def fake_get_db():
        yield conn

    monkeypatch.setattr(analyst_revisions, "get_db", fake_get_db)
    return conn


# ── record_today_target ─────────────────────────────────────────────────


class TestRecordTodayTarget:
    def test_records_target(self, in_memory_db):
        analyst_revisions.record_today_target("AAPL", target_mean_price=200.0)
        row = in_memory_db.execute(
            "SELECT symbol, target_mean_price FROM analyst_targets WHERE symbol = ?",
            ["AAPL"],
        ).fetchone()
        assert row is not None
        assert row[0] == "AAPL"
        assert row[1] == 200.0

    def test_upsert_on_same_day(self, in_memory_db):
        analyst_revisions.record_today_target("AAPL", target_mean_price=200.0)
        analyst_revisions.record_today_target("AAPL", target_mean_price=210.0)
        rows = in_memory_db.execute(
            "SELECT target_mean_price FROM analyst_targets WHERE symbol = ?",
            ["AAPL"],
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == 210.0  # updated to latest

    def test_skips_none_target(self, in_memory_db):
        analyst_revisions.record_today_target("AAPL", target_mean_price=None)
        rows = in_memory_db.execute(
            "SELECT * FROM analyst_targets WHERE symbol = ?", ["AAPL"]
        ).fetchall()
        assert len(rows) == 0

    def test_full_record(self, in_memory_db):
        analyst_revisions.record_today_target(
            symbol="AAPL",
            target_mean_price=200.0,
            target_low_price=170.0,
            target_high_price=230.0,
            num_analysts=15,
            consensus_rating="buy",
        )
        row = in_memory_db.execute(
            "SELECT target_low_price, target_high_price, num_analysts, consensus_rating "
            "FROM analyst_targets WHERE symbol = ?",
            ["AAPL"],
        ).fetchone()
        assert row == (170.0, 230.0, 15, "buy")


# ── get_latest_snapshot ─────────────────────────────────────────────────


class TestGetLatestSnapshot:
    def test_returns_none_for_unknown(self, in_memory_db):
        d, t = analyst_revisions.get_latest_snapshot("UNKNOWN")
        assert d is None
        assert t is None

    def test_returns_latest(self, in_memory_db):
        in_memory_db.execute(
            "INSERT INTO analyst_targets (symbol, snapshot_date, target_mean_price) "
            "VALUES (?, ?, ?), (?, ?, ?)",
            ["AAPL", _dt.date(2026, 8, 25), 180.0, "AAPL", _dt.date(2026, 8, 30), 200.0],
        )
        d, t = analyst_revisions.get_latest_snapshot("AAPL")
        assert d == _dt.date(2026, 8, 30)
        assert t == 200.0


# ── get_revision ────────────────────────────────────────────────────────


class TestGetRevision:
    def test_no_snapshots_returns_none(self, in_memory_db):
        rev = analyst_revisions.get_revision("UNKNOWN", window_days=5)
        assert rev is None

    def test_one_snapshot_returns_none(self, in_memory_db):
        in_memory_db.execute(
            "INSERT INTO analyst_targets (symbol, snapshot_date, target_mean_price) "
            "VALUES (?, ?, ?)",
            ["AAPL", _dt.date(2026, 8, 30), 200.0],
        )
        rev = analyst_revisions.get_revision("AAPL", window_days=5)
        assert rev is None

    def test_upgrade_revision(self, in_memory_db):
        # Snapshot 5 days ago at $180, today at $200 → +11.1% upgrade
        in_memory_db.execute(
            "INSERT INTO analyst_targets (symbol, snapshot_date, target_mean_price) "
            "VALUES (?, ?, ?), (?, ?, ?)",
            ["AAPL", _dt.date(2026, 8, 25), 180.0, "AAPL", _dt.date(2026, 8, 30), 200.0],
        )
        rev = analyst_revisions.get_revision("AAPL", window_days=5)
        assert rev is not None
        assert rev.change_abs == pytest.approx(20.0)
        assert rev.change_pct == pytest.approx(11.11)
        # Should produce an upgrade finding
        assert any("upgrade" in f.lower() for f in rev.findings)
        assert any("raised" in f.lower() for f in rev.findings)

    def test_downgrade_revision(self, in_memory_db):
        # 5 days ago at $200, today at $180 → -10% downgrade
        in_memory_db.execute(
            "INSERT INTO analyst_targets (symbol, snapshot_date, target_mean_price) "
            "VALUES (?, ?, ?), (?, ?, ?)",
            ["AAPL", _dt.date(2026, 8, 25), 200.0, "AAPL", _dt.date(2026, 8, 30), 180.0],
        )
        rev = analyst_revisions.get_revision("AAPL", window_days=5)
        assert rev is not None
        assert rev.change_pct == pytest.approx(-10.0)
        # Should produce a downgrade finding
        assert any("downgrade" in f.lower() for f in rev.findings)

    def test_stable_revision(self, in_memory_db):
        # 5 days ago at $200, today at $202 → +1% (stable)
        in_memory_db.execute(
            "INSERT INTO analyst_targets (symbol, snapshot_date, target_mean_price) "
            "VALUES (?, ?, ?), (?, ?, ?)",
            ["AAPL", _dt.date(2026, 8, 25), 200.0, "AAPL", _dt.date(2026, 8, 30), 202.0],
        )
        rev = analyst_revisions.get_revision("AAPL", window_days=5)
        assert rev is not None
        assert rev.change_pct == pytest.approx(1.0)
        # Should produce a stable finding
        assert any("stable" in f.lower() for f in rev.findings)

    def test_window_looks_back_5d(self, in_memory_db):
        # 10 days ago at $180, today at $200 → revision exists but the
        # 5d window only looks at the most recent 5d snapshot
        in_memory_db.execute(
            "INSERT INTO analyst_targets (symbol, snapshot_date, target_mean_price) "
            "VALUES (?, ?, ?), (?, ?, ?)",
            ["AAPL", _dt.date(2026, 8, 20), 180.0, "AAPL", _dt.date(2026, 8, 30), 200.0],
        )
        # The 5d-window lookup finds the snapshot at or before 2026-08-25
        # = the 2026-08-20 snapshot (only one in the DB)
        rev = analyst_revisions.get_revision("AAPL", window_days=5)
        assert rev is not None
        assert rev.window_days == 10  # actual days between snapshots

    def test_to_dict(self, in_memory_db):
        in_memory_db.execute(
            "INSERT INTO analyst_targets (symbol, snapshot_date, target_mean_price) "
            "VALUES (?, ?, ?), (?, ?, ?)",
            ["AAPL", _dt.date(2026, 8, 25), 180.0, "AAPL", _dt.date(2026, 8, 30), 200.0],
        )
        rev = analyst_revisions.get_revision("AAPL", window_days=5)
        d = rev.to_dict()
        assert d["symbol"] == "AAPL"
        assert d["change_pct"] == pytest.approx(11.11)
        assert d["window_days"] == 5
        assert "findings" in d
