# Research Backtest Artifacts

**Status: the JSON files in this directory are a harness smoke test, not valid
evidence.** See [D-79](../../DECISIONS/D-79-research-baseline-harness.md) and
[H-10](../HYPOTHESIS_LOG.md).

## Why the committed results are invalid

Two defects were found during documentation on 2026-11-11:

1. **Mixed data panel.** `download_daily()` reused cache files without checking
   that they covered the requested dates. 440 of 498 cached symbols covered only
   2020, while 40 covered 2014-2024. The artifact equity calendar is
   2014-01-02 to 2024-12-30, not the "2020-2023" in the commit message.
   `low_vol_setup` and `volume_trend_accumulation` have no entries after 2020.
2. **Stranded positions.** A position whose symbol's data ends is never exited;
   its cash is not returned, so the equity curve records an artificial loss.
   Example: `statistical_mean_reversion` has +$10,977 realized trade P&L but a
   final equity of $52,552 (-47.4%). For `low_vol_setup` and
   `volume_trend_accumulation` the stranded positions consumed the cash: the
   cache contains 395 and 859 post-2020 signals respectively, but the artifacts
   record zero post-2020 trades because no position could be sized.

Do **not** cite the return, drawdown, CAGR, volatility or alpha/beta fields.
Trade-level R, win rate, profit factor and exit reasons are internally
consistent but were computed on the mixed panel.

## What the files are

`{setup}_{YYYYmmdd_HHMMSS}.json` produced by
`scripts/run_research_baseline.py`:

| Field | Meaning |
|---|---|
| `setup` | Setup name |
| `timestamp` | Run timestamp |
| `metrics` | Trade-level and equity-curve metrics |
| `trades` | Every trade with entry/exit, R, P&L and exit reason |
| `equity_curve` | Daily marked equity |
| `control_summary` | Random / permuted / shifted control distributions |
| `p_values` | One-sided p-values on `r_net_sum` per control |

The quick-run files (`statistical_mean_reversion_20261110_12*`,
`*_1627*`, `*_1628*`) are 10-symbol, 2020-only runs from the harness bring-up.

## How to re-run (after the fixes in D-79)

```bash
python scripts/run_research_baseline.py \
  --setup statistical_mean_reversion \
  --universe config/replay_universe_sp500.txt \
  --start 2020-01-03 --end 2023-12-29 \
  --cache-dir .cache/research_clean \
  --output-dir docs/backtests/research
```

Use a **fresh cache directory** until the cache-range fix lands. Check the
artifact's actual span before interpreting anything.

## Baseline summary (as recorded; do not cite the return figures)

| Setup | Trades | Win rate | Mean net R | Profit factor | random p | permuted p | shifted p |
|---|---|---|---|---|---|---|---|
| statistical_mean_reversion | 700 | 49.0% | +0.038 | 1.076 | 0.524 | 0.286 | 0.476 |
| breakout_52week | 583 | 43.9% | -0.047 | 0.915 | 0.143 | 0.048 | 0.048 |
| low_vol_setup | 589 | 46.3% | -0.034 | 0.937 | 0.048 | 0.190 | 0.095 |
| volume_trend_accumulation | 748 | 48.3% | +0.012 | 1.024 | 0.762 | 0.905 | 0.667 |

The two significant p-values are **unfavorable** (controls were better). No
setup beat its controls at p < 0.05 in the favorable direction on the recorded
panel.
