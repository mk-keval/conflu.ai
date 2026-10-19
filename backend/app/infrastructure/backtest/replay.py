"""Two-month paper-trade replay (D-71) — orchestration.

What this is
------------
For each trading day in the replay window we compute the market regime using
the *same* scoring model as the live morning brief, look up the three deployed
screens that regime would have selected, and keep the signals those screens
would have produced across a broad universe. Each kept signal becomes one
journal-visible replay trade, entered at the next bar's open and exited with
the same conservative ATR rules used by the honest validation engine.

What this is **not**
-------------------
TradingView's screener only answers "now", so the live brief's ranking,
confluence scores, catalyst checks and final gate cannot be replayed. This is
a screen/template replay, not a reconstruction of the exact live picks. It is
labelled as simulated and must never be counted as forward evidence.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from backend.app.core.logging import get_logger
from backend.app.infrastructure.backtest.external_backtest import (
    BacktestConfig,
    ExternalBacktestEngine,
)
from backend.app.infrastructure.backtest.replay_data import (
    fetch_history,
    fetch_regime_frames,
    filter_usable,
    load_universe,
)
from backend.app.infrastructure.market.regime import (
    MACRO_SYMBOLS,
    SECTOR_SYMBOLS,
    compute_regime_from_frames,
)
from backend.app.infrastructure.screener.configs import ScreenConfig, load_screen_template

log = get_logger("conflu.backtest.replay")

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_REGIME_CONFIG = REPO_ROOT / "config" / "regime_screens.yaml"

REGIME_KEYS = ("strong_trend", "neutral", "choppy", "ranging", "high_vol")
TOP_N = 3

# Mirrors morning_brief._REGIME_LABEL_MAP (asserted in tests to prevent drift).
LABEL_TO_REGIME: dict[str, str] = {
    "Exuberance": "strong_trend",
    "Risk-On": "strong_trend",
    "Neutral": "neutral",
    "Cautious": "choppy",
    "Risk-Off": "high_vol",
    "Crisis": "high_vol",
}

REPLAY_CAVEATS = [
    "TradingView's screener cannot be rewound: screen ranking, confluence scores, "
    "catalyst checks and the live gate are not replayed.",
    "Signals are evaluated on locally cached OHLCV for a current S&P 500 snapshot "
    "(survivorship bias remains).",
    "Entries are next-bar opens; exits are ATR stop/target (2.0/3.0) with a "
    "15-bar cap; stop wins on same-bar ties; fees 10 bps + slippage 5 bps/side.",
    "Fundamental / RS-rank filters that need live data are recorded as not applied "
    "and treated as not matched (same honesty rule as the validation engine).",
    "This is simulated replay evidence, not forward paper-trade evidence and not a "
    "P&L promise.",
]


@dataclass(frozen=True)
class ReplayParams:
    """Knobs for a replay run (defaults match the validation engine)."""

    window_days: int = 60
    daily_lookback_days: int = 760
    hourly_lookback_days: int = 200
    stop_atr_mult: float = 2.0
    target_atr_mult: float = 3.0
    max_hold_bars: int = 15
    fees_bps: float = 10.0
    slippage_bps: float = 5.0
    risk_pct: float = 1.0
    account_value: float = 100_000.0
    max_per_day: int = 0


@dataclass
class ReplayResult:
    """Persistable replay output."""

    run: dict[str, Any]
    rows: list[dict[str, Any]]
    summary: dict[str, Any]


# ── Screen mix ──────────────────────────────────────────────────────────────


def load_screen_mix(
    path: str | Path | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Load the deployed regime → screen mix.

    Mirrors ``RegimeScreenSelector._select_from_config`` (top-3 primaries, the
    weakest primary slot replaced by the top defensive, then backfill on load
    failures) but keeps the YAML stem + weight, which is what the journal
    needs to display.
    """
    config_path = Path(path or DEFAULT_REGIME_CONFIG)
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    regimes = raw.get("regimes") or {}
    mix: dict[str, list[dict[str, Any]]] = {}

    for regime in REGIME_KEYS:
        entries = []
        for entry in regimes.get(regime) or []:
            name = str(entry.get("name") or "").strip()
            if not name:
                continue
            entries.append(
                {
                    "name": name,
                    "weight": float(entry.get("weight") or 0.0),
                    "role": str(entry.get("role") or ""),
                }
            )
        if not entries:
            continue
        ordered = sorted(entries, key=lambda item: item["weight"], reverse=True)
        primaries = [item for item in ordered if item["role"] != "defensive"]
        defensives = [item for item in ordered if item["role"] == "defensive"]

        picked = [item["name"] for item in primaries[:TOP_N]]
        if defensives:
            top_defensive = defensives[0]["name"]
            if top_defensive not in picked:
                if len(picked) >= TOP_N:
                    picked[-1] = top_defensive
                else:
                    picked.append(top_defensive)

        by_name = {item["name"]: item for item in ordered}
        loaded: list[dict[str, Any]] = []

        def _add(name: str) -> None:
            try:
                screen = load_screen_template(name)
            except Exception as exc:  # noqa: BLE001 - broken template is skipped loudly
                log.warning("replay.screen_load_failed", screen=name, error=str(exc))
                return
            meta = by_name.get(name, {"weight": 0.0, "role": ""})
            loaded.append(
                {
                    "stem": name,
                    "config": screen,
                    "weight": float(meta.get("weight") or 0.0),
                    "role": str(meta.get("role") or ""),
                    "rank": len(loaded) + 1,
                }
            )

        for name in picked:
            _add(name)

        if len(loaded) < TOP_N:
            picked_set = set(picked)
            for item in ordered:
                if len(loaded) >= TOP_N:
                    break
                if item["name"] in picked_set:
                    continue
                _add(item["name"])

        mix[regime] = loaded

    return mix


