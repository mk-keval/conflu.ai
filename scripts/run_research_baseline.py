#!/usr/bin/env python
"""Research baseline backtest runner.

Usage:
    python scripts/run_research_baseline.py [--setup SETUP] [--universe UNIVERSE]
        [--start START] [--end END] [--cache-dir DIR] [--tag TAG]

Runs a baseline backtest for a setup and compares it against random, permuted
and time-shifted control distributions. Writes a self-describing JSON artifact.
"""

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.research.data import (
    download_daily,
    load_universe,
    panel_span,
    coverage_report,
)
from backend.app.research.indicators import add_indicators
from backend.app.research.setups import (
    SETUPS,
    eligible,
    statistical_mean_reversion,
    breakout_52week,
    low_vol_setup,
    volume_trend_accumulation
)
from backend.app.research.engine import (
    run_portfolio,
    ExitRules,
    PortfolioRules,
    Trade,
    NON_TRADABLE,
)
from backend.app.research.metrics import (
    compute_metrics,
    print_metrics,
    metrics_to_dict,
    trades_in_window,
    BacktestMetrics,
)
from backend.app.research.control import (
    run_control_suite,
    compute_control_pvalues,
    summarize_control_results
)

# How far the actual panel may fall short of the requested span before the run
# refuses to write an artifact. Holidays and weekends need a few days of slack.
SPAN_TOLERANCE_DAYS = 10

# 2015 is indicator/universe warm-up. Trade statistics are evaluated from here
# so the real strategy and every control share one evaluation window.
EVAL_START = "2016-01-01"


def load_setup_config(setup_name: str) -> dict:
    """Load setup configuration from YAML."""
    # Map setup names to config filenames
    config_map = {
        "statistical_mean_reversion": "statistical-mean-reversion.yaml",
        "breakout_52week": "52week-breakout.yaml",
        "low_vol_setup": "low-vol-setup.yaml",
        "volume_trend_accumulation": "volume-trend-accumulation.yaml"
    }
    config_filename = config_map.get(setup_name, f"{setup_name}.yaml")
    config_path = Path(f"config/screens/{config_filename}")
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")
    with open(config_path) as f:
        return yaml.safe_load(f)


def get_setup_function(setup_name: str):
    """Get setup function by name."""
    return SETUPS.get(setup_name)


def _sha256_file(path: str) -> str | None:
    """SHA-256 of a file, or None when it cannot be read."""
    try:
        digest = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def _repo_root() -> Path:
    """Repository root (the parent of ``scripts/``)."""
    return Path(__file__).parent.parent


def _repo_relative_dir(directory: str | None, root: Path) -> str | None:
    """``directory`` as a repo-root-relative POSIX path, or None if outside."""
    if not directory:
        return None
    try:
        return Path(directory).resolve().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        return None


def _is_within(path: str, directory: str) -> bool:
    """True when repo-relative ``path`` is ``directory`` or lies beneath it."""
    path = path.replace("\\", "/")
    directory = directory.strip("/")
    return path == directory or path.startswith(directory + "/")


def _status_has_dirt(status: str, output_dir: str | None, root: Path) -> bool:
    """True when ``git status --porcelain -z`` reports a blocking change.

    Entries are ``XY path\\0``; renames and copies carry the original path as
    an extra NUL-separated field. Untracked files inside ``output_dir`` are the
    run's own artifacts, so they are ignored. Tracked edits (including inside
    ``output_dir``) and untracked files anywhere else still count as dirty.
    """
    ignored = _repo_relative_dir(output_dir, root)
    entries = status.split("\0")
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if len(entry) < 4:
            continue
        code, path = entry[:2], entry[3:]
        if code[0] in ("R", "C"):
            index += 1  # next field is the rename/copy source path
        if code == "??" and ignored is not None and _is_within(path, ignored):
            continue
        return True
    return False


def _git_state(output_dir: str | None = None) -> tuple[str | None, bool | None]:
    """Return (HEAD revision, working-tree-dirty) when git is available.

    Untracked files inside ``output_dir`` (the run's own artifacts) do not make
    the tree dirty; tracked changes anywhere and untracked files elsewhere do.
    """
    try:
        root = _repo_root()
        rev = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root,
            capture_output=True, text=True, timeout=10, check=True
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain", "-z", "--untracked-files=all"],
            cwd=root, capture_output=True, text=True, timeout=10, check=True
        ).stdout
        return rev or None, _status_has_dirt(status, output_dir, root)
    except Exception:
        return None, None


