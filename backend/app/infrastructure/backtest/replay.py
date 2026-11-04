"""Two-month paper-trade replay (D-71) — orchestration.

What this is
------------
For each trading day in the replay window we compute the market regime using
the *same* scoring model as the live morning brief, look up the three deployed
screens that regime would have selected, and keep the signals those screens
would have produced across a broad universe. Each kept signal becomes one
journal-visible replay trade, entered at the next bar's open and exited with
the same conservative ATR rules used by the honest validation engine.

What this is **not**
-------------------
TradingView's screener only answers "now", so the live brief's ranking,
confluence scores, catalyst checks and final gate cannot be replayed. This is
a screen/template replay, not a reconstruction of the exact live picks. It is
labelled as simulated and must never be counted as forward evidence.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from backend.app.core.logging import get_logger
from backend.app.domain.workflow import exit_policy as exit_policy_mod
from backend.app.domain.workflow import pending as pending_mod
from backend.app.infrastructure.backtest import replay_rules as rules_mod
from backend.app.infrastructure.backtest.external_backtest import (
    BacktestConfig,
    ExternalBacktestEngine,
)
from backend.app.infrastructure.backtest.replay_data import (
    fetch_history,
    fetch_regime_frames,
    filter_usable,
    load_universe,
)
from backend.app.infrastructure.market.regime import (
    MACRO_SYMBOLS,
    SECTOR_SYMBOLS,
    compute_regime_from_frames,
)
from backend.app.infrastructure.screener.configs import ScreenConfig, load_screen_template

log = get_logger("conflu.backtest.replay")

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_REGIME_CONFIG = REPO_ROOT / "config" / "regime_screens.yaml"

REGIME_KEYS = ("strong_trend", "neutral", "choppy", "ranging", "high_vol")
TOP_N = 3

# Mirrors morning_brief._REGIME_LABEL_MAP (asserted in tests to prevent drift).
LABEL_TO_REGIME: dict[str, str] = {
    "Exuberance": "strong_trend",
    "Risk-On": "strong_trend",
    "Neutral": "neutral",
    "Cautious": "choppy",
    "Risk-Off": "high_vol",
    "Crisis": "high_vol",
}

REPLAY_CAVEATS = [
    "TradingView's screener cannot be rewound: screen ranking, confluence scores, "
    "catalyst checks and the live gate are not replayed.",
    "Signals are evaluated on locally cached OHLCV for a current S&P 500 snapshot "
    "(survivorship bias remains).",
    "Entries are next-bar opens; exits are ATR stop/target (2.0/3.0) with a "
    "15-bar cap; stop wins on same-bar ties; fees 10 bps + slippage 5 bps/side.",
    "Fundamental / RS-rank filters that need live data are recorded as not applied "
    "and treated as not matched (same honesty rule as the validation engine).",
    "This is simulated replay evidence, not forward paper-trade evidence and not a "
    "P&L promise.",
]

H09_CAVEATS = [
    "Evidence label: exploratory_h09_not_evidence. Exploratory only: H-09 never "
    "enters the forward scorecard, the D-75 pass bar, the kill rule, /expectancy "
    "or any v0.2 verdict.",
    "TradingView's screener cannot be rewound. Ranking, confluence, catalysts, "
    "earnings/liquidity checks, portfolio caps and the live entry-zone branch "
    "selection are not replayed; only gate step 5 is applied.",
    "Both arms share the signal stream, the entry zone, the stop and the D-73 "
    "fills. They differ only in target selection, the gate floor and the exit.",
    "The signal stream is the D-71 engine's one-position-at-a-time entry list; it "
    "is not the live signal rate.",
    "Structural levels are OHLCV-only (no TradingView resistance), so the target "
    "population differs from live.",
    "The stop is 2xATR from the signal close, not from the fill (a disclosed "
    "deviation from D-71's fill-based stop).",
    "The v0.1 arm is a reconstruction of live v0.1 rules on replay geometry, not "
    "the live v0.1 journal. It reproduces the 5c midpoint-vs-entry-low quirk and "
    "infer_exit's T2-before-T1 ordering on purpose.",
    "Family names come from the live display name (G11). Screens whose display "
    "name does not normalize to a family run as 'unknown'; the stem-based "
    "sensitivity is secondary.",
    "Trades still open at the data edge close at the last close ('eod'); they are "
    "excluded from the primary aggregate unless the 36-day horizon is covered.",
    "Universe is today's S&P 500 snapshot (survivorship bias); one window and "
    "several cuts mean any positive result is a hypothesis, not evidence.",
]

DATA_HORIZON_DAYS = 36


@dataclass(frozen=True)
class ReplayParams:
    """Knobs for a replay run.

    ``rules_version="v0.1"`` keeps the published D-71 engine path (its prices,
    targets and exits). ``rules_version="v0.2"`` runs the H-09 two-arm replay:
    the signal stream stays frozen at 2.0/3.0 ATR and 15 bars, while
    ``stop_atr_mult`` becomes the **plan** stop (signal close − 2×ATR).
    """

    window_days: int = 60
    daily_lookback_days: int = 760
    hourly_lookback_days: int = 200
    stop_atr_mult: float = 2.0
    target_atr_mult: float = 3.0
    max_hold_bars: int = 15
    fees_bps: float = 10.0
    slippage_bps: float = 5.0
    risk_pct: float = 1.0
    account_value: float = 100_000.0
    max_per_day: int = 0
    # H-09 (D-78). Defaults are the frozen design in the H-09 plan.
    rules_version: str = rules_mod.RULES_V01
    window_start: str | None = None
    window_end: str | None = None
    entry_zone_atr_mult: float = rules_mod.ENTRY_ZONE_ATR_MULT
    min_zone_pct: float = rules_mod.MIN_ZONE_PCT
    fill_expiry_sessions: int = rules_mod.FILL_EXPIRY_SESSIONS
    v01_max_hold_days: int = rules_mod.V01_MAX_HOLD_DAYS


@dataclass
class ReplayResult:
    """Persistable replay output.

    ``artifacts`` carries per-arm detail for the JSON artifact only; it is never
    written to the replay ledger.
    """

    run: dict[str, Any]
    rows: list[dict[str, Any]]
    summary: dict[str, Any]
    artifacts: dict[str, Any] = field(default_factory=dict)


# ── Screen mix ──────────────────────────────────────────────────────────────


def load_screen_mix(
    path: str | Path | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Load the deployed regime → screen mix.

    Mirrors ``RegimeScreenSelector._select_from_config`` (top-3 primaries, the
    weakest primary slot replaced by the top defensive, then backfill on load
    failures) but keeps the YAML stem + weight, which is what the journal
    needs to display.
    """
    config_path = Path(path or DEFAULT_REGIME_CONFIG)
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    regimes = raw.get("regimes") or {}
    mix: dict[str, list[dict[str, Any]]] = {}

    for regime in REGIME_KEYS:
        entries = []
        for entry in regimes.get(regime) or []:
            name = str(entry.get("name") or "").strip()
            if not name:
                continue
            entries.append(
                {
                    "name": name,
                    "weight": float(entry.get("weight") or 0.0),
                    "role": str(entry.get("role") or ""),
                }
            )
        if not entries:
            continue
        ordered = sorted(entries, key=lambda item: item["weight"], reverse=True)
        primaries = [item for item in ordered if item["role"] != "defensive"]
        defensives = [item for item in ordered if item["role"] == "defensive"]

        picked = [item["name"] for item in primaries[:TOP_N]]
        if defensives:
            top_defensive = defensives[0]["name"]
            if top_defensive not in picked:
                if len(picked) >= TOP_N:
                    picked[-1] = top_defensive
                else:
                    picked.append(top_defensive)

        by_name = {item["name"]: item for item in ordered}
        loaded: list[dict[str, Any]] = []

        def _add(name: str, screens_by_name: dict[str, Any], target: list[dict[str, Any]]) -> None:
            try:
                screen = load_screen_template(name)
            except Exception as exc:  # noqa: BLE001 - broken template is skipped loudly
                log.warning("replay.screen_load_failed", screen=name, error=str(exc))
                return
            meta = screens_by_name.get(name, {"weight": 0.0, "role": ""})
            target.append(
                {
                    "stem": name,
                    "config": screen,
                    "weight": float(meta.get("weight") or 0.0),
                    "role": str(meta.get("role") or ""),
                    "rank": len(target) + 1,
                }
            )

        for name in picked:
            _add(name, by_name, loaded)

        if len(loaded) < TOP_N:
            picked_set = set(picked)
            for item in ordered:
                if len(loaded) >= TOP_N:
                    break
                if item["name"] in picked_set:
                    continue
                _add(item["name"], by_name, loaded)

        mix[regime] = loaded

    return mix


