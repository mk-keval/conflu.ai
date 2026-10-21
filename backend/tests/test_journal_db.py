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

CANONICAL_HEADER = (
    js.ENTRY_COLUMNS + js.EXIT_COLUMNS + js.EXTRA_COLUMNS
    + ["voided", "void_reason"]
)


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


def test_entry_metadata_and_exclusion_roundtrip() -> None:
    """Attribution/time-stop columns persist; the exclusion flag survives re-upsert."""
    js.upsert_entry(_entry(template="trend-pullback", regime="neutral", max_hold_days=30))
    row = js.fetch_rows()[0]
    assert row["template"] == "trend-pullback"
    assert row["regime"] == "neutral"
    assert row["max_hold_days"] == "30"
    assert row["exclude_from_stats"] == "0"

    assert js.set_exclude_from_stats("2026-10-05", "AAPL", True) is True
    assert js.fetch_rows()[0]["exclude_from_stats"] == "1"
    # A same-day re-evaluation must not reset the operational flag.
    assert js.upsert_entry(_entry(entry_price=211.0, max_hold_days=30)) == "updated"
    row = js.fetch_rows()[0]
    assert row["exclude_from_stats"] == "1"
    assert row["max_hold_days"] == "30"


def test_rejection_dedupe() -> None:
    rej = {
        "date_seen": "2026-10-05", "symbol": "TSLA", "conviction": 6,
        "failed_step": "Risk/Reward", "gate_verdict": "FAIL", "reason": "rr too low",
        "template": "trend-pullback", "regime": "neutral",
    }
    assert js.insert_rejection(rej) is True
    assert js.insert_rejection(rej) is False  # INSERT OR IGNORE
    assert js.insert_rejection({"symbol": "TSLA"}) is False  # missing date_seen
    listed = js.list_rejections()
    assert len(listed) == 1 and listed[0]["symbol"] == "TSLA" and listed[0]["conviction"] == 6
    assert listed[0]["template"] == "trend-pullback"
    assert listed[0]["regime"] == "neutral"


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


def test_market_today_is_et_and_run_date_defaults_to_it() -> None:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    expected = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    assert js.market_today() == expected

    js.record_run("sync_exits")  # no explicit run_date
    assert js.list_runs(limit=1)[0]["run_date"] == expected


def test_export_header_asc_order_and_roundtrip(tmp_path: Path) -> None:
    js.upsert_entry(_entry())  # 2026-10-05
    js.update_exit("2026-10-05", "AAPL", {
        "date_closed": "2026-10-09", "exit_price": 219.5, "exit_reason": "target_1",
    })
    js.upsert_entry(_entry(date_entered="2026-10-04", symbol="MSFT"))  # older, open
    js.void_trade("2026-10-04", "MSFT", "phantom test fill")

    payload = js.export_csv()
    parsed = list(csv.reader(io.StringIO(payload)))
    assert parsed[0] == CANONICAL_HEADER
    assert len(parsed) == 3
    # Chronological (diary-like) export order: 2026-10-04 first.
    assert parsed[1][1] == "MSFT" and parsed[2][1] == "AAPL"
    exit_idx = CANONICAL_HEADER.index("exit_price")
    assert parsed[2][exit_idx] == "219.5"
    void_idx = CANONICAL_HEADER.index("voided")
    reason_idx = CANONICAL_HEADER.index("void_reason")
    assert parsed[1][void_idx] == "1"
    assert parsed[1][reason_idx] == "phantom test fill"

    # Round-trip: importing the export back is idempotent (updates, no dupes)
    # and preserves the void audit flag.
    csv_dir = tmp_path / "export"
    csv_dir.mkdir()
    (csv_dir / "export.csv").write_text(payload, encoding="utf-8", newline="")
    summary = js.import_csv_dir(csv_dir)
    assert summary["inserted"] == 0 and summary["updated"] == 2
    assert summary["voided"] == 1
    assert len(js.fetch_rows()) == 2
    aapl = next(r for r in js.fetch_rows() if r["symbol"] == "AAPL")
    assert aapl["date_closed"] == "2026-10-09"
    msft = next(r for r in js.fetch_rows() if r["symbol"] == "MSFT")
    assert msft["voided"] == "1"
    assert msft["void_reason"] == "phantom test fill"


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