def _require_clean_tree(
    allow_dirty: bool,
    state=None,
    output_dir: str | None = None,
) -> None:
    """Refuse a run whose artifacts would be recorded as dirty.

    ``state`` is a ``(revision, dirty)`` pair; when omitted it is read from git
    with ``output_dir`` exempted (the run's own untracked artifacts). A run on a
    dirty tree records ``run.code.dirty = true``, which makes the artifact hard
    to reproduce; ``--allow-dirty`` accepts that explicitly.
    Unknown git state (git unavailable) does not block.
    """
    rev, dirty = _git_state(output_dir) if state is None else state
    if dirty is True and not allow_dirty:
        raise SystemExit(
            "Working tree is dirty (HEAD {rev}). Commit or stash your changes, "
            "or pass --allow-dirty to record code.dirty = true in the artifact."
            .format(rev=(rev or "unknown")[:7])
        )


def _symbol_coverage(
    data: dict[str, pd.DataFrame],
    requested_end: str,
    tolerance_days: int = SPAN_TOLERANCE_DAYS,
) -> list[dict]:
    """Per-symbol first/last bar, flagging symbols that end well before the request."""
    end_ts = pd.Timestamp(requested_end)
    rows = []
    for symbol in sorted(data):
        if symbol in NON_TRADABLE:
            continue
        df = data[symbol]
        if not len(df):
            continue
        last = df.index[-1]
        rows.append({
            "symbol": symbol,
            "first": df.index[0].strftime("%Y-%m-%d"),
            "last": last.strftime("%Y-%m-%d"),
            "bars": int(len(df)),
            "ends_early": bool(last < end_ts - pd.Timedelta(days=tolerance_days)),
        })
    return rows


def _validate_panel(
    requested_start: str,
    requested_end: str,
    actual_start: pd.Timestamp | None,
    actual_end: pd.Timestamp | None,
    allow_partial: bool,
) -> list[str]:
    """Refuse to write an artifact whose panel does not cover the requested span."""
    problems = []
    if actual_start is None or actual_end is None:
        problems.append("no price data loaded")
    else:
        if actual_start > pd.Timestamp(requested_start) + pd.Timedelta(days=SPAN_TOLERANCE_DAYS):
            problems.append(
                f"panel starts {actual_start.date()} but {requested_start} was requested"
            )
        if actual_end < pd.Timestamp(requested_end) - pd.Timedelta(days=SPAN_TOLERANCE_DAYS):
            problems.append(
                f"panel ends {actual_end.date()} but {requested_end} was requested"
            )
    if problems:
        message = "; ".join(problems)
        if allow_partial:
            print(f"WARNING: partial panel accepted: {message}")
        else:
            raise RuntimeError(
                f"Panel span check failed: {message}. "
                "Use --allow-partial-panel to override (the artifact will be marked partial)."
            )
    return problems


def strategy_seed_summary(seeds, r_net_means) -> dict:
    """The ``run_info.strategy_seeds`` payload: per-seed values and their stats.

    ``std`` is the population standard deviation (``ddof=0``), matching
    ``scripts/research_diagnostics.py``; ``se`` is ``std / sqrt(N)``.
    """
    values = np.asarray(r_net_means, dtype=float)
    n = int(values.size)
    mean = float(np.mean(values)) if n else 0.0
    std = float(np.std(values)) if n else 0.0
    se = float(std / math.sqrt(n)) if n else 0.0
    return {
        "seeds": [int(seed) for seed in seeds],
        "r_net_mean": [float(value) for value in values],
        "mean": mean,
        "std": std,
        "se": se,
    }


def strategy_seed_r_net_mean(trades, eval_start: str = EVAL_START) -> float:
    """Mean ``r_net`` over the evaluation window (uncensored trades only)."""
    windowed = trades_in_window(trades, eval_start)
    return float(np.mean([t.r_net for t in windowed])) if windowed else 0.0


