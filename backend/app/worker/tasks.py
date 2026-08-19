"""Celery tasks for conflu.ai background processing."""

from __future__ import annotations

import asyncio
from typing import Any

from celery import shared_task

from backend.app.core.config import settings
from backend.app.core.logging import configure_logging, get_logger

# Configure logging for Celery workers
configure_logging(
    log_level=settings.core.log_level,
    log_json=settings.core.log_json,
)

log = get_logger("conflu.worker.tasks")


def _run_async(coro):
    """Run an async coroutine in a new event loop."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def ingest_asset_class(
    self,
    asset_class: str,
    timeframes: list[str] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Ingest data for a single asset class.
    
    Args:
        asset_class: Asset class to ingest (equities, crypto, forex, commodities, indices)
        timeframes: Timeframes to ingest (default: all from config)
        dry_run: If True, validate only without writing
    
    Returns:
        Dict with ingestion report
    """
    from backend.app.infrastructure.ingest import run_ingestion

    log.info("celery_ingest_started", asset_class=asset_class, timeframes=timeframes, dry_run=dry_run)

    try:
        report = _run_async(
            run_ingestion(
                asset_classes=[asset_class],
                timeframes=timeframes,
                dry_run=dry_run,
                max_concurrent=settings.data.max_concurrent,
            )
        )

        result = {
            "asset_class": asset_class,
            "status": "success" if report.error_rate < 1.0 else "partial_failure",
            "symbols_processed": report.symbols_processed,
            "candles_written": report.candles_written,
            "symbols_failed": report.symbols_failed,
            "error_rate": report.error_rate,
            "duration_ms": report.duration_ms,
        }

        log.info("celery_ingest_completed", **result)
        return result

    except Exception:
        log.exception("celery_ingest_failed", asset_class=asset_class)
        raise


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=120,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def ingest_all(
    self,
    asset_classes: list[str] | None = None,
    timeframes: list[str] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Ingest data for all configured asset classes.
    
    Args:
        asset_classes: Asset classes to ingest (default: all from config)
        timeframes: Timeframes to ingest (default: all from config)
        dry_run: If True, validate only without writing
    
    Returns:
        Dict with combined ingestion report
    """
    from backend.app.infrastructure.ingest import run_ingestion

    log.info("celery_ingest_all_started", asset_classes=asset_classes, timeframes=timeframes)

    try:
        report = _run_async(
            run_ingestion(
                asset_classes=asset_classes,
                timeframes=timeframes,
                dry_run=dry_run,
                max_concurrent=settings.data.max_concurrent,
            )
        )

        result = {
            "status": "success" if report.error_rate < 1.0 else "partial_failure",
            "asset_classes_processed": report.asset_classes_processed,
            "timeframes_processed": report.timeframes_processed,
            "symbols_processed": report.symbols_processed,
            "candles_written": report.candles_written,
            "symbols_failed": report.symbols_failed,
            "error_rate": report.error_rate,
            "duration_ms": report.duration_ms,
            "scans_succeeded": report.scans_succeeded,
            "scans_failed": report.scans_failed,
        }

        log.info("celery_ingest_all_completed", **result)

        return result

    except Exception:
        log.exception("celery_ingest_all_failed")
        raise


@shared_task
def health_check() -> dict[str, Any]:
    """Health check task for monitoring."""
    from backend.app.core.database import get_db

    try:
        with get_db(read_only=True) as con:
            con.sql("SELECT 1").fetchone()
        db_ok = True
    except Exception:
        db_ok = False

    return {
        "status": "healthy" if db_ok else "unhealthy",
        "database": db_ok,
        "worker": "celery",
    }


# Periodic task registration (alternative to beat_schedule)
# These can be called from Celery Beat or external scheduler
@shared_task
def periodic_daily_ingestion() -> dict[str, Any]:
    """Daily ingestion task - triggered by Celery Beat."""
    return ingest_all.delay().get()


@shared_task
def periodic_intraday_ingestion() -> dict[str, Any]:
    """Intraday ingestion task - triggered by Celery Beat."""
    # Only ingest intraday timeframes
    timeframes = [tf for tf in settings.data.timeframes if tf != "1D"]
    return ingest_all.delay(timeframes=timeframes).get()
