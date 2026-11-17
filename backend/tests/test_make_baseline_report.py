"""Tests for scripts/make_baseline_report.py (D-82).

The report is a pure function of the artifact JSON, so these tests build a
tiny synthetic artifact (N trades per year over 3 years) and check the table,
the block bootstrap CI and the verdict labels.
"""

import math
import statistics

import pytest

from scripts.make_baseline_report import (
    block_bootstrap_ci,
    build_report,
    trade_stats,
    verdict,
)


PATTERN = [0.5, -0.3, 0.2, -0.1, 0.4, -0.2]
SEED_VALUES = [0.06, 0.08, 0.11]


def _artifact(n_per_year=5):
    trades = []
    for year in (2016, 2017, 2018):
        for i in range(n_per_year):
            r_net = PATTERN[i % len(PATTERN)]
            month = (i % 12) + 1
            exit_date = f"{year}-{month:02d}-15"
            trades.append(
                {
                    "symbol": f"STK{i}",
                    "signal_date": f"{year}-{month:02d}-05",
                    "entry_date": f"{year}-{month:02d}-06",
                    "entry_price": 100.0,
                    "stop": 95.0,
                    "target": 105.0,
                    "shares": 10,
                    "exit_date": exit_date,
                    "exit_price": 100.0,
                    "exit_reason": "target" if r_net > 0 else "stop",
                    "bars_held": 5,
                    "r_gross": r_net,
                    "r_net": r_net,
                    "pnl_usd": r_net * 1000.0,
                    "censored": False,
                }
            )

    start = 100_000.0
    final = start + sum(t["pnl_usd"] for t in trades)
    return {
        "setup": "demo",
        "run_info": {
            "start": "2016-01-01",
            "end": "2019-01-01",
            "n_symbols_used": 40,
            "dropped": [],
            "git_commit": "abc1234",
            "exit_rules": {"stop_atr": 2.0, "target_atr": 3.0, "max_hold_bars": 15},
            "portfolio_rules": {
                "start_equity": start,
                "risk_pct": 0.5,
                "max_positions": 8,
                "max_position_pct": 20.0,
                "cost_bps_per_side": 15.0,
            },
            "strategy_seeds": {
                "seeds": [42, 43, 44],
                "r_net_mean": list(SEED_VALUES),
                "mean": statistics.mean(SEED_VALUES),
                "std": statistics.pstdev(SEED_VALUES),
                "se": statistics.pstdev(SEED_VALUES) / math.sqrt(len(SEED_VALUES)),
            },
        },
        "trades": trades,
        "equity_curve": [
            {"date": "2016-01-01", "equity": start},
            {"date": "2017-01-01", "equity": start},
            {"date": "2018-01-01", "equity": start},
            {"date": "2019-01-01", "equity": final},
        ],
        "control_summary": {
            "matched_random": {
                "n_runs": 30,
                "n_trades_mean": 60.0,
                "r_net_mean_mean": 0.01,
                "r_net_mean_std": 0.02,
            }
        },
        "p_values": {"matched_random": 0.01},
        "p_values_seed_avg": {"matched_random": 0.02},
    }


def _row(**overrides):
    row = {
        "account": {"reconciles": True, "max_dd": -0.10},
        "p_matched": 0.01,
    }
    row.update(overrides)
    return row


def _stats(**overrides):
    stats = {
        "n": 200,
        "profit_factor": 1.2,
        "win_rate": 0.45,
        "ci95": (0.001, 0.3),
        "ci95_block": (0.01, 0.3),
    }
    stats.update(overrides)
    return stats


PER_YEAR = [
    {"year": 2016, "n": 40, "expectancy_net": 0.1, "profit_factor": 1.2},
    {"year": 2017, "n": 40, "expectancy_net": 0.1, "profit_factor": 1.2},
    {"year": 2018, "n": 40, "expectancy_net": 0.1, "profit_factor": 1.2},
]


def test_table_renders_with_both_cis():
    report = build_report({"demo": ("demo_20190101.json", _artifact(n_per_year=40))})

    assert "| demo | 120 |" in report
    assert "95% CI (iid)" in report
    assert "95% CI (block)" in report
    assert "Reconciliation" in report
    assert "random-path drawdown scale:" in report
    assert "| PASS |" in report


def test_block_ci_is_finite_and_not_wider_than_degenerate():
    stats = trade_stats(_artifact())

    low, high = stats["ci95_block"]
    assert math.isfinite(low) and math.isfinite(high)
    assert low <= high
    # The pooled bootstrap mean cannot escape the range of the trade R values.
    assert min(PATTERN) <= low <= high <= max(PATTERN)


def test_block_bootstrap_ci_handles_single_trade():
    low, high = block_bootstrap_ci([{"exit_date": "2016-01-15", "r_net": 0.5}])
    assert math.isnan(low) and math.isnan(high)


def test_verdict_candidate_needs_block_ci_and_pvalue():
    assert verdict(_row(), _stats(), PER_YEAR) == "CANDIDATE needs out-of-sample test"