def run_strategy_seeds(
    data: dict[str, pd.DataFrame],
    signals: dict[str, pd.Series],
    exit_rules: ExitRules,
    portfolio_rules: PortfolioRules,
    seeds,
    eval_start: str = EVAL_START,
) -> tuple[list[dict], dict]:
    """Run the identical signals under each engine seed.

    The engine seed only shuffles same-date candidates, so every seed trades
    the same signals and differs only in which candidate fills a scarce slot.
    Returns one row per seed (``seed``, ``r_net_mean``, ``trades``, ``equity``)
    plus the summary written to ``run_info.strategy_seeds``. The first seed
    (42) remains the primary artifact run.
    """
    rows = []
    for seed in seeds:
        trades, equity = run_portfolio(
            data, signals, exit_rules, portfolio_rules, seed=seed
        )
        rows.append({
            "seed": int(seed),
            "r_net_mean": strategy_seed_r_net_mean(trades, eval_start),
            "trades": trades,
            "equity": equity,
        })
    summary = strategy_seed_summary(
        [row["seed"] for row in rows], [row["r_net_mean"] for row in rows]
    )
    return rows, summary


def run_backtest(
    setup_name: str,
    universe_path: str,
    start_date: str,
    end_date: str,
    exit_rules: ExitRules,
    portfolio_rules: PortfolioRules,
    cache_dir: str = ".cache/research",
    output_dir: str = "docs/backtests/research",
    max_cache_age_hours: float = 20.0,
    force_download: bool = False,
    max_universe_symbols: int | None = None,
    n_strategy_seeds: int = 20,
) -> dict:
    """Run a full backtest for a setup and return everything needed to document it."""

    print(f"\n{'='*60}")
    print(f"Running {setup_name} backtest")
    print(f"Universe: {universe_path}")
    print(f"Period: {start_date} to {end_date}")
    print(f"Cache: {cache_dir}")
    print(f"{'='*60}")

    # Load universe
    symbols = load_universe(universe_path)
    if max_universe_symbols is not None:
        symbols = symbols[:max_universe_symbols]
    print(f"Loaded {len(symbols)} symbols from universe")

    # Add SPY for benchmark
    if "SPY" not in symbols:
        symbols.append("SPY")

    # Download data
    print("Downloading data...")
    data, dropped, cache_stats = download_daily(
        symbols, start_date, end_date, cache_dir,
        max_age_hours=max_cache_age_hours,
        force_download=force_download,
    )
    actual_start, actual_end = panel_span(data)
    coverage = coverage_report(data, start_date, end_date)
    print(
        f"Loaded {len(data)} symbols "
        f"(cache hits={cache_stats['hits']}, downloads={cache_stats['downloaded']}, "
        f"failed={cache_stats['failed']})"
    )
    print(
        f"Coverage: n_symbols={coverage['n_symbols']}, "
        f"early_end={len(coverage['early_end'])}, "
        f"late_start={len(coverage['late_start'])}"
    )
    if len(coverage["early_end"]) > 0.05 * max(1, coverage["n_symbols"]):
        raise RuntimeError(
            "Data coverage check failed: too many symbols end early: "
            f"{coverage['early_end'][:10]}"
        )
    if dropped:
        print(f"Dropped {len(dropped)} symbols: {[d[0] for d in dropped]}")
    if actual_start is not None:
        print(f"Actual panel span: {actual_start.date()} -> {actual_end.date()}")

    # Add indicators
    print("Adding indicators...")
    for symbol, df in data.items():
        data[symbol] = add_indicators(df)
    print("Indicators added")

    # Get setup function
    setup_fn = get_setup_function(setup_name)
    if setup_fn is None:
        raise ValueError(f"Unknown setup: {setup_name}")

    # Load config for eligibility
    config = load_setup_config(setup_name)

    # Generate signals
    print("Generating signals...")
    signals = {}
    for symbol, df in data.items():
        if symbol in NON_TRADABLE:
            signals[symbol] = pd.Series(False, index=df.index)
            continue

        # Check eligibility
        if not eligible(df).any():
            signals[symbol] = pd.Series(False, index=df.index)
            continue

        # Generate setup signals
        sig = setup_fn(df)
        signals[symbol] = sig

        n_signals = sig.sum()
        if n_signals > 0:
            print(f"  {symbol}: {n_signals} signals")

    total_signals = sum(s.sum() for s in signals.values())
    print(f"Total signals: {total_signals}")

    # Run portfolio backtest. The headline uses a seed sweep: the engine seed
    # only shuffles same-date candidates, so every seed trades the same
    # signals. Seed 42 stays the primary artifact (trades, equity, metrics).
    seeds = list(range(42, 42 + n_strategy_seeds))
    print(
        f"Running portfolio backtest "
        f"(strategy seeds {seeds[0]}..{seeds[-1]}, n={len(seeds)})..."
    )
    seed_runs, strategy_seeds = run_strategy_seeds(
        data, signals, exit_rules, portfolio_rules, seeds, eval_start=EVAL_START
    )
    primary = seed_runs[0]
    trades, equity = primary["trades"], primary["equity"]
    print(f"Completed {len(trades)} trades")
    print(
        f"Strategy seed sweep: mean={strategy_seeds['mean']:+.4f} "
        f"std={strategy_seeds['std']:.4f} se={strategy_seeds['se']:.4f}"
    )

    # Every position is closed, so equity must reconcile with realized P&L.
    expected = portfolio_rules.start_equity + sum(t.pnl_usd for t in trades)
    if abs(float(equity.iloc[-1]) - expected) > 0.5:
        raise RuntimeError(
            f"Equity reconciliation failed: final_equity={float(equity.iloc[-1]):.2f} "
            f"expected={expected:.2f}"
        )
    print("Reconciliation: OK")

    # Compute metrics
    spy_returns = None
    if "SPY" in data:
        spy_returns = data["SPY"]["close"].pct_change()

    metrics = compute_metrics(
        trades_in_window(trades, EVAL_START), equity,
        benchmark_returns=spy_returns,
        start_equity=portfolio_rules.start_equity,
    )
    print_metrics(metrics, f"{setup_name} Backtest Results")
    print(f"Evaluation window: closed trades with exit_date >= {EVAL_START}")

    return {
        "trades": trades,
        "equity": equity,
        "data": data,
        "signals": signals,
        "metrics": metrics,
        "dropped": dropped,
        "cache_stats": cache_stats,
        "actual_start": actual_start,
        "actual_end": actual_end,
        "requested_start": start_date,
        "requested_end": end_date,
        "n_universe_symbols": len(symbols),
        "strategy_seeds": strategy_seeds,
    }


