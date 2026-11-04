"""Tests for sector-relative RS (D-46 PR 2).

The elite trader's question: 'is this stock confirming its sector, or
fighting it?' A name can look good in isolation but actually be
LAGGING its sector — the sector is carrying it, which is a weak signal.
The opposite — outperforming the sector — is the elite trader's
strongest confirmation that institutional money is targeting this name.
"""

from __future__ import annotations

import pandas as pd
import pytest

from backend.app.infrastructure.professional import macro_context


# ── Fixtures ──────────────────────────────────────────────────────────────


def _make_history(closes: list[float]) -> pd.DataFrame:
    """Build a daily OHLCV history with monotonically-trending closes."""
    idx = pd.date_range("2026-06-01", periods=len(closes), freq="B")
    return pd.DataFrame(
        {
            "Open": closes,
            "High": [c * 1.01 for c in closes],
            "Low": [c * 0.99 for c in closes],
            "Close": closes,
            "Volume": [1_000_000] * len(closes),
        },
        index=idx,
    )


@pytest.fixture(autouse=True)
def _reset_caches():
    macro_context.clear_sector_cache()
    yield
    macro_context.clear_sector_cache()


# ── Sector → ETF mapping ─────────────────────────────────────────────────


class TestSectorToEtf:
    def test_energy_maps_to_xle(self):
        assert macro_context.sector_to_etf("Energy") == "XLE"

    def test_technology_maps_to_xlk(self):
        assert macro_context.sector_to_etf("Technology") == "XLK"

    def test_software_maps_to_xlk(self):
        assert macro_context.sector_to_etf("Software") == "XLK"

    def test_biotechnology_maps_to_xbi(self):
        # Sub-ETF (XLV mixes pharma + biotech)
        assert macro_context.sector_to_etf("Biotechnology") == "XBI"

    def test_banks_maps_to_kre(self):
        # Sub-ETF (XLF is too broad for regional banks)
        assert macro_context.sector_to_etf("Banks") == "KRE"

    def test_aerospace_defense_maps_to_ita(self):
        # Sub-ETF (defense is a huge theme right now)
        assert macro_context.sector_to_etf("Aerospace & Defense") == "ITA"

    def test_consumer_defensive_maps_to_xlp(self):
        # yfinance says "Consumer Defensive" (not "Consumer Staples")
        assert macro_context.sector_to_etf("Consumer Defensive") == "XLP"

    def test_consumer_cyclical_maps_to_xly(self):
        assert macro_context.sector_to_etf("Consumer Cyclical") == "XLY"

    def test_unknown_sector_returns_none(self):
        assert macro_context.sector_to_etf("Unknown Sector XYZ") is None

    def test_none_sector_returns_none(self):
        assert macro_context.sector_to_etf(None) is None

    def test_empty_string_returns_none(self):
        assert macro_context.sector_to_etf("") is None


# ── Window return helper ──────────────────────────────────────────────────


class TestWindowReturn:
    def test_positive_1m_return(self):
        # 1M = 21 trading days, prev=100, last=110 → +10%
        closes = [100] * 42 + [110]
        h = _make_history(closes)
        # Window of 21 days → need at least 22 closes
        result = macro_context._window_return(h, 21)
        assert result == pytest.approx(10.0)

    def test_negative_3m_return(self):
        closes = [100] * 64 + [85]
        h = _make_history(closes)
        result = macro_context._window_return(h, 63)
        assert result == pytest.approx(-15.0)

    def test_insufficient_data(self):
        closes = [100] * 10
        h = _make_history(closes)
        assert macro_context._window_return(h, 21) is None

    def test_none_history(self):
        assert macro_context._window_return(None, 21) is None

    def test_zero_prev_returns_none(self):
        closes = [0] * 22 + [100]
        h = _make_history(closes)
        assert macro_context._window_return(h, 21) is None


# ── compute_sector_relative_rs ──────────────────────────────────────────


