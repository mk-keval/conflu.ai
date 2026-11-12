# Research Backtest Artifacts

**Status: the `*_20261111_21*.json` files are valid for the panel and window described
below - one run of the current S&P 500 snapshot over 2015-01-01..2026-11-11.** They are
**exploratory**: no result here enters the D-75 pass bar, the kill rule, the forward
scorecard or any FWD-v0.2 verdict. The generated summary is
[`BASELINE_REPORT.md`](BASELINE_REPORT.md). See
[D-81](../../DECISIONS/D-81-research-baseline-v2-honesty-and-controls.md),
[D-80](../../DECISIONS/D-80-research-baseline-remediation.md) and
[H-10](../HYPOTHESIS_LOG.md).

The 13 older artifacts are **superseded** and moved to
[`invalid_20261110/`](invalid_20261110/), kept only as the audit trail for the defects
fixed in D-80 and D-81. Do not cite them.

## Provenance of the current files

| Item | Value |
|---|---|
| Harness | `scripts/run_research_baseline.py` + `backend/app/research` |
| Report generator | `scripts/make_baseline_report.py` (standard library only) |
| Code revision | HEAD `dcc9565`; the artifacts record `run.code.dirty = true` (work uncommitted) |
| Window | requested 2015-01-01..2026-11-11; actual 2015-01-02..2026-11-10 |
| Universe | `config/replay_universe_sp500.txt` (current snapshot), SHA-256 `a53242f2...9a729080` |
| Symbols | 501 tradable; 503 loaded with SPY + ^VIX; 2 dropped (KVUE: 1 row, VYLR: 29 rows) |
| Coverage | `panel.n_symbols_ending_early = 0`; 37 symbols start late (recent listings) |
| Cache | span-keyed `.cache/research`; 503 downloaded once (2 failures), then 503 hits per setup |
| Controls | matched-random 30, permuted dates 10, time-shifted +20..+60 bars 2, unmatched random 0 |
| Exits | 2.0 ATR stop, 3.0 ATR target, 15-bar time stop |
| Portfolio | $100,000 start, 0.5% risk, 8 positions, 20% notional cap, 15 bps/side |
| Evidence label | `exploratory_research` |

Files:

```
statistical_mean_reversion_20261111_210303.json
breakout_52week_20261111_210813.json
low_vol_setup_20261111_211337.json
volume_trend_accumulation_20261111_211931.json
```

## What the files are

Each artifact carries the D-80 `run` block and a D-81 `run_info` block:

| Field | Meaning |
|---|---|
| `setup`, `timestamp` | Setup name and run start |
| `run` | Requested vs actual span, panel coverage, universe path + SHA, cache counters, rules, control seeds, equity invariant, code revision, library versions, declared limitations |
| `run_info` | Requested `start`/`end`, `universe_path`, `n_symbols_used`, `dropped`, exit and portfolio rules, control budget, short `git_commit`, `quick` flag |
| `metrics` | Trade-level and equity-curve metrics (**`win_rate` is a fraction**, e.g. `0.472`; `total_return_pct`, `cagr` and `max_drawdown_pct` are percentages) |
| `trades` | Every trade with signal/entry/exit dates, R gross/net, P&L, bars held, exit reason and `censored` flag |
| `equity_curve` | Daily marked equity (forward-filled marks; final point is cash) |
| `control_summary` | Per-control `n_runs`, `n_trades_mean`, `r_net_mean_mean`, `r_net_mean_std`, R-sum and Sharpe distributions |
| `p_values` | One-sided p-values on `r_net_mean` (matched/permuted/shifted) |
| `p_values_sharpe` | One-sided p-values on trade-R Sharpe (informational) |

`metrics.pnl_usd_sum` covers strategy exits only; `metrics.pnl_usd_all` includes the
forced `data_end` / `eod_censored` closes and reconciles with `final_equity`:
`final_equity == 100000 + pnl_usd_all`.

### P-values

`p = mean(control >= real)` with the finite-sample correction `(p_raw*n + 1)/(n + 1)`.
The direction is **never** flipped for negative results: a losing strategy gets a p-value
near 1, not near 0. The matched-random control fires the same number of entries per day
as the strategy, on random symbols that pass `eligible()` (liquidity + all required
indicators non-NaN) on that date.

## Headline result (mechanical, from `BASELINE_REPORT.md`)

Trade statistics exclude censored trades and exits before 2016-01-01 (2015 is warm-up);
account statistics include every trade.

