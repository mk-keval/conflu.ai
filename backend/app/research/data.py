"""Data loading and downloading for research backtesting."""

import time
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd
import yfinance as yf


def load_universe(path: str = "config/replay_universe_sp500.txt") -> list[str]:
    """Load ticker symbols from universe file.
    
    Args:
        path: Path to universe file.
        
    Returns:
        List of ticker symbols (uppercase, '.' replaced with '-').
    """
    with open(path) as f:
        lines = f.readlines()
    
    tickers = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        ticker = line.upper().replace(".", "-")
        tickers.append(ticker)
    
    return tickers


def _clean_dataframe(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """Clean a single symbol's dataframe."""
    if df.empty:
        return df
    
    # Ensure lowercase column names
    df.columns = [c.lower() for c in df.columns]
    
    # Keep only required columns
    required = ["open", "high", "low", "close", "volume"]
    df = df[required].copy()
    
    # Drop rows with NaN in OHLC or volume < 0
    df = df.dropna(subset=["open", "high", "low", "close"])
    df = df[df["volume"] >= 0]
    
    # Drop duplicates
    df = df[~df.index.duplicated(keep="first")]
    
    # Ensure tz-naive datetime index ascending
    if df.index.tz is not None:
        df.index = df.index.tz_convert(None)
    df = df.sort_index()
    
    return df


def download_daily(
    symbols: list[str],
    start: str,
    end: str,
    cache_dir: str = ".cache/research"
) -> tuple[dict[str, pd.DataFrame], list[tuple[str, str]]]:
    """Download daily OHLCV data for symbols with caching.
    
    Args:
        symbols: List of ticker symbols.
        start: Start date (YYYY-MM-DD).
        end: End date (YYYY-MM-DD).
        cache_dir: Directory for cached CSV files.
        
    Returns:
        Tuple of (data dict symbol->DataFrame, list of dropped (symbol, reason)).
    """
    cache_path = Path(cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)
    
    # Always include SPY and VIX for benchmark
    all_symbols = list(set(symbols + ["SPY", "VIX"]))
    
    data = {}
    dropped = []
    
    # Process in batches of 20
    batch_size = 20
    for i in range(0, len(all_symbols), batch_size):
        batch = all_symbols[i:i + batch_size]
        
        for symbol in batch:
            cache_file = cache_path / f"{symbol}.csv.gz"
            
            # Check cache
            use_cache = False
            if cache_file.exists():
                mtime = cache_file.stat().st_mtime
                age_hours = (time.time() - mtime) / 3600
                if age_hours < 20:
                    use_cache = True
            
            if use_cache:
                try:
                    df = pd.read_csv(cache_file, index_col=0, parse_dates=True)
                    # Handle MultiIndex columns from cached data
                    if isinstance(df.columns, pd.MultiIndex):
                        if symbol in df.columns.get_level_values(0):
                            df = df[symbol]
                        else:
                            df = df[df.columns.get_level_values(0)[0]]
                    df = _clean_dataframe(df, symbol)
                    if len(df) >= 100:
                        data[symbol] = df
                    else:
                        dropped.append((symbol, f"insufficient rows after cleaning: {len(df)}"))
                except Exception as e:
                    dropped.append((symbol, f"cache read error: {e}"))
            else:
                # Download
                try:
                    df = yf.download(
                        symbol,
                        start=start,
                        end=end,
                        auto_adjust=True,
                        progress=False,
                        group_by="ticker"
                    )
                    
                    if df.empty:
                        dropped.append((symbol, "no data returned"))
                        continue
                    
                    # yfinance with group_by="ticker" returns MultiIndex columns
                    if isinstance(df.columns, pd.MultiIndex):
                        if symbol in df.columns.get_level_values(0):
                            df = df[symbol]
                        else:
                            # Try first level
                            df = df[df.columns.get_level_values(0)[0]]
                    
                    df = _clean_dataframe(df, symbol)
                    
                    if len(df) >= 100:
                        data[symbol] = df
                        # Save to cache
                        df.to_csv(cache_file, compression="gzip")
                    else:
                        dropped.append((symbol, f"insufficient rows after cleaning: {len(df)}"))
                        
                except Exception as e:
                    dropped.append((symbol, f"download error: {e}"))
        
        # Sleep between batches
        if i + batch_size < len(all_symbols):
            time.sleep(1)
    
    return data, dropped


def add_benchmark(data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Ensure SPY and VIX are in data dict (they're downloaded by download_daily)."""
    return data