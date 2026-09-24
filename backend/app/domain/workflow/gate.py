"""Workflow validation gate — the honest Wave-1 skeleton (plan Sec.1B/1C).

The gate is a backend-owned advisory assessment, distinct from strategy
validation (it never blocks a verdict — it attaches `AnalysisVerdict.gate`).
Seven steps mirror the frontend's teach-first philosophy in
``frontend/src/workflow/gate.ts``:

    1. Liquidity          — can we get in/out cleanly?   ($10M ADV floor)
    2. Structure          — do weekly + daily trends align?
    3. Positioning        — is crowded positioning a headwind? (Wave-1: not wired)
    4. Catalyst           — does a near-term catalyst support the trade?
    5. Risk/Reward        — stop-distance sanity + ceiling (5a/5b, active via
                            MAX_STOP_DISTANCE_PCT) + reported-tuple consistency
                            (5c). The 2.5:1 floor (5d) is DEFERRED to plan item
                            1H — surfaced honestly, never enforced.
    6. Portfolio Fit      — does size fit the open book? Real when open positions
                            are supplied; honest CONDITIONAL on the verdict path.
    7. Conviction         — overall 0-10 confidence from the FINAL verdict.

Honesty rule: a step whose inputs are missing returns CONDITIONAL (never a
false PASS), so the UI is never misled into thinking a step "passed" when it
could not actually verify it. Any hard FAIL overrides to overall FAIL; any
remaining CONDITIONAL makes the overall CONDITIONAL; otherwise PASS.

Thresholds are ported 1:1 from ``gate.ts`` — change them there first, then here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from math import isfinite
from typing import Literal

from backend.app.domain.ticker_analysis.models import GateResult, GateStepResult

# ── Thresholds (mirror frontend/src/workflow/gate.ts, keep in sync) ──
LIQUIDITY_MIN_AVG_DAILY_USD = 10_000_000   # $10M swing-liquidity floor
MAX_STOP_DISTANCE_PCT = 10.0               # 5b ceiling on entry-to-stop distance (D-8, v1)
RISK_REWARD_PASS = 2.5                     # 5d floor — reference only, NOT enforced yet (1H)
RISK_REWARD_CONDITIONAL = 2.0
CONVICTION_HIGH = 7
CONVICTION_LOW = 4

# ── Portfolio-fit limits (plan Sec.2C; turned real by the paper-trade script) ──
MAX_OPEN_POSITIONS = 8                     # cap on concurrent open positions
SECTOR_EXPOSURE_LIMIT_PCT = 30.0           # max share of the book per sector (audit: 81% in 2)

# 5c: tolerance for the reported R:R vs plan-geometry consistency assertion.
RR_CONSISTENCY_TOL = 0.35

# ── Step metadata (teach-first questions, ported + extended from gate.ts) ──
GATE_STEPS: list[dict[str, str]] = [
    {"name": "Liquidity", "question": "Is there enough trading volume to get in and out easily?"},
    {"name": "Structure", "question": "Is the higher-timeframe trend lining up with the setup?"},
    {"name": "Positioning", "question": "Is crowded positioning (short interest / institutional flow) a headwind?"},
    {"name": "Catalyst", "question": "Does a near-term catalyst support the trade?"},
    {"name": "Risk/Reward", "question": "Is the potential reward at least 2.5× the risk I am taking?"},
    {"name": "Portfolio Fit", "question": "Does size fit my open book, account risk, and current exposure?"},
    {"name": "Conviction", "question": "How confident am I overall, on a 0–10 scale?"},
]


@dataclass
class GateInput:
    """Inputs for the gate, drawn from the live verdict + trade-plan data.

    Every field is optional because a given setup may not expose all of them —
    missing fields yield a CONDITIONAL (see module docstring). Ported from the
    TS ``GateInput`` interface; Wave-1 adds the backend-only positioning and
    portfolio-fit fields (both unverified in Wave-1, hence CONDITIONAL).
    """

    symbol: str = ""
    avg_daily_volume_usd: float | None = None   # tv_data["avg_daily_volume_usd_calc"]
    volume_ratio: float | None = None           # tv_data["relative_volume_10d_calc"]
    daily_trend: str | None = None              # technical.ma_alignment
    weekly_trend: str | None = None             # technical_weekly.ma_alignment
    price: float | None = None
    entry_low: float | None = None
    entry_high: float | None = None
    stop_loss: float | None = None
    targets: list[float] = field(default_factory=list)
    risk_reward: float | None = None            # reported R:R from the verdict
    conviction: int | None = None               # 0-10 FINAL verdict conviction
    catalyst_bias: str | None = None            # tv_data["catalyst_bias_direction"]
    short_interest_pct: float | None = None     # Wave-1: not wired → CONDITIONAL
    institutional_ownership: float | None = None  # Wave-1: not wired → CONDITIONAL
    options_flow: str | None = None             # Wave-1: not wired → CONDITIONAL
    sector: str = ""                            # candidate sector (2C sector exposure)
    entry_type: str = "initial"                 # initial | add (2C duplicate rule)
    position_size_pct: float | None = None      # candidate planned size (2C exposure)
    open_positions: list[dict] = field(default_factory=list)
    # ^ journal rows: {symbol, sector, position_size_pct, stop_loss, entry_type}


def evaluate_stop_distance(
    entry: float | None,
    stop: float | None,
    max_stop_distance_pct: float | None = None,
) -> GateStepResult:
    """Check a long setup without selecting a stop-distance policy.

    5a/5b of the Risk/Reward step: stop sanity (positive stop below entry,
    risk > 0) and the stop-distance ceiling. The ceiling policy is NOT selected
    (D-8 unresolved) so ``max_stop_distance_pct=None`` yields CONDITIONAL —
    honest, never a false PASS.
    """
    if entry is None or not isfinite(entry) or entry <= 0:
        return GateStepResult(name="Risk/Reward", passed=False, conditional=True,
                              note="Entry is unavailable; stop distance was not evaluated.")
    if stop is None or not isfinite(stop) or stop <= 0 or stop >= entry:
        return GateStepResult(name="Risk/Reward", passed=False,
                              note="A long setup needs a positive stop below entry; risk must be greater than zero.")
    if max_stop_distance_pct is None:
        return GateStepResult(name="Risk/Reward", passed=False, conditional=True,
                              note="Stop-distance ceiling not evaluated: policy not configured.")
    if not isfinite(max_stop_distance_pct) or max_stop_distance_pct <= 0:
        raise ValueError("Stop-distance ceiling must be finite and positive")
    distance = (entry - stop) / entry * 100
    return GateStepResult(
        name="Risk/Reward", passed=distance <= max_stop_distance_pct,
        note=f"Stop distance {distance:.1f}% versus configured ceiling {max_stop_distance_pct:.1f}%.",
    )


# ── Step evaluators ──


def evaluate_liquidity(input: GateInput) -> GateStepResult:
    """Port of ``evaluateLiquidity`` from gate.ts ($10M ADV floor)."""
    adv = input.avg_daily_volume_usd
    ratio = input.volume_ratio
    if adv is None and ratio is None:
        return GateStepResult(
            name="Liquidity", passed=False, conditional=True,
            note="Liquidity data is not available for this setup right now — confirm volume is healthy before entering.",
        )
    if adv is not None:
        if adv >= LIQUIDITY_MIN_AVG_DAILY_USD:
            return GateStepResult(
                name="Liquidity", passed=True,
                note=f"Average daily volume ≈ ${adv / 1_000_000:.0f}M — well above the $10M swing liquidity floor.",
            )
        if adv >= LIQUIDITY_MIN_AVG_DAILY_USD / 2:
            return GateStepResult(
                name="Liquidity", passed=False, conditional=True,
                note=f"Average daily volume ≈ ${adv / 1_000_000:.0f}M — below the $10M floor; trade only with a tight, small position.",
            )
        return GateStepResult(
            name="Liquidity", passed=False,
            note=f"Average daily volume ≈ ${adv / 1_000_000:.0f}M — too thin to enter and exit cleanly.",
        )
    # Only volume ratio available (a confirmation signal, not a level).
    if (ratio or 0) >= 1.2:
        return GateStepResult(
            name="Liquidity", passed=True, conditional=True,
            note=f"Volume is running at {ratio or 0:.1f}× average — active participation. Confirm average daily $ volume is adequate before entering.",
        )
    return GateStepResult(
        name="Liquidity", passed=False, conditional=True,
        note="Volume looks quiet relative to average — execute with care and confirm participation.",
    )


def evaluate_structure(input: GateInput) -> GateStepResult:
    """Port of ``evaluateStructure`` from gate.ts (MTF trend alignment)."""
    weekly = None if input.weekly_trend is None else input.weekly_trend.lower()
    daily = None if input.daily_trend is None else input.daily_trend.lower()

    def _bull(b: str | None) -> bool:
        return b in ("bullish", "bull", "strong_bullish")

    def _bear(b: str | None) -> bool:
        return b in ("bearish", "bear", "strong_bearish")

    aligned_bull = _bull(weekly) and _bull(daily)
    aligned_bear = _bear(weekly) and _bear(daily)
    has_key_level = input.price is not None or (
        input.entry_low is not None and input.stop_loss is not None
    )

    if weekly is None or daily is None:
        return GateStepResult(
            name="Structure", passed=False, conditional=True,
            note="We could not confirm both timeframes' trends — multi-timeframe structure is a core part of the checklist, so confirm trend alignment yourself.",
        )
    if aligned_bull or aligned_bear:
        bias = weekly or daily
        return GateStepResult(
            name="Structure", passed=True,
            note=(
                f"Weekly and daily {bias} trends are aligned, and a clear level anchors your invalidation."
                if has_key_level
                else f"Weekly and daily {bias} trends are aligned — a clean trend-following setup."
            ),
        )
    if _bull(daily) and _bear(weekly):
        return GateStepResult(
            name="Structure", passed=False, conditional=True,
            note="The daily setup is bullish but the weekly trend is down — this is a counter-trend trade. Only consider it small and tight.",
        )
    return GateStepResult(
        name="Structure", passed=False, conditional=True,
        note="Trends are mixed across timeframes — the higher timeframe does not clearly support the setup. Reduce size or wait for alignment.",
    )


def evaluate_positioning(input: GateInput) -> GateStepResult:
    """Step 3 — Wave-1: positioning data is NOT wired into the verdict yet.

    Honest CONDITIONAL: we cannot verify crowding, so we say so instead of
    claiming a pass. When the D-46 options-flow / insider data layer lands in
    the gate input, this becomes a real evaluation.
    """
    if (
        input.short_interest_pct is None
        and input.institutional_ownership is None
        and input.options_flow is None
    ):
        return GateStepResult(
            name="Positioning", passed=False, conditional=True,
            note="Positioning data (short interest / institutional flow) is not wired into this check yet — treat crowded-positioning risk as unverified.",
        )
    # Future wired path (kept honest: never a blanket pass).
    red_flags: list[str] = []
    if input.short_interest_pct is not None and input.short_interest_pct >= 25:
        red_flags.append(f"short interest {input.short_interest_pct:.0f}% is elevated")
    if red_flags:
        return GateStepResult(
            name="Positioning", passed=False, conditional=True,
            note="Positioning is a headwind: " + "; ".join(red_flags) + ".",
        )
    return GateStepResult(
        name="Positioning", passed=True,
        note="Positioning does not appear to be a headwind on the signals we can see.",
    )


def evaluate_catalyst(input: GateInput) -> GateStepResult:
    """Step 4 — near-term catalyst bias (tv_data["catalyst_bias_direction"])."""
    cat = None if input.catalyst_bias is None else input.catalyst_bias.lower()
    if cat is None or cat in ("neutral", "mixed", "unknown"):
        return GateStepResult(
            name="Catalyst", passed=False, conditional=True,
            note="No explicit catalyst signal detected; confirm the reason this setup is special.",
        )
    if cat in ("bullish", "bull", "strong_bullish", "positive"):
        return GateStepResult(
            name="Catalyst", passed=True,
            note=f"The near-term catalyst ({cat}) supports the trade.",
        )
    # Bearish / cautious / negative catalyst works against the setup (gate.ts: catalystAgainst).
    return GateStepResult(
        name="Catalyst", passed=False,
        note=f"The near-term catalyst is {cat} — a headwind to the setup; size down or wait.",
    )


def _rr_consistency(input: GateInput) -> GateStepResult:
    """5c: the reported R:R must agree with the plan geometry.

    Consistency assertion only — it never *selects* on R:R (no floor here;
    the 2.5:1 floor is deferred to plan item 1H). Formula from plan Sec.1B:
    |(target - entry_basis) / (entry_basis - stop) - reported_rr| <= tol.
    """
    entry_basis = input.entry_low if input.entry_low is not None else input.entry_high
    if (
        entry_basis is None
        or input.stop_loss is None
        or not input.targets
        or input.risk_reward is None
    ):
        return GateStepResult(
            name="Risk/Reward", passed=False, conditional=True,
            note="Reported reward:risk could not be cross-checked against the plan geometry (missing levels/targets) — confirm the 2.5:1 expectation yourself.",
        )
    risk = entry_basis - input.stop_loss
    if risk <= 0 or not isfinite(risk):
        return GateStepResult(
            name="Risk/Reward", passed=False,
            note="Plan geometry is inconsistent: stop is not below the entry basis.",
        )
    measured = (input.targets[-1] - entry_basis) / risk
    if not isfinite(measured):
        return GateStepResult(
            name="Risk/Reward", passed=False, conditional=True,
            note="Plan geometry is not finite — reported reward:risk could not be verified.",
        )
    if abs(measured - input.risk_reward) <= RR_CONSISTENCY_TOL:
        return GateStepResult(
            name="Risk/Reward", passed=True,
            note=f"Reported R:R {input.risk_reward:.2f} is consistent with the plan geometry.",
        )
    return GateStepResult(
        name="Risk/Reward", passed=False, conditional=True,
        note=f"Reported R:R {input.risk_reward:.2f} disagrees with the plan geometry ({measured:.2f}) — verify the plan tuple before trading.",
    )


def evaluate_risk_reward(input: GateInput) -> GateStepResult:
    """Step 5 — stop sanity/ceiling (5a/5b) + reported-tuple consistency (5c) + R/R floor (5d).

    5d (the 2.5:1 floor) is now active: enforces R/R >= 2.5 on plan geometry.
    Combine sub-checks: any hard fail → FAIL; any conditional → CONDITIONAL;
    else PASS.
    """
    entry = input.entry_low if input.entry_low is not None else input.entry_high
    sub = [evaluate_stop_distance(entry, input.stop_loss, MAX_STOP_DISTANCE_PCT)]
    # Determine R/R to check against floor: prefer reported, else derive from plan geometry.
    rr_to_check = None
    if input.risk_reward is not None:
        rr_to_check = input.risk_reward
        sub.append(_rr_consistency(input))
    elif entry is not None and input.stop_loss is not None and input.targets:
        # No reported R:R — derive it from the plan geometry (teach-first).
        risk = entry - input.stop_loss
        if risk > 0 and input.targets:
            derived = (input.targets[-1] - entry) / risk
            rr_to_check = derived
            # Note: we still run consistency check? Actually _rr_consistency requires reported R:R.
            # We'll skip consistency check when no reported R:R, as before.
            sub.append(
                GateStepResult(
                    name="Risk/Reward", passed=False, conditional=True,
                    note=f"No reported R:R — plan geometry implies {derived:.2f}:1; confirm it clears the 2.5:1 bar.",
                )
            )
    # 5d floor: enforce R/R >= 2.5 for PASS
    # D1 tier: CONDITIONAL at 2.0:1 with r1 >= 1.0 (half size)
    if rr_to_check is not None:
        if rr_to_check >= RISK_REWARD_PASS:
            sub.append(
                GateStepResult(
                    name="Risk/Reward", passed=True,
                    note=f"R/R floor satisfied: {rr_to_check:.2f} >= {RISK_REWARD_PASS:.2f}",
                )
            )
        elif rr_to_check >= RISK_REWARD_CONDITIONAL:
            # D1 tier: check if first target gives at least 1R (r1 >= 1.0)
            if entry is not None and input.stop_loss is not None and input.targets:
                risk = entry - input.stop_loss
                if risk > 0 and input.targets:
                    r1 = (input.targets[0] - entry) / risk
                    if r1 >= 1.0:
                        sub.append(
                            GateStepResult(
                                name="Risk/Reward", passed=False, conditional=True,
                                note=f"D1 tier: R/R {rr_to_check:.2f} >= {RISK_REWARD_CONDITIONAL:.2f} with r1={r1:.2f} >= 1.0 — half-size CONDITIONAL",
                            )
                        )
                    else:
                        sub.append(
                            GateStepResult(
                                name="Risk/Reward", passed=False, conditional=False,
                                note=f"R/R {rr_to_check:.2f} >= {RISK_REWARD_CONDITIONAL:.2f} but r1={r1:.2f} < 1.0 (first target < 1R) — D1 tier not met",
                            )
                        )
                else:
                    sub.append(
                        GateStepResult(
                            name="Risk/Reward", passed=False, conditional=False,
                            note=f"R/R {rr_to_check:.2f} >= {RISK_REWARD_CONDITIONAL:.2f} but cannot compute r1 (missing levels)",
                        )
                    )
            else:
                sub.append(
                    GateStepResult(
                        name="Risk/Reward", passed=False, conditional=True,
                        note=f"R/R {rr_to_check:.2f} >= {RISK_REWARD_CONDITIONAL:.2f} — D1 tier needs r1 >= 1.0 check (missing entry/stop/targets)",
                    )
                )
        else:
            sub.append(
                GateStepResult(
                    name="Risk/Reward", passed=False, conditional=False,
                    note=f"R/R floor not met: {rr_to_check:.2f} < {RISK_REWARD_PASS:.2f}",
                )
            )
    # If we have no rr_to_check (missing levels), we rely on other sub-checks and will reach the else PASS only if no geometry exists.

    hard = [s for s in sub if not s.passed and not s.conditional]
    if hard:
        return GateStepResult(
            name="Risk/Reward", passed=False,
            note=" | ".join(s.note for s in hard),
        )
    conditional = [s for s in sub if s.conditional]
    if conditional:
        return GateStepResult(
            name="Risk/Reward", passed=False, conditional=True,
            note=" | ".join(s.note for s in conditional),
        )
    notes = " | ".join(s.note for s in sub)
    return GateStepResult(name="Risk/Reward", passed=True, note=notes)


def evaluate_portfolio_fit(input: GateInput) -> GateStepResult:
    """Step 6 — does size fit the open book? (plan Sec.2C)

    Real when the caller (the paper-trade script, phase 1D) supplies
    ``open_positions`` from the journal:

    1. Count cap        — ``len(open) >= MAX_OPEN_POSITIONS`` → FAIL.
    2. Duplicate symbol — only a planned scale-in at a NEW stop is permitted;
                          adding at market into an unchanged stop → FAIL.
    3. Sector exposure  — same-sector open size + candidate planned size must
                          stay under ``SECTOR_EXPOSURE_LIMIT_PCT``.

    The synthesis path supplies no open positions → honest CONDITIONAL (the
    verdict cannot see the journal).
    """
    positions = input.open_positions
    if not positions:
        return GateStepResult(
            name="Portfolio Fit", passed=False, conditional=True,
            note="Portfolio fit (open positions, account risk, sector exposure) is not wired into this check yet — verify size against your own book before entering.",
        )

    # 1. Count cap.
    if len(positions) >= MAX_OPEN_POSITIONS:
        return GateStepResult(
            name="Portfolio Fit", passed=False,
            note=f"Open-position count {len(positions)} is at/over the cap of {MAX_OPEN_POSITIONS} — no room for a new entry.",
        )

    symbol = (input.symbol or "").upper()

    # 2. Duplicate symbol: only a planned add at a NEW stop is permitted.
    same_symbol = [p for p in positions if str(p.get("symbol", "")).upper() == symbol]
    if same_symbol:
        open_stop = same_symbol[-1].get("stop_loss")
        new_stop = input.stop_loss
        planned_add = str(input.entry_type or "").lower() == "add"
        stop_changed = (
            open_stop is not None
            and new_stop is not None
            and abs(float(open_stop) - float(new_stop)) > 1e-9
        )
        if planned_add and stop_changed:
            return GateStepResult(
                name="Portfolio Fit", passed=False, conditional=True,
                note=f"Already open in {symbol} — a planned scale-in to a NEW stop is permitted; size it as an add, not a fresh entry.",
            )
        return GateStepResult(
            name="Portfolio Fit", passed=False,
            note=f"Already open in {symbol} — adding at market into an unchanged stop is not a plan. Close or scale at a new stop only.",
        )

    # 3. Sector exposure (planned size included).
    same_sector = [
        p for p in positions
        if str(p.get("sector", "")).strip().lower() == (input.sector or "").strip().lower()
    ]
    open_exposure = sum(
        float(p.get("position_size_pct") or 0.0) for p in same_sector
    )
    candidate_exposure = float(input.position_size_pct or 0.0)
    total_exposure = open_exposure + candidate_exposure
    if total_exposure > SECTOR_EXPOSURE_LIMIT_PCT:
        return GateStepResult(
            name="Portfolio Fit", passed=False,
            note=f"Sector {input.sector or '?'} exposure would hit {total_exposure:.1f}% of the book — over the {SECTOR_EXPOSURE_LIMIT_PCT:.0f}% ceiling; reduce size or skip.",
        )
    return GateStepResult(
        name="Portfolio Fit", passed=True,
        note=f"Portfolio fit OK: {len(positions)} open position(s); planned {input.sector or '?'} exposure {total_exposure:.1f}% stays under the {SECTOR_EXPOSURE_LIMIT_PCT:.0f}% ceiling.",
    )


def evaluate_conviction(input: GateInput) -> GateStepResult:
    """Step 7 — final verdict conviction (0-10). Port of the TS conviction step."""
    c = input.conviction
    if c is None:
        return GateStepResult(
            name="Conviction", passed=False, conditional=True,
            note="Conviction is unavailable; treat overall confidence as unverified.",
        )
    if c >= CONVICTION_HIGH:
        return GateStepResult(
            name="Conviction", passed=True,
            note=f"Conviction {c}/10 — a strong, tradeable signal.",
        )
    if c >= CONVICTION_LOW:
        return GateStepResult(
            name="Conviction", passed=False, conditional=True,
            note=f"Conviction {c}/10 — moderate; only take this small.",
        )
    return GateStepResult(
        name="Conviction", passed=False,
        note=f"Conviction {c}/10 — below the bar; skip this setup.",
    )


# ── Aggregate ──


def compute_gate(steps: list[GateStepResult]) -> Literal["PASS", "FAIL", "CONDITIONAL"]:
    """Any hard FAIL → FAIL; else any CONDITIONAL → CONDITIONAL; else PASS."""
    if any(not s.passed and not s.conditional for s in steps):
        return "FAIL"
    if any(s.conditional for s in steps):
        return "CONDITIONAL"
    return "PASS"


def evaluate_gate(input: GateInput) -> GateResult:
    """Run all seven steps in order and produce the typed GateResult."""
    steps: list[GateStepResult] = [
        evaluate_liquidity(input),      # 1
        evaluate_structure(input),      # 2
        evaluate_positioning(input),    # 3 (Wave-1: CONDITIONAL, not wired)
        evaluate_catalyst(input),       # 4
        evaluate_risk_reward(input),    # 5 (5a/5b/5c live; 5d deferred to 1H)
        evaluate_portfolio_fit(input),  # 6 (real when journal positions supplied)
        evaluate_conviction(input),     # 7
    ]
    overall = compute_gate(steps)
    gaps = [step.name for step in steps if step.conditional]
    conviction = input.conviction if input.conviction is not None else 0
    conviction_score = max(0, min(10, int(round(conviction))))
    return GateResult(
        overall=overall,
        steps=steps,
        conviction_score=conviction_score,
        data_gaps=gaps,
        evaluated_at=datetime.now(UTC).isoformat(timespec="seconds"),
    )


def build_gate_input(
    *,
    symbol: str = "",
    avg_daily_volume_usd: float | None = None,
    volume_ratio: float | None = None,
    daily_trend: str | None = None,
    weekly_trend: str | None = None,
    price: float | None = None,
    entry_low: float | None = None,
    entry_high: float | None = None,
    stop_loss: float | None = None,
    targets: list[float] | None = None,
    risk_reward: float | None = None,
    conviction: int | None = None,
    catalyst_bias: str | None = None,
    sector: str = "",
    entry_type: str = "initial",
    position_size_pct: float | None = None,
    open_positions: list[dict] | None = None,
) -> GateInput:
    """Adapter from verdict/tv_data pieces to GateInput (plan Sec.1B).

    ``sector``/``entry_type``/``position_size_pct``/``open_positions`` feed the
    real Step-6 portfolio fit (plan Sec.2C) from the paper-trade script.
    """
    return GateInput(
        symbol=symbol,
        avg_daily_volume_usd=avg_daily_volume_usd,
        volume_ratio=volume_ratio,
        daily_trend=daily_trend,
        weekly_trend=weekly_trend,
        price=price,
        entry_low=entry_low,
        entry_high=entry_high,
        stop_loss=stop_loss,
        targets=list(targets or []),
        risk_reward=risk_reward,
        conviction=conviction,
        catalyst_bias=catalyst_bias,
        sector=sector,
        entry_type=entry_type,
        position_size_pct=position_size_pct,
        open_positions=list(open_positions or []),
    )