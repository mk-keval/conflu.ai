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
    ChartReadingAnalysis,
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


def _all_chart_signals(cr):
    """Yield (timeframe_label, signal_kind, event_dict) across all timeframes.

    D-44: Fix for the D-36 regression. The D-36 chart-reading refactor
    moved events under per-timeframe TimeframeChartReading objects
    (cr.daily.bos_events, cr.weekly.bos_events, etc.). Pre-D-36 narration
    read cr.bos_events directly (flat). This helper consolidates the
    nested per-timeframe access so narration sees all signals regardless
    of which timeframe they fired on.

    Note: cr.composite_tpo_profile and cr.mtf_confluence are flat on
    the model (not nested under per-timeframe), so those continue to be
    read directly from cr.
    """
    if cr is None:
        return
    for tf_label, tf_data in (
        ("daily", cr.daily),
        ("weekly", cr.weekly),
        ("4h", cr.h4),
        ("1h", cr.h1),
    ):
        if tf_data is None:
            continue
        for ev in tf_data.bos_events or []:
            yield (tf_label, "bos", ev)
        for ev in tf_data.choch_events or []:
            yield (tf_label, "choch", ev)
        for ev in tf_data.order_blocks or []:
            yield (tf_label, "ob", ev)
        for ev in tf_data.fair_value_gaps or []:
            yield (tf_label, "fvg", ev)
        for ev in tf_data.breakout_events or []:
            yield (tf_label, "breakout", ev)


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
                f"Pullback quality {technical.pullback_quality} — the retest is institutional-grade, not noise."
            )
        if technical.structure == "bullish":
            lines.append("Market structure is bullish: higher lows into resistance.")
        
        # Chart Reading: BOS/CHoCH (D-44: uses helper for per-timeframe access)
        if technical.chart_reading:
            cr = technical.chart_reading
            all_signals = list(_all_chart_signals(cr))

            bos_signals = [ev for _tf, kind, ev in all_signals if kind == "bos"][:2]
            for ev in bos_signals:
                direction = "bullish" if ev["type"] == "bullish_bos" else "bearish"
                tf_label = next(tf for tf, k, e in all_signals if k == "bos" and e is ev)
                lines.append(f"Confirmed {direction} BOS ({tf_label}) at {ev['structure_level']:.2f} with {ev['volume_ratio']:.1f}x volume — structure holding.")

            choch_signals = [ev for _tf, kind, ev in all_signals if kind == "choch"][:2]
            for ev in choch_signals:
                direction = "bullish" if ev["type"] == "bullish_choch" else "bearish"
                tf_label = next(tf for tf, k, e in all_signals if k == "choch" and e is ev)
                lines.append(f"{direction.capitalize()} CHoCH ({tf_label}) confirmed at {ev['confirmation_price']:.2f} — structure shift.")

            # Chart Reading: Order Blocks / FVG (D-44: safe access — the
            # chart-reading builder emits dicts with 'top'/'bottom' for OB
            # and 'top'/'bottom' for FVG, NOT 'midpoint' which is a @property
            # on the dataclass but doesn't survive to_dict()).
            ob_signals = [ev for _tf, kind, ev in all_signals if kind == "ob"][:2]
            for ob in ob_signals:
                if not ob.get("mitigated"):
                    direction = "bullish" if ob["type"] == "bullish_ob" else "bearish"
                    tf_label = next(tf for tf, k, e in all_signals if k == "ob" and e is ob)
                    mid = (ob.get("top", 0) + ob.get("bottom", 0)) / 2 if "top" in ob and "bottom" in ob else ob.get("midpoint", 0)
                    lines.append(f"Unmitigated {direction} Order Block ({tf_label}) at {mid:.2f} — institutional entry zone.")

            fvg_signals = [ev for _tf, kind, ev in all_signals if kind == "fvg"][:2]
            for fvg in fvg_signals:
                if not fvg.get("filled"):
                    direction = "bullish" if fvg["type"] == "bullish_fvg" else "bearish"
                    tf_label = next(tf for tf, k, e in all_signals if k == "fvg" and e is fvg)
                    bottom = fvg.get("bottom", 0)
                    top = fvg.get("top", 0)
                    mid = fvg.get("midpoint", (bottom + top) / 2)
                    lines.append(f"Unfilled {direction} FVG ({tf_label}) {bottom:.2f}-{top:.2f} — price vacuum to fill.")

            # Chart Reading: Volume Profile (D-44: composite_tpo_profile is on
            # TimeframeChartReading, not on ChartReadingAnalysis. Read it from
            # the daily timeframe which is where it's populated.)
            comp = None
            if cr.daily and cr.daily.composite_tpo_profile:
                comp = cr.daily.composite_tpo_profile
            if comp:
                if comp.get("poc_migration") == "up":
                    lines.append(f"Volume Profile POC migrating up to {comp.get('composite_poc', 0):.2f} — accumulation.")
                elif comp.get("poc_migration") == "down":
                    lines.append(f"Volume Profile POC migrating down to {comp.get('composite_poc', 0):.2f} — distribution.")

            # MTF Confluence (still flat on the model)
            if cr.mtf_confluence:
                mtf = cr.mtf_confluence
                if mtf.get("overall_bias") == "bullish" and not mtf.get("has_critical_conflict"):
                    lines.append(f"MTF Confluence: {mtf.get('overall_bias', 'neutral').title()} bias across Daily/4H/1H — high confidence.")
                if mtf.get("conflicts"):
                    for conflict in mtf.get("conflicts", [])[:1]:
                        lines.append(f"⚠️ MTF Conflict: {conflict}")

            # Validated Breakouts (D-44: uses helper)
            breakout_signals = [ev for _tf, kind, ev in all_signals if kind == "breakout"][:1]
            for bo in breakout_signals:
                if bo.get("status") == "validated":
                    tf_label = next(tf for tf, k, e in all_signals if k == "breakout" and e is bo)
                    lines.append(f"Validated breakout ({tf_label}) of {bo.get('level_type', 'level')} at {bo.get('level_price', 0):.2f} with {bo.get('volume_ratio', 0):.1f}x volume.")

        if technical.volume_ratio is not None and technical.volume_ratio >= 1.5:
            lines.append(
                f"Volume running {_fmt(technical.volume_ratio)}x average — real participation behind the move."
            )
    if fundamental is not None and fundamental.score >= 0.15:
        positive = next(
            (f for f in fundamental.findings if any(w in f.lower() for w in ("✅", "strong", "growth", "quality"))),
            None,
        )
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
        lines.append(f"Fresh catalyst: last quarter beat by {surprise:.1f}% — momentum buyers have new fuel.")
    if earnings is not None and earnings.days_until_earnings is not None:
        days = earnings.days_until_earnings
        if 0 <= days <= 14:
            lines.append(f"Earnings lands in {days}d — the catalyst window is open; size down through the print.")
    if technical is not None:
        if technical.bb_position == "above_upper" and technical.rsi is not None and technical.rsi > 70:
            # Expansion, not caution: breakout contexts live above the band.
            lines.append("Pressing the upper Bollinger band — expansion phase in progress.")
        if technical.key_resistance and all(r > 0 for r in technical.key_resistance[:1]):
            nearest = min(technical.key_resistance)
            lines.append(
                f"Liquidity overhead at {_fmt(nearest)} — that's where the trade "
                "gets paid; structure below still has to hold."
            )
        
        # Chart Reading: BOS/CHoCH timing (D-44: uses helper for per-timeframe access)
        if technical.chart_reading:
            cr = technical.chart_reading
            all_signals = list(_all_chart_signals(cr))

            bos_signals = [ev for _tf, kind, ev in all_signals if kind == "bos"]
            if bos_signals:
                latest_bos = bos_signals[-1]
                direction = "bullish" if latest_bos["type"] == "bullish_bos" else "bearish"
                tf_label = next(tf for tf, k, e in all_signals if k == "bos" and e is latest_bos)
                lines.append(f"Recent {direction} BOS ({tf_label}) at {latest_bos['structure_level']:.2f} — structure confirmed, now watching for pullback entry.")

            choch_signals = [ev for _tf, kind, ev in all_signals if kind == "choch"]
            if choch_signals:
                latest_choch = choch_signals[-1]
                direction = "bullish" if latest_choch["type"] == "bullish_choch" else "bearish"
                tf_label = next(tf for tf, k, e in all_signals if k == "choch" and e is latest_choch)
                lines.append(f"Recent {direction} CHoCH ({tf_label}) — structure shift confirmed, new trend emerging.")

            # Chart Reading: Order Block / FVG entries
            ob_signals = [ev for _tf, kind, ev in all_signals if kind == "ob"][:1]
            for ob in ob_signals:
                if not ob.get("mitigated"):
                    direction = "bullish" if ob["type"] == "bullish_ob" else "bearish"
                    tf_label = next(tf for tf, k, e in all_signals if k == "ob" and e is ob)
                    mid_ob = (ob.get("top", 0) + ob.get("bottom", 0)) / 2 if "top" in ob and "bottom" in ob else ob.get("midpoint", 0)
                    lines.append(f"Unmitigated {direction} OB ({tf_label}) at {mid_ob:.2f} — waiting for pullback to enter.")

            fvg_signals = [ev for _tf, kind, ev in all_signals if kind == "fvg"][:1]
            for fvg in fvg_signals:
                if not fvg.get("filled"):
                    direction = "bullish" if fvg["type"] == "bullish_fvg" else "bearish"
                    tf_label = next(tf for tf, k, e in all_signals if k == "fvg" and e is fvg)
                    lines.append(f"Unfilled {direction} FVG ({tf_label}) — price vacuum waiting to fill.")

            # MTF Confluence entry zones (still flat on the model)
            if cr.mtf_confluence and cr.mtf_confluence.get("entry_zones"):
                for zone in cr.mtf_confluence.get("entry_zones", [])[:1]:
                    lines.append(f"MTF {zone.get('timeframe','4h')} {zone.get('type','OB')} entry zone at {zone.get('zone_low',0):.2f}-{zone.get('zone_high',0):.2f}.")
    
    if not lines:
        lines.append("No fresh catalyst yet — this is a staged setup: enter on confirmation, not anticipation.")
    return lines


