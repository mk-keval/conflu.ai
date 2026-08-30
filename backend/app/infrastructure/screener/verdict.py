# Verdict builder — plain-English per-ticker "second opinion" for the Screener.
#
# The screener table shows many institutional proxy columns (Confluence T/M/V/Q/F,
# RS Rtg, Inst Q, Conv, ADX, ATR%) that are accurate but cryptic to a beginner.
# This module produces a concise plain-English verdict per candidate so a novice
# can tell at a glance whether a ticker is a clean swing entry, needs to wait,
# or should be avoided — WITHOUT contradicting the downstream ticker page.
#
# The verdict *action* uses the same vocabulary the deep-analysis ticker page and
# the Morning Brief emit (STRONG_BUY / BUY / ACCUMULATE / WATCH / AVOID), so a
# screen-level verdict is consistent with the verdict reached on the ticker page.
#
# It is snapshot-based (operates on the confluence breakdown + elite enrichment +
# TV snapshot columns already computed for the screener row) so it adds no OHLCV
# fetch to the fast discovery path.

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ── Verdict model ──────────────────────────────────────────────────────────

@dataclass
class Verdict:
    """Plain-English second opinion for one screened ticker."""
    action: str            # STRONG_BUY / BUY / ACCUMULATE / WATCH / AVOID
    tone: str              # positive / caution / negative (drives UI color)
    summary: str           # one plain-English sentence explaining the action
    reasons: list[str] = field(default_factory=list)  # 1-3 plain-English bullets

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "tone": self.tone,
            "summary": self.summary,
            "reasons": list(self.reasons),
        }


# ── Letter-grade → verdict mapping ─────────────────────────────────────────
# Kept in sync with morning_brief._rating_to_verdict so the screener verdict
# matches the rest of the app. Letters are what TVConfluenceScorer emits.
_RATING_TO_ACTION: dict[str, str] = {
    "A+": "STRONG_BUY", "A": "BUY", "B+": "ACCUMULATE",
    "B": "WATCH", "C": "HOLD", "D": "AVOID",
}
# HOLD is surfaced as WATCH to a novice (they don't need the HOLD nuance).
_ACTION_DISPLAY: dict[str, str] = {
    "STRONG_BUY": "Strong Buy", "BUY": "Buy", "ACCUMULATE": "Accumulate",
    "WATCH": "Watch", "HOLD": "Watch", "AVOID": "Avoid",
}

_TONE: dict[str, str] = {
    "STRONG_BUY": "positive", "BUY": "positive", "ACCUMULATE": "positive",
    "WATCH": "caution", "HOLD": "caution", "AVOID": "negative",
}

# RSI thresholds for the "overbought / oversold" caveat
_RSI_OVERBOUGHT = 70
_RSI_OVERSOLD = 30


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        f = float(value)
        return f
    except (TypeError, ValueError):
        return None


def build_verdict(
    symbol: str,
    score_total: int,
    rating: str,
    breakdown: dict[str, Any] | None,
    elite: dict[str, Any] | None,
    tv_data: dict[str, Any] | None,
) -> Verdict:
    """Build a plain-English verdict for one screened ticker.

    All inputs come from the screener row already in memory — no extra fetches.
    """
    breakdown = breakdown or {}
    elite = elite or {}
    tv_data = tv_data or {}

    action = _RATING_TO_ACTION.get((rating or "").upper(), "WATCH")

    # ---- Factor pulls (plain-English reasons) ----
    reasons: list[str] = []

    trend = _num(breakdown.get("trend"))
    momentum = _num(breakdown.get("momentum"))

    # Verdict language: up → clean/dip; flat/weak → choppy; down → broken.
    if trend is not None and trend >= 20:
        reasons.append("Strong uptrend — price is holding above its key moving averages")
    elif trend is not None and trend < 10:
        reasons.append("Weak / broken trend — price is struggling below key moving averages")

    if momentum is not None and momentum >= 16:
        reasons.append("Solid momentum behind the move")
    elif momentum is not None and momentum < 6:
        reasons.append("Little momentum right now — may be early")

    vol = _num(breakdown.get("volume"))
    if vol is not None and vol >= 12:
        reasons.append("Strong volume confirming the move")

    # ---- Second opinion: caution flags a beginner can't see ----
    rsi = _num(tv_data.get("RSI"))
    if rsi is not None and rsi >= _RSI_OVERBOUGHT:
        reasons.append(f"⚠️ Overbought (RSI {round(rsi)}) — chasing here is risky; wait for a pullback")
        if action in ("STRONG_BUY", "BUY", "ACCUMULATE"):
            # Keep the directional action but tag the caution tone below.
            pass

    adx = _num(tv_data.get("ADX"))
    if adx is not None and adx < 20:
        reasons.append("Low trend strength (ADX below 20) — market may be choppy / range-bound")

    conviction = (elite.get("signal_conviction") or "low").lower()
    conflicts = elite.get("factor_conflicts")
    if isinstance(conflicts, list) and conflicts:
        reasons.append("⚠️ Conflicting signals — " + "; ".join(str(c) for c in conflicts[:2]))
    elif conviction == "low":
        reasons.append("Low conviction — not a high-confidence setup")

    # ---- Summary sentence ----
    display = _ACTION_DISPLAY.get(action, "Watch")
    # Tone is downgraded to caution if an overbought/conflict flag is present.
    tone = _TONE.get(action, "caution")
    has_flag = any("⚠️" in r for r in reasons)
    if action in ("STRONG_BUY", "BUY", "ACCUMULATE"):
        if has_flag:
            tone = "caution"

    summary = f"{symbol}: {display}."
    if action in ("STRONG_BUY", "BUY", "ACCUMULATE"):
        if score_total is not None and score_total >= 60:
            summary += " A strong confluence setup."
        if has_flag:
            summary += " But the price isn't a clean entry right now — wait for a pullback rather than chasing."
        else:
            summary += " A solid swing candidate — the key factors line up."
    elif action in ("WATCH", "HOLD"):
        summary += " No clear edge right now — not a clean setup to act on. Add to your watchlist and re-check it."
    else:  # AVOID
        summary += " Avoid for now — price or quality signals argue against a long setup."

    # Fallback: never show an empty reasons list.
    if not reasons:
        reasons.append("Snapshot signals are mixed — no strong single factor to hang a trade on.")

    return Verdict(
        action=action,
        tone=tone,
        summary=summary,
        reasons=reasons,
    )
