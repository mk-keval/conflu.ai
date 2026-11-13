# 2026-11-13 — Research Baseline v3: Engine Realism, One Evaluation Window, Honest Ratios (D-82)

**Branch:** `research/baseline-backtesting`
**Commits documented:** `c6d1780` (T0), `c6e7338` (T1), `69d45da` (T5), `bd93d02` (T2),
`7ed0135` (T3), `f07b576` (T4), `1fcac93` (T6a), `d3941e2` (T6b), `235f674` (T6c), plus
this documentation commit (find it with `git log --oneline -- docs/DECISIONS/D-82-*.md`).
**Decision:** [D-82](../DECISIONS/D-82-research-baseline-v3-engine-realism.md)
**Supersedes:** [D-81](../DECISIONS/D-81-research-baseline-v2-honesty-and-controls.md)
result tables (every D-81 harness guarantee stands and is still enforced)
**Experiment:** H-11 in [`docs/backtests/HYPOTHESIS_LOG.md`](../backtests/HYPOTHESIS_LOG.md)
**Documented:** 2026-11-13

---

## Summary

D-81 made the harness honest about *what it measured*. A follow-up audit of the same
harness found four ways it still measured something the strategy could not have done, and
three ways its headline statistics did not mean what their names said:

1. **Same-day slot recycling.** Exits were applied before entries, so a position closed on
   date D freed cash and a slot that a new position could spend at D's *open* — before the
   exit had filled.
2. **Unmasked indicator warm-up.** Every rolling/EWM indicator had a value from its first
   bar. Setups (and controls) could fire on partially formed indicators in 2015 or at the
   start of a recent listing. "2015 is warm-up" was a report filter, not an engine rule.
3. **Two different samples.** The strategy's trade statistics used every closed trade while
   the report showed exits from 2016 onward; controls were compared over yet another
   sample, and censored trades were handled inconsistently between the two paths.
4. **Controls that traded ineligible bars.** `permuted_signals` sampled any date after bar
   30 and `time_shifted_signals` kept any in-range destination, so a control could trade a
   pre-warm-up or illiquid bar the strategy could never have traded.
5. **A p-value on the wrong metric.** `compute_control_pvalues` defaulted to `r_net_sum`
   (grows with trade count) while the report's headline test is per-trade expectancy.
6. **Misnamed ratios.** `sharpe` annualised per-trade R by `sqrt(252)`; `cagr` divided the
   equity-curve length by 252 (a bar count) instead of using elapsed calendar time.
7. **An iid CI and a blunt bug label.** The 95% CI resampled trades independently even
   though exits cluster in time, and any max drawdown worse than -40% printed
   `SUSPECTED BUG` — a code-fault label for what can be a legitimate bad path.
8. **Unreproducible artifacts and no research CI.** A run started on a dirty tree recorded
   `dirty = true` and a HEAD that did not contain its code; nothing in CI ran the research
   tests or linted the research scripts.

This session fixed all eight, added read-only diagnostics and validity notes, re-ran all
four setups on one clean panel with defaults, regenerated `BASELINE_REPORT.md`, and put the
research tests and lint under CI.