# ── Regime as-of ────────────────────────────────────────────────────────────


def _breadth_at(
    sector_frames: dict[str, pd.DataFrame], as_of: pd.Timestamp
) -> dict[str, int]:
    """Replicate the live 5-day sector-breadth snapshot as of a past day."""
    positive = 0
    total = 0
    for symbol in SECTOR_SYMBOLS:
        frame = sector_frames.get(symbol)
        if frame is None or frame.empty:
            continue
        window = frame.loc[:as_of].tail(5)
        if len(window) < 2:
            continue
        first = float(window["Close"].iloc[0])
        last = float(window["Close"].iloc[-1])
        if first <= 0:
            continue
        if last > first:
            positive += 1
        total += 1
    return {"positive": positive, "total": total}


def historical_regime_map(
    macro_frames: dict[str, pd.DataFrame],
    sector_frames: dict[str, pd.DataFrame],
    dates: pd.DatetimeIndex | list[pd.Timestamp],
) -> dict[str, dict[str, Any]]:
    """Compute the regime label for each date using data through that close.

    The live morning brief runs pre-market and acts on the next open; here the
    signal is evaluated at date *T*'s close and entered at *T+1*'s open, so
    using *T*'s close for the regime keeps the information set aligned.
    """
    result: dict[str, dict[str, Any]] = {}
    last: dict[str, Any] | None = None

    for raw_ts in dates:
        ts = pd.Timestamp(raw_ts)
        macro_slice: dict[str, pd.DataFrame] = {}
        for symbol in MACRO_SYMBOLS:
            frame = macro_frames.get(symbol)
            if frame is None or frame.empty:
                continue
            window = frame.loc[:ts].tail(21)
            if len(window) >= 2:
                macro_slice[symbol] = window

        breadth = _breadth_at(sector_frames, ts)
        response = compute_regime_from_frames(
            macro_slice,
            breadth,
            now=datetime(ts.year, ts.month, ts.day, 20, 0, tzinfo=UTC),
        )
        key = ts.date().isoformat()
        if response is None:
            if last is not None:
                result[key] = dict(last, date=key)
            continue
        record = {
            "date": key,
            "label": response.regime_label,
            "key": LABEL_TO_REGIME.get(response.regime_label, "neutral"),
            "composite": response.composite_score,
        }
        result[key] = record
        last = record

    return result