def run_controls(
    data: dict[str, pd.DataFrame],
    signals: dict[str, pd.Series],
    exit_rules: ExitRules,
    portfolio_rules: PortfolioRules,
    n_matched: int = 30,
    n_random: int = 100,
    n_permuted: int = 50,
    n_shifted: int = 5,
    eval_start: str | None = EVAL_START,
) -> dict[str, list]:
    """Run control suite."""
    print(f"\n{'='*60}")
    print(f"Running Control Suite")
    print(
        f"Matched: {n_matched}, Random: {n_random}, "
        f"Permuted: {n_permuted}, Shifted: {n_shifted}"
    )
    print(f"Evaluation window: closed trades with exit_date >= {eval_start}")
    print(f"{'='*60}")

    control_results = run_control_suite(
        data, signals, exit_rules, portfolio_rules,
        n_matched=n_matched,
        n_random=n_random,
        n_permuted=n_permuted,
        n_shifted=n_shifted,
        base_seed=42,
        eval_start=eval_start,
    )

    # Summarize
    for ctype, results in control_results.items():
        if results:
            r_net_sums = [r.metrics.r_net_sum for r in results]
            sharpes = [r.metrics.sharpe for r in results]
            returns = [r.metrics.total_return_pct for r in results]
            print(f"\n{ctype.upper()} ({len(results)} runs):")
            print(f"  R-net Sum:  mean={np.mean(r_net_sums):.3f}, std={np.std(r_net_sums):.3f}, "
                  f"min={np.min(r_net_sums):.3f}, max={np.max(r_net_sums):.3f}")
            print(f"  Sharpe:     mean={np.mean(sharpes):.3f}, std={np.std(sharpes):.3f}")
            print(f"  Return %:   mean={np.mean(returns):.1f}%, std={np.std(returns):.1f}%")

    return control_results