def test_verdict_insufficient_sample():
    assert verdict(_row(), _stats(n=99), PER_YEAR) == "INSUFFICIENT SAMPLE"


@pytest.mark.parametrize(
    "row,stats",
    [
        (_row(account={"reconciles": False, "max_dd": -0.1}), _stats()),
        (_row(), _stats(profit_factor=3.0)),
        (_row(), _stats(win_rate=0.70)),
    ],
)
def test_verdict_suspected_bug(row, stats):
    assert verdict(row, stats, PER_YEAR) == "SUSPECTED BUG investigate before trusting"


def test_verdict_drawdown_is_review_not_bug():
    assert (
        verdict(_row(account={"reconciles": True, "max_dd": -0.45}), _stats(), PER_YEAR)
        == "REVIEW drawdown guard breached (not necessarily a bug)"
    )


def test_verdict_uses_block_ci_not_iid():
    stats = _stats(ci95=(0.001, 0.3), ci95_block=(-0.01, 0.3))
    assert verdict(_row(), stats, PER_YEAR) == "NO EVIDENCE OF EDGE"


def test_verdict_requires_profitable_years():
    years = [
        {"year": 2016, "n": 40, "expectancy_net": 0.1, "profit_factor": 1.2},
        {"year": 2017, "n": 40, "expectancy_net": -0.1, "profit_factor": 0.9},
        {"year": 2018, "n": 40, "expectancy_net": -0.1, "profit_factor": 0.9},
    ]
    assert verdict(_row(), _stats(), years) == "NO EVIDENCE OF EDGE"


def test_main_table_renders_seed_mean_column():
    report = build_report({"demo": ("demo_20190101.json", _artifact(n_per_year=40))})

    assert "Expectancy (mean of 3 seeds)" in report
    assert f"| {statistics.mean(SEED_VALUES):.3f} |" in report


def test_control_table_renders_gap_se_and_seed_averaged_p():
    art = _artifact(n_per_year=40)
    report = build_report({"demo": ("demo_20190101.json", art)})

    seeds = art["run_info"]["strategy_seeds"]
    controls = art["control_summary"]["matched_random"]
    gap = seeds["mean"] - controls["r_net_mean_mean"]
    z = gap / controls["r_net_mean_std"]
    se = math.sqrt(
        seeds["se"] ** 2 + controls["r_net_mean_std"] ** 2 / controls["n_runs"]
    )
    assert "Gap vs control (strategy seed-mean - control mean)" in report
    assert "Gap / control std" in report
    assert "SE of means (shuffle + control mean only; not a test)" in report
    assert "p (seed-averaged)" in report
    assert f"| {gap:.3f} | {z:.2f} | {se:.3f} |" in report
    assert "| 0.0100 | 0.0200 |" in report


def test_underperformance_line_when_gap_below_two_control_std():
    art = _artifact(n_per_year=40)
    values = [-0.041, -0.040, -0.039]
    art["run_info"]["strategy_seeds"].update(
        {
            "r_net_mean": values,
            "mean": statistics.mean(values),
            "std": statistics.pstdev(values),
            "se": statistics.pstdev(values) / math.sqrt(len(values)),
        }
    )
    report = build_report({"demo": ("demo_20190101.json", art)})

    assert "**demo**: strategy underperforms matched control (informational)" in report


def test_no_underperformance_line_when_gap_is_inside_two_control_std():
    report = build_report({"demo": ("demo_20190101.json", _artifact(n_per_year=40))})

    assert "**demo**: strategy underperforms matched control" not in report


def test_old_se_rule_flags_but_control_std_rule_does_not():
    art = _artifact(n_per_year=40)
    values = [-0.021, -0.020, -0.019]
    art["run_info"]["strategy_seeds"].update(
        {
            "r_net_mean": values,
            "mean": statistics.mean(values),
            "std": statistics.pstdev(values),
            "se": statistics.pstdev(values) / math.sqrt(len(values)),
        }
    )
    seeds = art["run_info"]["strategy_seeds"]
    controls = art["control_summary"]["matched_random"]
    gap = seeds["mean"] - controls["r_net_mean_mean"]
    se_gap = math.sqrt(
        seeds["se"] ** 2 + controls["r_net_mean_std"] ** 2 / controls["n_runs"]
    )
    assert gap < -2 * se_gap

    report = build_report({"demo": ("demo_20190101.json", art)})

    assert gap / controls["r_net_mean_std"] >= -2.0
    assert "**demo**: strategy underperforms matched control" not in report


def test_verdict_uses_seed_averaged_p_value():
    row = _row(p_matched=0.20, p_matched_seed_avg=0.01)
    assert verdict(row, _stats(), PER_YEAR) == "CANDIDATE needs out-of-sample test"


def test_verdict_seed_average_can_remove_candidate():
    row = _row(p_matched=0.01, p_matched_seed_avg=0.20)
    assert verdict(row, _stats(), PER_YEAR) == "NO EVIDENCE OF EDGE"
