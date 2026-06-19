"""Trade ledger — converts vectorbt trade records into structured Trade models.

Enriches raw vectorbt data with:
- MAE/MFE from daily OHLC (via MetricsComputer)
- Hold duration in bars
- Exit reason (from signal metadata)
"""

from __future__ import annotations

from datetime import timezone

import pandas as pd

from backend.app.domain.models import Trade
from backend.app.infrastructure.backtest.metrics import MetricsComputer


class TradeLedger:
    """Convert vectorbt trade records into structured Trade models.

    Post-processes portfolio.trades.records to add:
    - MAE/MFE per trade from OHLC data
    - Hold duration in bars
    - Exit reason from signal metadata lookup
    """

    def __init__(self) -> None:
        self._metrics_computer = MetricsComputer()

    def build_ledger(
        self,
        trades_records: pd.DataFrame,
        ohlcv: pd.DataFrame,
        signal_metadata: dict[int, dict] | None = None,
    ) -> list[Trade]:
        """Build structured trade ledger from vectorbt records.

        Args:
            trades_records: portfolio.trades.records DataFrame from vectorbt.
                Must have columns: column, size, entry_idx, entry_price,
                exit_idx, exit_price, pnl, return, direction, entry_fees, exit_fees.
            ohlcv: OHLCV DataFrame with 'high', 'low' columns and
                DatetimeIndex for MAE/MFE computation.
            signal_metadata: Optional dict mapping entry_idx to signal metadata
                dict (e.g., {"confidence": 0.85, "source": "rsi_oversold"}).

        Returns:
            List of Trade domain models with MAE/MFE/hold_duration/exit_reason populated.
        """
        if trades_records is None or trades_records.empty:
            return []

        trades: list[Trade] = []
        signal_metadata = signal_metadata or {}

        for _, record in trades_records.iterrows():
            entry_idx = int(record["entry_idx"])
            exit_idx = int(record.get("exit_idx", entry_idx))
            direction = "Long" if record.get("direction", 1) == 1 else "Short"

            # Compute MAE/MFE
            mae, mfe = MetricsComputer.compute_mae_mfe(
                trade_entry_idx=entry_idx,
                trade_exit_idx=exit_idx,
                entry_price=float(record["entry_price"]),
                ohlcv=ohlcv,
                direction=direction,
            )

            # Compute hold duration
            hold_duration = exit_idx - entry_idx

            # Lookup signal metadata for this entry
            meta = signal_metadata.get(entry_idx, {})
            exit_reason = meta.get("exit_reason", "signal_close")

            # Map column index to symbol name (if ohlcv has columns as symbol names)
            col_idx = int(record["column"])
            symbol = self._idx_to_symbol(col_idx, ohlcv)

            entry_time = ohlcv.index[entry_idx] if entry_idx < len(ohlcv) else ohlcv.index[-1]
            exit_time = ohlcv.index[exit_idx] if exit_idx < len(ohlcv) else ohlcv.index[-1]

            trade = Trade(
                symbol=symbol,
                entry_time=entry_time.to_pydatetime().replace(tzinfo=timezone.utc),
                exit_time=exit_time.to_pydatetime().replace(tzinfo=timezone.utc),
                entry_price=float(record["entry_price"]),
                exit_price=float(record.get("exit_price", float("nan"))),
                size=abs(float(record["size"])),
                fees=float(record.get("entry_fees", 0)) + float(record.get("exit_fees", 0)),
                pnl=float(record.get("pnl", 0)),
                mae=mae,
                mfe=mfe,
                hold_duration_bars=hold_duration,
                exit_reason=exit_reason,
            )
            trades.append(trade)

        return trades

    @staticmethod
    def _idx_to_symbol(col_idx: int, ohlcv: pd.DataFrame) -> str:
        """Map column index to symbol name using OHLCV DataFrame columns.

        If ohlcv.columns are symbol names, returns the matching symbol.
        Otherwise returns 'SYMBOL_{col_idx}'.
        """
        if hasattr(ohlcv, "columns") and col_idx < len(ohlcv.columns):
            col_name = ohlcv.columns[col_idx]
            if isinstance(col_name, str):
                return col_name
        return f"SYMBOL_{col_idx}"