def summarize_controls(control_results: dict[str, list]) -> dict:
    """Compact control distribution summary for the artifact."""
    summary = {}
    for ctype, results in control_results.items():
        if results:
            summary[ctype] = {
                "n_runs": len(results),
                "n_trades_mean": float(np.mean([r.metrics.n_trades for r in results])),
                "r_net_sum_mean": float(np.mean([r.metrics.r_net_sum for r in results])),
                "r_net_sum_std": float(np.std([r.metrics.r_net_sum for r in results])),
                "r_net_mean_mean": float(np.mean([r.metrics.r_net_mean for r in results])),
                "r_net_mean_std": float(np.std([r.metrics.r_net_mean for r in results])),
                "sharpe_mean": float(np.mean([r.metrics.sharpe for r in results])),
                "sharpe_std": float(np.std([r.metrics.sharpe for r in results])),
                "return_mean": float(np.mean([r.metrics.total_return_pct for r in results])),
                "return_std": float(np.std([r.metrics.total_return_pct for r in results])),
            }
    return summary


def save_results(
    setup_name: str,
    result: dict,
    control_summary: dict,
    pvalues_r_net_mean: dict,
    pvalues_sharpe: dict,
    pvalues_seed_avg: dict,
    metadata: dict,
    run_info: dict,
    output_dir: str = "docs/backtests/research",
    tag: str = "",
) -> str:
    """Save a self-describing results artifact to JSON."""
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = f"_{tag}" if tag else ""
    filename = f"{setup_name}_{timestamp}{suffix}.json"
    filepath = os.path.join(output_dir, filename)

    trades_data = []
    for t in result["trades"]:
        trades_data.append({
            "symbol": t.symbol,
            "signal_date": t.signal_date.isoformat() if isinstance(t.signal_date, pd.Timestamp) else str(t.signal_date),
            "entry_date": t.entry_date.isoformat() if isinstance(t.entry_date, pd.Timestamp) else str(t.entry_date),
            "entry_price": float(t.entry_price),
            "stop": float(t.stop),
            "target": float(t.target),
            "shares": int(t.shares),
            "exit_date": t.exit_date.isoformat() if isinstance(t.exit_date, pd.Timestamp) else str(t.exit_date),
            "exit_price": float(t.exit_price),
            "exit_reason": t.exit_reason,
            "bars_held": int(t.bars_held),
            "r_gross": float(t.r_gross),
            "r_net": float(t.r_net),
            "pnl_usd": float(t.pnl_usd),
            "censored": bool(t.censored)
        })

    equity_data = [
        {"date": d.isoformat(), "equity": float(e)}
        for d, e in result["equity"].items()
    ]

    payload = {
        "setup": setup_name,
        "timestamp": timestamp,
        "metrics": metrics_to_dict(result["metrics"]),
        "trades": trades_data,
        "equity_curve": equity_data,
        "control_summary": control_summary,
        "p_values": pvalues_r_net_mean,
        "p_value_metric": "r_net_mean",
        "p_values_seed_avg": pvalues_seed_avg,
        "p_values_sharpe": pvalues_sharpe,
        "run": metadata,
        "run_info": run_info,
    }

    with open(filepath, 'w', encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(f"\nResults saved to: {filepath}")
    return filepath


def _build_metadata(args, result: dict, exit_rules, portfolio_rules) -> dict:
    """Everything a reader needs to judge the artifact without the source."""
    rev, dirty = _git_state(args.output_dir)
    coverage = _symbol_coverage(result["data"], args.end)
    start_equity = portfolio_rules.start_equity
    # Reconciliation covers every trade; trade-level metrics may be windowed.
    pnl_all = float(sum(t.pnl_usd for t in result["trades"]))
    final_equity = float(result["equity"].iloc[-1]) if len(result["equity"]) else 0.0
    holds = bool(abs(final_equity - (start_equity + pnl_all)) <= 1e-6 * max(1.0, abs(start_equity)))

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "script": "scripts/run_research_baseline.py",
        "requested_span": {"start": result["requested_start"], "end": result["requested_end"]},
        "actual_span": {
            "start": result["actual_start"].strftime("%Y-%m-%d") if result["actual_start"] is not None else None,
            "end": result["actual_end"].strftime("%Y-%m-%d") if result["actual_end"] is not None else None,
        },
        "universe": {
            "path": args.universe,
            "sha256": _sha256_file(args.universe),
            "n_symbols_requested": result["n_universe_symbols"],
            "n_symbols_loaded": len(result["data"]),
            "symbols_dropped": [{"symbol": s, "reason": r} for s, r in result["dropped"]],
        },
        "cache": result["cache_stats"],
        "rules": {
            "start_equity": portfolio_rules.start_equity,
            "risk_pct": portfolio_rules.risk_pct,
            "max_positions": portfolio_rules.max_positions,
            "max_position_pct": portfolio_rules.max_position_pct,
            "cost_bps_per_side": portfolio_rules.cost_bps_per_side,
            "allow_same_day_recycling": portfolio_rules.allow_same_day_recycling,
            "stop_atr": exit_rules.stop_atr,
            "target_atr": exit_rules.target_atr,
            "max_hold_bars": exit_rules.max_hold_bars,
            "candidate_seed": 42,
        },
        "controls": {
            "matched_random": args.n_matched,
            "random": args.n_random,
            "permuted": args.n_permuted,
            "shifted": args.n_shifted,
        },
        "invariant": {
            "start_equity": start_equity,
            "pnl_usd_all": pnl_all,
            "final_equity": final_equity,
            "holds": holds,
            "expression": "final_equity == start_equity + sum(pnl_usd over all trades)",
        },
        "panel": {
            "n_symbols": len(coverage),
            "n_symbols_ending_early": sum(1 for row in coverage if row["ends_early"]),
            "symbol_coverage": coverage,
        },
        "code": {"revision": rev, "dirty": dirty},
        "environment": {
            "python": platform.python_version(),
            "pandas": pd.__version__,
            "numpy": np.__version__,
            "yfinance": _package_version("yfinance"),
        },
        "limitations": [
            "Universe is the current S&P 500 snapshot: survivorship bias remains.",
            "Sharpe/Sortino are computed from daily equity returns and annualised by sqrt(252); they are not per-trade ratios.",
            "CAGR is computed over elapsed calendar years from the equity curve, not bar count.",
            f"Trade statistics use one evaluation window: closed trades with exit_date >= {EVAL_START} (2015 is warm-up). Controls use the same window.",
            "Censored trades (exit_reason data_end / eod_censored) are excluded from trade-level R statistics but included in equity and pnl_usd_all.",
        ],
    }


