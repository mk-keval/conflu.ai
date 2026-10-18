"""SQLite journal store tests (D-68, plan P1.7).

Covers: upsert idempotency + fresh-eval-wins, exit preservation across entry
re-runs, closed-row exit guard, rejection dedupe, run logging, export header/
round-trip, import dedupe (exit-carrying row wins), and first-boot import.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

import pytest

from backend.app.domain.workflow import journal_store as js

CANONICAL_HEADER = js.ENTRY_COLUMNS + js.EXIT_COLUMNS + ["template", "regime", "entry_timing"]


def _entry(**over: object) -> dict[str, object]:
    row: dict[str, object] = {
        "date_entered": "2026-10-05",
        "symbol": "AAPL",
        "sector": "Technology",
        "entry_price": 210.0,
        "stop_loss": 200.0,
        "position_size_pct": 8.0,
        "account_value": 100_000.0,
        "gate_verdict": "PASS",
    }
    row.update(over)
    return row


def test_upsert_insert_then_update_no_dupes() -> None:
    assert js.upsert_entry(_entry()) == "inserted"
    assert js.upsert_entry(_entry(entry_price=211.5)) == "updated"
    rows = js.fetch_rows()
    assert len(rows) == 1
    assert rows[0]["entry_price"] == "211.5"
    # Missing optional cells stay None (legacy blank account_value parity).
    assert js.upsert_entry(_entry(symbol="NVDA", account_value=None)) == "inserted"
    nvda = next(r for r in js.fetch_rows() if r["symbol"] == "NVDA")
    assert nvda["account_value"] is None


def test_upsert_requires_identity() -> None:
    with pytest.raises(ValueError):
        js.upsert_entry({"date_entered": "2026-10-05"})
    with pytest.raises(ValueError):
        js.upsert_entry({"symbol": "AAPL"})


def test_upsert_preserves_exits_after_close() -> None:
    js.upsert_entry(_entry())
    assert js.update_exit("2026-10-05", "AAPL", {
        "date_closed": "2026-10-09", "exit_price": 220.0, "exit_reason": "target_1",
        "realized_r": 1.0, "plan_adherence": 1.0,
    }) is True
    # Same-day re-run: fresh evaluation wins on entry fields, exit untouched.
    assert js.upsert_entry(_entry(entry_price=999.0)) == "updated"
    row = js.fetch_rows()[0]
    assert row["entry_price"] == "999.0"
    assert row["date_closed"] == "2026-10-09"
    assert row["exit_price"] == "220.0"


def test_update_exit_guards() -> None:
    js.upsert_entry(_entry())
    # Non-exit keys are ignored → nothing to update.
    assert js.update_exit("2026-10-05", "AAPL", {"nonsense": 1}) is False
    # Unknown row → False.
    assert js.update_exit("1999-01-01", "ZZZ", {"date_closed": "1999-01-02"}) is False
    assert js.update_exit("2026-10-05", "AAPL", {"date_closed": "2026-10-09"}) is True
    # Already closed → the guard refuses a second write.
    assert js.update_exit("2026-10-05", "AAPL", {"exit_price": 1.0}) is False


def test_rejection_dedupe() -> None:
    rej = {
        "date_seen": "2026-10-05", "symbol": "TSLA", "conviction": 6,
        "failed_step": "Risk/Reward", "gate_verdict": "FAIL", "reason": "rr too low",
    }
    assert js.insert_rejection(rej) is True
    assert js.insert_rejection(rej) is False  # INSERT OR IGNORE
    assert js.insert_rejection({"symbol": "TSLA"}) is False  # missing date_seen
    listed = js.list_rejections()
    assert len(listed) == 1 and listed[0]["symbol"] == "TSLA" and listed[0]["conviction"] == 6


def test_record_run_and_list_runs() -> None:
    rid = js.record_run(
        "enforce", accepted=2, rejected=1, status="ok",
        message="2 accepted, 1 rejected", details={"kept": ["AAPL"]},
    )
    runs = js.list_runs()
    assert runs[0]["id"] == rid
    assert runs[0]["mode"] == "enforce"
    assert runs[0]["accepted"] == 2 and runs[0]["rejected"] == 1
    assert runs[0]["apply"] == 0
    assert '"kept"' in runs[0]["details_json"]


def test_export_header_asc_order_and_roundtrip(tmp_path: Path) -> None:
    js.upsert_entry(_entry())  # 2026-10-05
    js.update_exit("2026-10-05", "AAPL", {
        "date_closed": "2026-10-09", "exit_price": 219.5, "exit_reason": "target_1",
    })
    js.upsert_entry(_entry(date_entered="2026-10-04", symbol="MSFT"))  # older, open

    payload = js.export_csv()
    parsed = list(csv.reader(io.StringIO(payload)))
    assert parsed[0] == CANONICAL_HEADER
    assert len(parsed) == 3
    # Chronological (diary-like) export order: 2026-10-04 first.
    assert parsed[1][1] == "MSFT" and parsed[2][1] == "AAPL"
    exit_idx = CANONICAL_HEADER.index("exit_price")
    assert parsed[2][exit_idx] == "219.5"

    # Round-trip: importing the export back is idempotent (updates, no dupes).
    csv_dir = tmp_path / "export"
    csv_dir.mkdir()
    (csv_dir / "export.csv").write_text(payload, encoding="utf-8", newline="")
    summary = js.import_csv_dir(csv_dir)
    assert summary["inserted"] == 0 and summary["updated"] == 2
    assert len(js.fetch_rows()) == 2
    aapl = next(r for r in js.fetch_rows() if r["symbol"] == "AAPL")
    assert aapl["date_closed"] == "2026-10-09"


def test_import_dedupe_prefers_exit_carrying_row(tmp_path: Path) -> None:
    d = tmp_path / "dups"
    d.mkdir()
    header = js.ENTRY_COLUMNS + js.EXIT_COLUMNS
    closed_row = ["2026-01-02", "DUPX"] + [""] * (len(header) - 2)
    closed_row[header.index("date_closed")] = "2026-01-05"
    closed_row[header.index("exit_price")] = "12.34"
    js_headers = [header, header]
    for name, row in (("2026-01-02.csv", ["2026-01-02", "DUPX"] + [""] * (len(header) - 2)),
                      ("2026-01-03.csv", closed_row)):
        with (d / name).open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(js_headers[0])
            w.writerow(row)

    js.set_db_path(tmp_path / "dups.db")
    summary = js.import_csv_dir(d)
    assert summary["collapsed"] == 1
    assert summary["inserted"] == 1
    assert summary["exit_updates"] == 1
    row = js.fetch_rows()[0]
    assert row["date_closed"] == "2026-01-05" and row["exit_price"] == "12.34"


def test_import_legacy_if_needed(tmp_path: Path) -> None:
    d = tmp_path / "legacy"
    d.mkdir()
    header = js.ENTRY_COLUMNS + js.EXIT_COLUMNS
    with (d / "2026-09-01.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerow(["2026-09-01", "OLD"] + [""] * (len(header) - 2))
    with (d / "TEMPLATE.csv").open("w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerow(header)

    js.set_db_path(tmp_path / "boot.db")
    summary = js.import_legacy_if_needed(d)
    assert summary is not None and summary["inserted"] == 1
    # Non-empty journal → no-op.
    assert js.import_legacy_if_needed(d) is None
    # Missing dir / header-only dir → no-op on an empty journal.
    js.set_db_path(tmp_path / "boot2.db")
    assert js.import_legacy_if_needed(tmp_path / "nope") is None
    only_template = tmp_path / "only_template"
    only_template.mkdir()
    (only_template / "TEMPLATE.csv").write_text(",".join(header) + "\n", encoding="utf-8")
    assert js.import_legacy_if_needed(only_template) is None


def test_ensure_autoimports_configured_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """First boot of the configured DB imports legacy CSVs (plan P1.1)."""
    d = tmp_path / "legacy"
    d.mkdir()
    header = js.ENTRY_COLUMNS + js.EXIT_COLUMNS
    with (d / "2026-09-01.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerow(["2026-09-01", "OLD"] + [""] * (len(header) - 2))

    js.set_db_path(tmp_path / "auto.db")
    monkeypatch.setattr(js, "_explicit_override", False)  # pretend: configured DB
    monkeypatch.setattr(js, "DEFAULT_CSV_DIR", d)
    js.ensure()
    rows = js.fetch_rows()
    assert len(rows) == 1 and rows[0]["symbol"] == "OLD"
