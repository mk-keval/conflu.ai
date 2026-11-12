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