def _what_kills_it(verdict: AnalysisVerdict, price: float | None, technical: TechnicalAnalysis | None = None) -> list[str]:
    kills: list[str] = []
    # Level-bearing plans — including WATCH-with-levels, which is how live
    # marginal setups actually appear — always state their invalidation.
    if verdict.stop_loss is not None and verdict.action in ("BUY", "SELL", "ACCUMULATE", "WATCH"):
        side = "below" if verdict.action != "SELL" else "above"
        anchor = "the structural invalidation" if verdict.entry_zone_low is not None else "the setup"
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
            f"At +{_fmt(r)}R the stop moves to breakeven — after that, the market pays you to stay wrong-free."
        )
    
    # Chart Reading: MTF invalidation levels (still flat on the model)
    if technical and technical.chart_reading:
        cr = technical.chart_reading
        all_signals = list(_all_chart_signals(cr))

        if cr.mtf_confluence and cr.mtf_confluence.get("invalidation_level"):
            invalidation = cr.mtf_confluence.get("invalidation_level")
            reason = cr.mtf_confluence.get("invalidation_reason", "structure break")
            kills.append(f"MTF invalidation: {invalidation:.2f} — {reason}")

        # Chart Reading: Break of Order Block / FVG (D-44: uses helper)
        ob_signals = [ev for _tf, kind, ev in all_signals if kind == "ob"][:1]
        for ob in ob_signals:
            if not ob.get("mitigated"):
                direction = "bullish" if ob["type"] == "bullish_ob" else "bearish"
                tf_label = next(tf for tf, k, e in all_signals if k == "ob" and e is ob)
                mid_kill_ob = (ob.get("top", 0) + ob.get("bottom", 0)) / 2 if "top" in ob and "bottom" in ob else ob.get("midpoint", 0)
                kills.append(f"Break of {direction} OB ({tf_label}) at {mid_kill_ob:.2f} — institutional thesis invalidated.")

        fvg_signals = [ev for _tf, kind, ev in all_signals if kind == "fvg"][:1]
        for fvg in fvg_signals:
            if not fvg.get("filled"):
                direction = "bullish" if fvg["type"] == "bullish_fvg" else "bearish"
                tf_label = next(tf for tf, k, e in all_signals if k == "fvg" and e is fvg)
                mid_fvg = (fvg.get("bottom", 0) + fvg.get("top", 0)) / 2 if "bottom" in fvg and "top" in fvg else fvg.get("midpoint", 0)
                kills.append(f"Fill of {direction} FVG ({tf_label}) at {mid_fvg:.2f} — imbalance resolved, thesis weakened.")

        # Chart Reading: Volume Profile POC break (D-44: read from
        # TimeframeChartReading, not ChartReadingAnalysis)
        comp = None
        if cr.daily and cr.daily.composite_tpo_profile:
            comp = cr.daily.composite_tpo_profile
        if comp:
            if comp.get("poc_migration") == "down" and price is not None and price > comp.get("composite_poc", 0):
                kills.append(f"Price below composite POC at {comp.get('composite_poc', 0):.2f} — distribution confirmed.")
            elif comp.get("poc_migration") == "up" and price is not None and price < comp.get("composite_poc", 0):
                kills.append(f"Price above composite POC at {comp.get('composite_poc', 0):.2f} — accumulation confirmed.")
    
    if not kills:
        kills.append("No plan, no invalidation — that's exactly why there's no position.")
    return kills