Outcome: **89 tests pass**, `ruff` clean, all four accounts reconcile
(`Reconciliation: OK`, `invariant.holds = true`), all four artifacts record revision
`7ed0135` (the first run also records `dirty = false`; the other three record `dirty =
true` because the preceding run's artifact was untracked — see Deviations), and the
mechanical verdict is `NO EVIDENCE OF EDGE` for all four setups. `low_vol_setup` is no
longer flagged: its D-81 `SUSPECTED BUG` was the -43.0% drawdown guard, and under the D-82
engine its max drawdown is -31.6%. No production code path is involved.

---

## The eight defects and their fixes

### 1. Same-day slot recycling (engine look-ahead)

Entries fill at the next open; exits fill during the session. The loop processed exits
first, so cash and slots released on date D were available to entries also priced at D's
open.

Fix: exits detected on date D are applied **after** D's entries are sized.
`PortfolioRules.allow_same_day_recycling` defaults to `False`; `True` restores the pre-D-82
behaviour for comparison, and the flag is recorded in `run_info.portfolio_rules`.

Tests: `test_exits_do_not_fund_same_day_entries`,
`test_same_day_recycling_flag_restores_old_behaviour`.

### 2. Unmasked indicator warm-up

EMAs, RSI, ATR, ADX, MACD, CCI, Bollinger and volume averages were computed with no
`min_periods`, so every series had a value from the first few bars.

Fix: each indicator is masked at its own window. Values from the point the window is full
are identical to the unmasked series. ADX and the MACD signal line are computed on the
unmasked inputs and then hidden until their own history exists, so masking does not restart
a recursion and shift later values. `eligible()` now requires `atr14` in addition to the
other columns.

Tests: `test_indicators_are_nan_during_warmup`,
`test_masked_series_matches_unmasked_after_warmup`,
`test_macd_signal_starts_after_macd_history`.

### 3. One evaluation window

The strategy used every closed trade; the report displayed exits from 2016 onward; the
controls used a third sample; censored trades were treated inconsistently.

Fix: `EVAL_START = "2016-01-01"`. `trades_in_window(trades, since)` returns uncensored
trades whose `exit_date >= since`, and the real metrics plus all four control families use
it. Equity statistics (final equity, drawdown, daily Sharpe/Sortino, CAGR) stay on the
full curve. Reconciliation is computed from **all** trades so windowing cannot hide a cash
break. `run_info.eval_start` records the choice.

Test: `test_trades_in_window_drops_warmup_and_censored`.

### 4. Controls that traded ineligible bars

Fix: `permuted_signals` samples only eligible dates; `time_shifted_signals` keeps a
destination only when the symbol is eligible there. The dead `if/else` branch in
`permuted_signals` is deleted.

Tests: `test_permuted_signals_only_fire_on_eligible_dates`,
`test_time_shifted_signals_drop_ineligible_destinations`.

### 5. The p-value metric is the headline metric

Fix: `compute_control_pvalues` defaults to `metric_name="r_net_mean"`, matching the report.
The existing p-value tests now exercise the default.

### 6. Sharpe and CAGR mean what they say

Fix: `sharpe` is a daily-equity Sharpe —
`mean(daily return) / std(daily return, ddof=1) * sqrt(252)`; Sortino uses the
root-mean-square of negative daily returns as downside deviation; a flat curve returns 0,
not NaN. `cagr` uses `(last_date - first_date).days / 365.25` in both `metrics.py` and
`make_baseline_report.account_stats`.

Tests: `test_sharpe_from_daily_equity_returns`, `test_sharpe_zero_for_constant_equity`,
`test_cagr_uses_calendar_years_not_bar_count`, plus the existing CAGR test (fixture
corrected — see Deviations).

### 7. Month-block bootstrap CI; `REVIEW` instead of `SUSPECTED BUG`

Fix: the report resamples exit year-months with replacement (2000 resamples, seed 42) and
requires the **block** lower bound to be positive for `CANDIDATE`. The iid CI is shown for
reference. A drawdown breach alone prints
`REVIEW drawdown guard breached (not necessarily a bug)`; `SUSPECTED BUG` is kept for a
failed reconciliation, PF > 2.5 or win rate > 65%. A random-path drawdown scale was added
to the report so the number is interpretable.

Tests: `test_block_ci_is_finite_and_not_wider_than_degenerate`,
`test_verdict_drawdown_is_review_not_bug`, `test_verdict_uses_block_ci_not_iid`,
`test_verdict_requires_profitable_years`.

### 8. Clean-tree artifacts and research CI

Fix: `main()` refuses to start on a dirty working tree and points at `--allow-dirty`, which
records the dirt explicitly. `.github/workflows/research.yml` runs the nine research/report
test files and `ruff` on `backend/app/research` plus the three research scripts on every
push and pull request.

Tests: `test_dirty_tree_refused_without_flag`, `test_main_refuses_dirty_tree_before_any_work`.
The workflow is valid YAML and both of its commands pass locally; it was not exercised on
GitHub because nothing was pushed.

### Supporting work (no behaviour change)

- `scripts/research_diagnostics.py` + `DIAGNOSTICS.md`: seed sensitivity, cost sensitivity,
  data-integrity scan and exit mix. Read-only; no engine or artifact change.
- `VALIDITY_NOTES.md`: research conditions vs deployed YAML, setup naming, control design
  and known simplifications.
- `docs/SESSIONS/research-harden-d82-1og.md`: one entry per task with exact commands and
  output.

---

## Verification

| Check | Result |
|---|---|
| Research + report tests | **89 passed** (nine files) |
| `ruff check` (research package + 3 scripts) | clean |
| CI workflow | valid YAML; both steps pass locally; not yet run on GitHub (no push) |
| Baseline runs | 4/4 exit 0, `Reconciliation: OK`, `invariant.holds = true` |
| Artifact provenance | revision `7ed0135` in all four; `statistical_mean_reversion` records `dirty = false`, the other three `dirty = true` (the preceding run's untracked artifact; no source difference); `run_info.eval_start = "2016-01-01"`, `allow_same_day_recycling = false` |
| Requested vs actual span | 2015-01-01..2026-11-13 requested; 2015-01-02..2026-11-12 actual |
| Panel coverage | 501 tradable; `early_end = 0`; 37 `late_start`; 2 dropped (KVUE 1 row, VYLR 31 rows) |
| Cache | span `2015-01-01__2026-11-13`; 503 downloaded once (2 failed), then 503 hits per setup |
| No-look-ahead entry / max hold | PASS / 15 bars in all four |
| Drawdown breach | none (worst -35.6%); the `REVIEW` path is unit-tested, not exercised |

Test totals by stage: 43 at T0 (the four-file command specified for T0), 67 at the start of
T2, 82 at the end of T3, 84 after T6(a), 89 after T6(b). The D-81 note's "58" came from a
six-module run; both figures are correct for their file lists.

---

## Re-run design

| Item | Value |
|---|---|
| Window | 2015-01-01 to 2026-11-13 (actual 2015-01-02..2026-11-12) |
| Universe | current S&P 500 snapshot, SHA-256 `a53242f2...9a729080` |
| Symbols | 501 tradable; 503 loaded with SPY + ^VIX; 2 dropped (KVUE 1 row, VYLR 31 rows) |
| Cache | `.cache/research`, span-keyed; 503 downloaded, then 503 hits per setup |
| Exits | 2.0 ATR stop, 3.0 ATR target, 15-bar time stop |
| Portfolio | $100,000 start, 0.5% risk, 8 positions, 20% notional cap, 15 bps/side, no same-day recycling |
| Controls | 30 matched-random, 10 permuted, 2 shifted; 0 unmatched random |
| Evaluation window | uncensored trades with exit date >= 2016-01-01 for trade statistics and controls |
| Code | `7ed0135`; first run `dirty = false`, next three `dirty = true` (untracked artifact from the preceding run) |

Trade statistics in the report use `trades_in_window`; account statistics include every
trade. Reconciliation uses every trade.

---

## Results

Main table, verbatim from `BASELINE_REPORT.md`:

| Setup | n | Win rate | Avg win R | Avg loss R | Expectancy net | 95% CI (iid) | 95% CI (block) | Expectancy gross | PF | CAGR | Max DD | Reconciliation |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| breakout_52week | 1684 | 48.6% | 1.084 | -0.959 | 0.033 | [-0.022, 0.087] | [-0.044, 0.112] | 0.106 | 1.07 | 1.5% | -21.1% | PASS |
| low_vol_setup | 1746 | 48.4% | 1.121 | -0.998 | 0.028 | [-0.027, 0.084] | [-0.061, 0.120] | 0.119 | 1.05 | 1.6% | -31.6% | PASS |
| statistical_mean_reversion | 1680 | 50.1% | 1.015 | -0.920 | 0.049 | [-0.003, 0.099] | [-0.027, 0.130] | 0.111 | 1.11 | 2.4% | -23.4% | PASS |
| volume_trend_accumulation | 2120 | 47.0% | 1.088 | -0.973 | -0.004 | [-0.053, 0.044] | [-0.076, 0.069] | 0.068 | 0.99 | -0.6% | -35.6% | PASS |

Matched-random control on `r_net_mean`:

| Setup | Control runs | Control trades (mean) | Control expectancy (mean +/- std) | Strategy expectancy | p (matched_random) |
|---|---|---|---|---|---|
| breakout_52week | 30 | 1667.7 | 0.045 +/- 0.028 | 0.033 | 0.6452 |
| low_vol_setup | 30 | 1783.2 | 0.022 +/- 0.022 | 0.028 | 0.3871 |
| statistical_mean_reversion | 30 | 1870.1 | 0.035 +/- 0.023 | 0.049 | 0.2903 |
| volume_trend_accumulation | 30 | 2042.1 | 0.049 +/- 0.021 | -0.004 | 1.0000 |

Shadow controls (not used by the verdict): permuted p-values are 1.0000 / 0.8182 / 0.2727 /
1.0000 and shifted p-values are 0.3333 / 0.6667 / 1.0000 / 1.0000 for breakout / low_vol /
SMR / volume. Their floors are 0.091 and 0.333 at 10 and 2 runs.

Mechanical verdicts, verbatim:

- **breakout_52week**: NO EVIDENCE OF EDGE
- **low_vol_setup**: NO EVIDENCE OF EDGE
- **statistical_mean_reversion**: NO EVIDENCE OF EDGE
- **volume_trend_accumulation**: NO EVIDENCE OF EDGE

### D-81 vs D-82

| Setup | n (D-81 → D-82) | Expectancy net | PF | CAGR | Max DD | p (matched) | Verdict |
|---|---|---|---|---|---|---|---|
| breakout_52week | 1876 → 1684 | -0.008 → 0.033 | 0.98 → 1.07 | -1.6% → 1.5% | -36.0% → -21.1% | 0.9355 → 0.6452 | unchanged |
| low_vol_setup | 1982 → 1746 | 0.000 → 0.028 | 1.00 → 1.05 | -0.7% → 1.6% | **-43.0% → -31.6%** | 0.6774 → 0.3871 | **SUSPECTED BUG → NO EVIDENCE OF EDGE** |
| statistical_mean_reversion | 1860 → 1680 | -0.001 → 0.049 | 1.00 → 1.11 | -0.9% → 2.4% | -35.2% → -23.4% | 0.6129 → 0.2903 | unchanged |
| volume_trend_accumulation | 2373 → 2120 | 0.018 → -0.004 | 1.03 → 0.99 | 0.2% → -0.6% | -37.8% → -35.6% | 0.7742 → 1.0000 | unchanged |

Every setup trades less than under D-81: warm-up masking removes early signals and
no-recycling removes entries previously funded by the same day's exits. None of the four
matched p-values reaches 0.05; the smallest is 0.2903.

---

## Reading (mechanical only)

- No setup reached a favorable matched-control p-value on this panel.
- `low_vol_setup` is no longer flagged: the D-81 flag was the drawdown guard, not a
  p-value, and a drawdown breach alone would now print `REVIEW`.
- The D-82 numbers are somewhat better for three setups and slightly worse for volume.
  They are the size of the measurement changes, not a discovered edge; every block CI
  contains zero.
- Do not compare these figures with D-80 or D-81 as if they were the same experiment.
  Same window, different engine and different statistics.
- The artifacts predate T6(a) (control eligibility). Their control p-values therefore do
  not include that gate; the effect is strictly fewer ineligible control trades. T6 forbids
  re-running the baseline, so this is recorded, not fixed.
- These are research implementations with fixed ATR exits, not the deployed templates. No
  result here changes a screen, weight, gate, sample or forward verdict.

---

## Files

```
backend/app/research/engine.py
backend/app/research/indicators.py
backend/app/research/metrics.py
backend/app/research/setups.py
backend/app/research/control.py
backend/tests/test_research_engine.py
backend/tests/test_research_indicators.py
backend/tests/test_research_metrics.py
backend/tests/test_research_control.py
backend/tests/test_research_setups.py
backend/tests/test_research_diagnostics.py      (new)
backend/tests/test_research_runner.py           (new)
backend/tests/test_make_baseline_report.py      (new)
scripts/run_research_baseline.py
scripts/make_baseline_report.py
scripts/research_diagnostics.py                 (new)
.github/workflows/research.yml                  (new)
docs/backtests/research/BASELINE_REPORT.md
docs/backtests/research/{setup}_20261113_*.json (4 new artifacts)
docs/backtests/research/DIAGNOSTICS.md          (new)
docs/backtests/research/VALIDITY_NOTES.md       (new)
```

## Documentation updates

- Created `docs/DECISIONS/D-82-research-baseline-v3-engine-realism.md`.
- Created this session log.
- Rewrote `docs/backtests/research/README.md` for the 2026-11-13 artifacts, the new
  metrics and columns, the clean-tree rule and the evaluation window.
- Added H-11 to `docs/backtests/HYPOTHESIS_LOG.md`; H-10 stays as superseded history.
- Updated `docs/DECISIONS/index.md`, `docs/index.md` and root `INDEX.md`.
- Added a superseded-results banner to D-81 and this session log's predecessor; corrected
  the D-81 commit line (it was committed as `90bfea5`, while its artifacts record
  `dcc9565` dirty) and the "2015 is warm-up" claim (a report filter only; real masking
  landed in D-82).
- `ARCHITECTURE.md` and `API.md` intentionally unchanged: no production wiring.

---

## Deviations

- **The verdict rule changed after seeing D-81.** The block CI and the `REVIEW` relabel are
  post-hoc; both are recorded in D-82 rather than buried. Under the old rule the D-82
  verdicts would be identical; the block CI is stricter, not looser.
- **CAGR changed definition** from bar count to elapsed calendar years, and **Sharpe
  changed meaning** from per-trade R to daily equity. The D-81 columns are not directly
  comparable.
- **`test_cagr_calculation`'s fixture was corrected** (504 daily bars → a true two-year
  span) because the old fixture encoded `len/252` as "two years". The assertion strength
  (9.54% ± 0.5) is unchanged.
- **`DIAGNOSTICS.md` was computed from the D-81 artifacts** (window ending 2026-11-11)
  before the D-82 engine changes. It explains the D-81 magnitudes; it is not a D-82 table.
- **T4's default `--end` is 2026-11-13**, one day later than D-81's 2026-11-11, because the
  task required defaults. That forced one fresh 503-symbol download.
- **Three of the four artifacts record `dirty = true`.** T4 started on a clean tree, but
  each run writes its JSON into `docs/backtests/research/`, and the clean-tree guard only
  landed in T6(b) (`d3941e2`). The second, third and fourth runs therefore saw the
  preceding run's untracked artifact and recorded `dirty = true`. All four ran at revision
  `7ed0135`; `f07b576` contains only the four JSONs, the report and the work log, so no
  source file differed. The first run is the one that records `dirty = false`. The
  artifacts were not re-run or edited; T6(b) exists to stop this recurring.

---

## Next steps

1. Re-run the four setups once on a clean tree **after** T6(a) if a control p-value that
   includes control eligibility is needed; pre-register it first.
2. Raise `--n-shifted` above 20, or stop citing the shifted control for anything.
3. Add a walk-forward split (e.g. 2015-2020 fit / 2021-2026 test) before treating any setup
   as more than exploratory.
4. Re-generate `DIAGNOSTICS.md` from the D-82 artifacts on the next run.
5. Study the `low_vol_setup` risk setting; its -31.6% drawdown is within the guard but
   still the second-worst path.

---

## Status

| Item | Status |
|---|---|
| Same-day recycling | Fixed + tested (`allow_same_day_recycling=False`) |
| Indicator warm-up | Masked + tested; `eligible()` requires `atr14` |
| One evaluation window | Implemented + tested (`trades_in_window`, `EVAL_START`) |
| Control eligibility | Fixed + tested (T6a) |
| p-value default metric | `r_net_mean` |
| Daily-equity Sharpe / calendar CAGR | Implemented + tested |
| Block-bootstrap CI / `REVIEW` label | Implemented + tested |
| Clean-tree refusal | Implemented + tested (`--allow-dirty`) |
| Research CI | `.github/workflows/research.yml` |
| Diagnostics + validity notes | `DIAGNOSTICS.md`, `VALIDITY_NOTES.md` |
| 2015-2026 re-run | Done, 4/4 reconcile, report regenerated |
| Production impact | None |
| Live trading rules | Unchanged |
