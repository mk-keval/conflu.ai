"""Fundamental analysis module — evaluates financial health and valuation."""

from __future__ import annotations

from typing import Any

from backend.app.domain.ticker_analysis.models import FundamentalAnalysis


def analyze(info: dict[str, Any]) -> FundamentalAnalysis:
    """Analyse fundamental metrics from yfinance info dict.

    Uses yfinance Ticker.info fields: marketCap, trailingPE, trailingEps,
    profitMargins, debtToEquity, revenueGrowth, freeCashflow,
    dividendYield, returnOnEquity, priceToBook, etc.
    """
    findings: list[str] = []
    score = 0.0
    weight_count = 0

    market_cap = info.get("marketCap") or info.get("market_cap")
    pe = info.get("trailingPE") or info.get("forwardPE")
    eps = info.get("trailingEps") or info.get("forwardEps")
    margin = info.get("profitMargins")
    dte = info.get("debtToEquity")
    rev_growth = info.get("revenueGrowth")
    fcf = info.get("freeCashflow")
    div_yield = info.get("dividendYield")
    op_margin = info.get("operatingMargins")
    roe = info.get("returnOnEquity")
    pb = info.get("priceToBook")
    sector = info.get("sector", "")
    quote_type = info.get("quoteType", "")

    # ── Instrument Type Detection ──
    is_etf = quote_type in ("ETF", "CEF")
    if is_etf:
        findings.append(f"📊 ETF/CEF — different risk profile from single equities")
        score += 0.0  # neutral — just informational

    # ── Market Cap ──
    # Skip micro-cap labeling for ETFs/CEFs — they have different risk profiles
    # and their yfinance marketCap may not reflect tradable liquidity.
    if is_etf and (not market_cap or market_cap < 50_000_000):
        findings.append(f"📊 ETF/CEF — no market cap classification needed")
    elif market_cap:
        if market_cap >= 10_000_000_000:
            findings.append(f"✅ Mega-cap (${market_cap / 1e9:.1f}B) — institutional-grade liquidity")
            score += 0.3
        elif market_cap >= 2_000_000_000:
            findings.append(f"✅ Large-cap (${market_cap / 1e9:.1f}B) — established, liquid")
            score += 0.2
        elif market_cap >= 300_000_000:
            findings.append(f"📊 Mid-cap (${market_cap / 1e6:.0f}M) — decent liquidity, higher growth potential")
            score += 0.1
        elif market_cap >= 50_000_000:
            findings.append(f"⚠️ Small-cap (${market_cap / 1e6:.0f}M) — higher risk, less liquidity")
            score -= 0.2
        else:
            findings.append(f"🚨 Micro-cap (${market_cap / 1e6:.0f}M) — very high risk, illiquid")
            score -= 0.5
    weight_count += 1

    # ── P/E Ratio ──
    if pe and pe > 0:
        if pe < 10:
            findings.append(f"💰 P/E {pe:.1f} — potentially undervalued (value territory)")
            score += 0.3
        elif pe < 20:
            findings.append(f"✅ P/E {pe:.1f} — reasonable valuation")
            score += 0.2
        elif pe < 30:
            findings.append(f"📊 P/E {pe:.1f} — fair-to-premium valuation")
        elif pe < 50:
            findings.append(f"⚠️ P/E {pe:.1f} — premium valuation, priced for growth")
            score -= 0.2
        else:
            findings.append(f"🚨 P/E {pe:.1f} — extreme valuation, high expectations priced in")
            score -= 0.4
    elif pe is not None and pe < 0:
        findings.append("⚠️ Negative P/E — company is not profitable")
        score -= 0.3
    weight_count += 1

    # ── Profitability ──
    if margin is not None:
        margin_pct = margin * 100
        if margin_pct > 20:
            findings.append(f"✅ Profit margin {margin_pct:.1f}% — excellent profitability")
            score += 0.3
        elif margin_pct > 10:
            findings.append(f"✅ Profit margin {margin_pct:.1f}% — good")
            score += 0.2
        elif margin_pct > 5:
            findings.append(f"📊 Profit margin {margin_pct:.1f}% — adequate")
        elif margin_pct > 0:
            findings.append(f"⚠️ Profit margin {margin_pct:.1f}% — thin, sensitive to costs")
            score -= 0.1
        else:
            findings.append(f"🚨 Negative profit margin {margin_pct:.1f}% — unprofitable")
            score -= 0.4
    weight_count += 1

    # ── Debt-to-Equity (sector-adjusted + growth-adjusted) ──
    # Financial companies (banks, insurers, payment processors) naturally have
    # high D/E because customer deposits and settlement liabilities count as
    # debt. Use 8x thresholds for these sectors.
    # Energy companies also carry elevated debt due to capital-intensive
    # operations (drilling, infrastructure). Use 3x for Energy.
    # High-growth companies (>50% YoY revenue growth) often carry elevated
    # leverage to fund expansion — halve the D/E penalty since the growth
    # trajectory makes the debt serviceable.
    if dte is not None:
        financial_sectors = {"Financial Services", "Banks", "Insurance", "Capital Markets"}
        energy_sectors = {"Energy", "Oil & Gas", "Oil & Gas E&P", "Oil & Gas Equipment & Services"}
        is_financial = sector in financial_sectors
        is_energy = sector in energy_sectors
        is_high_growth = rev_growth is not None and rev_growth > 0.50
        dte_mult = 8 if is_financial else (3 if is_energy else 1)
        growth_discount = 0.5 if is_high_growth else 1.0
        if dte < 0.3 * dte_mult:
            findings.append(f"✅ D/E {dte:.2f} — conservative balance sheet (low debt)")
            score += 0.2
        elif dte < 1.0 * dte_mult:
            findings.append(f"✅ D/E {dte:.2f} — healthy leverage")
            score += 0.1
        elif dte < 2.0 * dte_mult:
            findings.append(f"📊 D/E {dte:.2f} — moderate leverage, manageable")
        elif dte < 4.0 * dte_mult:
            penalty = 0.1 if (is_financial or is_energy) else 0.2
            findings.append(f"⚠️ D/E {dte:.2f} — elevated debt, monitor")
            score -= penalty * growth_discount
        else:
            sector_normal = is_financial or is_energy
            suffix = " (normal for sector)" if sector_normal else ", financial risk"
            suffix += " — moderated by exceptional growth" if is_high_growth else ""
            findings.append(f"🚨 D/E {dte:.2f} — highly leveraged{suffix}")
            score -= (0.4 if not sector_normal else 0.1) * growth_discount
    weight_count += 1

    # ── Revenue Growth ──
    if rev_growth is not None:
        growth_pct = rev_growth * 100
        if growth_pct > 20:
            findings.append(f"✅ Revenue growth {growth_pct:.1f}% — exceptional")
            score += 0.3
        elif growth_pct > 10:
            findings.append(f"✅ Revenue growth {growth_pct:.1f}% — strong")
            score += 0.2
        elif growth_pct > 3:
            findings.append(f"📊 Revenue growth {growth_pct:.1f}% — modest")
            score += 0.1
        elif growth_pct > 0:
            findings.append(f"⚠️ Revenue growth {growth_pct:.1f}% — anemic")
        else:
            findings.append(f"🚨 Revenue declining {growth_pct:.1f}% — contraction")
            score -= 0.4
    weight_count += 1

    # ── Free Cash Flow ──
    # Skip FCF analysis for ETFs/CEFs — they don't have meaningful FCF
    if is_etf:
        pass  # FCF doesn't apply to funds
    elif fcf is not None and market_cap:
        fcf_yield = fcf / market_cap
        if fcf_yield > 0.05:
            findings.append(f"💰 FCF yield {fcf_yield:.1%} — strong cash generation")
            score += 0.3
        elif fcf_yield > 0.02:
            findings.append(f"✅ FCF yield {fcf_yield:.1%} — positive cash flow")
            score += 0.1
        elif fcf_yield > 0:
            findings.append(f"📊 FCF yield {fcf_yield:.1%} — minimal free cash flow")
        else:
            findings.append(f"⚠️ Negative FCF — burning cash")
            score -= 0.2
    weight_count += 1

    # ── Dividend Yield ──
    # yfinance returns dividendYield as a percentage value (0.34 = 0.34%).
    # No *100 needed — just use it directly.
    if div_yield:
        dy_pct = div_yield
        if dy_pct > 4:
            findings.append(f"💰 Dividend yield {dy_pct:.2f}% — income-generating")
        elif dy_pct > 1:
            findings.append(f"📊 Dividend yield {dy_pct:.2f}% — modest income")

    normalised = max(-1.0, min(1.0, score / max(weight_count, 1) * 2.5))

    return FundamentalAnalysis(
        score=round(normalised, 2),
        market_cap=market_cap,
        pe_ratio=round(pe, 2) if pe and pe > 0 else (pe if pe is not None else None),
        eps=round(eps, 4) if eps else None,
        profit_margin=round(margin * 100, 2) if margin is not None else None,
        debt_to_equity=round(dte, 2) if dte is not None else None,
        revenue_growth_yoy=round(rev_growth * 100, 2) if rev_growth is not None else None,
        fcf_yield=round(fcf / market_cap * 100, 2) if fcf and market_cap else None,
        dividend_yield=round(div_yield, 4) if div_yield else None,
        findings=findings,
    )