# ── Regime as-of ────────────────────────────────────────────────────────────


def _breadth_at(
    sector_frames: dict[str, pd.DataFrame], as_of: pd.Timestamp
) -> dict[str, int]:
    """Replicate the live 5-day sector-breadth snapshot as of a past day."""
    positive = 0
    total = 0
    for symbol in SECTOR_SYMBOLS:
        frame = sector_frames.get(symbol)
        if frame is None or frame.empty:
            continue
        window = frame.loc[:as_of].tail(5)
        if len(window) < 2:
            continue
        first = float(window["Close"].iloc[0])
        last = float(window["Close"].iloc[-1])
        if first <= 0:
            continue
        if last > first:
            positive += 1
        total += 1
    return {"positive": positive, "total": total}


def historical_regime_map(
    macro_frames: dict[str, pd.DataFrame],
    sector_frames: dict[str, pd.DataFrame],
    dates: pd.DatetimeIndex | list[pd.Timestamp],
) -> dict[str, dict[str, Any]]:
    """Compute the regime label for each date using data through that close.

    The live morning brief runs pre-market and acts on the next open; here the
    signal is evaluated at date *T*'s close and entered at *T+1*'s open, so
    using *T*'s close for the regime keeps the information set aligned.
    """
    result: dict[str, dict[str, Any]] = {}
    last: dict[str, Any] | None = None

    for raw_ts in dates:
        ts = pd.Timestamp(raw_ts)
        macro_slice: dict[str, pd.DataFrame] = {}
        for symbol in MACRO_SYMBOLS:
            frame = macro_frames.get(symbol)
            if frame is None or frame.empty:
                continue
            window = frame.loc[:ts].tail(21)
            if len(window) >= 2:
                macro_slice[symbol] = window

        breadth = _breadth_at(sector_frames, ts)
        response = compute_regime_from_frames(
            macro_slice,
            breadth,
            now=datetime(ts.year, ts.month, ts.day, 20, 0, tzinfo=UTC),
        )
        key = ts.date().isoformat()
        if response is None:
            if last is not None:
                result[key] = dict(last, date=key)
            continue
        record = {
            "date": key,
            "label": response.regime_label,
            "key": LABEL_TO_REGIME.get(response.regime_label, "neutral"),
            "composite": response.composite_score,
        }
        result[key] = record
        last = record

    return result


# ── Helpers ─────────────────────────────────────────────────────────────────


def _signal_date(trade: dict[str, Any], daily_index: pd.Index) -> str:
    """Signal bar date (fallback for legacy trade rows without the field)."""
    explicit = trade.get("signal_date")
    if explicit:
        return str(explicit)[:10]
    entry = pd.Timestamp(trade["entry_date"])
    prior = daily_index[daily_index < entry]
    if len(prior) == 0:
        return ""
    return pd.Timestamp(prior[-1]).date().isoformat()


def _rvol(daily: pd.DataFrame, signal_date: str) -> float | None:
    """Volume on the signal bar / mean volume of the prior 20 bars."""
    try:
        ts = pd.Timestamp(signal_date)
        if ts not in daily.index:
            return None
        idx = daily.index.get_loc(ts)
        if not isinstance(idx, int) or idx < 20:
            return None
        vol = float(daily["Volume"].iloc[idx])
        avg = float(daily["Volume"].iloc[idx - 20 : idx].mean())
        if not pd.notna(vol) or not pd.notna(avg) or avg <= 0:
            return None
        return float(vol / avg)
    except Exception:  # noqa: BLE001 - rvol is a display/ranking nicety only
        return None


