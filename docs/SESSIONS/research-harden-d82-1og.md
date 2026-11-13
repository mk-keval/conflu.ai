# Research Harden D-82 — Work Log

Append-only log for the D-82 research-harness hardening tasks. One entry per task.

---

## T0 — Verification (change no code)

- **Date:** 2026-11-12
- **Branch:** `research/baseline-backtesting` @ `90bfea5` (pulled; already up to date)
- **What changed and why:** nothing in code. Baseline verification of the state left by
  D-81 before starting T1.
- **Files touched:** `docs/SESSIONS/research-harden-d82-1og.md` (this file only).

### Commands and exact output

```text
$ pytest backend/tests/test_research_control.py backend/tests/test_research_data.py backend/tests/test_research_engine.py backend/tests/test_research_metrics.py -q
...........................................                                                                                                                                                               [100%]
43 passed in 4.04s
LASTEXIT=0
```

Note: the D-81 session note claims "58 passed". The command specified for T0 covers
four of the six research test modules and yields **43**. The 58 figure came from a
six-module run in D-81 (`test_research_data`, `test_research_engine`,
`test_research_metrics`, `test_research_setups`, `test_research_indicators`,
`test_research_control`). No test was skipped or modified here.

```text
$ ruff check backend/app/research scripts/run_research_baseline.py scripts/make_baseline_report.py backend/tests/test_research_*.py
All checks passed!
LASTEXIT=0
```

```text
$ python scripts/run_research_baseline.py --quick
...
Reconciliation: OK
INFO: NOT statistically significant vs controls (best p=0.6667 on permuted)
LASTEXIT=0
```

The quick run used `.cache/research_quick`, completed, printed `Reconciliation: OK`
and an `INFO:` significance line, and exited 0. Yahoo access worked (the run
downloaded or reused the quick cache without a network error). Result artifact:
`.cache/research_quick/out/statistical_mean_reversion_20261112_180109.json`
(ignored by git).

### Outcome

- Tests: **pass** (43/43).
- Ruff: **clean**.
- Quick run: **exit 0**, reconciliation OK, INFO line present.
- Skipped: none.
- Gate for T1: **open** (no earlier task outstanding).

---

## T1 — Read-only diagnostics

- **Date:** 2026-11-12
- **What changed and why:** added one read-only diagnostics script, one test file and one
  generated report. The engine, setups, indicators, control and artifacts were **not**
  modified. The script exists to quantify four things the baseline report does not show:
  how much the candidate shuffle moves the headline, how far costs can rise before
  expectancy dies, whether the loaded panel contains broken bars, and whether the strategy's
  exit mix differs from a matched-random book.
- **Files touched:**
  - `scripts/research_diagnostics.py` (new)
  - `backend/tests/test_research_diagnostics.py` (new)
  - `docs/backtests/research/DIAGNOSTICS.md` (new, generated)
  - `docs/SESSIONS/research-harden-d82-1og.md` (this file)
