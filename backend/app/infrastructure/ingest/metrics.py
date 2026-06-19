"""Ingestion metrics tracking and reporting."""

from __future__ import annotations

import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator
from uuid import uuid4

import duckdb

from backend.app.core.logging import get_logger, set_correlation_id
from backend.app.infrastructure.ingest.models import IngestionHealth, IngestionReport, ScanResult

log = get_logger("conflu.ingest.metrics")


class IngestionMetrics:
    """Tracks counters, timing, and generates IngestionReport.

    Usage:
        metrics = IngestionMetrics()
        with metrics.track_time():
            ... do work ...
        report = metrics.report()
    """

    def __init__(self) -> None:
        self.correlation_id: str = set_correlation_id()
        self.started_at: datetime = datetime.now(timezone.utc)
        self.asset_classes_processed: list[str] = []
        self.timeframes_processed: list[str] = []
        self.symbols_processed: int = 0
        self.candles_written: int = 0
        self.symbols_failed: int = 0
        self.bytes_written: int = 0
        self.scans_succeeded: int = 0
        self.scans_failed: int = 0
        self.rows_discarded: int = 0
        self.scan_results: list[ScanResult] = []
        self._duration_ms: float | None = None

    @contextmanager
    def track_time(self) -> Iterator[None]:
        """Context manager that records elapsed time."""
        start = time.monotonic()
        try:
            yield
        finally:
            self._duration_ms = (time.monotonic() - start) * 1000

    def record_scan(self, result: ScanResult) -> None:
        """Record a single scan result."""
        self.scan_results.append(result)
        if result.success:
            self.scans_succeeded += 1
            self.symbols_processed += result.tickers_received
        else:
            self.scans_failed += 1
            self.symbols_failed += result.tickers_requested

    def record_write(self, new_rows: int, bytes_written: int, discarded: int) -> None:
        """Record write statistics."""
        self.candles_written += new_rows
        self.bytes_written += bytes_written
        self.rows_discarded += discarded

    def record_asset_class(self, asset_class: str) -> None:
        """Record that an asset class was processed."""
        if asset_class not in self.asset_classes_processed:
            self.asset_classes_processed.append(asset_class)

    def record_timeframe(self, timeframe: str) -> None:
        """Record that a timeframe was processed."""
        if timeframe not in self.timeframes_processed:
            self.timeframes_processed.append(timeframe)

    def report(self) -> IngestionReport:
        """Generate the final IngestionReport."""
        total_ops = self.scans_succeeded + self.scans_failed
        error_rate = round(self.scans_failed / total_ops, 4) if total_ops > 0 else 0.0

        return IngestionReport(
            correlation_id=self.correlation_id,
            started_at=self.started_at,
            completed_at=datetime.now(timezone.utc),
            duration_ms=self._duration_ms,
            asset_classes_processed=self.asset_classes_processed,
            timeframes_processed=self.timeframes_processed,
            symbols_processed=self.symbols_processed,
            candles_written=self.candles_written,
            symbols_failed=self.symbols_failed,
            bytes_written=self.bytes_written,
            scans_succeeded=self.scans_succeeded,
            scans_failed=self.scans_failed,
            rows_discarded=self.rows_discarded,
            error_rate=error_rate,
            scan_results=self.scan_results,
        )

    def log_summary(self) -> None:
        """Emit a structured log line with the ingestion summary."""
        report = self.report()
        log.info(
            "ingestion_complete",
            correlation_id=report.correlation_id,
            duration_ms=report.duration_ms,
            symbols_processed=report.symbols_processed,
            candles_written=report.candles_written,
            symbols_failed=report.symbols_failed,
            bytes_written=report.bytes_written,
            error_rate=report.error_rate,
            asset_classes=report.asset_classes_processed,
            timeframes=report.timeframes_processed,
        )


def load_latest_health(con: duckdb.DuckDBPyConnection) -> IngestionHealth | None:
    """Load most recent ingestion health from DuckDB."""
    row = con.sql(
        "SELECT * FROM ingestion_health ORDER BY last_successful_run DESC LIMIT 1"
    ).fetchdf()
    if row.empty:
        return None
    return IngestionHealth(**row.iloc[0].to_dict())


def save_health(con: duckdb.DuckDBPyConnection, report: IngestionReport) -> None:
    """Save ingestion health report to DuckDB."""
    health = IngestionHealth(
        last_successful_run=report.completed_at or datetime.now(timezone.utc),
        last_run_duration_ms=report.duration_ms,
        symbols_processed=report.symbols_processed,
        candles_written=report.candles_written,
        error_rate=report.error_rate,
        circuit_breaker_state="CLOSED",
        is_running=False,
    )
    con.execute(
        """
        INSERT INTO ingestion_health (
            last_successful_run, last_run_duration_ms, symbols_processed,
            candles_written, error_rate, circuit_breaker_state, is_running
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            health.last_successful_run,
            health.last_run_duration_ms,
            health.symbols_processed,
            health.candles_written,
            health.error_rate,
            health.circuit_breaker_state,
            health.is_running,
        ],
    )