def _candidate_to_row(
    candidate: dict[str, Any],
    params: ReplayParams,
) -> dict[str, Any] | None:
    trade = candidate["trade"]
    entry = float(trade["entry_price"])
    stop = float(trade["stop_price"])
    target = float(trade["target_price"])
    exit_price = float(trade["exit_price"])
    direction = 1 if trade.get("direction", "long") == "long" else -1
    risk_per_share = abs(entry - stop)
    if risk_per_share <= 0:
        return None

    risk_usd = params.account_value * params.risk_pct / 100.0
    shares = risk_usd / risk_per_share
    slip = params.slippage_bps / 10_000.0
    fees_rate = params.fees_bps / 10_000.0
    entry_fill = entry * (1 + direction * slip)
    exit_fill = exit_price * (1 - direction * slip)
    gross = direction * shares * (exit_fill - entry_fill)
    fees = (shares * entry_fill + shares * exit_fill) * fees_rate
    pnl_usd = gross - fees
    position_size_pct = (
        shares * entry_fill / params.account_value * 100.0
        if params.account_value > 0
        else None
    )

    also = candidate.get("also_signaled_by") or ""
    notes = (
        "SIMULATED REPLAY (not forward evidence) · "
        f"screen rank {candidate['screen_rank']}/{candidate['screen_total']} "
        f"(weight {candidate['screen_weight']:.0f}) · "
        f"ATR stop {params.stop_atr_mult:g} / target {params.target_atr_mult:g} · "
        f"max {params.max_hold_bars} bars"
    )
    if also:
        notes += f" · also signalled by: {also}"

    return {
        "signal_date": candidate["signal_date"],
        "date_entered": str(trade["entry_date"])[:10],
        "symbol": candidate["symbol"],
        "template": candidate["template"],
        "regime": candidate["regime"],
        "regime_key": candidate["regime_key"],
        "screen_rank": candidate["screen_rank"],
        "screen_weight": candidate["screen_weight"],
        "direction": trade.get("direction", "long"),
        "entry_price": entry,
        "stop_loss": stop,
        "target_1": target,
        "exit_date": str(trade["exit_date"])[:10],
        "exit_price": exit_price,
        "exit_reason": trade.get("exit_reason"),
        "realized_r": float(trade.get("r_multiple") or 0.0),
        "pnl_usd": float(pnl_usd),
        "risk_pct": params.risk_pct,
        "position_size_pct": position_size_pct,
        "shares": float(shares),
        "account_value": params.account_value,
        "hold_bars": int(trade.get("hold_bars") or 0),
        "rvol": candidate.get("rvol"),
        "also_signaled_by": also or None,
        "notes": notes,
    }


def _group_summary(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(key) or "—")].append(row)
    return {name: _basic_summary(items) for name, items in sorted(grouped.items())}


def _basic_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate replay rows.

    Convention: ``wins`` / ``losses`` / ``win_rate`` classify by **net** dollar P&L
    (``pnl_usd``, after fees + slippage), while ``expectancy_r`` / ``avg_win_r`` /
    ``avg_loss_r`` / ``profit_factor_r`` use the engine's **gross** R-multiples.
    Net R per trade is ``pnl_usd / (account_value * risk_pct / 100)``.

    Rows without an exit (rejected plans) are excluded by the caller.
    """
    n = len(rows)
    empty = {
        "trades": 0,
        "wins": 0,
        "losses": 0,
        "win_rate": 0.0,
        "expectancy_r": 0.0,
        "avg_win_r": 0.0,
        "avg_loss_r": 0.0,
        "profit_factor_r": None,
        "pnl_usd": 0.0,
        "pnl_gross_usd": 0.0,
        "costs_usd": 0.0,
        "avg_hold_bars": 0.0,
        "mfe_capture": None,
        "censored": 0,
    }
    if n == 0:
        return empty
    wins = [row for row in rows if float(row.get("pnl_usd") or 0.0) > 0]
    losses = [row for row in rows if float(row.get("pnl_usd") or 0.0) <= 0]
    rs = [float(row["realized_r"]) for row in rows if row.get("realized_r") is not None]
    wins_r = [r for r in rs if r > 0]
    losses_r = [r for r in rs if r < 0]
    gross_win_r = sum(wins_r)
    gross_loss_r = abs(sum(losses_r))
    captures = [
        float(row["realized_r"]) / float(row["mfe_r"])
        for row in rows
        if row.get("realized_r") is not None
        and row.get("mfe_r") is not None
        and float(row["mfe_r"]) > 0
    ]
    return {
        "trades": n,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": len(wins) / n,
        "expectancy_r": (sum(rs) / len(rs)) if rs else 0.0,
        "avg_win_r": (sum(wins_r) / len(wins_r)) if wins_r else 0.0,
        "avg_loss_r": (sum(losses_r) / len(losses_r)) if losses_r else 0.0,
        "profit_factor_r": (gross_win_r / gross_loss_r) if gross_loss_r > 0 else None,
        "pnl_usd": sum(float(row.get("pnl_usd") or 0.0) for row in rows),
        "pnl_gross_usd": sum(float(row.get("pnl_gross_usd") or 0.0) for row in rows),
        "costs_usd": sum(float(row.get("costs_usd") or 0.0) for row in rows),
        "avg_hold_bars": sum(int(row.get("hold_bars") or 0) for row in rows) / n,
        "mfe_capture": (sum(captures) / len(captures)) if captures else None,
        "censored": sum(1 for row in rows if row.get("censored")),
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Overall + per-template + per-regime replay statistics."""
    base = _basic_summary(rows)
    base["templates"] = _group_summary(rows, "template")
    base["regimes"] = _group_summary(rows, "regime")
    base["exit_reasons"] = dict(Counter(str(row.get("exit_reason") or "—") for row in rows))
    base["total_r"] = sum(float(row["realized_r"]) for row in rows)
    return base


# ── H-09 two-arm replay ─────────────────────────────────────────────────────


def _signal_key(candidate: dict[str, Any]) -> str:
    return f"{candidate['signal_date']}|{candidate['symbol']}"


