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
    industry = info.get("industry", "") or ""
    short_name = info.get("shortName", "") or ""
    long_name = info.get("longName", "") or ""
    business_summary = (info.get("longBusinessSummary") or info.get("businessSummary") or "")

    # ── Instrument Type Detection ──
    # Fund/ETF detection: use multiple yfinance signals for robustness
    is_fund = quote_type in ("ETF", "CEF", "MUTUALFUND", "ETF_MUTUALFUND")
    is_etn = quote_type == "ETN"
    if not is_fund and not is_etn:
        # Additional fund signals: yfinance fund-specific fields
        fund_fields = [
            info.get("fundFamily"),
            info.get("legalType"),
            info.get("morningStarOverallRating"),
            info.get("annualReportExpenseRatio"),
            info.get("ytdReturn"),
        ]
        has_fund_data = any(f is not None for f in fund_fields)
        # Also check quoteType variant and type field
        info_type = info.get("type", "")
        if info_type in ("ETF", "CEF", "MUTUALFUND") or has_fund_data:
            is_fund = True
        # ETN check: legalType or name contains "Exchange Traded Note"
        if is_etn:
            pass  # already set
        elif info.get("legalType") and "exchange traded note" in str(info.get("legalType")).lower():
            is_etn = True
        elif ("exchange traded note" in (short_name + " " + long_name).lower()
              or info.get("type") == "ETN"):
            is_etn = True

    instrument_type: str = "equity"
    is_spac = False
    if not is_fund and not is_etn:
        # SPAC detection: multi-signal heuristic
        spac_keywords = ["acquisition corp", "acquisition company", "blank check",
                         "special purpose acquisition", "acquisition co.", "acquisition hold"]
        name_lower = (short_name + " " + long_name + " " + business_summary).lower()
        is_spac = any(kw in name_lower for kw in spac_keywords)
        # Strong signal: industry contains "Shell" or "Blank Check"
        if industry and ("Shell" in industry or "Blank" in industry):
            is_spac = True
        # Weak signal: no PE, no EPS, no revenue AND name contains "Acquisition" — confirm spac
        no_trailing_pe = (info.get("trailingPE") is None and info.get("forwardPE") is None)
        no_revenue = info.get("totalRevenue") is None
        name_has_acquisition = "acquisition" in name_lower
        if no_trailing_pe and no_revenue and name_has_acquisition:
            is_spac = True
        # Post-merger deSPAC override: if name suggests SPAC but it has real
        # operating revenue AND an actual industry, it's a post-merger deSPAC.
        if is_spac and info.get("totalRevenue") is not None and industry:
            is_spac = False  # Already merged with operating business

    # CEF / Fund name-based heuristic for funds that yfinance doesn't tag
    # (e.g., PIMCO Dynamic Income Fund PDI, Voya Global Equity IGD)
    if not is_fund and not is_etn and not is_spac:
        name_lower = (short_name + " " + long_name + " " + business_summary).lower()
        
        # EXCLUSION: Major financial institutions that should NEVER be classified as CEF/funds
        # These are well-known banks, broker-dealers, investment banks, and universal banks
        MAJOR_FINANCIAL_INSTITUTIONS = {
            "jpmorgan", "jp morgan", "chase", "bank of america", "wells fargo",
            "citigroup", "citi", "goldman sachs", "morgan stanley", "barclays",
            "deutsche bank", "ubs", "credit suisse", "hsbc", "bnp paribas",
            "societe generale", "standard chartered", "royal bank of canada",
            "toronto dominion", "bank of montreal", "scotiabank", "cibc",
            "charles schwab", "schwab", "etrade", "td ameritrade", "fidelity",
            "vanguard", "blackrock", "state street", "northern trust", "bny mellon",
            "intercontinental exchange", "cme group", "nasdaq", "ice",
        }
        is_major_financial = any(inst in name_lower for inst in MAJOR_FINANCIAL_INSTITUTIONS)
        
        name_has_fund_keywords = any(kw in name_lower for kw in [
            " fund", "funds", "income fund", "growth fund", "dividend fund",
            "dynamic income", "global equity", "municipal fund", "bond fund",
        ])
        # Strong signal: name says "Fund" + Financial Services sector + no P/E or no EPS
        # EXCLUDE major financial institutions from this heuristic
        is_name_fund = name_has_fund_keywords and sector in ("Financial Services", "Financial") and not is_major_financial
        has_fund_like_data = (info.get("trailingPE") is None or info.get("eps") is None)
        if is_name_fund and has_fund_like_data:
            is_fund = True
            # yfinance doesn't differentiate CEF vs ETF here, but most "Income Fund"
            # names and "Global Equity" names on US exchanges are CEFs
            if any(kw in name_lower for kw in ["dynamic income", "global equity", "income fund", "municipal"]):
                instrument_type = "cef"
            else:
                instrument_type = "cef"  # default to CEF for name-detected funds

    if is_fund:
        # Differentiate fund types: CEF vs regular ETF
        # If CEF name heuristic already set instrument_type, keep it
        if instrument_type == "cef":
            pass
        elif quote_type == "CEF" or info.get("legalType") == "Closed-End Fund":
            instrument_type = "cef"
        elif is_etn:
            instrument_type = "etn"
        else:
            instrument_type = "etf"
    elif is_etn:
        instrument_type = "etn"
    elif is_spac:
        instrument_type = "spac"

    # ── Special Instrument Type Detection ──
    # These instruments are not standard operating equities but also not funds.
    # They use different analytical frameworks (FFO, DCF, NII, yield).
    if instrument_type == "equity":
        # REIT: sector=Real Estate or industry starts with "REIT"
        if sector == "Real Estate" or (industry and ("reit" in industry.lower() or industry.lower().startswith("reit"))):
            instrument_type = "reit"
        # Preferred stock: quoteType signals preferred
        elif quote_type == "PREFERRED":
            instrument_type = "preferred"
        # MLP: partnership name + energy sector
        else:
            mlp_name = any(kw in (short_name + " " + long_name).lower() for kw in [" l.p.", "limited partnership", "partners lp"])
            mlp_industry = industry and "midstream" in industry.lower()
            if (mlp_name or mlp_industry) and sector in ("Energy", "Oil & Gas"):
                instrument_type = "mlp"
            # BDC: legalType or name/industry signals
            elif (info.get("legalType") and "business development" in str(info.get("legalType")).lower()) \
                 or any(kw in (short_name + " " + long_name + " " + business_summary).lower() for kw in ["business development company", "bdc "]):
                instrument_type = "bdc"

    is_fund_or_etn = is_fund or is_etn

    if is_spac:
        findings.append(
            "📊 Pre-deal SPAC — no operating business, no fundamental data to analyze. "
            "Analysis based on trust value and sponsor quality instead."
        )
    elif is_fund_or_etn:
        if instrument_type == "etn":
            findings.append("📊 ETN (Exchange Traded Note) — credit risk of issuer, different from equity analysis")
        elif instrument_type == "cef":
            findings.append("📊 Closed-End Fund — traded like a stock but has unique premium/discount dynamics")
        else:
            findings.append("📊 ETF — fund instrument, different risk profile from single equities")
    elif instrument_type in ("reit", "mlp", "bdc", "preferred"):
        type_labels = {
            "reit": "🏢 REIT — real estate investment trust, evaluate on FFO/NAV not P/E",
            "mlp": "📊 MLP — master limited partnership, K-1 tax treatment, evaluate on DCF not P/E",
            "bdc": "📊 BDC — business development company, evaluate on NII/NAV not P/E",
            "preferred": "📊 Preferred stock — fixed-income hybrid, evaluate on yield/credit not P/E",
        }
        findings.append(type_labels.get(instrument_type, f"📊 {instrument_type.upper()} — special instrument"))

    # ── Exchange / Listing Quality ──
    exchange = info.get("exchange") or info.get("exchangeCode") or ""
    full_exchange_name = info.get("fullExchangeName") or info.get("exchangeName") or ""
    listing_exchange = exchange.upper() if exchange else None

    # Classify exchange quality
    PRIMARY_EXCHANGES = {"NYQ", "NMS", "NCM", "NGM", "PCX", "BATS", "NYSE", "NASDAQ", "ASE"}
    OTC_EXCHANGES = {"OTC", "PNK", "OQB", "OQX", "OTCQX", "OTCQB", "OTC PINK", "OID"}
    exchange_category: str = "unknown"
    if listing_exchange and listing_exchange in PRIMARY_EXCHANGES:
        exchange_category = "primary"
    elif listing_exchange and listing_exchange in OTC_EXCHANGES:
        exchange_category = "otc"
    elif listing_exchange and listing_exchange.startswith("OTC"):
        exchange_category = "otc"
    elif listing_exchange and listing_exchange not in ("UNKNOWN", "", None):
        # Before defaulting to "foreign", check the full exchange name for OTC
        # signals (e.g., "YHD" with fullExchangeName="Expert Market" → OTC).
        # This catches exchange codes not in our known sets but whose
        # descriptive name clearly identifies them as OTC markets.
        exchange_category = "foreign"
        if full_exchange_name:
            otc_keywords = ["otc", "pink", "over-the-counter", "grey market", "expert market"]
            if any(kw in full_exchange_name.lower() for kw in otc_keywords):
                exchange_category = "otc"

    # Check full exchange name for unknown exchange codes
    if exchange_category == "unknown" and full_exchange_name:
        otc_keywords = ["otc", "pink", "over-the-counter", "grey market", "expert market"]
        if any(kw in full_exchange_name.lower() for kw in otc_keywords):
            exchange_category = "otc"
        elif "exchange" in full_exchange_name.lower():
            exchange_category = "primary"

    # Score adjustment based on listing quality
    if exchange_category == "otc":
        findings.append(
            "🚨 OTC/Pink-listed — extremely low liquidity, wide spreads, "
            "limited disclosure. Institutional-grade data may be unavailable."
        )
        score -= 0.3
    elif exchange_category == "foreign":
        findings.append(
            "📊 Non-US exchange — cross-check ADR/liquidity metrics "
            "before positioning. Local reporting standards may differ."
        )
    elif exchange_category == "primary":
        findings.append(
            "✅ Listed on major US exchange — institutional-grade liquidity and disclosure"
        )
        score += 0.1

    # OTC sub-tier: detect Caveat Emptor / Yield / skull-and-crossbones
    # The most dangerous OTC stocks have no financial reporting, no bids
    is_caveat_emptor = False
    if exchange_category == "otc":
        # Signals of extreme OTC danger: no book value, no market cap data,
        # no bid/ask spread, or 52-week range
        has_no_book = info.get("bookValue") is None
        has_no_revenue_otc = info.get("totalRevenue") is None
        is_untestable = has_no_book and has_no_revenue_otc
        if is_untestable or (market_cap is not None and market_cap < 2_000_000):
            is_caveat_emptor = True
            findings.append(
                "☠️ Caveat Emptor OTC — no financial reporting, no book value, "
                "extremely dangerous. Position size should be zero regardless of scores. "
                "These stocks are frequently used in pump-and-dump schemes."
            )
            score -= 1.0  # Heaviest possible penalty — effectively floors score to AVOID

    # ── Asset Category Detection ──
    # Some companies are not standard operating businesses — they hold a primary
    # reserve asset (Bitcoin, gold), hold patents/IP, or are holding companies.
    # Standard equity analysis (P/E, margins, growth) doesn't apply to them.
    asset_category: str = "operating"
    if not is_fund_or_etn and not is_spac:
        name_lower = (short_name + " " + long_name + " " + business_summary).lower()
        # Detect Bitcoin/treasury asset companies (e.g., MPLT, MSTR)
        btc_keywords = ["bitcoin", "btc", "digital asset", "cryptocurrency treasury",
                        "crypto treasury", "bitcoin treasury", "holds bitcoin",
                        "bitcoin reserve", "digital gold"]
        btc_score = sum(1 for kw in btc_keywords if kw in name_lower)
        # Detect crypto miners vs treasury asset holders
        # Miners (RIOT, MARA) have "mining" context in their business summary
        # and are operating businesses, not passive treasury holders.
        is_crypto_miner = btc_score >= 2 and "mining" in name_lower
        # Detect companies with majority assets in a single non-operating asset
        # Strong signal: Bitcoin treasury + no revenue + financial sector
        is_btc_treasury = btc_score >= 2 and not is_crypto_miner
        # Secondary signals
        if is_btc_treasury:
            asset_category = "treasury_asset"
            findings.append(
                "📊 Bitcoin treasury company — value tracks primary reserve asset (BTC), "
                "not operating earnings. Standard P/E/margin analysis is misleading. "
                "Evaluate based on BTC holdings per share and premium/discount to NAV."
            )
            # Don't score for treasury asset companies — P/E and margins are meaningless
            findings.append("ℹ️ Treasury asset company — fundamental score neutral (standard metrics not applicable)")
        # Holding company detection (e.g., Berkshire Hathaway, investment conglomerates)
        hold_keywords = ["holding company", "holding co", "conglomerate", "investment holding",
                         "investment company", "management investment company", "asset management"]
        is_holding_co = any(kw in name_lower for kw in hold_keywords) and not is_btc_treasury
        # Industry-based holding company detection: Asset Management / Investment Companies
        # with no operating revenue are likely holding structures (e.g., Destiny Tech100)
        if not is_holding_co and not is_btc_treasury:
            total_revenue_asset = info.get("totalRevenue")
            has_no_revenue_asset = total_revenue_asset is None or total_revenue_asset < 1_000_000
            is_holding_co = (
                industry is not None
                and ("asset management" in industry.lower() or "investment" in industry.lower())
                and has_no_revenue_asset
            )
        if is_holding_co:
            asset_category = "holding_company"
            findings.append(
                "📊 Holding company / conglomerate — earnings from diverse subsidiaries. "
                "Sum-of-parts valuation more appropriate than single P/E."
            )

        # Mining royalty / streaming company detection (e.g., Franco-Nevada, Wheaton PM)
        # These companies don't operate mines — they finance miners in exchange for
        # royalty/streaming rights. High margins but passive income, not operating.
        if asset_category == "operating" and not is_btc_treasury:
            royalty_keywords = ["royalty", "streaming company", "net smelter", "n.s.r."]
            is_royalty_co = any(kw in business_summary.lower() for kw in royalty_keywords)
            if is_royalty_co and sector in ("Basic Materials", "Financial Services"):
                asset_category = "mining_royalty"
                findings.append(
                    "📊 Mining royalty / streaming company — does not operate mines. "
                    "Revenue from passive royalty/streaming agreements. "
                    "High margins are typical for royalty model, not operational excellence. "
                    "Evaluate based on portfolio diversification and reserve life."
                )

    # ── Lifecycle Stage Detection ──
    # Development-stage companies (pre-revenue, pre-profit, clinical-stage)
    # require different analytical frameworks than operating companies.
    is_development_stage = False
    lifecycle_stage = "operating"

    if not is_spac and not is_fund_or_etn and asset_category not in ("treasury_asset", "holding_company") and instrument_type not in ("reit", "mlp", "bdc", "preferred"):
        name_lower = (short_name + " " + long_name + " " + business_summary).lower()
        total_revenue = info.get("totalRevenue")
        has_no_revenue = total_revenue is None or (total_revenue is not None and total_revenue < 1_000_000)
        has_negative_pe = (info.get("trailingPE") is not None and info.get("trailingPE") < 0)
        has_no_trailing_pe = info.get("trailingPE") is None
        has_no_forward_pe = info.get("forwardPE") is None
        ent_val = info.get("enterpriseValue")

        # Clinical-stage biotech/pharma: no revenue, R&D spend, biotech/pharma sector
        # Check both sector AND industry for biotech/pharma keywords
        biotech_industry_keywords = ["biotechnology", "biotech", "pharmaceutical", "pharma",
                                     "clinical", "therapeutic", "biopharma", "biopharmaceutical",
                                     "drug discovery", "medical research"]
        is_biotech_sector = (sector and "biotechnology" in sector.lower()) or (sector and "healthcare" in sector.lower())
        is_biotech_industry = industry and any(kw in industry.lower() for kw in biotech_industry_keywords)

        if is_biotech_sector or is_biotech_industry:
            # Clinical-stage requires no/minimal revenue as primary signal
            # (pre-revenue biotech) OR negative PE with no revenue growth
            if has_no_revenue:
                lifecycle_stage = "clinical_stage"
                is_development_stage = True
                findings.append(
                    "🧬 Clinical-stage biotechnology company — no approved products / revenue. "
                    "Binary pipeline-driven value. Standard P/E, margin, and growth analysis "
                    "does not apply. Evaluate based on cash runway, trial milestones, "
                    "and pipeline probability-adjusted value."
                )
            elif total_revenue is not None and total_revenue < 500_000_000:
                # Biotech with partnership/milestone revenue ($1M-$500M) but no approved
                # products. Revenue is from licensing/collaboration, not product sales.
                no_pe = has_no_trailing_pe and has_no_forward_pe
                deeply_unprofitable = (op_margin is not None and op_margin < -0.5) or (margin is not None and margin < -0.5)
                if no_pe or deeply_unprofitable:
                    lifecycle_stage = "clinical_stage"
                    is_development_stage = True
                    findings.append(
                        "🧬 Clinical-stage biotechnology company — revenue from "
                        "partnerships/collaborations, not approved product sales. "
                        "Standard P/E, margin, and growth analysis does not apply. "
                        "Evaluate based on cash runway, trial milestones, "
                        "and pipeline probability-adjusted value."
                    )

        # Pre-revenue technology: no revenue, tech sector, enterprise value > 0
        elif sector and "technology" in sector.lower():
            if has_no_revenue:
                lifecycle_stage = "pre_revenue"
                is_development_stage = True
                findings.append(
                    "💻 Pre-revenue technology company — no operating revenue. "
                    "Standard fundamental metrics (P/E, margins, FCF yield) are not applicable. "
                    "Evaluate based on product development stage, cash runway, "
                    "and path to commercialization."
                )

        # General development-stage: no revenue + no trailing PE across any sector
        elif has_no_revenue and (has_negative_pe or has_no_trailing_pe):
            if sector and "mining" in sector.lower():
                lifecycle_stage = "development"
                is_development_stage = True
                findings.append(
                    "⛏️ Mineral exploration / development-stage company — no production revenue. "
                    "Standard equity analysis does not apply. Evaluate based on resource "
                    "estimates, feasibility studies, and funding runway."
                )
            else:
                lifecycle_stage = "development"
                is_development_stage = True
                findings.append(
                    "📊 Development-stage company — no operating revenue. "
                    "Standard fundamental metrics (P/E, margins, FCF yield) are not meaningful. "
                    "Evaluate based on development milestones, cash runway, "
                    "and path to commercialization."
                )

        # Pre-profit development-stage: some revenue but deeply unprofitable
        # (< $100M revenue + operating/profit margin < -50% + negative FCF)
        # Catches pre-profit tech (ASTS: $85M revenue, -1014% op margin, -$1.4B FCF),
        # pre-clinical biotech with token revenue, mineral explorers, etc.
        # Standalone check (not elif) in case the sector elif chain was entered
        # but the inner conditions didn't match.
        if (lifecycle_stage == "operating"
            and total_revenue is not None and not has_no_revenue and total_revenue < 100_000_000
            and ((op_margin is not None and op_margin < -0.5) or (margin is not None and margin < -0.5))
            and fcf is not None and fcf < 0):
            lifecycle_stage = "development"
            is_development_stage = True
            findings.append(
                "📊 Development-stage / pre-profit company — limited revenue with "
                "deeply negative margins and negative free cash flow. Company is still "
                "investing heavily relative to revenue base. Standard valuation metrics "
                "(P/E, FCF yield) are not yet meaningful. Evaluate based on cash runway, "
                "revenue growth trajectory, and path to profitability."
            )

        # Catch companies with >$100M revenue but devastating cash burn
        # (FCF burn > 30% of market cap = catastrophic, burns through market cap in 3 yrs)
        if (lifecycle_stage == "operating"
            and total_revenue is not None and total_revenue >= 100_000_000 and total_revenue < 1_000_000_000
            and ((op_margin is not None and op_margin < -0.8) or (margin is not None and margin < -0.8))
            and fcf is not None and fcf < 0
            and market_cap is not None and abs(fcf) / market_cap > 0.3):
            lifecycle_stage = "development"
            is_development_stage = True
            findings.append(
                "📊 Pre-profit company with extreme cash burn — despite meaningful "
                "revenue, deeply negative margins and cash consumption relative to "
                "market cap indicate development-stage profile. Standard valuation "
                "metrics (P/E, FCF yield) are not meaningful. Evaluate based on "
                "cash runway and path to profitability."
            )

    # ── Market Cap ──
    if is_spac:
        findings.append(f"📊 SPAC — market cap reflects trust value, not operating business")
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
    # Skip P/E for SPACs, ETFs, Bitcoin treasury companies, and development-stage companies
    # Also skip for special instruments that use FFO/DCF/NII instead of EPS
    special_no_pe = instrument_type in ("reit", "mlp", "bdc", "preferred")
    if not is_spac and not is_fund_or_etn and asset_category != "treasury_asset" and asset_category != "holding_company" and lifecycle_stage == "operating" and not special_no_pe:
        # Must have PE data for analysis
        if pe is not None:

            # ── Adjusted Earnings Detection ──
            # Some companies report low GAAP P/E because earnings are inflated by adding back
            # amortization of intangibles from acquisitions. This creates a misleading "value"
            # signal. Key indicators: low P/E + high debt (from acquisition financing) + low
            # revenue growth relative to earnings growth.
            # Check if adjusted/GAAP gap indicates amortization-heavy earnings.
            # yfinance forwardPE often reflects adjusted estimates — compare with trailingPE.
            # Adjusted earnings detection (for positive P/E with high debt + slow revenue)
            if pe > 0:
                pe_is_low = pe < 15
                dte_is_high = dte is not None and dte > 2.0
                revenue_growth_slow = rev_growth is not None and rev_growth < 0.05
                if pe_is_low and dte_is_high and revenue_growth_slow:
                    findings.append(
                        "⚠️ Low P/E may reflect adjusted (non-GAAP) earnings inflated by "
                        "adding back amortization of intangibles from past acquisitions. "
                        f"GAAP P/E is {pe:.1f}x but debt-to-equity of {dte:.1f}x and slow "
                        "revenue growth suggest earnings quality concerns. Consider using "
                        "adjusted P/E and evaluating free cash flow instead."
                    )
                    score -= 0.1

            # Standard P/E valuation chain
            if pe > 0 and pe < 10:
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
    else:
        # Skip P/E for SPACs, funds, treasury assets
        if pe is not None:
            weight_count += 1

    # ── Profitability ──
    # Skip margin analysis for SPACs, development-stage companies, and special instruments
    if margin is not None and not is_spac and lifecycle_stage == "operating" and not special_no_pe:
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

    # Pre-calculate sector flags (needed regardless of D/E validity)
    financial_sectors = {"Financial Services", "Banks", "Insurance", "Capital Markets"}
    energy_sectors = {"Energy", "Oil & Gas", "Oil & Gas E&P", "Oil & Gas Equipment & Services"}
    is_financial = sector in financial_sectors
    is_energy = sector in energy_sectors
    is_high_growth = rev_growth is not None and rev_growth > 0.50

    if dte is not None:
        # SANITY CHECK: yfinance sometimes returns bogus D/E (e.g., 79.5 for AAPL)
        # when totalStockholderEquity is None. Flag and attempt recalculation.
        # Also catch moderate bogus values (e.g., NVDA 6.55) that are too high for non-financials.
        if dte > 5 and not is_financial:
            # Try to recalculate from raw balance sheet data
            total_debt = info.get("totalDebt")
            total_equity = info.get("totalStockholderEquity")
            if total_debt and total_equity and total_equity > 0:
                recalculated = total_debt / total_equity
                if recalculated < 20:  # Sanity check on recalculated value
                    findings.append(f"⚠️ yfinance D/E {dte:.2f} appears incorrect; recalculated to {recalculated:.2f} from balance sheet")
                    dte = recalculated
                else:
                    findings.append(f"⚠️ yfinance D/E {dte:.2f} appears incorrect (likely missing equity data); excluding from analysis")
                    dte = None
            else:
                findings.append(f"⚠️ yfinance D/E {dte:.2f} appears incorrect (likely missing equity data); excluding from analysis")
                dte = None

        if dte is not None:
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
    # Skip for SPACs — no operating revenue to evaluate
    if rev_growth is not None and not is_spac:
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
    # Skip FCF analysis for ETFs/CEFs, SPACs, and special instruments — they don't have meaningful FCF
    if is_fund_or_etn or is_spac or special_no_pe:
        pass  # FCF doesn't apply to funds/SPACs/special instruments
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
        instrument_type=instrument_type,
        listing_exchange=listing_exchange,
        exchange_category=exchange_category,
        asset_category=asset_category,
        lifecycle_stage=lifecycle_stage,
        market_cap=market_cap,
        pe_ratio=round(pe, 2) if pe and pe > 0 else (pe if pe is not None else None),
        eps=round(eps, 4) if eps else None,
        profit_margin=round(margin * 100, 2) if margin is not None else None,
        debt_to_equity=round(dte, 2) if dte is not None else None,
        revenue_growth_yoy=round(rev_growth * 100, 2) if rev_growth is not None else None,
        fcf_yield=round(fcf / market_cap * 100, 2) if fcf and market_cap else None,
        dividend_yield=round(div_yield, 4) if div_yield else None,
        return_on_equity=round(roe * 100, 2) if roe is not None else None,
        price_to_book=round(pb, 2) if pb is not None else None,
        operating_margin=round(op_margin * 100, 2) if op_margin is not None else None,
        findings=findings,
    )
