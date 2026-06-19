"""Tests for structured logging configuration."""

from __future__ import annotations

from backend.app.core.logging import configure_logging, get_logger, set_correlation_id


class TestConfigureLogging:
    def test_configure_stdout(self) -> None:
        """Verify configure_logging runs without error."""
        configure_logging(log_level="DEBUG", log_json=False)
        log = get_logger("test")
        assert log is not None

    def test_configure_json(self) -> None:
        """Verify JSON configuration runs without error."""
        configure_logging(log_level="INFO", log_json=True)
        log = get_logger("test-json")
        assert log is not None


class TestCorrelationId:
    def test_set_generates_id(self) -> None:
        cid = set_correlation_id()
        assert isinstance(cid, str)
        assert len(cid) > 0

    def test_set_provided_id(self) -> None:
        cid = set_correlation_id("my-test-id")
        assert cid == "my-test-id"


class TestGetLogger:
    def test_default_name(self) -> None:
        log = get_logger()
        assert log is not None

    def test_custom_name(self) -> None:
        log = get_logger("custom.module")
        assert log is not None