def _arm_row(
    candidate: dict[str, Any],
    geometry: rules_mod.PlanGeometry,
    plan: rules_mod.PlanDecision,
    fill: pending_mod.FillDecision,
    outcome: rules_mod.TradeOutcome | None,
    shares: float | None,
    params: ReplayParams,
    *,
    arm: str,
) -> dict[str, Any]:
    """One arm's row. Rejected plans carry no exit and never enter the ledger."""
    targets = list(plan.targets)
    fill_price = float(fill.fill_price or 0.0)
    condition = plan.gate_verdict == "CONDITIONAL"
    risk_pct = params.risk_pct * 0.5 if condition else params.risk_pct
    position_size_pct = (
        shares * fill_price / params.account_value * 100.0
        if shares is not None and params.account_value > 0
        else None
    )
    notes = [
        "SIMULATED REPLAY (H-09, not forward evidence)",
        f"arm {arm}",
        f"gate {plan.gate_verdict or '—'}",
    ]
    if plan.family:
        notes.append(f"family {plan.family}")
    if plan.rejection:
        notes.append(f"rejected: {plan.rejection}")
    if candidate.get("also_signaled_by"):
        notes.append(f"also signalled by: {candidate['also_signaled_by']}")

    return {
        # Artifact-only fields (the store ignores unknown keys).
        "signal_key": _signal_key(candidate),
        "arm": arm,
        "accepted": plan.accepted,
        "has_exit": outcome is not None and outcome.exit_price is not None,
        "rejection": plan.rejection,
        "rejection_detail": plan.rejection_detail,
        "censored": bool(outcome.censored) if outcome else False,
        # Ledger fields.
        "rules_version": arm,
        "signal_date": candidate["signal_date"],
        "date_entered": str(fill.fill_date or "")[:10],
        "symbol": candidate["symbol"],
        "template": candidate["template"],
        "regime": candidate["regime"],
        "regime_key": candidate["regime_key"],
        "screen_rank": candidate["screen_rank"],
        "screen_weight": candidate["screen_weight"],
        "direction": "long",
        "entry_price": round(fill_price, 4),
        "entry_low": geometry.entry_low,
        "entry_high": geometry.entry_high,
        "stop_loss": geometry.stop_loss,
        "target_1": targets[0] if len(targets) >= 1 else None,
        "target_2": targets[1] if len(targets) >= 2 else None,
        "target_3": targets[2] if len(targets) >= 3 else None,
        "setup_family": plan.family,
        "plan_rr": plan.plan_rr,
        "target_1_r": plan.target_1_r,
        "stretch_rr": plan.stretch_rr,
        "atr_at_entry": geometry.atr,
        "gate_verdict": plan.gate_verdict,
        "gate_note": (plan.gate_note or "")[:300] or None,
        "exit_date": outcome.exit_date if outcome else None,
        "exit_price": outcome.exit_price if outcome else None,
        "exit_reason": outcome.exit_reason if outcome else None,
        "realized_r": outcome.realized_r if outcome else None,
        "pnl_usd": outcome.pnl_usd if outcome else None,
        "pnl_gross_usd": outcome.pnl_gross_usd if outcome else None,
        "costs_usd": outcome.costs_usd if outcome else None,
        "mfe_r": outcome.mfe_r if outcome else None,
        "mae_r": outcome.mae_r if outcome else None,
        "plan_adherence": outcome.plan_adherence if outcome else None,
        "exit_legs": (
            json.dumps(outcome.legs, separators=(",", ":"))
            if outcome and outcome.legs
            else None
        ),
        "risk_pct": risk_pct,
        "position_size_pct": position_size_pct,
        "shares": shares,
        "account_value": params.account_value,
        "hold_bars": outcome.bars_held if outcome else 0,
        "rvol": candidate.get("rvol"),
        "also_signaled_by": candidate.get("also_signaled_by") or None,
        "notes": " · ".join(notes),
    }


def _fill_outcome(
    plan: rules_mod.PlanDecision,
    *,
    arm: str,
    fill: pending_mod.FillDecision,
    geometry: rules_mod.PlanGeometry,
    exit_bars: list[dict[str, Any]],
    shares: float | None,
    same_session: bool,
    params: ReplayParams,
) -> rules_mod.TradeOutcome | None:
    if not plan.has_plan:
        return None
    if same_session:
        return rules_mod.stop_outcome(fill, geometry.stop_loss, shares)
    if arm == "v0.1":
        return rules_mod.v01_outcome(
            exit_bars,
            fill=fill,
            stop_loss=geometry.stop_loss,
            targets=plan.targets,
            shares=shares,
            max_hold_days=params.v01_max_hold_days,
        )
    return rules_mod.v02_outcome(
        exit_bars,
        fill=fill,
        stop_loss=geometry.stop_loss,
        targets=plan.targets,
        family=plan.family or "unknown",
        atr=geometry.atr,
        shares=shares,
    )


