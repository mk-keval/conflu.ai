"""Thread-pool wrapper around tradingview-screener with retry and circuit breaker."""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Sequence
from typing import Any

import pandas as pd
from tradingview_screener import Query

from backend.app.core.config import settings
from backend.app.core.logging import get_logger

log = get_logger("conflu.ingest.scanner")

# Circuit breaker state per market
_CIRCUIT_BREAKER_STATE: dict[str, dict[str, Any]] = {}


def _get_breaker(market: str) -> dict[str, Any]:
    """Get or initialize circuit breaker state for a market."""
    if market not in _CIRCUIT_BREAKER_STATE:
        _CIRCUIT_BREAKER_STATE[market] = {
            "state": "CLOSED",
            "failures": 0,
            "last_failure": 0.0,
        }
    return _CIRCUIT_BREAKER_STATE[market]


async def scan_symbols(
    tickers: Sequence[str],
    columns: Sequence[str],
    market: str = "america",
) -> pd.DataFrame:
    """Fetch scanner data for a batch of tickers asynchronously.

    Runs the synchronous tradingview-screener Query in a thread pool
    to avoid blocking the event loop.

    Args:
        tickers: List of TV tickers (e.g., ['NASDAQ:AAPL', 'BINANCE:BTCUSDT']).
        columns: OHLCV field names to select (e.g., ['close', 'volume']).
        market: TradingView market name.

    Returns:
        DataFrame with ticker column + requested columns.
    """
    breaker = _get_breaker(market)

    # Check circuit breaker
    if breaker["state"] == "OPEN":
        cooldown_elapsed = time.monotonic() - breaker["last_failure"]
        if cooldown_elapsed < settings.ingestion.circuit_breaker_cooldown_s:
            raise RuntimeError(
                f"Circuit breaker OPEN for market '{market}' "
                f"(cooldown: {cooldown_elapsed:.1f}s / "
                f"{settings.ingestion.circuit_breaker_cooldown_s}s)"
            )
        # Half-open: allow one request through
        breaker["state"] = "HALF_OPEN"
        log.info("circuit_breaker_half_open", market=market)

    if not tickers:
        return pd.DataFrame()

    q = Query()
    q.select(*columns)
    q.set_tickers(*tickers)
    q.limit(len(tickers))

    loop = asyncio.get_running_loop()
    try:
        total, df = await loop.run_in_executor(None, q.get_scanner_data)
        # Reset circuit breaker on success
        breaker["state"] = "CLOSED"
        breaker["failures"] = 0
        log.info(
            "scan_completed",
            market=market,
            requested=len(tickers),
            received=len(df),
            total_available=total,
        )
        return df
    except Exception:
        # Increment circuit breaker
        breaker["failures"] += 1
        breaker["last_failure"] = time.monotonic()
        if breaker["failures"] >= settings.ingestion.circuit_breaker_threshold:
            breaker["state"] = "OPEN"
            log.warning(
                "circuit_breaker_opened",
                market=market,
                failures=breaker["failures"],
                threshold=settings.ingestion.circuit_breaker_threshold,
            )
        log.exception("scan_failed", market=market, ticker_count=len(tickers))
        raise


async def scan_with_retry(
    tickers: Sequence[str],
    columns: Sequence[str],
    market: str = "america",
) -> pd.DataFrame:
    """Fetch scanner data with exponential backoff retry.

    Retries on any exception up to retry_max_attempts times.
    Adds jitter to avoid thundering herd.
    """
    if not tickers:
        return pd.DataFrame()

    last_exception: Exception | None = None
    cfg = settings.ingestion

    for attempt in range(cfg.retry_max_attempts):
        try:
            return await scan_symbols(tickers, columns, market)
        except Exception as e:
            last_exception = e
            if attempt < cfg.retry_max_attempts - 1:
                delay = min(
                    cfg.retry_base_delay_s * (cfg.retry_backoff_factor**attempt),
                    cfg.retry_max_delay_s,
                )
                # Add jitter
                jitter = delay * cfg.retry_jitter
                actual_delay = delay * (1 + random.uniform(-jitter, jitter))
                log.warning(
                    "scan_retry",
                    market=market,
                    attempt=attempt + 1,
                    max_attempts=cfg.retry_max_attempts,
                    delay_seconds=round(actual_delay, 2),
                    error=str(e),
                )
                await asyncio.sleep(actual_delay)

    log.error(
        "scan_failed_after_retries",
        market=market,
        tickers=len(tickers),
        attempts=cfg.retry_max_attempts,
        last_error=str(last_exception),
    )
    raise last_exception  # type: ignore[misc]


def circuit_breaker_state(market: str) -> dict[str, Any]:
    """Return a copy of circuit breaker state for a market."""
    return dict(_get_breaker(market))


def reset_circuit_breaker(market: str) -> None:
    """Reset circuit breaker state for a market."""
    _CIRCUIT_BREAKER_STATE[market] = {
        "state": "CLOSED",
        "failures": 0,
        "last_failure": 0.0,
    }
    log.info("circuit_breaker_reset", market=market)
