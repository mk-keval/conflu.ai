"""Classification contract tests for the ticker analysis pipeline.

Tests use synthetic data to verify that classification rules work correctly
for all known edge cases. No yfinance, no API, no network calls.

Purpose: When someone modifies the analysis logic, these tests ensure that
every previously-discovered edge case still produces the correct classification.
This is our regression safety net.

Adding a new edge case:
    1. Write a failing test with synthetic data that demonstrates the bug
    2. Fix the analysis logic
    3. Test passes — edge case is permanently covered
"""

from __future__ import annotations

from typing import Any

import pytest

from backend.app.domain.ticker_analysis import fundamentals, synthesis
from backend.app.domain.ticker_analysis.models import (
    AnalysisVerdict,
    FundamentalAnalysis,
    RiskAssessment,
    SentimentAnalysis,
    TechnicalAnalysis,
)


# ── Helpers ──


def _base_info() -> dict[str, Any]:
    """Baseline info dict for a healthy, operating technology company.

    All classification fields should return 'operating' / 'equity' / 'primary'.
    Individual tests override specific fields to create edge cases.
    """
    return {
        "shortName": "AcmeTech Inc.",
        "longName": "AcmeTech Inc.",
        "longBusinessSummary": "AcmeTech develops enterprise software solutions.",
        "sector": "Technology",
        "industry": "Software - Infrastructure",
        "quoteType": "EQUITY",
        "exchange": "NMS",
        "marketCap": 50_000_000_000,
        "totalRevenue": 10_000_000_000,
        "trailingPE": 25.0,
        "forwardPE": 22.0,
        "trailingEps": 2.5,
        "forwardEps": 2.8,
        "profitMargins": 0.15,
        "operatingMargins": 0.18,
        "freeCashflow": 2_000_000_000,
        "debtToEquity": 0.5,
        "revenueGrowth": 0.12,
        "dividendYield": None,
        "returnOnEquity": 0.20,
        "priceToBook": 5.0,
        "beta": 1.1,
        "enterpriseValue": 55_000_000_000,
        "fiftyTwoWeekLow": 80.0,
        "fiftyTwoWeekHigh": 120.0,
        "bookValue": 20.0,
        "earningsPerShare": 2.5,
        "type": None,
        "fundFamily": None,
        "legalType": None,
        "morningStarOverallRating": None,
        "annualReportExpenseRatio": None,
        "ytdReturn": None,
    }


def _analyze_fundamentals(overrides: dict[str, Any] | None = None) -> FundamentalAnalysis:
    """Call fundamentals.analyze() with synthetic data."""
    info = _base_info()
    if overrides:
        info.update(overrides)
    return fundamentals.analyze(info)


def _base_tv_data() -> dict[str, Any]:
    """Baseline TV data for risk module tests."""
    return {
        "close": 100.0,
        "ATR": 2.0,
        "volume": 5_000_000,
        "SMA20": 98.0,
        "SMA50": 95.0,
        "SMA200": 90.0,
        "RSI": 55.0,
        "ADX": 25.0,
    }


# ── Fundamentals: Lifecycle Stage Tests ──


