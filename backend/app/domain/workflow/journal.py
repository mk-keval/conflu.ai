"""Paper-trade journal reader (plan Sec.2B).

Reads the dated CSV files in ``docs/paper_trades/`` (the 29-column D-51 schema,
or the 21-column D-50 legacy schema) and exposes the open book for:

- the gate's Step-6 portfolio fit (plan Sec.2C),
- the paper-trade enforcement script (phase 1D),
- the auto-exit backfill (plan Sec.2E).

Defensive by design: rows are plain CSVs written by the daily ritual / script,
and legacy rows may lack some columns entirely (``account_value`` was blank on
many early rows). Never raise on a malformed row — skip it and report.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

DEFAULT_TRADES_DIR = Path(__file__).resolve().parents[4] / "docs" / "paper_trades"

# Files that live in the trades dir but are NOT journal data.
NON_JOURNAL_FILES = {"TEMPLATE.csv", "REJECTIONS.csv"}

# Columns present in the D-51 29-column schema (superset of D-50's 21).
ENTRY_COLUMNS = [
    "date_entered", "symbol", "sector", "action", "entry_type", "entry_price",
    "stop_loss", "target_1", "target_2", "position_size_pct", "account_value",
    "shares", "confluence_count", "signal_at_entry", "gate_verdict",
    "gate_failed_step", "entry_low", "entry_high", "risk_reward_planned",
    "gate_version", "notes",
]
EXIT_COLUMNS = [
    "date_closed", "exit_price", "exit_reason", "realized_r", "pnl_usd",
    "mfe_r", "mae_r", "plan_adherence",
]


def _journal_files(trades_dir: Path | str | None = None) -> list[Path]:
    """Dated journal CSVs in the trades dir (archive/, TEMPLATE, REJECTIONS excluded)."""
    root = Path(trades_dir or DEFAULT_TRADES_DIR)
    if not root.is_dir():
        return []
    return sorted(
        p for p in root.glob("*.csv")
        if p.name not in NON_JOURNAL_FILES
    )


def _row_dict(row: dict[str, Any]) -> dict[str, Any]:
    """Normalize a CSV row: lowercase keys, strip whitespace, None for ''/'-'."""
    out: dict[str, Any] = {}
    for k, v in row.items():
        key = (k or "").strip().lower()
        if isinstance(v, str):
            v = v.strip()
        out[key] = None if v in ("", "-", "NA", "nan") else v
    return out


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    f = _as_float(value)
    return None if f is None else int(round(f))


def read_rows(trades_dir: Path | str | None = None) -> list[dict[str, Any]]:
    """All journal rows (both schemas) across dated CSVs, most-recent first.

    Rows are normalized dicts; numeric-ish cells are left as strings unless a
    typed accessor is used (see ``position_size_pct`` etc.).
    """
    rows: list[dict[str, Any]] = []
    for path in _journal_files(trades_dir):
        with path.open("r", encoding="utf-8", newline="") as fh:
            for raw in csv.DictReader(fh):
                norm = _row_dict(raw)
                if not norm.get("symbol"):
                    continue  # blank/header-only line
                norm["_file"] = path.name
                rows.append(norm)
    rows.sort(key=lambda r: r.get("date_entered") or "", reverse=True)
    return rows


def read_open_positions(trades_dir: Path | str | None = None) -> list[dict[str, Any]]:
    """Rows still open: no ``date_closed`` (blank, missing, or '-')."""
    return [
        r for r in read_rows(trades_dir)
        if not r.get("date_closed")
    ]


def read_closed_trades(trades_dir: Path | str | None = None) -> list[dict[str, Any]]:
    """Rows with a ``date_closed`` — the measurable sample."""
    return [
        r for r in read_rows(trades_dir)
        if r.get("date_closed")
    ]


def position_size_pct(row: dict[str, Any]) -> float:
    """Planned size as a % of account value (defensive default 0.0)."""
    return _as_float(row.get("position_size_pct")) or 0.0


def account_value(row: dict[str, Any]) -> float | None:
    """Account value at entry; None when absent (legacy rows)."""
    return _as_float(row.get("account_value"))


def sector_exposure(trades_dir: Path | str | None = None) -> dict[str, float]:
    """Aggregated position_size_pct by sector over the OPEN book.

    Returns {sector: total_size_pct}; ``position_size_pct`` is already a % of
    account value, so per-sector sums compare directly against
    ``SECTOR_EXPOSURE_LIMIT_PCT`` in the gate (plan Sec.2C).
    """
    out: dict[str, float] = {}
    for row in read_open_positions(trades_dir):
        sector = (row.get("sector") or "Unknown").strip() or "Unknown"
        out[sector] = out.get(sector, 0.0) + position_size_pct(row)
    return out


def available_capital(
    trades_dir: Path | str | None = None,
    explicit_account_value: float | None = None,
) -> float:
    """Account value minus open notional (position_size_pct × account value).

    ``explicit_account_value`` may be passed (the script knows it from the
    verdict); otherwise the most recent non-blank journal value is used, and
    finally a documented default of $100,000.
    """
    account_value_f: float | None = explicit_account_value
    if account_value_f is None:
        for row in read_rows(trades_dir):
            av = _as_float(row.get("account_value"))
            if av:
                account_value_f = av
                break
    if account_value_f is None:
        account_value_f = 100_000.0  # documented default when journal never recorded it
    open_notional = sum(
        position_size_pct(r) / 100.0 * account_value_f
        for r in read_open_positions(trades_dir)
    )
    return account_value_f - open_notional


__all__ = [
    "DEFAULT_TRADES_DIR",
    "read_rows",
    "read_open_positions",
    "read_closed_trades",
    "position_size_pct",
    "account_value",
    "sector_exposure",
    "available_capital",
]