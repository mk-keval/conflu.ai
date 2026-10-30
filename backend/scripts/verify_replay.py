"""Replay ledger integrity check (D-71 v0.1 / H-09 v0.2 — D-78).

This is the pass/fail gate for the replay ledger. It never rebuilds a trade from
market data; it proves that what is stored is internally consistent and that the
replay stayed out of the forward journal.

Checks, against the configured journal DB:

1. **Run identity** — exactly one replay run; every row carries the run's
   ``rules_version`` (v0.2 rows must never appear in a v0.1 run).
2. **Geometry** — stop < entry_low <= entry_high, a limit fill never above the
   entry low, and a target above the planned fill.
3. **Exit legs** — legs sum to 100%, prices/dates are valid, the stored exit
   price is the size-weighted leg price, and the leg R's sum to ``realized_r``.
4. **Dollar P&L** — ``pnl_usd`` / ``pnl_gross_usd`` / ``costs_usd`` equal the
   canonical ``pnl.dollar_pnl`` result (v0.2 rows; v0.1 gaps are warnings).
5. **Sizing** — shares equal fixed-fractional risk (1% PASS / 0.5% CONDITIONAL).
6. **Plan provenance** — v0.2 Plan R is T1 from the planned fill, matches the
   stored ``target_1_r``, respects the family band, and an accepted trade is
   never below the family half-size floor (PASS also clears the full floor).
7. **Funnel** — the stored rows reconcile with the run's funnel and summary.
8. **Forward journal untouched** — no replay row leaked into ``paper_trades``.
9. **Artifact** — optional: both arms were evaluated on the same signal keys,
   the accepted v0.2 arm matches the stored ledger, and the design is frozen.

Exit code 0 = PASS, 1 = FAIL. Warnings do not fail the run.

    python backend/scripts/verify_replay.py
    python backend/scripts/verify_replay.py --artifact docs/backtests/h09_replay_*.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from backend.app.domain.workflow import exit_policy  # noqa: E402
from backend.app.domain.workflow import journal_store  # noqa: E402
from backend.app.domain.workflow import pnl as pnl_mod  # noqa: E402
from backend.app.domain.workflow import replay_store  # noqa: E402
from backend.app.domain.workflow.exits import (  # noqa: E402
    EXIT_STOP,
    EXIT_TARGET_1,
    EXIT_TARGET_2,
    EXIT_TIME,
)

PRICE_TOL = 0.02
R_TOL = 0.02
MONEY_TOL = 0.02
PCT_TOL = 0.05
EOD_REASON = "eod"
EVIDENCE_LABEL = "exploratory_h09_not_evidence"

KNOWN_EXIT_REASONS = {
    EXIT_STOP,
    EXIT_TARGET_1,
    EXIT_TARGET_2,
    EXIT_TIME,
    "trail",
    "scale_out",
    EOD_REASON,
}


def _num(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number


def _key(row: dict[str, Any]) -> str:
    return f"{row.get('symbol')} {row.get('date_entered')}"


def _signal_key(row: dict[str, Any]) -> str:
    return f"{row.get('signal_date')}|{row.get('symbol')}"


# ── Row checks ──────────────────────────────────────────────────────────────


def _verify_row(
    row: dict[str, Any],
    *,
    run_version: str,
    warn: list[str],
    failures: list[str],
) -> None:
    key = _key(row)
    symbol = row.get("symbol")

    def fail(message: str) -> None:
        failures.append(f"{key}: {message}")

    version = row.get("rules_version")
    if run_version == "v0.2":
        if version != "v0.2":
            fail(f"rules_version {version!r} != run version 'v0.2'")
        family = row.get("setup_family")
        if family not in exit_policy.SETUP_FAMILIES:
            fail(f"invalid setup_family {family!r}")
        if row.get("gate_verdict") not in ("PASS", "CONDITIONAL"):
            fail(f"stored row is not accepted (gate {row.get('gate_verdict')!r})")
    elif version not in (None, "", "v0.1"):
        fail(f"rules_version {version!r} in a v0.1 run")

    entry = _num(row.get("entry_price"))
    low = _num(row.get("entry_low"))
    high = _num(row.get("entry_high"))
    stop = _num(row.get("stop_loss"))
    target_1 = _num(row.get("target_1"))
    exit_price = _num(row.get("exit_price"))
    exit_date = str(row.get("exit_date") or "")[:10]
    date_entered = str(row.get("date_entered") or "")[:10]

    if None in (entry, low, high, stop, target_1, exit_price) or not exit_date:
        if run_version == "v0.2":
            fail("missing geometry, target or exit columns")
        else:
            warn.append(f"{key}: legacy row has a geometry/exit gap")
        return

    assert entry is not None and low is not None and high is not None
    assert stop is not None and target_1 is not None and exit_price is not None

    if not (stop < low <= high):
        fail(f"invalid geometry: stop {stop} low {low} high {high}")
    if entry > low + PRICE_TOL:
        fail(f"limit fill {entry} is above the entry low {low}")
    if entry <= stop:
        fail(f"fill {entry} is not above the stop {stop}")
    if target_1 <= low:
        fail(f"target_1 {target_1} is not above the planned fill {low}")
    if exit_date < date_entered:
        fail(f"exit date {exit_date} precedes the fill date {date_entered}")

    reason = str(row.get("exit_reason") or "")
    if reason not in KNOWN_EXIT_REASONS:
        fail(f"unknown exit reason {reason!r}")

    # ── Legs → VWAP → R ──
    raw_legs = row.get("exit_legs")
    legs: list[dict[str, Any]] = []
    if raw_legs:
        try:
            parsed = json.loads(raw_legs)
        except Exception:  # noqa: BLE001 - corrupt legs are a hard failure
            parsed = None
        if isinstance(parsed, list):
            legs = [leg for leg in parsed if isinstance(leg, dict)]
        if not legs:
            fail("exit_legs is not a non-empty JSON list")
    elif run_version == "v0.2":
        fail("missing exit_legs")

    if legs:
        risk = entry - stop
        pcts: list[float] = []
        weighted = 0.0
        leg_r = 0.0
        for index, leg in enumerate(legs):
            price = _num(leg.get("price"))
            size_pct = _num(leg.get("size_pct"))
            leg_date = str(leg.get("date") or "")[:10]
            if price is None or price <= 0:
                fail(f"leg {index} has an invalid price")
                continue
            if size_pct is None or size_pct <= 0:
                fail(f"leg {index} has an invalid size_pct")
                continue
            if leg_date < date_entered:
                fail(f"leg {index} exits before the fill")
            pcts.append(size_pct)
            weighted += price * size_pct
            leg_r += (size_pct / 100.0) * (price - entry) / risk
        total_pct = sum(pcts)
        if abs(total_pct - 100.0) > PCT_TOL:
            fail(f"exit legs sum to {total_pct:.4f}% (expected 100%)")
        if pcts:
            vwap = weighted / total_pct
            if abs(vwap - exit_price) > PRICE_TOL:
                fail(f"exit price {exit_price} != leg VWAP {vwap:.4f}")
            realized_r = _num(row.get("realized_r"))
            if realized_r is not None and abs(leg_r - realized_r) > R_TOL:
                fail(f"leg R {leg_r:.4f} != stored realized_r {realized_r:.4f}")

    # ── Canonical dollar P&L ──
    shares = _num(row.get("shares"))
    money = pnl_mod.dollar_pnl(entry, exit_price, shares)
    if money is None:
        if run_version == "v0.2":
            fail("canonical dollar P&L could not be computed")
    else:
        for column, expected in (
            ("pnl_usd", money["pnl_usd"]),
            ("pnl_gross_usd", money["pnl_gross_usd"]),
            ("costs_usd", money["costs_usd"]),
        ):
            stored = _num(row.get(column))
            if stored is None:
                if run_version == "v0.2":
                    fail(f"{column} is missing")
                else:
                    warn.append(f"{key}: legacy {column} is missing")
                continue
            if abs(stored - expected) > MONEY_TOL:
                message = f"{column} {stored} != canonical {expected}"
                if run_version == "v0.2":
                    fail(message)
                else:
                    warn.append(f"{key}: legacy {message}")

    if run_version != "v0.2" or shares is None:
        return

    # ── Sizing ──
    account = _num(row.get("account_value"))
    risk_pct = _num(row.get("risk_pct"))
    if account is None or risk_pct is None:
        fail("sizing inputs (account_value / risk_pct) are missing")
        return
    if risk_pct not in (0.5, 1.0):
        fail(f"risk_pct {risk_pct} is neither 1.0 nor the 0.5 CONDITIONAL half")
    expected_shares = account * risk_pct / 100.0 / (entry - stop)
    if abs(shares - expected_shares) > max(0.02, expected_shares * 0.001):
        fail(f"shares {shares} != fixed-fractional {expected_shares:.2f}")
    if row.get("gate_verdict") == "PASS" and risk_pct != 1.0:
        fail("PASS row did not take full size")
    if row.get("gate_verdict") == "CONDITIONAL" and risk_pct != 0.5:
        fail("CONDITIONAL row did not take half size")

    # ── Plan provenance and the family band ──
    family = str(row.get("setup_family") or "")
    plan_rr = _num(row.get("plan_rr"))
    target_1_r = _num(row.get("target_1_r"))
    if plan_rr is None or target_1_r is None:
        fail("v0.2 row is missing plan_rr / target_1_r")
        return
    planned_r = (target_1 - low) / (low - stop)
    if abs(target_1_r - planned_r) > R_TOL:
        fail(f"target_1_r {target_1_r} != T1 from planned fill {planned_r:.4f}")
    if abs(plan_rr - target_1_r) > R_TOL:
        fail(f"plan_rr {plan_rr} != target_1_r {target_1_r}")
    if family in exit_policy.SETUP_FAMILIES:
        policy = exit_policy.policy_for(family)
        if plan_rr < policy.half_size_floor_r - R_TOL:
            fail(
                f"accepted Plan R {plan_rr} is below the {family} half-size "
                f"floor {policy.half_size_floor_r}"
            )
        if row.get("gate_verdict") == "PASS" and plan_rr < policy.full_size_floor_r - R_TOL:
            fail(
                f"PASS Plan R {plan_rr} is below the {family} full-size floor "
                f"{policy.full_size_floor_r}"
            )
        if plan_rr > policy.max_t1_r + R_TOL:
            fail(
                f"Plan R {plan_rr} exceeds the {family} band cap {policy.max_t1_r}"
            )
    else:
        fail(f"unknown family {family!r}")


# ── Run / funnel / summary ──────────────────────────────────────────────────


def _verify_run(
    run: dict[str, Any],
    rows: list[dict[str, Any]],
    *,
    failures: list[str],
    warn: list[str],
) -> None:
    version = str(run.get("rules_version") or "")
    if version not in ("v0.1", "v0.2"):
        warn.append(f"run rules_version is {version!r}; treating it as v0.1")
        version = "v0.1"

    window_start = str(run.get("window_start") or "")
    window_end = str(run.get("window_end") or "")
    for row in rows:
        signal_date = str(row.get("signal_date") or "")[:10]
        if signal_date and (signal_date < window_start or signal_date > window_end):
            failures.append(
                f"{_key(row)}: signal {signal_date} is outside the run window "
                f"{window_start}..{window_end}"
            )

    if version != "v0.2":
        return

    metadata = run.get("metadata") or {}
    h09 = metadata.get("h09") or {}
    funnel = h09.get("funnel") or {}
    if not funnel:
        failures.append("v0.2 run is missing the H-09 funnel")
        return
    if h09.get("evidence_label") != EVIDENCE_LABEL:
        failures.append(
            f"evidence_label {h09.get('evidence_label')!r} != {EVIDENCE_LABEL!r}"
        )

    accepted = len(rows)
    eod = sum(1 for row in rows if row.get("exit_reason") == EOD_REASON)
    closed = accepted - eod
    for label, actual, expected in (
        ("funnel.v02_accepted", funnel.get("v02_accepted"), accepted),
        ("funnel.v02_eod", funnel.get("v02_eod"), eod),
        ("funnel.v02_closed", funnel.get("v02_closed"), closed),
    ):
        if actual != expected:
            failures.append(f"{label} is {actual}, ledger has {expected}")

    filled = funnel.get("filled")
    if filled != (
        (funnel.get("v02_rejected") or 0)
        + (funnel.get("v02_gated_out") or 0)
        + (funnel.get("v02_accepted") or 0)
    ):
        failures.append("funnel does not reconcile: filled != rejected + gated + accepted")
    if funnel.get("orders") != (
        (filled or 0)
        + (funnel.get("cancelled_gap") or 0)
        + (funnel.get("expired") or 0)
        + (funnel.get("no_sessions") or 0)
    ):
        failures.append("funnel does not reconcile at the fill stage")

    summary = run.get("summary") or {}
    if (summary.get("all_accepted") or {}).get("trades") != accepted:
        failures.append("summary.all_accepted.trades != stored rows")
    if summary.get("trades") != closed:
        failures.append("summary.trades != stored closed rows")
    if summary.get("censored_excluded") != eod:
        failures.append("summary.censored_excluded != eod rows")
    arms = summary.get("arms") or {}
    if (arms.get("v02_accepted") or {}).get("trades") != accepted:
        failures.append("summary.arms.v02_accepted.trades != stored rows")

    design = h09.get("design") or {}
    if design.get("deviations"):
        failures.append(
            "frozen-design deviation(s) in a written run: "
            + ", ".join(design["deviations"])
        )
    horizon = metadata.get("data_horizon") or {}
    consent = metadata.get("write_consent") or {}
    if not horizon.get("ok") and not consent.get("allow_censored"):
        failures.append(
            "run was written before the 36-day data horizon without "
            "write_consent.allow_censored"
        )


# ── Artifact checks ─────────────────────────────────────────────────────────


def _verify_artifact(
    path: Path,
    run: dict[str, Any],
    rows: list[dict[str, Any]],
    *,
    failures: list[str],
) -> None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        failures.append(f"artifact {path} could not be read: {exc}")
        return

    artifact_run = data.get("run") or {}
    if artifact_run.get("generated_at") != run.get("generated_at"):
        failures.append("artifact run does not match the stored run (generated_at)")
    if artifact_run.get("rules_version") != run.get("rules_version"):
        failures.append("artifact rules_version does not match the stored run")
    if (artifact_run.get("metadata") or {}).get("h09") != (run.get("metadata") or {}).get("h09"):
        # The CLI may add write consent to the DB copy after the artifact is
        # written; only the H-09 block itself must match.
        failures.append("artifact H-09 metadata does not match the stored run")

    arms = data.get("arms") or {}
    if run.get("rules_version") != "v0.2":
        return
    for name in ("v01", "v02", "v02_stem"):
        if name not in arms:
            failures.append(f"artifact is missing the {name} arm")

    def keys(name: str) -> set[str]:
        return {
            str(row.get("signal_key"))
            for row in arms.get(name) or []
            if row.get("signal_key")
        }

    if keys("v01") != keys("v02"):
        failures.append("v0.1 and v0.2 arms were evaluated on different signal sets")

    v02 = arms.get("v02") or []
    accepted = {
        str(row.get("signal_key"))
        for row in v02
        if row.get("accepted") and row.get("has_exit")
    }
    stored = {_signal_key(row) for row in rows}
    if accepted != stored:
        missing = sorted(accepted - stored)[:3]
        extra = sorted(stored - accepted)[:3]
        failures.append(
            f"artifact accepted v0.2 rows != ledger (missing={missing}, extra={extra})"
        )

    by_key = {str(row.get("signal_key")): row for row in v02}
    for row in rows:
        key = _signal_key(row)
        source = by_key.get(key)
        if source is None:
            continue
        for column in ("realized_r", "entry_price", "exit_price", "stop_loss"):
            left = _num(source.get(column))
            right = _num(row.get(column))
            if left is None or right is None or abs(left - right) > R_TOL:
                failures.append(
                    f"{_key(row)}: artifact {column} {left} != ledger {right}"
                )


# ── Main ────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", help="Override the journal DB path")
    parser.add_argument("--artifact", help="Optional H-09 JSON artifact to cross-check")
    parser.add_argument(
        "--expected-paper-trades",
        type=int,
        default=None,
        help="Fail unless paper_trades has exactly this many rows",
    )
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    args = parser.parse_args()

    if args.db:
        journal_store.set_db_path(args.db)
    journal_store.ensure()

    payload = replay_store.latest_run()
    failures: list[str] = []
    warn: list[str] = []

    if payload is None:
        failures.append("no replay run found")
        run: dict[str, Any] = {}
        rows: list[dict[str, Any]] = []
    else:
        run = payload.get("run") or {}
        rows = payload.get("rows") or []

    if run:
        _verify_run(run, rows, failures=failures, warn=warn)
        run_version = str(run.get("rules_version") or "v0.1")
        seen: set[str] = set()
        for row in rows:
            key = _signal_key(row)
            if key in seen:
                failures.append(f"{_key(row)}: duplicate signal key {key}")
            seen.add(key)
            _verify_row(row, run_version=run_version, warn=warn, failures=failures)

    if args.artifact:
        _verify_artifact(Path(args.artifact), run, rows, failures=failures)

    with journal_store.session() as con:
        paper_count = int(
            con.execute("SELECT COUNT(*) FROM paper_trades").fetchone()[0]
        )
        leaked = int(
            con.execute(
                "SELECT COUNT(*) FROM paper_trades "
                "WHERE notes LIKE '%H-09%' OR notes LIKE '%SIMULATED REPLAY%'"
            ).fetchone()[0]
        )
    if leaked:
        failures.append(f"{leaked} replay row(s) leaked into paper_trades")
    if (
        args.expected_paper_trades is not None
        and paper_count != args.expected_paper_trades
    ):
        failures.append(
            f"paper_trades has {paper_count} rows, expected "
            f"{args.expected_paper_trades}"
        )

    report = {
        "status": "FAIL" if failures else "PASS",
        "db": str(journal_store.get_db_path()),
        "run": {
            "id": run.get("id"),
            "generated_at": run.get("generated_at"),
            "rules_version": run.get("rules_version"),
            "window_start": run.get("window_start"),
            "window_end": run.get("window_end"),
        },
        "rows": {
            "total": len(rows),
            "closed": sum(1 for row in rows if row.get("exit_reason") != EOD_REASON),
            "eod": sum(1 for row in rows if row.get("exit_reason") == EOD_REASON),
            "paper_trades": paper_count,
        },
        "failures": failures,
        "warnings": warn,
    }

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print(f"Replay verification: {report['status']}")
        print(f"DB: {report['db']}")
        if run:
            print(
                f"Run: {run.get('rules_version')} #{run.get('id')} "
                f"{run.get('window_start')} -> {run.get('window_end')}"
            )
        print(
            f"Rows: {report['rows']['total']} total, "
            f"{report['rows']['closed']} closed, {report['rows']['eod']} eod"
        )
        print(f"paper_trades rows: {paper_count} (replay leakage: {leaked})")
        for message in warn:
            print(f"WARN: {message}")
        for message in failures:
            print(f"FAIL: {message}")
        if not failures:
            print("PASS: replay ledger is consistent and isolated from the forward journal.")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
