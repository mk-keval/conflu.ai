# D-82: Research Baseline v3 — Engine Realism, One Evaluation Window, Honest Ratios

**Date:** 2026-11-13
**Status:** Accepted and implemented. **The 2015-2026 results recorded here supersede the
D-81 result tables.** Every D-81/D-80 harness guarantee (span-keyed cache, `data_end`
closes, forward-filled marking, no look-ahead sizing, matched control, one-sided p-value,
coverage gate, hard reconciliation) stands and is still enforced.
**Branch:** `research/baseline-backtesting`
**Commits:** `c6d1780`..`235f674` (T0, T1, T5, T2, T3, T4, T6a, T6b, T6c). The four
artifacts all record `run.code.revision = 7ed0135`; the first run records
`run.code.dirty = false` and the other three record `dirty = true` because the preceding
run's artifact was untracked in the tree (no source file differed — see Deviations).
**Related:** D-81 (superseded results), D-80, D-79, H-11 in
[`docs/backtests/HYPOTHESIS_LOG.md`](../backtests/HYPOTHESIS_LOG.md),
[`VALIDITY_NOTES.md`](../backtests/research/VALIDITY_NOTES.md),
[`DIAGNOSTICS.md`](../backtests/research/DIAGNOSTICS.md), D-70, D-74, D-75, D-76.

## Context

D-81 made the research harness honest about what it *measured*: the cache was
span-keyed, positions could no longer strand at a symbol's data end, entries sized off
previous-close equity, and the control was size-matched. A follow-up audit of the same
harness found that some of what it measured was still not a decision the strategy could
have made, and that several headline names were computed over the wrong sample:

1. **Same-day slot recycling (engine look-ahead).** Exits were processed before entries.
   A position that closed on date D freed a slot and cash that same date, and a new
   position could be bought at D's open using money released by a D exit. In reality the
   exit fills during the session and the entry fills at the open; the two cannot fund one
   another.
2. **Unmasked indicator warm-up.** The EMAs, RSI, ATR, ADX, MACD, CCI, Bollinger and
   volume averages were computed with no `min_periods`, so every series had a value from
   the first few bars. Setups could fire in 2015 (or at the start of a recent listing's
   history) on partially formed indicators. "2015 is warm-up" was a *report* filter, not
   an engine guarantee.
3. **A p-value on the wrong metric.** `compute_control_pvalues` defaulted to
   `metric_name="r_net_sum"`, which grows with trade count, while the report's headline
   test is per-trade expectancy (`r_net_mean`). The default and the report disagreed.
4. **Two different samples.** The real strategy's trade statistics used every closed
   trade, while the report displayed exits from 2016 onward. The strategy and the
   controls were also compared over different samples, and censored trades were treated
   inconsistently between the two paths.
5. **Ratios that were not what their names said.** `sharpe` annualised the per-trade
   mean/std of R by `sqrt(252)` — not a Sharpe ratio — and `cagr` divided the equity
   curve length by 252 (a bar count) instead of using elapsed calendar time.
6. **An iid bootstrap and a blunt bug label.** The 95% CI resampled trades
   independently even though exits cluster in time, and any max drawdown worse than
   -40% produced `SUSPECTED BUG` — a code-fault label for what can be a legitimate bad
   equity path.
7. **Controls that traded ineligible bars.** `permuted_signals` sampled any date after
   bar 30 and `time_shifted_signals` kept any in-range destination, so a control could
   trade a pre-warm-up or illiquid bar the strategy could never have traded.
8. **Unreproducible artifacts.** A run started on a dirty tree wrote
   `run.code.dirty = true` and a HEAD that did not contain the code that produced it, and
   nothing in CI ran the research tests or linted the research scripts.

## Decision

Adopt the following contract for every research baseline from v3 onward.

1. **No same-day recycling.** `PortfolioRules.allow_same_day_recycling` defaults to
   `False`: exits detected on date D are applied **after** D's entries are sized, so a D
   exit cannot fund a D entry. `True` restores the pre-D-82 behaviour for comparison
   only, and the flag is recorded in `run_info.portfolio_rules`.
2. **Warm-up is real, not cosmetic.** Every indicator is masked with `min_periods` equal
   to its window; values from the point the window is full are identical to the unmasked
   series. ADX and the MACD signal line are computed on the unmasked inputs and then
   hidden until their own history exists, so masking does not restart a recursion and
   shift later values. `eligible()` requires `atr14` in addition to the other columns,
   so no setup and no control can act on a partially formed bar.