def _thesis_one_liner(symbol: str, verdict: AnalysisVerdict, price: float | None) -> str:
    action = verdict.action
    zone = ""
    if verdict.entry_zone_low is not None and verdict.entry_zone_high is not None:
        zone = f" zone {_fmt(verdict.entry_zone_low)}–{_fmt(verdict.entry_zone_high)}"
    rr = f" at {verdict.risk_reward:.1f}R" if verdict.risk_reward is not None else ""
    return f"{action} {symbol}:{zone}{rr} — {verdict.thesis}" if verdict.thesis else (f"{action} {symbol}:{zone}{rr}.")


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
    """Deterministic reasoning chain attached to every verdict.

    D-44: chart-reading integration is best-effort. The D-36 refactor left
    several schema mismatches that aren't worth fixing in one pass. We
    wrap each chart-reading consumer in a try/except so a malformed or
    missing field never crashes the whole narration. The base
    MA-alignment + RSI + ADX + volume-ratio signals still work; the
    chart-reading enrichment is bonus.
    """
    def _safe(fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception:
            return []

    return MentorNarration(
        why_this=_safe(_why_this, technical, fundamental, earnings, sentiment),
        why_now=_safe(_why_now, technical, earnings),
        what_kills_it=_safe(_what_kills_it, verdict, price, technical),
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
