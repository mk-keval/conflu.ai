"""Tests for scanner module — circuit breaker, retry, scan_symbols."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from backend.app.infrastructure.ingest.scanner import (
    circuit_breaker_state,
    reset_circuit_breaker,
    scan_symbols,
    scan_with_retry,
)


@pytest.fixture(autouse=True)
def reset_breaker() -> None:
    """Reset circuit breaker state before each test."""
    for market in ["america", "crypto", "test_market"]:
        reset_circuit_breaker(market)


def test_circuit_breaker_initial_state() -> None:
    """Circuit starts CLOSED with 0 failures."""
    state = circuit_breaker_state("america")
    assert state["state"] == "CLOSED"
    assert state["failures"] == 0


def test_circuit_breaker_reset() -> None:
    """reset_circuit_breaker() resets state."""
    state = circuit_breaker_state("test_market")
    state["state"] = "OPEN"
    state["failures"] = 5
    reset_circuit_breaker("test_market")
    state = circuit_breaker_state("test_market")
    assert state["state"] == "CLOSED"
    assert state["failures"] == 0


@pytest.mark.asyncio
async def test_scan_symbols_empty_tickers() -> None:
    """Empty tickers returns empty DataFrame."""
    df = await scan_symbols([], ["close"])
    assert df.empty


@pytest.mark.asyncio
async def test_scan_with_retry_empty_tickers() -> None:
    """scan_with_retry with empty tickers returns empty DataFrame."""
    df = await scan_with_retry([], ["close"])
    assert df.empty


@pytest.mark.asyncio
async def test_scan_with_retry_fails_after_retries() -> None:
    """Mock get_scanner_data to always raise, verify retry logic runs."""
    mock_query = MagicMock()
    mock_query.get_scanner_data.side_effect = RuntimeError("TV API error")

    with patch(
        "backend.app.infrastructure.ingest.scanner.Query",
        return_value=mock_query,
    ), pytest.raises(RuntimeError, match="TV API error"):
        await scan_with_retry(["NASDAQ:AAPL"], ["close"], "america")

    # Should have been called retry_max_attempts times (default 3)
    assert mock_query.get_scanner_data.call_count == 3


@pytest.mark.asyncio
async def test_scan_symbols_success() -> None:
    """Successful scan returns DataFrame."""
    mock_query = MagicMock()
    mock_df = pd.DataFrame({"ticker": ["NASDAQ:AAPL"], "close": [150.0]})
    mock_query.get_scanner_data.return_value = (1, mock_df)

    with patch(
        "backend.app.infrastructure.ingest.scanner.Query",
        return_value=mock_query,
    ):
        df = await scan_symbols(["NASDAQ:AAPL"], ["close"], "america")
        assert not df.empty
        assert df.iloc[0]["close"] == 150.0


@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_threshold() -> None:
    """Circuit breaker opens after threshold failures."""
    mock_query = MagicMock()
    mock_query.get_scanner_data.side_effect = RuntimeError("fail")

    with patch(
        "backend.app.infrastructure.ingest.scanner.Query",
        return_value=mock_query,
    ):
        for _ in range(5):
            with pytest.raises(RuntimeError):
                await scan_symbols(["NASDAQ:AAPL"], ["close"], "test_breaker")

    state = circuit_breaker_state("test_breaker")
    assert state["failures"] == 5
    assert state["state"] == "OPEN"