3. **One evaluation window.** `EVAL_START = "2016-01-01"`. `trades_in_window(trades,
   since)` returns uncensored trades whose `exit_date >= since`; the real metrics and all
   four control families use it. Equity-based statistics (final equity, drawdown, daily
   Sharpe/Sortino, CAGR) stay on the full curve. Reconciliation is computed from **all**
   trades, so windowing cannot hide a cash break. `run_info.eval_start` records the
   choice.
4. **The p-value metric is the headline metric.** `compute_control_pvalues` defaults to
   `r_net_mean`, matching the report.
5. **Sharpe is a daily-equity Sharpe.** `mean(daily equity return) / std(daily equity
   return, ddof=1) * sqrt(252)`. Sortino uses the root-mean-square of negative daily
   returns as downside deviation. A flat curve returns 0, not NaN.
6. **CAGR uses calendar time.** `(last_date - first_date).days / 365.25` in both
   `metrics.py` and `make_baseline_report.account_stats`.
7. **The verdict uses a month-block bootstrap CI.** The report resamples exit year-months
   with replacement (2000 resamples, seed 42) and requires the **block** lower bound to be
   positive for `CANDIDATE`. The iid CI is shown for reference only.
8. **A drawdown breach is `REVIEW`, not `SUSPECTED BUG`.** `SUSPECTED BUG` is kept for a
   failed reconciliation, PF > 2.5 or win rate > 65%. A drawdown breach alone prints
   `REVIEW drawdown guard breached (not necessarily a bug)`.
9. **Controls obey `eligible()`.** Permutation samples only eligible dates; a time-shifted
   destination is kept only when the symbol is eligible there. The dead
   `if/else` branch in `permuted_signals` is deleted.
10. **Artifacts come from a clean tree.** `main()` refuses to start on a dirty working
    tree and points at `--allow-dirty`, which records the dirt explicitly.
11. **CI guards the harness.** `.github/workflows/research.yml` runs the nine research /
    report test files and `ruff` on `backend/app/research` plus the three research
    scripts on every push and pull request.

## What changed

| # | Defect | Change | Commit | Regression test |
|---|---|---|---|---|
| 1 | Same-day slot recycling | Exits are deferred until after entries are sized; `allow_same_day_recycling` defaults to `False` and is recorded in the artifact. | `bd93d02` | `test_exits_do_not_fund_same_day_entries`, `test_same_day_recycling_flag_restores_old_behaviour` |
| 2 | Unmasked warm-up | `min_periods` on every rolling/EWM indicator; ADX/MACD computed unmasked then masked; `eligible()` requires `atr14`. | `bd93d02` | `test_indicators_are_nan_during_warmup`, `test_masked_series_matches_unmasked_after_warmup`, `test_macd_signal_starts_after_macd_history` |
| 3 | Wrong p-value default | `metric_name` defaults to `r_net_mean`. | `7ed0135` | control tests (existing p-value tests now exercise the default) |
| 4 | Two samples | `trades_in_window`; `EVAL_START`; window passed to every control; `run_info.eval_start`; invariant from all trades. | `7ed0135` | `test_trades_in_window_drops_warmup_and_censored` |
| 5 | Misnamed ratios | Daily-equity Sharpe/Sortino; calendar-year CAGR in metrics and report. | `7ed0135` | `test_sharpe_from_daily_equity_returns`, `test_sharpe_zero_for_constant_equity`, `test_cagr_uses_calendar_years_not_bar_count` |
| 6 | iid CI / blunt bug label | Month-block bootstrap CI; verdict uses its lower bound; drawdown breach relabelled `REVIEW`; random-path drawdown scale added. | `7ed0135` | `test_block_ci_is_finite_and_not_wider_than_degenerate`, `test_verdict_drawdown_is_review_not_bug`, `test_verdict_uses_block_ci_not_iid` |
| 7 | Ineligible control bars | Permutation and shift apply `eligible()`; dead branch removed. | `1fcac93` | `test_permuted_signals_only_fire_on_eligible_dates`, `test_time_shifted_signals_drop_ineligible_destinations` |
| 8 | Dirty-tree artifacts | `_require_clean_tree` + `--allow-dirty`; refusal happens before any work. | `d3941e2` | `test_dirty_tree_refused_without_flag`, `test_main_refuses_dirty_tree_before_any_work` |
| 9 | No research CI | `.github/workflows/research.yml` (tests + ruff on every push/PR). | `235f674` | workflow linted locally; same two commands pass locally |

Supporting work in the same branch:

- `scripts/research_diagnostics.py` + `DIAGNOSTICS.md` (`c6e7338`): seed sensitivity, cost
  sensitivity, data-integrity scan and exit mix. Read-only; no engine or artifact change.
