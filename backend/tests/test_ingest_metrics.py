"""Tests for ingestion metrics and reporting."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import duckdb
import pytest

from backend.app.infrastructure.ingest.metrics import (
    IngestionMetrics,
    load_latest_health,
    save_health,
)
from backend.app.infrastructure.ingest.models import ScanResult


def test_metrics_initialization() -> None:
    """Correlation ID is set, started_at is UTC."""
    m = IngestionMetrics()
    assert m.correlation_id is not None
    assert len(m.correlation_id) > 0
    assert m.started_at.tzinfo == timezone.utc


def test_metrics_track_time() -> None:
    """Duration is populated after context manager."""
    m = IngestionMetrics()
    with m.track_time():
        pass
    assert m._duration_ms is not None
    assert m._duration_ms >= 0


def test_metrics_record_scan_success() -> None:
    """record_scan increments scans_succeeded and symbols_processed."""
    m = IngestionMetrics()
    sr = ScanResult(
        market="america",
        tickers_requested=100,
        tickers_received=95,
        duration_ms=1500.0,
        success=True,
    )
    m.record_scan(sr)
    assert m.scans_succeeded == 1
    assert m.symbols_processed == 95
    assert m.scans_failed == 0


def test_metrics_record_scan_failure() -> None:
    """record_scan increments scans_failed and symbols_failed."""
    m = IngestionMetrics()
    sr = ScanResult(
        market="america",
        tickers_requested=100,
        tickers_received=0,
        duration_ms=500.0,
        success=False,
        error="Timeout",
    )
    m.record_scan(sr)
    assert m.scans_failed == 1
    assert m.symbols_failed == 100


def test_metrics_record_write() -> None:
    """record_write increments candles_written, bytes_written, rows_discarded."""
    m = IngestionMetrics()
    m.record_write(500, 1024, 10)
    assert m.candles_written == 500
    assert m.bytes_written == 1024
    assert m.rows_discarded == 10


def test_metrics_report() -> None:
    """report() returns IngestionReport with correct aggregated values."""
    m = IngestionMetrics()
    with m.track_time():
        m.record_asset_class("equities")
        m.record_timeframe("1D")
        sr = ScanResult(
            market="america",
            tickers_requested=100,
            tickers_received=95,
            duration_ms=1500.0,
            success=True,
        )
        m.record_scan(sr)
        m.record_write(500, 2048, 5)

    report = m.report()
    assert report.symbols_processed == 95
    assert report.candles_written == 500
    assert report.bytes_written == 2048
    assert report.rows_discarded == 5
    assert report.scans_succeeded == 1
    assert "equities" in report.asset_classes_processed
    assert "1D" in report.timeframes_processed


def test_metrics_log_summary() -> None:
    """log_summary emits structured log (capture with log capture)."""
    m = IngestionMetrics()
    # Just verify it doesn't raise
    m.log_summary()


def test_asset_class_timeframe_tracking() -> None:
    """record_asset_class and record_timeframe deduplicate."""
    m = IngestionMetrics()
    m.record_asset_class("equities")
    m.record_asset_class("equities")  # duplicate
    m.record_asset_class("crypto")
    m.record_timeframe("1D")
    m.record_timeframe("1D")  # duplicate
    m.record_timeframe("1h")
    assert m.asset_classes_processed == ["equities", "crypto"]
    assert m.timeframes_processed == ["1D", "1h"]


def test_save_health_and_load() -> None:
    """Save then load returns equal health data."""
    m = IngestionMetrics()
    with m.track_time():
        m.record_asset_class("equities")
        sr = ScanResult(
            market="america",
            tickers_requested=100,
            tickers_received=95,
            duration_ms=1500.0,
            success=True,
        )
        m.record_scan(sr)
        m.record_write(500, 2048, 5)

    report = m.report()
    con = duckdb.connect(":memory:")
    con.execute("""
        CREATE TABLE ingestion_health (
            id INTEGER PRIMARY KEY,
            last_successful_run TIMESTAMPTZ,
            last_run_duration_ms DOUBLE,
            symbols_processed INTEGER DEFAULT 0,
            candles_written INTEGER DEFAULT 0,
            error_rate DOUBLE DEFAULT 0.0,
            circuit_breaker_state VARCHAR DEFAULT 'CLOSED',
            is_running BOOLEAN DEFAULT false,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    """)

    save_health(con, report)
    loaded = load_latest_health(con)
    assert loaded is not None
    assert loaded.symbols_processed == 95
    assert loaded.candles_written == 500
    assert loaded.circuit_breaker_state == "CLOSED"

    # Test with empty table
    con.execute("DELETE FROM ingestion_health")
    no_data = load_latest_health(con)
    assert no_data is None

    con.close()
