"""Tests for Pydantic models — ScanResult, IngestionReport, IngestionHealth."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from backend.app.infrastructure.ingest.models import (
    IngestionHealth,
    IngestionReport,
    ScanResult,
)


def test_scan_result_fields() -> None:
    """ScanResult has all required fields with correct types."""
    sr = ScanResult(
        market="america",
        tickers_requested=100,
        tickers_received=95,
        duration_ms=1500.0,
        success=True,
    )
    assert sr.market == "america"
    assert sr.tickers_requested == 100
    assert sr.tickers_received == 95
    assert sr.duration_ms == 1500.0
    assert sr.success is True
    assert sr.error is None


def test_scan_result_with_error() -> None:
    """ScanResult can include an error message."""
    sr = ScanResult(
        market="america",
        tickers_requested=100,
        tickers_received=0,
        duration_ms=500.0,
        success=False,
        error="Connection timeout",
    )
    assert sr.error == "Connection timeout"


def test_ingestion_report_defaults() -> None:
    """IngestionReport default values are correct."""
    report = IngestionReport(
        correlation_id="test-123",
        started_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    assert report.correlation_id == "test-123"
    assert report.symbols_processed == 0
    assert report.candles_written == 0
    assert report.error_rate == 0.0
    assert report.scan_results == []


def test_ingestion_report_with_scan_results() -> None:
    """IngestionReport can include a list of ScanResults."""
    sr = ScanResult(
        market="america",
        tickers_requested=100,
        tickers_received=95,
        duration_ms=1500.0,
        success=True,
    )
    report = IngestionReport(
        correlation_id="test-456",
        started_at=datetime(2024, 1, 1, tzinfo=UTC),
        scan_results=[sr],
        symbols_processed=95,
        candles_written=190,
        scans_succeeded=1,
    )
    assert len(report.scan_results) == 1
    assert report.symbols_processed == 95
    assert report.candles_written == 190
    assert report.scans_succeeded == 1


def test_ingestion_health() -> None:
    """IngestionHealth has all required fields."""
    health = IngestionHealth()
    assert health.circuit_breaker_state == "CLOSED"
    assert health.is_running is False
    assert health.symbols_processed == 0


def test_ingestion_health_with_data() -> None:
    """IngestionHealth with full data."""
    health = IngestionHealth(
        last_successful_run=datetime(2024, 1, 1, tzinfo=UTC),
        last_run_duration_ms=15000.0,
        symbols_processed=100,
        candles_written=500,
        error_rate=0.02,
        circuit_breaker_state="CLOSED",
        is_running=False,
    )
    assert health.last_run_duration_ms == 15000.0
    assert health.symbols_processed == 100


def test_report_utc_validation() -> None:
    """Naive datetime gets UTC assigned by validator."""
    report = IngestionReport(
        correlation_id="test",
        started_at=datetime(2024, 1, 1),  # naive
    )
    assert report.started_at.tzinfo is not None
    assert report.started_at.tzinfo == UTC


def test_report_frozen() -> None:
    """Trying to modify a frozen model field raises ValidationError."""
    report = IngestionReport(
        correlation_id="test",
        started_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    with pytest.raises(ValidationError):
        report.symbols_processed = 100  # type: ignore[misc]


def test_extra_fields_forbidden() -> None:
    """Extra fields are not allowed."""
    with pytest.raises(ValidationError):
        IngestionReport(
            correlation_id="test",
            started_at=datetime(2024, 1, 1, tzinfo=UTC),
            extra_field="not allowed",  # type: ignore[call-arg]
        )