def _run_h09(
    params: ReplayParams,
    candidates: list[dict[str, Any]],
    daily: dict[str, pd.DataFrame],
    *,
    templates: dict[str, ScreenConfig],
    horizon_end: str | None,
) -> dict[str, Any]:
    """Evaluate both arms on the same signals, fills and geometry."""
    funnel: Counter[str] = Counter()
    # Every funnel bucket is present even when a stage never runs, so a stored
    # run always reconciles (an empty signal stream is a valid result).
    for bucket in (
        "orders",
        "filled",
        "expired",
        "cancelled_gap",
        "no_sessions",
        "geometry_invalid",
        "v01_gated_out",
        "v01_accepted",
        "v02_rejected",
        "v02_gated_out",
        "v02_accepted",
        "v02_closed",
        "v02_eod",
    ):
        funnel[bucket] = 0
    funnel["deduped"] = len(candidates)
    rejection_reasons: Counter[str] = Counter()
    arms: dict[str, list[dict[str, Any]]] = {"v01": [], "v02": [], "v02_stem": []}

    family_map = {
        stem: {
            "display_name": config.name,
            "family": exit_policy_mod.family_for_screen(config.name),
            "stem_family": exit_policy_mod.family_for_screen(stem),
        }
        for stem, config in templates.items()
    }
    unknown_screens = sorted(
        stem for stem, meta in family_map.items() if meta["family"] == "unknown"
    )

    bars_by_symbol = {
        symbol: rules_mod.frame_to_bars(frame, end=horizon_end)
        for symbol, frame in daily.items()
    }

    for candidate in candidates:
        symbol = candidate["symbol"]
        frame = daily.get(symbol)
        signal_date = candidate["signal_date"]
        if frame is None or frame.empty:
            funnel["geometry_invalid"] += 1
            continue
        timestamp = pd.Timestamp(signal_date)
        if timestamp not in frame.index:
            funnel["geometry_invalid"] += 1
            continue

        close = float(frame.loc[timestamp, "Close"])
        atr = rules_mod.atr_at(frame, signal_date)
        geometry = rules_mod.build_geometry(
            close,
            atr,
            entry_zone_atr_mult=params.entry_zone_atr_mult,
            min_zone_pct=params.min_zone_pct,
            stop_atr_mult=params.stop_atr_mult,
        )
        if geometry is None:
            funnel["geometry_invalid"] += 1
            continue

        funnel["orders"] += 1
        bars = bars_by_symbol.get(symbol) or []
        fill = rules_mod.evaluate_fill(
            geometry,
            signal_date,
            bars,
            expiry_sessions=params.fill_expiry_sessions,
            today=horizon_end,
        )
        if fill.status != pending_mod.FILLED:
            if fill.status == pending_mod.CANCELLED:
                funnel["cancelled_gap"] += 1
            elif fill.status == pending_mod.EXPIRED:
                funnel["expired"] += 1
            else:
                funnel["no_sessions"] += 1
            continue
        funnel["filled"] += 1

        levels = rules_mod.structural_levels(
            frame.loc[:timestamp], close=close, atr=atr
        )
        meta = family_map.get(candidate["template"]) or {}
        family = meta.get("family") or "unknown"
        stem_family = meta.get("stem_family") or "unknown"

        v01 = rules_mod.v01_plan(geometry, levels, symbol=symbol)
        v02 = rules_mod.v02_plan(geometry, levels, family, symbol=symbol)
        v02_stem = (
            rules_mod.v02_plan(geometry, levels, stem_family, symbol=symbol)
            if stem_family != family
            else v02
        )

        fill_price = float(fill.fill_price or 0.0)
        same_session = rules_mod.same_session_stop(fill, geometry.stop_loss)
        exit_bars = [
            bar for bar in bars if str(bar.get("date") or "") >= str(fill.fill_date)
        ]

        def _shares(
            plan: rules_mod.PlanDecision, price: float, stop_loss: float
        ) -> float | None:
            risk = params.risk_pct * 0.5 if plan.gate_verdict == "CONDITIONAL" else params.risk_pct
            return rules_mod.shares_for(
                price,
                stop_loss,
                risk_pct=risk,
                account_value=params.account_value,
            )

        shares01 = _shares(v01, fill_price, geometry.stop_loss)
        shares02 = _shares(v02, fill_price, geometry.stop_loss)
        outcome01 = _fill_outcome(
            v01, arm="v0.1", fill=fill, geometry=geometry, exit_bars=exit_bars,
            shares=shares01, same_session=same_session, params=params,
        )
        outcome02 = _fill_outcome(
            v02, arm="v0.2", fill=fill, geometry=geometry, exit_bars=exit_bars,
            shares=shares02, same_session=same_session, params=params,
        )
        arms["v01"].append(
            _arm_row(candidate, geometry, v01, fill, outcome01, shares01, params, arm="v0.1")
        )
        arms["v02"].append(
            _arm_row(candidate, geometry, v02, fill, outcome02, shares02, params, arm="v0.2")
        )
        if v02_stem is not v02:
            shares_stem = _shares(v02_stem, fill_price, geometry.stop_loss)
            outcome_stem = _fill_outcome(
                v02_stem, arm="v0.2", fill=fill, geometry=geometry,
                exit_bars=exit_bars, shares=shares_stem,
                same_session=same_session, params=params,
            )
            arms["v02_stem"].append(
                _arm_row(
                    candidate, geometry, v02_stem, fill, outcome_stem,
                    shares_stem, params, arm="v0.2",
                )
            )

        if v02.rejection:
            rejection_reasons[v02.rejection] += 1

    # ── Funnel reconciliation (hard failure, never a rounding note) ──
    v01_rows = arms["v01"]
    v02_rows = arms["v02"]
    funnel["v01_gated_out"] = sum(1 for row in v01_rows if row["gate_verdict"] == "FAIL")
    funnel["v01_accepted"] = sum(1 for row in v01_rows if row["accepted"])
    funnel["v02_rejected"] = sum(1 for row in v02_rows if row["rejection"])
    funnel["v02_rejected_reasons"] = dict(rejection_reasons)
    funnel["v02_gated_out"] = sum(
        1 for row in v02_rows if not row["rejection"] and row["gate_verdict"] == "FAIL"
    )
    funnel["v02_accepted"] = sum(1 for row in v02_rows if row["accepted"])
    funnel["v02_closed"] = sum(
        1 for row in v02_rows if row["accepted"] and row["has_exit"] and not row["censored"]
    )
    funnel["v02_eod"] = sum(
        1 for row in v02_rows if row["accepted"] and row["censored"]
    )

    filled = funnel["filled"]
    if funnel["v02_rejected"] + funnel["v02_gated_out"] + funnel["v02_accepted"] != filled:
        raise RuntimeError(
            "H-09 funnel does not reconcile for v0.2: "
            f"filled={filled} rejected={funnel['v02_rejected']} "
            f"gated_out={funnel['v02_gated_out']} accepted={funnel['v02_accepted']}"
        )
    if funnel["v01_gated_out"] + funnel["v01_accepted"] != filled:
        raise RuntimeError(
            "H-09 funnel does not reconcile for v0.1: "
            f"filled={filled} gated_out={funnel['v01_gated_out']} "
            f"accepted={funnel['v01_accepted']}"
        )
    if (
        funnel["filled"] + funnel["cancelled_gap"]
        + funnel["expired"] + funnel["no_sessions"]
        != funnel["orders"]
    ):
        raise RuntimeError(
            "H-09 funnel does not reconcile at the fill stage: "
            f"orders={funnel['orders']} filled={funnel['filled']} "
            f"cancelled={funnel['cancelled_gap']} expired={funnel['expired']} "
            f"no_sessions={funnel['no_sessions']}"
        )

    # ── Deltas ──
    exited01 = {row["signal_key"]: row for row in v01_rows if row["has_exit"]}
    exited02 = {row["signal_key"]: row for row in v02_rows if row["has_exit"]}
    paired = sorted(set(exited01) & set(exited02))

    accepted02_keys = {row["signal_key"] for row in v02_rows if row["accepted"]}
    v01_gate_fail_keys = {
        row["signal_key"] for row in v01_rows if row["gate_verdict"] == "FAIL"
    }
    rejected02_keys = {row["signal_key"] for row in v02_rows if row["rejection"]}

    delta = {
        "exit_only": {
            "n_paired": len(paired),
            "v01": _basic_summary([exited01[key] for key in paired]),
            "v02": _basic_summary([exited02[key] for key in paired]),
        },
        "policy": {
            "v01": _basic_summary([row for row in exited01.values() if row["accepted"]]),
            "v02": _basic_summary([row for row in exited02.values() if row["accepted"]]),
        },
        "rejection_quality": {
            "v02_rejected": {
                "n": len(rejected02_keys),
                "v01_counterfactual": _basic_summary(
                    [exited01[key] for key in sorted(rejected02_keys) if key in exited01]
                ),
            },
            "v02_accepted_v01_gate_fail": {
                "n": len(accepted02_keys & v01_gate_fail_keys),
                "v02": _basic_summary(
                    [
                        exited02[key]
                        for key in sorted(accepted02_keys & v01_gate_fail_keys)
                        if key in exited02
                    ]
                ),
            },
        },
        "sensitivity_stem_family": {
            "n_changed": sum(
                1
                for stem, meta in family_map.items()
                if meta["family"] != meta["stem_family"]
            ),
            "v02": _basic_summary(
                [
                    row
                    for row in arms["v02_stem"]
                    if row["accepted"] and row["has_exit"]
                ]
            ),
        },
    }

    accepted_rows = [
        row for row in v02_rows if row["accepted"] and row["has_exit"]
    ]
    accepted_rows.sort(key=lambda row: (row["date_entered"], row["symbol"]), reverse=True)

    # Frozen-design provenance: the CLI refuses to write a run when this list is
    # non-empty. Dry runs may deviate on purpose; the artifact says so.
    frozen = {
        "entry_zone_atr_mult": rules_mod.ENTRY_ZONE_ATR_MULT,
        "min_zone_pct": rules_mod.MIN_ZONE_PCT,
        "stop_atr_mult": rules_mod.STOP_ATR_MULT,
        "fill_expiry_sessions": rules_mod.FILL_EXPIRY_SESSIONS,
        "v01_max_hold_days": rules_mod.V01_MAX_HOLD_DAYS,
        "signal_stop_atr_mult": rules_mod.SIGNAL_STOP_ATR_MULT,
        "signal_target_atr_mult": rules_mod.SIGNAL_TARGET_ATR_MULT,
        "signal_max_hold_bars": rules_mod.SIGNAL_MAX_HOLD_BARS,
    }
    actual = {
        "entry_zone_atr_mult": params.entry_zone_atr_mult,
        "min_zone_pct": params.min_zone_pct,
        "stop_atr_mult": params.stop_atr_mult,
        "fill_expiry_sessions": params.fill_expiry_sessions,
        "v01_max_hold_days": params.v01_max_hold_days,
        # The engine is hard-wired to these for H-09 (run_replay); record them
        # so the verifier can prove the signal stream never moved.
        "signal_stop_atr_mult": rules_mod.SIGNAL_STOP_ATR_MULT,
        "signal_target_atr_mult": rules_mod.SIGNAL_TARGET_ATR_MULT,
        "signal_max_hold_bars": rules_mod.SIGNAL_MAX_HOLD_BARS,
    }
    design = {
        "frozen": frozen,
        "actual": actual,
        "deviations": sorted(
            key for key, value in frozen.items() if actual[key] != value
        ),
    }

    return {
        "rows": accepted_rows,
        "arms": arms,
        "funnel": dict(funnel),
        "delta": delta,
        "family_map": family_map,
        "unknown_screens": unknown_screens,
        "family_mix": dict(Counter(row["setup_family"] or "unknown" for row in accepted_rows)),
        "arm_summaries": {
            "v01": _basic_summary([row for row in v01_rows if row["has_exit"]]),
            "v01_accepted": _basic_summary(
                [row for row in v01_rows if row["accepted"] and row["has_exit"]]
            ),
            "v02": _basic_summary([row for row in v02_rows if row["has_exit"]]),
            "v02_accepted": _basic_summary(accepted_rows),
            "v02_accepted_closed": _basic_summary(
                [row for row in accepted_rows if not row["censored"]]
            ),
        },
        "design": design,
    }