- `VALIDITY_NOTES.md` (`69d45da`): research conditions vs deployed YAML, setup naming,
  control design and simplifications.
- Work log `docs/SESSIONS/research-harden-d82-1og.md` (`c6d1780` onward): one entry per
  task with the exact commands and output.

## Verification

| Check | Result |
|---|---|
| Research + report tests | **89 passed** (`test_research_{control,data,diagnostics,engine,indicators,metrics,runner,setups}.py` + `test_make_baseline_report.py`) |
| `ruff check` (research package + 3 scripts) | clean |
| CI workflow | valid YAML; both steps pass locally; not yet exercised on GitHub (no push) |
| Baseline runs | 4/4 exit 0, `Reconciliation: OK`, `invariant.holds = true` |
| Artifact provenance | revision `7ed0135` in all four; `statistical_mean_reversion` records `dirty = false`, the other three `dirty = true` (the preceding run's untracked artifact; no source difference); `run_info.eval_start = "2016-01-01"`, `allow_same_day_recycling = false` |
| Panel | requested `2015-01-01..2026-11-13`; actual `2015-01-02..2026-11-12`; 501 tradable; `early_end = 0`; `late_start = 37`; 2 dropped (KVUE 1 row, VYLR 31 rows) |
| Cache | span `2015-01-01__2026-11-13`; 503 downloaded once (2 failed), then 503 hits per setup |
| No-look-ahead entry / max hold | PASS / 15 bars in all four artifacts |
| Drawdown breach | none (worst max DD -35.6%); the `REVIEW` path is unit-tested, not exercised by these artifacts |

Test totals by stage: 43 at T0 (the four-file command specified for T0), 67 at the start
of T2, 82 at the end of T3, 84 after T6(a), 89 after T6(b). The D-81 note's "58" came from
a six-module run; both figures are correct for their file lists and the difference is
recorded in the T0 work-log entry rather than silently reconciled.

## Results (valid for this panel and window)

Verbatim mechanical output of
[`BASELINE_REPORT.md`](../backtests/research/BASELINE_REPORT.md). Trade statistics exclude
censored trades and exits before 2016-01-01; account statistics include every trade.

| Setup | n | Win rate | Avg win R | Avg loss R | Expectancy net | 95% CI (iid) | 95% CI (block) | Expectancy gross | PF | CAGR | Max DD | Reconciliation |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| breakout_52week | 1684 | 48.6% | 1.084 | -0.959 | 0.033 | [-0.022, 0.087] | [-0.044, 0.112] | 0.106 | 1.07 | 1.5% | -21.1% | PASS |
| low_vol_setup | 1746 | 48.4% | 1.121 | -0.998 | 0.028 | [-0.027, 0.084] | [-0.061, 0.120] | 0.119 | 1.05 | 1.6% | -31.6% | PASS |
| statistical_mean_reversion | 1680 | 50.1% | 1.015 | -0.920 | 0.049 | [-0.003, 0.099] | [-0.027, 0.130] | 0.111 | 1.11 | 2.4% | -23.4% | PASS |
| volume_trend_accumulation | 2120 | 47.0% | 1.088 | -0.973 | -0.004 | [-0.053, 0.044] | [-0.076, 0.069] | 0.068 | 0.99 | -0.6% | -35.6% | PASS |

Matched-random control on per-trade expectancy (`r_net_mean`):

| Setup | Control runs | Control trades (mean) | Control expectancy (mean +/- std) | Strategy expectancy | p (matched_random) |
|---|---|---|---|---|---|
| breakout_52week | 30 | 1667.7 | 0.045 +/- 0.028 | 0.033 | 0.6452 |
| low_vol_setup | 30 | 1783.2 | 0.022 +/- 0.022 | 0.028 | 0.3871 |
| statistical_mean_reversion | 30 | 1870.1 | 0.035 +/- 0.023 | 0.049 | 0.2903 |
| volume_trend_accumulation | 30 | 2042.1 | 0.049 +/- 0.021 | -0.004 | 1.0000 |

Shadow controls (`permuted` / `shifted` p-values): 1.0000 / 0.3333 (breakout),
0.8182 / 0.6667 (low_vol), 0.2727 / 1.0000 (SMR), 1.0000 / 1.0000 (volume).

Mechanical verdicts (verbatim):

- **breakout_52week**: NO EVIDENCE OF EDGE
- **low_vol_setup**: NO EVIDENCE OF EDGE
- **statistical_mean_reversion**: NO EVIDENCE OF EDGE
- **volume_trend_accumulation**: NO EVIDENCE OF EDGE

### D-81 vs D-82

The two runs share the window, universe, costs, exits and control budget. They differ in
the engine and measurement contract above, and in one extra day of data.

| Setup | n (D-81 → D-82) | Expectancy net | PF | CAGR | Max DD | p (matched) | Verdict (D-81 → D-82) |
|---|---|---|---|---|---|---|---|
| breakout_52week | 1876 → 1684 | -0.008 → 0.033 | 0.98 → 1.07 | -1.6% → 1.5% | -36.0% → -21.1% | 0.9355 → 0.6452 | NO EVIDENCE OF EDGE (unchanged) |
| low_vol_setup | 1982 → 1746 | 0.000 → 0.028 | 1.00 → 1.05 | -0.7% → 1.6% | **-43.0% → -31.6%** | 0.6774 → 0.3871 | **SUSPECTED BUG → NO EVIDENCE OF EDGE** |
| statistical_mean_reversion | 1860 → 1680 | -0.001 → 0.049 | 1.00 → 1.11 | -0.9% → 2.4% | -35.2% → -23.4% | 0.6129 → 0.2903 | NO EVIDENCE OF EDGE (unchanged) |
| volume_trend_accumulation | 2373 → 2120 | 0.018 → -0.004 | 1.03 → 0.99 | 0.2% → -0.6% | -37.8% → -35.6% | 0.7742 → 1.0000 | NO EVIDENCE OF EDGE (unchanged) |

Every setup trades less than under D-81. That is the expected direction: warm-up masking
removes early signals, and no-recycling removes entries that were previously funded by the
same day's exits. The drawdowns are smaller partly for the same reason and partly because
`max_drawdown_pct` is now computed on a curve whose trade statistics are windowed
consistently. None of the four matched-control p-values reaches 0.05; the smallest is
0.2903.

## Reading the result

- **No setup has evidence of an edge on this panel.** `NO EVIDENCE OF EDGE` is the
  mechanical output of the pre-registered rules, not a judgement added afterwards.
- **`low_vol_setup` is no longer flagged.** Its D-81 flag was the -40% drawdown guard
  (-43.0%), not a p-value result. Under the D-82 engine its drawdown is -31.6%, and a
  drawdown breach alone would now print `REVIEW`, not `SUSPECTED BUG`.
- **The D-82 numbers are somewhat better for three setups and slightly worse for
  volume.** The differences are the size of the measurement changes, not a discovered
  edge; every block CI contains zero comfortably.
- **Do not compare these numbers to D-80 or to D-81 as if they were the same
  experiment.** Same window, different engine and different statistics. D-81 remains
  citable only as the previous baseline under its own contract; its result table is
  superseded for current use.
- **The control is now as strict as the strategy.** Permutation and shift cannot place a
  signal on a bar the strategy could not have traded. The artifacts were produced just
  before that change landed (`f07b576` at `7ed0135`, fix in `1fcac93`); the effect on
  the four p-values is not re-measured here because T6 forbids re-running the baseline.
  The direction is strictly fewer ineligible control trades, i.e. a marginally tighter
  comparison, not a friendlier one.

## Deviations from the pre-registered plan

- **The verdict rule changed after seeing D-81.** The switch from the iid CI to the
  month-block CI lower bound, and the relabelling of a drawdown-only breach from
  `SUSPECTED BUG` to `REVIEW`, both happened after the D-81 result table existed. They
  are honest corrections to how a path-dependent statistic is tested, but they are
  post-hoc and they are recorded here rather than buried. Under the old rule the D-82
  verdicts would be identical (`NO EVIDENCE OF EDGE` for all four); the block CI is
  stricter, not looser.
- **CAGR changed definition** from `len(equity)/252` years to elapsed calendar years.
  Both implementations are pinned by tests; the D-81 CAGR column is not directly
  comparable.
- **The Sharpe column changed meaning** from a per-trade R ratio to a daily-equity
  Sharpe. It is not used by the verdict.
- **`test_cagr_calculation`'s fixture was corrected** (504 daily bars → a true two-year
  span) because the old fixture encoded `len/252` as "two years". The assertion strength
  is unchanged (9.54% +/- 0.5).
