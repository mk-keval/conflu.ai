# Mentor narration — deterministic veteran reasoning chain (P2.1)
"""
Turns module outputs + plan geometry into the veteran's three answers:

- **Why this** — which module confluences actually back the setup
- **Why now** — the catalyst or liquidity event that times it
- **What kills it** — the invalidation LEVEL and the CONDITION that ends
  the trade (a stop without a stated condition is not an answer)

Template-based only: zero external calls, deterministic, testable.
Optional LLM enhancement rides on the existing education hook downstream —
this layer never depends on it.

Also exposes :func:`brief_thesis_line` for P2.2 one-liners on Morning
Brief cards, where only screener-grade data exists.
"""

from __future__ import annotations

from typing import Any

from backend.app.domain.ticker_analysis.models import (
    AnalysisVerdict,
    EarningsAnalysis,
    FundamentalAnalysis,
    MentorNarration,
    SentimentAnalysis,
    TechnicalAnalysis,
)

_MAX_WHY_THIS = 4


def _fmt(value: float | None, suffix: str = "") -> str:
    if value is None:
        return "?"
    return f"{value:g}{suffix}"


def _why_this(
    technical: TechnicalAnalysis | None,
    fundamental: FundamentalAnalysis | None,
    earnings: EarningsAnalysis | None,
    sentiment: SentimentAnalysis | None,
) -> list[str]:
    lines: list[str] = []
    if technical is not None:
        if technical.ma_alignment == "bullish":
            trend_word = {
                "strong": "trending hard",
                "extreme": "in a powerful trend",
                "moderate": "trending",
            }.get(technical.adx_verdict, "holding its trend")
            line = f"Price is {trend_word} with moving averages stacked bullishly"
            if technical.adx is not None:
                line += f" (ADX {_fmt(technical.adx)})"
            lines.append(line + ".")
        if technical.pullback_quality in ("A+", "A"):
            lines.append(
                f"Pullback quality {technical.pullback_quality} — the retest is "
                "institutional-grade, not noise."
            )
        if technical.structure == "bullish":
            lines.append("Market structure is bullish: higher lows into resistance.")
        if technical.volume_ratio is not None and technical.volume_ratio >= 1.5:
            lines.append(
                f"Volume running {_fmt(technical.volume_ratio)}x average — real "
                "participation behind the move."
            )
    if fundamental is not None and fundamental.score >= 0.15:
        positive = next((f for f in fundamental.findings if any(
            w in f.lower() for w in ("✅", "strong", "growth", "quality")
        )), None)
        lines.append(positive or "Fundamental quality clears the bar for swing capital.")
    if earnings is not None and (earnings.last_surprise_pct or 0) > 0 and earnings.beat_rate:
        lines.append(f"Earnings track record supports the story: {earnings.beat_rate} beats.")
    if sentiment is not None and sentiment.score >= 0.25:
        lines.append("Sentiment tailwind: analysts and insiders lean the same way.")
    return lines[:_MAX_WHY_THIS]


def _why_now(
    technical: TechnicalAnalysis | None,
    earnings: EarningsAnalysis | None,
) -> list[str]:
    lines: list[str] = []
    if earnings is not None and (earnings.last_surprise_pct or 0) > 3:
        surprise = earnings.last_surprise_pct or 0
        lines.append(
            f"Fresh catalyst: last quarter beat by {surprise:.1f}% — momentum "
            "buyers have new fuel."
        )
    if earnings is not None and earnings.days_until_earnings is not None:
        days = earnings.days_until_earnings
        if 0 <= days <= 14:
            lines.append(
                f"Earnings lands in {days}d — the catalyst window is open; "
                "size down through the print."
            )
    if technical is not None:
        if technical.bb_position == "above_upper" and technical.rsi is not None and technical.rsi > 70:
            # Expansion, not caution: breakout contexts live above the band.
            lines.append("Pressing the upper Bollinger band — expansion phase in progress.")
        if (
            technical.key_resistance
            and all(r > 0 for r in technical.key_resistance[:1])
        ):
            nearest = min(technical.key_resistance)
            lines.append(
                f"Liquidity overhead at {_fmt(nearest)} — that's where the trade "
                "gets paid; structure below still has to hold."
            )
    if not lines:
        lines.append(
            "No fresh catalyst yet — this is a staged setup: enter on "
            "confirmation, not anticipation."
        )
    return lines


