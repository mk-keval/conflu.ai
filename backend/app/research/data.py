"""Data loading, caching and downloading for research backtesting.

The cache contract is explicit: a cached file is only valid for the exact
``(symbol, start, end)`` request that produced it. The previous implementation
reused any file younger than 20 hours and taller than 100 rows, so a 2020-only
download could satisfy a 2020-2023 request and silently produce a mixed panel
(see D-79).
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

MANIFEST_NAME = "_manifest.json"


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


def _normalise_span(start: str, end: str) -> tuple[str, str]:
    """Return an inclusive ``(start, end)`` pair as YYYY-MM-DD strings.

    ``end`` is inclusive here; yfinance treats its ``end`` as exclusive, so the
    download call adds one day.
    """
    start_ts = pd.Timestamp(start).normalize()
    end_ts = pd.Timestamp(end).normalize()
    if end_ts < start_ts:
        raise ValueError(f"end ({end}) is before start ({start})")
    return start_ts.strftime("%Y-%m-%d"), end_ts.strftime("%Y-%m-%d")


def _cache_key(symbol: str, start: str, end: str) -> str:
    """Cache key includes the requested span, so spans cannot be mixed."""
    return f"{symbol}__{start}__{end}"


def _read_manifest(cache_path: Path) -> dict:
    """Read the cache manifest. A corrupt or missing manifest means an empty one."""
    manifest_path = cache_path / MANIFEST_NAME
    if not manifest_path.exists():
        return {}
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _write_manifest(cache_path: Path, manifest: dict) -> None:
    """Write the manifest atomically."""
    manifest_path = cache_path / MANIFEST_NAME
    tmp_path = manifest_path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp_path, manifest_path)


def download_daily(
    symbols: list[str],
    start: str,
    end: str,
    cache_dir: str = ".cache/research",
    max_age_hours: float = 20.0,
    force_download: bool = False,
) -> tuple[dict[str, pd.DataFrame], list[tuple[str, str]], dict]:
    """Download daily OHLCV data for symbols with a span-keyed cache.

    A cached file is reused only when it was downloaded for the same requested
    span and is younger than ``max_age_hours``. Changing the window therefore
    forces a new download instead of silently reusing a shorter history.

    Args:
        symbols: List of ticker symbols.
        start: Start date (inclusive, YYYY-MM-DD).
        end: End date (inclusive, YYYY-MM-DD).
        cache_dir: Directory for cached CSV files and the manifest.
        max_age_hours: Reuse a cache entry only if it is younger than this.
        force_download: Ignore the cache entirely.

    Returns:
        Tuple of:
            data: symbol -> DataFrame.
            dropped: list of (symbol, reason).
            stats: cache/run counters for the artifact metadata.
    """
    start, end = _normalise_span(start, end)
    cache_path = Path(cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)

    manifest = _read_manifest(cache_path)
    stats = {
        "cache_dir": str(cache_path),
        "requested_start": start,
        "requested_end": end,
        "hits": 0,
        "misses": 0,
        "downloaded": 0,
        "failed": 0,
    }

    # Always include SPY and VIX for benchmark. Sorted so the panel (and the
    # engine's per-date shuffle) is reproducible across processes.
    all_symbols = sorted(set(symbols + ["SPY", "VIX"]))

    data = {}
    dropped = []
    end_exclusive = (pd.Timestamp(end) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

    batch_size = 20
    for i in range(0, len(all_symbols), batch_size):
        batch = all_symbols[i:i + batch_size]

        for symbol in batch:
            key = _cache_key(symbol, start, end)
            cache_file = cache_path / f"{key}.csv.gz"
            meta = manifest.get(key)

            use_cache = False
            if not force_download and meta and cache_file.exists():
                same_request = (
                    meta.get("requested_start") == start
                    and meta.get("requested_end") == end
                )
                age_hours = (time.time() - cache_file.stat().st_mtime) / 3600
                use_cache = same_request and age_hours < max_age_hours

            if use_cache:
                try:
                    df = pd.read_csv(cache_file, index_col=0, parse_dates=True)
                    if isinstance(df.columns, pd.MultiIndex):
                        if symbol in df.columns.get_level_values(0):
                            df = df[symbol]
                        else:
                            df = df[df.columns.get_level_values(0)[0]]
                    df = _clean_dataframe(df, symbol)
                    # Defensive: the cache key already pins the span, but clip so
                    # a hand-copied file can never widen the panel.
                    df = df.loc[start:end]
                    if len(df) >= 100:
                        data[symbol] = df
                        stats["hits"] += 1
                    else:
                        dropped.append((symbol, f"insufficient rows after cleaning: {len(df)}"))
                        stats["hits"] += 1
                    continue
                except Exception as e:
                    # Corrupt cache entry: warn and fall through to a fresh
                    # download. Do not mark the symbol as dropped.
                    print(f"  cache read error for {symbol}: {e}")

            stats["misses"] += 1
            try:
                df = yf.download(
                    symbol,
                    start=start,
                    end=end_exclusive,
                    auto_adjust=True,
                    progress=False,
                    group_by="ticker",
                )

                if df.empty:
                    dropped.append((symbol, "no data returned"))
                    stats["failed"] += 1
                    continue

                # yfinance with group_by="ticker" returns MultiIndex columns
                if isinstance(df.columns, pd.MultiIndex):
                    if symbol in df.columns.get_level_values(0):
                        df = df[symbol]
                    else:
                        # Try first level
                        df = df[df.columns.get_level_values(0)[0]]

                df = _clean_dataframe(df, symbol).loc[start:end]

                if len(df) >= 100:
                    data[symbol] = df
                    df.to_csv(cache_file, compression="gzip")
                    manifest[key] = {
                        "symbol": symbol,
                        "requested_start": start,
                        "requested_end": end,
                        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        "rows": int(len(df)),
                        "actual_start": df.index.min().strftime("%Y-%m-%d"),
                        "actual_end": df.index.max().strftime("%Y-%m-%d"),
                    }
                    stats["downloaded"] += 1
                else:
                    dropped.append((symbol, f"insufficient rows after cleaning: {len(df)}"))
                    stats["failed"] += 1

            except Exception as e:
                dropped.append((symbol, f"download error: {e}"))
                stats["failed"] += 1

        # Sleep between batches
        if i + batch_size < len(all_symbols):
            time.sleep(1)

    _write_manifest(cache_path, manifest)
    return data, dropped, stats


def panel_span(
    data: dict[str, pd.DataFrame],
    exclude: tuple[str, ...] = ("SPY", "VIX"),
) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    """Return the (first, last) trading date of the tradable panel."""
    frames = [df for sym, df in data.items() if sym not in exclude and len(df)]
    if not frames:
        return None, None
    return min(df.index.min() for df in frames), max(df.index.max() for df in frames)


def add_benchmark(data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Ensure SPY and VIX are in data dict (they're downloaded by download_daily)."""
    return data
