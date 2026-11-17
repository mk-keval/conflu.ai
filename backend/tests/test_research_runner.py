"""Tests for the research baseline runner guardrails (D-82)."""

import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
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


def _synthetic_panel(n_bars=140, n_symbols=4):
    """Tiny deterministic panel: random walks, constant ATR, periodic signals."""
    dates = pd.bdate_range("2016-01-04", periods=n_bars)
    data = {}
    signals = {}
    for i in range(n_symbols):
        rng = np.random.default_rng(100 + i)
        close = 100.0 + np.cumsum(rng.normal(0.0, 1.5, n_bars))
        close = np.maximum(close, 5.0)
        symbol = f"STK{i}"
        data[symbol] = pd.DataFrame(
            {
                "open": close,
                "high": close * 1.02,
                "low": close * 0.98,
                "close": close,
                "volume": 1_000_000,
                "atr14": 1.0,
            },
            index=dates,
        )
        signal = pd.Series(False, index=dates)
        signal.iloc[5::10] = True
        signals[symbol] = signal
    return data, signals


def test_strategy_seed_summary_reports_list_and_stats():
    summary = runner.strategy_seed_summary([42, 43, 44], [0.01, 0.02, 0.03])

    assert summary["seeds"] == [42, 43, 44]
    assert summary["r_net_mean"] == [0.01, 0.02, 0.03]
    assert summary["mean"] == pytest.approx(0.02)
    assert summary["std"] == pytest.approx(np.std([0.01, 0.02, 0.03]))
    assert summary["se"] == pytest.approx(np.std([0.01, 0.02, 0.03]) / math.sqrt(3))


def test_run_strategy_seeds_on_synthetic_panel():
    data, signals = _synthetic_panel()
    seeds = [42, 43, 44]
    exit_rules = runner.ExitRules()
    portfolio_rules = runner.PortfolioRules()

    rows, summary = runner.run_strategy_seeds(
        data, signals, exit_rules, portfolio_rules, seeds
    )

    assert [row["seed"] for row in rows] == seeds
    assert summary["seeds"] == seeds
    assert len(summary["r_net_mean"]) == len(seeds)
    assert summary["mean"] == pytest.approx(np.mean(summary["r_net_mean"]))
    assert summary["se"] == pytest.approx(summary["std"] / math.sqrt(len(seeds)))

    primary_trades, _ = runner.run_portfolio(
        data, signals, exit_rules, portfolio_rules, seed=42
    )
    assert [t.symbol for t in rows[0]["trades"]] == [t.symbol for t in primary_trades]
    assert rows[0]["r_net_mean"] == pytest.approx(
        runner.strategy_seed_r_net_mean(primary_trades)
    )


def test_artifact_contains_strategy_seeds(tmp_path):
    data, signals = _synthetic_panel()
    rows, summary = runner.run_strategy_seeds(
        data, signals, runner.ExitRules(), runner.PortfolioRules(), [42, 43]
    )
    primary = rows[0]
    rules = runner.PortfolioRules()
    metrics = runner.compute_metrics(
        runner.trades_in_window(primary["trades"], runner.EVAL_START),
        primary["equity"],
        start_equity=rules.start_equity,
    )
    result = {
        "trades": primary["trades"],
        "equity": primary["equity"],
        "metrics": metrics,
    }

    path = runner.save_results(
        "demo",
        result,
        {},
        {"matched_random": 0.5},
        {},
        {"matched_random": 0.5},
        {"git_commit": "abcdef0"},
        {"strategy_seeds": summary},
        str(tmp_path),
    )
    payload = json.loads(Path(path).read_text(encoding="utf-8"))

    assert payload["run_info"]["strategy_seeds"]["seeds"] == [42, 43]
    assert set(payload["run_info"]["strategy_seeds"]) == {
        "seeds",
        "r_net_mean",
        "mean",
        "std",
        "se",
    }
    assert payload["p_values"] == {"matched_random": 0.5}
    assert payload["p_values_seed_avg"] == {"matched_random": 0.5}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