def _what_kills_it(verdict: AnalysisVerdict, price: float | None) -> list[str]:
    kills: list[str] = []
    # Level-bearing plans — including WATCH-with-levels, which is how live
    # marginal setups actually appear — always state their invalidation.
    if verdict.stop_loss is not None and verdict.action in ("BUY", "SELL", "ACCUMULATE", "WATCH"):
        side = "below" if verdict.action != "SELL" else "above"
        anchor = (
            "the structural invalidation"
            if verdict.entry_zone_low is not None
            else "the setup"
        )
        line = f"A close {side} {_fmt(verdict.stop_loss)} breaks {anchor} — exit, no averaging down."
        kills.append(line)
    plan = verdict.trade_plan
    if plan is not None and plan.max_hold_days:
        kills.append(
            f"{plan.max_hold_days} calendar days without progress kills the thesis "
            "(time stop) — swings need the thesis to work on schedule."
        )
    if verdict.trade_plan is not None and verdict.trade_plan.move_to_breakeven_at_r:
        r = verdict.trade_plan.move_to_breakeven_at_r
        kills.append(
            f"At +{_fmt(r)}R the stop moves to breakeven — after that, the market "
            "pays you to stay wrong-free."
        )
    if not kills:
        kills.append("No plan, no invalidation — that's exactly why there's no position.")
    return kills


def _thesis_one_liner(symbol: str, verdict: AnalysisVerdict, price: float | None) -> str:
    action = verdict.action
    zone = ""
    if verdict.entry_zone_low is not None and verdict.entry_zone_high is not None:
        zone = f" zone {_fmt(verdict.entry_zone_low)}–{_fmt(verdict.entry_zone_high)}"
    rr = (
        f" at {verdict.risk_reward:.1f}R"
        if verdict.risk_reward is not None
        else ""
    )
    return f"{action} {symbol}:{zone}{rr} — {verdict.thesis}" if verdict.thesis else (
        f"{action} {symbol}:{zone}{rr}."
    )


def build_narration(
    *,
    symbol: str,
    price: float | None,
    verdict: AnalysisVerdict,
    technical: TechnicalAnalysis | None,
    fundamental: FundamentalAnalysis | None,
    earnings: EarningsAnalysis | None,
    sentiment: SentimentAnalysis | None,
) -> MentorNarration:
    """Deterministic reasoning chain attached to every verdict."""
    return MentorNarration(
        why_this=_why_this(technical, fundamental, earnings, sentiment),
        why_now=_why_now(technical, earnings),
        what_kills_it=_what_kills_it(verdict, price),
        thesis_one_liner=_thesis_one_liner(symbol, verdict, price),
    )


# ─────────────────────────────────────────────────────────────
# P2.2 — Morning Brief one-liner (screener-grade inputs only)
# ─────────────────────────────────────────────────────────────


def brief_thesis_line(
    *,
    symbol: str,
    verdict: str,
    entry: float,
    stop_loss: float,
    targets: list[float],
    tv_data: dict[str, Any] | None,
    rs_composite: float | None = None,
) -> str:
    """One trader-style line for a brief card from available screen data."""
    tv = tv_data or {}

    def _num(key: str) -> float | None:
        try:
            v = tv.get(key)
            return float(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    parts: list[str] = []
    adx = _num("ADX")
    ema50 = _num("EMA50")
    close = _num("close") or _num("price")
    if close is not None and ema50 is not None:
        if close > ema50:
            parts.append("trend support holding above the 50-EMA")
        else:
            parts.append("reclaiming the 50-EMA is the first tell")
    elif adx is not None and adx >= 25:
        parts.append(f"ADX {_fmt(adx)} says the move has institutional follow-through")

    high52 = _num("price_52_week_high")
    if close is not None and high52 is not None and high52 > 0 and close >= high52 * 0.97:
        parts.append("pressing 52-week highs — supply is absent overhead")

    rvol = _num("relative_volume_10d_calc")
    if rvol is not None and rvol >= 1.5:
        parts.append(f"rvol {_fmt(rvol)}x confirms participation")

    if rs_composite is not None:
        if rs_composite >= 70:
            parts.append(f"RS percentile {_fmt(rs_composite)} vs market")
        elif rs_composite <= 30:
            parts.append(f"RS percentile {_fmt(rs_composite)} — fighting the tape")

    risk = ""
    if entry > 0 and stop_loss > 0:
        risk = f" Risk from {_fmt(stop_loss)}."
    target_txt = ""
    if targets:
        target_txt = f" First target {_fmt(targets[0])}."

    body = "; ".join(parts) if parts else "confluence-ranked setup"
    return f"{verdict} {symbol}: {body}.{risk}{target_txt}"
