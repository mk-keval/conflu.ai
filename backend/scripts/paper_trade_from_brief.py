"""Generate today's paper-trade CSV from the Morning Brief (same data as the UI).

This script is the source of truth for paper trade entries. It:
  1. Calls GET /api/v1/professional/morning-brief (same as the UI Morning Brief page)
  2. Pulls the curated ticker list (Trend Follower + High-Conviction Stack + Sector Rotation)
  3. For each ticker you select, fetches the live verdict via /api/v1/ticker/{sym}/analyze
  4. ENFORCES the workflow gate (plan Sec.1D):
       - reuses the verdict's attached gate (steps 1-5,7 — computed backend-side
         with tv_data, which never leaves the server),
       - re-evaluates ONLY Step 6 (Portfolio Fit) against the paper journal's
         real open book (gate.build_gate_input + evaluate_portfolio_fit),
       - recomputes the overall verdict with compute_gate.
      PASS     → full-size entry row written (entry_type=initial)
      CONDITIONAL → half-size row (sizing halves), gate_verdict + first
                    conditional gate_failed_step recorded
      FAIL     → rejection written to the journal DB, no trade
        A blank/absent stop_loss always REJECTS the symbol (never a blank stop).
  5. Queues accepted rows as pending orders in the journal DB (fill T+1,
     never the signal day)

Touchpoint A (Pre-market ~10 min):
  python backend/scripts/paper_trade_from_brief.py                    # dry-run (default)
  python backend/scripts/paper_trade_from_brief.py --apply            # persist CSV writes

Touchpoint B (After-close ~2 min):
  python backend/scripts/paper_trade_from_brief.py --sync-exits --dry-run  # review fills
  python backend/scripts/paper_trade_from_brief.py --sync-exits --apply    # apply + set plan_adherence

One-go after close (recommended, P3):
  python backend/scripts/paper_trade_from_brief.py --run-close   # enforce (implies --apply) + exits applied

--dry-run is the DEFAULT (nothing is written or fetched for OHLCV/sync-exits
unless --apply is supplied); pass --apply to actually persist.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Literal

import requests

# Make `backend.app.*` importable when run as `python backend/scripts/paper_trade_from_brief.py`
# (repo root is parents[2]; mirror of daily_morning_ritual.py bootstrap).
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Import the ticker_analysis package FIRST: its __init__ eagerly imports
# synthesis → workflow.gate, and gate re-imports ticker_analysis.models.
# Importing workflow.gate cold would hit that cycle mid-init (see test_gate.py
# for the same ordering constraint).
import backend.app.domain.ticker_analysis  # noqa: F401

from backend.app.domain.workflow import exits as exits_mod
from backend.app.domain.workflow import exit_policy as exit_policy_mod
from backend.app.domain.workflow import gate as gate_mod
from backend.app.domain.workflow import journal as journal_mod
from backend.app.domain.workflow import pending as pending_mod
from backend.app.domain.workflow import pending_service
from backend.app.domain.workflow import pnl as pnl_mod
from backend.app.domain.workflow import sizing as sizing_mod
from backend.app.domain.ticker_analysis.technical import _fetch_daily_ohlcv

BASE_URL = "http://localhost:8000"
REPO_ROOT = Path(__file__).resolve().parents[2]
CSV_DIR = REPO_ROOT / "docs" / "paper_trades"  # import/export artifacts (D-68)
GATE_VERSION = "1D-enforcement"


def _fetch_brief(base_url: str) -> dict:
    """GET /api/v1/professional/morning-brief — same as the UI page."""
    r = requests.get(f"{base_url}/api/v1/professional/morning-brief", timeout=60)
    r.raise_for_status()
    return r.json()["data"]


def _fetch_verdict(base_url: str, symbol: str, setup_family: str = "unknown") -> dict:
    """POST /api/v1/ticker/{symbol}/analyze — full verdict with entry/stop/targets.

    ``setup_family`` selects the Bundle A target band and exit policy (D-77);
    the caller derives it from the brief's ``screen_name``.
    """
    r = requests.post(
        f"{base_url}/api/v1/ticker/{symbol}/analyze",
        json={"symbol": symbol, "timeframe": "1D", "setup_family": setup_family},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["data"]


_OVERALL_LITERALS = ("PASS", "FAIL", "CONDITIONAL")


def _normalize_overall(raw: object) -> Literal["PASS", "FAIL", "CONDITIONAL"]:
    """Coerce a serialized overall verdict to one of PASS/FAIL/CONDITIONAL."""
    text = str(raw or "").strip().upper()
    if text in _OVERALL_LITERALS:
        return text  # type: ignore[return-value]
    return "CONDITIONAL"  # unknown/missing serialized value — honest middle ground


def _attached_gate(verdict: dict) -> gate_mod.GateResult | None:
    """Rehydrate the backend-computed gate from the serialized verdict.

    The /analyze response serializes the full GateResult (steps 1-5,7 were
    evaluated with tv_data that never leaves the server). Returns None when
    the verdict carries no gate — the caller then treats the symbol as
    CONDITIONAL (data gap), never PASS.
    """
    gate_dict = (verdict.get("verdict") or {}).get("gate")
    if not isinstance(gate_dict, dict):
        return None
    try:
        steps = [
            gate_mod.GateStepResult(
                name=s["name"], passed=bool(s["passed"]),
                conditional=bool(s.get("conditional", False)),
                note=str(s.get("note", "")),
            )
            for s in gate_dict.get("steps", [])
        ]
        if not steps:
            return None
        return gate_mod.GateResult(
            overall=_normalize_overall(gate_dict.get("overall", "CONDITIONAL")),
            steps=steps,
            conviction_score=int(gate_dict.get("conviction_score", 0)),
            data_gaps=[g for g in gate_dict.get("data_gaps", []) if isinstance(g, str)],
            evaluated_at=str(gate_dict.get("evaluated_at", "")),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _reevaluate_portfolio_fit(
    attached: gate_mod.GateResult,
    *,
    symbol: str,
    stop_loss: float | None,
    sector: str,
    position_size_pct: float | None,
) -> tuple[list[gate_mod.GateStepResult], str]:
    """Swap Step 6 with a journal-aware evaluation and recompute the overall.

    Steps 1-5,7 come from the backend verdict untouched. Step 6 runs the real
    gate.evaluate_portfolio_fit against journal.read_open_positions() (count
    cap, duplicate symbol, sector exposure). Returns (steps, overall).

    A journal with ZERO open rows is a *verified* clear book (the reader found
    no open positions) — Step 6 PASSES, unlike the synthesis path where
    ``open_positions`` is absent and the gate honestly reports CONDITIONAL.
    """
    steps = list(attached.steps)
    open_positions = (
        journal_mod.read_open_positions()
        + journal_mod.read_pending_positions()
    )
    if not open_positions:
        journal_step = gate_mod.GateStepResult(
            name="Portfolio Fit", passed=True,
            note="No open positions or pending orders in the paper journal — book is verified clear; no count/sector conflicts.",
        )
    else:
        journal_step = gate_mod.evaluate_portfolio_fit(
            gate_mod.build_gate_input(
                symbol=symbol,
                stop_loss=stop_loss,
                sector=sector,
                entry_type="initial",
                position_size_pct=position_size_pct,
                open_positions=open_positions,
            )
        )
    replaced = False
    for i, s in enumerate(steps):
        if s.name == "Portfolio Fit":
            steps[i] = journal_step
            replaced = True
            break
    if not replaced:
        steps.append(journal_step)
    return steps, gate_mod.compute_gate(steps)


def _first_unpassed_step(
    steps: list[gate_mod.GateStepResult],
) -> tuple[str | None, str | None]:
    """(hard-failing step, first-conditional step) for the report columns."""
    hard_fail = next((s.name for s in steps if not s.passed and not s.conditional), None)
    first_conditional = next((s.name for s in steps if s.conditional), None)
    return hard_fail, first_conditional


def _print_gate_table(symbol: str, steps: list[gate_mod.GateStepResult], overall: str) -> None:
    """Print a formatted 7-step gate table for a symbol."""
    step_order = [
        "Liquidity", "Structure", "Positioning", "Catalyst",
        "Risk/Reward", "Portfolio Fit", "Conviction"
    ]
    
    # Map step results by name for quick lookup
    step_map = {s.name: s for s in steps}
    
    print(f"\n  ┌─ Gate: {symbol} ──────────────────────────────────────────┐")
    print(f"  │ Step              │ Status       │ Note                                          │")
    print(f"  ├───────────────────┼──────────────┼──────────────────────────────────────────────┤")
    
    for step_name in step_order:
        step = step_map.get(step_name)
        if step:
            if step.passed and not step.conditional:
                status = "✓ PASS"
            elif step.conditional:
                status = "⚠ COND"
            else:
                status = "✗ FAIL"
            note = step.note[:50] + ("..." if len(step.note) > 50 else "")
        else:
            status = "? MISSING"
            note = "Step not evaluated"
        
        print(f"  │ {step_name:<17} │ {status:<12} │ {note:<50} │")
    
    overall_icon = "✓" if overall == "PASS" else "⚠" if overall == "CONDITIONAL" else "✗"
    print(f"  ├───────────────────┼──────────────┼──────────────────────────────────────────────┤")
    print(f"  │ {'OVERALL':<17} │ {overall_icon} {overall:<10} │ {'All steps green → PASS; any ⚠ → CONDITIONAL; any ✗ → FAIL':<50} │")
    print(f"  └───────────────────┴──────────────┴──────────────────────────────────────────────┘")


def build_row(
    symbol: str,
    brief_section: dict,
    verdict: dict,
    market_regime: str = "",
) -> tuple[dict | None, dict | None]:
    """Build a CSV row (or a rejection row) under gate enforcement.

    Returns (trade_row | None, rejection_row | None). Exactly one is set:
    - PASS        → trade_row with full size, entry_type=initial
    - CONDITIONAL → trade_row with half size (sizing halves), gate columns set
    - FAIL        → rejection_row written to the journal DB
    Blank/absent stop_loss → rejection (never write a blank stop).
    """
    v = verdict.get("verdict", {})
    sector = verdict.get("sector") or brief_section.get("sector") or "Unknown"
    template_name = str(brief_section.get("screen_name") or "").strip()
    regime_name = str(market_regime or "").strip()
    # Bundle A (D-77/A3): the brief screen is the family source of truth.
    setup_family = exit_policy_mod.family_for_screen(template_name)
    max_hold_days = (v.get("trade_plan") or {}).get("max_hold_days")
    if max_hold_days in (None, ""):
        max_hold_days = exit_policy_mod.policy_for(setup_family).time_stop_days

    def _rejection(step: str, reason: str, notes: str = "") -> dict:
        return {
            "date_seen": journal_mod.market_today(),
            "symbol": symbol, "sector": sector,
            "action": brief_section.get("verdict") or v.get("action", ""),
            "conviction": v.get("conviction") or brief_section.get("conviction", ""),
            "failed_step": step, "gate_verdict": "FAIL",
            "reason": reason, "notes": notes,
            "template": template_name, "regime": regime_name,
        }

    # Entry zone
    entry_lo = v.get("entry_zone_low") or verdict.get("price") or 0
    entry_hi = v.get("entry_zone_high") or entry_lo
    entry = round((entry_lo + entry_hi) / 2, 2) if entry_lo and entry_hi else 0
    stop = v.get("stop_loss")

    # ── Hard rejection: no stop / degenerate entry geometry ──
    if not entry or entry <= 0:
        return None, _rejection(
            "entry", "No valid entry price from the verdict.",
            f"entry_lo={entry_lo!r} entry_hi={entry_hi!r} price={verdict.get('price')!r}",
        )
    if not stop:
        return None, _rejection(
            "stop_loss",
            "Verdict has no stop loss — a paper trade without an invalidation is not a plan.",
            f"entry={entry} targets={v.get('targets') or []}",
        )

    # ── Gate enforcement ──
    # D-77/A4: a rejected plan has no structural target in the family band.
    plan_rejection = str(v.get("plan_rejection") or "").strip()
    if plan_rejection:
        return None, _rejection(
            "plan",
            f"Plan rejected ({setup_family}): {plan_rejection}",
            f"entry={entry_lo} stop={stop} targets={v.get('targets') or []}",
        )

    attached = _attached_gate(verdict)
    if attached is None:
        # No gate on the verdict — honest CONDITIONAL, never PASS.
        overall = "CONDITIONAL"
        steps: list[gate_mod.GateStepResult] = []
        failed_step, conditional_step = None, "gate"
    else:
        # Size needed for the sector-exposure check; ValueError → reject.
        try:
            size_pct = sizing_mod.compute_position_size_pct(entry, stop, None)
        except ValueError as e:
            return None, _rejection(
                "sizing", f"Sizing rejected the setup: {e}",
                f"entry={entry} stop={stop}",
            )

        steps, overall = _reevaluate_portfolio_fit(
            attached, symbol=symbol, stop_loss=stop,
            sector=sector, position_size_pct=size_pct,
        )
        failed_step, conditional_step = _first_unpassed_step(steps)

    # CONDITIONAL → size halves (sizing applies CONDITIONAL_HALVING).
    try:
        size = sizing_mod.compute_position_size_pct(entry, stop, overall)
    except ValueError as e:
        return None, _rejection(
            "sizing", f"Sizing rejected the setup: {e}",
            f"entry={entry} stop={stop}",
        )

    if overall == "FAIL":
        failed = failed_step or "gate"
        reason = next((s.note for s in steps if not s.passed and not s.conditional), "Gate failed.")
        return None, _rejection(
            failed, reason[:250], f"entry={entry} stop={stop} size_pct={size}",
        )

    # ── Accepted row (PASS or CONDITIONAL) ──
    targets = v.get("targets") or []
    t1 = round(targets[0], 2) if len(targets) >= 1 else ""
    t2 = round(targets[1], 2) if len(targets) >= 2 else ""
    t3 = round(targets[2], 2) if len(targets) >= 3 else ""
    metrics = pnl_mod.plan_metrics(
        entry_lo, entry_hi, stop, targets, basis="planned_fill",
    ) or {}

    account_value = journal_mod.available_capital()  # journal-recorded value or $100k default
    shares = round((size / 100.0 * account_value) / entry, 2) if entry else ""

    confluence_raw = brief_section.get("confluence_score", 0)
    confluence_norm = round((confluence_raw or 0) / 20) if confluence_raw else 0  # 0-100 → 0-5

    triggers = v.get("buy_triggers") or []
    red_flags = v.get("key_red_flags") or []
    signal = ";".join(triggers[:2]) if triggers else template_name
    notes_parts = []
    if triggers:
        notes_parts.append("Triggers: " + "; ".join(triggers[:2]))
    if red_flags:
        notes_parts.append("⚠️ " + "; ".join(red_flags[:1]))
    if confluence_raw:
        notes_parts.append(f"raw confluence {confluence_raw}/100")  # R7: keep the raw 0-100
    if overall == "CONDITIONAL" and conditional_step:
        notes_parts.append(f"conditional on {conditional_step}")
    notes = " | ".join(notes_parts)

    trade_row = {
        "date_entered": journal_mod.market_today(),
        "symbol": symbol,
        "sector": sector,
        "action": brief_section.get("verdict") or v.get("action", "ACCUMULATE"),
        "entry_type": "initial",
        "entry_price": entry,
        "stop_loss": stop,
        "target_1": t1,
        "target_2": t2,
        "target_3": t3,
        "plan_rr": metrics.get("plan_rr"),
        "target_1_r": metrics.get("target_1_r"),
        "stretch_rr": metrics.get("stretch_rr"),
        "setup_family": setup_family,
        "atr_at_entry": (v.get("trade_plan") or {}).get("atr_at_entry"),
        "position_size_pct": size,
        "account_value": round(account_value, 2),
        "shares": shares,
        "confluence_count": confluence_norm,
        "signal_at_entry": signal[:200],
        "gate_verdict": overall,
        "gate_failed_step": conditional_step if overall == "CONDITIONAL" else "",
        "entry_low": entry_lo,
        "entry_high": entry_hi,
        "risk_reward_planned": v.get("risk_reward") or "",
        "gate_version": GATE_VERSION,
        "notes": notes[:500],
        "template": template_name,
        "regime": regime_name,
        "max_hold_days": max_hold_days,
    }
    return trade_row, None


def sync_exits(trades_dir: Path, apply: bool, *, log_run: bool = True) -> dict:
    """Backfill exit data on open journal rows (plan Sec.2E) via infer_exit.

    For each open row: fetch daily OHLCV from the entry date, run
    exits.infer_exit with the row's entry/stop/targets, and (when --apply)
    write date_closed / exit_price / exit_reason / realized_r / pnl_usd /
    mfe_r / mae_r / plan_adherence back into the journal DB (D-68).
    Dry-run by default (shows what would be applied).

    Returns a summary dict ``{"updated", "skipped", "message"}`` — used by
    --run-close to write one combined run row; ``log_run=False`` suppresses
    this function's own workflow_runs row.

    Touchpoint B (After-close ~2 min):
      --sync-exits --dry-run  → review fills
      --sync-exits --apply    → apply + set plan_adherence
    """
    open_rows = journal_mod.read_open_positions(trades_dir)
    if not open_rows:
        message = "No open journal rows to sync."
        print(message)
        if log_run:
            journal_mod.record_run(
                "sync_exits", apply=apply, updated=0, skipped=0,
                message=message, details={"applied": [], "skipped": []},
            )
        return {"updated": 0, "skipped": 0, "message": message}

    run_date = journal_mod.market_today()
    updated = 0
    skipped = 0
    for row in open_rows:
        symbol = str(row.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        # Same-day guard (P2.3): entries are stamped at the close — today's
        # rows cannot have a real exit yet.
        if str(row.get("date_entered") or "")[:10] >= run_date:
            print(f"  - {symbol}: entered today — exits start next session")
            skipped += 1
            continue
        entry = journal_mod._as_float(row.get("entry_price"))
        stop = journal_mod._as_float(row.get("stop_loss"))
        if not entry or not stop or stop >= entry:
            skipped += 1
            continue
        family = exit_policy_mod.normalize_family(row.get("setup_family"))
        targets = [
            t for t in (
                journal_mod._as_float(row.get("target_1")),
                journal_mod._as_float(row.get("target_2")),
                journal_mod._as_float(row.get("target_3")),
            ) if t is not None
        ]
        max_hold = journal_mod._as_int(row.get("max_hold_days"))
        shares = journal_mod._as_float(row.get("shares"))
        if not shares:
            account_value = journal_mod._as_float(row.get("account_value"))
            size_pct = journal_mod.position_size_pct(row)
            if account_value and size_pct:
                shares = account_value * size_pct / 100.0 / entry

        df = _fetch_daily_ohlcv(symbol)
        if df is None or df.empty:
            print(f"  - {symbol}: no OHLCV")
            skipped += 1
            continue
        bars = []
        for _, b in df.reset_index().iterrows():
            d = str(b.get("Date") or b.get("Datetime") or "")[:10]
            if d < str(row.get("date_entered") or "")[:10]:
                continue
            bars.append({
                "date": d,
                "open": b["Open"], "high": b["High"],
                "low": b["Low"], "close": b["Close"],
            })

        if family is not None:
            # Bundle A (D-77): family tranches, breakeven, ATR trail, time stop.
            sim = exit_policy_mod.simulate_exit(
                bars, entry=entry, stop=stop, targets=targets, family=family,
                shares=shares, atr=journal_mod._as_float(row.get("atr_at_entry")),
                entry_date=row.get("date_entered"), max_hold_days=max_hold,
            )
            if sim.exit_price is None or not sim.exit_date:
                skipped += 1
                continue
            updates = sim.as_exit_columns(entry=entry, stop=stop, shares=shares)
            if not updates:
                skipped += 1
                continue
            print(
                f"  {symbol}: {updates['date_closed']} {updates['exit_reason']} "
                f"@ {updates['exit_price']:.2f} (R {updates['realized_r']:+.2f}) "
                f"[plan_adherence={updates['plan_adherence']:.0%}] "
                f"[{family}, {len(sim.legs)} leg(s)]"
                f"{' [dry-run]' if not apply else ''}"
            )
        else:
            # v0.1 rows: legacy single-exit walker (never re-simulated).
            max_hold_bars = exits_mod.hold_limit_bars(
                bars, row.get("date_entered"), max_hold,
            )
            fill = exits_mod.infer_exit(
                bars, entry=entry, stop=stop,
                targets=targets, max_hold_days=max_hold_bars,
                # The fill bar is in the past: EOD rows filled at that close;
                # limit/MOO rows filled intraday and already had their same-session
                # stop checked at fill time (D-73). Counting that bar here would
                # reintroduce look-ahead.
                exclude_entry_bar_excursions=True,
            )
            if not fill.exit_price or not fill.exit_date:
                skipped += 1
                continue
            realized_r = (fill.exit_price - entry) / (entry - stop)
            money = pnl_mod.dollar_pnl(entry, fill.exit_price, shares) or {}
            # Plan adherence = 1.0 if exit reason matches a planned target/stop,
            # else 0.5 for time_stop.
            plan_adherence = 1.0 if fill.exit_reason in (
                exits_mod.EXIT_STOP, exits_mod.EXIT_TARGET_1, exits_mod.EXIT_TARGET_2,
            ) else 0.5
            updates = {
                "date_closed": fill.exit_date,
                "exit_price": round(fill.exit_price, 2),
                "exit_reason": fill.exit_reason,
                "realized_r": round(realized_r, 2),
                "pnl_usd": money.get("pnl_usd"),
                "pnl_gross_usd": money.get("pnl_gross_usd"),
                "costs_usd": money.get("costs_usd"),
                "mfe_r": fill.mfe_r,
                "mae_r": fill.mae_r,
                "plan_adherence": plan_adherence,
            }
            print(
                f"  {symbol}: {fill.exit_date} {fill.exit_reason} "
                f"@ {fill.exit_price:.2f} (R {realized_r:+.2f}) "
                f"[plan_adherence={plan_adherence:.0%}]"
                f"{' [dry-run]' if not apply else ''}"
            )
        if apply:
            if not journal_mod.update_exit(row.get("date_entered"), row.get("symbol"), updates):
                print(f"  - {symbol}: row already closed — skipped")
                skipped += 1
                continue
        updated += 1

    message = (f"{updated} exit(s) {'applied' if apply else 'would be applied'} "
               f"({skipped} skipped: no OHLCV / no valid geometry / exit not reached).")
    print(f"\n{message}")
    if not apply and updated > 0:
        print("  Re-run with --apply to persist exits and set plan_adherence.")
    # Run log (P2.5): every touchpoint leaves a workflow_runs row.
    if log_run:
        journal_mod.record_run(
            "sync_exits", apply=apply, updated=updated, skipped=skipped,
            message=message, details={"applied": [], "skipped": []},
        )
    return {"updated": updated, "skipped": skipped, "message": message}


def main() -> int:
    # Force UTF-8 stdout so emoji (✓, ⚠️, 💾) don't crash on Windows cp1252 consoles.
    # On *nix this is a no-op; on Windows it converts un-encodable chars to '?'.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            # Non-reconfigurable stream (e.g. piped/redirected) — fall back silently
            pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="Comma-separated symbols (default: all from brief)")
    ap.add_argument("--min-conviction", type=int, default=5, help="Min conviction 1-10 (default 5)")
    ap.add_argument("--base-url", default=BASE_URL)
    ap.add_argument("--apply", action="store_true",
                    help="Persist CSV writes (default is a dry run)")
    ap.add_argument("--sync-exits", action="store_true",
                    help="Backfill exits on open journal rows (2E), then exit")
    ap.add_argument("--fill-pending", action="store_true",
                    help="Process eligible pending orders from actual bars, then exit")
    ap.add_argument("--run-close", action="store_true",
                    help="One-go after-close run: fill pending, enforce (implies --apply), sync exits")
    ap.add_argument("--order-type", choices=pending_mod.ORDER_TYPES, default=pending_mod.ORDER_LIMIT,
                    help="Entry order type for new signals (default: limit at entry_low)")
    ap.add_argument("--expiry-sessions", type=int, default=pending_mod.DEFAULT_EXPIRY_SESSIONS,
                    help="Sessions an unfilled order stays active (default: 3)")
    args = ap.parse_args()

    trades_dir = CSV_DIR

    if args.run_close:
        args.apply = True  # --run-close implies --apply

    if args.sync_exits and not args.run_close:
        sync_exits(trades_dir, apply=args.apply)
        return 0

    if args.fill_pending and not args.run_close:
        results = pending_service.process_pending_orders(
            today=journal_mod.market_today(), bars_provider=_fetch_daily_ohlcv,
        )
        fills = [r for r in results if r.status == pending_mod.FILLED]
        closed = [r for r in results if r.status in (pending_mod.EXPIRED, pending_mod.CANCELLED)]
        for r in fills:
            print(f"  ✓ {r.symbol}: filled {r.fill_date} @ {r.fill_price:.2f}"
                  f"{' (same-session stop)' if r.same_day_stop else ''}")
        for r in closed:
            print(f"  - {r.symbol}: {r.status} — {r.note}")
        print(f"\n{len(fills)} fill(s), {len(closed)} order(s) closed, "
              f"{sum(1 for r in results if r.status == pending_mod.PENDING)} still pending")
        return 0

    base_url = args.base_url

    # Actual next-session fills happen before today's signals are evaluated.
    pending_fills: list = []
    if args.apply:
        results = pending_service.process_pending_orders(
            today=journal_mod.market_today(), bars_provider=_fetch_daily_ohlcv,
        )
        pending_fills = [r for r in results if r.status == pending_mod.FILLED]
        closed_orders = [
            r for r in results
            if r.status in (pending_mod.EXPIRED, pending_mod.CANCELLED)
        ]
        for r in pending_fills:
            print(f"  ✓ {r.symbol}: filled {r.fill_date} @ {r.fill_price:.2f}"
                  f"{' (same-session stop)' if r.same_day_stop else ''}")
        for r in closed_orders:
            print(f"  - {r.symbol}: {r.status} — {r.note}")

    print(f"Fetching morning brief from {base_url}...")
    brief = _fetch_brief(base_url)
    print(f"  Regime: {brief['regime']} — {brief['regime_description']}")
    print(f"  Sections: {len(brief['screen_sections'])}")

    # Collect candidates
    candidates: list[tuple[str, dict]] = []  # (symbol, brief_section)
    for section in brief["screen_sections"]:
        screen_name = section["screen_name"]
        for t in section["tickers"]:
            if t.get("conviction", 0) < args.min_conviction:
                continue
            candidates.append((t["symbol"], t))

    if args.only:
        wanted = {s.strip().upper() for s in args.only.split(",")}
        candidates = [(s, t) for s, t in candidates if s in wanted]
        if not candidates:
            print(f"ERROR: none of {args.only} found in morning brief", file=sys.stderr)
            return 1

    print(f"\n{len(candidates)} candidates match filter (min_conviction={args.min_conviction}):")
    for sym, t in candidates:
        print(f"  {sym:<7} conviction={t.get('conviction'):>2}  verdict={t.get('verdict'):<14}  "
              f"screen={t.get('screen_name')}")

    if not candidates:
        if args.run_close:
            # No new entries — still honor the exit half of the combined run.
            print("\nNo candidates matched the filter — running exits sync only.")
            summary = sync_exits(trades_dir, apply=True, log_run=False)
            journal_mod.record_run(
                "run_close", apply=True, accepted=0, rejected=0,
                updated=summary["updated"], skipped=summary["skipped"],
                message=f"No candidates matched the filter | {summary['message']}",
                details={
                    "enforce": {
                        "accepted": [],
                        "filled": [
                            {
                                "symbol": r.symbol, "date": r.fill_date,
                                "price": r.fill_price, "same_day_stop": r.same_day_stop,
                            }
                            for r in pending_fills
                        ],
                        "rejected": [],
                    },
                    "exits": {"updated": summary["updated"], "skipped": summary["skipped"]},
                },
            )
            return 0
        journal_mod.record_run(
            "enforce", apply=args.apply, accepted=0, rejected=0,
            message="No candidates matched the filter",
            details={"accepted": [], "rejected": []},
        )
        return 0

    # Fetch verdicts + enforce the gate
    trade_rows = []
    rejections = 0
    gate_results: dict[str, tuple[list[gate_mod.GateStepResult], str]] = {}  # symbol -> (steps, overall)
    for sym, brief_t in candidates:
        try:
            family = exit_policy_mod.family_for_screen(brief_t.get("screen_name"))
            verdict = _fetch_verdict(base_url, sym, family)
            trade_row, rejection = build_row(
                sym, brief_t, verdict,
                market_regime=str(brief.get("regime") or ""),
            )
            if rejection is not None:
                rejections += 1
                print(f"  ✗ {sym} REJECTED: {rejection['failed_step']} — {rejection['reason'][:80]}")
                if args.apply:
                    journal_mod.insert_rejection(rejection)
                continue
            if trade_row is None:
                continue  # unreachable by contract (exactly one of the two is set)
            trade_rows.append(trade_row)
            
            # Extract gate steps for table printing
            attached = _attached_gate(verdict)
            if attached:
                size_pct = sizing_mod.compute_position_size_pct(
                    trade_row['entry_price'], trade_row['stop_loss'], None
                )
                steps, overall = _reevaluate_portfolio_fit(
                    attached, symbol=sym, stop_loss=trade_row['stop_loss'],
                    sector=trade_row['sector'], position_size_pct=size_pct,
                )
                gate_results[sym] = (steps, overall)
            
            print(f"  ✓ {sym} [{trade_row['gate_verdict']}] → entry={trade_row['entry_price']}, "
                  f"stop={trade_row['stop_loss']}, size={trade_row['position_size_pct']}%, "
                  f"T1={trade_row['target_1']}, T2={trade_row['target_2']}")
        except Exception as e:
            print(f"  ✗ {sym} failed: {e}", file=sys.stderr)

    # Print 7-step gate tables for all evaluated symbols (Touchpoint A)
    if gate_results:
        print("\n" + "=" * 70)
        print("TOUCHPOINT A — Pre-Market Gate Tables (7 Steps)")
        print("=" * 70)
        for sym, (steps, overall) in gate_results.items():
            _print_gate_table(sym, steps, overall)

    # Check for qualifying setups
    qualifying = [r for r in trade_rows if r['gate_verdict'] in ('PASS', 'CONDITIONAL')]
    if not qualifying:
        print("\n⚠ No qualifying setups today — no symbols passed the gate.")
        print("  (All candidates were rejected or need manual review.)")

    created = 0
    created_symbols: list[str] = []
    if args.apply:
        for trade_row in trade_rows:
            try:
                order_id = pending_service.create_pending_order(
                    trade_row,
                    order_type=args.order_type,
                    expires_after_sessions=args.expiry_sessions,
                )
            except ValueError as exc:
                rejections += 1
                print(f"  ✗ {trade_row['symbol']} order rejected: {exc}", file=sys.stderr)
                continue
            if order_id is None:
                rejections += 1
                print(f"  - {trade_row['symbol']}: an active pending order already exists")
                continue
            created += 1
            created_symbols.append(str(trade_row.get("symbol") or ""))
        run_message = f"{created} pending order(s) created, {rejections} rejected"
        if pending_fills:
            run_message += f", {len(pending_fills)} filled from T+1"
        print(f"\n💾 {created} pending order(s) created ({rejections} rejected)")
    else:
        run_message = (f"[dry-run] {len(trade_rows)} signal(s) accepted, "
                       f"{rejections} rejected — pass --apply to persist as pending orders.")
        print(f"\n[dry-run] {len(trade_rows)} signal(s) accepted, {rejections} rejected — "
              f"pass --apply to persist as pending orders.")

    fills_detail = [
        {
            "symbol": r.symbol, "date": r.fill_date,
            "price": r.fill_price, "same_day_stop": r.same_day_stop,
        }
        for r in pending_fills
    ]

    if args.run_close:
        # One combined run row (P3.3): fills + pending orders + exits together.
        summary = sync_exits(trades_dir, apply=True, log_run=False)
        journal_mod.record_run(
            "run_close", apply=True,
            accepted=created, rejected=rejections,
            updated=summary["updated"], skipped=summary["skipped"],
            message=f"{run_message} | {summary['message']}",
            details={
                "enforce": {
                    "accepted": created_symbols[:50],
                    "filled": fills_detail[:50],
                },
                "exits": {"updated": summary["updated"], "skipped": summary["skipped"]},
            },
        )
        return 0

    # Run log (P2.5): every touchpoint leaves a workflow_runs row.
    journal_mod.record_run(
        "enforce", apply=args.apply,
        accepted=created, rejected=rejections,
        updated=len(pending_fills) if args.apply else None,
        message=run_message,
        details={"accepted": created_symbols[:50], "filled": fills_detail[:50]},
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())