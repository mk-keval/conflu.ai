# Deep Analysis Orchestrator -- On-demand comprehensive analysis for TV-discovered tickers.
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd

from backend.app.core.database import get_db
from backend.app.core.logging import get_logger
from backend.app.infrastructure.analysis.levels import compute_atr_levels, compute_fallback_levels
from backend.app.infrastructure.backtest.engine import BacktestEngine
from backend.app.infrastructure.backtest.models import BacktestRunConfig
from backend.app.infrastructure.risk.engine import RiskEngine

log = get_logger("conflu.analysis.deep")


@dataclass
class DeepAnalysisResult:
    symbol: str
    timeframe: str
    timestamp: datetime
    ohlcv: pd.DataFrame
    indicators: dict[str, pd.Series]
    backtest: Any | None = None
    risk: Any | None = None
    confluence_score: float = 0.0
    entry: float = 0.0
    stop_loss: float = 0.0
    targets: list[float] = field(default_factory=list)


class DeepAnalysisOrchestrator:
    def __init__(self) -> None:
        self._backtest_engine = BacktestEngine()
        self._risk_engine = RiskEngine()
        self._log = get_logger("conflu.analysis.deep")

    async def analyze(
        self,
        symbol: str,
        timeframe: str = "1D",
        include_backtest: bool = True,
        include_risk: bool = True,
    ) -> DeepAnalysisResult:
        self._log.info("deep_analysis_start", symbol=symbol, timeframe=timeframe)

        # 1. Load OHLCV from DuckDB
        ohlcv = await self._load_ohlcv(symbol, timeframe)
        if ohlcv is None or ohlcv.empty:
            self._log.warning("no_ohlcv_data", symbol=symbol)
            return DeepAnalysisResult(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=datetime.now(timezone.utc),
                ohlcv=pd.DataFrame(),
                indicators={},
            )

        # 2. Compute indicators
        indicators = await self._compute_indicators(ohlcv)

        # 3. Compute confluence score from indicators
        confluence = self._compute_confluence(ohlcv, indicators)

        # 4. Run backtest if requested
        backtest_result = None
        if include_backtest:
            backtest_result = await self._run_backtest(symbol, timeframe, ohlcv)

        # 6. Run risk analysis if requested
        risk_result = None
        if include_risk:
            risk_result = await self._run_risk(symbol, ohlcv)

        # 7. Build entry/exit/target from confluence
        entry, stop_loss, targets = self._compute_entry_exit(ohlcv, indicators)

        result = DeepAnalysisResult(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=datetime.now(timezone.utc),
            ohlcv=ohlcv,
            indicators=indicators,
            backtest=backtest_result,
            risk=risk_result,
            confluence_score=confluence,
            entry=entry,
            stop_loss=stop_loss,
            targets=targets,
        )

        self._log.info("deep_analysis_complete", symbol=symbol, score=confluence)
        return result

    async def _load_ohlcv(self, symbol: str, timeframe: str) -> pd.DataFrame | None:
        try:
            with get_db(read_only=True) as con:
                result = con.sql(
                    """
                    SELECT symbol, timestamp, open, high, low, close, volume
                    FROM ohlcv
                    WHERE symbol = ? AND timeframe = ?
                    ORDER BY timestamp
                    """,
                    params=[symbol, timeframe],
                ).fetchdf()
            if result.empty:
                return None
            result.set_index("timestamp", inplace=True)
            result.index = pd.DatetimeIndex(result.index)
            return result
        except Exception:
            return None

    async def _compute_indicators(self, ohlcv: pd.DataFrame) -> dict[str, Any]:
        try:
            from backend.app.infrastructure.indicators import compute_all
            return await asyncio.to_thread(compute_all, ohlcv)
        except Exception:
            return {}

    def _compute_confluence(self, ohlcv: pd.DataFrame, indicators: dict[str, pd.Series]) -> float:
        score = 0.0
        close = ohlcv["close"]
        if "EMA20" in indicators and "EMA50" in indicators:
            if close.iloc[-1] > indicators["EMA20"].iloc[-1] > indicators["EMA50"].iloc[-1]:
                score += 20
        if "RSI" in indicators:
            rsi = indicators["RSI"].iloc[-1]
            if 40 < rsi < 60:
                score += 15
            elif rsi < 30:
                score += 25
        if "MACD" in indicators and "MACD.signal" in indicators:
            macd = indicators["MACD"].iloc[-1]
            signal = indicators["MACD.signal"].iloc[-1]
            if macd > signal:
                score += 15
        return min(100.0, score)

    async def _run_backtest(self, symbol: str, timeframe: str, ohlcv: pd.DataFrame) -> dict[str, Any]:
        from backend.app.infrastructure.backtest.engine import BacktestEngine
        from backend.app.infrastructure.backtest.models import BacktestRunConfig
        config = BacktestRunConfig(
            run_id=f"deep_{symbol}_{timeframe}",
            symbols=[symbol],
            timeframe=timeframe,
            start=ohlcv.index[0],
            end=ohlcv.index[-1],
            initial_cash=100000.0,
            position_sizing="atr",
        )
        engine = BacktestEngine()
        result = await engine.run(config)
        return result.model_dump()

    async def _run_risk(self, symbol: str, ohlcv: pd.DataFrame) -> dict[str, Any]:
        from backend.app.infrastructure.risk.engine import RiskEngine
        risk_engine = RiskEngine()
        result = await risk_engine.analyze_portfolio(
            portfolio_id=f"deep_{symbol}",
            symbols=[symbol],
            positions={symbol: 1.0},
        )
        return result.model_dump()

    def _compute_entry_exit(
        self, ohlcv: pd.DataFrame, indicators: dict[str, pd.Series]
    ) -> tuple[float, float, list[float]]:
        close = ohlcv["close"].iloc[-1]
        atr = None
        if "ATR" in indicators:
            atr = indicators["ATR"].iloc[-1]
        # Shared math (infrastructure/analysis/levels.py) — historical policy:
        # fixed 2x ATR stop / 2x / 3x ATR targets; ±5%/±10% fallback without ATR.
        if atr and atr > 0:
            levels = compute_atr_levels(close, atr, 2.0, 2.0, 3.0)
        else:
            levels = compute_fallback_levels(close)
        return levels.entry, levels.stop_loss, [levels.target_1, levels.target_2]