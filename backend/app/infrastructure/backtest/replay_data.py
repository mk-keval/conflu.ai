"""Historical OHLCV plumbing for the paper-trade replay (D-71).

The live discovery pipeline queries TradingView's screener, which only answers
"now" — it cannot be rewound. The replay therefore evaluates the *same screen
templates* against locally cached OHLCV so we can show what the deployed
templates would have signalled on past days.

Data is fetched in **batched yfinance chunks** (one request per ~20 symbols)
instead of per-symbol, which keeps a 500-name universe well inside Yahoo's
informal rate limits. Frames are validated and cached under
``.cache/replay/`` so a run is reproducible without re-hitting Yahoo.

Nothing here writes to the journal; the caller decides whether to persist.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import yfinance as yf

from backend.app.core.logging import get_logger

log = get_logger("conflu.backtest.replay_data")

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_CACHE_DIR = REPO_ROOT / ".cache" / "replay"
DEFAULT_UNIVERSE_FILE = REPO_ROOT / "config" / "replay_universe_sp500.txt"

BATCH_SIZE = 20
CHUNK_SLEEP_SECONDS = 1.0
CACHE_MAX_AGE_HOURS = 20
MIN_DAILY_BARS = 200
MIN_HOURLY_BARS = 100

_OHLCV = ("Open", "High", "Low", "Close", "Volume")


# ── Universe ────────────────────────────────────────────────────────────────


def load_universe(path: str | Path | None = None) -> list[str]:
    """Read a newline-delimited ticker file (comments with ``#`` allowed)."""
    p = Path(path or DEFAULT_UNIVERSE_FILE)
    if not p.exists():
        raise FileNotFoundError(
            f"Replay universe file not found: {p}. "
            "Run `python run_paper_replay.py --refresh-universe` to create it."
        )
    symbols: list[str] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        symbols.append(raw.upper().replace(".", "-"))
    return sorted(set(symbols))


def refresh_sp500_universe(path: str | Path | None = None) -> list[str]:
    """Fetch the current S&P 500 constituent list and rewrite the ticker file.

    Wikipedia blocks the default urllib user-agent; a browser UA is used. The
    list is a *current* membership snapshot, so survivorship bias remains (the
    replay is a screen-behavior demo, not a P&L promise).
    """
    import io

    import requests

    p = Path(path or DEFAULT_UNIVERSE_FILE)
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    ua = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/124 Safari/537.36"
        )
    }
    resp = requests.get(url, headers=ua, timeout=30)
    resp.raise_for_status()
    tables = pd.read_html(io.StringIO(resp.text))
    symbols = [
        str(s).strip().upper().replace(".", "-")
        for s in tables[0]["Symbol"].tolist()
    ]
    symbols = sorted(set(symbols))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        "# S&P 500 constituents (current snapshot, survivorship bias remains)\n"
        + "\n".join(symbols)
        + "\n",
        encoding="utf-8",
    )
    log.info("replay.universe.refreshed", path=str(p), count=len(symbols))
    return symbols


# ── Normalisation / validation ──────────────────────────────────────────────


def normalize_frame(df: pd.DataFrame | None) -> pd.DataFrame | None:
    """Return a clean, tz-naive OHLCV frame or ``None`` when unusable."""
    if df is None or getattr(df, "empty", True):
        return None
    frame = df.copy()
    if isinstance(frame.columns, pd.MultiIndex):
        # Single-ticker slices occasionally retain a one-level MultiIndex.
        frame.columns = [str(c[0] if isinstance(c, tuple) else c) for c in frame.columns]
    rename = {c: str(c).strip().title() for c in frame.columns}
    frame = frame.rename(columns=rename)
    if any(c not in frame.columns for c in _OHLCV):
        return None
    frame = frame[list(_OHLCV)]
    frame = frame.apply(pd.to_numeric, errors="coerce")
    frame = frame.dropna(subset=["Open", "High", "Low", "Close"])
    if frame.empty:
        return None
    frame = frame[~frame.index.duplicated(keep="last")].sort_index()
    index = pd.to_datetime(frame.index)
    if getattr(index, "tz", None) is not None:
        index = index.tz_localize(None)
    frame.index = index
    return frame