- **`DIAGNOSTICS.md` was refreshed after this record was written** (2026-11-16, engine
  `7628660`). Its seed/cost/exit-mix sections use the script's 2015-01-01..2026-11-11 panel,
  and its artifact-derived columns come from the same-day-recycling ablation runs, not from
  the four v3 artifacts.
- **The v3 artifacts predate T6(a).** Their control p-values do not include the
  eligibility gate on permuted/shifted signals (see above). T6 forbids re-running the
  baseline, so this is recorded, not fixed.
- **T4's default `--end` is 2026-11-13**, one day later than D-81's 2026-11-11, because
  the task requires defaults. The panel therefore ends 2026-11-12 and one fresh 503-symbol
  download was needed.
- **Three of the four artifacts record `dirty = true`, not `false`.** T4 required a clean
  tree, and it started clean, but each run writes its artifact into
  `docs/backtests/research/`; because the clean-tree guard did not exist yet (`d3941e2`,
  T6b, landed later), the second, third and fourth runs saw the preceding run's untracked
  JSON and recorded `dirty = true`. All four ran at revision `7ed0135` and no source file
  differed between them: `f07b576` contains only the four JSON files, the regenerated
  report and the work log. The first run (`statistical_mean_reversion`) is the one that
  records `dirty = false`. This is exactly the failure mode T6(b) now blocks; the artifacts
  were not patched up or re-run.