class TestLifecycleStage:
    """Verify lifecycle_stage classification for all known edge cases."""

    def test_standard_operating(self):
        """Healthy tech company with revenue and positive earnings → operating."""
        result = _analyze_fundamentals()
        assert result.lifecycle_stage == "operating"
        assert result.asset_category == "operating"
        assert result.instrument_type == "equity"

    def test_clinical_stage_biotech_no_revenue(self):
        """Biotech with Healthcare sector + no revenue → clinical_stage."""
        result = _analyze_fundamentals({
            "sector": "Healthcare",
            "industry": "Biotechnology",
            "totalRevenue": None,
        })
        assert result.lifecycle_stage == "clinical_stage"

    def test_clinical_stage_biotech_low_revenue(self):
        """Biotech with sub-$1M revenue → still clinical_stage."""
        result = _analyze_fundamentals({
            "sector": "Healthcare",
            "industry": "Biotechnology",
            "totalRevenue": 500_000,
        })
        assert result.lifecycle_stage == "clinical_stage"

    def test_clinical_stage_industry_variant(self):
        """MPLT-style: sector=Healthcare, industry=Biotechnology (not sector=Biotechnology)."""
        result = _analyze_fundamentals({
            "sector": "Healthcare",
            "industry": "Biotechnology",
            "totalRevenue": None,
        })
        assert result.lifecycle_stage == "clinical_stage"

    def test_clinical_stage_pharma_industry(self):
        """Pharmaceutical industry also qualifies for clinical_stage."""
        result = _analyze_fundamentals({
            "sector": "Healthcare",
            "industry": "Drug Manufacturers - Specialty & Generic",
            "totalRevenue": None,
        })
        assert result.lifecycle_stage == "clinical_stage"

    def test_operating_healthcare_with_revenue(self):
        """TOI-style: Healthcare with meaningful revenue → operating, NOT clinical."""
        result = _analyze_fundamentals({
            "sector": "Healthcare",
            "industry": "Medical Care Facilities",
            "totalRevenue": 500_000_000,
            "trailingPE": None,
        })
        assert result.lifecycle_stage == "operating"

    def test_pre_revenue_technology(self):
        """Tech company with no revenue → pre_revenue."""
        result = _analyze_fundamentals({
            "sector": "Technology",
            "totalRevenue": None,
        })
        assert result.lifecycle_stage == "pre_revenue"

    def test_pre_profit_development_stage(self):
        """ASTS-style: low revenue, deeply negative margins, negative FCF → development."""
        result = _analyze_fundamentals({
            "sector": "Technology",
            "industry": "Communication Equipment",
            "totalRevenue": 85_000_000,
            "operatingMargins": -10.14,
            "profitMargins": 0.0,
            "freeCashflow": -1_400_000_000,
            "trailingPE": None,
            "forwardPE": None,
        })
        assert result.lifecycle_stage == "development"

    def test_pre_profit_proteomics(self):
        """SEER-style: biotech-adjacent with min revenue + deep losses → development."""
        result = _analyze_fundamentals({
            "sector": "Technology",
            "industry": "Software - Application",
            "totalRevenue": 17_000_000,
            "operatingMargins": -3.5,
            "profitMargins": -3.2,
            "freeCashflow": -80_000_000,
            "trailingPE": None,
        })
        assert result.lifecycle_stage == "development"

    def test_development_general_no_revenue(self):
        """Any sector with no revenue + no trailing PE → development."""
        result = _analyze_fundamentals({
            "sector": "Energy",
            "industry": "Oil & Gas E&P",
            "totalRevenue": None,
            "trailingPE": None,
        })
        assert result.lifecycle_stage == "development"

    def test_development_mining_exploration(self):
        """Mining/exploration with no revenue → development with mining finding."""
        result = _analyze_fundamentals({
            "sector": "Basic Materials",
            "industry": "Gold",
            "totalRevenue": None,
            "trailingPE": None,
        })
        assert result.lifecycle_stage == "development"

    def test_biotech_milestone_revenue(self):
        """Biotech with $150M partnership revenue but no PE → clinical_stage."""
        result = _analyze_fundamentals({
            "shortName": "Pipeline Bio Ltd.",
            "longName": "Pipeline Bio Ltd.",
            "longBusinessSummary": "a clinical-stage biotechnology company focused on developing gene therapies. Revenue from collaboration agreements",
            "sector": "Healthcare",
            "industry": "Biotechnology",
            "quoteType": "EQUITY",
            "exchange": "NMS",
            "totalRevenue": 150_000_000,
            "profitMargins": -1.20,
            "operatingMargins": -1.50,
            "freeCashflow": -400_000_000,
            "trailingPE": None,
            "forwardPE": None,
        })
        assert result.lifecycle_stage == "clinical_stage"

    def test_kura_commercial_biotech(self):
        """KURA-shaped: biotech with FDA-approved product revenue → NOT clinical_stage.

        KURA (~9.1M/quarter = ~$36M TTM from approved drug KOMZIFTI) lands in the
        $1M-$500M biotech branch which wrongly classified it clinical_stage.
        With commercial-sale evidence in the business summary, it must classify
        as operating so downstream synthesis emits a real trade plan.
        """
        result = _analyze_fundamentals({
            "shortName": "Kura Oncology plc",
            "longName": "Kura Oncology plc",
            "longBusinessSummary": (
                "Kura Oncology is a commercial-stage biotechnology company "
                "developing precision medicines for cancer. The company has an "
                "FDA-approved product, KOMZIFTI (quisotentinalactone), which is "
                "commercially launched and generating sales of approved drug "
                "products to patients with solid tumors."
            ),
            "sector": "Healthcare",
            "industry": "Biotechnology",
            "quoteType": "EQUITY",
            "exchange": "NMS",
            "totalRevenue": 36_000_000,
            "profitMargins": 0.15,
            "operatingMargins": 0.10,
            "freeCashflow": -50_000_000,
            "trailingPE": None,
            "forwardPE": None,
            "marketCap": 3_000_000_000,
        })
        assert result.lifecycle_stage != "clinical_stage"
        assert result.lifecycle_stage == "operating"
        # Should have a finding documenting the commercial-stage detection
        assert any("commercial-stage" in f.lower() or "commercial-stage" in f for f in result.findings)

    def test_kura_live_shape_deep_loss_commercial(self):
        """KURA live-data shape (2026-08-21 replay) → operating, NOT clinical/development.

        Live yfinance: $77.2M TTM revenue, op margin -350%, gross margin negative,
        summary self-labels "clinical-stage biopharmaceutical company" but states
        "first commercial product, KOMZIFTI". The old profitability guard blocked
        detection and the pre-profit demotion re-caught it downstream — both must
        yield to product-level evidence for biotechs.
        """
        result = _analyze_fundamentals({
            "shortName": "Kura Oncology, Inc.",
            "longName": "Kura Oncology, Inc.",
            "longBusinessSummary": (
                "Kura Oncology, Inc., a clinical-stage biopharmaceutical company, "
                "develops medicines for the treatment of cancer. The company's "
                "first commercial product, KOMZIFTI (ziftomenib), a potent, "
                "selective, reversible and oral small molecule menin inhibitor; "
                "Darlifarnib, a Phase 1 first-in-human trial."
            ),
            "sector": "Healthcare",
            "industry": "Biotechnology",
            "quoteType": "EQUITY",
            "exchange": "NMS",
            "totalRevenue": 77_225_000,
            "operatingMargins": -3.4976501,
            "grossMargins": -2.3672,
            "freeCashflow": -120_000_000,
            "trailingPE": None,
            "forwardPE": None,
            "marketCap": 1_058_000_000,
        })
        assert result.lifecycle_stage == "operating"
        assert any("commercial-stage" in f.lower() for f in result.findings)

    def test_pure_clinical_biotech(self):
        """True pre-revenue/clinical biotech (no revenue, no product language) → clinical_stage."""
        result = _analyze_fundamentals({
            "shortName": "Preclinical Bio Inc.",
            "longName": "Preclinical Bio Inc.",
            "longBusinessSummary": (
                "a clinical-stage biotechnology company developing novel immunotherapies. "
                "No approved products. Revenue from research grants."
            ),
            "sector": "Healthcare",
            "industry": "Biotechnology",
            "quoteType": "EQUITY",
            "exchange": "NMS",
            "totalRevenue": None,
            "trailingPE": None,
            "forwardPE": None,
        })
        assert result.lifecycle_stage == "clinical_stage"

    def test_partnership_revenue_biotech(self):
        """Partnership/milestone-only revenue biotech (no product language) → clinical_stage.

        Small revenue, no product language, deeply unprofitable, no PE. The
        commercial-sale keyword signal must NOT fire here.
        """
        result = _analyze_fundamentals({
            "shortName": "Partnership Bio Ltd.",
            "longName": "Partnership Bio Ltd.",
            "longBusinessSummary": (
                "a clinical-stage biotechnology company focused on developing gene "
                "therapies. Revenue from collaboration and license agreements with "
                "pharmaceutical partners for development milestones."
            ),
            "sector": "Healthcare",
            "industry": "Biotechnology",
            "quoteType": "EQUITY",
            "exchange": "NMS",
            "totalRevenue": 75_000_000,
            "profitMargins": -1.10,
            "operatingMargins": -1.40,
            "freeCashflow": -300_000_000,
            "trailingPE": None,
            "forwardPE": None,
            "marketCap": 800_000_000,
        })
        assert result.lifecycle_stage == "clinical_stage"

    def test_astst_spy_pre_profit_not_reclassified(self):
        """ASTS-style pre-profit tech (~$85M rev, <50% op margin, negative FCF) → development.

        Regression guard: the product-revenue keyword signal must NOT reclassify
        pre-profit tech companies. ASTS has no biotech sector and no commercial-
        sale keywords, so it stays in the development bucket via L408-420.
        """
        result = _analyze_fundamentals({
            "shortName": "ASTS Inc.",
            "longName": "ASTS Inc.",
            "longBusinessSummary": (
                "operates satellite communications network providing connectivity "
                "services to enterprise and government customers"
            ),
            "sector": "Technology",
            "industry": "Communication Equipment",
            "quoteType": "EQUITY",
            "exchange": "NMS",
            "totalRevenue": 85_000_000,
            "operatingMargins": -10.14,
            "profitMargins": 0.0,
            "freeCashflow": -1_400_000_000,
            "trailingPE": None,
            "forwardPE": None,
            "marketCap": 8_000_000_000,
        })
        assert result.lifecycle_stage == "development"

    def test_pre_profit_high_revenue(self):
        """>$100M revenue but extreme cash burn → development."""
        result = _analyze_fundamentals({
            "shortName": "CashBurn Inc.",
            "longName": "CashBurn Inc.",
            "longBusinessSummary": "operates a technology-based logistics platform",
            "sector": "Technology",
            "industry": "Software - Application",
            "quoteType": "EQUITY",
            "exchange": "NMS",
            "totalRevenue": 250_000_000,
            "profitMargins": -0.80,
            "operatingMargins": -0.90,
            "freeCashflow": -800_000_000,
            "trailingPE": None,
            "forwardPE": None,
            "marketCap": 2_000_000_000,
        })
        assert result.lifecycle_stage == "development"


