"""Regression test for the D-43 bug: TickerAnalysisService.analyze_async failed
silently with `TypeError: analyze() got an unexpected keyword argument
'daily_ohlcv'` because the orchestrator pre-fetches OHLCV to enable parallel
fan-out and passes it as kwargs into ``technical.analyze``, but the analyze
function signature was never updated to accept those kwargs. The result was
``technical=null`` on every response, so the frontend's Technical tab rendered
an empty ``<div></div>``.

This test exercises the orchestrator -> technical.analyze call path and asserts
the technical field is populated on the response.
"""
from __future__ import annotations

import inspect
from unittest.mock import MagicMock, patch

import pytest

from backend.app.domain.ticker_analysis import technical as tech_module
from backend.app.domain.ticker_analysis.orchestrator import TickerAnalysisService


def test_technical_analyze_signature_accepts_ohlcv_kwargs() -> None:
    """D-43 regression: the orchestrator passes daily/weekly/intraday OHLCV
    frames as kwargs into ``technical.analyze`` to enable parallel pre-fetch.
    The signature MUST accept those names — otherwise every request raises
    TypeError and the frontend's Technical tab is empty.
    """
    sig = inspect.signature(tech_module.analyze)
    for name in ("daily_ohlcv", "weekly_ohlcv", "intraday_4h_ohlcv", "intraday_1h_ohlcv"):
        assert name in sig.parameters, (
            f"technical.analyze() is missing kwarg {name!r} that the orchestrator "
            f"passes when pre-fetching OHLCV. Without it, every request fails with "
            f"TypeError and the Technical tab renders empty (D-43 regression)."
        )


@pytest.mark.asyncio
async def test_analyze_async_populates_technical(monkeypatch) -> None:
    """End-to-end regression: a real analyze_async call must return a
    response with a non-null ``technical`` field. The previous bug returned
    technical=None because the analyze() call raised TypeError which the
    per-module runner silently swallowed, so the request 'succeeded' with an
    empty technical field.
    """
    # Stub yfinance to avoid real network calls — return a minimal empty
    # DataFrame so the module's _fetch_*_ohlcv helpers don't blow up.
    import pandas as pd

    empty_df = pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])

    def fake_history(*args, **kwargs):  # yfinance .Ticker(...).history(...)
        return empty_df

    def fake_ticker(symbol):
        m = MagicMock()
        m.info = {"currentPrice": 100.0, "regularMarketPrice": 100.0, "sector": "Tech"}
        m.history = fake_history
        return m

    monkeypatch.setattr("yfinance.Ticker", fake_ticker)

    # Patch the heavy modules so we don't pull real data; just ensure analyze() is
    # called with the kwargs the orchestrator passes and returns a TechnicalAnalysis.
    fake_daily_result = tech_module.TechnicalAnalysis(
        score=0.5,
        ma_alignment="mixed",
        rsi=57.0,
        rsi_regime="neutral_bullish",
        adx=14.0,
        adx_verdict="weak",
        atr_pct=2.4,
        volatility_regime="normal",
        findings=["stub"],
    )

    async def run() -> None:
        svc = TickerAnalysisService()
        req = MagicMock()
        req.symbol = "AAPL"
        req.timeframe = "1D"
        req.tv_data = None
        req.regime = None

        with (
            patch.object(tech_module, "analyze", return_value=fake_daily_result) as mock_analyze,
            patch("backend.app.domain.ticker_analysis.orchestrator.fundamentals.analyze", return_value=None),
            patch("backend.app.domain.ticker_analysis.orchestrator.earnings.analyze", return_value=None),
            patch("backend.app.domain.ticker_analysis.orchestrator.sentiment.analyze", return_value=None),
            patch("backend.app.domain.ticker_analysis.orchestrator.risk_module.analyze", return_value=None),
        ):
            result = await svc.analyze_async(req)

        # The signature test above would have failed at import time. This test
        # also asserts the orchestrator passes the OHLCV kwargs through.
        assert mock_analyze.called, "technical.analyze was not invoked"
        call_kwargs = mock_analyze.call_args.kwargs
        for name in ("daily_ohlcv", "weekly_ohlcv", "intraday_4h_ohlcv", "intraday_1h_ohlcv"):
            assert name in call_kwargs, (
                f"Orchestrator did not pass {name!r} kwarg to technical.analyze"
            )

        # And the response carries the technical payload through.
        assert result.technical is not None, (
            "analyze_async returned technical=None — D-43 regression: the "
            "orchestrator's call to technical.analyze is failing silently."
        )

    await run()