def _h09_summary(result: dict[str, Any]) -> dict[str, Any]:
    """Primary aggregate for the H-09 ledger.

    The primary number excludes ``eod`` rows (trades still open at the data
    edge). ``all_accepted`` keeps them visible so the exclusion can never hide
    a loss; ``censored_excluded`` records how many were left out.
    """
    accepted = result["rows"]
    closed = [row for row in accepted if row["has_exit"] and not row["censored"]]
    base = _basic_summary(closed)
    base["templates"] = _group_summary(closed, "template")
    base["regimes"] = _group_summary(closed, "regime")
    base["exit_reasons"] = dict(
        Counter(str(row.get("exit_reason") or "—") for row in closed)
    )
    base["total_r"] = sum(
        float(row["realized_r"])
        for row in closed
        if row.get("realized_r") is not None
    )
    base["all_accepted"] = _basic_summary(accepted)
    base["censored_excluded"] = len(accepted) - len(closed)
    base["arms"] = result["arm_summaries"]
    base["delta"] = result["delta"]
    base["funnel"] = result["funnel"]
    base["family_mix"] = result["family_mix"]
    base["unknown_screens"] = result["unknown_screens"]
    base["evidence_label"] = rules_mod.EVIDENCE_LABEL
    return base


# ── Core run ────────────────────────────────────────────────────────────────


