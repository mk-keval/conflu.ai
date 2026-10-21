"""SQLite-backed paper-trade journal store (D-68, plan P1).

The journal of record is a single SQLite file (``data/paper_trades.db`` by
default, ``CONFLU_CORE_PAPER_JOURNAL_PATH``). Three tables:

- ``paper_trades``   — one row per (date_entered, symbol); entry and exit
                       columns are separate so an exit sync never collides
                       with an entry re-run. ``voided`` rows stay visible but
                       are not positions and never enter the scorecard.
- ``pending_orders`` — after-close orders waiting for an actual next-session
                       fill (D-73); one active order per symbol.
- ``rejections``     — gate rejections (one per date_seen + symbol).
- ``workflow_runs``  — one row per touchpoint run (enforce / sync_exits /
                       run_close / import).

CSV files in ``docs/paper_trades/`` become import/export artifacts: they are
never written by this module and are imported only into an empty journal
(first boot). Concurrency: per-call short-lived connections (single user),
WAL + busy_timeout. stdlib ``sqlite3`` only.

Ops CLI (from the repo root):

    python -m backend.app.domain.workflow.journal_store --import-csv
    python -m backend.app.domain.workflow.journal_store --export-csv out.csv
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import sqlite3
import sys
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator
from zoneinfo import ZoneInfo

from backend.app.core.logging import get_logger

log = get_logger("conflu.workflow.journal_store")

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DB_PATH = REPO_ROOT / "data" / "paper_trades.db"
DEFAULT_CSV_DIR = REPO_ROOT / "docs" / "paper_trades"
NON_JOURNAL_FILES = {"TEMPLATE.csv", "REJECTIONS.csv"}

# Canonical entry columns (21, D-51 schema) + journal-only extra columns.
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
EXTRA_COLUMNS = ["template", "regime", "entry_timing", "max_hold_days"]
# Operational flags: fetched with rows but never overwritten by an entry upsert.
META_COLUMNS = ["exclude_from_stats", "voided", "void_reason"]
ENTRY_DB_COLUMNS = ENTRY_COLUMNS + EXTRA_COLUMNS
FETCH_COLUMNS = ENTRY_DB_COLUMNS + EXIT_COLUMNS + META_COLUMNS
PENDING_COLUMNS = [
    "signal_date", "symbol", "sector", "action", "order_type", "limit_price",
    "entry_low", "entry_high", "stop_loss", "target_1", "target_2",
    "position_size_pct", "account_value", "shares", "confluence_count",
    "signal_at_entry", "gate_verdict", "gate_failed_step",
    "risk_reward_planned", "gate_version", "notes", "template", "regime",
    "max_hold_days", "expires_after_sessions", "status", "status_date",
    "status_reason",
]
PENDING_STATUSES = ("pending", "filled", "expired", "cancelled")
ORDER_TYPES = ("limit", "moo")
REJECTION_COLUMNS = [
    "date_seen", "symbol", "sector", "action", "conviction",
    "failed_step", "gate_verdict", "reason", "notes", "template", "regime",
]
RUN_MODES = ("enforce", "sync_exits", "run_close", "import")

_FLOAT_COLUMNS = {
    "entry_price", "stop_loss", "target_1", "target_2", "position_size_pct",
    "account_value", "shares", "entry_low", "entry_high", "risk_reward_planned",
    "exit_price", "realized_r", "pnl_usd", "mfe_r", "mae_r", "plan_adherence",
    "limit_price",
}
_INT_COLUMNS = {
    "confluence_count", "conviction", "max_hold_days", "exclude_from_stats",
    "voided", "expires_after_sessions",
}
_EMPTY_CELLS = {"", "-", "NA", "nan"}

_DDL = """
CREATE TABLE IF NOT EXISTS paper_trades (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  date_entered TEXT NOT NULL,
  symbol TEXT NOT NULL,
  sector TEXT, action TEXT, entry_type TEXT DEFAULT 'initial',
  entry_price REAL, stop_loss REAL, target_1 REAL, target_2 REAL,
  position_size_pct REAL, account_value REAL, shares REAL,
  confluence_count INTEGER, signal_at_entry TEXT,
  gate_verdict TEXT, gate_failed_step TEXT,
  entry_low REAL, entry_high REAL, risk_reward_planned REAL,
  gate_version TEXT, notes TEXT,
  template TEXT, regime TEXT,
  entry_timing TEXT NOT NULL DEFAULT 'eod',
  max_hold_days INTEGER,
  date_closed TEXT, exit_price REAL, exit_reason TEXT,
  realized_r REAL, pnl_usd REAL, mfe_r REAL, mae_r REAL, plan_adherence REAL,
  exclude_from_stats INTEGER NOT NULL DEFAULT 0,
  voided INTEGER NOT NULL DEFAULT 0,
  void_reason TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_paper_trades_day_symbol
  ON paper_trades(date_entered, symbol);

CREATE TABLE IF NOT EXISTS pending_orders (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  signal_date TEXT NOT NULL,
  symbol TEXT NOT NULL,
  sector TEXT, action TEXT,
  order_type TEXT NOT NULL DEFAULT 'limit',
  limit_price REAL, entry_low REAL, entry_high REAL,
  stop_loss REAL, target_1 REAL, target_2 REAL,
  position_size_pct REAL, account_value REAL, shares REAL,
  confluence_count INTEGER, signal_at_entry TEXT,
  gate_verdict TEXT, gate_failed_step TEXT,
  risk_reward_planned REAL, gate_version TEXT, notes TEXT,
  template TEXT, regime TEXT, max_hold_days INTEGER,
  expires_after_sessions INTEGER NOT NULL DEFAULT 3,
  status TEXT NOT NULL DEFAULT 'pending',
  status_date TEXT, status_reason TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_pending_orders_active_symbol
  ON pending_orders(symbol) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS ix_pending_orders_status
  ON pending_orders(status);

CREATE TABLE IF NOT EXISTS rejections (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  date_seen TEXT NOT NULL, symbol TEXT NOT NULL, sector TEXT, action TEXT,
  conviction INTEGER, failed_step TEXT, gate_verdict TEXT, reason TEXT, notes TEXT,
  template TEXT, regime TEXT,
  created_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_rejections_day_symbol
  ON rejections(date_seen, symbol);

CREATE TABLE IF NOT EXISTS workflow_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_date TEXT NOT NULL,
  ran_at TEXT NOT NULL,
  mode TEXT NOT NULL,
  apply INTEGER NOT NULL DEFAULT 0,
  accepted INTEGER, rejected INTEGER, updated INTEGER, skipped INTEGER,
  status TEXT NOT NULL DEFAULT 'ok',
  message TEXT, details_json TEXT
);
"""


def _migrate(con: sqlite3.Connection) -> None:
    """Add columns introduced after a DB was first created (idempotent)."""
    additions = {
        "paper_trades": {
            "template": "TEXT",
            "regime": "TEXT",
            "entry_timing": "TEXT NOT NULL DEFAULT 'eod'",
            "max_hold_days": "INTEGER",
            "exclude_from_stats": "INTEGER NOT NULL DEFAULT 0",
            "voided": "INTEGER NOT NULL DEFAULT 0",
            "void_reason": "TEXT",
        },
        "rejections": {"template": "TEXT", "regime": "TEXT"},
    }
    for table, columns in additions.items():
        existing = {row[1] for row in con.execute(f"PRAGMA table_info({table})")}
        for name, decl in columns.items():
            if name not in existing:
                con.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")


# ── Path resolution / initialization ──

_db_path_override: Path | None = None
_explicit_override = False
_initialized_path: Path | None = None


def get_db_path() -> Path:
    """Resolve the active DB path: explicit override → config → default."""
    if _db_path_override is not None:
        return _db_path_override
    configured: str | None = None
    try:
        from backend.app.core.config import settings

        configured = getattr(settings.core, "paper_journal_path", None)
    except Exception:  # config unavailable (standalone import) — use the default
        configured = None
    path = Path(configured) if configured else DEFAULT_DB_PATH
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path


def set_db_path(path: Path | str) -> Path:
    """Override the journal DB path (tests / ops). Disables first-boot import."""
    global _db_path_override, _explicit_override, _initialized_path
    _db_path_override = Path(path)
    _explicit_override = True
    _initialized_path = None
    return _db_path_override


def reset_db_path() -> None:
    """Restore config/default path resolution and drop process init state."""
    global _db_path_override, _explicit_override, _initialized_path
    _db_path_override = None
    _explicit_override = False
    _initialized_path = None


def ensure() -> None:
    """Idempotent init: DDL + WAL, then first-boot CSV import (configured DB only)."""
    global _initialized_path
    path = get_db_path()
    if _initialized_path == path:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=30.0)
    try:
        try:
            con.execute("PRAGMA journal_mode=WAL")
        except sqlite3.OperationalError as exc:  # e.g. exotic FS without WAL
            log.warning("journal.wal_unavailable", error=str(exc))
        con.execute("PRAGMA busy_timeout=5000")
        con.executescript(_DDL)
        _migrate(con)
        con.commit()
    finally:
        con.close()
    _initialized_path = path
    if not _explicit_override:
        summary = import_legacy_if_needed()
        if summary:
            log.info("journal.migrated", db=str(path), **summary)


@contextmanager
def session() -> Iterator[sqlite3.Connection]:
    """Short-lived connection: commits on success, rolls back on error."""
    ensure()
    con = sqlite3.connect(get_db_path(), timeout=30.0)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout=5000")
    try:
        yield con
        con.commit()
    except BaseException:
        con.rollback()
        raise
    finally:
        con.close()


# ── Value normalization ──


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


_EASTERN = ZoneInfo("America/New_York")


def market_today() -> str:
    """Current ET market date (YYYY-MM-DD) — the journal's date stamp.

    Entries are recorded after the close; an evening run (≥8pm ET) under UTC
    would stamp *tomorrow* (data-audit bug R3). ``ran_at``/``created_at``
    columns stay UTC ISO — only market dates are ET.
    """
    return datetime.now(_EASTERN).strftime("%Y-%m-%d")


def _clean(value: Any) -> Any:
    """CSV-parity normalization: strip strings; None for ''/'-'/'NA'/'nan'/NaN."""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, str):
        value = value.strip()
        if value in _EMPTY_CELLS:
            return None
    return value


def _coerce(column: str, value: Any) -> Any:
    value = _clean(value)
    if value is None:
        return None
    if column in _FLOAT_COLUMNS:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    if column in _INT_COLUMNS:
        try:
            return int(round(float(value)))
        except (TypeError, ValueError):
            return None
    return value


def _cell(value: Any) -> Any:
    """Stringify a stored cell for CSV parity (legacy reader returned strings)."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        if math.isnan(value):
            return None
        return str(value)  # legacy CSV convention: str(float) e.g. "100000.0"
    return str(value)


def _norm_row(row: dict[str, Any]) -> dict[str, Any]:
    return {str(k).strip().lower(): v for k, v in row.items()}


# ── Reads ──


def fetch_rows(*, order: str = "desc") -> list[dict[str, Any]]:
    """All journal rows, stringified cells (CSV parity), most-recent first.

    ``order="asc"`` is used by the exporter (chronological, diary-like).
    """
    direction = "ASC" if str(order).lower() == "asc" else "DESC"
    with session() as con:
        cur = con.execute(
            f"SELECT {', '.join(FETCH_COLUMNS)} FROM paper_trades "
            f"ORDER BY date_entered {direction}, id {direction}"
        )
        return [{c: _cell(row[c]) for c in FETCH_COLUMNS} for row in cur.fetchall()]


# ── Writes ──


def upsert_entry(row: dict[str, Any]) -> str:
    """Insert/update one entry by (date_entered, symbol). Exit columns untouched.

    Returns ``"inserted"`` or ``"updated"``. A same-day re-run wins on entry
    fields (fresh evaluation); a row with exit data keeps it.
    """
    norm = _norm_row(row)
    date_entered = _clean(norm.get("date_entered"))
    symbol = _clean(norm.get("symbol"))
    if not date_entered or not symbol:
        raise ValueError("upsert_entry requires non-empty date_entered and symbol")
    values = {c: _coerce(c, norm.get(c)) for c in ENTRY_DB_COLUMNS}
    values["date_entered"] = str(date_entered)
    values["symbol"] = str(symbol)
    values["entry_timing"] = _clean(norm.get("entry_timing")) or "eod"
    now = _utc_now()
    with session() as con:
        existing = con.execute(
            "SELECT id FROM paper_trades WHERE date_entered = ? AND symbol = ?",
            (date_entered, symbol),
        ).fetchone()
        if existing:
            sets = [c for c in ENTRY_DB_COLUMNS if c not in ("date_entered", "symbol")]
            con.execute(
                f"UPDATE paper_trades SET {', '.join(f'{c} = ?' for c in sets)}, "
                "updated_at = ? WHERE id = ?",
                [*[values[c] for c in sets], now, existing["id"]],
            )
            return "updated"
        cols = [*ENTRY_DB_COLUMNS, "created_at", "updated_at"]
        con.execute(
            f"INSERT INTO paper_trades ({', '.join(cols)}) "
            f"VALUES ({', '.join('?' * len(cols))})",
            [*[values[c] for c in ENTRY_DB_COLUMNS], now, now],
        )
        return "inserted"


def update_exit(date_entered: Any, symbol: Any, updates: dict[str, Any]) -> bool:
    """Apply exit columns to an open row. Returns True when a row was updated.

    Guarded by ``date_closed IS NULL`` — an already-closed row is never
    rewritten; identity is (date_entered, symbol) like the store's unique key.
    """
    de = _clean(date_entered)
    sym = _clean(symbol)
    payload = {
        str(k).strip().lower(): _coerce(str(k).strip().lower(), v)
        for k, v in updates.items()
        if str(k).strip().lower() in EXIT_COLUMNS
    }
    if not de or not sym or not payload:
        return False
    with session() as con:
        cur = con.execute(
            f"UPDATE paper_trades SET {', '.join(f'{c} = ?' for c in payload)}, "
            "updated_at = ? WHERE date_entered = ? AND symbol = ? AND date_closed IS NULL",
            [*payload.values(), _utc_now(), de, sym],
        )
        return cur.rowcount > 0


def set_exclude_from_stats(date_entered: Any, symbol: Any, excluded: bool = True) -> bool:
    """Mark one row in/out of the forward-sample statistics.

    The row stays visible in the journal and in the open book; only the
    expectancy/scorecard queries skip it. Used for the three pre-instrumentation
    legacy rows.
    """
    de = _clean(date_entered)
    sym = _clean(symbol)
    if not de or not sym:
        return False
    with session() as con:
        cur = con.execute(
            "UPDATE paper_trades SET exclude_from_stats = ?, updated_at = ? "
            "WHERE date_entered = ? AND symbol = ?",
            (1 if excluded else 0, _utc_now(), de, sym),
        )
        return cur.rowcount > 0


def void_trade(date_entered: Any, symbol: Any, reason: str) -> bool:
    """Void one journal row: visible, but not a position and never scored.

    Used for rows whose recorded fill never traded (the 2026-10-19/20 phantom
    fills). The row is kept for the audit trail; ``read_open_positions`` and the
    scorecard both ignore it. Idempotent.
    """
    de = _clean(date_entered)
    sym = _clean(symbol)
    if not de or not sym:
        return False
    with session() as con:
        cur = con.execute(
            "UPDATE paper_trades SET voided = 1, void_reason = ?, "
            "exclude_from_stats = 1, updated_at = ? "
            "WHERE date_entered = ? AND symbol = ?",
            (str(reason or "voided")[:500], _utc_now(), de, sym),
        )
        return cur.rowcount > 0


# ── Pending orders (D-73) ──


def insert_pending_order(
    row: dict[str, Any],
    *,
    order_type: str = "limit",
    limit_price: float | None = None,
    expires_after_sessions: int = 3,
) -> int | None:
    """Create one after-close pending order. Returns its id, or None if blocked.

    ``row`` is a normal entry row (``date_entered`` is the signal date). A limit
    order defaults to ``entry_low`` — the bottom of the desired zone. A MOO
    order fills only at the next open inside ``entry_high`` (no chase).

    One active order per symbol: the partial unique index turns a duplicate into
    ``None`` instead of raising, so a re-run is idempotent.
    """
    norm = _norm_row(row)
    signal_date = _clean(norm.get("signal_date") or norm.get("date_entered"))
    symbol = _clean(norm.get("symbol"))
    if not signal_date or not symbol:
        raise ValueError("insert_pending_order requires a signal date and symbol")

    order_type = str(order_type or norm.get("order_type") or "limit").strip().lower()
    if order_type not in ORDER_TYPES:
        raise ValueError(f"Unknown order_type {order_type!r}; expected one of {ORDER_TYPES}")

    values = {c: _coerce(c, norm.get(c)) for c in PENDING_COLUMNS}
    values["signal_date"] = str(signal_date)[:10]
    values["symbol"] = str(symbol).strip().upper()
    values["order_type"] = order_type

    if limit_price is None:
        limit_price = values.get("limit_price")
    if limit_price is None and order_type == "limit":
        limit_price = values.get("entry_low") or _coerce("limit_price", norm.get("entry_price"))
    values["limit_price"] = _coerce("limit_price", limit_price)

    stop = values.get("stop_loss")
    if not stop:
        raise ValueError("pending order requires stop_loss")
    if order_type == "limit":
        if not values["limit_price"] or values["limit_price"] <= stop:
            raise ValueError("limit order requires limit_price above stop_loss")
    else:
        values["limit_price"] = None
        if not (values.get("entry_high") or values.get("entry_low")):
            raise ValueError("MOO order requires an entry zone (entry_high)")

    try:
        expires = int(expires_after_sessions)
    except (TypeError, ValueError):
        expires = 3
    values["expires_after_sessions"] = max(1, expires)
    values["shares"] = None
    values["status"] = "pending"
    values["status_date"] = None
    values["status_reason"] = None

    cols = [*PENDING_COLUMNS, "created_at", "updated_at"]
    now = _utc_now()
    try:
        with session() as con:
            cur = con.execute(
                f"INSERT INTO pending_orders ({', '.join(cols)}) "
                f"VALUES ({', '.join('?' * len(cols))})",
                [*[values[c] for c in PENDING_COLUMNS], now, now],
            )
            return int(cur.lastrowid or 0)
    except sqlite3.IntegrityError:
        return None  # an active order already exists for this symbol


def list_pending_orders(
    status: str | None = "pending", limit: int = 200
) -> list[dict[str, Any]]:
    """Pending-order rows, most recent first. ``status='all'`` returns history."""
    where, params = "", []
    if status and str(status).lower() != "all":
        status = str(status).lower()
        if status not in PENDING_STATUSES:
            raise ValueError(f"Unknown pending status {status!r}")
        where, params = " WHERE status = ?", [status]
    cols = ["id", *PENDING_COLUMNS, "created_at", "updated_at"]
    with session() as con:
        cur = con.execute(
            f"SELECT {', '.join(cols)} FROM pending_orders{where} "
            "ORDER BY id DESC LIMIT ?",
            (*params, max(1, int(limit))),
        )
        return [dict(row) for row in cur.fetchall()]


def update_pending_order(
    order_id: int,
    *,
    status: str,
    status_date: str,
    status_reason: str | None = None,
) -> bool:
    """Move one active order to filled/expired/cancelled.

    Guarded by ``status = 'pending'`` so a re-run never rewrites history.
    """
    status = str(status).lower()
    if status not in PENDING_STATUSES or status == "pending":
        raise ValueError(f"Invalid terminal pending status {status!r}")
    with session() as con:
        cur = con.execute(
            "UPDATE pending_orders SET status = ?, status_date = ?, "
            "status_reason = ?, updated_at = ? WHERE id = ? AND status = 'pending'",
            (status, str(status_date)[:10], status_reason, _utc_now(), int(order_id)),
        )
        return cur.rowcount > 0


def insert_rejection(rejection: dict[str, Any]) -> bool:
    """One rejection per (date_seen, symbol) — re-runs don't duplicate."""
    norm = _norm_row(rejection)
    date_seen = _clean(norm.get("date_seen"))
    symbol = _clean(norm.get("symbol"))
    if not date_seen or not symbol:
        return False
    values = {c: _coerce(c, norm.get(c)) for c in REJECTION_COLUMNS}
    values["date_seen"] = str(date_seen)
    values["symbol"] = str(symbol)
    values["created_at"] = _utc_now()
    cols = [*REJECTION_COLUMNS, "created_at"]
    with session() as con:
        cur = con.execute(
            f"INSERT OR IGNORE INTO rejections ({', '.join(cols)}) "
            f"VALUES ({', '.join('?' * len(cols))})",
            [values[c] for c in cols],
        )
        return cur.rowcount == 1


def record_run(
    mode: str,
    *,
    run_date: str | None = None,
    apply: bool = False,
    accepted: int | None = None,
    rejected: int | None = None,
    updated: int | None = None,
    skipped: int | None = None,
    status: str = "ok",
    message: str | None = None,
    details: Any = None,
) -> int:
    """Append a workflow_runs row; returns its id. ``ran_at`` is UTC ISO."""
    details_json = (
        json.dumps(details, ensure_ascii=False, default=str) if details is not None else None
    )
    with session() as con:
        cur = con.execute(
            "INSERT INTO workflow_runs (run_date, ran_at, mode, apply, accepted, "
            "rejected, updated, skipped, status, message, details_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_date or market_today(), _utc_now(), str(mode), 1 if apply else 0,
                accepted, rejected, updated, skipped, str(status),
                message, details_json,
            ),
        )
        return int(cur.lastrowid or 0)


def list_runs(limit: int = 14) -> list[dict[str, Any]]:
    """Most-recent-first workflow run rows (UI runs strip)."""
    with session() as con:
        cur = con.execute(
            "SELECT id, run_date, ran_at, mode, apply, accepted, rejected, updated, "
            "skipped, status, message, details_json FROM workflow_runs "
            "ORDER BY id DESC LIMIT ?",
            (max(1, int(limit)),),
        )
        return [dict(row) for row in cur.fetchall()]


def list_rejections(limit: int = 200) -> list[dict[str, Any]]:
    """Most-recent-first rejection rows."""
    cols = ["id", *REJECTION_COLUMNS, "created_at"]
    with session() as con:
        cur = con.execute(
            f"SELECT {', '.join(cols)} FROM rejections ORDER BY id DESC LIMIT ?",
            (max(1, int(limit)),),
        )
        return [dict(row) for row in cur.fetchall()]


# ── Export / import ──


def export_csv() -> str:
    """Canonical CSV export: journal columns plus voided/void_reason audit flags."""
    header = [*ENTRY_COLUMNS, *EXIT_COLUMNS, *EXTRA_COLUMNS, "voided", "void_reason"]
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    for row in fetch_rows(order="asc"):
        writer.writerow(["" if row.get(c) is None else row.get(c) for c in header])
    return buf.getvalue()


def import_csv_dir(csv_dir: Path | str | None = None) -> dict[str, int]:
    """Import top-level dated CSVs (+ REJECTIONS.csv) into the store.

    Additive and idempotent via the upsert/ignore rules; never modifies the
    CSVs. Same-day duplicates collapse to one row — a row carrying exit data
    wins over one without.
    """
    root = Path(csv_dir or DEFAULT_CSV_DIR)
    summary = {
        "files": 0, "rows": 0, "inserted": 0, "updated": 0,
        "collapsed": 0, "exit_updates": 0, "rejections": 0, "voided": 0,
    }
    if not root.is_dir():
        return summary

    batch: dict[tuple[str, str], dict[str, Any]] = {}
    for path in sorted(root.glob("*.csv")):
        if path.name in NON_JOURNAL_FILES:
            continue
        summary["files"] += 1
        with path.open("r", encoding="utf-8", newline="") as fh:
            for raw in csv.DictReader(fh):
                norm = _norm_row({k: _clean(v) for k, v in raw.items() if k})
                symbol, date_entered = norm.get("symbol"), norm.get("date_entered")
                if not symbol or not date_entered:
                    continue  # blank/header-only line
                summary["rows"] += 1
                key = (str(date_entered), str(symbol))
                prev = batch.get(key)
                if prev is None:
                    batch[key] = norm
                    continue
                summary["collapsed"] += 1
                if norm.get("date_closed") and not prev.get("date_closed"):
                    batch[key] = norm
                    log.info("journal.import.collapsed", symbol=symbol,
                             date_entered=date_entered, file=path.name, kept="exit")
                else:
                    log.info("journal.import.collapsed", symbol=symbol,
                             date_entered=date_entered, file=path.name, kept="first")

    for norm in batch.values():
        outcome = upsert_entry(norm)
        summary["inserted" if outcome == "inserted" else "updated"] += 1
        exit_updates = {
            c: norm.get(c) for c in EXIT_COLUMNS if _clean(norm.get(c)) is not None
        }
        if exit_updates and update_exit(norm.get("date_entered"), norm.get("symbol"), exit_updates):
            summary["exit_updates"] += 1
        if str(norm.get("voided") or "0").strip().lower() in {"1", "true", "yes"}:
            if void_trade(
                norm.get("date_entered"), norm.get("symbol"),
                str(norm.get("void_reason") or "voided (imported)"),
            ):
                summary["voided"] += 1

    rej_path = root / "REJECTIONS.csv"
    if rej_path.exists():
        with rej_path.open("r", encoding="utf-8", newline="") as fh:
            for raw in csv.DictReader(fh):
                norm = _norm_row({k: _clean(v) for k, v in raw.items() if k})
                if not norm.get("symbol") or not norm.get("date_seen"):
                    continue
                if insert_rejection(norm):
                    summary["rejections"] += 1

    log.info("journal.import.done", csv_dir=str(root), **summary)
    return summary


def import_legacy_if_needed(csv_dir: Path | str | None = None) -> dict[str, int] | None:
    """First-boot import: only when paper_trades is empty and CSVs exist."""
    with session() as con:
        (count,) = con.execute("SELECT COUNT(*) FROM paper_trades").fetchone()
    if count:
        return None
    root = Path(csv_dir or DEFAULT_CSV_DIR)
    if not root.is_dir():
        return None
    if not any(p.name not in NON_JOURNAL_FILES for p in root.glob("*.csv")):
        return None
    return import_csv_dir(root)


# ── Ops CLI (plan 1.4) ──


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="journal_store", description="Paper journal SQLite store ops (D-68)."
    )
    parser.add_argument("--db", help="Override DB path (default: CONFLU_CORE_PAPER_JOURNAL_PATH)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--import-csv", nargs="?", const=str(DEFAULT_CSV_DIR), metavar="DIR",
        help="Import dated CSVs from DIR (default: docs/paper_trades)",
    )
    group.add_argument(
        "--export-csv", metavar="PATH",
        help="Write the canonical CSV export to PATH ('-' for stdout)",
    )
    args = parser.parse_args(argv)

    if args.db:
        set_db_path(args.db)

    if args.import_csv:
        summary = import_csv_dir(args.import_csv)
        print(f"Imported from {args.import_csv}: {summary}")
        return 0

    payload = export_csv()
    if args.export_csv == "-":
        sys.stdout.write(payload)
        return 0
    out = Path(args.export_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(payload, encoding="utf-8", newline="")
    print(f"Exported {len(payload.splitlines()) - 1} row(s) to {out}")
    return 0


__all__ = [
    "DEFAULT_DB_PATH",
    "DEFAULT_CSV_DIR",
    "ENTRY_COLUMNS",
    "EXIT_COLUMNS",
    "EXTRA_COLUMNS",
    "get_db_path",
    "set_db_path",
    "reset_db_path",
    "ensure",
    "session",
    "market_today",
    "fetch_rows",
    "upsert_entry",
    "update_exit",
    "set_exclude_from_stats",
    "void_trade",
    "insert_pending_order",
    "list_pending_orders",
    "update_pending_order",
    "insert_rejection",
    "record_run",
    "list_runs",
    "list_rejections",
    "export_csv",
    "import_csv_dir",
    "import_legacy_if_needed",
]


if __name__ == "__main__":
    raise SystemExit(main())
