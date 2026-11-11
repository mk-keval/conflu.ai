# Research Backtest Artifacts

**Status: the `*_clean.json` files are valid for the panel and window described
below — one run of the current S&P 500 snapshot over 2020-01-03..2023-12-29.**
They are **exploratory**: no result here enters the D-75 pass bar, the kill rule,
the forward scorecard or any FWD-v0.2 verdict. See
[D-80](../../DECISIONS/D-80-research-baseline-remediation.md) and
[H-10](../HYPOTHESIS_LOG.md).

The `*_20261110_*.json` files are **superseded** and kept only as the audit trail
for the two defects fixed in D-80. Do not cite them.

## Provenance of the clean files

| Item | Value |
|---|---|
| Harness | `scripts/run_research_baseline.py` + `backend/app/research` |
| Code revision | `821454e` (`dirty=false` in every artifact) |
| Window | 2020-01-03 to 2023-12-29, inclusive |
| Universe | `config/replay_universe_sp500.txt` (current snapshot), SHA-256 `a53242f2...9a729080` |
| Symbols | 494 loaded (493 tradable + SPY); 11 dropped, each with a reason in the artifact |
| Cache | span-keyed `.cache/research_clean`; 494 symbols downloaded once, then 494 hits per setup (11 always fail) |
| Controls | random 2%/day (100 runs), permuted signal dates (50), time-shifted +20..+60 bars (5) |
| Determinism | repeated full runs on the same cache produced identical metrics, exits and p-values (alpha/beta only changed when that path was fixed) |

## What the files are

`{setup}_{YYYYmmdd_HHMMSS}_clean.json`:

| Field | Meaning |
|---|---|
| `setup`, `timestamp` | Setup name and run start |
| `run` | Requested vs actual span, panel coverage, universe path + SHA, cache counters, rules, control seeds, equity invariant, code revision, library versions, declared limitations |
| `metrics` | Trade-level and equity-curve metrics (**`win_rate` is a fraction**, e.g. `0.479`; `total_return_pct` and `max_drawdown_pct` are already percentages, e.g. `-22.0`) |
| `trades` | Every trade with entry/exit, R, P&L, bars held, exit reason and `censored` flag |
| `equity_curve` | Daily marked equity |
| `control_summary` | Random / permuted / shifted control distributions |
| `p_values`, `p_values_sharpe` | One-sided p-values per control on `r_net_sum` and on trade-R Sharpe |

`metrics.pnl_usd_sum` covers strategy exits only; `metrics.pnl_usd_all` includes
the forced `eod_censored` closes and reconciles with `final_equity`:
`final_equity == 100000 + pnl_usd_all`.

## Headline result (trade-level, strategy exits only)

| Setup | Trades | Win rate | Mean net R | R sum | PF | Return | Max DD |
|---|---|---|---|---|---|---|---|
| statistical_mean_reversion | 591 | 47.9% | +0.037 | **+21.93** | 1.08 | **+9.6%** | -22.0% |
| breakout_52week | 601 | 47.6% | +0.005 | +3.22 | 1.01 | -1.6% | -19.2% |
| low_vol_setup | 613 | 42.4% | -0.117 | **-71.62** | 0.80 | -27.2% | -37.3% |
| volume_trend_accumulation | 847 | 44.5% | -0.046 | -38.59 | 0.92 | -17.4% | -32.3% |

SPY buy-and-hold over the same window returned **+57.0%** (adjusted closes).
All four setups underperformed the benchmark.

Control p-values (`r_net_sum` / trade-R Sharpe). Small values mean the control
was more extreme than the real result:

| Setup | random | permuted | shifted |
|---|---|---|---|
| statistical_mean_reversion | 0.079 / **0.050** | **0.020** / **0.020** | 0.500 / 0.500 |
| breakout_52week | 0.228 / 0.228 | 0.745 / 0.745 | 0.833 / 0.833 |
| low_vol_setup | **0.050** / **0.020** | 0.059 / **0.020** | 0.167 / 0.167 |
| volume_trend_accumulation | 0.337 / 0.327 | 0.157 / 0.137 | 0.167 / 0.167 |

Read this as: `statistical_mean_reversion` is the only setup with a favorable
single-control signal; `low_vol_setup` is significantly *worse* than its controls;
nothing survives a Bonferroni correction across the 12 tests (smallest p = 0.0196,
threshold 0.0042), and the shifted control cannot reach p < 0.05 with 5 runs
(floor 1/6 = 0.167).

## How to re-run

```bash
python scripts/run_research_baseline.py \
  --setup statistical_mean_reversion \
  --universe config/replay_universe_sp500.txt \
  --start 2020-01-03 --end 2023-12-29 \
  --cache-dir .cache/research_clean \
  --output-dir .cache/artifacts_clean \
  --tag clean --n-random 100 --n-permuted 50 --n-shifted 5
```

The cache is keyed by `SYMBOL__{start}__{end}`, so re-requesting the same window
is fast and cannot mix spans. The runner refuses to write when the actual panel
is more than 10 days short of the request (unless `--allow-partial-panel`), and
exits `0` only when a control p-value is < 0.05 **and** the real metric is better
than that control's mean.

## Superseded files

`statistical_mean_reversion_20261110_*.json`, `breakout_52week_20261110_204613.json`,
`low_vol_setup_20261110_211920.json`, `volume_trend_accumulation_20261110_215337.json`.
They were produced with a cache that served mixed spans and an engine that never
closed positions stranded at a symbol's data end. Keep them as an audit trail;
do not cite their returns, drawdowns, CAGR, volatility or alpha/beta.

## Known limitations

- **Survivorship:** the universe is the *current* index membership. Companies
  removed from the index are absent, and recent listings that did not trade in
  2020 are dropped (FDXF, GEV, HONA, KVUE, Q, RDDT, SNDK, SOLV, VYLR; VLTO has
  61 bars; VIX is no longer served by Yahoo).
- **One window, no holdout.** 2020-2023 includes the crash and recovery; there is
  no walk-forward split or out-of-sample period.
- **Fixed research exits.** 2.0 ATR stop, 3.0 ATR target, 15-bar time stop — not
  the deployed template geometry (D-70/D-77). A weak result here does not retire
  a screen from the live mix.
- **Trade-R Sharpe.** `sharpe` annualizes per-trade R by `sqrt(252)`; it is not a
  daily equity Sharpe. Compare only at similar trade counts (591-847 here).
- **Alpha/beta** are annualized percentage alpha and beta regressed on SPY daily
  returns, informational only; they are not a buy-and-hold spread.
- **Shifted control** is capped at p = 0.167 with 5 runs and can never establish
  superiority; raise `--n-shifted` above 20 if that test matters.
