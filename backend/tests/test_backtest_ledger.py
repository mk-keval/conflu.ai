"""Tests for trade ledger."""

from __future__ import annotations

import pandas as pd
import pytest

from backend.app.infrastructure.backtest.ledger import TradeLedger


@pytest.fixture
def ohlcv() -> pd.DataFrame:
    """OHLCV with DatetimeIndex, symbol column (col 0), and high/low for MAE/MFE."""
    return pd.DataFrame(
        {
            "SYMBOL_0": [1.0] * 6,  # Column 0 = symbol for column-to-symbol mapping
            "high": [152.0, 154.0, 150.0, 158.0, 155.0, 157.0],
            "low": [148.0, 150.0, 147.0, 153.0, 152.0, 151.0],
        },
        index=pd.date_range("2024-01-01", periods=6, freq="D", tz="UTC"),
    )


@pytest.fixture
def trades_records() -> pd.DataFrame:
    """Simulated vectorbt trades.records DataFrame."""
    return pd.DataFrame({
        "column": [0],
        "size": [100.0],
        "entry_idx": [1],
        "entry_price": [153.0],
        "exit_idx": [3],
        "exit_price": [156.0],
        "pnl": [300.0],
        "return": [0.02],
        "direction": [1],  # 1 = Long
        "entry_fees": [1.5],
        "exit_fees": [1.5],
    })


def test_empty_records(ohlcv):
    """Empty records return empty list."""
    ledger = TradeLedger()
    empty = pd.DataFrame()
    result = ledger.build_ledger(empty, ohlcv)
    assert result == []


def test_single_trade(trades_records, ohlcv):
    """Single trade record produces one Trade model."""
    ledger = TradeLedger()
    trades = ledger.build_ledger(trades_records, ohlcv)
    assert len(trades) == 1
    trade = trades[0]
    assert trade.symbol == "SYMBOL_0"
    assert trade.size == 100.0
    assert trade.pnl == 300.0


def test_trade_timezone_aware(trades_records, ohlcv):
    """Trade entry/exit times should be timezone-aware."""
    ledger = TradeLedger()
    trades = ledger.build_ledger(trades_records, ohlcv)
    trade = trades[0]
    assert trade.entry_time.tzinfo is not None
    assert trade.exit_time.tzinfo is not None


def test_mae_mfe_long(trades_records, ohlcv):
    """MAE/MFE computed for long direction."""
    # entry_idx=1 (price=153), exit_idx=3
    # high[1..3] = max(154, 150, 158) = 158, MFE = 158-153 = 5
    # low[1..3] = min(150, 147, 153) = 147, MAE = 153-147 = 6
    ledger = TradeLedger()
    trades = ledger.build_ledger(trades_records, ohlcv)
    trade = trades[0]
    assert trade.mfe == pytest.approx(5.0, abs=0.01), f"Expected MFE=5, got {trade.mfe}"
    assert trade.mae == pytest.approx(6.0, abs=0.01), f"Expected MAE=6, got {trade.mae}"


def test_mae_mfe_short(ohlcv):
    """MAE/MFE computed for short direction."""
    short_records = pd.DataFrame({
        "column": [0],
        "size": [100.0],
        "entry_idx": [1],
        "entry_price": [153.0],
        "exit_idx": [3],
        "exit_price": [148.0],
        "pnl": [500.0],
        "return": [0.03],
        "direction": [-1],  # -1 = Short
        "entry_fees": [1.5],
        "exit_fees": [1.5],
    })
    ledger = TradeLedger()
    trades = ledger.build_ledger(short_records, ohlcv)
    trade = trades[0]
    # Short: MFE = entry - min(low) = 153 - 147 = 6
    # Short: MAE = max(high) - entry = 158 - 153 = 5
    assert trade.mfe == pytest.approx(6.0, abs=0.01), f"Expected MFE=6, got {trade.mfe}"
    assert trade.mae == pytest.approx(5.0, abs=0.01), f"Expected MAE=5, got {trade.mae}"


def test_hold_duration_computed(trades_records, ohlcv):
    """Hold duration = exit_idx - entry_idx."""
    ledger = TradeLedger()
    trades = ledger.build_ledger(trades_records, ohlcv)
    trade = trades[0]
    assert trade.hold_duration_bars == 2  # 3 - 1


def test_signal_metadata_attached(trades_records, ohlcv):
    """Signal metadata maps to correct trade."""
    metadata = {1: {"exit_reason": "stop_loss", "confidence": 0.85}}
    ledger = TradeLedger()
    trades = ledger.build_ledger(trades_records, ohlcv, metadata)
    trade = trades[0]
    assert trade.exit_reason == "stop_loss"


def test_idx_to_symbol():
    """_idx_to_symbol maps column index to symbol name."""
    ohlcv = pd.DataFrame({"AAPL": [1, 2, 3], "MSFT": [4, 5, 6]})
    assert TradeLedger._idx_to_symbol(0, ohlcv) == "AAPL"
    assert TradeLedger._idx_to_symbol(1, ohlcv) == "MSFT"
    assert TradeLedger._idx_to_symbol(5, ohlcv) == "SYMBOL_5"
