"""Earnings analysis module — evaluates earnings quality and surprise history."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.app.domain.ticker_analysis.models import EarningsAnalysis


def analyze(info: dict[str, Any], symbol: str | None = None) -> EarningsAnalysis:
    """Analyse earnings quality from yfinance info dict.

    Fields used: earningsQuarterly (DataFrame), earningsTimestamp,
    earningsSurprisePct, revenueSurprisePct, lastSplitDate, etc.
    Also falls back to averages from info where quarterly breakdown
    is unavailable.

    If `symbol` is provided, fetches earnings_dates from yfinance to get
    the last reported quarter's surprise data (yfinance .info doesn't
    populate earningsSurprisePct).
    """
    findings: list[str] = []
    score = 0.0
    weight_count = 0

    # ── Last Quarter Surprise ──
    # Try to get from yfinance earnings_dates DataFrame (has actual reported data)
    surprise_pct = None
    rev_surprise_pct = None
    last_surprise_pct = None
    days_until_earnings = None
    next_earnings_date = None

    if symbol:
        try:
            import yfinance as yf
            ed = yf.Ticker(symbol).earnings_dates
            if ed is not None and not ed.empty:
                # Find the most recent quarter with reported EPS (not future estimates)
                for i, row in ed.iterrows():
                    r = row.get("Reported EPS")
                    if r is not None and str(r).lower() != "nan":
                        surprise_pct = float(row.get("Surprise(%)", 0)) if row.get("Surprise(%)") is not None else 0
                        rev_surprise_pct = float(row.get("Revenue Surprise(%)", 0)) if row.get("Revenue Surprise(%)") is not None else None
                        last_surprise_pct = surprise_pct
                        break
                # Also get next earnings date
                if days_until_earnings is None:
                    for i, row in ed.iterrows():
                        r = row.get("Reported EPS")
                        if r is None or str(r).lower() == "nan":
                            # This is a future earnings date
                            if hasattr(i, "strftime"):
                                next_earnings_date = i.strftime("%Y-%m-%d")
                                dt = i
                                if dt.tzinfo is None:
                                    dt = dt.replace(tzinfo=timezone.utc)
                            else:
                                dt = datetime.fromisoformat(str(i).replace("Z", "+00:00")).replace(tzinfo=timezone.utc)
                            days_until_earnings = (dt - datetime.now(timezone.utc)).days
                            break
        except Exception:
            pass  # Silently fall back to .info values

    # Fallback to .info values if earnings_dates didn't work
    if surprise_pct is None:
        surprise_pct = info.get("earningsSurprisePct") or info.get("surprisePct")
    if rev_surprise_pct is None:
        rev_surprise_pct = info.get("revenueSurprisePct")
    if last_surprise_pct is None:
        last_surprise_pct = surprise_pct
    if days_until_earnings is None:
        next_date = info.get("earningsTimestampStart") or info.get("earningsTimestamp")
        if next_date:
            try:
                if isinstance(next_date, (int, float)):
                    dt = datetime.fromtimestamp(next_date)
                else:
                    dt = datetime.fromisoformat(str(next_date).replace("Z", "+00:00"))
                dt = dt.replace(tzinfo=timezone.utc)
                days_until_earnings = (dt - datetime.now(timezone.utc)).days
                next_earnings_date = dt.strftime("%Y-%m-%d")
            except Exception:
                pass

    if surprise_pct is not None:
        if surprise_pct > 10:
            findings.append(f"✅ Last quarter BEAT by {surprise_pct:.1f}% — strong earnings momentum")
            score += 0.4
        elif surprise_pct > 3:
            findings.append(f"✅ Beat by {surprise_pct:.1f}% — solid print")
            score += 0.2
        elif surprise_pct > 0:
            findings.append(f"📊 Beat by {surprise_pct:.1f}% — marginal")
            score += 0.1
        elif surprise_pct > -3:
            findings.append(f"⚠️ Missed by {abs(surprise_pct):.1f}% — narrow miss, within noise")
            score -= 0.1
        elif surprise_pct > -10:
            findings.append(f"⚠️ Missed by {abs(surprise_pct):.1f}% — concerning miss")
            score -= 0.3
        else:
            findings.append(f"🚨 Missed by {abs(surprise_pct):.1f}% — significant earnings failure")
            score -= 0.6
    weight_count += 1

    if rev_surprise_pct is not None:
        if rev_surprise_pct > 5:
            score += 0.2
        elif rev_surprise_pct < -5:
            score -= 0.2

    # ── Beat Rate (how many of last 4 quarters beat) ──
    eps_trend = info.get("epsTrailingTwelveMonths")
    eps_forward = info.get("epsForward")

    # Construct beat rate from available data
    quarterly = info.get("earningsQuarterly")
    beat_rate_str = None
    if quarterly and isinstance(quarterly, list):
        beats = sum(1 for q in quarterly if q.get("surprisePercent", 0) > 0)
        total = len(quarterly)
        if total > 0:
            beat_rate_str = f"{beats}/{total}"
            if beats / total >= 0.75:
                findings.append(f"✅ Beat rate {beat_rate_str} — consistently beating estimates")
                score += 0.3
            elif beats / total >= 0.5:
                findings.append(f"📊 Beat rate {beat_rate_str} — mixed track record")
            else:
                findings.append(f"⚠️ Beat rate {beat_rate_str} — consistently missing")
                score -= 0.3
        weight_count += 1

    # ── EPS Trend (growing or shrinking) ──
    if eps_trend and eps_forward:
        if eps_forward > eps_trend:
            findings.append("✅ Forward EPS > TTM EPS — earnings expected to grow")
            score += 0.2
        elif eps_forward < eps_trend:
            findings.append("⚠️ Forward EPS < TTM EPS — earnings expected to decline")
            score -= 0.2
    weight_count += 1

    # ── Next Earnings Date ──
    next_date = info.get("earningsTimestampStart") or info.get("earningsTimestamp")
    next_date_str = None
    if next_date:
        try:
            if isinstance(next_date, (int, float)):
                dt = datetime.fromtimestamp(next_date)
            else:
                dt = datetime.fromisoformat(str(next_date).replace("Z", "+00:00"))
            # Normalize to aware-local so the subtraction below can never
            # hit naive-vs-aware TypeError (which previously swallowed the
            # whole proximity computation into the except branch).
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            next_date_str = dt.strftime("%b %d, %Y")
            days_until = (dt - datetime.now(timezone.utc).astimezone()).days
            # P1.5: persist the proximity so brief cards + watchlist rows can
            # render a warning chip without re-deriving it.
            days_until_earnings = int(days_until)
            if 0 <= days_until <= 14:
                findings.append(f"⚠️ Earnings in {days_until}d ({next_date_str}) — earnings risk window")
                score -= 0.1  # Uncertainty premium
            elif days_until < 0:
                findings.append(f"📊 Last earnings: {next_date_str}")
            else:
                findings.append(f"📊 Next earnings: {next_date_str} ({days_until}d away)")
        except (ValueError, TypeError):
            pass

    # ── Growth Rate ──
    growth = info.get("earningsGrowth")
    if growth is not None:
        growth_pct = growth * 100
        if growth_pct > 25:
            findings.append(f"✅ Earnings growth {growth_pct:.1f}% — exceptional")
            score += 0.3
        elif growth_pct > 10:
            findings.append(f"✅ Earnings growth {growth_pct:.1f}% — strong")
            score += 0.2
        elif growth_pct > 0:
            findings.append(f"📊 Earnings growth {growth_pct:.1f}% — positive but modest")
            score += 0.1
        else:
            findings.append(f"⚠️ Earnings declining {growth_pct:.1f}% — contraction")
            score -= 0.3
        weight_count += 1

    normalised = max(-1.0, min(1.0, score / max(weight_count, 1) * 2))

    return EarningsAnalysis(
        score=round(normalised, 2),
        last_surprise_pct=round(surprise_pct, 2) if surprise_pct is not None else None,
        beat_rate=beat_rate_str,
        avg_reaction_pct=None,
        next_earnings_date=next_date_str,
        days_until_earnings=days_until_earnings,
        findings=findings,
    )