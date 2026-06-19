"""Tests for CSV/JSON export utilities."""

from __future__ import annotations

import json
import os
import tempfile

import pandas as pd
import pytest

from backend.app.infrastructure.screener.export import export_csv, export_json


class TestExportCsv:
    """Test CSV export."""

    def test_writes_csv_file(self) -> None:
        df = pd.DataFrame({
            "symbol": ["AAPL", "MSFT"],
            "score": [100.0, 80.0],
            "matched_filters": [["rsi_oversold"], ["macd_bullish", "rvol_high"]],
        })
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
            tmp_path = f.name
        try:
            export_csv(df, tmp_path)
            assert os.path.exists(tmp_path)
            with open(tmp_path) as f:
                content = f.read()
            assert "symbol" in content
            assert "AAPL" in content
            assert "MSFT" in content
        finally:
            os.unlink(tmp_path)

    def test_csv_has_header_and_data(self) -> None:
        df = pd.DataFrame({
            "symbol": ["TEST"],
            "score": [100.0],
            "matched_filters": [[]],
        })
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
            tmp_path = f.name
        try:
            export_csv(df, tmp_path)
            with open(tmp_path) as f:
                lines = f.readlines()
            assert len(lines) == 2  # header + 1 data row
        finally:
            os.unlink(tmp_path)

    def test_empty_dataframe(self) -> None:
        df = pd.DataFrame(columns=["symbol", "score", "matched_filters"])
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
            tmp_path = f.name
        try:
            export_csv(df, tmp_path)
            with open(tmp_path) as f:
                content = f.read()
            assert "symbol,score,matched_filters" in content
        finally:
            os.unlink(tmp_path)


class TestExportJson:
    """Test JSON export."""

    def test_writes_json_file(self) -> None:
        df = pd.DataFrame({
            "symbol": ["AAPL", "MSFT"],
            "score": [100.0, 80.0],
        })
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            tmp_path = f.name
        try:
            export_json(df, tmp_path)
            assert os.path.exists(tmp_path)
            with open(tmp_path) as f:
                data = json.load(f)
            assert isinstance(data, list)
            assert len(data) == 2
            assert data[0]["symbol"] == "AAPL"
        finally:
            os.unlink(tmp_path)

    def test_json_records_orient(self) -> None:
        df = pd.DataFrame({
            "symbol": ["A"],
            "score": [100.0],
        })
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            tmp_path = f.name
        try:
            export_json(df, tmp_path, orient="records")
            with open(tmp_path) as f:
                data = json.load(f)
            assert isinstance(data, list)
        finally:
            os.unlink(tmp_path)

    def test_json_split_orient(self) -> None:
        df = pd.DataFrame({
            "symbol": ["A"],
            "score": [100.0],
        })
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            tmp_path = f.name
        try:
            export_json(df, tmp_path, orient="split")
            with open(tmp_path) as f:
                data = json.load(f)
            assert "columns" in data
            assert "data" in data
        finally:
            os.unlink(tmp_path)
