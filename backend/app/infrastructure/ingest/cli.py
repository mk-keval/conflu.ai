"""CLI entry point for ingestion pipeline.

Usage:
    python -m backend.app.infrastructure.ingest
    python -m backend.app.infrastructure.ingest --asset-class equities --timeframe 1D
    python -m backend.app.infrastructure.ingest --dry-run
    python -m backend.app.infrastructure.ingest --health
    python -m backend.app.infrastructure.ingest --setup  # Initialize DB tables
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any

from backend.app.core.config import settings
from backend.app.core.database import get_db, initialize_database
from backend.app.core.logging import configure_logging, get_logger
from backend.app.infrastructure.ingest.metrics import load_latest_health

log = get_logger("conflu.ingest.cli")


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="python -m backend.app.infrastructure.ingest",
        description="conflu.ai data ingestion pipeline — TradingView scanner to Parquet",
    )

    parser.add_argument(
        "--asset-class",
        action="append",
        choices=list(settings.data.assets.keys()),
        dest="asset_classes",
        help="Asset class(es) to process (default: all). Can be specified multiple times.",
    )
    parser.add_argument(
        "--timeframe",
        action="append",
        choices=settings.data.timeframes,
        dest="timeframes",
        help="Timeframe(s) to fetch (default: all). Can be specified multiple times.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Validate configuration and connectivity without writing data.",
    )
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=None,
        help=f"Max concurrent scan operations (default: {settings.data.max_concurrent}).",
    )
    parser.add_argument(
        "--health",
        action="store_true",
        default=False,
        help="Show last ingestion health status and exit.",
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        default=False,
        help="Initialize DuckDB tables (symbol_metadata, ingestion_health) and exit.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns exit code."""
    configure_logging(
        log_level=settings.core.log_level,
        log_json=settings.core.log_json,
    )

    parser = build_parser()
    args = parser.parse_args(argv)

    # Handle --setup
    if args.setup:
        initialize_database()
        _ensure_ingestion_tables()
        log.info("setup_complete", tables=["ohlcv", "symbol_metadata", "ingestion_health"])
        return 0

    # Handle --health
    if args.health:
        try:
            with get_db() as con:
                health = load_latest_health(con)
            if health:
                print(health.model_dump_json(indent=2))
            else:
                print('{"status": "no_data", "message": "No ingestion runs recorded yet."}')
        except Exception as e:
            print(f'{{"status": "error", "message": "{e}"}}')
        return 0

    # Run ingestion
    try:
        from backend.app.infrastructure.ingest import run_ingestion

        report = asyncio.run(
            run_ingestion(
                asset_classes=args.asset_classes,
                timeframes=args.timeframes,
                dry_run=args.dry_run,
                max_concurrent=args.max_concurrent,
            )
        )
        print(report.model_dump_json(indent=2))
        return 0 if report.error_rate < 1.0 else 1
    except Exception:
        log.exception("ingestion_fatal")
        return 1


def _ensure_ingestion_tables() -> None:
    """Create symbol_metadata and ingestion_health tables if not exist."""
    from backend.app.core.database import get_db

    with get_db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS symbol_metadata (
                symbol VARCHAR PRIMARY KEY,
                asset_class VARCHAR NOT NULL,
                exchange VARCHAR,
                tv_ticker VARCHAR,
                timezone VARCHAR DEFAULT 'UTC',
                active BOOLEAN DEFAULT true,
                added_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                last_seen_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS ingestion_health (
                id INTEGER PRIMARY KEY AUTO_INCREMENT,
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
        log.info("ingestion_tables_ensured")


if __name__ == "__main__":
    sys.exit(main())