# ── Fundamentals: Instrument Type Tests ──


class TestInstrumentType:
    """Verify instrument_type classification."""

    def test_equity_standard(self):
        """Normal company → equity."""
        result = _analyze_fundamentals()
        assert result.instrument_type == "equity"

    def test_etf_via_quotetype(self):
        """quoteType=ETF → etf."""
        result = _analyze_fundamentals({"quoteType": "ETF"})
        assert result.instrument_type == "etf"

    def test_cef_name_heuristic(self):
        """PDI/IGD-style: name contains 'Fund' + Financial Services → cef."""
        result = _analyze_fundamentals({
            "shortName": "PIMCO Dynamic Income Fund",
            "longName": "PIMCO Dynamic Income Fund",
            "sector": "Financial Services",
            "trailingPE": None,
            "fundFamily": None,
            "legalType": None,
        })
        assert result.instrument_type == "cef"

    def test_cef_name_heuristic_secondary(self):
        """IGD-style: 'Global Equity' fund name → cef."""
        result = _analyze_fundamentals({
            "shortName": "Voya Global Equity Dividend Fund",
            "longName": "Voya Global Equity Dividend and Premium Opportunity Fund",
            "sector": "Financial Services",
            "trailingPE": None,
            "fundFamily": None,
            "legalType": None,
        })
        assert result.instrument_type == "cef"

    def test_major_financial_not_cef(self):
        """JPMorgan Chase and other major banks should NEVER be classified as CEF/fund."""
        for name in [
            "JPMorgan Chase & Co.",
            "JPMorgan Chase",
            "Bank of America Corporation",
            "Wells Fargo & Company",
            "Citigroup Inc.",
            "Goldman Sachs Group Inc.",
            "Morgan Stanley",
            "Barclays PLC",
            "Deutsche Bank AG",
            "UBS Group AG",
            "Charles Schwab Corporation",
            "Vanguard Group Inc.",
            "BlackRock Inc.",
        ]:
            result = _analyze_fundamentals({
                "shortName": name,
                "longName": name,
                "sector": "Financial Services",
                "trailingPE": 15.0,
                "eps": 5.0,
                "fundFamily": None,
                "legalType": None,
            })
            assert result.instrument_type == "equity", f"{name} should be equity, got {result.instrument_type}"

    def test_spac_detection(self):
        """SPAC via name keywords + no revenue + no PE."""
        result = _analyze_fundamentals({
            "shortName": "Vertex Energy Acquisition Corp",
            "longName": "Vertex Energy Acquisition Corp",
            "totalRevenue": None,
            "trailingPE": None,
            "forwardPE": None,
        })
        assert result.instrument_type == "spac"

    def test_etn_detection(self):
        """ETN via exchange traded note in name."""
        result = _analyze_fundamentals({
            "shortName": "iPath Exchange Traded Note",
            "totalRevenue": None,
        })
        assert result.instrument_type == "etn"

    def test_reit_detection_sector(self):
        """REIT with sector=Real Estate → reit."""
        result = _analyze_fundamentals({
            "shortName": "Realty Income Corporation",
            "longName": "Realty Income Corporation",
            "sector": "Real Estate",
            "industry": "Retail REITs",
            "quoteType": "EQUITY",
            "exchange": "NYQ",
        })
        assert result.instrument_type == "reit"

    def test_reit_detection_industry(self):
        """REIT with industry starting with REIT → reit."""
        result = _analyze_fundamentals({
            "shortName": "VICI Properties Inc.",
            "longName": "VICI Properties Inc.",
            "longBusinessSummary": "VICI Properties is an experiential real estate investment trust",
            "sector": "Real Estate",
            "industry": "REIT - Diversified",
            "quoteType": "EQUITY",
            "exchange": "NYQ",
        })
        assert result.instrument_type == "reit"

    def test_preferred_detection(self):
        """Preferred stock with quoteType=PREFERRED → preferred."""
        result = _analyze_fundamentals({
            "shortName": "Bank of America Dep Shs",
            "longName": "Bank of America Corporation Depositary Shares Series L",
            "sector": "Financial Services",
            "industry": "Banks - Diversified",
            "quoteType": "PREFERRED",
            "exchange": "NYQ",
        })
        assert result.instrument_type == "preferred"

    def test_mlp_detection_name(self):
        """MLP via name ending with L.P. → mlp."""
        result = _analyze_fundamentals({
            "shortName": "Enterprise Products Partners L.P.",
            "longName": "Enterprise Products Partners L.P.",
            "sector": "Energy",
            "industry": "Oil & Gas Midstream",
            "quoteType": "EQUITY",
            "exchange": "NYQ",
        })
        assert result.instrument_type == "mlp"

    def test_bdc_detection(self):
        """BDC via business summary → bdc."""
        result = _analyze_fundamentals({
            "shortName": "Main Street Capital Corp",
            "longName": "Main Street Capital Corporation",
            "longBusinessSummary": "a business development company that provides debt and equity capital",
            "sector": "Financial Services",
            "industry": "Asset Management",
            "quoteType": "EQUITY",
            "exchange": "NYQ",
        })
        assert result.instrument_type == "bdc"

    def test_despac_not_spac(self):
        """Post-merger deSPAC with revenue and industry → equity (not spac)."""
        result = _analyze_fundamentals({
            "shortName": "Target Co Acquisition Corp",
            "longName": "Target Co Acquisition Corp",
            "longBusinessSummary": "Target Company operates electric vehicle charging stations across North America",
            "sector": "Consumer Cyclical",
            "industry": "Auto Parts",
            "quoteType": "EQUITY",
            "exchange": "NMS",
            "totalRevenue": 250_000_000,
            "trailingPE": None,
            "forwardPE": None,
        })
        assert result.instrument_type == "equity"


