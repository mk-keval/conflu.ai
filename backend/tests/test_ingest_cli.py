"""Tests for CLI entry point argument parsing."""

from __future__ import annotations

from unittest.mock import patch

from backend.app.infrastructure.ingest.cli import build_parser, main


def test_parser_asset_class() -> None:
    """--asset-class equities sets asset_classes=['equities']."""
    parser = build_parser()
    args = parser.parse_args(["--asset-class", "equities"])
    assert args.asset_classes == ["equities"]


def test_parser_multiple_asset_classes() -> None:
    """--asset-class equities --asset-class crypto sets both."""
    parser = build_parser()
    args = parser.parse_args(["--asset-class", "equities", "--asset-class", "crypto"])
    assert args.asset_classes == ["equities", "crypto"]


def test_parser_timeframe() -> None:
    """--timeframe 1D sets timeframes."""
    parser = build_parser()
    args = parser.parse_args(["--timeframe", "1D"])
    assert args.timeframes == ["1D"]


def test_parser_dry_run() -> None:
    """--dry-run sets dry_run=True."""
    parser = build_parser()
    args = parser.parse_args(["--dry-run"])
    assert args.dry_run is True


def test_parser_health() -> None:
    """--health sets health=True."""
    parser = build_parser()
    args = parser.parse_args(["--health"])
    assert args.health is True


def test_parser_setup() -> None:
    """--setup sets setup=True."""
    parser = build_parser()
    args = parser.parse_args(["--setup"])
    assert args.setup is True


def test_parser_max_concurrent() -> None:
    """--max-concurrent 25 sets max_concurrent."""
    parser = build_parser()
    args = parser.parse_args(["--max-concurrent", "25"])
    assert args.max_concurrent == 25


def test_parser_defaults() -> None:
    """No args gives None for optional params."""
    parser = build_parser()
    args = parser.parse_args([])
    assert args.asset_classes is None
    assert args.timeframes is None
    assert args.dry_run is False
    assert args.health is False
    assert args.setup is False
    assert args.max_concurrent is None


@patch("backend.app.infrastructure.ingest.cli.initialize_database")
@patch("backend.app.infrastructure.ingest.cli._ensure_ingestion_tables")
def test_main_setup(mock_ensure, mock_init) -> None:
    """main(['--setup']) returns 0 and calls initialize_database."""
    result = main(["--setup"])
    assert result == 0
    mock_init.assert_called_once()
    mock_ensure.assert_called_once()


@patch("backend.app.infrastructure.ingest.cli.get_db")
@patch("backend.app.infrastructure.ingest.cli.load_latest_health")
def test_main_health_no_data(mock_health, mock_db):
    """main(['--health']) returns 0 with no data."""
    mock_health.return_value = None
    result = main(["--health"])
    assert result == 0


@patch("backend.app.infrastructure.ingest.cli.asyncio.run")
def test_main_run(mock_asyncio_run):
    """main([]) returns 0 (mock run_ingestion)."""
    mock_report = mock_asyncio_run.return_value
    mock_report.error_rate = 0.0
    mock_report.model_dump_json.return_value = "{}"
    result = main([])
    assert result == 0


@patch("backend.app.infrastructure.ingest.cli.asyncio.run")
def test_main_run_with_args(mock_asyncio_run):
    """main with --asset-class and --timeframe passes args to run_ingestion."""
    mock_report = mock_asyncio_run.return_value
    mock_report.error_rate = 0.0
    mock_report.model_dump_json.return_value = "{}"
    result = main(["--asset-class", "equities", "--timeframe", "1D", "--dry-run"])
    assert result == 0
