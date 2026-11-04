"""Replay engine + ledger tests (D-71).

Covers: regime-label map drift guard, deployed screen-mix parity with the live
selector, as-of regime slicing (no look-ahead), the replay orchestrator
(regime gate, dedupe, day cap, P&L math) and the separate replay store.

Network is never touched: OHLCV, regime frames and the screen mix are injected.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import numpy as np
import pandas as pd
import pytest

from backend.app.domain.workflow import replay_store
from backend.app.infrastructure.backtest import replay as replay_mod
from backend.app.infrastructure.backtest.replay import (
    LABEL_TO_REGIME,
    REGIME_KEYS,
    ReplayParams,
    historical_regime_map,
    load_screen_mix,
    run_replay,
)
from backend.app.infrastructure.market.regime import (
    MACRO_SYMBOLS,
    SECTOR_SYMBOLS,
    compute_regime_from_frames,
)
from backend.app.infrastructure.professional.morning_brief import _REGIME_LABEL_MAP
from backend.app.infrastructure.professional.regime_selector import RegimeScreenSelector
from backend.app.infrastructure.screener.configs import FilterRule, ScreenConfig

_NOW = datetime(2026, 10, 19, 16, 0, tzinfo=UTC)


# ── Fixtures / helpers ──────────────────────────────────────────────────────


def _frame(closes: np.ndarray | list[float], end: str = "2026-10-16") -> pd.DataFrame:
    idx = pd.bdate_range(end=end, periods=len(closes))
    close = pd.Series(closes, index=idx, dtype=float)
    prev = close.shift(1).fillna(close.iloc[0])
    return pd.DataFrame(
        {
            "Open": prev,
            "High": np.maximum(prev, close) + 0.7,
            "Low": np.minimum(prev, close) - 0.7,
            "Close": close,
            "Volume": 1_000_000.0,
        },
        index=idx,
    )


def _breakout_frame() -> pd.DataFrame:
    """260 bars: flat ~90, then a sustained step above the 100 filter."""
    closes = np.full(260, 90.0)
    closes[-25:] = 104.0 + np.sin(np.arange(25)) * 1.5
    return _frame(closes)


def _screen() -> ScreenConfig:
    return ScreenConfig(
        name="Test Close Above",
        filters=[
            FilterRule(
                category="momentum",
                indicator="close_above",
                params={"threshold": 100.0},
                operator="gt",
            )
        ],
        timeframes=["1D"],
        direction="long",
    )


def _mix(screen: ScreenConfig) -> dict[str, list[dict]]:
    def item(stem: str, weight: float, rank: int) -> dict:
        return {"stem": stem, "config": screen, "weight": weight, "role": "", "rank": rank}

    return {
        "strong_trend": [item("test-a", 95.0, 1), item("test-b", 90.0, 2)],
        "choppy": [item("choppy-only", 95.0, 1)],
    }


def _flat_regime_frames(index: pd.DatetimeIndex) -> dict[str, pd.DataFrame]:
    """Only SPY is needed when historical_regime_map is patched."""
    spy = pd.DataFrame(
        {
            "Open": 100.0,
            "High": 101.0,
            "Low": 99.0,
            "Close": 100.0,
            "Volume": 1_000_000.0,
        },
        index=index,
    )
    return {"SPY": spy}


def _patch_regime(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_map(macro, sector, dates):  # noqa: ARG001
        return {
            pd.Timestamp(d).date().isoformat(): {
                "date": pd.Timestamp(d).date().isoformat(),
                "label": "Risk-On",
                "key": "strong_trend",
                "composite": 82.0,
            }
            for d in dates
        }

    monkeypatch.setattr(replay_mod, "historical_regime_map", fake_map)


async def _run(
    *,
    symbols: list[str] | None = None,
    daily: dict[str, pd.DataFrame] | None = None,
    hourly: dict[str, pd.DataFrame] | None = None,
    regime_frames: dict[str, pd.DataFrame] | None = None,
    screen_mix: dict[str, list[dict]] | None = None,
    params: ReplayParams | None = None,
):
    return await run_replay(
        params or ReplayParams(window_days=60),
        symbols=symbols or ["AAA", "BBB"],
        daily=daily,
        hourly=hourly if hourly is not None else {},
        regime_frames=regime_frames,
        screen_mix=screen_mix,
        progress=False,
        now=_NOW,
    )


# ── Mapping / config parity ─────────────────────────────────────────────────


def test_label_map_matches_morning_brief() -> None:
    assert LABEL_TO_REGIME == _REGIME_LABEL_MAP


def test_screen_mix_matches_live_selector() -> None:
    mix = load_screen_mix()
    selector = RegimeScreenSelector()
    for regime in REGIME_KEYS:
        expected = [screen.name for screen in selector.select_top_screens(regime)]
        actual = [item["config"].name for item in mix.get(regime, [])]
        assert actual == expected, regime
        assert [item["rank"] for item in mix[regime]] == list(
            range(1, len(mix[regime]) + 1)
        )
        assert all(item["weight"] > 0 for item in mix[regime])


# ── Regime as-of ────────────────────────────────────────────────────────────


def test_compute_regime_from_frames_handles_missing_data() -> None:
    response = compute_regime_from_frames({}, {"positive": 0, "total": 0})
    assert response is not None
    assert response.regime_label in LABEL_TO_REGIME


def test_historical_regime_map_does_not_look_ahead() -> None:
    idx = pd.bdate_range(end="2026-10-16", periods=80)
    cutoff = idx[50]

    def series(values: np.ndarray) -> pd.DataFrame:
        close = pd.Series(values, index=idx, dtype=float)
        return pd.DataFrame(
            {
                "Open": close,
                "High": close + 0.2,
                "Low": close - 0.2,
                "Close": close,
                "Volume": 1_000_000.0,
            }
        )

    n = len(idx)
    spy = np.linspace(100, 130, n)
    spy[51:] = spy[50] * 0.6  # crash only after the cutoff
    frames = {
        "^VIX": series(np.full(n, 20.0)),
        "SPY": series(spy),
        "TLT": series(np.linspace(95, 90, n)),
        "GLD": series(np.full(n, 180.0)),
        "SHY": series(np.full(n, 82.0)),
    }
    for i, symbol in enumerate(SECTOR_SYMBOLS):
        up = i % 2 == 0
        frames[symbol] = series(np.linspace(100, 110 if up else 90, n))

    macro = {sym: frames[sym] for sym in MACRO_SYMBOLS if sym in frames}
    sectors = {sym: frames[sym] for sym in SECTOR_SYMBOLS}
    truncated_macro = {sym: frame.loc[:cutoff] for sym, frame in macro.items()}
    truncated_sectors = {sym: frame.loc[:cutoff] for sym, frame in sectors.items()}

    full = historical_regime_map(macro, sectors, [cutoff])[cutoff.date().isoformat()]
    sliced = historical_regime_map(
        truncated_macro, truncated_sectors, [cutoff]
    )[cutoff.date().isoformat()]

    assert full == sliced
    assert full["label"] in LABEL_TO_REGIME


# ── Orchestration ───────────────────────────────────────────────────────────


def test_run_replay_regime_gate_dedupe_and_pnl(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_regime(monkeypatch)
    screen = _screen()
    daily = {"AAA": _breakout_frame(), "BBB": _breakout_frame()}
    daily["AAA"].loc[daily["AAA"].index[-25:], "Volume"] = 2_000_000.0
    daily["BBB"].loc[daily["BBB"].index[-25:], "Volume"] = 1_200_000.0
    spy = _flat_regime_frames(daily["AAA"].index)

    result = asyncio.run(
        _run(
            daily=daily,
            regime_frames=spy,
            screen_mix=_mix(screen),
        )
    )

    counts = result.run["metadata"]["counts"]
    assert counts["after_regime_gate"] > 0
    assert counts["after_regime_gate"] == counts["after_dedupe"] * 2  # a + b
    assert counts["rows"] == counts["after_dedupe"]
    assert result.rows

    for row in result.rows:
        assert row["template"] == "test-a"  # highest-priority screen wins
        assert row["also_signaled_by"] == "test-b"
        assert row["regime"] == "Risk-On"
        assert row["regime_key"] == "strong_trend"
        assert row["direction"] == "long"

        # Entry is the next bar's open after the signal bar.
        idx = daily["AAA"].index
        signal_pos = idx.get_loc(pd.Timestamp(row["signal_date"]))
        assert row["date_entered"] == idx[signal_pos + 1].date().isoformat()

        # $ P&L is rebuilt from fills with 1% risk, 10 bps fees, 5 bps slippage.
        risk_usd = 100_000.0 * 0.01
        shares = risk_usd / abs(row["entry_price"] - row["stop_loss"])
        entry_fill = row["entry_price"] * 1.0005
        exit_fill = row["exit_price"] * 0.9995
        expected = shares * (exit_fill - entry_fill) - (
            shares * entry_fill + shares * exit_fill
        ) * 0.001
        assert row["pnl_usd"] == pytest.approx(expected, abs=1e-6)

    # The choppy-only screen never gets a strong_trend day.
    assert all(row["template"] != "choppy-only" for row in result.rows)
    assert "choppy-only" in result.run["metadata"]["templates"]


def test_run_replay_day_cap_keeps_highest_rvol(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_regime(monkeypatch)
    screen = _screen()
    daily = {"AAA": _breakout_frame(), "BBB": _breakout_frame()}
    daily["AAA"].loc[daily["AAA"].index[-25:], "Volume"] = 2_000_000.0
    daily["BBB"].loc[daily["BBB"].index[-25:], "Volume"] = 1_200_000.0
    spy = _flat_regime_frames(daily["AAA"].index)

    result = asyncio.run(
        _run(
            daily=daily,
            regime_frames=spy,
            screen_mix=_mix(screen),
            params=ReplayParams(window_days=60, max_per_day=1),
        )
    )

    assert result.rows
    signal_dates = [row["signal_date"] for row in result.rows]
    assert len(signal_dates) == len(set(signal_dates))
    assert all(row["symbol"] == "AAA" for row in result.rows)  # higher RVOL wins


# ── Store + API ─────────────────────────────────────────────────────────────


def _run_payload() -> dict:
    return {
        "generated_at": "2026-10-19T20:00:00+00:00",
        "window_start": "2026-08-20",
        "window_end": "2026-10-19",
        "universe_count": 503,
        "templates_count": 14,
        "params": {"window_days": 60},
        "summary": {"trades": 2, "wins": 1},
        "metadata": {"counts": {"rows": 2}},
    }


def _trade_row(symbol: str = "TEST", pnl: float = 1900.0) -> dict:
    return {
        "signal_date": "2026-09-25",
        "date_entered": "2026-09-26",
        "symbol": symbol,
        "template": "bull-flag-continuation",
        "regime": "Cautious",
        "regime_key": "choppy",
        "screen_rank": 1,
        "screen_weight": 85.0,
        "direction": "long",
        "entry_price": 100.0,
        "stop_loss": 95.0,
        "target_1": 110.0,
        "exit_date": "2026-10-01",
        "exit_price": 110.0,
        "exit_reason": "target",
        "realized_r": 2.0,
        "pnl_usd": pnl,
        "risk_pct": 1.0,
        "position_size_pct": 5.0,
        "shares": 50.0,
        "account_value": 100_000.0,
        "hold_bars": 3,
        "rvol": 1.2,
        "also_signaled_by": None,
        "notes": "test",
    }


def test_replay_store_replace_read_clear() -> None:
    run_id = replay_store.replace_run(_run_payload(), [_trade_row("AAA"), _trade_row("BBB")])
    payload = replay_store.latest_run()
    assert payload is not None
    assert payload["run"]["id"] == run_id
    assert payload["run"]["window_start"] == "2026-08-20"
    assert payload["summary"]["trades"] == 2
    assert len(payload["rows"]) == 2
    assert payload["rows"][0]["exit_price"] == 110.0

    replay_store.replace_run(_run_payload(), [_trade_row("CCC")])
    payload = replay_store.latest_run()
    assert len(payload["rows"]) == 1
    assert payload["rows"][0]["symbol"] == "CCC"

    assert replay_store.clear() == 1
    assert replay_store.latest_run() is None


def test_replay_endpoints_round_trip() -> None:
    from backend.app.api.routers import workflow as wf

    empty = asyncio.run(wf.get_replay())
    assert empty.data == {"run": None, "rows": [], "summary": None}

    replay_store.replace_run(_run_payload(), [_trade_row()])
    resp = asyncio.run(wf.get_replay())
    assert resp.data["run"]["window_start"] == "2026-08-20"
    assert len(resp.data["rows"]) == 1

    deleted = asyncio.run(wf.delete_replay())
    assert deleted.data["removed"] == 1
    assert asyncio.run(wf.get_replay()).data["run"] is None
