"""Screen results export to CSV and JSON formats."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import pandas as pd

from backend.app.core.logging import get_logger

log = get_logger("conflu.screener.export")


def export_csv(results: pd.DataFrame, path: str | Path) -> None:
    """Export screen results to CSV.

    Columns: symbol, score, matched_filters, indicator_values, timestamp.
    matched_filters stored as pipe-separated string.

    Args:
        results: DataFrame with screen results.
        path: Output file path.
    """
    df = results.copy()

    # Flatten list columns for CSV
    if "matched_filters" in df.columns:
        df["matched_filters"] = df["matched_filters"].apply(
            lambda x: "|".join(x) if isinstance(x, list) else str(x),
        )

    # Flatten indicator_values dict
    if "indicator_values" in df.columns and "indicators" not in df.columns:
        df["indicators"] = df["indicator_values"].apply(
            lambda x: str(x) if isinstance(x, dict) else "",
        )
    elif "indicators" in df.columns:
        df["indicators"] = df["indicators"].apply(
            lambda x: str(x) if isinstance(x, dict) else "",
        )

    df.to_csv(path, index=False)
    log.info("csv_exported", path=str(path), rows=len(df))


def export_json(
    results: pd.DataFrame,
    path: str | Path,
    orient: Literal["records", "split", "index"] = "records",
) -> None:
    """Export screen results to JSON.

    Args:
        results: DataFrame with screen results.
        path: Output file path.
        orient: JSON orientation:
            - 'records' -> list of objects (default)
            - 'split' -> {columns, index, data}
            - 'index' -> {index: {column: value}}
    """
    results.to_json(path, orient=orient, date_format="iso")
    log.info("json_exported", path=str(path), orient=orient, rows=len(results))