async def run_replay(
    params: ReplayParams | None = None,
    *,
    symbols: list[str] | None = None,
    universe_file: str | Path | None = None,
    cache_dir: str | Path | None = None,
    refresh_data: bool = False,
    templates_filter: list[str] | None = None,
    progress: bool = True,
    now: datetime | None = None,
    daily: dict[str, pd.DataFrame] | None = None,
    hourly: dict[str, pd.DataFrame] | None = None,
    regime_frames: dict[str, pd.DataFrame] | None = None,
    screen_mix: dict[str, list[dict[str, Any]]] | None = None,
    suppress_engine_logs: bool = True,
) -> ReplayResult:
    """Run the historical replay and return rows + summaries.

    Data/regime/screen inputs are injectable so the orchestration can be
    tested without network access.
    """
    params = params or ReplayParams()
    now = now or datetime.now(UTC)
    today = now.date()

    if params.rules_version not in rules_mod.RULES_VERSIONS:
        raise ValueError(
            f"Unknown rules_version {params.rules_version!r}; "
            f"expected one of {rules_mod.RULES_VERSIONS}"
        )
    h09 = params.rules_version == rules_mod.RULES_V02
    if h09:
        if not params.window_start or not params.window_end:
            raise ValueError(
                "H-09 (rules_version='v0.2') requires explicit window_start and "
                "window_end; the frozen window is not inferred from the data edge."
            )
        if params.max_per_day:
            raise ValueError(
                "H-09 requires max_per_day=0 (no portfolio caps in the replay)."
            )

    if symbols is None:
        symbols = sorted(daily) if daily is not None else load_universe(universe_file)

    fetch_anchor = (
        pd.Timestamp(params.window_start).date() if params.window_start else today
    )
    daily_start = (fetch_anchor - timedelta(days=params.daily_lookback_days)).isoformat()
    hourly_start = (fetch_anchor - timedelta(days=params.hourly_lookback_days)).isoformat()
    end_date = today.isoformat()

    missing_daily: list[str] = []
    missing_hourly: list[str] = []
    dropped: dict[str, str] = {}

    if daily is None or (hourly is None and not h09):
        if progress:
            print(f"Fetching daily OHLCV for {len(symbols)} symbols...")
        raw_daily, missing_daily = fetch_history(
            symbols,
            start=daily_start,
            end=end_date,
            interval="1d",
            cache_dir=cache_dir,
            refresh=refresh_data,
            progress=progress,
        )
        raw_hourly: dict[str, pd.DataFrame] = {}
        if not h09:
            # H-09 is daily-only: its geometry, structure and signal engine all
            # read daily bars, so skipping the hourly fetch halves the run time
            # without changing the population.
            if progress:
                print(f"Fetching hourly OHLCV for {len(symbols)} symbols...")
            raw_hourly, missing_hourly = fetch_history(
                symbols,
                start=hourly_start,
                end=end_date,
                interval="1h",
                cache_dir=cache_dir,
                refresh=refresh_data,
                progress=progress,
            )
        daily, hourly, dropped = filter_usable(raw_daily, raw_hourly)
    else:
        daily, hourly, dropped = filter_usable(daily, hourly or {})

    if regime_frames is None:
        if progress:
            print("Fetching macro + sector regime frames...")
        regime_frames = fetch_regime_frames(
            start=daily_start,
            end=end_date,
            cache_dir=cache_dir,
            refresh=refresh_data,
        )

    spy = regime_frames.get("SPY")
    if spy is None or spy.empty:
        raise RuntimeError("Regime frames are missing SPY; cannot build a trading calendar.")

    data_end_ts = pd.Timestamp(spy.index[-1])
    window_end_ts = (
        pd.Timestamp(params.window_end) if params.window_end else data_end_ts
    )
    window_start_ts = (
        pd.Timestamp(params.window_start)
        if params.window_start
        else window_end_ts - pd.Timedelta(days=params.window_days)
    )
    signal_dates = [
        ts for ts in spy.index if window_start_ts <= ts <= window_end_ts
    ]
    if not signal_dates:
        raise RuntimeError(
            "No signal days in the replay window "
            f"{window_start_ts.date()} .. {window_end_ts.date()} "
            f"(data ends {data_end_ts.date()})."
        )
    # The D-71 ledger can be written at any time; the H-09 ledger needs enough
    # post-window data for a 3-session fill + 30-day time stop. 36 calendar days
    # is the frozen minimum (H-09 plan §9; earliest full run 2026-11-24).
    data_horizon_days = int(
        (data_end_ts.normalize() - window_end_ts.normalize()).days
    )
    horizon_ok = data_horizon_days >= DATA_HORIZON_DAYS

    macro_frames = {sym: regime_frames[sym] for sym in MACRO_SYMBOLS if sym in regime_frames}
    sector_frames = {sym: regime_frames[sym] for sym in SECTOR_SYMBOLS if sym in regime_frames}
    regime_by_date = historical_regime_map(macro_frames, sector_frames, signal_dates)

    if progress:
        counts = Counter(record["key"] for record in regime_by_date.values())
        print(f"Regime days: {dict(counts)}")

    mix = screen_mix or load_screen_mix()
    if templates_filter:
        allowed = {name.strip() for name in templates_filter if name.strip()}
        mix = {
            regime: [item for item in items if item["stem"] in allowed]
            for regime, items in mix.items()
        }
    screen_lookup = {
        regime: {item["stem"]: item for item in items} for regime, items in mix.items()
    }

    # One engine run per (unique template, symbol); signals are deduped later.
    templates: dict[str, ScreenConfig] = {}
    for items in mix.values():
        for item in items:
            templates.setdefault(item["stem"], item["config"])

    if progress:
        print(f"Running {len(templates)} deployed templates across {len(daily)} symbols...")

    # The signal stream is the population. In H-09 it is frozen independently
    # of the plan geometry (2.0 stop / 3.0 target / 15 bars); the shared plan
    # stop is applied later by replay_rules.build_geometry.
    signal_stop_mult = (
        rules_mod.SIGNAL_STOP_ATR_MULT if h09 else params.stop_atr_mult
    )
    signal_target_mult = (
        rules_mod.SIGNAL_TARGET_ATR_MULT if h09 else params.target_atr_mult
    )
    signal_max_hold = (
        rules_mod.SIGNAL_MAX_HOLD_BARS if h09 else params.max_hold_bars
    )

    prefetched: dict[tuple[str, str], pd.DataFrame] = {}
    for symbol, frame in daily.items():
        prefetched[(symbol, "1D")] = frame
    for symbol, frame in hourly.items():
        prefetched[(symbol, "1h")] = frame
    engine = ExternalBacktestEngine(fetcher=_PrefetchedFetcher(prefetched))
    if suppress_engine_logs:
        # ~7k engine runs would otherwise emit ~21k INFO lines. Replay progress
        # is printed explicitly below; real failures still surface in results.
        engine._log = _QuietLogger()  # type: ignore[attr-defined]

    candidates: list[dict[str, Any]] = []
    raw_signal_count = 0
    excluded: dict[str, dict[str, Any]] = {}
    skipped_by_template: dict[str, Counter[str]] = {stem: Counter() for stem in templates}

    for template_index, (stem, screen) in enumerate(sorted(templates.items()), start=1):
        template_trades = 0
        for symbol, frame in daily.items():
            config = BacktestConfig(
                symbol=symbol,
                timeframe="1D",
                start_date=daily_start,
                end_date=end_date,
                signal_filters=list(screen.filters),
                direction=getattr(screen, "direction", "long"),
                stop_atr_mult=signal_stop_mult,
                target_atr_mult=signal_target_mult,
                max_hold_bars=signal_max_hold,
                fees_bps=params.fees_bps,
                slippage_bps=params.slippage_bps,
            )
            result = await engine.run_backtest(config)
            skipped_by_template[stem].update(result.skipped_filters)
            if result.error:
                excluded[f"{stem}/{symbol}"] = {
                    "error": result.error,
                    "skipped": result.skipped_filters,
                }
                continue

            for trade in result.trades:
                raw_signal_count += 1
                signal_date = _signal_date(trade, frame.index)
                if signal_date not in regime_by_date:
                    continue
                regime = regime_by_date[signal_date]
                selected = screen_lookup.get(regime["key"]) or {}
                selection = selected.get(stem)
                if selection is None:
                    continue
                template_trades += 1
                candidates.append(
                    {
                        "signal_date": signal_date,
                        "symbol": symbol,
                        "template": stem,
                        "screen_name": screen.name,
                        "regime": regime["label"],
                        "regime_key": regime["key"],
                        "screen_rank": selection["rank"],
                        "screen_total": len(mix.get(regime["key"]) or []),
                        "screen_weight": selection["weight"],
                        "trade": trade,
                        "rvol": _rvol(frame, signal_date),
                        "also_signaled_by": "",
                    }
                )
        if progress:
            print(
                f"  [{template_index}/{len(templates)}] {stem:38} "
                f"signals={template_trades}"
            )

    # Dedupe: one entry per symbol/signal day, highest-priority screen wins.
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        grouped[(candidate["signal_date"], candidate["symbol"])].append(candidate)

    deduped: list[dict[str, Any]] = []
    for group in grouped.values():
        group.sort(key=lambda item: (item["screen_rank"], item["template"]))
        keep = group[0]
        others = sorted({item["template"] for item in group[1:]})
        keep["also_signaled_by"] = ", ".join(others)
        deduped.append(keep)

    deduped_count = len(deduped)

    if params.max_per_day and params.max_per_day > 0:
        by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for candidate in deduped:
            by_day[candidate["signal_date"]].append(candidate)
        capped: list[dict[str, Any]] = []
        for items in by_day.values():
            items.sort(key=lambda item: (item.get("rvol") or 0.0), reverse=True)
            capped.extend(items[: params.max_per_day])
        deduped = capped

    h09_result: dict[str, Any] | None = None
    if h09:
        h09_result = _run_h09(
            params,
            deduped,
            daily,
            templates=templates,
            horizon_end=data_end_ts.date().isoformat(),
        )
        rows = h09_result["rows"]
        summary = _h09_summary(h09_result)
    else:
        rows = []
        for candidate in deduped:
            row = _candidate_to_row(candidate, params)
            if row is not None:
                rows.append(row)
        rows.sort(key=lambda row: (row["date_entered"], row["symbol"]), reverse=True)
        summary = summarize(rows)
    regime_days = Counter(record["key"] for record in regime_by_date.values())
    run = {
        "generated_at": now.isoformat(),
        "window_start": window_start_ts.date().isoformat(),
        "window_end": window_end_ts.date().isoformat(),
        "universe_count": len(daily),
        "universe_requested": len(symbols),
        "templates_count": len(templates),
        "rules_version": params.rules_version,
        "params": asdict(params),
        "summary": summary,
        "metadata": {
            "engine": "external_backtest v2 (validation reset 2026-10-19)",
            "source": "local OHLCV replay of deployed screen templates",
            "rules_version": params.rules_version,
            "evidence_label": (
                rules_mod.EVIDENCE_LABEL if h09 else "d71_screen_replay_not_evidence"
            ),
            "templates": sorted(templates),
            "screens": {
                regime: [
                    {
                        "name": item["stem"],
                        "display_name": item["config"].name,
                        "weight": item["weight"],
                        "rank": item["rank"],
                        "role": item["role"],
                    }
                    for item in items
                ]
                for regime, items in mix.items()
            },
            "regime_days": dict(regime_days),
            "data_horizon": {
                "as_of": data_end_ts.date().isoformat(),
                "window_end": window_end_ts.date().isoformat(),
                "days": data_horizon_days,
                "required_days": DATA_HORIZON_DAYS,
                "ok": horizon_ok,
            },
            "data_quality": {
                "requested": len(symbols),
                "usable_daily": len(daily),
                "usable_hourly": len(hourly),
                "missing_daily": missing_daily,
                "missing_hourly": missing_hourly,
                "dropped": dropped,
                "excluded": excluded,
            },
            "counts": {
                "raw_signals": raw_signal_count,
                "after_regime_gate": len(candidates),
                "after_dedupe": deduped_count,
                "after_day_cap": len(deduped),
                "rows": len(rows),
            },
            "h09": (
                {
                    "evidence_label": rules_mod.EVIDENCE_LABEL,
                    "funnel": h09_result["funnel"],
                    "delta": h09_result["delta"],
                    "family_map": h09_result["family_map"],
                    "unknown_screens": h09_result["unknown_screens"],
                    "family_mix": h09_result["family_mix"],
                    "arm_summaries": h09_result["arm_summaries"],
                    "design": h09_result["design"],
                    "primary_excludes_censored": True,
                }
                if h09_result is not None
                else None
            ),
            "not_applied_filters": {
                stem: dict(counter)
                for stem, counter in skipped_by_template.items()
                if counter
            },
            "caveats": H09_CAVEATS if h09 else REPLAY_CAVEATS,
        },
    }

    return ReplayResult(
        run=run,
        rows=rows,
        summary=summary,
        artifacts=(
            {"arms": h09_result["arms"]} if h09_result is not None else {}
        ),
    )


class _PrefetchedFetcher:
    """Serve pre-fetched frames to the engine (same contract as the validation runner)."""

    def __init__(self, data: dict[tuple[str, str], pd.DataFrame]):
        self.data = data
        self.misses: Counter[tuple[str, str]] = Counter()

    async def fetch_yahoo(self, symbol: str, timeframe: str, start: str, end: str):  # noqa: ARG002
        frame = self.data.get((symbol, timeframe))
        if frame is None:
            self.misses[(symbol, timeframe)] += 1
        return frame


class _QuietLogger:
    """No-op structlog stand-in for the per-symbol engine chatter."""

    def _noop(self, *args: Any, **kwargs: Any) -> None:
        return None

    debug = info = warning = error = exception = _noop
