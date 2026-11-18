# Pre-registration — research harness experiment

**Purpose:** freeze the question, metric, design and pass/fail rule **before** a research
run so a post-hoc result cannot be presented as a pre-declared test (D-83/H-12 and
D-84/H-13/H-14 were run without one and are labelled EXPLORATORY for that reason).

**How to use:** copy this file to
`docs/backtests/research/PREREGISTRATION-<H-ID>-v<n>.md`, fill every field, and commit
it *before* the first full run. Write `not recorded` for any field that does not apply.
Once frozen, no field may change without an entry in section 8; a changed pass/fail
criterion makes the result EXPLORATORY, not confirmatory. The research harness is
always EXPLORATORY — this template makes the rule explicit, it does not turn a
research backtest into forward evidence.

---

## 1. Identity

| Field | Value |
|---|---|
| Hypothesis ID (H-nn) | `H-16` |
| Task / experiment ID | `E8` |
| Title | Time-reversed check: does `breakout_52week` show positive vol-matched excess at h=60 on 2006-2015? |
| Date written (before run) | `2026-11-18` |
| Author | Keval Makwana |
| Evidence label | `EXPLORATORY` (research harness) |
| Status | `run` |
| Decision ADR / linked decision | `D-86` (to be written in E10) |

## 2. Question and metric

| Field | Value |
|---|---|
| Research question (one sentence) | Does `breakout_52week` have mean excess return at horizon 60 versus the volatility-bucket benchmark that is greater than 0 on entries 2006-01-01..2015-12-31, a window not used by E1/E2/E4? |
| Single primary metric | mean bucket excess at h=60 in bp |
| Direction tested | `higher` |
| Secondary metrics | reported, **NO pass/fail**: the same metric for `breakout_52week` at h=1, 5, 10, 20; all four setups at all five horizons; per-calendar-year means for `breakout_52week` at h=10, 20, 60; sanity draws |
| What result would change a live decision? | `none — exploratory only` |
| What is explicitly out of scope? | exits, costs, portfolio, any new setup, any other window, any re-run with changed parameters |

## 3. Data and scope

| Field | Value |
|---|---|
| Loader | `download_daily` on `.cache/research`, then `add_indicators` |
| Requested span | `2005-01-01 -> 2015-12-31` |
| Actual panel | `2005-01-03 -> 2015-12-31` |
| Universe | `config/replay_universe_sp500.txt` current snapshot (survivorship-biased, and **more biased the further back the window goes**) |
| Exclusions | `NON_TRADABLE` |
| Signal source | `SETUPS["breakout_52week"](df)` at the close of day `t` (other setups descriptive only) |
| Eligibility | `events.eligibility_frame` at the signal bar (`close >= 10`, `adv_usd20 >= 20M`, evaluated on dividend-adjusted prices, which is stricter in older years) |
| Evaluation / entry start | `2006-01-01` (2005 is indicator warm-up) |
| Panel-end rule | forward rows without the future close are dropped, as `events.py` does; no data after `2015-12-31` is loaded |
| Symbols tradable / dropped | `461 / 42` |
| Code revision / dirty flag | `1cc53df / false` |

## 4. Design

| Field | Value |
|---|---|
| Setups | `breakout_52week` (primary); `statistical_mean_reversion`, `low_vol_setup`, `volume_trend_accumulation` descriptive only |
| Horizons / variants | `1, 5, 10, 20, 60` |
| Cell count | 1 primary cell (`breakout_52week` h=60) plus 19 descriptive cells |
| Entry rule | `signal at t, entry at open of t+1, ATR14 of the signal bar, skip NaN/<=0` |
| Exit rule | `none — forward return only, no stops or targets` |
| 1R definition | `not applicable — event study in percent units` |
| Costs | `none — raw forward return` |
| Sizing / position limit | `none — measurement only, no portfolio` |
| Capacity / slot competition | `ignored` |
| Cooldown / dedupe | `5` bars |
| Strategy seeds | `none` |
| Null / control family | `sanity only: vol_matched_random_signals (no significance null)` |
| Null draws and seeds | `20 vol-matched random event sets per setup, seeds 90000..90019` |
| Bootstrap resamples and seed | `2000 resamples, seed 42` |
| Benchmark | `volatility-bucket benchmark via matched_control.vol_bucket_frame / bucket_benchmark / bucket_excess_frame` |

