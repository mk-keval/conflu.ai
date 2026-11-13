"""Tests for the research baseline runner guardrails (D-82)."""

import sys

import pytest

import scripts.run_research_baseline as runner


def test_dirty_tree_refused_without_flag():
    with pytest.raises(SystemExit) as exc:
        runner._require_clean_tree(False, state=("abc1234deadbeef", True))
    assert "--allow-dirty" in str(exc.value)


def test_dirty_tree_allowed_with_flag():
    runner._require_clean_tree(True, state=("abc1234deadbeef", True))


def test_clean_tree_runs():
    runner._require_clean_tree(False, state=("abc1234deadbeef", False))


def test_unknown_git_state_does_not_block():
    """Git unavailable -> (None, None); a tarball run is not refused."""
    runner._require_clean_tree(False, state=(None, None))


def test_main_refuses_dirty_tree_before_any_work(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["run_research_baseline.py", "--setup", "low_vol_setup"])
    monkeypatch.setattr(runner, "_git_state", lambda: ("abc1234deadbeef", True))

    with pytest.raises(SystemExit) as exc:
        runner.main()
    assert "--allow-dirty" in str(exc.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
