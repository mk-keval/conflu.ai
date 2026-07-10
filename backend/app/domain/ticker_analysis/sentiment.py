"""Sentiment analysis module — evaluates market sentiment and insider activity."""

from __future__ import annotations

from typing import Any

from backend.app.domain.ticker_analysis.models import SentimentAnalysis


def analyze(info: dict[str, Any]) -> SentimentAnalysis:
    """Analyse sentiment signals from yfinance info dict.

    Fields used: analystRating, targetMeanPrice, targetHighPrice,
    targetLowPrice, recommendationKey, numberOfAnalystOpinions,
    heldPercentInstitutions, heldPercentInsiders, shortRatio,
    shortPercentOfFloat, bookValue, etc.
    """
    findings: list[str] = []
    score = 0.0
    weight_count = 0

    # ── Analyst Consensus ──
    rec_key = info.get("recommendationKey", "")
    mean_target = info.get("targetMeanPrice")
    current_price = info.get("currentPrice") or info.get("regularMarketPrice")
    analyst_count = info.get("numberOfAnalystOpinions", 0)

    consensus_label = {
        "strong_buy": "Strong Buy",
        "buy": "Buy",
        "hold": "Hold",
        "overweight": "Overweight",
        "equal-weight": "Equal Weight",
        "underweight": "Underweight",
        "sell": "Sell",
        "strong_sell": "Strong Sell",
    }.get(rec_key, rec_key.capitalize() if rec_key else "N/A")

    if rec_key in ("strong_buy", "buy", "overweight"):
        findings.append(f"✅ Analyst consensus: {consensus_label} ({analyst_count} analysts)")
        score += 0.3
    elif rec_key in ("hold", "equal-weight"):
        findings.append(f"📊 Analyst consensus: {consensus_label} — neutral outlook")
    elif rec_key in ("sell", "strong_sell", "underweight"):
        findings.append(f"⚠️ Analyst consensus: {consensus_label} — bearish outlook")
        score -= 0.3
    weight_count += 1

    # ── Price Target Upside ──
    if mean_target and current_price and current_price > 0:
        upside = (mean_target / current_price - 1) * 100
        if upside > 20:
            findings.append(f"💰 Analyst target ${mean_target:.2f} ({upside:+.1f}% upside) — significant upside")
            score += 0.2
        elif upside > 10:
            findings.append(f"✅ Target ${mean_target:.2f} ({upside:+.1f}% upside) — room to run")
            score += 0.1
        elif upside > 0:
            findings.append(f"📊 Target ${mean_target:.2f} ({upside:+.1f}% upside) — near fair value")
        else:
            findings.append(f"⚠️ Target ${mean_target:.2f} ({upside:+.1f}% downside) — above target price")
            score -= 0.2
    weight_count += 1

    # ── Insider Holdings ──
    insider_pct = info.get("heldPercentInsiders")
    insider_status = "neutral"
    if insider_pct is not None:
        insider = insider_pct * 100
        if insider > 30:
            findings.append(f"📊 Insider ownership {insider:.1f}% — high alignment with shareholders")
            score += 0.2
        elif insider > 10:
            findings.append(f"✅ Insider ownership {insider:.1f}% — meaningful insider skin-in-the-game")
            score += 0.1
        elif insider > 2:
            findings.append(f"📊 Insider ownership {insider:.1f}% — moderate")
        else:
            findings.append(f"⚠️ Insider ownership {insider:.1f}% — very low, minimal alignment")
            score -= 0.1
    weight_count += 1

    # ── Institutional Holdings ──
    inst_pct = info.get("heldPercentInstitutions")
    if inst_pct is not None:
        inst = inst_pct * 100
        if inst > 60:
            findings.append(f"✅ Institutional ownership {inst:.1f}% — strong institutional confidence")
            score += 0.2
        elif inst > 30:
            findings.append(f"📊 Institutional ownership {inst:.1f}% — moderate institutional interest")
        elif inst > 10:
            findings.append(f"📊 Institutional ownership {inst:.1f}% — light institutional coverage")
        else:
            findings.append(f"⚠️ Institutional ownership {inst:.1f}% — minimal institutional interest")
            score -= 0.2
    weight_count += 1

    # ── Short Interest ──
    short_pct = info.get("shortPercentOfFloat")
    short_ratio = info.get("shortRatio")
    if short_pct is not None:
        si = short_pct * 100
        if si > 30:
            findings.append(f"🚨 Short interest {si:.1f}% of float — extremely high, potential squeeze")
            score -= 0.3
            insider_status = "high_short"
        elif si > 15:
            findings.append(f"⚠️ Short interest {si:.1f}% of float — elevated bearish positioning")
            score -= 0.2
            insider_status = "high_short"
        elif si > 5:
            findings.append(f"📊 Short interest {si:.1f}% of float — moderate")
        else:
            findings.append(f"✅ Short interest {si:.1f}% of float — low (bullish sentiment)")
            score += 0.1
    weight_count += 1

    if short_ratio and short_ratio > 5:
        findings.append(f"⚠️ Days to cover: {short_ratio:.1f} — extended squeeze potential if catalyst hits")

    # ── Beta (implied sentiment through systematic risk) ──
    beta = info.get("beta")
    if beta is not None:
        if beta > 1.5:
            findings.append(f"📊 Beta {beta:.2f} — high volatility, moves 1.5x the market")
        elif beta > 0.8:
            findings.append(f"📊 Beta {beta:.2f} — moves in-line with the market")
        else:
            findings.append(f"📊 Beta {beta:.2f} — low volatility relative to market")

    normalised = max(-1.0, min(1.0, score / max(weight_count, 1) * 2))

    return SentimentAnalysis(
        score=round(normalised, 2),
        analyst_consensus=consensus_label,
        insider_status=insider_status,
        short_interest_pct=round(short_pct * 100, 2) if short_pct is not None else None,
        days_to_cover=round(short_ratio, 2) if short_ratio is not None else None,
        findings=findings,
    )