def _package_version(name: str) -> str | None:
    try:
        from importlib.metadata import version
        return version(name)
    except Exception:
        return None


def _git_commit_short() -> str:
    """Short HEAD revision, or ``"unknown"`` when git is unavailable."""
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).parent.parent,
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def main():
    parser = argparse.ArgumentParser(description="Run research baseline backtest")
    parser.add_argument("--setup", default="statistical_mean_reversion",
                        choices=list(SETUPS.keys()),
                        help="Setup name to test")
    parser.add_argument("--universe", default="config/replay_universe_sp500.txt",
                        help="Path to universe file")
    parser.add_argument("--start", default="2015-01-01",
                        help="Start date (inclusive, YYYY-MM-DD)")
    parser.add_argument("--end", default=datetime.now().strftime("%Y-%m-%d"),
                        help="End date (inclusive, YYYY-MM-DD)")
    parser.add_argument("--stop-atr", type=float, default=2.0,
                        help="Stop loss ATR multiplier")
    parser.add_argument("--target-atr", type=float, default=3.0,
                        help="Target ATR multiplier")
    parser.add_argument("--max-hold", type=int, default=15,
                        help="Max hold bars")
    parser.add_argument("--risk-pct", type=float, default=0.5,
                        help="Risk percent per trade")
    parser.add_argument("--max-positions", type=int, default=8,
                        help="Max concurrent positions")
    parser.add_argument("--cost-bps", type=float, default=15.0,
                        help="Cost basis points per side")
    parser.add_argument("--allow-same-day-recycling", action="store_true",
                        help="Let an exit on date D free a slot/cash for entries on D (pre-D-82 behaviour)")
    parser.add_argument("--n-matched", type=int, default=30,
                        help="Number of matched-random control runs")
    parser.add_argument("--n-random", type=int, default=0,
                        help="Number of random control runs")
    parser.add_argument("--n-permuted", type=int, default=10,
                        help="Number of permuted control runs")
    parser.add_argument("--n-shifted", type=int, default=2,
                        help="Number of time-shifted control runs")
    parser.add_argument("--n-strategy-seeds", type=int, default=20,
                        help="Number of engine seeds (42..42+N-1) for the strategy headline")
    parser.add_argument("--cache-dir", default=".cache/research",
                        help="Cache directory")
    parser.add_argument("--cache-max-age-hours", type=float, default=20.0,
                        help="Reuse a span-matched cache entry younger than this")
    parser.add_argument("--force-download", action="store_true",
                        help="Ignore the cache and re-download every symbol")
    parser.add_argument("--output-dir", default="docs/backtests/research",
                        help="Output directory")
    parser.add_argument("--tag", default="",
                        help="Suffix for the artifact filename (e.g. clean)")
    parser.add_argument("--allow-partial-panel", action="store_true",
                        help="Write the artifact even if the panel misses the requested span")
    parser.add_argument("--no-controls", action="store_true",
                        help="Skip control suite")
    parser.add_argument("--allow-dirty", action="store_true",
                        help="Run even when the git working tree is dirty (artifact records dirty=true)")
    parser.add_argument("--quick", action="store_true",
                        help="Fast smoke run: 40 symbols, 2019-2020, separate cache")
    parser.add_argument("--quick-setup", metavar="SETUP", default=None,
                        help="Alias for --quick with a setup name")

    args = parser.parse_args()

    if args.n_strategy_seeds < 1:
        parser.error("--n-strategy-seeds must be >= 1")

    # An artifact is only reproducible from a clean tree; refuse by default.
    # The run's own output directory is exempt (its untracked artifacts are not
    # an input to this run).
    _require_clean_tree(args.allow_dirty, output_dir=args.output_dir)

    if args.quick_setup is not None:
        if args.quick_setup not in SETUPS:
            parser.error(f"unknown setup: {args.quick_setup}")
        args.quick = True
        args.setup = args.quick_setup

    if args.quick:
        args.start = "2019-01-01"
        args.end = "2020-12-31"
        args.n_matched = 3
        args.n_random = 0
        args.n_permuted = 2
        args.n_shifted = 1
        args.cache_dir = ".cache/research_quick"
        args.output_dir = ".cache/research_quick/out"

    exit_rules = ExitRules(
        stop_atr=args.stop_atr,
        target_atr=args.target_atr,
        max_hold_bars=args.max_hold
    )

    portfolio_rules = PortfolioRules(
        start_equity=100_000.0,
        risk_pct=args.risk_pct,
        max_positions=args.max_positions,
        max_position_pct=20.0,
        cost_bps_per_side=args.cost_bps,
        allow_same_day_recycling=args.allow_same_day_recycling,
    )

    print(f"\n{'='*60}")
    print(f"RESEARCH BASELINE BACKTEST")
    print(f"{'='*60}")
    print(f"Setup:         {args.setup}")
    print(f"Universe:      {args.universe}")
    print(f"Date Range:    {args.start} to {args.end} (inclusive)")
    print(f"Stop ATR:      {args.stop_atr}")
    print(f"Target ATR:    {args.target_atr}")
    print(f"Max Hold:      {args.max_hold}")
    print(f"Risk %:        {args.risk_pct}%")
    print(f"Max Positions: {args.max_positions}")
    print(f"Cost BPS:      {args.cost_bps}")
    print(f"Strategy seeds:{args.n_strategy_seeds} (42..{41 + args.n_strategy_seeds})")
    print(f"{'='*60}")

    # Run backtest
    result = run_backtest(
        args.setup,
        args.universe,
        args.start,
        args.end,
        exit_rules,
        portfolio_rules,
        args.cache_dir,
        args.output_dir,
        max_cache_age_hours=args.cache_max_age_hours,
        force_download=args.force_download,
        max_universe_symbols=40 if args.quick else None,
        n_strategy_seeds=args.n_strategy_seeds,
    )

    metrics = result["metrics"]

    # Refuse to write an artifact that does not describe the requested panel.
    span_problems = _validate_panel(
        args.start, args.end, result["actual_start"], result["actual_end"],
        allow_partial=args.allow_partial_panel,
    )
    if span_problems:
        result["cache_stats"]["panel_warnings"] = span_problems

    # Invariant: every position is closed, so equity must reconcile with realized P&L.
    metadata = _build_metadata(args, result, exit_rules, portfolio_rules)
    if not metadata["invariant"]["holds"]:
        raise RuntimeError(
            "Equity invariant failed: final_equity != start_equity + sum(pnl_usd). "
            f"{metadata['invariant']}"
        )

    run_info = {
        "start": args.start,
        "end": args.end,
        "universe_path": args.universe,
        "n_symbols_used": len(
            [s for s in result["data"] if s not in NON_TRADABLE]
        ),
        "dropped": [[s, r] for s, r in result["dropped"]],
        "exit_rules": asdict(exit_rules),
        "portfolio_rules": asdict(portfolio_rules),
        "controls": {
            "n_matched": args.n_matched,
            "n_random": args.n_random,
            "n_permuted": args.n_permuted,
            "n_shifted": args.n_shifted,
        },
        "git_commit": _git_commit_short(),
        "quick": bool(args.quick),
        "eval_start": EVAL_START,
        "strategy_seeds": result["strategy_seeds"],
    }

    # Run controls
    pvalues_r = {}
    pvalues_seed_avg = {}
    pvalues_sharpe = {}
    control_results = {}
    control_summary = {}

    if not args.no_controls:
        control_results = run_controls(
            result["data"], result["signals"], exit_rules, portfolio_rules,
            n_matched=args.n_matched,
            n_random=args.n_random,
            n_permuted=args.n_permuted,
            n_shifted=args.n_shifted,
            eval_start=EVAL_START,
        )
        control_summary = summarize_controls(control_results)

        pvalues_r = compute_control_pvalues(metrics, control_results, "r_net_mean")
        pvalues_seed_avg = compute_control_pvalues(
            replace(metrics, r_net_mean=result["strategy_seeds"]["mean"]),
            control_results,
            "r_net_mean",
        )
        pvalues_sharpe = compute_control_pvalues(metrics, control_results, "sharpe")

        print(f"\n{'='*60}")
        print(f"P-VALUES (vs R-net Mean, seed 42)")
        print(f"{'='*60}")
        for ctype, p in pvalues_r.items():
            sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else ""
            print(f"  {ctype:14s}: p = {p:.4f} {sig}")

        print(f"\nP-VALUES (vs R-net Mean, strategy seed mean)")
        print(f"{'='*60}")
        for ctype, p in pvalues_seed_avg.items():
            sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else ""
            print(f"  {ctype:14s}: p = {p:.4f} {sig}")

        print(f"\nP-VALUES (vs Sharpe, informational)")
        print(f"{'='*60}")
        for ctype, p in pvalues_sharpe.items():
            sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else ""
            print(f"  {ctype:14s}: p = {p:.4f} {sig}")

    save_results(
        args.setup,
        result,
        control_summary,
        pvalues_r,
        pvalues_sharpe,
        pvalues_seed_avg,
        metadata,
        run_info,
        args.output_dir,
        tag=args.tag,
    )

    print(f"\n{'='*60}")
    print(f"BACKTEST COMPLETE")
    print(f"{'='*60}")

    # INFO only: a completed run is a successful run. Significance never
    # changes the exit code. The headline test is the strategy seed mean.
    if pvalues_seed_avg:
        strategy_mean = result["strategy_seeds"]["mean"]
        best_control = min(pvalues_seed_avg, key=pvalues_seed_avg.get)
        best_p = pvalues_seed_avg[best_control]
        control_mean = control_summary[best_control]["r_net_mean_mean"]
        favorable = strategy_mean > control_mean

        if best_p < 0.05 and favorable:
            print(
                f"INFO: significantly BETTER than {best_control} "
                f"(p={best_p:.4f}, strategy seed mean={strategy_mean:.3f} "
                f"vs control mean {control_mean:.3f})"
            )
        elif best_p < 0.05:
            print(
                f"INFO: significantly WORSE than {best_control} "
                f"(p={best_p:.4f}, strategy seed mean={strategy_mean:.3f} "
                f"vs control mean {control_mean:.3f})"
            )
        else:
            print(
                f"INFO: NOT statistically significant vs controls "
                f"(seed-averaged best p={best_p:.4f} on {best_control})"
            )
    else:
        print("INFO: No controls run")

    return 0


if __name__ == "__main__":
    sys.exit(main())
