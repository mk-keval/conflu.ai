"""Tests for the research baseline runner guardrails (D-82)."""

import subprocess
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


def _dirty_state(*_args, **_kwargs):
    return ("abc1234deadbeef", True)


def test_main_refuses_dirty_tree_before_any_work(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["run_research_baseline.py", "--setup", "low_vol_setup"])
    monkeypatch.setattr(runner, "_git_state", _dirty_state)

    with pytest.raises(SystemExit) as exc:
        runner.main()
    assert "--allow-dirty" in str(exc.value)


def _git(repo, *args):
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args],
        cwd=repo, check=True, capture_output=True, text=True,
    )


@pytest.fixture
def temp_repo(tmp_path, monkeypatch):
    """A throwaway git repo with a tracked file and the artifact directory."""
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "tracked.txt").write_text("hello\n", encoding="utf-8")
    out = tmp_path / "docs" / "backtests" / "research"
    out.mkdir(parents=True)
    (out / ".gitkeep").write_text("", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")
    monkeypatch.setattr(runner, "_repo_root", lambda: tmp_path)
    return tmp_path, out


def test_clean_tree_not_dirty(temp_repo):
    _, out = temp_repo
    rev, dirty = runner._git_state(str(out))
    assert rev is not None
    assert dirty is False


def test_modified_tracked_file_is_dirty(temp_repo):
    repo, out = temp_repo
    (repo / "tracked.txt").write_text("changed\n", encoding="utf-8")
    assert runner._git_state(str(out))[1] is True


def test_modified_tracked_file_in_output_dir_is_dirty(temp_repo):
    _, out = temp_repo
    (out / ".gitkeep").write_text("changed\n", encoding="utf-8")
    assert runner._git_state(str(out))[1] is True


def test_untracked_file_in_output_dir_not_dirty(temp_repo):
    _, out = temp_repo
    (out / "statistical_mean_reversion_29990101_000000.json").write_text(
        "{}", encoding="utf-8"
    )
    assert runner._git_state(str(out))[1] is False


def test_untracked_file_elsewhere_is_dirty(temp_repo):
    repo, out = temp_repo
    (repo / "new_source.py").write_text("x = 1\n", encoding="utf-8")
    assert runner._git_state(str(out))[1] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
