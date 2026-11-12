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
