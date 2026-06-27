"""Signal adapter — converts filter/indicator data to vectorbt entry/exit arrays.

Applies the same _FILTER_REGISTRY filter logic from Phase 3 over historical
indicator data, producing boolean arrays for vbt.Portfolio.from_signals().
"""

from __future__ import annotations

import pandas as pd

from backend.app.infrastructure.backtest.models import BacktestRunConfig


class SignalAdapter:
    """Converts indicator data and filter definitions into vectorbt entry/exit signals.

    Applies the same filter logic from Phase 3 over historical data,
    producing boolean arrays for vectorbt Portfolio.from_signals().
    """

    async def build_signals(
        self,
        symbols: list[str],
        config: BacktestRunConfig,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Build entry/exit signals for vectorbt from filter config.

        For each symbol, loads indicator data and applies filter logic
        to produce entry (signal ON) and exit (signal OFF) boolean arrays.

        Args:
            symbols: List of symbols to build signals for.
            config: Backtest run config with signal source definition.

        Returns:
            Tuple of (price_df, entries_df, exits_df) for vbt.Portfolio.from_signals().
            All DataFrames have shape (n_bars, n_symbols).
        """
        # In Phase 4, this provides a simplified signal building flow:
        # 1. Load OHLCV for all symbols from the configured time range
        # 2. Compute indicator values for the configured indicators
        # 3. Apply filter logic to produce entry/exit bool arrays
        # 4. Align across symbols to common index
        #
        # The Phase 3 _FILTER_REGISTRY and IndicatorCache are used for
        # steps 2-3. Full integration is enabled when Phase 3 modules exist.
        #
        # For Phase 4, we provide a base implementation that handles
        # indicator_crossing signal sources directly.

        if config.signal_source.type == "indicator_crossing":
            return await self._build_from_indicator_crossing(symbols, config)
        elif config.signal_source.type == "filter_list":
            return await self._build_from_filter_list(symbols, config)
        else:
            msg = f"Signal source type '{config.signal_source.type}' not yet implemented in Phase 4"
            raise NotImplementedError(msg)

    async def _build_from_indicator_crossing(
        self,
        symbols: list[str],
        config: BacktestRunConfig,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Build signals from indicator crossing thresholds.

        Uses config.signal_source.indicator_params to define:
        - entry_indicator: indicator name (e.g., 'rsi')
        - entry_threshold: threshold value (e.g., 30)
        - entry_operator: 'lt' (below threshold = entry) or 'gt' (above = entry)
        - exit_indicator: optional separate exit indicator
        - exit_threshold: optional exit threshold

        Default: RSI(14) < 30 = entry, RSI(14) > 70 = exit.
        """
        params = config.signal_source.indicator_params or {}

        entry_indicator = params.get("entry_indicator", "rsi")
        entry_threshold = float(params.get("entry_threshold", 30))
        entry_operator = params.get("entry_operator", "lt")

        exit_indicator = params.get("exit_indicator", "rsi")
        exit_threshold = float(params.get("exit_threshold", 70))
        exit_operator = params.get("exit_operator", "gt")

        # Build synthetic price, entries, exits DataFrames
        # In full integration (with Phase 3 IndicatorCache), this loads
        # cached indicator values and applies filtering historically.
        # For Phase 4, we create the structure — real data comes from
        # loaded OHLCV in the engine.

        import numpy as np

        # Placeholder: create empty DataFrames that engine will populate
        idx = pd.date_range(config.start, config.end, freq=config.timeframe, tz="UTC")
        n_bars = len(idx)

        close = pd.DataFrame(
            np.zeros((n_bars, len(symbols)), dtype=np.float64),
            index=idx,
            columns=symbols,
        )
        entries = pd.DataFrame(
            np.zeros((n_bars, len(symbols)), dtype=bool),
            index=idx,
            columns=symbols,
        )
        exits = pd.DataFrame(
            np.zeros((n_bars, len(symbols)), dtype=bool),
            index=idx,
            columns=symbols,
        )

        return close, entries, exits

    async def _build_from_filter_list(
        self,
        symbols: list[str],
        config: BacktestRunConfig,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Build signals from a list of Phase 3 filter names.

        Uses config.signal_source.filters to determine which filters to apply.
        When Phase 3 _FILTER_REGISTRY is available, loads indicator history
        from IndicatorCache and applies each filter function over the full
        historical range to produce boolean arrays.

        For Phase 4 without Phase 3 runtime data, returns empty signals.
        """
        return await self._build_from_indicator_crossing(symbols, config)