# ── Helpers ─────────────────────────────────────────────────────────────────


def _signal_date(trade: dict[str, Any], daily_index: pd.Index) -> str:
    """Signal bar date (fallback for legacy trade rows without the field)."""
    explicit = trade.get("signal_date")
    if explicit:
        return str(explicit)[:10]
    entry = pd.Timestamp(trade["entry_date"])
    prior = daily_index[daily_index < entry]
    if len(prior) == 0:
        return ""
    return pd.Timestamp(prior[-1]).date().isoformat()


def _rvol(daily: pd.DataFrame, signal_date: str) -> float | None:
    """Volume on the signal bar / mean volume of the prior 20 bars."""
    try:
        ts = pd.Timestamp(signal_date)
        if ts not in daily.index:
            return None
        idx = daily.index.get_loc(ts)
        if not isinstance(idx, int) or idx < 20:
            return None
        vol = float(daily["Volume"].iloc[idx])
        avg = float(daily["Volume"].iloc[idx - 20 : idx].mean())
        if not pd.notna(vol) or not pd.notna(avg) or avg <= 0:
            return None
        return float(vol / avg)
    except Exception:  # noqa: BLE001 - rvol is a display/ranking nicety only
        return None


def _candidate_to_row(
    candidate: dict[str, Any],
    params: ReplayParams,
) -> dict[str, Any] | None:
    trade = candidate["trade"]
    entry = float(trade["entry_price"])
    stop = float(trade["stop_price"])
    target = float(trade["target_price"])
    exit_price = float(trade["exit_price"])
    direction = 1 if trade.get("direction", "long") == "long" else -1
    risk_per_share = abs(entry - stop)
    if risk_per_share <= 0:
        return None

    risk_usd = params.account_value * params.risk_pct / 100.0
    shares = risk_usd / risk_per_share
    slip = params.slippage_bps / 10_000.0
    fees_rate = params.fees_bps / 10_000.0
    entry_fill = entry * (1 + direction * slip)
    exit_fill = exit_price * (1 - direction * slip)
    gross = direction * shares * (exit_fill - entry_fill)
    fees = (shares * entry_fill + shares * exit_fill) * fees_rate
    pnl_usd = gross - fees
    position_size_pct = (
        shares * entry_fill / params.account_value * 100.0
        if params.account_value > 0
        else None
    )

    also = candidate.get("also_signaled_by") or ""
    notes = (
        "SIMULATED REPLAY (not forward evidence) · "
        f"screen rank {candidate['screen_rank']}/{candidate['screen_total']} "
        f"(weight {candidate['screen_weight']:.0f}) · "
        f"ATR stop {params.stop_atr_mult:g} / target {params.target_atr_mult:g} · "
        f"max {params.max_hold_bars} bars"
    )
    if also:
        notes += f" · also signalled by: {also}"

    return {
        "signal_date": candidate["signal_date"],
        "date_entered": str(trade["entry_date"])[:10],
        "symbol": candidate["symbol"],
        "template": candidate["template"],
        "regime": candidate["regime"],
        "regime_key": candidate["regime_key"],
        "screen_rank": candidate["screen_rank"],
        "screen_weight": candidate["screen_weight"],
        "direction": trade.get("direction", "long"),
        "entry_price": entry,
        "stop_loss": stop,
        "target_1": target,
        "exit_date": str(trade["exit_date"])[:10],
        "exit_price": exit_price,
        "exit_reason": trade.get("exit_reason"),
        "realized_r": float(trade.get("r_multiple") or 0.0),
        "pnl_usd": float(pnl_usd),
        "risk_pct": params.risk_pct,
        "position_size_pct": position_size_pct,
        "shares": float(shares),
        "account_value": params.account_value,
        "hold_bars": int(trade.get("hold_bars") or 0),
        "rvol": candidate.get("rvol"),
        "also_signaled_by": also or None,
        "notes": notes,
    }


