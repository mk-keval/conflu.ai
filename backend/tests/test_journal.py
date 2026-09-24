"""Journal reader tests (plan Sec.2B).

Uses a temp trades dir with one 29-col CSV (D-51) and one 21-col legacy CSV
(D-50), plus TEMPLATE.csv / REJECTIONS.csv that must be ignored.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from backend.app.domain.workflow import journal

HEADER_29 = [
    "date_entered", "symbol", "sector", "action", "entry_type", "entry_price",
    "stop_loss", "target_1", "target_2", "position_size_pct", "account_value",
    "shares", "confluence_count", "signal_at_entry", "gate_verdict",
    "gate_failed_step", "entry_low", "entry_high", "risk_reward_planned",
    "gate_version", "notes", "date_closed", "exit_price", "exit_reason",
    "realized_r", "pnl_usd", "mfe_r", "mae_r", "plan_adherence",
]
HEADER_21 = [
    "date_entered", "symbol", "sector", "action", "entry_price", "stop_loss",
    "target_1", "target_2", "position_size_pct", "confluence_count",
    "signal_at_entry", "notes", "date_closed", "exit_price", "exit_reason",
    "shares", "realized_r", "pnl_usd", "mfe_r", "mae_r", "plan_adherence",
]


def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)


def _make_trades_dir(tmp_path: Path) -> Path:
    d = tmp_path / "trades"
    d.mkdir()
    # Open position (29-col, D-51 schema).
    _write_csv(d / "2026-09-18.csv", HEADER_29, [[
        "2026-09-18", "AAPL", "Technology", "buy", "initial", "210.00",
        "200.00", "225.00", "240.00", "8.0", "100000", "38", "3",
        "TECH_SCREENER", "CONDITIONAL", "Liquidity", "209.50", "210.50",
        "2.4", "D-53-gate", "test", "", "", "", "", "", "", "", "",
    ]])
    # Closed position (29-col).
    _write_csv(d / "2026-09-15.csv", HEADER_29, [[
        "2026-09-15", "MSFT", "Technology", "buy", "initial", "420.00",
        "410.00", "450.00", "470.00", "5.0", "100000", "11", "2",
        "TECH_SCREENER", "PASS", "", "419.50", "420.50", "3.0",
        "D-53-gate", "test", "2026-09-17", "455.00", "target_1", "2.5",
        "1750.00", "3.1", "1.2", "adherence_yes",
    ]])
    # Legacy 21-col open row with blank account_value.
    _write_csv(d / "2026-09-10.csv", HEADER_21, [[
        "2026-09-10", "NVDA", "Semiconductors", "buy", "95.00", "90.00",
        "105.00", "112.00", "6.0", "2", "CHIP_SCREENER", "legacy",
        "", "", "", "", "", "", "", "", "",
    ]])
    # Non-journal files must be ignored.
    _write_csv(d / "TEMPLATE.csv", HEADER_29, [])
    _write_csv(d / "REJECTIONS.csv", ["date_seen", "symbol", "reason"], [["2026-09-18", "TSLA", "gate_fail"]])
    return d


def test_read_rows_normalizes_and_sorts(tmp_path: Path) -> None:
    d = _make_trades_dir(tmp_path)
    rows = journal.read_rows(d)
    assert len(rows) == 3
    assert rows[0]["symbol"] == "AAPL"  # 2026-09-18 first (desc)
    assert rows[0]["position_size_pct"] == "8.0"
    assert rows[0]["entry_type"] == "initial"
    # TEMPLATE/REJECTIONS never appear.
    assert all(r["_file"] not in ("TEMPLATE.csv", "REJECTIONS.csv") for r in rows)


def test_read_open_positions_filters_by_date_closed(tmp_path: Path) -> None:
    d = _make_trades_dir(tmp_path)
    open_rows = journal.read_open_positions(d)
    assert {r["symbol"] for r in open_rows} == {"AAPL", "NVDA"}
    closed = journal.read_closed_trades(d)
    assert {r["symbol"] for r in closed} == {"MSFT"}


def test_position_size_pct_and_account_value_accessors(tmp_path: Path) -> None:
    d = _make_trades_dir(tmp_path)
    rows = {r["symbol"]: r for r in journal.read_rows(d)}
    assert journal.position_size_pct(rows["AAPL"]) == 8.0
    assert journal.account_value(rows["AAPL"]) == 100_000.0
    # Legacy row: blank account_value → None.
    assert journal.account_value(rows["NVDA"]) is None


def test_sector_exposure_aggregates_open_book(tmp_path: Path) -> None:
    d = _make_trades_dir(tmp_path)
    exposure = journal.sector_exposure(d)
    # Technology: AAPL 8.0 open. Semiconductors: NVDA 6.0 open. MSFT closed → excluded.
    assert exposure == {"Technology": 8.0, "Semiconductors": 6.0}


def test_available_capital_explicit_and_fallback(tmp_path: Path) -> None:
    d = _make_trades_dir(tmp_path)
    # Explicit account value: 8.0% + 6.0% open notional.
    assert journal.available_capital(d, explicit_account_value=100_000.0) == pytest.approx(86_000.0)
    # Fallback: most recent non-blank journal account_value = 100000 (AAPL row).
    assert journal.available_capital(d) == pytest.approx(86_000.0)
    # Empty dir → default $100k.
    empty = tmp_path / "empty"
    empty.mkdir()
    assert journal.available_capital(empty) == pytest.approx(100_000.0)


def test_ignores_empty_and_blank_dirs(tmp_path: Path) -> None:
    empty = tmp_path / "nothing"
    empty.mkdir()
    assert journal.read_rows(empty) == []
    assert journal.read_open_positions(empty) == []
    assert journal.sector_exposure(empty) == {}