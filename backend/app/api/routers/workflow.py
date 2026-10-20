"""Workflow API router (plan Sec.2B, Sec.2E).

Exposes the paper-trade journal as a read-only API so the frontend can
hydrate its local store from the journal DB (D-68: SQLite is the journal of
record; D7 single source of truth).

Also exposes the enforcement endpoints for the 2-touchpoint daily routine:
- POST /api/v1/workflow/paper-trades/enforce  — Touchpoint A: run gate + write journal
- POST /api/v1/workflow/paper-trades/sync-exits  — Touchpoint B: infer + apply exits
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Literal

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from backend.app.api.schemas import ApiResponse, MetaInfo
from backend.app.core.logging import get_logger

# Import ticker_analysis first to avoid circular import (see paper_trade_from_brief.py)
import backend.app.domain.ticker_analysis  # noqa: F401

from backend.app.domain.workflow import exits as exits_mod
from backend.app.domain.workflow import gate as gate_mod
from backend.app.domain.workflow import journal as journal_mod
from backend.app.domain.workflow import replay_store
from backend.app.domain.workflow import sizing as sizing_mod
from backend.app.domain.workflow import verification as verification_mod
from backend.app.domain.ticker_analysis.technical import _fetch_daily_ohlcv

# Re-export journal functions for the existing endpoints
read_rows = journal_mod.read_rows
read_open_positions = journal_mod.read_open_positions
read_closed_trades = journal_mod.read_closed_trades
sector_exposure = journal_mod.sector_exposure
available_capital = journal_mod.available_capital
DEFAULT_TRADES_DIR = journal_mod.DEFAULT_TRADES_DIR

router = APIRouter(prefix="/workflow", tags=["workflow"])
log = get_logger("conflu.api.workflow")

# Import morning brief service directly (avoid HTTP self-call deadlock)
from backend.app.infrastructure.professional.morning_brief import MorningBriefService

# Reuse the same constants from paper_trade_from_brief.py
GATE_VERSION = "1D-enforcement"

# Singleton service instance (same pattern as professional router)
_morning_brief_service: MorningBriefService | None = None


def _get_morning_brief_service() -> MorningBriefService:
    global _morning_brief_service
    if _morning_brief_service is None:
        _morning_brief_service = MorningBriefService()
    return _morning_brief_service


class JournalRow(BaseModel):
    """Normalized journal row (both D-50 21-col and D-51 29-col schemas)."""
    model_config = {"extra": "allow"}

    date_entered: str | None = None
    symbol: str
    sector: str | None = None
    action: str | None = None
    entry_type: str | None = None
    entry_price: float | None = None
    stop_loss: float | None = None
    target_1: float | None = None
    target_2: float | None = None
    position_size_pct: float | None = None
    account_value: float | None = None
    shares: float | None = None
    confluence_count: int | None = None
    signal_at_entry: str | None = None
    gate_verdict: str | None = None
    gate_failed_step: str | None = None
    entry_low: float | None = None
    entry_high: float | None = None
    risk_reward_planned: float | None = None
    gate_version: str | None = None
    notes: str | None = None
    date_closed: str | None = None
    exit_price: float | None = None
    exit_reason: str | None = None
    realized_r: float | None = None
    pnl_usd: float | None = None
    mfe_r: float | None = None
    mae_r: float | None = None
    plan_adherence: float | None = None
    _file: str | None = None


class JournalResponse(BaseModel):
    """Journal rows response."""
    rows: list[JournalRow]
    count: int


class OpenPositionsResponse(BaseModel):
    """Open positions from the journal."""
    positions: list[JournalRow]
    count: int
    total_size_pct: float
    sector_exposure: dict[str, float]


class ClosedTradesResponse(BaseModel):
    """Closed trades from the journal."""
    trades: list[JournalRow]
    count: int
    win_rate: float | None
    expectancy_r: float | None
    profit_factor: float | None


class AvailableCapitalResponse(BaseModel):
    """Available capital for new positions."""
    account_value: float
    open_notional: float
    available: float
    sector_exposure: dict[str, float]


@router.get(
    "/journal",
    summary="Read all journal rows",
    description="Returns all rows from the paper-trade journal DB (both open and closed).",
)
async def get_journal(
    limit: int | None = Query(None, ge=1, le=10000),
) -> ApiResponse:
    rows = read_rows()
    if limit:
        rows = rows[:limit]
    return ApiResponse(
        data=JournalResponse(rows=[JournalRow(**r) for r in rows], count=len(rows)),
        meta=MetaInfo(),
    )


@router.get(
    "/journal/open",
    summary="Read open positions",
    description="Returns rows with no date_closed (the current open book).",
)
async def get_open_positions() -> ApiResponse:
    rows = read_open_positions()
    total_size = sum(
        float(r.get("position_size_pct") or 0.0) for r in rows
    )
    return ApiResponse(
        data=OpenPositionsResponse(
            positions=[JournalRow(**r) for r in rows],
            count=len(rows),
            total_size_pct=round(total_size, 2),
            sector_exposure=sector_exposure(),
        ),
        meta=MetaInfo(),
    )


@router.get(
    "/journal/closed",
    summary="Read closed trades",
    description="Returns rows with a date_closed (the measurable sample for expectancy).",
)
async def get_closed_trades() -> ApiResponse:
    rows = [
        r for r in read_closed_trades()
        if verification_mod.in_forward_sample(r)
    ]
    wins = 0
    total_r = 0.0
    gross_profit = 0.0
    gross_loss = 0.0
    for r in rows:
        rr = float(r.get("realized_r") or 0.0)
        total_r += rr
        if rr > 0:
            wins += 1
            gross_profit += rr
        elif rr < 0:
            gross_loss += abs(rr)
    count = len(rows)
    win_rate = wins / count if count else None
    expectancy = total_r / count if count else None
    profit_factor = gross_profit / gross_loss if gross_loss else None
    return ApiResponse(
        data=ClosedTradesResponse(
            trades=[JournalRow(**r) for r in rows],
            count=count,
            win_rate=win_rate,
            expectancy_r=expectancy,
            profit_factor=profit_factor,
        ),
        meta=MetaInfo(),
    )


@router.get(
    "/journal/capital",
    summary="Available capital for new positions",
    description="Returns the account value minus open notional, with sector exposure.",
)
async def get_available_capital(
    account_value: float | None = Query(None, gt=0),
) -> ApiResponse:
    avail = available_capital(explicit_account_value=account_value)
    open_rows = read_open_positions()
    open_notional = sum(
        (float(r.get("position_size_pct") or 0.0) / 100.0) * (account_value or 100_000.0)
        for r in open_rows
    )
    return ApiResponse(
        data=AvailableCapitalResponse(
            account_value=account_value or 100_000.0,
            open_notional=round(open_notional, 2),
            available=round(avail, 2),
            sector_exposure=sector_exposure(),
        ),
        meta=MetaInfo(),
    )


@router.get(
    "/journal/trades-dir",
    summary="Get the journal directory path",
    description="Returns the path to the paper-trades directory for debugging.",
)
async def get_trades_dir() -> ApiResponse:
    return ApiResponse(
        data={"path": str(DEFAULT_TRADES_DIR)},
        meta=MetaInfo(),
    )


@router.get(
    "/journal/export",
    summary="Export the journal as CSV",
    description="Canonical 29-col CSV (chronological) plus template/regime/entry_timing/max_hold_days "
                "— Excel remains an output format, never the store.",
    response_class=PlainTextResponse,
)
async def export_journal() -> PlainTextResponse:
    return PlainTextResponse(
        journal_mod.export_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="paper_journal.csv"'},
    )


class JournalRejectionItem(BaseModel):
    """One rejection-log row (why a candidate did not become a trade)."""
    id: int
    date_seen: str
    symbol: str
    sector: str | None = None
    action: str | None = None
    conviction: int | None = None
    failed_step: str | None = None
    gate_verdict: str | None = None
    reason: str | None = None
    notes: str | None = None
    template: str | None = None
    regime: str | None = None
    created_at: str | None = None


class JournalRejectionsResponse(BaseModel):
    """Rejection log response."""
    items: list[JournalRejectionItem]
    count: int


@router.get(
    "/journal/rejections",
    summary="Read the rejection log",
    description="Most-recent-first rejections from the journal DB (gate/sizing failures).",
)
async def get_journal_rejections(
    limit: int = Query(200, ge=1, le=1000),
) -> ApiResponse:
    rows = journal_mod.list_rejections(limit)
    return ApiResponse(
        data=JournalRejectionsResponse(
            items=[JournalRejectionItem(**r) for r in rows],
            count=len(rows),
        ),
        meta=MetaInfo(),
    )


class WorkflowRunItem(BaseModel):
    """One workflow_runs row (touchpoint execution record)."""
    id: int
    run_date: str
    ran_at: str
    mode: str
    apply: bool = False
    accepted: int | None = None
    rejected: int | None = None
    updated: int | None = None
    skipped: int | None = None
    status: str = "ok"
    message: str | None = None
    details: Any = None


class WorkflowRunsResponse(BaseModel):
    """Recent workflow runs response (feeds the UI runs strip)."""
    items: list[WorkflowRunItem]
    count: int


@router.get(
    "/runs",
    summary="Recent workflow runs (UI runs strip)",
    description="Most-recent-first run records for enforce / sync-exits / run-close.",
)
async def get_runs(
    limit: int = Query(14, ge=1, le=200),
) -> ApiResponse:
    rows = journal_mod.list_runs(limit)
    items: list[WorkflowRunItem] = []
    for r in rows:
        details = None
        if r.get("details_json"):
            try:
                details = json.loads(r["details_json"])
            except ValueError:
                details = r["details_json"]
        items.append(WorkflowRunItem(
            id=r["id"], run_date=r["run_date"], ran_at=r["ran_at"],
            mode=r["mode"], apply=bool(r.get("apply")),
            accepted=r.get("accepted"), rejected=r.get("rejected"),
            updated=r.get("updated"), skipped=r.get("skipped"),
            status=r.get("status") or "ok", message=r.get("message"),
            details=details,
        ))
    return ApiResponse(
        data=WorkflowRunsResponse(items=items, count=len(items)),
        meta=MetaInfo(),
    )


# ── Helper functions (ported from paper_trade_from_brief.py) ──

_OVERALL_LITERALS = ("PASS", "FAIL", "CONDITIONAL")


def _normalize_overall(raw: object) -> Literal["PASS", "FAIL", "CONDITIONAL"]:
    text = str(raw or "").strip().upper()
    if text in _OVERALL_LITERALS:
        return text  # type: ignore[return-value]
    return "CONDITIONAL"


def _attached_gate(verdict: dict) -> gate_mod.GateResult | None:
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
            stepResults=steps,
            convictionScore=int(gate_dict.get("conviction_score", 0)),
            dataGaps=[g for g in gate_dict.get("data_gaps", []) if isinstance(g, str)],
            evaluatedAt=str(gate_dict.get("evaluated_at", "")),
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
    steps = list(attached.steps)
    open_positions = journal_mod.read_open_positions()
    if not open_positions:
        journal_step = gate_mod.GateStepResult(
            name="Portfolio Fit", passed=True,
            note="No open positions in the paper journal — book is verified clear; no count/sector conflicts.",
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
    hard_fail = next((s.name for s in steps if not s.passed and not s.conditional), None)
    first_conditional = next((s.name for s in steps if s.conditional), None)
    return hard_fail, first_conditional


# ── Enforce endpoint (Touchpoint A) ──

class EnforceRequest(BaseModel):
    min_conviction: int = 5
    only: str | None = None  # comma-separated symbols


class EnforceResponseItem(BaseModel):
    symbol: str
    gate_verdict: str
    entry_price: float | None = None
    stop_loss: float | None = None
    position_size_pct: float | None = None
    target_1: float | None = None
    target_2: float | None = None
    rejected: bool = False
    failed_step: str | None = None
    reason: str | None = None


class EnforceResponse(BaseModel):
    accepted: list[EnforceResponseItem]
    rejected: list[EnforceResponseItem]
    message: str


@router.post(
    "/paper-trades/enforce",
    summary="Touchpoint A — Run gate enforcement and write paper trades",
    description="Fetches morning brief, evaluates candidates through the 7-step gate, "
                "and writes accepted trades to the journal DB (like --apply).",
    response_model=ApiResponse[EnforceResponse],
)
async def enforce_paper_trades(
    request: EnforceRequest = Body(default=EnforceRequest()),
) -> ApiResponse[EnforceResponse]:
    """Touchpoint A endpoint — thin wrapper over the shared implementation."""
    return ApiResponse(data=await _execute_enforce(request), meta=MetaInfo())


async def _execute_enforce(
    request: EnforceRequest,
    *,
    log_run: bool = True,
) -> EnforceResponse:
    """Gate enforcement → journal DB (P3.1 shared implementation).

    ``log_run=False`` lets the combined run-close call write one row instead.
    """
    # Fetch morning brief using internal service (avoid HTTP self-call)
    try:
        service = _get_morning_brief_service()
        # 60s timeout for morning brief (prevents yfinance hangs)
        brief_response = await asyncio.wait_for(
            service.generate_morning_brief(),
            timeout=60.0,
        )
        brief = brief_response.model_dump(mode="json")
    except asyncio.TimeoutError:
        raise HTTPException(504, "Morning brief generation timed out (60s)")
    except Exception as e:
        raise HTTPException(502, f"Failed to fetch morning brief: {e}")

    # Collect candidates
    candidates: list[tuple[str, dict]] = []
    for section in brief.get("screen_sections", []):
        for t in section.get("tickers", []):
            if t.get("conviction", 0) >= request.min_conviction:
                candidates.append((t["symbol"], t))

    if request.only:
        wanted = {s.strip().upper() for s in request.only.split(",")}
        candidates = [(s, t) for s, t in candidates if s in wanted]

    trade_rows = []
    rejections = []
    accepted_items = []
    rejected_items = []

    for sym, brief_t in candidates:
        try:
            # Fetch verdict using internal service (avoid HTTP self-call)
            from backend.app.api.dependencies import get_ticker_analysis_engine
            from backend.app.domain.ticker_analysis.models import TickerAnalysisRequest
            
            engine = await get_ticker_analysis_engine()
            # 45s timeout per ticker analysis (prevents yfinance hangs)
            v_resp = await asyncio.wait_for(
                engine.analyze_async(TickerAnalysisRequest(symbol=sym, timeframe="1D")),
                timeout=45.0,
            )
            verdict = v_resp.model_dump(mode="json")

            # Build row with gate enforcement
            trade_row, rejection = await _build_row(
                sym, brief_t, verdict,
                market_regime=str(brief.get("regime") or ""),
            )

            if rejection is not None:
                rejected_items.append(EnforceResponseItem(
                    symbol=sym, gate_verdict="FAIL", rejected=True,
                    failed_step=rejection.get("failed_step"),
                    reason=rejection.get("reason"),
                ))
                rejections.append(rejection)
                continue

            if trade_row is None:
                continue

            trade_rows.append(trade_row)
            accepted_items.append(EnforceResponseItem(
                symbol=sym,
                gate_verdict=trade_row["gate_verdict"],
                entry_price=trade_row.get("entry_price"),
                stop_loss=trade_row.get("stop_loss"),
                position_size_pct=trade_row.get("position_size_pct"),
                target_1=trade_row.get("target_1"),
                target_2=trade_row.get("target_2"),
            ))

        except Exception as e:
            rejected_items.append(EnforceResponseItem(
                symbol=sym, gate_verdict="FAIL", rejected=True,
                failed_step="error", reason=str(e),
            ))

    # Persist to the journal DB (D-68): entry-only upsert per accepted row
    # (fresh evaluation wins; exit columns are never touched) and an
    # insert-or-ignore per rejection (one per date+symbol).
    run_date = journal_mod.market_today()
    message = f"{len(trade_rows)} accepted, {len(rejections)} rejected"
    for rejection in rejections:
        journal_mod.insert_rejection(rejection)
    inserted = updated = kept = 0
    if trade_rows:
        inserted = sum(journal_mod.upsert_entry(row) == "inserted" for row in trade_rows)
        updated = len(trade_rows) - inserted
        message += f" — journal updated ({inserted} new, {updated} updated)"
        # Earlier same-day acceptances that were not re-accepted now are kept
        # (P2.2: a re-run never deletes rows it did not accept this time).
        accepted_symbols = {str(r.get("symbol") or "").strip().upper() for r in trade_rows}
        kept = sum(
            1 for r in journal_mod.read_rows()
            if str(r.get("date_entered") or "")[:10] == run_date
            and str(r.get("symbol") or "").strip().upper() not in accepted_symbols
        )
        if kept:
            message += f"; {kept} earlier acceptance(s) kept"
    else:
        message += " — no qualifying setups today"

    # Run log (P2.5): every touchpoint leaves a workflow_runs row.
    # ``skipped`` = earlier same-day acceptances kept (not re-evaluated).
    if log_run:
        journal_mod.record_run(
            "enforce", apply=True,
            accepted=len(trade_rows), rejected=len(rejections),
            updated=inserted + updated, skipped=kept,
            status="partial" if any(r.get("failed_step") == "error" for r in rejections) else "ok",
            message=message,
            details={
                "accepted": [str(r.get("symbol") or "") for r in trade_rows][:50],
                "rejected": [str(r.get("symbol") or "") for r in rejections][:50],
            },
        )

    return EnforceResponse(
        accepted=accepted_items,
        rejected=rejected_items,
        message=message,
    )


# Build row helper (adapted from paper_trade_from_brief.py)
async def _build_row(
    symbol: str,
    brief_section: dict,
    verdict: dict,
    market_regime: str = "",
) -> tuple[dict | None, dict | None]:
    """Build a trade row or rejection dict from verdict + gate.

    Attribution comes from the morning-brief ticker (screen + confluence) and
    the analysis response (sector), never from the verdict body where those
    fields do not exist.
    """
    v = verdict.get("verdict") or {}
    tp = v.get("trade_plan") or {}

    sector = str(
        verdict.get("sector") or brief_section.get("sector") or "Unknown"
    ).strip() or "Unknown"
    template_name = str(brief_section.get("screen_name") or "").strip()
    regime_name = str(market_regime or "").strip()
    max_hold_days = tp.get("max_hold_days")

    def _rejection(step: str, reason: str, notes: str = "") -> dict:
        return {
            "date_seen": journal_mod.market_today(),
            "symbol": symbol, "sector": sector,
            "action": v.get("action", ""), "conviction": v.get("conviction", 0),
            "failed_step": step, "gate_verdict": "FAIL",
            "reason": reason, "notes": notes,
            "template": template_name, "regime": regime_name,
        }

    # Extract gate
    attached = _attached_gate(verdict)
    if not attached:
        return None, _rejection("gate", "No gate attached to verdict")

    # Re-evaluate Portfolio Fit against journal. Use the unhalved risk-based
    # size as the upper bound (CONDITIONAL halves it later) so the sector cap
    # is never understated.
    entry = v.get("entry_zone_low") or v.get("entry_zone_high") or 0
    stop = v.get("stop_loss") or 0
    try:
        size_for_fit = sizing_mod.compute_position_size_pct(entry, stop, None)
    except ValueError:
        size_for_fit = 0.0
    steps, overall = _reevaluate_portfolio_fit(
        attached, symbol=symbol, stop_loss=stop, sector=sector,
        position_size_pct=size_for_fit,
    )
    failed_step, conditional_step = _first_unpassed_step(steps)

    # Compute final size
    try:
        size = sizing_mod.compute_position_size_pct(entry, stop, overall)
    except ValueError as e:
        return None, _rejection(
            "sizing", f"Sizing rejected: {e}", f"entry={entry} stop={stop}",
        )

    if overall == "FAIL":
        failed = failed_step or "gate"
        reason = next((s.note for s in steps if not s.passed and not s.conditional), "Gate failed.")
        return None, _rejection(
            failed, reason[:250], f"entry={entry} stop={stop} size_pct={size}",
        )

    # Accepted row
    targets = v.get("targets") or []
    t1 = round(targets[0], 2) if len(targets) >= 1 else ""
    t2 = round(targets[1], 2) if len(targets) >= 2 else ""

    account_value = journal_mod.available_capital()
    shares = round((size / 100.0 * account_value) / entry, 2) if entry else ""

    confluence_raw = brief_section.get("confluence_score", 0) or 0
    confluence_norm = round(confluence_raw / 20) if confluence_raw else 0

    triggers = v.get("buy_triggers") or []
    red_flags = v.get("key_red_flags") or []
    signal = ";".join(triggers[:2]) if triggers else template_name
    notes_parts = []
    if triggers:
        notes_parts.append("Triggers: " + "; ".join(triggers[:2]))
    if red_flags:
        notes_parts.append("⚠️ " + "; ".join(red_flags[:1]))
    if confluence_raw:
        notes_parts.append(f"raw confluence {confluence_raw}/100")
    if overall == "CONDITIONAL" and conditional_step:
        notes_parts.append(f"conditional on {conditional_step}")
    notes = " | ".join(notes_parts)

    trade_row = {
        "date_entered": journal_mod.market_today(),
        "symbol": symbol,
        "sector": sector,
        "action": v.get("action", "ACCUMULATE"),
        "entry_type": "initial",
        "entry_price": entry,
        "stop_loss": stop,
        "target_1": t1,
        "target_2": t2,
        "position_size_pct": size,
        "account_value": round(account_value, 2),
        "shares": shares,
        "confluence_count": confluence_norm,
        "signal_at_entry": signal[:200],
        "gate_verdict": overall,
        "gate_failed_step": conditional_step if overall == "CONDITIONAL" else "",
        "entry_low": v.get("entry_zone_low"),
        "entry_high": v.get("entry_zone_high"),
        "risk_reward_planned": v.get("risk_reward", ""),
        "gate_version": GATE_VERSION,
        "notes": notes[:500],
        "template": template_name,
        "regime": regime_name,
        "max_hold_days": max_hold_days,
    }
    return trade_row, None


# ── Sync-exits endpoint (Touchpoint B) ──

class SyncExitsRequest(BaseModel):
    apply: bool = False


class SyncExitsResponseItem(BaseModel):
    symbol: str
    exit_date: str | None = None
    exit_price: float | None = None
    exit_reason: str | None = None
    realized_r: float | None = None
    pnl_usd: float | None = None
    mfe_r: float | None = None
    mae_r: float | None = None
    plan_adherence: float | None = None
    applied: bool = False
    skipped: bool = False
    skip_reason: str | None = None


class SyncExitsResponse(BaseModel):
    updated: int
    skipped: int
    items: list[SyncExitsResponseItem]
    message: str


@router.post(
    "/paper-trades/sync-exits",
    summary="Touchpoint B — Sync exits from OHLCV (infer + apply)",
    description="Fetches daily OHLCV for open journal rows, infers exit (stop/target/time), "
                "and when apply=true writes exit data + plan_adherence to the journal DB.",
    response_model=ApiResponse[SyncExitsResponse],
)
async def sync_exits(
    request: SyncExitsRequest = Body(default=SyncExitsRequest()),
) -> ApiResponse[SyncExitsResponse]:
    """Touchpoint B endpoint — thin wrapper over the shared implementation."""
    return ApiResponse(data=await _execute_sync_exits(request), meta=MetaInfo())


async def _execute_sync_exits(
    request: SyncExitsRequest,
    *,
    log_run: bool = True,
) -> SyncExitsResponse:
    """Exit inference → journal DB (P3.1 shared implementation).

    ``log_run=False`` lets the combined run-close call write one row instead.
    """
    run_date = journal_mod.market_today()
    open_rows = journal_mod.read_open_positions()
    if not open_rows:
        message = "No open journal rows to sync."
        if log_run:
            journal_mod.record_run(
                "sync_exits", apply=request.apply, updated=0, skipped=0,
                message=message, details={"applied": [], "skipped": []},
            )
        return SyncExitsResponse(
            updated=0, skipped=0, items=[],
            message=message,
        )

    updated = 0
    skipped = 0
    items = []

    for row in open_rows:
        symbol = str(row.get("symbol") or "").strip().upper()
        # Same-day guard (P2.3): entries are stamped at the close, so today's
        # rows cannot have a real exit yet — skip, not an error.
        if str(row.get("date_entered") or "")[:10] >= run_date:
            skipped += 1
            items.append(SyncExitsResponseItem(
                symbol=symbol or "?",
                skipped=True,
                skip_reason="entered today — exits start next session",
            ))
            continue
        if not symbol:
            skipped += 1
            items.append(SyncExitsResponseItem(symbol="?", skipped=True, skip_reason="no symbol"))
            continue
        entry = journal_mod._as_float(row.get("entry_price"))
        stop = journal_mod._as_float(row.get("stop_loss"))
        if not entry or not stop or stop >= entry:
            skipped += 1
            items.append(SyncExitsResponseItem(symbol=symbol, skipped=True, skip_reason="invalid geometry"))
            continue
        targets = [
            t for t in (
                journal_mod._as_float(row.get("target_1")),
                journal_mod._as_float(row.get("target_2")),
            ) if t is not None
        ]
        max_hold = journal_mod._as_int(row.get("max_hold_days"))

        df = _fetch_daily_ohlcv(symbol)
        if df is None or df.empty:
            skipped += 1
            items.append(SyncExitsResponseItem(symbol=symbol, skipped=True, skip_reason="no OHLCV"))
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
        # The plan states calendar days; infer_exit counts trading bars.
        max_hold_bars = exits_mod.hold_limit_bars(
            bars, row.get("date_entered"), max_hold,
        )
        fill = exits_mod.infer_exit(
            bars, entry=entry, stop=stop,
            targets=targets, max_hold_days=max_hold_bars,
            # EOD entries fill at the close: the entry-day bar's high/low
            # predate the position (P2.4; bug R4).
            exclude_entry_bar_excursions=(
                str(row.get("entry_timing") or "eod").strip().lower() == "eod"
            ),
        )
        if not fill.exit_price or not fill.exit_date:
            skipped += 1
            items.append(SyncExitsResponseItem(symbol=symbol, skipped=True, skip_reason="exit not reached"))
            continue

        realized_r = (fill.exit_price - entry) / (entry - stop)
        account_value = journal_mod._as_float(row.get("account_value"))
        pnl_usd = None
        if account_value:
            risk_amount = account_value * (journal_mod.position_size_pct(row) / 100.0)
            pnl_usd = round(realized_r * risk_amount, 2)

        plan_adherence = 1.0 if fill.exit_reason in (exits_mod.EXIT_STOP, exits_mod.EXIT_TARGET_1, exits_mod.EXIT_TARGET_2) else 0.5

        updates = {
            "date_closed": fill.exit_date,
            "exit_price": round(fill.exit_price, 2),
            "exit_reason": fill.exit_reason,
            "realized_r": round(realized_r, 2),
            "pnl_usd": pnl_usd,
            "mfe_r": fill.mfe_r,
            "mae_r": fill.mae_r,
            "plan_adherence": plan_adherence,
        }

        item = SyncExitsResponseItem(
            symbol=symbol,
            exit_date=fill.exit_date,
            exit_price=round(fill.exit_price, 2),
            exit_reason=fill.exit_reason,
            realized_r=round(realized_r, 2),
            pnl_usd=pnl_usd,
            mfe_r=fill.mfe_r,
            mae_r=fill.mae_r,
            plan_adherence=plan_adherence,
            applied=request.apply,
        )
        items.append(item)

        if request.apply:
            if journal_mod.update_exit(row.get("date_entered"), row.get("symbol"), updates):
                updated += 1
            else:
                item.applied = False
                item.skipped = True
                item.skip_reason = "row already closed"
                skipped += 1
        else:
            # Dry-run: count as would-be applied (script parity) — the message
            # says "would be applied", item.applied stays False.
            updated += 1

    message = f"{updated} exit(s) {'applied' if request.apply else 'would be applied'} ({skipped} skipped)"
    if not request.apply and updated > 0:
        message += " — re-run with apply=true to persist"

    # Run log (P2.5): every touchpoint leaves a workflow_runs row.
    if log_run:
        journal_mod.record_run(
            "sync_exits", apply=request.apply,
            updated=updated, skipped=skipped,
            message=message,
            details={
                "applied": [i.symbol for i in items if i.applied][:50],
                "skipped": [
                    {"symbol": i.symbol, "reason": i.skip_reason}
                    for i in items if i.skipped
                ][:50],
            },
        )

    return SyncExitsResponse(
        updated=updated, skipped=skipped, items=items, message=message,
    )


# ── One-click after-close combined run (P3) ──


class RunCloseRequest(BaseModel):
    """One-go after-close run: enforce (A) then sync exits (B, apply)."""
    min_conviction: int = 5
    only: str | None = None
    apply_exits: bool = True


class RunCloseResponse(BaseModel):
    """Combined run response: one workflow_runs row, both touchpoint results."""
    run_id: int
    enforce: EnforceResponse
    exits: SyncExitsResponse
    message: str


@router.post(
    "/paper-trades/run-close",
    summary="One-go after-close run — Touchpoint A then B(apply)",
    description="Runs gate enforcement (entries) and then exit sync (exits applied) in one call, "
                "so forgetting one of the two touchpoints is impossible. Writes a single "
                "workflow_runs row (mode='run_close'). Entries logged today are skipped by the "
                "exit phase ('exits start next session').",
    response_model=ApiResponse[RunCloseResponse],
)
async def run_close(
    request: RunCloseRequest = Body(default=RunCloseRequest()),
) -> ApiResponse[RunCloseResponse]:
    try:
        enforce_resp = await _execute_enforce(
            EnforceRequest(min_conviction=request.min_conviction, only=request.only),
            log_run=False,
        )
    except HTTPException as exc:
        journal_mod.record_run(
            "run_close", apply=True, status="error",
            message=f"Enforce failed: {exc.detail}",
        )
        raise

    try:
        exits_resp = await _execute_sync_exits(
            SyncExitsRequest(apply=request.apply_exits), log_run=False,
        )
    except Exception as exc:  # entries are written; exits failed afterwards
        journal_mod.record_run(
            "run_close", apply=True, status="partial",
            accepted=len(enforce_resp.accepted), rejected=len(enforce_resp.rejected),
            message=f"Entries written but exits failed: {exc}",
        )
        raise

    message = f"{enforce_resp.message} | Exits: {exits_resp.message}"
    if not request.apply_exits:
        message += " (exits preview only)"
    run_id = journal_mod.record_run(
        "run_close", apply=True,
        accepted=len(enforce_resp.accepted), rejected=len(enforce_resp.rejected),
        updated=exits_resp.updated, skipped=exits_resp.skipped,
        message=message,
        details={
            "enforce": {
                "accepted": [i.symbol for i in enforce_resp.accepted][:50],
                "rejected": [i.symbol for i in enforce_resp.rejected][:50],
            },
            "exits": {
                "applied": [i.symbol for i in exits_resp.items if i.applied][:50],
                "skipped": [
                    {"symbol": i.symbol, "reason": i.skip_reason}
                    for i in exits_resp.items if i.skipped
                ][:50],
            },
        },
    )

    return ApiResponse(
        data=RunCloseResponse(
            run_id=run_id,
            enforce=enforce_resp,
            exits=exits_resp,
            message=message,
        ),
        meta=MetaInfo(),
    )


# ── Expectancy Tracking (Sec.2E verification) ──

class ExpectancyItem(BaseModel):
    """Expectancy metrics for a template/regime combination."""
    template: str
    regime: str
    n_trades: int
    win_rate: float
    expectancy_r: float
    profit_factor: float | None
    avg_r: float
    avg_win_r: float
    avg_loss_r: float
    max_win_r: float
    max_loss_r: float
    total_r: float
    is_elite: bool
    elite_min_trades: int


class ExpectancyResponse(BaseModel):
    """All template/regime expectancy metrics."""
    items: list[ExpectancyItem]
    elite_count: int
    total_combinations: int


class RollingExpectancyRequest(BaseModel):
    symbol: str | None = None
    template: str | None = None
    regime: str | None = None
    window: int = 30


class RollingExpectancyResponse(BaseModel):
    symbol: str | None = None
    template: str | None = None
    regime: str | None = None
    window: int
    win_rate: float
    expectancy_r: float
    profit_factor: float | None
    total_r: float


@router.get(
    "/expectancy",
    summary="Get expectancy metrics per template/regime",
    description="Returns rolling expectancy, win rate, profit factor for each template/regime combination. Elite badge requires n>=30 and expectancy>0.",
    response_model=ApiResponse[ExpectancyResponse],
)
async def get_expectancy(
    min_trades: int = Query(30, ge=1, description="Minimum trades for elite status"),
) -> ApiResponse[ExpectancyResponse]:
    metrics = verification_mod.compute_expectancy_per_template_regime(min_trades=min_trades)
    items = [ExpectancyItem(**m.to_dict()) for m in metrics.values()]
    elite_count = sum(1 for m in metrics.values() if m.is_elite)
    return ApiResponse(
        data=ExpectancyResponse(
            items=items,
            elite_count=elite_count,
            total_combinations=len(items),
        ),
        meta=MetaInfo(),
    )


@router.get(
    "/expectancy/elite",
    summary="Get only elite template/regime combinations",
    description="Returns only combinations with n>=30 trades and positive expectancy.",
    response_model=ApiResponse[ExpectancyResponse],
)
async def get_elite_expectancy(
    min_trades: int = Query(30, ge=1, description="Minimum trades for elite status"),
) -> ApiResponse[ExpectancyResponse]:
    elite_metrics = verification_mod.get_elite_templates(min_trades=min_trades)
    items = [ExpectancyItem(**m.to_dict()) for m in elite_metrics]
    return ApiResponse(
        data=ExpectancyResponse(
            items=items,
            elite_count=len(items),
            total_combinations=len(items),
        ),
        meta=MetaInfo(),
    )


@router.post(
    "/expectancy/rolling",
    summary="Get rolling expectancy for a symbol/template/regime",
    description="Computes rolling expectancy over the last N trades for a specific filter.",
    response_model=ApiResponse[RollingExpectancyResponse | None],
)
async def get_rolling_expectancy(
    request: RollingExpectancyRequest = Body(default=RollingExpectancyRequest()),
) -> ApiResponse[RollingExpectancyResponse | None]:
    result = verification_mod.compute_rolling_expectancy(
        symbol=request.symbol,
        template=request.template,
        regime=request.regime,
        window=request.window,
    )
    if result is None:
        return ApiResponse(data=None, meta=MetaInfo())
    return ApiResponse(
        data=RollingExpectancyResponse(**result),
        meta=MetaInfo(),
    )


# ── Replay ledger (D-71) ────────────────────────────────────────────────────


@router.get(
    "/replay",
    summary="Latest two-month replay ledger",
    description=(
        "Simulated screen-template replay stored in replay_runs / replay_trades. "
        "Deliberately separate from the forward journal: replay rows never count "
        "toward expectancy or the kill rule. Returns {run, rows, summary}; "
        "run is null until `python run_paper_replay.py` has been run."
    ),
)
async def get_replay() -> ApiResponse:
    payload = replay_store.latest_run()
    if payload is None:
        return ApiResponse(
            data={"run": None, "rows": [], "summary": None}, meta=MetaInfo()
        )
    return ApiResponse(data=payload, meta=MetaInfo())


@router.delete(
    "/replay",
    summary="Clear the replay ledger",
    description="Deletes replay_runs / replay_trades rows. The forward journal is untouched.",
)
async def delete_replay() -> ApiResponse:
    removed = replay_store.clear()
    return ApiResponse(data={"removed": removed}, meta=MetaInfo())