"""Pydantic models for ingestion pipeline."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ScanResult(BaseModel):
    """Result of a single TradingView scan operation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    market: str
    tickers_requested: int
    tickers_received: int
    duration_ms: float
    success: bool
    error: str | None = None


class IngestionReport(BaseModel):
    """Summary report for a full ingestion run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    correlation_id: str
    started_at: datetime
    completed_at: datetime | None = None
    duration_ms: float | None = None
    asset_classes_processed: list[str] = Field(default_factory=list)
    timeframes_processed: list[str] = Field(default_factory=list)
    symbols_processed: int = 0
    candles_written: int = 0
    symbols_failed: int = 0
    bytes_written: int = 0
    scans_succeeded: int = 0
    scans_failed: int = 0
    rows_discarded: int = 0
    error_rate: float = 0.0
    scan_results: list[ScanResult] = Field(default_factory=list)

    @field_validator("started_at", "completed_at")
    @classmethod
    def ensure_utc(cls, v: datetime | None) -> datetime | None:
        if v is not None and v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v


class IngestionHealth(BaseModel):
    """Health status for the ingestion pipeline."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    last_successful_run: datetime | None = None
    last_run_duration_ms: float | None = None
    symbols_processed: int = 0
    candles_written: int = 0
    error_rate: float = 0.0
    circuit_breaker_state: str = "CLOSED"
    is_running: bool = False