class TestComputeSectorRelativeRs:
    def _stub_yfinance_sector(self, monkeypatch, sector_etf_prices: list[float]):
        """Replace _fetch_sector_etf_history to return a stub history."""

        def fake_fetch(etf):
            return _make_history(sector_etf_prices)

        # Patch at the source module — compute_sector_relative_rs uses
        # _fetch_sector_etf_history via module attribute lookup
        monkeypatch.setattr(
            macro_context, "_fetch_sector_etf_history", fake_fetch
        )

    def test_outperformer(self, monkeypatch):
        # Sector up 5% over 1M, stock up 12% over 1M → RS +7% (outperformer)
        # Need 64 rows for the 3M window check
        closes_sector = [100] * 64 + [105]
        closes_stock = [100] * 64 + [112]
        self._stub_yfinance_sector(monkeypatch, closes_sector)
        rs = macro_context.compute_sector_relative_rs(
            symbol="TEST",
            sector="Energy",
            stock_history=_make_history(closes_stock),
        )
        assert rs.sector_etf == "XLE"
        assert rs.stock_return_1m_pct == pytest.approx(12.0)
        assert rs.sector_return_1m_pct == pytest.approx(5.0)
        assert rs.rs_vs_sector_1m_pct == pytest.approx(7.0)
        # Should produce an outperformer finding
        assert any("outperforming" in f for f in rs.findings)

    def test_lagger(self, monkeypatch):
        # Sector up 10%, stock up 2% → RS -8% (lagger)
        closes_sector = [100] * 64 + [110]
        closes_stock = [100] * 64 + [102]
        self._stub_yfinance_sector(monkeypatch, closes_sector)
        rs = macro_context.compute_sector_relative_rs(
            symbol="LAG",
            sector="Energy",
            stock_history=_make_history(closes_stock),
        )
        assert rs.rs_vs_sector_1m_pct == pytest.approx(-8.0)
        # Should produce a lagger finding
        assert any("lagging" in f for f in rs.findings)

    def test_tracking(self, monkeypatch):
        # Stock and sector both up ~5% → RS ~0
        closes_sector = [100] * 64 + [105]
        closes_stock = [100] * 64 + [105]
        self._stub_yfinance_sector(monkeypatch, closes_sector)
        rs = macro_context.compute_sector_relative_rs(
            symbol="TRK",
            sector="Energy",
            stock_history=_make_history(closes_stock),
        )
        assert rs.rs_vs_sector_1m_pct == pytest.approx(0.0)
        assert any("tracking" in f for f in rs.findings)

    def test_unknown_sector(self, monkeypatch):
        closes_stock = [100] * 64 + [110]
        rs = macro_context.compute_sector_relative_rs(
            symbol="XYZ",
            sector="Made Up Sector",
            stock_history=_make_history(closes_stock),
        )
        assert rs.sector_etf is None
        assert any("Unknown sector" in f for f in rs.findings)

    def test_no_stock_history(self, monkeypatch):
        closes_sector = [100] * 64 + [110]
        self._stub_yfinance_sector(monkeypatch, closes_sector)
        rs = macro_context.compute_sector_relative_rs(
            symbol="XXX",
            sector="Energy",
            stock_history=None,
        )
        assert rs.sector_etf == "XLE"
        assert rs.sector_return_1m_pct == pytest.approx(10.0)
        assert rs.stock_return_1m_pct is None
        assert rs.rs_vs_sector_1m_pct is None

    def test_3m_extreme_outperformer_emits_extra_finding(self, monkeypatch):
        # Stock up 30% over 3M, sector up 5% → RS +25% (huge)
        closes_sector = [100] * 80 + [105]
        closes_stock = [100] * 80 + [130]
        self._stub_yfinance_sector(monkeypatch, closes_sector)
        rs = macro_context.compute_sector_relative_rs(
            symbol="MOON",
            sector="Technology",
            stock_history=_make_history(closes_stock),
        )
        assert rs.rs_vs_sector_3m_pct == pytest.approx(25.0)
        # Should produce a 3M outperformance finding
        assert any("3M outperformance" in f for f in rs.findings)

    def test_to_dict_round_trip(self, monkeypatch):
        closes_sector = [100] * 64 + [110]
        closes_stock = [100] * 64 + [115]
        self._stub_yfinance_sector(monkeypatch, closes_sector)
        rs = macro_context.compute_sector_relative_rs(
            symbol="T",
            sector="Energy",
            stock_history=_make_history(closes_stock),
        )
        d = rs.to_dict()
        assert d["sector_etf"] == "XLE"
        assert d["rs_vs_sector_1m_pct"] == pytest.approx(5.0)
        assert "findings" in d