## What this does not settle

- **Survivorship.** The universe is the current S&P 500 snapshot; companies removed from
  the index are absent, and recent listings start late (37 symbols).
- **One window, in-sample.** 2015-2026 spans several regimes, but there is no walk-forward
  split, holdout or pre-registered out-of-sample test.
- **Fixed research exits.** 2.0 ATR stop, 3.0 ATR target, 15-bar hold — not the deployed
  template geometry (D-70/D-77). A weak result here does not retire a live screen.
- **Control floors.** 30 matched runs give a p-value floor of about 0.032; 10 permuted
  runs give 0.091; 2 shifted runs give 0.333. The shifted control is descriptive only.
- **No benchmark comparison.** The report records the account path but does not compute
  SPY buy-and-hold, so this folder makes no benchmark claim.
- **The drawdown guard is still blunt in the other direction.** `REVIEW` correctly stops
  calling a bad path a bug, but it does not distinguish "bad path under this risk
  setting" from "risk setting is wrong for the strategy".

## Consequences

- `BASELINE_REPORT.md` becomes the citable summary for the D-82 panel. The four
  `*_20261113_*.json` artifacts are the underlying evidence.
- The D-81 `*_20261111_21*.json` artifacts and their report table remain in the repo as
  the previous baseline; they are marked superseded and must not be cited as current.
- H-11 records the D-82 result; H-10 (D-81) stays as superseded history.
- The research README, decision index, docs index and root index point at D-82.
- The same-day-recycling ablation (D-82 default vs `--allow-same-day-recycling`) is in
  [`ABLATION.md`](../backtests/research/ABLATION.md).
- **No live behaviour changed.** The research package is not imported by the API, the
  gate, the journal, the scorecard or the forward loop. Nothing here enters the D-75 pass
  bar, the kill rule or any FWD-v0.2 verdict.

## Alternatives considered

- **Keep same-day recycling as the default and only document it.** Rejected: using cash
  released by an exit that fills later in the day to buy at the open is look-ahead, not a
  modelling choice. The flag keeps the old behaviour reproducible for comparison.
- **Mask only the longest window (EMA200).** Rejected: RSI/ATR/ADX/CCI/Bollinger all have
  short warm-ups that still produced partially formed values. Masking each at its own
  window is the smallest correct rule.
- **Keep the iid bootstrap because it was already specified.** Rejected: exits cluster in
  time, so the iid interval is too narrow exactly where the result matters. The block CI
  is stricter and is used only for the upper-bound test, not to rescue a result.
- **Keep `SUSPECTED BUG` for drawdowns.** Rejected: a -40% path can be the configured
  risk working as intended; calling it a bug teaches readers to ignore the label.
- **Re-run the baseline after T6(a) to fold in control eligibility.** Rejected by the task
  rules and by discipline: the next run should be a deliberate, pre-registered one, not a
  patch-up of the run that is being documented.
- **Move the D-81 artifacts to the quarantine.** Rejected: they were valid for the D-81
  contract. They are marked superseded in place; the quarantine remains for artifacts
  produced under known defects (D-79/D-80).

## Follow-ups

1. Re-run the four setups once on a clean tree **after** T6(a) if a current control
   p-value that includes control eligibility is needed; pre-register it first.
2. Raise `--n-shifted` above 20 or drop the shifted control from any claim it cannot
   support (its floor is 0.333).
3. Add a walk-forward split (e.g. 2015-2020 fit / 2021-2026 test) before any setup is
   treated as more than exploratory.
4. ~~Re-generate `DIAGNOSTICS.md` from the D-82 artifacts when the baseline is next run.~~
   Done on 2026-11-16 under engine `7628660`; see `DIAGNOSTICS.md` and `ABLATION.md`.
5. Consider a risk-setting study for `low_vol_setup`; its -31.6% drawdown is within the
   guard but still the second-worst path.