def _group_summary(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(key) or "—")].append(row)
    return {name: _basic_summary(items) for name, items in sorted(grouped.items())}


def _basic_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    if n == 0:
        return {
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "expectancy_r": 0.0,
            "avg_win_r": 0.0,
            "avg_loss_r": 0.0,
            "profit_factor_r": None,
            "pnl_usd": 0.0,
            "avg_hold_bars": 0.0,
        }
    wins = [row for row in rows if float(row["pnl_usd"]) > 0]
    losses = [row for row in rows if float(row["pnl_usd"]) <= 0]
    rs = [float(row["realized_r"]) for row in rows]
    wins_r = [r for r in rs if r > 0]
    losses_r = [r for r in rs if r < 0]
    gross_win_r = sum(wins_r)
    gross_loss_r = abs(sum(losses_r))
    return {
        "trades": n,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": len(wins) / n,
        "expectancy_r": sum(rs) / n,
        "avg_win_r": (sum(wins_r) / len(wins_r)) if wins_r else 0.0,
        "avg_loss_r": (sum(losses_r) / len(losses_r)) if losses_r else 0.0,
        "profit_factor_r": (gross_win_r / gross_loss_r) if gross_loss_r > 0 else None,
        "pnl_usd": sum(float(row["pnl_usd"]) for row in rows),
        "avg_hold_bars": sum(int(row["hold_bars"]) for row in rows) / n,
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Overall + per-template + per-regime replay statistics."""
    base = _basic_summary(rows)
    base["templates"] = _group_summary(rows, "template")
    base["regimes"] = _group_summary(rows, "regime")
    base["exit_reasons"] = dict(Counter(str(row.get("exit_reason") or "—") for row in rows))
    base["total_r"] = sum(float(row["realized_r"]) for row in rows)
    return base


# ── Core run ────────────────────────────────────────────────────────────────


async def run_replay(
    params: ReplayParams | None = None,
    *,
    symbols: list[str] | None = None,
    universe_file: str | Path | None = None,
    cache_dir: str | Path | None = None,
    refresh_data: bool = False,
    templates_filter: list[str] | None = None,
    progress: bool = True,
    now: datetime | None = None,
    daily: dict[str, pd.DataFrame] | None = None,
    hourly: dict[str, pd.DataFrame] | None = None,
    regime_frames: dict[str, pd.DataFrame] | None = None,
    screen_mix: dict[str, list[dict[str, Any]]] | None = None,
    suppress_engine_logs: bool = True,
) -> ReplayResult:
    """Run the historical replay and return rows + summaries.

    Data/regime/screen inputs are injectable so the orchestration can be
    tested without network access.
    """
    params = params or ReplayParams()
    now = now or datetime.now(UTC)
    today = now.date()

    if symbols is None:
        symbols = sorted(daily) if daily is not None else load_universe(universe_file)

    daily_start = (today - timedelta(days=params.daily_lookback_days)).isoformat()
    hourly_start = (today - timedelta(days=params.hourly_lookback_days)).isoformat()
    end_date = today.isoformat()

    missing_daily: list[str] = []
    missing_hourly: list[str] = []
    dropped: dict[str, str] = {}

    if daily is None or hourly is None:
        if progress:
            print(f"Fetching daily OHLCV for {len(symbols)} symbols...")
        raw_daily, missing_daily = fetch_history(
            symbols,
            start=daily_start,
            end=end_date,
            interval="1d",
            cache_dir=cache_dir,
            refresh=refresh_data,
            progress=progress,
        )
        if progress:
            print(f"Fetching hourly OHLCV for {len(symbols)} symbols...")
        raw_hourly, missing_hourly = fetch_history(
            symbols,
            start=hourly_start,
            end=end_date,
            interval="1h",
            cache_dir=cache_dir,
            refresh=refresh_data,
            progress=progress,
        )
        daily, hourly, dropped = filter_usable(raw_daily, raw_hourly)
    else:
        daily, hourly, dropped = filter_usable(daily, hourly)

    if regime_frames is None:
        if progress:
            print("Fetching macro + sector regime frames...")
        regime_frames = fetch_regime_frames(
            start=daily_start,
            end=end_date,
            cache_dir=cache_dir,
            refresh=refresh_data,
        )

    spy = regime_frames.get("SPY")
    if spy is None or spy.empty:
        raise RuntimeError("Regime frames are missing SPY; cannot build a trading calendar.")

    end_ts = pd.Timestamp(spy.index[-1])
    window_start_ts = end_ts - pd.Timedelta(days=params.window_days)
    signal_dates = [ts for ts in spy.index if window_start_ts <= ts <= end_ts]

    macro_frames = {sym: regime_frames[sym] for sym in MACRO_SYMBOLS if sym in regime_frames}
    sector_frames = {sym: regime_frames[sym] for sym in SECTOR_SYMBOLS if sym in regime_frames}
    regime_by_date = historical_regime_map(macro_frames, sector_frames, signal_dates)

    if progress:
        counts = Counter(record["key"] for record in regime_by_date.values())
        print(f"Regime days: {dict(counts)}")

    mix = screen_mix or load_screen_mix()
    if templates_filter:
        allowed = {name.strip() for name in templates_filter if name.strip()}
        mix = {
            regime: [item for item in items if item["stem"] in allowed]
            for regime, items in mix.items()
        }
    screen_lookup = {
        regime: {item["stem"]: item for item in items} for regime, items in mix.items()
    }

    # One engine run per (unique template, symbol); signals are deduped later.
    templates: dict[str, ScreenConfig] = {}
    for items in mix.values():
        for item in items:
            templates.setdefault(item["stem"], item["config"])

    if progress:
        print(f"Running {len(templates)} deployed templates across {len(daily)} symbols...")

    prefetched: dict[tuple[str, str], pd.DataFrame] = {}
    for symbol, frame in daily.items():
        prefetched[(symbol, "1D")] = frame
    for symbol, frame in hourly.items():
        prefetched[(symbol, "1h")] = frame
    engine = ExternalBacktestEngine(fetcher=_PrefetchedFetcher(prefetched))
    if suppress_engine_logs:
        # ~7k engine runs would otherwise emit ~21k INFO lines. Replay progress
        # is printed explicitly below; real failures still surface in results.
        engine._log = _QuietLogger()  # type: ignore[attr-defined]

    candidates: list[dict[str, Any]] = []
    raw_signal_count = 0
    excluded: dict[str, dict[str, Any]] = {}
    skipped_by_template: dict[str, Counter[str]] = {stem: Counter() for stem in templates}

    for template_index, (stem, screen) in enumerate(sorted(templates.items()), start=1):
        template_trades = 0
        for symbol, frame in daily.items():
            config = BacktestConfig(
                symbol=symbol,
                timeframe="1D",
                start_date=daily_start,
                end_date=end_date,
                signal_filters=list(screen.filters),
                direction=getattr(screen, "direction", "long"),
                stop_atr_mult=params.stop_atr_mult,
                target_atr_mult=params.target_atr_mult,
                max_hold_bars=params.max_hold_bars,
                fees_bps=params.fees_bps,
                slippage_bps=params.slippage_bps,
            )
            result = await engine.run_backtest(config)
            skipped_by_template[stem].update(result.skipped_filters)
            if result.error:
                excluded[f"{stem}/{symbol}"] = {
                    "error": result.error,
                    "skipped": result.skipped_filters,
                }
                continue

            for trade in result.trades:
                raw_signal_count += 1
                signal_date = _signal_date(trade, frame.index)
                if signal_date not in regime_by_date:
                    continue
                regime = regime_by_date[signal_date]
                selected = screen_lookup.get(regime["key"]) or {}
                selection = selected.get(stem)
                if selection is None:
                    continue
                template_trades += 1
                candidates.append(
                    {
                        "signal_date": signal_date,
                        "symbol": symbol,
                        "template": stem,
                        "regime": regime["label"],
                        "regime_key": regime["key"],
                        "screen_rank": selection["rank"],
                        "screen_total": len(mix.get(regime["key"]) or []),
                        "screen_weight": selection["weight"],
                        "trade": trade,
                        "rvol": _rvol(frame, signal_date),
                        "also_signaled_by": "",
                    }
                )
        if progress:
            print(
                f"  [{template_index}/{len(templates)}] {stem:38} "
                f"signals={template_trades}"
            )

    # Dedupe: one entry per symbol/signal day, highest-priority screen wins.
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        grouped[(candidate["signal_date"], candidate["symbol"])].append(candidate)

    deduped: list[dict[str, Any]] = []
    for group in grouped.values():
        group.sort(key=lambda item: (item["screen_rank"], item["template"]))
        keep = group[0]
        others = sorted({item["template"] for item in group[1:]})
        keep["also_signaled_by"] = ", ".join(others)
        deduped.append(keep)

    deduped_count = len(deduped)

    if params.max_per_day and params.max_per_day > 0:
        by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for candidate in deduped:
            by_day[candidate["signal_date"]].append(candidate)
        capped: list[dict[str, Any]] = []
        for items in by_day.values():
            items.sort(key=lambda item: (item.get("rvol") or 0.0), reverse=True)
            capped.extend(items[: params.max_per_day])
        deduped = capped

    rows: list[dict[str, Any]] = []
    for candidate in deduped:
        row = _candidate_to_row(candidate, params)
        if row is not None:
            rows.append(row)
    rows.sort(key=lambda row: (row["date_entered"], row["symbol"]), reverse=True)

    summary = summarize(rows)
    regime_days = Counter(record["key"] for record in regime_by_date.values())
    run = {
        "generated_at": now.isoformat(),
        "window_start": window_start_ts.date().isoformat(),
        "window_end": end_ts.date().isoformat(),
        "universe_count": len(daily),
        "universe_requested": len(symbols),
        "templates_count": len(templates),
        "params": asdict(params),
        "summary": summary,
        "metadata": {
            "engine": "external_backtest v2 (validation reset 2026-10-19)",
            "source": "local OHLCV replay of deployed screen templates",
            "templates": sorted(templates),
            "screens": {
                regime: [
                    {
                        "name": item["stem"],
                        "display_name": item["config"].name,
                        "weight": item["weight"],
                        "rank": item["rank"],
                        "role": item["role"],
                    }
                    for item in items
                ]
                for regime, items in mix.items()
            },
            "regime_days": dict(regime_days),
            "data_quality": {
                "requested": len(symbols),
                "usable_daily": len(daily),
                "usable_hourly": len(hourly),
                "missing_daily": missing_daily,
                "missing_hourly": missing_hourly,
                "dropped": dropped,
                "excluded": excluded,
            },
            "counts": {
                "raw_signals": raw_signal_count,
                "after_regime_gate": len(candidates),
                "after_dedupe": deduped_count,
                "after_day_cap": len(deduped),
                "rows": len(rows),
            },
            "not_applied_filters": {
                stem: dict(counter)
                for stem, counter in skipped_by_template.items()
                if counter
            },
            "caveats": REPLAY_CAVEATS,
        },
    }

    return ReplayResult(run=run, rows=rows, summary=summary)


class _PrefetchedFetcher:
    """Serve pre-fetched frames to the engine (same contract as the validation runner)."""

    def __init__(self, data: dict[tuple[str, str], pd.DataFrame]):
        self.data = data
        self.misses: Counter[tuple[str, str]] = Counter()

    async def fetch_yahoo(self, symbol: str, timeframe: str, start: str, end: str):  # noqa: ARG002
        frame = self.data.get((symbol, timeframe))
        if frame is None:
            self.misses[(symbol, timeframe)] += 1
        return frame


class _QuietLogger:
    """No-op structlog stand-in for the per-symbol engine chatter."""

    def _noop(self, *args: Any, **kwargs: Any) -> None:
        return None

    debug = info = warning = error = exception = _noop