# ── Fundamentals: Exchange Category Tests ──


class TestExchangeCategory:
    """Verify exchange_category classification."""

    def test_primary_exchange(self):
        """NYSE/NASDAQ → primary."""
        result = _analyze_fundamentals({"exchange": "NMS"})
        assert result.exchange_category == "primary"

    def test_otc_exchange(self):
        """OTC PINK exchange code → otc."""
        result = _analyze_fundamentals({"exchange": "PNK"})
        assert result.exchange_category == "otc"

    def test_otc_oid_exchange(self):
        """FXLG-style: OID exchange code → otc."""
        result = _analyze_fundamentals({"exchange": "OID"})
        assert result.exchange_category == "otc"

    def test_foreign_exchange(self):
        """Non-US, non-OTC exchange → foreign."""
        result = _analyze_fundamentals({"exchange": "BTS"})
        assert result.exchange_category == "foreign"

    def test_expert_market_otc(self):
        """Expert Market detected via fullExchangeName → otc."""
        result = _analyze_fundamentals({
            "shortName": "Defunct Corp",
            "longName": "Defunct Corp Common Stock",
            "sector": "Technology",
            "quoteType": "EQUITY",
            "exchange": "YHD",
            "fullExchangeName": "Expert Market",
        })
        assert result.exchange_category == "otc"


