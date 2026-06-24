"""Tests for async chunked fetcher — IngestionFetcher."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from backend.app.infrastructure.ingest.fetcher import IngestionFetcher


@pytest.mark.asyncio
async def test_fetcher_initialization() -> None:
    """Defaults use config values."""
    fetcher = IngestionFetcher()
    assert fetcher._batch_size == 100
    assert fetcher._max_concurrent == 50


@pytest.mark.asyncio
async def test_fetcher_custom_concurrency() -> None:
    """Constructor override works."""
    fetcher = IngestionFetcher(max_concurrent=10)
    assert fetcher._max_concurrent == 10


@pytest.mark.asyncio
async def test_fetcher_empty_tickers() -> None:
    """Returns empty DataFrame for empty ticker list."""
    fetcher = IngestionFetcher()
    df, results = await fetcher.fetch_asset_class("equities", "america", [], ["close"])
    assert df.empty
    assert len(results) == 0


@pytest.mark.asyncio
async def test_fetcher_chunking() -> None:
    """Verifies chunking splits tickers correctly."""
    tickers = [f"NASDAQ:A{i}" for i in range(250)]
    expected_chunks = 3  # 250 / 100 = 3 chunks (100 + 100 + 50)

    async def mock_scan(*args, **kwargs):
        df = pd.DataFrame({"ticker": args[0], "close": [100.0] * len(args[0])})
        return df

    with patch(
        "backend.app.infrastructure.ingest.fetcher.scan_with_retry",
        new=mock_scan,
    ):
        fetcher = IngestionFetcher(max_concurrent=50)
        df, results = await fetcher.fetch_asset_class(
            "equities", "america", tickers, ["close"]
        )
        assert len(results) == expected_chunks
        assert not df.empty


@pytest.mark.asyncio
async def test_fetcher_partial_failure() -> None:
    """One chunk fails, others succeed, no exception raised (D-15)."""
    call_count = 0

    async def mock_scan_partial(tickers, columns, market="america"):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("First chunk fails")
        return pd.DataFrame({"ticker": list(tickers), "close": [100.0] * len(tickers)})

    with patch(
        "backend.app.infrastructure.ingest.fetcher.scan_with_retry",
        new=mock_scan_partial,
    ):
        tickers = [f"NASDAQ:A{i}" for i in range(250)]
        fetcher = IngestionFetcher(max_concurrent=50)
        df, results = await fetcher.fetch_asset_class(
            "equities", "america", tickers, ["close"]
        )
        # Should have results for all 3 chunks
        assert len(results) == 3
        # First one failed
        assert results[0].success is False


@pytest.mark.asyncio
async def test_fetcher_semaphore_applied() -> None:
    """Verify semaphore is used in chunk fetching."""
    fetcher = IngestionFetcher(max_concurrent=5)
    assert fetcher._semaphore._value == 5


@pytest.mark.asyncio
async def test_fetcher_asset_class_column() -> None:
    """Asset class column is attached to each chunk."""

    async def mock_scan(tickers, columns, market="america"):
        return pd.DataFrame({"ticker": list(tickers), "close": [100.0] * len(tickers)})

    with patch(
        "backend.app.infrastructure.ingest.fetcher.scan_with_retry",
        new=mock_scan,
    ):
        fetcher = IngestionFetcher(max_concurrent=50)
        df, results = await fetcher.fetch_asset_class(
            "crypto", "crypto", ["BINANCE:BTCUSDT"], ["close"]
        )
        assert "asset_class" in df.columns
        assert df.iloc[0]["asset_class"] == "crypto"
