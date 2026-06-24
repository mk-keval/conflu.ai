"""OHLCV data quality validation."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from backend.app.core.logging import get_logger

log = get_logger("conflu.ingest.quality")


@dataclass
class QualityReport:
    """Result of a quality validation pass."""

    total_rows: int = 0
    rows_discarded: int = 0
    duplicate_timestamps: int = 0
    ohlc_inconsistencies: int = 0
    negative_volume: int = 0
    zero_negative_prices: int = 0
    nan_values: int = 0
    passed: bool = True


def validate_ohlcv(df: pd.DataFrame) -> tuple[pd.DataFrame, QualityReport]:
    """Validate OHLCV data quality. Returns (cleaned_df, report).

    Validation rules (D-09):
    1. No NaN values in any column
    2. No duplicate (symbol, timestamp, timeframe) combos — keep first occurrence
    3. OHLC consistency: high >= max(open, close), low <= min(open, close)
    4. Volume >= 0
    5. All prices (open, high, low, close) > 0
    6. 'ticker' column (if present) is used for symbol extraction
    """
    report = QualityReport()
    if df.empty:
        return df, report

    n_before = len(df)
    report.total_rows = n_before

    # 1. Handle 'time' column from TradingView (Unix timestamp)
    if "time" in df.columns and "timestamp" not in df.columns:
        df["timestamp"] = pd.to_datetime(df["time"], unit="s", utc=True)

    # 2. Remove NaN rows
    nan_mask = df[["open", "high", "low", "close", "volume"]].isna().any(axis=1)
    df = df[~nan_mask].copy()
    report.nan_values = int(nan_mask.sum())

    # 3. Handle ticker -> symbol conversion if ticker column exists
    if "ticker" in df.columns and "symbol" not in df.columns:
        df["symbol"] = df["ticker"].apply(lambda t: str(t).split(":")[-1] if ":" in str(t) else str(t))

    # 4. Remove duplicate (symbol, timestamp, timeframe) — keep first
    if "symbol" in df.columns and "timestamp" in df.columns:
        if "timeframe" not in df.columns:
            df["timeframe"] = "1D"  # default if not present
        before_dedup = len(df)
        df = df.drop_duplicates(subset=["symbol", "timestamp", "timeframe"], keep="first")
        report.duplicate_timestamps = before_dedup - len(df)

    # 4. OHLC consistency: high >= max(open, close)
    ohlc_mask = (df["high"] >= df[["open", "close"]].max(axis=1)) & (df["low"] <= df[["open", "close"]].min(axis=1))
    # 5. Volume >= 0
    vol_mask = df["volume"] >= 0
    # 6. Prices > 0
    price_mask = (df[["open", "high", "low", "close"]] > 0).all(axis=1)

    combined_mask = ohlc_mask & vol_mask & price_mask
    report.ohlc_inconsistencies = int((~ohlc_mask).sum())
    report.negative_volume = int((~vol_mask).sum())
    report.zero_negative_prices = int((~price_mask).sum())

    rows_discarded = int((~combined_mask).sum())
    report.rows_discarded = rows_discarded

    if rows_discarded > 0:
        report.passed = False
        log.warning(
            "quality_check_failed",
            total_rows=n_before,
            discarded=rows_discarded,
            nan_values=report.nan_values,
            duplicates=report.duplicate_timestamps,
            ohlc_inconsistencies=report.ohlc_inconsistencies,
            negative_volume=report.negative_volume,
            bad_prices=report.zero_negative_prices,
        )

    return df[combined_mask].copy(), report


def validate_ohlcv_strict(df: pd.DataFrame) -> pd.DataFrame:
    """Validate OHLCV data strictly — raises ValueError on any failure.

    For use in tests / dry-run mode where strict adherence is required.
    """
    clean_df, report = validate_ohlcv(df)
    if not report.passed:
        raise ValueError(
            f"OHLCV validation failed: {report.rows_discarded} rows discarded "
            f"({report.ohlc_inconsistencies} OHLC inconsistencies, "
            f"{report.negative_volume} negative volume, "
            f"{report.zero_negative_prices} bad prices, "
            f"{report.nan_values} NaN values, "
            f"{report.duplicate_timestamps} duplicates)"
        )
    return clean_df


def merge_quality_reports(reports: list[QualityReport]) -> QualityReport:
    """Aggregate multiple quality reports into one."""
    merged = QualityReport()
    for r in reports:
        merged.total_rows += r.total_rows
        merged.rows_discarded += r.rows_discarded
        merged.duplicate_timestamps += r.duplicate_timestamps
        merged.ohlc_inconsistencies += r.ohlc_inconsistencies
        merged.negative_volume += r.negative_volume
        merged.zero_negative_prices += r.zero_negative_prices
        merged.nan_values += r.nan_values
        if not r.passed:
            merged.passed = False
    return merged