# ── Fundamentals: Asset Category Tests ──


class TestAssetCategory:
    """Verify asset_category classification."""

    def test_operating_default(self):
        """Standard operating company → operating."""
        result = _analyze_fundamentals()
        assert result.asset_category == "operating"

    def test_holding_company_name(self):
        """Name contains 'Holding Company' → holding_company."""
        result = _analyze_fundamentals({
            "sector": "Financial Services",
            "industry": "Banks - Regional",
            "longBusinessSummary": "operates as the holding company for Farmers State Bank",
            "totalRevenue": 50_000_000,
        })
        assert result.asset_category == "holding_company"

    def test_holding_company_industry_no_revenue(self):
        """DXYZ-style: Asset Management industry + no revenue → holding_company."""
        result = _analyze_fundamentals({
            "sector": "Financial Services",
            "industry": "Asset Management",
            "totalRevenue": None,
            "shortName": "Destiny Tech100 Inc.",
        })
        assert result.asset_category == "holding_company"

    def test_bitcoin_treasury(self):
        """Bitcoin treasury company (MPLT-style) → treasury_asset."""
        result = _analyze_fundamentals({
            "shortName": "MicroStrategy",
            "longName": "MicroStrategy Incorporated",
            "longBusinessSummary": "holds bitcoin as primary treasury reserve asset",
            "sector": "Technology",
            "totalRevenue": 500_000_000,
        })
        assert result.asset_category == "treasury_asset"

    def test_mstr_treasury(self):
        """MSTR-like: Bitcoin treasury company with operating software revenue → treasury_asset + operating.

        MicroStrategy holds bitcoin as primary reserve asset while also operating
        business intelligence software. asset_category must be 'treasury_asset' (not
        operating) and lifecycle_stage must be 'operating' (excluded from dev-stage
        detection because treasury_asset companies skip lifecycle analysis).
        """
        result = _analyze_fundamentals({
            "shortName": "MicroStrategy",
            "longName": "MicroStrategy Incorporated",
            "longBusinessSummary": (
                "MicroStrategy Incorporated acquires and holds bitcoin as primary "
                "treasury reserve asset. The company also provides enterprise business "
                "intelligence software powered by AI, with commercial license revenue "
                "and subscription services. Bitcoin treasury strategy as primary "
                "investment focus."
            ),
            "sector": "Technology",
            "industry": "Software - Infrastructure",
            "quoteType": "EQUITY",
            "exchange": "NMS",
            "totalRevenue": 500_000_000,
            "trailingPE": 45.0,
            "forwardPE": 40.0,
            "profitMargins": 0.22,
            "operatingMargins": 0.25,
            "freeCashflow": 100_000_000,
            "marketCap": 60_000_000_000,
        })
        assert result.asset_category == "treasury_asset"
        assert result.lifecycle_stage == "operating"
        # Must NOT be classified as crypto_miner (excluded via "mining" check
        # — this summary must not contain "mining")
        assert not any("mining" in f.lower() for f in result.findings)

    def test_otc_caveat_emptor(self):
        """OTC with no book value + no revenue → caveat emptor."""
        result = _analyze_fundamentals({
            "exchange": "PNK",
            "totalRevenue": None,
            "bookValue": None,
            "marketCap": None,
        })
        assert result.exchange_category == "otc"
        assert any("Caveat Emptor" in f or "caveat emptor" in f.lower()
                   for f in result.findings)

    def test_crypto_miner_not_treasury(self):
        """RIOT-like bitcoin miner → operating (NOT treasury_asset)."""
        result = _analyze_fundamentals({
            "shortName": "Riot Platforms Inc.",
            "longName": "Riot Platforms Inc.",
            "longBusinessSummary": "Riot Platforms is a vertically integrated bitcoin mining company that operates large-scale bitcoin mining facilities",
            "sector": "Technology",
            "industry": "Software - Infrastructure",
            "quoteType": "EQUITY",
            "exchange": "NMS",
            "totalRevenue": 280_000_000,
        })
        assert result.asset_category == "operating"

    def test_mining_royalty_detection(self):
        """Franco-Nevada style royalty company → mining_royalty."""
        result = _analyze_fundamentals({
            "shortName": "Franco-Nevada Corporation",
            "longName": "Franco-Nevada Corporation",
            "longBusinessSummary": "Franco-Nevada is a gold-focused royalty and streaming company with a diversified portfolio",
            "sector": "Basic Materials",
            "industry": "Gold",
            "quoteType": "EQUITY",
            "exchange": "NYQ",
        })
        assert result.asset_category == "mining_royalty"
        assert result.lifecycle_stage == "operating"

    def test_de_sanity_check_recalculates_from_balance_sheet(self):
        """AAPL-style: yfinance returns bogus D/E (79.5) when equity missing; should recalculate from balance sheet."""
        result = _analyze_fundamentals({
            "shortName": "Apple Inc.",
            "longName": "Apple Inc.",
            "longBusinessSummary": "Apple designs, manufactures, and markets smartphones, personal computers, tablets, wearables, and accessories.",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "quoteType": "EQUITY",
            "exchange": "NMS",
            "marketCap": 3_000_000_000_000,
            "totalRevenue": 390_000_000_000,
            "trailingPE": 30.0,
            "trailingEps": 6.0,
            "profitMargins": 0.25,
            "operatingMargins": 0.30,
            "freeCashflow": 100_000_000_000,
            "debtToEquity": 79.55,  # Bogus yfinance value when equity is missing
            "revenueGrowth": 0.05,
            "totalDebt": 120_000_000_000,      # $120B total debt
            "totalStockholderEquity": 65_000_000_000,  # $65B equity → D/E = 1.85
            "dividendYield": 0.005,
            "returnOnEquity": 1.5,
            "priceToBook": 45.0,
            "beta": 1.2,
        })
        # Should recalculate D/E to ~1.85, not use the bogus 79.55
        assert result.debt_to_equity is not None
        assert result.debt_to_equity < 5.0, f"Expected recalculated D/E < 5, got {result.debt_to_equity}"
        assert abs(result.debt_to_equity - 1.85) < 0.5, f"Expected ~1.85, got {result.debt_to_equity}"
        # Should have a finding about the recalculation
        assert any("recalculated" in f.lower() for f in result.findings)

    def test_de_sanity_check_excludes_when_no_balance_sheet(self):
        """If balance sheet data also missing, D/E should be excluded (set to None)."""
        result = _analyze_fundamentals({
            "shortName": "Mystery Corp",
            "longName": "Mystery Corp",
            "longBusinessSummary": "A company with no balance sheet data.",
            "sector": "Technology",
            "industry": "Software - Application",
            "quoteType": "EQUITY",
            "exchange": "NMS",
            "marketCap": 10_000_000_000,
            "totalRevenue": 1_000_000_000,
            "trailingPE": 25.0,
            "trailingEps": 2.0,
            "profitMargins": 0.15,
            "operatingMargins": 0.20,
            "freeCashflow": 200_000_000,
            "debtToEquity": 79.55,  # Bogus value
            "revenueGrowth": 0.10,
            "totalDebt": None,  # Missing balance sheet data
            "totalStockholderEquity": None,
            "dividendYield": 0.01,
            "returnOnEquity": 0.20,
            "priceToBook": 5.0,
            "beta": 1.1,
        })
        # Should exclude the bogus D/E (set to None) since can't recalculate
        assert result.debt_to_equity is None
        assert any("excluding" in f.lower() or "incorrect" in f.lower() for f in result.findings)


