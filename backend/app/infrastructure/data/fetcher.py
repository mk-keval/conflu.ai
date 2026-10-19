"""
Robust OHLCV Data Fetcher with Multiple Sources
Fetches from Yahoo Finance (primary) and caches locally
"""

from __future__ import annotations

import asyncio
import os
import pickle
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import yfinance as yf

from backend.app.core.logging import get_logger

log = get_logger("conflu.data.fetcher")

# Cache directory
CACHE_DIR = Path(os.getenv("CONFLU_CACHE_DIR", ".cache/ohlcv"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Rate limiting
REQUEST_DELAY = 0.1  # seconds between requests
MAX_RETRIES = 3
RETRY_DELAY = 1.0


class OHLCVFetcher:
    """
    Robust OHLCV data fetcher with caching and multiple source fallback.
    
    Features:
    - Yahoo Finance as primary source (reliable, free)
    - Local caching (pickle + parquet)
    - Automatic retry with exponential backoff
    - Rate limiting
    - Data validation
    """
    
    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        request_delay: float = REQUEST_DELAY,
        max_retries: int = MAX_RETRIES,
    ):
        self.cache_dir = cache_dir or CACHE_DIR
        self.request_delay = request_delay
        self.max_retries = max_retries
        self._last_request = 0.0
    
    def _cache_path(self, symbol: str, timeframe: str, start: str, end: str) -> Path:
        """Generate cache file path."""
        key = f"{symbol}_{timeframe}_{start}_{end}"
        return self.cache_dir / f"{key}.parquet"
    
    def _meta_path(self, symbol: str, timeframe: str, start: str, end: str) -> Path:
        """Generate metadata file path."""
        key = f"{symbol}_{timeframe}_{start}_{end}"
        return self.cache_dir / f"{key}.meta"
    
    async def _rate_limit(self):
        """Enforce rate limiting."""
        now = time.time()
        elapsed = now - self._last_request
        if elapsed < self.request_delay:
            await asyncio.sleep(self.request_delay - elapsed)
        self._last_request = time.time()
    
    def _load_from_cache(self, cache_path: Path) -> Optional[pd.DataFrame]:
        """Load data from cache if valid."""
        if not cache_path.exists():
            return None
        try:
            df = pd.read_parquet(cache_path)
            log.debug(f"Loaded from cache: {cache_path}")
            return df
        except Exception as e:
            log.warning(f"Cache read failed: {e}")
            return None
    
    def _save_to_cache(self, df: pd.DataFrame, cache_path: Path):
        """Save data to cache."""
        try:
            df.to_parquet(cache_path, compression='snappy')
            log.debug(f"Saved to cache: {cache_path}")
        except Exception as e:
            log.warning(f"Cache write failed: {e}")
    
    def _normalize_timeframe(self, timeframe: str) -> str:
        """Normalize timeframe to yfinance format."""
        mapping = {
            "1D": "1d",
            "1W": "1wk",
            "1M": "1mo",
            "4h": "4h",
            "1h": "1h",
            "30m": "30m",
            "15m": "15m",
            "5m": "5m",
            "1m": "1m",
        }
        return mapping.get(timeframe, timeframe)
    
    def _validate_data(self, df: pd.DataFrame, symbol: str) -> bool:
        """Validate fetched data."""
        if df is None or df.empty:
            return False
        
        required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        if not all(col in df.columns for col in required_cols):
            log.warning(f"{symbol}: Missing required columns")
            return False
        
        # Check for reasonable data
        if len(df) < 2:
            log.warning(f"{symbol}: Too few rows ({len(df)})")
            return False
        
        # Check for NaN in critical columns
        if df[['Open', 'High', 'Low', 'Close']].isna().any().any():
            log.warning(f"{symbol}: NaN values in OHLC")
            return False
        
        # Validate price relationships
        invalid = (df['High'] < df['Low']) | (df['High'] < df['Open']) | (df['High'] < df['Close']) | \
                  (df['Low'] > df['Open']) | (df['Low'] > df['Close'])
        if invalid.any():
            log.warning(f"{symbol}: Invalid OHLC relationships")
            return False
        
        return True
    
    async def fetch_yahoo(
        self,
        symbol: str,
        timeframe: str = "1D",
        start: Optional[str] = None,
        end: Optional[str] = None,
        period: str = "max",
    ) -> Optional[pd.DataFrame]:
        """
        Fetch OHLCV data from Yahoo Finance.
        
        Args:
            symbol: Ticker symbol (e.g., "AAPL")
            timeframe: Timeframe (1D, 4h, 1h, etc.)
            start: Start date (YYYY-MM-DD)
            end: End date (YYYY-MM-DD)
            period: Period string for yfinance (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
        
        Returns:
            DataFrame with OHLCV data or None if failed
        """
        await self._rate_limit()
        
        # Check cache first
        cache_start = start or (datetime.now() - timedelta(days=365*5)).strftime("%Y-%m-%d")
        cache_end = end or datetime.now().strftime("%Y-%m-%d")
        cache_path = self._cache_path(symbol, timeframe, cache_start, cache_end)
        
        cached = self._load_from_cache(cache_path)
        if cached is not None:
            # Filter to requested range
            if start:
                cached = cached[cached.index >= pd.Timestamp(start)]
            if end:
                cached = cached[cached.index <= pd.Timestamp(end)]
            return cached
        
        # Fetch from Yahoo
        yf_tf = self._normalize_timeframe(timeframe)

        # yfinance treats `end` as exclusive; add one day so the requested
        # end date is included, matching the cache-read path below.
        fetch_end = end
        if fetch_end:
            fetch_end = (
                pd.Timestamp(fetch_end) + pd.Timedelta(days=1)
            ).strftime("%Y-%m-%d")

        for attempt in range(self.max_retries):
            try:
                ticker = yf.Ticker(symbol)

                # Honour an explicit start/end window. Previously this branch
                # required a non-"max" period, so with the default period a
                # cold cache returned FULL history while cache reads returned
                # only the window — the same backtest could silently use
                # different spans depending on cache state (found during the
                # 2026-10-19 validation reset).
                if start:
                    df = ticker.history(
                        start=start,
                        end=fetch_end,
                        interval=yf_tf,
                        auto_adjust=False,
                        prepost=False,
                    )
                else:
                    df = ticker.history(
                        period=period,
                        interval=yf_tf,
                        auto_adjust=False,
                        prepost=False,
                    )
                
                if df.empty:
                    log.warning(f"{symbol}: Empty response from Yahoo")
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                        continue
                    return None
                
                # Standardize column names
                df = df.rename(columns={
                    'Open': 'Open',
                    'High': 'High',
                    'Low': 'Low',
                    'Close': 'Close',
                    'Volume': 'Volume',
                })
                
                # Ensure datetime index
                if not isinstance(df.index, pd.DatetimeIndex):
                    df.index = pd.to_datetime(df.index)
                
                # Remove timezone info for consistency
                if df.index.tz is not None:
                    df.index = df.index.tz_localize(None)
                
                # Keep only OHLCV
                df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()

                # Enforce the requested window exactly like the cache-read
                # path does, so fresh and cached fetches are identical.
                if start:
                    df = df[df.index >= pd.Timestamp(start)]
                if end:
                    df = df[df.index <= pd.Timestamp(end)]
                if df.empty:
                    log.warning(f"{symbol}: No bars in requested range {start}..{end}")
                    return None

                # Validate
                if not self._validate_data(df, symbol):
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                        continue
                    return None
                
                # Save to cache
                self._save_to_cache(df, cache_path)
                
                log.info(f"Fetched {len(df)} bars for {symbol} ({timeframe})")
                return df
                
            except Exception as e:
                log.warning(f"{symbol} fetch attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                else:
                    log.error(f"{symbol}: All fetch attempts failed")
                    return None
        
        return None
    
    async def fetch_multiple(
        self,
        symbols: list[str],
        timeframe: str = "1D",
        start: Optional[str] = None,
        end: Optional[str] = None,
        period: str = "2y",
    ) -> dict[str, pd.DataFrame]:
        """Fetch multiple symbols concurrently with rate limiting."""
        semaphore = asyncio.Semaphore(5)  # Limit concurrent requests
        
        async def fetch_one(sym: str) -> tuple[str, Optional[pd.DataFrame]]:
            async with semaphore:
                df = await self.fetch_yahoo(sym, timeframe, start, end, period)
                return sym, df
        
        tasks = [fetch_one(sym) for sym in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        result_dict = {}
        for result in results:
            if isinstance(result, Exception):
                log.error(f"Fetch failed: {result}")
            elif isinstance(result, tuple):
                sym, df = result
                if df is not None:
                    result_dict[sym] = df
        
        return result_dict
    
    def get_cached_data(
        self,
        symbol: str,
        timeframe: str = "1D",
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> Optional[pd.DataFrame]:
        """Get data from cache only (no network)."""
        cache_start = start or (datetime.now() - timedelta(days=365*5)).strftime("%Y-%m-%d")
        cache_end = end or datetime.now().strftime("%Y-%m-%d")
        cache_path = self._cache_path(symbol, timeframe, cache_start, cache_end)
        
        df = self._load_from_cache(cache_path)
        if df is not None:
            if start:
                df = df[df.index >= pd.Timestamp(start)]
            if end:
                df = df[df.index <= pd.Timestamp(end)]
            return df
        return None


# Convenience function
async def fetch_ohlcv(
    symbols: list[str],
    timeframe: str = "1D",
    start: Optional[str] = None,
    end: Optional[str] = None,
    period: str = "2y",
) -> dict[str, pd.DataFrame]:
    """Fetch OHLCV for multiple symbols."""
    fetcher = OHLCVFetcher()
    return await fetcher.fetch_multiple(symbols, timeframe, start, end, period)


# CLI for testing
if __name__ == "__main__":
    import sys
    
    async def main():
        if len(sys.argv) < 2:
            print("Usage: python fetcher.py SYMBOL [TIMEFRAME] [START] [END]")
            sys.exit(1)
        
        symbol = sys.argv[1].upper()
        timeframe = sys.argv[2] if len(sys.argv) > 2 else "1D"
        start = sys.argv[3] if len(sys.argv) > 3 else None
        end = sys.argv[4] if len(sys.argv) > 4 else None
        
        fetcher = OHLCVFetcher()
        df = await fetcher.fetch_yahoo(symbol, timeframe, start, end)
        
        if df is not None:
            print(f"\n{symbol} - {len(df)} bars")
            print(f"Date range: {df.index[0]} to {df.index[-1]}")
            print(f"\nLast 5 rows:")
            print(df.tail())
            print(f"\nStats:")
            print(f"  Close range: {df['Close'].min():.2f} - {df['Close'].max():.2f}")
            print(f"  Volume avg: {df['Volume'].mean():,.0f}")
        else:
            print(f"Failed to fetch {symbol}")
    
    asyncio.run(main())