# ── Pending orders + voiding (D-73) ──


def _pending(**over: object) -> dict[str, object]:
    row: dict[str, object] = {
        "date_entered": "2026-10-20",
        "symbol": "AAPL",
        "sector": "Technology",
        "entry_low": 100.0,
        "entry_high": 102.0,
        "entry_price": 100.0,
        "stop_loss": 95.0,
        "target_1": 110.0,
        "position_size_pct": 20.0,
        "account_value": 100_000.0,
        "gate_verdict": "PASS",
    }
    row.update(over)
    return row


def test_pending_order_is_unique_per_active_symbol() -> None:
    first = js.insert_pending_order(_pending())
    assert first
    assert js.insert_pending_order(_pending(entry_low=99.0)) is None

    assert js.update_pending_order(first, status="filled", status_date="2026-10-21") is True
    # Guarded transition: a filled order cannot be rewritten.
    assert js.update_pending_order(first, status="filled", status_date="2026-10-22") is False
    # A new order for the same symbol is now allowed.
    assert js.insert_pending_order(_pending(entry_low=99.0))


def test_pending_order_requires_valid_geometry() -> None:
    with pytest.raises(ValueError):
        js.insert_pending_order(_pending(entry_low=94.0))  # limit at/below stop
    with pytest.raises(ValueError):
        js.insert_pending_order(_pending(entry_low=None, entry_price=None))
    with pytest.raises(ValueError):
        js.insert_pending_order(_pending(), order_type="market")


def test_pending_order_status_and_listing() -> None:
    order_id = js.insert_pending_order(_pending())
    assert order_id
    active = js.list_pending_orders("pending")
    assert len(active) == 1
    assert active[0]["symbol"] == "AAPL"
    assert active[0]["limit_price"] == 100.0
    assert active[0]["status"] == "pending"

    js.update_pending_order(
        order_id, status="expired", status_date="2026-10-23",
        status_reason="not filled in 3 session(s)",
    )
    assert js.list_pending_orders("pending") == []
    history = js.list_pending_orders("all")
    assert history[0]["status"] == "expired"
    assert history[0]["status_reason"] == "not filled in 3 session(s)"
    with pytest.raises(ValueError):
        js.update_pending_order(order_id, status="pending", status_date="2026-10-23")


def test_voided_row_is_visible_but_not_open_or_scored() -> None:
    js.upsert_entry(_entry())
    assert js.void_trade("2026-10-05", "AAPL", "phantom fill — price never traded") is True

    row = js.fetch_rows()[0]
    assert row["voided"] == "1"
    assert row["void_reason"] == "phantom fill — price never traded"
    assert row["exclude_from_stats"] == "1"

    from backend.app.domain.workflow import journal as journal_mod
    from backend.app.domain.workflow import verification

    assert journal_mod.read_rows()
    assert journal_mod.read_open_positions() == []
    assert verification.in_forward_sample(row) is False
    # Idempotent and still visible.
    assert js.void_trade("2026-10-05", "AAPL", "again") is True
    assert len(js.fetch_rows()) == 1


def test_pending_reserves_capital_but_is_not_an_open_position() -> None:
    from backend.app.domain.workflow import journal as journal_mod

    js.insert_pending_order(_pending())
    assert journal_mod.read_open_positions() == []
    pending_rows = journal_mod.read_pending_positions()
    assert len(pending_rows) == 1
    assert pending_rows[0]["entry_price"] == 100.0
    assert pending_rows[0]["entry_timing"] == "pending"
    assert journal_mod.available_capital(explicit_account_value=100_000.0) == 80_000.0