# ── Risk: Position Sizing Tests ──


class TestPositionSizing:
    """Verify risk position sizing rules, especially for ETFs/CEFs."""

    def _analyze_risk(self, info_overrides: dict[str, Any] | None = None,
                      tv_data: dict[str, Any] | None = None) -> RiskAssessment:
        from backend.app.domain.ticker_analysis import risk as risk_module
        info = _base_info()
        if info_overrides:
            info.update(info_overrides)
        data = _base_tv_data()
        if tv_data:
            data.update(tv_data)
        return risk_module.analyze(data, info)

    def test_standard_equity_position_sizing(self):
        """Standard equity with $50B market cap → uses market-cap cap."""
        result = self._analyze_risk()
        # $50B → established cap (not micro/small)
        assert result.suggested_position_size_pct <= 15.0

    def test_etf_no_micro_cap_cap(self):
        """GDX/TLT-style: ETFs should NEVER get micro-cap position cap."""
        result = self._analyze_risk(
            info_overrides={
                "instrument_type": "etf",
                "marketCap": None,
                "quoteType": "ETF",
            }
        )
        assert result.suggested_position_size_pct >= 5.0
        assert not any("Micro-cap risk cap" in f for f in result.findings)

    def test_cef_no_micro_cap_cap(self):
        """PDI/IGD-style: CEFs should NEVER get micro-cap position cap."""
        result = self._analyze_risk(
            info_overrides={
                "instrument_type": "cef",
                "marketCap": None,
                "quoteType": "CEF",
            }
        )
        assert result.suggested_position_size_pct >= 5.0
        assert not any("Micro-cap risk cap" in f for f in result.findings)

    def test_micro_cap_equity_gets_capped(self):
        """Real micro-cap equity ($5M) → micro-cap risk cap applies."""
        result = self._analyze_risk(
            info_overrides={"marketCap": 5_000_000}
        )
        assert any("Micro-cap risk cap" in f for f in result.findings)

    def test_otc_position_cap(self):
        """OTC-listed equity → position capped at 3%."""
        result = self._analyze_risk(
            info_overrides={"exchange": "PNK"}
        )
        # Controlled by the OTC-listed risk cap
        assert result.suggested_position_size_pct <= 5.0


