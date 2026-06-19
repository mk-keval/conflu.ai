"""Data ingestion pipeline — TradingView scanner, fetcher, writer, quality.

Usage:
    from backend.app.infrastructure.ingest import run_ingestion
    report = await run_ingestion()
"""

from __future__ import annotations

from backend.app.core.logging import get_logger
from backend.app.infrastructure.ingest.fetcher import IngestionFetcher
from backend.app.infrastructure.ingest.metrics import IngestionMetrics
from backend.app.infrastructure.ingest.models import IngestionReport
from backend.app.infrastructure.ingest.symbol_map import TickerResolver
from backend.app.infrastructure.ingest.writer import write_incremental_multi

# Re-export cli.main so `python -m backend.app.infrastructure.ingest` works
from backend.app.infrastructure.ingest.cli import main  # noqa: F401

log = get_logger("conflu.ingest")


async def run_ingestion(
    asset_classes: list[str] | None = None,
    timeframes: list[str] | None = None,
    dry_run: bool = False,
    max_concurrent: int | None = None,
) -> IngestionReport:
    """Run the full ingestion pipeline.

    Args:
        asset_classes: Subset of asset classes to process (None = all configured).
        timeframes: Subset of timeframes to process (None = all configured).
        dry_run: If True, validate only — don't write to Parquet.
        max_concurrent: Override max concurrent requests (default from config).

    Returns:
        IngestionReport with summary of the run.

    Flow:
    1. Resolve all symbols -> TV tickers via TickerResolver
    2. For each (asset_class, timeframe):
       a. Determine which columns to request from scanner
       b. Chunk tickers into batches of 100
       c. Fire semaphore-constrained concurrent scans
       d. Validate OHLCV data quality
       e. Deduplicate against existing data
       f. Write new rows to Parquet + DuckDB (unless dry_run)
    3. Update symbol_metadata table
    4. Save health report to DuckDB
    5. Emit metrics summary
    """
    from backend.app.core.config import settings
    from backend.app.core.database import get_db

    metrics = IngestionMetrics()
    resolver = TickerResolver()
    fetcher = IngestionFetcher(max_concurrent=max_concurrent)

    # Determine which asset classes and timeframes to process
    acs = asset_classes or list(settings.data.assets.keys())
    tfs = timeframes or list(settings.data.timeframes)

    # Build column sets per timeframe
    # 1D = bare fields, intraday = pipe suffix (e.g., close|5, open|60)
    timeframe_columns: dict[str, list[str]] = {}
    for tf in tfs:
        if tf == "1D":
            timeframe_columns[tf] = ["open", "high", "low", "close", "volume"]
        else:
            suffix = _timeframe_to_tv_suffix(tf)
            timeframe_columns[tf] = [
                f"open{suffix}",
                f"high{suffix}",
                f"low{suffix}",
                f"close{suffix}",
                f"volume{suffix}",
            ]

    with metrics.track_time():
        for asset_class in acs:
            cfg = resolver.get_asset_classes().get(asset_class)
            if cfg is None:
                log.warning("unknown_asset_class", asset_class=asset_class)
                continue

            market = cfg.market
            tickers = [resolver.to_tv_ticker(s, asset_class) for s in cfg.symbols]
            metrics.record_asset_class(asset_class)

            for tf in tfs:
                metrics.record_timeframe(tf)
                columns = ["ticker"] + timeframe_columns.get(tf, ["close"])

                log.info(
                    "fetching_asset_class_timeframe",
                    asset_class=asset_class,
                    timeframe=tf,
                    market=market,
                    symbol_count=len(tickers),
                )

                # Fetch
                chunk_df, scan_results = await fetcher.fetch_asset_class(
                    asset_class=asset_class,
                    market=market,
                    tickers=tickers,
                    columns=columns,
                )

                for sr in scan_results:
                    metrics.record_scan(sr)

                if chunk_df.empty:
                    log.info("no_data_fetched", asset_class=asset_class, timeframe=tf)
                    continue

                # Assign timeframe to the data
                chunk_df["timeframe"] = tf

                # Write (unless dry run)
                if not dry_run:
                    results = write_incremental_multi(chunk_df, asset_class)
                    timeframe_key = f"{asset_class}/{tf}"
                    if timeframe_key in results:
                        new_rows, bytes_written, quality = results[timeframe_key]
                        metrics.record_write(
                            new_rows, bytes_written, quality.rows_discarded
                        )
                else:
                    log.info(
                        "dry_run_validation",
                        asset_class=asset_class,
                        timeframe=tf,
                        rows_fetched=len(chunk_df),
                    )

        # Update symbol_metadata after processing
        if not dry_run:
            try:
                with get_db() as con:
                    _update_symbol_metadata(con, resolver, acs)
                    from backend.app.infrastructure.ingest.metrics import save_health

                    save_health(con, metrics.report())
            except Exception:
                log.exception("metadata_update_failed")

        # Update indicator cache after successful ingestion
        if not dry_run:
            try:
                from backend.app.infrastructure.screener.cache import IndicatorCache

                cache = IndicatorCache()
                cache_updated = await cache.update_cache(
                    timeframes=tfs,
                    indicator_names=None,  # all cached indicators
                )
                if cache_updated > 0:
                    log.info("indicator_cache_updated", new_values=cache_updated)
            except Exception:
                log.exception("indicator_cache_update_failed")

    metrics.log_summary()
    return metrics.report()


def _timeframe_to_tv_suffix(tf: str) -> str:
    """Convert internal timeframe to TV pipe suffix.

    Examples:
        '5m' -> '|5'
        '15m' -> '|15'
        '1h' -> '|60'
        '4h' -> '|240'
        '1D' -> ''  (bare field)
    """
    if tf == "1D":
        return ""
    if tf.endswith("h"):
        mins = int(tf[:-1]) * 60
        return f"|{mins}"
    if tf.endswith("m"):
        mins = int(tf[:-1])
        return f"|{mins}"
    return ""


def _update_symbol_metadata(
    con, resolver: TickerResolver, asset_classes: list[str]
) -> None:
    """Upsert symbols into symbol_metadata table."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    for ac in asset_classes:
        cfg = resolver.get_asset_classes().get(ac)
        if cfg is None:
            continue
        for symbol in cfg.symbols:
            exchange = resolver.get_exchange(symbol, ac)
            tv_ticker = resolver.to_tv_ticker(symbol, ac)
            con.execute(
                """
                INSERT INTO symbol_metadata (symbol, asset_class, exchange, tv_ticker, timezone, active, last_seen_at)
                VALUES (?, ?, ?, ?, ?, true, ?)
                ON CONFLICT (symbol) DO UPDATE SET
                    last_seen_at = EXCLUDED.last_seen_at,
                    active = true
                """,
                [symbol, ac, exchange.rstrip(":"), tv_ticker, cfg.timezone, now],
            )


__all__ = ["run_ingestion", "IngestionReport"]