| Setup | n | Win rate | Avg win R | Avg loss R | Expectancy net | 95% CI | Expectancy gross | PF | CAGR | Max DD | Reconciliation |
|---|---|---|---|---|---|---|---|---|---|---|---|
| breakout_52week | 1876 | 47.2% | 1.086 | -0.986 | -0.008 | [-0.059, 0.046] | 0.064 | 0.98 | -1.6% | -36.0% | PASS |
| low_vol_setup | 1982 | 47.5% | 1.132 | -1.025 | 0.000 | [-0.052, 0.051] | 0.092 | 1.00 | -0.7% | -43.0% | PASS |
| statistical_mean_reversion | 1860 | 47.7% | 1.012 | -0.926 | -0.001 | [-0.051, 0.050] | 0.060 | 1.00 | -0.9% | -35.2% | PASS |
| volume_trend_accumulation | 2373 | 47.8% | 1.108 | -0.982 | 0.018 | [-0.028, 0.063] | 0.091 | 1.03 | 0.2% | -37.8% | PASS |

Matched-random control on per-trade expectancy (`r_net_mean`):

| Setup | Control runs | Control trades (mean) | Control expectancy (mean +/- std) | Strategy expectancy | p (matched_random) |
|---|---|---|---|---|---|
| breakout_52week | 30 | 1979.0 | 0.014 +/- 0.023 | -0.008 | 0.9355 |
| low_vol_setup | 30 | 2156.9 | 0.006 +/- 0.017 | 0.000 | 0.6774 |
| statistical_mean_reversion | 30 | 2260.1 | 0.006 +/- 0.024 | -0.001 | 0.6129 |
| volume_trend_accumulation | 30 | 2468.3 | 0.019 +/- 0.027 | 0.018 | 0.7742 |

Mechanical verdicts:

- **breakout_52week**: NO EVIDENCE OF EDGE
- **low_vol_setup**: SUSPECTED BUG investigate before trusting
- **statistical_mean_reversion**: NO EVIDENCE OF EDGE
- **volume_trend_accumulation**: NO EVIDENCE OF EDGE

The `low_vol_setup` flag fires because max drawdown (-43.0%) is worse than the report's
-40% guard. It is a request to investigate the account path, not a diagnosis.

## How to re-run

```bash
python scripts/run_research_baseline.py \
  --setup statistical_mean_reversion \
  --universe config/replay_universe_sp500.txt \
  --start 2015-01-01 --end 2026-11-11 \
  --cache-dir .cache/research \
  --output-dir docs/backtests/research \
  --n-matched 30 --n-random 0 --n-permuted 10 --n-shifted 2

python scripts/make_baseline_report.py
```

The cache is keyed by `SYMBOL__{start}__{end}` with a manifest, so re-requesting the same
window is fast and cannot mix spans. The runner refuses to write when the actual panel is
more than 10 days short of the request (unless `--allow-partial-panel`), when more than 5%
of tradable symbols end early, when the equity check fails, or when the invariant does
not hold. A completed run always exits 0; significance is printed as `INFO:`.

Fast smoke run (40 symbols, 2019-2020, separate `.cache/research_quick`):

```bash
python scripts/run_research_baseline.py --quick-setup statistical_mean_reversion
```

## Superseded files (quarantined)

`docs/backtests/research/invalid_20261110/` contains the 13 moved artifacts:

- the four D-80 `*_20261111_*_clean.json` files (2020-2023);
- the nine D-79/D-80 `*_20261110_*.json` files.

They were produced before the D-80 cache/data-end fixes and/or before the D-81 sizing,
marking, matched-control and p-value fixes. Keep them as an audit trail; do not cite
their returns, drawdowns, CAGR, volatility, alpha/beta or p-values. The quarantine
[README](invalid_20261110/README.md) lists the defects.

## Known limitations

- **Survivorship:** the universe is the *current* index membership. Companies removed
  from the index are absent; recent listings start late and enter only from their first
  bar (37 names).
- **One window, in-sample.** 2015-2026 has no walk-forward split, holdout or
  pre-registered out-of-sample test. `NO EVIDENCE OF EDGE` is the absence of evidence in
  this panel, not proof that a setup cannot work.
- **Fixed research exits.** 2.0 ATR stop, 3.0 ATR target, 15-bar time stop - not the
  deployed template geometry (D-70/D-77). A weak result here does not retire a screen
  from the live mix.
- **Drawdown guard is blunt.** A -40% max drawdown raises `SUSPECTED BUG` even when the
  reconciliation passes; it cannot distinguish a code defect from a genuinely bad path.
- **Trade-R Sharpe.** `sharpe` annualizes per-trade R by `sqrt(252)`; it is not a daily
  equity Sharpe. Compare only at similar trade counts.
- **Control floors.** With 30 matched runs the p-value floor is about 0.032; 10 permuted
  runs give 1/11 = 0.091; 2 shifted runs give 1/3 = 0.333. The shifted control is
  descriptive only and cannot establish superiority at p < 0.05.
- **No benchmark comparison in the report.** The generator records the account path but
  does not compute SPY buy-and-hold, so this folder makes no benchmark claim.
- **2015 is warm-up.** Trades with an exit before 2016-01-01 are excluded from the
  report's trade statistics because the longer indicator windows are still filling.
- **`^VIX` is downloaded** as a benchmark but is not used by any verdict or p-value.
