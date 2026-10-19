"""Tests for ExternalBacktestEngine — validation-reset semantics (2026-10-19).

Covers: next-open entries (no look-ahead), ATR stop/target exits with
conservative same-bar stop priority, time-cap exits, R-multiple math,
direction-aware simulation, honest skip recording (unknown indicators,
fundamental rules), legacy signal_params compatibility, and per-rule
4h view alignment.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from backend.app.infrastructure.backtest.external_backtest import (
    _SIMPLE_FILTER_RULES,
    BacktestConfig,
    ExternalBacktestEngine,
    _EvalRule,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _frame(closes, highs=None, lows=None, opens=None, start="2024-01-01"):
    idx = pd.bdate_range(start, periods=len(closes))
    closes = pd.Series(closes, index=idx, dtype=float)
    highs = pd.Series(highs, index=idx, dtype=float) if highs is not None else closes + 0.5
    lows = pd.Series(lows, index=idx, dtype=float) if lows is not None else closes - 0.5
    opens = pd.Series(opens, index=idx, dtype=float) if opens is not None else closes.copy()
    return pd.DataFrame(
        {"Open": opens, "High": highs, "Low": lows, "Close": closes, "Volume": 1_000_000.0}
    )


def _size(series, index, signal_bar, units):
    size = pd.DataFrame({"size": 0.0}, index=index)
    size.iloc[signal_bar, 0] = units
    return size


class _FakeFetcher:
    def __init__(self, frames):
        self.frames = frames
        self.calls: list[tuple[str, str]] = []

    async def fetch_yahoo(self, symbol, timeframe, start, end):
        self.calls.append((symbol, timeframe))
        return self.frames.get((symbol, timeframe))


def _engine(fees_bps=0.0, slippage_bps=0.0):
    return ExternalBacktestEngine(fetcher=None, fees_bps=fees_bps, slippage_bps=slippage_bps)


# ---------------------------------------------------------------------------
# Simulation semantics (direct _run_simulation calls)
# ---------------------------------------------------------------------------


class TestSimulationSemantics:
    def test_signal_executes_at_next_open_and_time_exits(self):
        df = _frame([100.0] * 30)
        df["ATR"] = 1.0
        idx = df.index
        entries = pd.Series(False, index=idx)
        entries.iloc[10] = True
        size = _size(None, idx, 10, 100.0)

        config = BacktestConfig(
            symbol="TEST",
            start_date="2024-01-01",
            end_date="2024-02-15",
            fees_bps=0,
            slippage_bps=0,
            max_hold_bars=3,
        )
        result = _engine()._run_simulation(df, entries, size, config)

        assert len(result.trades) == 1
        trade = result.trades[0]
        assert trade["entry_date"] == str(idx[11].date())  # next bar, never the signal bar
        assert trade["entry_price"] == pytest.approx(100.0)
        assert trade["exit_reason"] == "time"
        assert trade["hold_bars"] == 3
        assert result.exit_reason_counts == {"time": 1}
        assert result.time_in_market_pct > 0

    def test_stop_wins_when_both_stop_and_target_touched_same_bar(self):
        highs = [100.5, 100.5, 104.0, 100.5, 100.5]
        lows = [99.5, 99.5, 97.0, 99.5, 99.5]
        closes = [100.0] * 5
        df = _frame(closes, highs=highs, lows=lows)
        df["ATR"] = 1.0
        idx = df.index
        entries = pd.Series(False, index=idx)
        entries.iloc[0] = True
        size = _size(None, idx, 0, 100.0)

        config = BacktestConfig(symbol="TEST", start_date="2024-01-01", end_date="2024-01-05", fees_bps=0, slippage_bps=0)
        result = _engine()._run_simulation(df, entries, size, config)

        trade = result.trades[0]
        assert trade["exit_reason"] == "stop"  # conservative same-bar priority
        assert trade["exit_price"] == pytest.approx(98.0)  # 100 - 2*ATR
        assert trade["r_multiple"] == pytest.approx(-1.0)
        assert trade["hold_bars"] == 1

    def test_target_hit_gives_planned_r_multiple(self):
        highs = [100.5, 100.5, 103.4, 100.5]
        lows = [99.5, 99.5, 99.9, 99.5]
        closes = [100.0] * 4
        df = _frame(closes, highs=highs, lows=lows)
        df["ATR"] = 1.0
        idx = df.index
        entries = pd.Series(False, index=idx)
        entries.iloc[0] = True
        size = _size(None, idx, 0, 100.0)

        config = BacktestConfig(symbol="TEST", start_date="2024-01-01", end_date="2024-01-04", fees_bps=0, slippage_bps=0)
        result = _engine()._run_simulation(df, entries, size, config)

        trade = result.trades[0]
        assert trade["exit_reason"] == "target"
        assert trade["exit_price"] == pytest.approx(103.0)  # 100 + 3*ATR
        assert trade["r_multiple"] == pytest.approx(1.5)  # 3 ATR target / 2 ATR stop

    def test_short_direction_target_and_stop(self):
        # Target hit: price falls to 96.5 (below target 97), stop 102 untouched.
        closes = [100.0, 100.0, 97.0, 97.0]
        highs = [100.5, 100.5, 100.2, 100.5]
        lows = [99.5, 99.5, 96.5, 96.5]
        df = _frame(closes, highs=highs, lows=lows)
        df["ATR"] = 1.0
        idx = df.index
        entries = pd.Series(False, index=idx)
        entries.iloc[0] = True
        size = _size(None, idx, 0, 100.0)

        config = BacktestConfig(
            symbol="TEST", start_date="2024-01-01", end_date="2024-01-04",
            fees_bps=0, slippage_bps=0, direction="short",
        )
        result = _engine()._run_simulation(df, entries, size, config)

        trade = result.trades[0]
        assert trade["exit_reason"] == "target"
        assert trade["exit_price"] == pytest.approx(97.0)
        assert trade["r_multiple"] == pytest.approx(1.5)
        assert result.final_equity > config.initial_cash  # falling price profits a short

    def test_short_stop_is_above_entry(self):
        closes = [100.0, 100.0, 100.0, 100.0]
        highs = [100.5, 100.5, 102.5, 100.5]
        lows = [99.5, 99.5, 99.5, 99.5]
        df = _frame(closes, highs=highs, lows=lows)
        df["ATR"] = 1.0
        idx = df.index
        entries = pd.Series(False, index=idx)
        entries.iloc[0] = True
        size = _size(None, idx, 0, 100.0)

        config = BacktestConfig(
            symbol="TEST", start_date="2024-01-01", end_date="2024-01-04",
            fees_bps=0, slippage_bps=0, direction="short",
        )
        result = _engine()._run_simulation(df, entries, size, config)

        trade = result.trades[0]
        assert trade["exit_reason"] == "stop"
        assert trade["exit_price"] == pytest.approx(102.0)
        assert trade["r_multiple"] == pytest.approx(-1.0)

    def test_annualized_return_matches_cagr_formula(self):
        n = 20
        closes = [100.0] * n
        highs = [100.5] * n
        lows = [99.5] * n
        highs[2] = 103.2  # target hit on the bar after entry
        df = _frame(closes, highs=highs, lows=lows)
        df["ATR"] = 1.0
        idx = df.index
        entries = pd.Series(False, index=idx)
        entries.iloc[0] = True
        size = _size(None, idx, 0, 100.0)

        config = BacktestConfig(symbol="TEST", start_date="2024-01-01", end_date="2024-01-30", fees_bps=0, slippage_bps=0)
        result = _engine()._run_simulation(df, entries, size, config)

        expected_total = result.final_equity / config.initial_cash - 1.0
        expected_cagr = (1.0 + expected_total) ** (252.0 / n) - 1.0
        assert result.total_return == pytest.approx(expected_total)
        assert result.annualized_return == pytest.approx(expected_cagr, rel=1e-9)

    def test_r_stats_computed(self):
        df = _frame([100.0] * 6)
        df["ATR"] = 1.0
        idx = df.index
        entries = pd.Series(False, index=idx)
        entries.iloc[0] = True
        size = _size(None, idx, 0, 100.0)

        config = BacktestConfig(
            symbol="TEST", start_date="2024-01-01", end_date="2024-01-08",
            fees_bps=0, slippage_bps=0, target_atr_mult=2.0, stop_atr_mult=2.0, max_hold_bars=1,
        )
        df.loc[idx[2], "High"] = 105.0  # +2 ATR target = 102 -> 1R win
        result = _engine()._run_simulation(df, entries, size, config)

        assert result.expectancy_r == pytest.approx(1.0)
        assert result.avg_win_r == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Signal generation honesty + per-rule timeframes
# ---------------------------------------------------------------------------


class TestSignalGenerationHonesty:
    async def test_unknown_indicator_recorded_and_never_manufactures_entries(self):
        df = _frame([100.0] * 40)
        engine = ExternalBacktestEngine(fetcher=_FakeFetcher({("AAPL", "1D"): df}))
        config = BacktestConfig(
            symbol="AAPL",
            start_date="2024-01-01",
            end_date="2024-02-25",
            signal_filters=[_EvalRule(indicator="totally_unknown")],
        )
        result = await engine.run_backtest(config)

        assert result.error is None
        assert result.total_trades == 0
        assert any("totally_unknown" in s for s in result.skipped_filters)

    async def test_fundamental_rules_recorded_not_applied(self):
        df = _frame([100.0] * 40)
        engine = ExternalBacktestEngine(fetcher=_FakeFetcher({("AAPL", "1D"): df}))
        config = BacktestConfig(
            symbol="AAPL",
            start_date="2024-01-01",
            end_date="2024-02-25",
            signal_filters=[
                _EvalRule(indicator="market_cap_gt", params={"value": 500_000_000}),
                _EvalRule(indicator="close_above", params={"threshold": 3.0}),
            ],
        )
        result = await engine.run_backtest(config)

        assert result.error is None
        assert any(s.startswith("market_cap_gt") for s in result.skipped_filters)
        # close_above is locally evaluable (100 > 3 on every bar) -> at least one trade
        assert result.total_trades >= 1

    async def test_legacy_signal_params_still_work(self):
        pytest.importorskip("pandas_ta")
        closes = np.linspace(100.0, 140.0, 90)
        df = _frame(closes.tolist(), highs=(closes + 1).tolist(), lows=(closes - 1).tolist())
        engine = ExternalBacktestEngine(fetcher=_FakeFetcher({("AAPL", "1D"): df}))
        config = BacktestConfig(
            symbol="AAPL",
            start_date="2024-01-01",
            end_date="2024-12-31",
            signal_params={"price_above_ema": {"period": 20}},
        )
        result = await engine.run_backtest(config)

        assert result.error is None
        assert result.total_trades >= 1

    async def test_4h_rule_without_intraday_data_excludes_symbol(self):
        df = _frame([100.0] * 40)
        engine = ExternalBacktestEngine(fetcher=_FakeFetcher({("AAPL", "1D"): df}))
        config = BacktestConfig(
            symbol="AAPL",
            start_date="2024-01-01",
            end_date="2024-02-25",
            signal_filters=[_EvalRule(indicator="rsi_gt", params={"threshold": 50}, timeframe="4h")],
        )
        result = await engine.run_backtest(config)

        # Hard exclusion: cannot claim a result for an unevaluable rule set.
        assert result.error == "Signal generation failed"
        assert any("no intraday data available" in s for s in result.skipped_filters)

    async def test_intraday_view_aligns_to_daily_bars(self):
        days = pd.bdate_range("2024-01-01", periods=10)
        index = []
        rows = []
        for d in days:
            for hour in (10, 11, 12, 13, 14, 15, 16):
                index.append(d.replace(hour=hour))
                rows.append(
                    {"Open": 100.0, "High": 101.0, "Low": 99.0, "Close": 100.0 + hour / 10, "Volume": 1000.0}
                )
        intraday = pd.DataFrame(rows, index=pd.DatetimeIndex(index))
        engine = ExternalBacktestEngine(fetcher=_FakeFetcher({("AAPL", "1h"): intraday}))
        config = BacktestConfig(symbol="AAPL", start_date="2024-01-01", end_date="2024-02-01")

        view = await engine._build_intraday_view(config, "4h", days)

        assert view is not None
        assert view.index.equals(days)
        assert view["close"].notna().all()
        # last 4h bucket of the final day contains the 16:00 bar -> its close
        assert view["close"].iloc[-1] == pytest.approx(101.6)


# ---------------------------------------------------------------------------
# Coverage guard: every template indicator has an evaluator or is recorded
# ---------------------------------------------------------------------------


def test_all_template_indicators_have_evaluator_coverage():
    special = {
        "price_above_ema",
        "price_below_ema",
        "price_near_ema",
        "macd_cross_above",
        "macd_cross_below",
    }
    not_applied = ExternalBacktestEngine._NOT_APPLIED_INDICATORS
    missing: list[str] = []

    for path in sorted((_REPO_ROOT / "config" / "screens").glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        for rule in data.get("filters") or []:
            indicator = rule.get("indicator")
            if indicator in _SIMPLE_FILTER_RULES or indicator in special or indicator in not_applied:
                continue
            missing.append(f"{path.name}: {indicator}")

    assert not missing, f"indicators with no evaluator: {sorted(set(missing))}"