## 5. Pass/fail criteria (fixed before the run)

State one primary rule. Do not add or change a criterion after seeing the result.

| Field | Value |
|---|---|
| Primary threshold | bucket excess at h=60 `> 0` bp |
| Direction | `higher` |
| Significance rule | 95% month-block CI lower bound `> 0` AND `block_t >= z_crit(1) = 1.96` (use `matched_control.cell_passes` with `z = z_crit(1)`) |
| p-value | `not used — no p_high / p_low; the spread of one control run is descriptive, not a test` |
| CI rule | 95% month-block bootstrap lower bound `> 0` |
| Multiple-comparison handling | `m = 1`: exactly one cell is tested on this data; the 80 earlier exploratory cells explain why the hypothesis was chosen, they are not tests on this window |
| R and percent | `not applicable — event study, percent units only` |
| Pass action | record as a hypothesis only; no live change; next step would be point-in-time membership data and a forward sample |
| Fail action | record and stop; do **not** re-run with another horizon, bucket count, cooldown, window or setup |
| Amendment rule | any post-run change here invalidates the confirmatory label |

## 6. Outputs and evidence

| Field | Value |
|---|---|
| Script | `scripts/research_window_study.py` |
| Flags | defaults only: `--start 2005-01-01 --end 2015-12-31 --eval-start 2006-01-01` |
| Report path | `docs/backtests/research/WINDOW_STUDY_H16.md` |
| JSON path | `docs/backtests/research/event_study/window_study_<timestamp>.json` |
| Unit-test command | `python -m pytest -q backend/tests/test_research_window_study.py` plus the explicit CI list |
| Lint command | the exact CI ruff scope, including `scripts/research_window_study.py` |
| Commit hash of the frozen pre-registration | recorded in the E7 work-log entry, **not** in this file |
| Commit hash(es) of the run | `1cc53df` (code) / `2f9a1f5` (results) |

## 7. Limits to restate with any result

- In-sample, survivorship-biased universe; no walk-forward.
- The universe is today's S&P 500 snapshot; the bias is larger for 2006-2015 than for
  later windows, and there is **no point-in-time membership; results cannot rule out
  survivorship**.
- The liquidity gate is evaluated on dividend-adjusted prices, which is stricter in
  older years.
- Exploratory: never the scorecard, D-75 pass bar, kill rule or any forward verdict.
- Capacity and slot competition are ignored.
- The descriptive cells share signals and are not independent trials.
- The bucket benchmark is a same-date eligibility mean, not sector- or size-matched.

## 8. Amendment log

| Date | Field | Old value | New value | Reason | Effect on label |
|---|---|---|---|---|---|
| `not recorded` | `none` | `none` | `none` | no amendment before the run | `still EXPLORATORY` |
| 2026-11-18 | run-filled fields only (`Status`, `Actual panel`, `Symbols tradable / dropped`, `Code revision / dirty flag`, `Commit hash(es) of the run`) | `frozen` / the five run-filled fields were unfilled | `run` / `2005-01-03 -> 2015-12-31` / `461 / 42` / `1cc53df / false` / `1cc53df` (code) + `2f9a1f5` (results) | post-run fill, no criterion changed | `still EXPLORATORY` |

---

Reference: [D-84](../../DECISIONS/D-84-research-signal-information-and-exit-shape.md),
[D-85](../../DECISIONS/D-85-research-vol-matched-remeasurement.md),
[H-13 / H-14 / H-15 and the trial ledger](../HYPOTHESIS_LOG.md),
[EVENT_STUDY.md](EVENT_STUDY.md), [EXIT_STUDY.md](EXIT_STUDY.md),
[VOL_MATCHED_STUDY.md](VOL_MATCHED_STUDY.md).