- **Design notes / choices:**
  - Window is `2015-01-01` to `2026-11-11`, which matches the existing span-keyed cache
    `.cache/research` (`2015-01-01__2026-11-11`, 503 manifest entries) and the newest D-81
    artifacts. `--end` therefore reads the latest cached span rather than today's date
    (today is 2026-11-12, the cache's last actual bar is 2026-11-10).
  - `--cache-max-age-hours` defaults to `1e9` so the existing cache is reused instead of
    being re-downloaded by the 20h default.
  - Trade statistics use `censored == False` and `exit_date >= 2016-01-01`; CAGR and max
    drawdown come from the full equity curve.
  - Seed-sensitivity std uses `np.std` (ddof=0) to match the artifact `control_summary`
    std convention.
  - Setup selection is `--setups`; seeds are `--seeds` (`42-61` or `42,44,50`).
  - One engine run took ~5s, so the full 20-seed sweep was kept and the "drop to 10 seeds"
    fallback was not needed.

### Commands and exact output

```text
$ pytest backend/tests/test_research_diagnostics.py -q
...                                                                                                                                                                                                       [100%]
3 passed in 1.23s
LASTEXIT=0
```

```text
$ ruff check scripts/research_diagnostics.py backend/tests/test_research_diagnostics.py
All checks passed!
LASTEXIT=0
```

Single-setup smoke run used to validate the script end to end before the full sweep:

```text
$ python scripts/research_diagnostics.py --setups statistical_mean_reversion --seeds 42 --report "$env:TEMP\diag_smoke.md"
Panel: 503 symbols, 2015-01-02 -> 2026-11-10, cache hits=503 downloads=0 failed=2
[statistical_mean_reversion] (a) seed sensitivity, 1 seeds
    seed 42: n=1860 mean=-0.0012
[statistical_mean_reversion] (b) cost sensitivity
    cost  0.0 bps: n=1857 exp_net=+0.0625
    cost  7.5 bps: n=1857 exp_net=+0.0319
    cost 15.0 bps: n=1860 exp_net=-0.0012
    cost 30.0 bps: n=1860 exp_net=-0.0624
[statistical_mean_reversion] (d) exit mix
    matched seed 30042: n=2050
    matched seed 30043: n=2070
    matched seed 30044: n=2069
    matched seed 30045: n=2055
    matched seed 30046: n=2071
Wrote C:\Users\keval\AppData\Local\Temp\diag_smoke.md
LASTEXIT=0
```

Full run (all four setups, seeds 42..61):

```text
$ python scripts/research_diagnostics.py
...
Panel: 503 symbols, 2015-01-02 -> 2026-11-10, cache hits=503 downloads=0 failed=2

[statistical_mean_reversion] (a) seed sensitivity, 20 seeds
    seed 42: n=1860 mean=-0.0012
    ...
    seed 61: n=1900 mean=-0.0215
[statistical_mean_reversion] (b) cost sensitivity
[statistical_mean_reversion] (d) exit mix
[breakout_52week] building signals
[breakout_52week] (a) seed sensitivity, 20 seeds
    seed 61: n=1896 mean=+0.0151
[breakout_52week] (b) cost sensitivity
[breakout_52week] (d) exit mix
[low_vol_setup] building signals
[low_vol_setup] (a) seed sensitivity, 20 seeds
    seed 61: n=1961 mean=-0.0179
[low_vol_setup] (b) cost sensitivity
[low_vol_setup] (d) exit mix
[volume_trend_accumulation] building signals
[volume_trend_accumulation] (a) seed sensitivity, 20 seeds
    seed 61: n=2388 mean=-0.0245
[volume_trend_accumulation] (b) cost sensitivity
[volume_trend_accumulation] (d) exit mix

(c) data integrity scan

Wrote docs/backtests/research/DIAGNOSTICS.md
LASTEXIT=0
ELAPSED_SEC=754.2
```

`$KVUE` failed to download (delisted / no price data for 2015-01-01 -> 2026-11-12) and was
dropped by `download_daily`; this is the `failed=2` count and is pre-existing, not a T1
regression. No cache download was needed.

### Report contents (real numbers, from `docs/backtests/research/DIAGNOSTICS.md`)

`DIAGNOSTICS.md` is 123 lines and all four tables are populated:

- **(a) Seed sensitivity** — across-seed std of the mean net R is 0.0136 / 0.0170 / 0.0175 /
  0.0219 for statistical_mean_reversion / breakout_52week / low_vol_setup /
  volume_trend_accumulation, against matched-control std 0.0243 / 0.0233 / 0.0174 / 0.0268
  from the newest artifacts.
- **(b) Cost sensitivity** — net expectancy crosses zero at 14.72 / 13.37 / 15.08 / 18.49 bps
  per side (same setup order).
- **(c) Data integrity** — 1,441,683 bars, 3,649 flagged, 31 bars with |return| > 40%,
  419 bars with open/close outside [low, high], 3,377 zero-volume bars, 0 duplicate dates,
  0 gaps > 5 business days. Worst symbols: SW (1,395), FERG (1,042), AMCR (909).
  13 artifact trades touch a flagged bar (listed in the report).
- **(d) Exit mix** — strategy win rates 0.477 / 0.472 / 0.475 / 0.478 vs matched-random
  0.479 / 0.474 / 0.474 / 0.490.

### Outcome

- Tests: **pass** (3/3) — `window_trades` + `r_net_stats`, `interpolate_zero_crossing`,
  `integrity_flags`.
- Ruff: **clean** on both new files.
- Full run: **exit 0**, wrote the report.
- Skipped: `exit_mix` and the portfolio-level helpers (`analyze_seeds`, `analyze_costs`,
  `analyze_integrity`, `analyze_exit_mix`, `render_markdown`) have **no unit tests** — the
  task allowed only 2-3 tests and they went to the pure numeric helpers.
- Gate for T5: **open** (T0 and T1 both pass).

---

## T5 — Validity notes (docs only)

- **Date:** 2026-11-12
- **What changed and why:** added a factual comparison of the four research setups against
  their deployed YAML counterparts, plus notes on naming, control design, the provenance of the
  `74.3% WR, 5.92 PF` claim and the known simplifications. No code, YAML or artifact was
  touched; this task exists so the gap between the research harness and the live screens is
  written down next to the numbers that the baseline report publishes.
- **Files touched:**
  - `docs/backtests/research/VALIDITY_NOTES.md` (new)
  - `docs/backtests/research/README.md` (one pointer line only)
  - `docs/SESSIONS/research-harden-d82-1og.md` (this file)

### Commands and exact output

Provenance lookup for the `74.3% WR, 5.92 PF` comment at `config/regime_screens.yaml:29`:

```text
$ git log -S"74.3% WR, 5.92 PF" --oneline -- config/regime_screens.yaml
a8d7983 fix: Ticker analysis data accuracy fixes (D-65)

$ git log -S"74.3 | 5.92" --oneline -- docs/DECISIONS/D-61-elite-template-deployment.md
a8d7983 fix: Ticker analysis data accuracy fixes (D-65)

$ Select-String -Path config/regime_screens.yaml -Pattern '74\.3'
29: - { name: 52week-breakout, weight: 95 }        # 74.3% WR, 5.92 PF

$ Select-String -Path docs/DECISIONS/D-61-elite-template-deployment.md -Pattern '74\.3'
43: | **52week-breakout** | 74.3% | 5.92 | 0.51 | 10/10 | 55.9 |

$ Select-String -Path docs/backtests/VALIDATION_REPORT.md -Pattern '52week|52-week'
53: | *52week-breakout* | ? | 30 | 53.3% | 1.57 | +0.193 | +1.22 | -0.98 | 7.1 |
71: **Deployed but thin:** 52week-breakout carries the top weight in `strong_trend`
    (95) and `neutral` (95) on only 30 trades (PF 1.57).
```

Confirmed the price-adjustment simplification the task named:

```text
$ Select-String -Path backend/app/research/data.py -Pattern "auto_adjust|yf.download"
backend\app\research\data.py:204:                df = yf.download(
backend\app\research\data.py:208:                    auto_adjust=True,
```

The D-61 run file named in its method section exists:

```text
$ Test-Path backtest_results_20260926_060935.json
True
```

No tests or ruff were run for T5 because it changes no Python. `docs/backtests/research/README.md`
received exactly one added line (the `VALIDITY_NOTES.md` pointer).

### Findings recorded (summary)

- Liquidity gates differ for every setup: the research harness uses `close >= 10` and
  `adv_usd20 >= 20,000,000`; the deployed YAMLs use `close_above 5.0` plus volume / market-cap
  rules, and `low-vol-setup.yaml` has no liquidity gate at all.
- Only `low_vol_setup` matches its YAML rule-for-rule on technicals. The other three differ by
  fundamentals, VWAP, 4h timeframes, OBV or `close > sma20`.
- `breakout_52week` has no 52-week-high condition in **either** the research setup or the
  deployed YAML.
- `volume_trend_accumulation` has no accumulation measure in research; `obv_rising` exists only
  in the deployed YAML.
- The 74.3% / 5.92 pair comes from D-61 (`docs/DECISIONS/D-61-elite-template-deployment.md:43`,
  commit `a8d7983`), is marked SUPERSEDED there and CAVEATed in the regime file, and is not
  reproducible under the current harness (D-82 baseline: 47.2% WR, PF 0.98).

### Outcome

- Tests: not applicable (docs only).
- Ruff: not applicable (docs only).
- Skipped: nothing. No file was renamed; the proposed names are stated in the note only.
- Gate for T2: **open** (T0, T1, T5 all complete).

---

## T2 — Entry/exit ordering and indicator warm-up

- **Date:** 2026-11-12
- **What changed and why:** four behavioural fixes.
  1. `engine.PortfolioRules` gains `allow_same_day_recycling` (default **False**). Entry
     prices are today's open and exits happen during the day, so a slot or the cash
     released by an exit on date D must not fund entries on date D. The default now
     collects exits before the entry step (they still happen at the right price/date, and
     close the position) but applies them **after** sizing and opening today's entries.
     `--allow-same-day-recycling` restores the old ordering for side-by-side comparison.
  2. `indicators.py` masks every recursive indicator for its warm-up via `min_periods`,
     instead of emitting values that are built from one or two bars. ADX and the MACD
     signal are computed from the **unmasked** recursions and only then hidden, so no
     later value moves.
  3. `setups.eligible()` now requires `ema200` and `atr14` (previously any non-NaN value
     of the unmasked EMA/ATR series qualified), so the control universe no longer includes
     bars before the 200-bar warm-up.
  4. `run_research_baseline.py` exposes `--allow-same-day-recycling` and records the flag
     in the artifact `rules` block.
- **Files touched:**
  - `backend/app/research/engine.py`
  - `backend/app/research/indicators.py`
  - `backend/app/research/setups.py`
  - `scripts/run_research_baseline.py`
  - `backend/tests/test_research_engine.py`
  - `backend/tests/test_research_indicators.py`
  - `backend/tests/test_research_setups.py`
  - `docs/SESSIONS/research-harden-d82-1og.md` (this file)

### Commands and exact output

Full research test set at the **start** of T2:

```text
$ pytest backend/tests/test_research_data.py backend/tests/test_research_engine.py backend/tests/test_research_metrics.py backend/tests/test_research_setups.py backend/tests/test_research_indicators.py backend/tests/test_research_control.py backend/tests/test_research_diagnostics.py -q
.............................................................                    [100%]
61 passed in 4.78s
LASTEXIT=0
```

Tests after the code changes (before the new tests were added), which showed the
warm-up-related expectations that had to be updated:

```text
$ pytest backend/tests/test_research_engine.py backend/tests/test_research_setups.py -q
... E assert elig.iloc[60:].all() ... FAILED backend/tests/test_research_setups.py::test_eligible
1 failed, 26 passed
```

The old `test_eligible` assumed eligibility from bar 60, which was only possible because
`ema200` had no warm-up. It was **strengthened**, not weakened: `n` 100 -> 260, and it now
asserts no eligible bar before 199 and every bar from 199 onward eligible. Similarly the
three existing engine tests that entered trades at bars 2-10 were moved after the 14-bar
ATR warm-up (otherwise the engine skips them for `atr = NaN`); their assertions are
unchanged or stricter.

New tests added:

- `test_same_day_exit_does_not_free_a_slot_by_default` — 8 slots full, one stops on
  bar 4, a 9th candidate would enter on bar 4: default mode never enters the 9th;
  recycling mode enters it on bar 4. Also asserts the stop's date and reason.
- `test_position_and_cash_bounds_hold[False/True]` — over a random panel, reconstructed
  cash never goes negative (entry cash is debited before today's deferred exits are
  credited in default mode) and the held count never exceeds `max_positions`.
- `test_reconciliation_holds_in_both_modes[False/True]` — `final_equity == start_equity +
  sum(pnl_usd)` in both orderings.
- `test_warmup_is_masked_without_shifting_later_values` — `ema20/50/200`, `sma20`, `atr14`
  and `macd_signal` are NaN for exactly their warm-up and match the unmasked recursion
  from the first observable bar onward.

End-of-task run (full research set) and ruff:

```text
$ ruff check backend/app/research/engine.py backend/app/research/indicators.py backend/app/research/setups.py scripts/run_research_baseline.py backend/tests/test_research_engine.py backend/tests/test_research_indicators.py backend/tests/test_research_setups.py
All checks passed!
RUFF_EXIT=0

$ pytest backend/tests/test_research_data.py backend/tests/test_research_engine.py backend/tests/test_research_metrics.py backend/tests/test_research_setups.py backend/tests/test_research_indicators.py backend/tests/test_research_control.py backend/tests/test_research_diagnostics.py -q
...................................................................               [100%]
67 passed in 5.02s
LASTEXIT=0
```

(The end count is 67, not 61, because T2 adds six test functions — three of them
parametrised twice.)

### Outcome

- Tests: **pass** — 61 at start, 67 at end; no test deleted or weakened.
- Ruff: **clean**.
- Skipped: no baseline re-run (forbidden before T4). Therefore the numbers in the committed
  `docs/backtests/research/DIAGNOSTICS.md` and `BASELINE_REPORT.md` are **stale as of this
  commit**: they were produced before the same-day-recycling and warm-up fixes. They are
  regenerated in T4, after T3's metric changes, so the reports and the code agree at the end
  of the sequence.
- Gate for T3: **open** (T2 passes).

---

## T3 — Metrics and report correctness

- **Date:** 2026-11-13
- **What changed and why:** five correctness fixes so the real strategy and every control
  are measured the same way and the headline ratios mean what their names say.
  1. `control.compute_control_pvalues` now defaults to `metric_name="r_net_mean"` (it was
     `r_net_sum`, which the report never used as its headline test).
  2. One evaluation window. `metrics.trades_in_window(trades, since)` returns uncensored
     trades with `exit_date >= since`. `run_research_baseline.py` sets
     `EVAL_START = "2016-01-01"`, computes the real metrics on
     `trades_in_window(trades, EVAL_START)`, passes `eval_start` through
     `run_controls` -> `run_control_suite` (which applies the same filter to all four
     control families), and records `run_info["eval_start"]`. Equity-based statistics stay
     on the full curve. The reconciliation invariant is now computed from **all** trades
     (`sum(t.pnl_usd)`), so windowing trade statistics cannot mask a cash break.
  3. Sharpe/Sortino are computed from daily equity returns
     (`equity.pct_change().dropna()`, `std(ddof=1)`, annualised by `sqrt(252)`), replacing
     the per-trade `r_net_mean / r_net_std * sqrt(252)` version, which is not a Sharpe
     ratio. Sortino uses the root-mean-square of negative daily returns as downside
     deviation.
  4. CAGR uses elapsed calendar years (`(last - first).days / 365.25`) in both
     `metrics.py` and `make_baseline_report.account_stats`, instead of `len(curve)/252`.
  5. The report adds a month-block bootstrap CI (resamples exit year-months with
     replacement, 2000 resamples, seed 42, stdlib `random`). The main table shows
     `95% CI (iid)` and `95% CI (block)`; the verdict rule now requires the **block**
     lower bound > 0. A drawdown breach alone is relabelled
     `REVIEW drawdown guard breached (not necessarily a bug)`; `SUSPECTED BUG` is kept for
     reconciliation failure, PF > 2.5 and win rate > 65%. Sanity checks gain
     `random-path drawdown scale: sqrt(n) * sd(R) * risk_pct`. Deviations record both the
     post-D-81 verdict-rule change and the calendar-year CAGR.
- **Files touched:**
  - `backend/app/research/metrics.py`
  - `backend/app/research/control.py`
  - `scripts/run_research_baseline.py`
  - `scripts/make_baseline_report.py`
  - `backend/tests/test_research_metrics.py`
  - `backend/tests/test_make_baseline_report.py` (new; the task wrote
    `test_researcts/test_make_baseline_report.py`, read as this path)
  - `docs/SESSIONS/research-harden-d82-1og.md` (this file)
- **Test changes:** `test_cagr_calculation` previously built 504 **daily** bars and
  asserted 9.54% by treating `504/252` as two years. Under the required calendar-year
  formula that series spans 1.38 years, so the fixture was changed to
  `2020-01-01 .. 2022-01-01` (same 20% return, same 9.54% +/- 0.5 assertion). No assertion
  was loosened and no test was removed; the new semantics are additionally pinned by
  `test_cagr_uses_calendar_years_not_bar_count`. Nothing else in an existing test changed.

### Commands and exact output

Full research test set at the **start** of T3 (clean tree, before the edits):

```text
$ pytest backend/tests/test_research_control.py backend/tests/test_research_data.py backend/tests/test_research_diagnostics.py backend/tests/test_research_engine.py backend/tests/test_research_indicators.py backend/tests/test_research_metrics.py backend/tests/test_research_setups.py -q
...................................................................               [100%]
67 passed in 6.11s
LASTEXIT=0
```

New/extended tests:

```text
$ pytest backend/tests/test_research_metrics.py backend/tests/test_make_baseline_report.py -q
..........................                                                                                                                                                                                [100%]
26 passed in 0.97s
LASTEXIT=0
```

End-of-task full set plus the new report test file:

```text
$ pytest backend/tests/test_research_control.py backend/tests/test_research_data.py backend/tests/test_research_diagnostics.py backend/tests/test_research_engine.py backend/tests/test_research_indicators.py backend/tests/test_research_metrics.py backend/tests/test_research_setups.py backend/tests/test_make_baseline_report.py -q
..................................................................................                                                                                                                        [100%]
82 passed in 5.86s
LASTEXIT=0
```

Ruff on every touched file:

```text
$ ruff check backend/app/research scripts/run_research_baseline.py scripts/make_baseline_report.py backend/tests/test_research_control.py backend/tests/test_research_data.py backend/tests/test_research_diagnostics.py backend/tests/test_research_engine.py backend/tests/test_research_indicators.py backend/tests/test_research_metrics.py backend/tests/test_research_setups.py backend/tests/test_make_baseline_report.py
All checks passed!
LASTEXIT=0
```

CLI/import smoke checks and a report build into the **ignored** quick cache (the committed
`docs/backtests/research/BASELINE_REPORT.md` is deliberately left untouched until T4):

```text
$ python scripts/run_research_baseline.py --help
HELP_EXIT=0

$ python -c "import scripts.run_research_baseline, scripts.make_baseline_report; print('imports OK')"
imports OK
IMPORT_EXIT=0

$ python scripts/make_baseline_report.py --dir .cache/research_quick/out
Wrote .cache/research_quick/out\BASELINE_REPORT.md (1 setups)
REPORT_EXIT=0

$ Select-String -Path .cache/research_quick/out/BASELINE_REPORT.md -Pattern "95% CI|random-path"
| Setup | n | Win rate | Avg win R | Avg loss R | Expectancy net | 95% CI (iid) | 95% CI (block) | Expectancy gross | PF | CAGR | Max DD | Reconciliation |
- random-path drawdown scale: 5.3%
```

### Outcome

- Tests: **pass** — 67 at start, 82 at end (26 in the two metrics/report files).
- Ruff: **clean**.
- Baseline re-run: **not done** (forbidden before T4). `DIAGNOSTICS.md` and
  `BASELINE_REPORT.md` in the repo are still the pre-T2/T3 numbers until T4.
- Skipped: nothing else.
- Gate for T4: **open** (T0, T1, T5, T2, T3 all complete).

---

## T4 — Re-run the baseline under the fixed harness

- **Date:** 2026-11-13
- **Precondition:** clean tree at `7ed0135` (T2 `bd93d02` and T3 `7ed0135` both committed).
  The artifacts therefore record `run.code.dirty = false` and `run.code.revision = 7ed0135`.
- **What changed and why:** nothing in code. This is the first baseline produced by the
  D-82 engine (no same-day recycling, masked warm-up) and the D-82 metrics (one evaluation
  window, daily-equity Sharpe, calendar-year CAGR, month-block CI). Runs use the defaults
  2015-01-01 -> today, 30 matched / 0 random / 10 permuted / 2 shifted and reuse
  `.cache/research`.
- **Files touched (new/changed):**
  - `docs/backtests/research/statistical_mean_reversion_20261113_093317.json` (new)
  - `docs/backtests/research/breakout_52week_20261113_093833.json` (new)
  - `docs/backtests/research/low_vol_setup_20261113_094423.json` (new)
  - `docs/backtests/research/volume_trend_accumulation_20261113_095014.json` (new)
  - `docs/backtests/research/BASELINE_REPORT.md` (regenerated)
  - `docs/SESSIONS/research-harden-d82-1og.md` (this file)
- **Panel / cache:** requested `2015-01-01..2026-11-13`; actual `2015-01-02..2026-11-12`;
  501 tradable symbols; `early_end=0`, `late_start=37`; 2 dropped (`KVUE`: 1 row,
  `VYLR`: 31 rows). The first run downloaded 503 and failed 2; the next three were served
  from cache (`cache hits=503, downloads=0, failed=2`). Universe SHA-256 begins
  `a53242f23d15d485`.

### Commands and exact output

```text
$ python scripts/run_research_baseline.py --setup statistical_mean_reversion
...
  permuted      : p = 0.2727
  shifted       : p = 0.6667
Results saved to: docs/backtests/research\statistical_mean_reversion_20261113_093317.json

============================================================
BACKTEST COMPLETE
============================================================
INFO: NOT statistically significant vs controls (best p=0.2727 on permuted)
EXIT=0

$ python scripts/run_research_baseline.py --setup breakout_52week
...
  permuted      : p = 0.9091
  shifted       : p = 0.3333
Results saved to: docs/backtests/research\breakout_52week_20261113_093833.json

============================================================
BACKTEST COMPLETE
============================================================
INFO: NOT statistically significant vs controls (best p=0.3333 on shifted)
EXIT=0

$ python scripts/run_research_baseline.py --setup low_vol_setup
...
  permuted      : p = 0.7273
  shifted       : p = 0.6667
Results saved to: docs/backtests/research\low_vol_setup_20261113_094423.json

============================================================
BACKTEST COMPLETE
============================================================
INFO: NOT statistically significant vs controls (best p=0.3871 on matched_random)
EXIT=0

$ python scripts/run_research_baseline.py --setup volume_trend_accumulation
...
  permuted      : p = 0.9091
  shifted       : p = 0.6667
Results saved to: docs/backtests/research\volume_trend_accumulation_20261113_095014.json

============================================================
BACKTEST COMPLETE
============================================================
INFO: NOT statistically significant vs controls (best p=1.0000 on matched_random)
EXIT=0

$ python scripts/make_baseline_report.py
Wrote docs/backtests/research\BASELINE_REPORT.md (4 setups)
REPORT_EXIT=0
```

Every run printed `Reconciliation: OK`:

```text
statistical_mean_reversion: Completed 1843 trades; Reconciliation: OK
breakout_52week:            Completed 1714 trades; Reconciliation: OK
low_vol_setup:              Completed 1873 trades; Reconciliation: OK
volume_trend_accumulation:  Completed 2277 trades; Reconciliation: OK
```

### Verbatim from `BASELINE_REPORT.md`

Main table:

| Setup | n | Win rate | Avg win R | Avg loss R | Expectancy net | 95% CI (iid) | 95% CI (block) | Expectancy gross | PF | CAGR | Max DD | Reconciliation |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| breakout_52week | 1684 | 48.6% | 1.084 | -0.959 | 0.033 | [-0.022, 0.087] | [-0.044, 0.112] | 0.106 | 1.07 | 1.5% | -21.1% | PASS |
| low_vol_setup | 1746 | 48.4% | 1.121 | -0.998 | 0.028 | [-0.027, 0.084] | [-0.061, 0.120] | 0.119 | 1.05 | 1.6% | -31.6% | PASS |
| statistical_mean_reversion | 1680 | 50.1% | 1.015 | -0.920 | 0.049 | [-0.003, 0.099] | [-0.027, 0.130] | 0.111 | 1.11 | 2.4% | -23.4% | PASS |
| volume_trend_accumulation | 2120 | 47.0% | 1.088 | -0.973 | -0.004 | [-0.053, 0.044] | [-0.076, 0.069] | 0.068 | 0.99 | -0.6% | -35.6% | PASS |

Control comparison:

| Setup | Control runs | Control trades (mean) | Control expectancy (mean +/- std) | Strategy expectancy | p (matched_random) |
|---|---|---|---|---|---|
| breakout_52week | 30 | 1667.7 | 0.045 +/- 0.028 | 0.033 | 0.6452 |
| low_vol_setup | 30 | 1783.2 | 0.022 +/- 0.022 | 0.028 | 0.3871 |
| statistical_mean_reversion | 30 | 1870.1 | 0.035 +/- 0.023 | 0.049 | 0.2903 |
| volume_trend_accumulation | 30 | 2042.1 | 0.049 +/- 0.021 | -0.004 | 1.0000 |

Mechanical verdicts:

- **breakout_52week**: NO EVIDENCE OF EDGE
- **low_vol_setup**: NO EVIDENCE OF EDGE
- **statistical_mean_reversion**: NO EVIDENCE OF EDGE
- **volume_trend_accumulation**: NO EVIDENCE OF EDGE

Artifact p-value sets (`matched_random` / `permuted` / `shifted`): 0.6452 / 1.0000 /
0.3333 (breakout), 0.3871 / 0.8182 / 0.6667 (low_vol), 0.2903 / 0.2727 / 1.0000 (SMR),
1.0000 / 1.0000 / 1.0000 (volume).

### Outcome

- All four runs: **exit 0**, `Reconciliation: OK`, `invariant.holds = true`,
  `code.dirty = false`.
- Report: regenerated from the four new artifacts; `PASS` reconciliation in all four.
- No drawdown breach this run: worst max DD is -35.6% (volume), so the relabelled
  `REVIEW` path is not exercised by these artifacts.
- Skipped: none. No tests/ruff were needed for this task (no code change); T0-T3 already
  record this tree's test and lint results.
- Gate for T6: **open** (T0, T1, T5, T2, T3, T4 complete).

---

## T6(a) — Controls apply eligibility; dead branch removed

- **Date:** 2026-11-13
- **What changed and why:** `permuted_signals` and `time_shifted_signals` now place
  signals only on dates where `eligible(df)` is true, the same gate the real strategy and
  the matched-random control use. Before this, permutation sampled from `df.index[30:]`
  and shifting kept any in-range destination, so a control could trade a pre-warm-up bar
  (where every setup indicator is NaN) or an illiquid name - an opportunity the strategy
  never had. The `if len(available_dates) < len(signal_dates)` / `else` branch in
  `permuted_signals` was dead code (both arms were the same call) and is deleted; the
  single call now sizes with `min(...)` instead of raising in the rare short-pool case.
- **Impact check:** `gitnexus_impact` (upstream) for both functions: risk **LOW**,
  1 direct caller (`run_control_suite`) -> `run_controls` -> `main`; signatures unchanged.
- **Files touched:**
  - `backend/app/research/control.py`
  - `backend/tests/test_research_control.py`
  - `docs/SESSIONS/research-harden-d82-1og.md` (this file)
- **New tests:**
  - `test_permuted_signals_only_fire_on_eligible_dates` — real signals placed on
    pre-warm-up bars are re-homed onto eligible dates; no permuted signal lands on an
    ineligible bar; the count is preserved.
  - `test_time_shifted_signals_drop_ineligible_destinations` — shifting bar 10 by +20
    lands at bar 30 (pre-warm-up) and is dropped; shifting bar 200 by +20 lands at 220 and
    is kept.

### Commands and exact output

```text
$ pytest backend/tests/test_research_control.py -q
.......                                                                                                                                                                                                   [100%]
7 passed in 1.60s
PYTEST_EXIT=0

$ ruff check backend/app/research/control.py backend/tests/test_research_control.py
All checks passed!
RUFF_EXIT=0

$ pytest backend/tests/test_research_control.py backend/tests/test_research_data.py backend/tests/test_research_diagnostics.py backend/tests/test_research_engine.py backend/tests/test_research_indicators.py backend/tests/test_research_metrics.py backend/tests/test_research_setups.py backend/tests/test_make_baseline_report.py -q
....................................................................................                                                                                                                      [100%]
84 passed in 6.44s
LASTEXIT=0
```

### Outcome

- Tests: **pass** (7 in the control module, 84 across the research set + report tests).
- Ruff: **clean**.
- Baseline re-run: **not done** (forbidden in T6). The committed v3 artifacts were produced
  before this control-eligibility change, so their control p-values do not include it.
- Skipped: nothing.

---

## T6(b) — Refuse to run on a dirty working tree

- **Date:** 2026-11-13
- **What changed and why:** a run started on a dirty tree writes
  `run.code.dirty = true` and a HEAD that does not contain the code that produced it,
  which makes the artifact unreproducible. `main()` now calls `_require_clean_tree()`
  immediately after argument parsing and exits with a message before any download,
  signal generation or file write. `--allow-dirty` accepts a dirty run explicitly.
  Unknown git state (git unavailable, e.g. a source tarball) does not block.
- **Files touched:**
  - `scripts/run_research_baseline.py`
  - `backend/tests/test_research_runner.py` (new)
  - `docs/SESSIONS/research-harden-d82-1og.md` (this file)
- **Tests:** `_require_clean_tree` dirty/clean/allow/unknown, plus an end-to-end
  `main()` test that patches `_git_state` and asserts `SystemExit` before any work.

### Commands and exact output

```text
$ pytest backend/tests/test_research_runner.py -q
.....                                                                                                                                                                                                     [100%]
5 passed in 1.20s
PYTEST_EXIT=0

$ ruff check scripts/run_research_baseline.py backend/tests/test_research_runner.py
All checks passed!
RUFF_EXIT=0
```

End-to-end refusal on the actually-dirty tree of this task:

```text
$ python scripts/run_research_baseline.py --setup low_vol_setup
Working tree is dirty (HEAD 1fcac93). Commit or stash your changes, or pass --allow-dirty to record code.dirty = true in the artifact.
DIRTY_RUN_EXIT=1
```

Full research set plus the report tests:

```text
$ pytest backend/tests/test_research_control.py backend/tests/test_research_data.py backend/tests/test_research_diagnostics.py backend/tests/test_research_engine.py backend/tests/test_research_indicators.py backend/tests/test_research_metrics.py backend/tests/test_research_runner.py backend/tests/test_research_setups.py backend/tests/test_make_baseline_report.py -q
.........................................................................................                                                                                                                 [100%]
89 passed in 5.34s
LASTEXIT=0

$ python scripts/run_research_baseline.py --help
HELP_EXIT=0
```

### Outcome

- Tests: **pass** (5 in the runner module, 89 across the set).
- Ruff: **clean**.
- Baseline re-run: **not done** (forbidden in T6).
- Skipped: nothing.
