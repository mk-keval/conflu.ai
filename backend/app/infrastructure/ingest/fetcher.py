"""Async chunked fetcher with semaphore concurrency control."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from typing import Any

import pandas as pd

from backend.app.core.config import settings
from backend.app.core.logging import get_logger
from backend.app.infrastructure.ingest.models import ScanResult
from backend.app.infrastructure.ingest.scanner import scan_with_retry

log = get_logger("conflu.ingest.fetcher")


class IngestionFetcher:
    """Async fetcher that chunks symbols and manages concurrency.

    Uses TradingView's batch endpoint (100 symbols/call) with semaphore
    limiting to max_concurrent simultaneous operations.
    """

    def __init__(self, max_concurrent: int | None = None) -> None:
        self._max_concurrent = max_concurrent or settings.data.max_concurrent
        self._semaphore = asyncio.Semaphore(self._max_concurrent)
        self._batch_size = settings.data.batch_size

    async def fetch_asset_class(
        self,
        asset_class: str,
        market: str,
        tickers: list[str],
        columns: list[str],
    ) -> tuple[pd.DataFrame, list[ScanResult]]:
        """Fetch OHLCV data for all tickers in an asset class.

        Returns:
            Tuple of (combined DataFrame, list of per-chunk ScanResults).
        """
        all_chunks: list[pd.DataFrame] = []
        all_results: list[ScanResult] = []

        async for chunk_df, scan_result in self._chunked_fetch(tickers, columns, market):
            all_results.append(scan_result)
            if not chunk_df.empty:
                chunk_df = chunk_df.copy()
                chunk_df["asset_class"] = asset_class
                all_chunks.append(chunk_df)

        if not all_chunks:
            return pd.DataFrame(), all_results
        return pd.concat(all_chunks, ignore_index=True), all_results

    async def _chunked_fetch(
        self,
        tickers: list[str],
        columns: list[str],
        market: str,
    ) -> AsyncIterator[tuple[pd.DataFrame, ScanResult]]:
        """Yield (DataFrame, ScanResult) for each chunk as they complete."""
        chunks = [
            tickers[i : i + self._batch_size]
            for i in range(0, len(tickers), self._batch_size)
        ]

        async def fetch_chunk(chunk_tickers: list[str]) -> tuple[pd.DataFrame, ScanResult]:
            start = time.monotonic()
            async with self._semaphore:
                try:
                    df = await scan_with_retry(chunk_tickers, columns, market)
                    duration = (time.monotonic() - start) * 1000
                    result = ScanResult(
                        market=market,
                        tickers_requested=len(chunk_tickers),
                        tickers_received=len(df),
                        duration_ms=round(duration, 2),
                        success=True,
                    )
                    return df, result
                except Exception as e:
                    duration = (time.monotonic() - start) * 1000
                    result = ScanResult(
                        market=market,
                        tickers_requested=len(chunk_tickers),
                        tickers_received=0,
                        duration_ms=round(duration, 2),
                        success=False,
                        error=str(e),
                    )
                    log.exception(
                        "chunk_fetch_failed",
                        market=market,
                        chunk_size=len(chunk_tickers),
                    )
                    # D-15: partial failures don't stop pipeline
                    return pd.DataFrame(), result

        tasks = [fetch_chunk(chunk) for chunk in chunks]
        for coro in asyncio.as_completed(tasks):
            result = await coro
            yield result
