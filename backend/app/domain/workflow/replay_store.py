"""SQLite store for two-month paper-trade replays (D-71).

Deliberately separate from ``paper_trades``:

- The forward journal of record and its expectancy/kill-rule math stay clean
  (a replay must never be counted as forward evidence).
- Replay rows may repeat a symbol on a date across templates, which the live
  table's ``(date_entered, symbol)`` unique key would forbid.
- Replays are disposable: a new run replaces the previous one.

Lives in the same SQLite file as the journal (single-file policy, D-68).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from typing import Any

from backend.app.core.logging import get_logger
from backend.app.domain.workflow import journal_store

log = get_logger("conflu.workflow.replay_store")

_DDL = """
CREATE TABLE IF NOT EXISTS replay_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  generated_at TEXT NOT NULL,
  window_start TEXT NOT NULL,
  window_end TEXT NOT NULL,
  universe_count INTEGER NOT NULL,
  templates_count INTEGER NOT NULL,
  params_json TEXT NOT NULL,
  summary_json TEXT NOT NULL,
  metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS replay_trades (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL,
  signal_date TEXT,
  date_entered TEXT NOT NULL,
  symbol TEXT NOT NULL,
  template TEXT,
  regime TEXT,
  regime_key TEXT,
  screen_rank INTEGER,
  screen_weight REAL,
  direction TEXT,
  entry_price REAL,
  stop_loss REAL,
  target_1 REAL,
  exit_date TEXT,
  exit_price REAL,
  exit_reason TEXT,
  realized_r REAL,
  pnl_usd REAL,
  risk_pct REAL,
  position_size_pct REAL,
  shares REAL,
  account_value REAL,
  hold_bars INTEGER,
  rvol REAL,
  also_signaled_by TEXT,
  notes TEXT,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_replay_trades_run
  ON replay_trades(run_id, date_entered);
"""

_TRADE_COLUMNS = (
    "run_id", "signal_date", "date_entered", "symbol", "template", "regime",
    "regime_key", "screen_rank", "screen_weight", "direction", "entry_price",
    "stop_loss", "target_1", "exit_date", "exit_price", "exit_reason",
    "realized_r", "pnl_usd", "risk_pct", "position_size_pct", "shares",
    "account_value", "hold_bars", "rvol", "also_signaled_by", "notes",
    "created_at",
)


def ensure() -> None:
    """Create replay tables in the journal DB (idempotent)."""
    with journal_store.session() as con:
        con.executescript(_DDL)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def replace_run(run: dict[str, Any], rows: list[dict[str, Any]]) -> int:
    """Store ``run`` + ``rows``, replacing any previous replay. Returns run id."""
    ensure()
    now = _utc_now()
    with journal_store.session() as con:
        con.execute("DELETE FROM replay_trades")
        con.execute("DELETE FROM replay_runs")
        cur = con.execute(
            "INSERT INTO replay_runs (generated_at, window_start, window_end, "
            "universe_count, templates_count, params_json, summary_json, metadata_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(run.get("generated_at") or now),
                str(run.get("window_start") or ""),
                str(run.get("window_end") or ""),
                int(run.get("universe_count") or 0),
                int(run.get("templates_count") or 0),
                _json(run.get("params") or {}),
                _json(run.get("summary") or {}),
                _json(run.get("metadata") or {}),
            ),
        )
        run_id = int(cur.lastrowid or 0)
        records = []
        for row in rows:
            records.append(
                tuple(
                    run_id if column == "run_id" else
                    now if column == "created_at" else
                    row.get(column)
                    for column in _TRADE_COLUMNS
                )
            )
        if records:
            placeholders = ", ".join("?" * len(_TRADE_COLUMNS))
            con.executemany(
                f"INSERT INTO replay_trades ({', '.join(_TRADE_COLUMNS)}) "
                f"VALUES ({placeholders})",
                records,
            )
    log.info("replay.stored", run_id=run_id, rows=len(rows))
    return run_id


def _row_to_trade(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def latest_run() -> dict[str, Any] | None:
    """Latest replay payload: ``{"run": ..., "rows": [...], "summary": ...}``."""
    ensure()
    with journal_store.session() as con:
        run = con.execute(
            "SELECT * FROM replay_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if run is None:
            return None
        trades = con.execute(
            "SELECT * FROM replay_trades WHERE run_id = ? "
            "ORDER BY date_entered DESC, symbol ASC",
            (run["id"],),
        ).fetchall()

    def _loads(raw: str | None) -> Any:
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:  # noqa: BLE001 - corrupt payload stays visible as None
            return None

    payload = {
        "id": run["id"],
        "generated_at": run["generated_at"],
        "window_start": run["window_start"],
        "window_end": run["window_end"],
        "universe_count": run["universe_count"],
        "templates_count": run["templates_count"],
        "params": _loads(run["params_json"]) or {},
        "summary": _loads(run["summary_json"]) or {},
        "metadata": _loads(run["metadata_json"]) or {},
    }
    return {
        "run": payload,
        "rows": [_row_to_trade(row) for row in trades],
        "summary": payload["summary"],
    }


def clear() -> int:
    """Delete all replay rows; returns the number of trades removed."""
    ensure()
    with journal_store.session() as con:
        count = con.execute("SELECT COUNT(*) FROM replay_trades").fetchone()[0]
        con.execute("DELETE FROM replay_trades")
        con.execute("DELETE FROM replay_runs")
    log.info("replay.cleared", rows=int(count))
    return int(count)
