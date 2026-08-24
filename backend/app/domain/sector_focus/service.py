"""Sector Focus scoring service.

Fuses existing per-sector signals (weekly relative strength, institutional flow,
momentum, volume confirmation) into ONE prescriptive verdict per sector:
FOCUS / WATCH / NEUTRAL / AVOID — answering "which sector do I hunt this week?"

Design notes
------------
- Weekly horizon is the decision lens; daily moves are explicitly treated as noise.
- RS component is rank-normalized ACROSS sectors, which alone would crown the
  "least-fallen" sector in a downtrend. Two guards prevent that:
    1. Absolute-vs-market gate: sector 1W return must exceed SPY 1W return.
    2. Regime gate: broad_market_weakness caps FOCUS at zero.
- Missing signals drop their term and RENORMALIZE remaining weights. Fewer than
  two available components ⇒ score is None (verdict WATCH, "insufficient data").
  Never fabricate.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

METHOD_VERSION = "sf-v1"

FOCUS_THRESHOLD = 70.0
WATCH_THRESHOLD = 55.0
NEUTRAL_THRESHOLD = 40.0

# FOCUS cap by rotation-detected market regime
REGIME_CAPS: dict[str, int] = {
    "broad_market_strength": 3,
    "mixed": 2,
    "unknown": 2,
    "broad_market_weakness": 0,
}

WEIGHTS = {"rs": 0.40, "flow": 0.25, "mom": 0.20, "vol": 0.15}


# ── Models ───────────────────────────────────────────────────────────────


@dataclass
class SectorFocusMetrics:
    """Raw per-sector inputs for one snapshot."""

    symbol: str
    name: str
    change_1w: float | None = None
    rs_1w_z: float | None = None
    flow_strength_1w: float | None = None
    momentum_score: float | None = None
    volume_vs_avg_1w: float | None = None


@dataclass
class SectorFocusEntry:
    symbol: str
    name: str
    verdict: str  # FOCUS / WATCH / NEUTRAL / AVOID
    score: float | None
    reasons: list[str] = field(default_factory=list)
    metrics: dict[str, float | None] = field(default_factory=dict)


@dataclass
class SectorFocusSnapshot:
    entries: list[SectorFocusEntry]
    focus: list[SectorFocusEntry]
    watch: list[SectorFocusEntry]
    avoid: list[SectorFocusEntry]
    market_regime: str
    no_hunt_mode: bool
    generated_at: datetime
    next_refresh_at: datetime
    methodology_version: str = METHOD_VERSION
    snapshot_id: str = ""

    def to_dict(self) -> dict:
        return {
            "snapshot_id": self.snapshot_id,
            "generated_at": self.generated_at.isoformat(),
            "next_refresh_at": self.next_refresh_at.isoformat(),
            "market_regime": self.market_regime,
            "no_hunt_mode": self.no_hunt_mode,
            "methodology_version": self.methodology_version,
            "cadence": "continuous (~5m cache); weekly horizon is the decision lens",
            "focus": [entry_to_dict(e) for e in self.focus],
            "watch": [entry_to_dict(e) for e in self.watch],
            "avoid": [entry_to_dict(e) for e in self.avoid],
        }


def entry_to_dict(e: SectorFocusEntry) -> dict:
    return {
        "symbol": e.symbol,
        "name": e.name,
        "verdict": e.verdict,
        "score": round(e.score, 1) if e.score is not None else None,
        "reasons": list(e.reasons),
        "metrics": {k: (round(v, 2) if isinstance(v, float) else v) for k, v in e.metrics.items()},
    }


# ── Pure scoring helpers ─────────────────────────────────────────────────


def percentile_scores(values: dict[str, float | None]) -> dict[str, float | None]:
    """Rank-based 0-100 normalization across sectors (100 = strongest).

    None stays None. Ties share the same score.
    """
    valid = {s: v for s, v in values.items() if v is not None}
    n = len(valid)
    if n == 0:
        return {s: None for s in values}
    ordered = sorted(valid.items(), key=lambda kv: kv[1])
    scores: dict[str, float | None] = {}
    i = 0
    while i < len(ordered):
        j = i
        while j + 1 < len(ordered) and ordered[j + 1][1] == ordered[i][1]:
            j += 1
        # average rank for ties (dense positions i..j)
        avg_pos = ((i + j) // 2 + 1) / n * 100.0
        for k in range(i, j + 1):
            scores[ordered[k][0]] = round(avg_pos, 1)
        i = j + 1
    for s in values:
        if s not in scores:
            scores[s] = None
    return scores


def compute_focus_score(
    s_rs: float | None,
    s_flow: float | None,
    s_mom: float | None,
    s_vol: float | None,
    bonus: float = 0.0,
) -> tuple[float | None, list[str]]:
    """Weighted composite with renormalization over available components.

    Returns (score|None, used_components). Score None when <2 components exist.
    """
    components = {"rs": s_rs, "flow": s_flow, "mom": s_mom, "vol": s_vol}
    available = {k: v for k, v in components.items() if v is not None}
    used = sorted(available.keys())
    if len(available) < 2:
        return None, used
    total_w = sum(WEIGHTS[k] for k in available)
    score = sum(WEIGHTS[k] * v for k, v in available.items()) / total_w
    return round(min(100.0, max(0.0, score + bonus)), 1), used


def improvement_bonus(cur_rank: int, prev_rank: int | None) -> float:
    """+10 if weekly RS rank improved; +5 if holding steady inside top 3."""
    if prev_rank is None:
        return 0.0
    if cur_rank < prev_rank:
        return 10.0
    if cur_rank == prev_rank and cur_rank <= 3:
        return 5.0
    return 0.0


def weekly_return_ranks(
    df: pd.DataFrame, symbols: list[str]
) -> tuple[dict[str, int], dict[str, int] | None]:
    """Current and previous-week ranks by 1W price return (desc).

    Current window: latest close vs close 6 bars back (≈1 trading week).
    Previous window: same length ending one week earlier (iloc[-6] vs iloc[-12]).
    Sectors lacking enough history are excluded from both rankings.
    """
    def _ranks(end_offset: int) -> dict[str, int]:
        rets: dict[str, float] = {}
        for sym in symbols:
            if sym not in df.columns:
                continue
            prices = df[sym].dropna()
            need = end_offset + 7
            if len(prices) < need:
                continue
            now_p = float(prices.iloc[-1 - end_offset])
            past_p = float(prices.iloc[-need])
            if past_p == 0:
                continue
            rets[sym] = (now_p - past_p) / past_p * 100
        ranked = sorted(rets.items(), key=lambda kv: kv[1], reverse=True)
        return {sym: i + 1 for i, (sym, _) in enumerate(ranked)}

    current = _ranks(0)
    try:
        previous = _ranks(5)
    except Exception:
        previous = None
    return current, previous or None


def absolute_gate_passed(change_1w: float | None, spy_change_1w: float | None) -> tuple[bool, str]:
    """FOOCUS eligibility requires beating SPY over the same weekly window.

    Unknown benchmark ⇒ gate NOT satisfied (conservative); sector stays WATCH.
    """
    if change_1w is None:
        return False, "weekly return unavailable"
    if spy_change_1w is None:
        return False, "market benchmark unavailable"
    if change_1w > spy_change_1w:
        return True, ""
    return False, f"trailing market ({change_1w:+.1f}% vs SPY {spy_change_1w:+.1f}% this week)"


# ── Reason generation (deterministic; no jargon) ────────────────────────


def build_reasons(
    entry: SectorFocusEntry,
    rs_rank: int | None,
    n_sectors: int,
    spy_gate_reason: str,
    bonus: float,
) -> list[str]:
    reasons: list[str] = []
    m = entry.metrics
    if rs_rank is not None and n_sectors:
        ordinal = f"#{rs_rank} of {n_sectors}"
        if entry.verdict in ("FOCUS", "WATCH") and rs_rank <= 3:
            reasons.append(f"{ordinal} sectors in weekly relative strength")
        elif entry.verdict == "AVOID" and rs_rank > n_sectors - 3:
            reasons.append(f"Weakest group — {ordinal} sectors in weekly strength")
    if m.get("flow_strength_1w") is not None and (m["flow_strength_1w"] or 0) >= 40:
        reasons.append(f"Institutions accumulating — weekly volume strength {m['flow_strength_1w']:.0f}/100")
    if m.get("volume_vs_avg_1w") is not None and (m["volume_vs_avg_1w"] or 1.0) >= 1.3:
        reasons.append(f"Heavy participation: weekly volume {(m['volume_vs_avg_1w']):.1f}× average")
    if m.get("momentum_score") is not None and (m["momentum_score"] or 50) >= 65:
        reasons.append(f"Momentum confirming ({m['momentum_score']:.0f}/100)")
    if bonus >= 10:
        reasons.append("Improving: gained ground vs last week")
    elif bonus >= 5:
        reasons.append("Holding a top-3 strength position vs last week")
    if entry.verdict == "WATCH" and spy_gate_reason:
        reasons.append(f"Not yet confirmed: {spy_gate_reason}")
    if entry.verdict == "AVOID":
        if m.get("volume_vs_avg_1w") is not None and (m["volume_vs_avg_1w"] or 1.0) < 0.9:
            reasons.append("Below-average participation — moves here tend to fade")
    return reasons[:4]


# ── Snapshot builder ─────────────────────────────────────────────────────


def _snapshot_id(entries: list[SectorFocusEntry], regime: str) -> str:
    payload = {
        "v": METHOD_VERSION,
        "regime": regime,
        "sectors": sorted(
            (
                e.symbol,
                round(e.score, 1) if e.score is not None else None,
                e.verdict,
                tuple(sorted((k, round(v, 2)) for k, v in e.metrics.items() if isinstance(v, float))),
            )
            for e in entries
        ),
    }
    raw = repr(payload)
    return "sha1:" + hashlib.sha1(raw.encode()).hexdigest()[:16]


def build_sector_focus_snapshot(
    df: pd.DataFrame,
    volume_ratios_1w: dict[str, float],
    flow_strength_1w_by_symbol: dict[str, float],
    spy_change_1w: float | None,
    now: datetime,
    ttl_seconds: float = 300.0,
) -> SectorFocusSnapshot:
    """Build the full verdict snapshot from cached sector data.

    Regime is detected by the rotation router's own detector (single source of
    truth shared with the Sector Rotation page). df is the cached price matrix.
    """
    from backend.app.api.routers.sector_rotation import (
        SECTOR_ETFS,
        SECTOR_SYMBOLS,
        SectorPerformance,
        _compute_momentum,
        _compute_relative_strength,
        _compute_returns,
        _detect_market_regime,
    )

    empty_ok = df.empty or len(df.columns) < 2
    returns = {} if empty_ok else _compute_returns(df)
    rs_1d_map = {} if empty_ok else _compute_relative_strength(returns, "change_1d")
    rs_1w_map = {} if empty_ok else _compute_relative_strength(returns, "change_1w")

    # Breadth regime — same detector the rotation page uses
    perf_min = [
        SectorPerformance(symbol=s, name=SECTOR_ETFS.get(s, {}).get("name", s), relative_strength_1d=rs_1d_map.get(s))
        for s in SECTOR_SYMBOLS
    ]
    regime = _detect_market_regime(perf_min)

    s_rs = percentile_scores(rs_1w_map)
    cur_ranks, prev_ranks = weekly_return_ranks(df, SECTOR_SYMBOLS)
    gate_reasons: dict[str, str] = {}

    entries: list[SectorFocusEntry] = []
    for sym in SECTOR_SYMBOLS:
        info = SECTOR_ETFS.get(sym, {"name": sym})
        r = returns.get(sym, {})
        chg_1w = r.get("change_1w")
        flow_1w = flow_strength_1w_by_symbol.get(sym)
        mom = _compute_momentum(rs_1d_map.get(sym), rs_1w_map.get(sym))
        vol_1w = volume_ratios_1w.get(sym)

        s_vol = min(100.0, max(0.0, vol_1w * 50)) if vol_1w is not None else None
        rs_rank = cur_ranks.get(sym)
        prev_rank = prev_ranks.get(sym) if prev_ranks else None
        bonus = improvement_bonus(rs_rank, prev_rank) if rs_rank is not None else 0.0

        score, _used = compute_focus_score(
            s_rs.get(sym), flow_1w, mom, s_vol, bonus=bonus
        )
        gate_ok, gate_reason = absolute_gate_passed(chg_1w, spy_change_1w)
        gate_reasons[sym] = gate_reason

        metrics = {
            "rs_rank": float(rs_rank) if rs_rank is not None else None,
            "rs_z_1w": rs_1w_map.get(sym),
            "flow_strength_1w": flow_1w,
            "momentum": mom,
            "volume_vs_avg_1w": vol_1w,
            "change_1w": chg_1w,
        }

        if score is None:
            verdict = "WATCH"
        elif score >= FOCUS_THRESHOLD and gate_ok:
            verdict = "FOCUS_CANDIDATE"
        elif score >= WATCH_THRESHOLD:
            verdict = "WATCH"
        elif score >= NEUTRAL_THRESHOLD:
            verdict = "NEUTRAL"
        else:
            verdict = "AVOID"

        entry = SectorFocusEntry(
            symbol=sym,
            name=info.get("name", sym),
            verdict=verdict,
            score=score,
            metrics=metrics,
        )
        entries.append(entry)

    cap = REGIME_CAPS.get(regime, 2)
    candidates = sorted(
        (e for e in entries if e.verdict == "FOCUS_CANDIDATE"),
        key=lambda e: (e.score or 0), reverse=True,
    )
    for e in candidates[:cap]:
        e.verdict = "FOCUS"
    for e in candidates[cap:]:
        e.verdict = "WATCH"

    # Reasons are built AFTER final tier assignment so templates can key off
    # the definitive verdict (e.g. FOCUS gets the "#N of 11" headline reason).
    for e in entries:
        raw_rank = e.metrics.get("rs_rank")
        rs_rank = int(raw_rank) if isinstance(raw_rank, float) else None
        cur_rank = cur_ranks.get(e.symbol)
        prev_rank = prev_ranks.get(e.symbol) if prev_ranks else None
        bonus = improvement_bonus(cur_rank, prev_rank) if cur_rank is not None else 0.0
        g_reason = gate_reasons.get(e.symbol, "")
        e.reasons = build_reasons(e, rs_rank, len(SECTOR_SYMBOLS), g_reason, bonus)
        if (
            e.verdict == "WATCH"
            and e.score is not None
            and e.score >= FOCUS_THRESHOLD
            and g_reason
        ):
            e.reasons.insert(0, f"Strong but unconfirmed: {g_reason}")

    for e in candidates[cap:]:
        e.reasons.insert(0, "Qualified, but sector slots are full this week")

    no_hunt = regime == "broad_market_weakness"

    focus = [e for e in entries if e.verdict == "FOCUS"]
    watch = [
        e for e in entries
        if e.verdict == "WATCH" or (e.verdict == "NEUTRAL" and (e.score or 0) >= WATCH_THRESHOLD - 10)
    ]
    avoid_pool = [e for e in entries if e.verdict == "AVOID"]
    if len(avoid_pool) < 3:
        extras = sorted(
            (e for e in entries if e not in avoid_pool and e.verdict not in ("FOCUS",)),
            key=lambda e: (e.score if e.score is not None else -1),
        )
        avoid_pool = avoid_pool + extras[: 3 - len(avoid_pool)]
        for e in avoid_pool:
            if e.verdict != "AVOID":
                e.verdict = "AVOID_RELATIVE"
    avoid = sorted(avoid_pool, key=lambda e: (e.score if e.score is not None else -1))

    watch = [e for e in watch if e not in avoid]

    snap = SectorFocusSnapshot(
        entries=entries,
        focus=focus,
        watch=watch,
        avoid=avoid,
        market_regime=regime,
        no_hunt_mode=no_hunt,
        generated_at=now,
        next_refresh_at=datetime.fromtimestamp(now.timestamp() + ttl_seconds, tz=now.tzinfo),
    )
    snap.snapshot_id = _snapshot_id(entries, regime)
    return snap
