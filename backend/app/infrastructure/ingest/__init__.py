"""Data ingestion pipeline — TradingView scanner, fetcher, writer, quality."""

from backend.app.infrastructure.ingest.orchestrator import run_ingestion

__all__ = ["run_ingestion"]