def _extract_tickers(raw: pd.DataFrame, symbols: list[str]) -> dict[str, pd.DataFrame]:
    """Split a ``yf.download(group_by='ticker')`` result into clean frames."""
    out: dict[str, pd.DataFrame] = {}
    if raw is None or raw.empty:
        return out
    if isinstance(raw.columns, pd.MultiIndex):
        level = raw.columns.get_level_values(0)
        for symbol in symbols:
            if symbol not in level:
                continue
            frame = normalize_frame(raw[symbol])
            if frame is not None:
                out[symbol] = frame
    elif len(symbols) == 1:
        frame = normalize_frame(raw)
        if frame is not None:
            out[symbols[0]] = frame
    return out


# ── Cache ───────────────────────────────────────────────────────────────────


def _cache_meta_path(cache_dir: Path) -> Path:
    return cache_dir / "meta.json"


def _read_meta(cache_dir: Path) -> dict[str, Any]:
    path = _cache_meta_path(cache_dir)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - corrupt cache is simply a miss
        return {}


def _write_meta(cache_dir: Path, meta: dict[str, Any]) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    _cache_meta_path(cache_dir).write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )


def _cache_covers(
    meta: dict[str, Any], kind: str, start: str, end: str
) -> bool:
    block = meta.get(kind) or {}
    try:
        fetched = datetime.fromisoformat(block["fetched_at"])
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=UTC)
        fresh = (datetime.now(UTC) - fetched).total_seconds() < CACHE_MAX_AGE_HOURS * 3600
        covers = block.get("start", "9999") <= start and block.get("end", "0000") >= end
        return bool(fresh and covers)
    except Exception:  # noqa: BLE001
        return False


def _load_cached(cache_dir: Path, kind: str, symbols: list[str]) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    folder = cache_dir / kind
    for symbol in symbols:
        path = folder / f"{_safe_name(symbol)}.pkl"
        if not path.exists():
            continue
        try:
            frame = pd.read_pickle(path)
        except Exception:  # noqa: BLE001
            continue
        if isinstance(frame, pd.DataFrame) and not frame.empty:
            out[symbol] = frame
    return out


def _save_cached(cache_dir: Path, kind: str, data: dict[str, pd.DataFrame]) -> None:
    folder = cache_dir / kind
    folder.mkdir(parents=True, exist_ok=True)
    for symbol, frame in data.items():
        frame.to_pickle(folder / f"{_safe_name(symbol)}.pkl")


def _safe_name(symbol: str) -> str:
    return symbol.replace("^", "_").replace("/", "_").replace("\\", "_")


# ── Fetch ───────────────────────────────────────────────────────────────────


def _download_chunk(
    symbols: list[str],
    *,
    start: str,
    end: str,
    interval: str,
    retries: int = 2,
) -> dict[str, pd.DataFrame]:
    """Batch-download one chunk, then fall back per-symbol for any misses."""
    # yfinance's `end` is exclusive: add a day so `end` itself is included.
    end_exclusive = (date.fromisoformat(end) + timedelta(days=1)).isoformat()
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            raw = yf.download(
                symbols,
                start=start,
                end=end_exclusive,
                interval=interval,
                group_by="ticker",
                threads=True,
                progress=False,
                auto_adjust=False,
                actions=False,
                prepost=False,
            )
            frames = _extract_tickers(raw, symbols)
            if frames:
                return frames
        except Exception as exc:  # noqa: BLE001 - retried below
            last_error = exc
            time.sleep(1.5 * (attempt + 1))

    # Fallback: one request per miss (slow but resilient).
    frames = {}
    for symbol in symbols:
        try:
            ticker = yf.Ticker(symbol)
            raw = ticker.history(
                start=start,
                end=end_exclusive,
                interval=interval,
                auto_adjust=False,
                actions=False,
                prepost=False,
            )
            frame = normalize_frame(raw)
            if frame is not None:
                frames[symbol] = frame
        except Exception as exc:  # noqa: BLE001
            last_error = exc
        time.sleep(0.2)
    if last_error is not None and not frames:
        log.warning("replay.fetch.chunk_failed", symbols=symbols[:3], error=str(last_error))
    return frames


