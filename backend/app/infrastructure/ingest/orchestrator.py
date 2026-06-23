"""Main ingestion orchestrator - coordinates scanner, fetcher, writer, quality."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import pandas as pd

from backend.app.core.config import settings
from backend.app.core.database import get_db, initialize_database
from backend.app.core.logging import get_logger
from backend.app.infrastructure.ingest.fetcher import IngestionFetcher
from backend.app.infrastructure.ingest.models import IngestionReport, ScanResult
from backend.app.infrastructure.ingest.quality import QualityReport, validate_ohlcv
from backend.app.infrastructure.ingest.scanner import circuit_breaker_state, reset_circuit_breaker
from backend.app.infrastructure.ingest.symbol_map import TickerResolver
from backend.app.infrastructure.ingest.writer import write_incremental

log = get_logger("conflu.ingest.orchestrator")


@dataclass
class IngestionTracker:
    """Mutable tracker for ingestion progress."""
    correlation_id: str
    started_at: datetime
    asset_classes_processed: list[str] = field(default_factory=list)
    timeframes_processed: list[str] = field(default_factory=list)
    symbols_processed: int = 0
    candles_written: int = 0
    symbols_failed: int = 0
    bytes_written: int = 0
    scans_succeeded: int = 0
    scans_failed: int = 0
    rows_discarded: int = 0
    scan_results: list[ScanResult] = field(default_factory=list)
    completed_at: datetime | None = None
    duration_ms: float | None = None
    error_rate: float = 0.0

    def record_asset_class(self, asset_class: str) -> None:
        if asset_class not in self.asset_classes_processed:
            self.asset_classes_processed.append(asset_class)

    def record_timeframe(self, timeframe: str) -> None:
        if timeframe not in self.timeframes_processed:
            self.timeframes_processed.append(timeframe)

    def record_scan(self, result: ScanResult) -> None:
        self.scan_results.append(result)
        if result.success:
            self.scans_succeeded += 1
            self.symbols_processed += result.tickers_received
        else:
            self.scans_failed += 1
            self.symbols_failed += result.tickers_requested

    def record_write(self, new_rows: int, bytes_written: int, discarded: int) -> None:
        self.candles_written += new_rows
        self.bytes_written += bytes_written
        self.rows_discarded += discarded

    def to_report(self) -> IngestionReport:
        """Convert to frozen IngestionReport."""
        total_ops = self.scans_succeeded + self.scans_failed
        error_rate = round(self.scans_failed / total_ops, 4) if total_ops > 0 else 0.0
        
        return IngestionReport(
            correlation_id=self.correlation_id,
            started_at=self.started_at,
            completed_at=self.completed_at,
            duration_ms=self.duration_ms,
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


async def run_ingestion(
    asset_classes: list[str] | None = None,
    timeframes: list[str] | None = None,
    dry_run: bool = False,
    max_concurrent: int | None = None,
) -> IngestionReport:
    """Run the full ingestion pipeline.
    
    Args:
        asset_classes: Asset classes to process (default: all from config).
        timeframes: Timeframes to fetch (default: all from config).
        dry_run: Validate configuration and connectivity without writing data.
        max_concurrent: Max concurrent scan operations (default: from config).
    
    Returns:
        IngestionReport with pipeline statistics.
    """
    # Ensure database is initialized
    initialize_database()
    
    # Resolve asset classes and timeframes
    asset_classes = asset_classes or list(settings.data.assets.keys())
    timeframes = timeframes or list(settings.data.timeframes)
    max_concurrent = max_concurrent or settings.data.max_concurrent
    
    # Initialize tracker
    tracker = IngestionTracker(
        correlation_id=str(uuid4())[:8],
        started_at=datetime.now(timezone.utc),
    )
    
    # Track circuit breaker states
    breaker_states = {market: circuit_breaker_state(market) for market in settings.data.asset_class_markets.values()}
    
    try:
        # Initialize fetcher
        fetcher = IngestionFetcher(max_concurrent=max_concurrent)
        
        # Process each asset class
        for asset_class in asset_classes:
            if asset_class not in settings.data.assets:
                log.warning("unknown_asset_class", asset_class=asset_class)
                continue
            
            symbols = settings.data.assets[asset_class]
            market = settings.data.asset_class_markets.get(asset_class, "america")
            
            # Check circuit breaker
            breaker = breaker_states.get(market, {})
            if breaker.get("state") == "OPEN":
                log.warning("circuit_breaker_open_skipping", market=market, asset_class=asset_class)
                tracker.record_asset_class(f"{asset_class} (skipped)")
                continue
            
            # Resolve TV tickers
            resolver = TickerResolver()
            tickers = [resolver.to_tv_ticker(sym, asset_class) for sym in symbols]
            
            # Determine columns to fetch (OHLCV + timestamp from TV)
            columns = ["time", "open", "high", "low", "close", "volume"]
            
            log.info(
                "ingestion_asset_class_start",
                asset_class=asset_class,
                market=market,
                symbols=len(symbols),
                timeframes=timeframes,
            )
            
            tracker.record_asset_class(asset_class)
            
            # Process each timeframe
            for timeframe in timeframes:
                tracker.record_timeframe(timeframe)
                
                try:
                    # Fetch data for this asset class + timeframe
                    df, scan_results = await fetcher.fetch_asset_class(
                        asset_class=asset_class,
                        market=market,
                        tickers=tickers,
                        columns=columns,
                    )
                    
                    # Record scan results
                    for scan in scan_results:
                        tracker.record_scan(scan)
                    
                    if df.empty:
                        log.warning("no_data_fetched", asset_class=asset_class, timeframe=timeframe)
                        continue
                    
                    # Add metadata columns
                    df = df.copy()
                    df["asset_class"] = asset_class
                    df["timeframe"] = timeframe
                    
                    if dry_run:
                        log.info("dry_run_skip_write", asset_class=asset_class, timeframe=timeframe, rows=len(df))
                        continue
                    
                    # Validate quality
                    clean_df, quality_report = validate_ohlcv(df)
                    
                    if clean_df.empty:
                        log.warning(
                            "no_valid_rows_after_quality",
                            asset_class=asset_class,
                            timeframe=timeframe,
                            total_rows=len(df),
                        )
                        tracker.rows_discarded += quality_report.rows_discarded
                        continue
                    
                    # Write incrementally
                    new_rows, bytes_written, _ = write_incremental(
                        clean_df,
                        asset_class=asset_class,
                        timeframe=timeframe,
                    )
                    
                    tracker.record_write(new_rows, bytes_written, quality_report.rows_discarded)
                    
                    log.info(
                        "ingestion_timeframe_complete",
                        asset_class=asset_class,
                        timeframe=timeframe,
                        new_rows=new_rows,
                        bytes_written=bytes_written,
                    )
                    
                except Exception as e:
                    log.exception(
                        "ingestion_timeframe_failed",
                        asset_class=asset_class,
                        timeframe=timeframe,
                    )
                    # Continue with other timeframes
                    continue
        
        # Update symbol metadata
        await _update_symbol_metadata(asset_classes)
        
        # Finalize tracker
        tracker.completed_at = datetime.now(timezone.utc)
        tracker.duration_ms = (tracker.completed_at - tracker.started_at).total_seconds() * 1000
        
        # Convert to report
        report = tracker.to_report()
        
        # Store health check
        await _store_health(report)
        
        log.info(
            "ingestion_complete",
            correlation_id=report.correlation_id,
            asset_classes=report.asset_classes_processed,
            symbols_processed=report.symbols_processed,
            candles_written=report.candles_written,
            error_rate=report.error_rate,
            duration_ms=report.duration_ms,
        )
        
        return report
        
    except Exception as e:
        log.exception("ingestion_fatal")
        # Create error report
        error_tracker = IngestionTracker(
            correlation_id=str(uuid4())[:8],
            started_at=datetime.now(timezone.utc),
        )
        error_tracker.completed_at = datetime.now(timezone.utc)
        error_tracker.duration_ms = (error_tracker.completed_at - error_tracker.started_at).total_seconds() * 1000
        error_tracker.error_rate = 1.0
        await _store_health(error_tracker.to_report())
        raise


async def _update_symbol_metadata(asset_classes: list[str]) -> None:
    """Update symbol_metadata table with processed symbols."""
    from backend.app.core.database import get_db
    from backend.app.infrastructure.ingest.symbol_map import TickerResolver
    
    resolver = TickerResolver()
    
    symbols_data = []
    for asset_class in asset_classes:
        if asset_class not in settings.data.assets:
            continue
        for symbol in settings.data.assets[asset_class]:
            tv_ticker = resolver.to_tv_ticker(symbol, asset_class)
            exchange, _ = resolver.from_tv_ticker(tv_ticker)
            timezone = resolver.get_timezone(asset_class)
            
            symbols_data.append({
                "symbol": symbol,
                "asset_class": asset_class,
                "exchange": exchange,
                "tv_ticker": tv_ticker,
                "timezone": timezone,
                "active": True,
            })
    
    if not symbols_data:
        return
    
    df = pd.DataFrame(symbols_data)
    
    def _upsert() -> None:
        with get_db() as con:
            for _, row in df.iterrows():
                con.sql("""
                    INSERT INTO symbol_metadata (symbol, asset_class, exchange, tv_ticker, timezone, active)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT (symbol) DO UPDATE SET
                        asset_class = EXCLUDED.asset_class,
                        exchange = EXCLUDED.exchange,
                        tv_ticker = EXCLUDED.tv_ticker,
                        timezone = EXCLUDED.timezone,
                        active = EXCLUDED.active
                """, params=[
                    row["symbol"], row["asset_class"], row["exchange"],
                    row["tv_ticker"], row["timezone"], row["active"]
                ])
    
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _upsert)


async def _store_health(report: IngestionReport) -> None:
    """Store ingestion health in database."""
    from backend.app.core.database import get_db
    
    def _insert() -> None:
        with get_db() as con:
            # Delete old health record (keep only latest)
            con.sql("DELETE FROM ingestion_health WHERE id = 1")
            con.sql("""
                INSERT INTO ingestion_health (
                    id, last_successful_run, last_run_duration_ms,
                    symbols_processed, candles_written, error_rate,
                    circuit_breaker_state, is_running
                ) VALUES (1, ?, ?, ?, ?, ?, 'CLOSED', FALSE)
            """, params=[
                report.completed_at,
                report.duration_ms,
                report.symbols_processed,
                report.candles_written,
                report.error_rate,
            ])
    
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _insert)


# Export for backward compatibility
__all__ = ["run_ingestion"]