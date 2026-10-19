"""Paper-trade journal (D-68): SQLite-backed store, read API unchanged.

The journal of record is ``data/paper_trades.db`` (SQLite; see
``journal_store`` for schema, upsert rules, import/export). This module keeps
the historical read API used by the gate's Step-6 portfolio fit, the
paper-trade enforcement endpoints, the auto-exit backfill, and expectancy
verification. CSV files in ``docs/paper_trades/`` are import/export
artifacts only.

``trades_dir`` parameters are deprecated-but-accepted (ignored with a debug
log) so no caller breaks during the migration.

Defensive by design: rows are normalized dicts with stringified cells
(CSV parity); never raise on a malformed row — skip it and report.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.app.core.logging import get_logger
from backend.app.domain.workflow import journal_store

log = get_logger("conflu.workflow.journal")

# Kept for compatibility with existing callers (verification.py, router):
# the path where CSV import/export artifacts live — NOT the journal store.
DEFAULT_TRADES_DIR = journal_store.DEFAULT_CSV_DIR


def _note_deprecated(func_name: str, trades_dir: Path | str | None) -> None:
    if trades_dir is not None:
        log.debug("journal.trades_dir_ignored", func=func_name, trades_dir=str(trades_dir))


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
    """All journal rows from the DB, most-recent first.

    Rows are normalized dicts; numeric-ish cells are left as strings unless a
    typed accessor is used (see ``position_size_pct`` etc.).
    """
    _note_deprecated("read_rows", trades_dir)
    return journal_store.fetch_rows()


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


# ── Write API (store re-exports; router/script/tests call these) ──

set_db_path = journal_store.set_db_path
reset_db_path = journal_store.reset_db_path
get_db_path = journal_store.get_db_path
market_today = journal_store.market_today
upsert_entry = journal_store.upsert_entry
update_exit = journal_store.update_exit
insert_rejection = journal_store.insert_rejection
record_run = journal_store.record_run
list_runs = journal_store.list_runs
list_rejections = journal_store.list_rejections
export_csv = journal_store.export_csv
import_csv_dir = journal_store.import_csv_dir


__all__ = [
    "DEFAULT_TRADES_DIR",
    "read_rows",
    "read_open_positions",
    "read_closed_trades",
    "position_size_pct",
    "account_value",
    "sector_exposure",
    "available_capital",
    "set_db_path",
    "reset_db_path",
    "get_db_path",
    "market_today",
    "upsert_entry",
    "update_exit",
    "insert_rejection",
    "record_run",
    "list_runs",
    "list_rejections",
    "export_csv",
    "import_csv_dir",
]