def fetch_history(
    symbols: list[str],
    *,
    start: str,
    end: str,
    interval: str,
    cache_dir: str | Path | None = None,
    refresh: bool = False,
    progress: bool = True,
) -> tuple[dict[str, pd.DataFrame], list[str]]:
    """Fetch (or load) daily/hourly frames for ``symbols``.

    Returns ``(frames, missing)``. Cache keys are per symbol; the metadata
    block records the covered window so a later run with a wider window
    refetches instead of silently serving a shorter slice.
    """
    kind = "daily" if interval == "1d" else "hourly"
    root = Path(cache_dir or DEFAULT_CACHE_DIR)
    meta = _read_meta(root)

    if not refresh and _cache_covers(meta, kind, start, end):
        cached = _load_cached(root, kind, symbols)
        missing = [s for s in symbols if s not in cached]
        if not missing:
            if progress:
                print(f"  {kind}: loaded {len(cached)} cached frames")
            return cached, []
        if progress:
            print(f"  {kind}: cache hit for {len(cached)}, fetching {len(missing)}")
        symbols_to_fetch = missing
    else:
        symbols_to_fetch = list(symbols)

    fetched: dict[str, pd.DataFrame] = {}
    total = len(symbols_to_fetch)
    for index in range(0, total, BATCH_SIZE):
        chunk = symbols_to_fetch[index : index + BATCH_SIZE]
        if progress:
            done = min(index + len(chunk), total)
            print(f"  {kind}: fetching {done}/{total}...")
        frames = _download_chunk(chunk, start=start, end=end, interval=interval)
        fetched.update(frames)
        if index + BATCH_SIZE < total:
            time.sleep(CHUNK_SLEEP_SECONDS)

    _save_cached(root, kind, fetched)
    meta = _read_meta(root)
    window = meta.get(kind) or {}
    covered_start = min(start, window.get("start", start))
    covered_end = max(end, window.get("end", end))
    meta[kind] = {
        "start": covered_start,
        "end": covered_end,
        "fetched_at": datetime.now(UTC).isoformat(),
    }
    _write_meta(root, meta)

    if refresh and not _cache_covers(meta, kind, start, end):
        # Defensive: metadata should always cover what we just fetched.
        meta[kind] = {
            "start": start,
            "end": end,
            "fetched_at": datetime.now(UTC).isoformat(),
        }
        _write_meta(root, meta)

    merged = _load_cached(root, kind, symbols)
    missing = [s for s in symbols if s not in merged]
    return merged, missing


def filter_usable(
    daily: dict[str, pd.DataFrame],
    hourly: dict[str, pd.DataFrame],
    *,
    min_daily: int = MIN_DAILY_BARS,
    min_hourly: int = MIN_HOURLY_BARS,
) -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame], dict[str, str]]:
    """Drop frames with too little history; return reasons for the drops."""
    daily_ok: dict[str, pd.DataFrame] = {}
    hourly_ok: dict[str, pd.DataFrame] = {}
    dropped: dict[str, str] = {}
    for symbol, frame in daily.items():
        if len(frame) < min_daily:
            dropped[symbol] = f"daily bars {len(frame)} < {min_daily}"
            continue
        daily_ok[symbol] = frame
    for symbol, frame in hourly.items():
        if len(frame) < min_hourly:
            dropped[symbol] = (
                f"{dropped[symbol]}; " if symbol in dropped else ""
            ) + f"hourly bars {len(frame)} < {min_hourly}"
            continue
        if symbol in daily_ok:
            hourly_ok[symbol] = frame
    return daily_ok, hourly_ok, dropped


def fetch_regime_frames(
    *,
    start: str,
    end: str,
    cache_dir: str | Path | None = None,
    refresh: bool = False,
) -> dict[str, pd.DataFrame]:
    """Daily frames for the macro + sector-breadth symbols."""
    from backend.app.infrastructure.market.regime import MACRO_SYMBOLS, SECTOR_SYMBOLS

    symbols = sorted(set(MACRO_SYMBOLS) | set(SECTOR_SYMBOLS))
    root = Path(cache_dir or DEFAULT_CACHE_DIR)
    meta = _read_meta(root)
    if not refresh and _cache_covers(meta, "regime", start, end):
        cached = _load_cached(root, "regime", symbols)
        if len(cached) == len(symbols):
            return cached

    frames = _download_chunk(symbols, start=start, end=end, interval="1d")
    _save_cached(root, "regime", frames)
    meta = _read_meta(root)
    meta["regime"] = {
        "start": start,
        "end": end,
        "fetched_at": datetime.now(UTC).isoformat(),
    }
    _write_meta(root, meta)
    return frames