# ── Synthesis: Override Tests ──


class TestSynthesisOverrides:
    """Verify that synthesis override rules fire correctly."""

    def _make_technical(self, **kw: Any) -> TechnicalAnalysis:
        base = TechnicalAnalysis(
            score=0.0, ma_alignment="mixed", rsi=50.0, rsi_regime="neutral",
            adx=20.0, adx_verdict="weak", atr_pct=2.0, volatility_regime="normal",
            volume_ratio=1.0, bb_position="inside", macd_status="neutral",
            findings=[],
        )
        return base.model_copy(update=kw) if kw else base

    def _make_fundamental(self, **kw: Any) -> FundamentalAnalysis:
        base = FundamentalAnalysis(
            score=0.0, instrument_type="equity", exchange_category="primary",
            asset_category="operating", lifecycle_stage="operating",
            market_cap=10_000_000_000, pe_ratio=20.0, eps=2.0,
            profit_margin=10.0, debt_to_equity=0.5, revenue_growth_yoy=10.0,
            findings=[],
        )
        return base.model_copy(update=kw) if kw else base

    def _make_sentiment(self, **kw: Any) -> SentimentAnalysis:
        base = SentimentAnalysis(
            score=0.0, analyst_consensus="Hold", insider_status="neutral",
            short_interest_pct=None, days_to_cover=None,
            institutional_ownership=None, beta=1.0, findings=[],
        )
        return base.model_copy(update=kw) if kw else base

    def _make_risk(self, **kw: Any) -> RiskAssessment:
        base = RiskAssessment(
            score=0.0, volatility_regime="normal",
            suggested_stop_pct=5.0, suggested_position_size_pct=10.0,
            findings=[],
        )
        return base.model_copy(update=kw) if kw else base

    def _synthesise(self, technical: TechnicalAnalysis | None = None,
                    fundamental: FundamentalAnalysis | None = None,
                    sentiment: SentimentAnalysis | None = None,
                    risk: RiskAssessment | None = None,
                    price: float = 100.0) -> AnalysisVerdict:
        return synthesis.synthesise(
            technical=technical or self._make_technical(),
            fundamental=fundamental or self._make_fundamental(),
            earnings=None,
            sentiment=sentiment or self._make_sentiment(),
            risk=risk or self._make_risk(),
            price=price,
        )

    def test_squeeze_override_fires(self):
        """Short interest > 30% → WATCH c:3 with squeeze dynamics."""
        sent = self._make_sentiment(short_interest_pct=35.0, beta=2.0)
        verdict = self._synthesise(sentiment=sent)
        assert verdict.action == "WATCH"
        assert verdict.conviction >= 3
        assert any("Short interest" in f for f in verdict.key_red_flags)

    def test_squeeze_override_not_below_threshold(self):
        """Short interest < 30% → no squeeze override."""
        sent = self._make_sentiment(short_interest_pct=15.0, beta=1.5)
        verdict = self._synthesise(sentiment=sent)
        assert verdict.action != "WATCH" or verdict.conviction < 3

    def test_spac_override_fires(self):
        """SPAC instrument_type → WATCH c:3."""
        fund = self._make_fundamental(instrument_type="spac", lifecycle_stage="operating")
        verdict = self._synthesise(fundamental=fund)
        assert verdict.action == "WATCH"

    def test_etf_override_fires(self):
        """ETF instrument_type → WATCH c:2."""
        fund = self._make_fundamental(instrument_type="etf", lifecycle_stage="operating")
        verdict = self._synthesise(fundamental=fund)
        assert verdict.action == "WATCH"

    def test_development_override_fires(self):
        """Development lifecycle → WATCH c:3."""
        fund = self._make_fundamental(lifecycle_stage="development", instrument_type="equity")
        verdict = self._synthesise(fundamental=fund)
        assert verdict.action == "WATCH"

    def test_clinical_stage_override_fires(self):
        """Clinical-stage lifecycle → WATCH c:3."""
        fund = self._make_fundamental(lifecycle_stage="clinical_stage", instrument_type="equity")
        verdict = self._synthesise(fundamental=fund)
        assert verdict.action == "WATCH"

    def test_meme_position_cap_applied(self):
        """GME-style: SI>10%, beta>1.5, bearish MA → position capped at 5%."""
        sent = self._make_sentiment(short_interest_pct=15.0, beta=1.8)
        tech = self._make_technical(ma_alignment="bearish")
        risk = self._make_risk(suggested_position_size_pct=15.0)
        verdict = self._synthesise(technical=tech, sentiment=sent, risk=risk)
        assert verdict.position_size_pct <= 5.0

    def test_meme_position_cap_not_applied_low_si(self):
        """AMC-style: SI<10% → position NOT capped."""
        sent = self._make_sentiment(short_interest_pct=8.0, beta=1.7)
        tech = self._make_technical(ma_alignment="bearish")
        risk = self._make_risk(suggested_position_size_pct=15.0)
        verdict = self._synthesise(technical=tech, sentiment=sent, risk=risk)
        assert verdict.position_size_pct > 5.0

    def test_meme_position_cap_not_applied_low_beta(self):
        """Low beta despite high SI → position NOT capped."""
        sent = self._make_sentiment(short_interest_pct=20.0, beta=0.8)
        tech = self._make_technical(ma_alignment="bearish")
        risk = self._make_risk(suggested_position_size_pct=15.0)
        verdict = self._synthesise(technical=tech, sentiment=sent, risk=risk)
        assert verdict.position_size_pct > 5.0

    def test_avoid_reduce_zero_position(self):
        """AVOID/REDUCE → position_size = 0 regardless."""
        risk = self._make_risk(suggested_position_size_pct=10.0)
        # A very negative fundamental and risk score should produce REDUCE
        fund = self._make_fundamental(score=-0.8)
        risk = RiskAssessment(score=-0.8, volatility_regime="extreme",
                              suggested_stop_pct=10.0, suggested_position_size_pct=10.0,
                              findings=["🚨 Extreme risk"])
        sent = self._make_sentiment(score=-0.5)
        verdict = self._synthesise(fundamental=fund, sentiment=sent, risk=risk)
        assert verdict.position_size_pct == 0.0
