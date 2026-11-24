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
| Hypothesis ID (H-nn) | `H-17` |
| Task / experiment ID | `F3` |
| Title | ETF momentum plus trend filter: does it meet a drawdown bar (Tier A) or a return bar (Tier B) against SPY buy-and-hold on a 2016-onward holdout? |
| Date written (before run) | `2026-11-24` |
| Author | Keval Makwana |
| Evidence label | `EXPLORATORY` (research harness) |
| Status | `frozen` |
| Decision ADR / linked decision | `D-87` (to be written in F6) |

## 2. Question and metric

| Field | Value |
|---|---|
| Research question (one sentence) | On a 2016-onward holdout, does one pre-registered ETF momentum+trend strategy meet a drawdown bar (Tier A) or a return bar (Tier B) against SPY buy-and-hold? |
| Single primary metric | Tier A and Tier B flags on the holdout (Tier A: `abs(MaxDD_strategy) < 0.6 * abs(MaxDD_SPY)` AND `Sharpe_strategy >= Sharpe_SPY`; Tier B: `CAGR_strategy > CAGR_SPY`), both evaluated net of `cost_bps=10`. |
| Direction tested | `Tier A: lower drawdown ratio and higher/equal Sharpe; Tier B: higher CAGR` |
| Secondary metrics | Descriptive only (not pass criteria): 95% month-block bootstrap CI (2000 resamples, seed 17000, whole calendar months of paired daily returns resampled with replacement) for `Sharpe_strategy - Sharpe_SPY`, `CAGR_strategy - CAGR_SPY`, and `abs(MaxDD_strategy)/abs(MaxDD_SPY)`; if a CI includes zero (or 1 for the ratio) the report must say the bar was met on point estimates and that the difference is not statistically distinguishable. |
| What result would change a live decision? | `none — exploratory only; record as hypothesis only; next step would be a forward paper test` |
| What is explicitly out of scope? | any other universe, parameters, filters, windows or costs for the pass rule; individual stocks; options; shorting; leverage; taxes |

## 3. Data and scope

| Field | Value |
|---|---|
| Loader | Frozen snapshot files in `research_data/etf_20261124/`; no re-download is allowed for the run |
| Requested span | `2003-01-01 -> 2026-11-24` (snapshot request; see manifest) |
| Actual panel | `2003-01-02 -> 2026-11-23` (from ETF_DATA_QUALITY.md symbol table; SPY calendar) |
| Universe | 20 frozen ETFs: `SPY QQQ IWM EFA EEM XLB XLE XLF XLI XLK XLP XLU XLV XLY TLT IEF LQD GLD VNQ SHY` |
| Exclusions | `none beyond frozen universe; assets not eligible at signal date are not selected` |
| Signal source | Frozen strategy rules below at signal date `s` = last trading day of each calendar month in SPY's calendar |
| Eligibility | An asset is eligible at `s` only if it has at least 253 bars of Adj Close up to and including `s` |
| Evaluation / entry start | Development `2005-01-01..2015-12-31` (reported only, nothing is chosen or tuned on it); holdout `2016-01-01..latest snapshot date` (primary) |
| Panel-end rule | Use data available in frozen snapshot through latest snapshot date; no re-download |
| Symbols tradable / dropped | `not recorded` (filled after run if needed; frozen universe has 20 symbols) |
| Code revision / dirty flag | `<recorded from the run artifact>` |

**Data integrity:** snapshot `research_data/etf_20261124/`, manifest sha256 `c0bb469785aa64679f3b8f48e17f7ee42584d2d049a88b1a6b2b316f19aa9304` (copied from `docs/backtests/research/ETF_DATA_QUALITY.md`). Returns use Adj Close (total return). Calendar: SPY's dates. Risk-free rate 0 for Sharpe (same as the baseline). Portfolio starts at 1.0 in cash (SHY) and each window's equity and drawdown restart at 1.0 on its first day.

## 4. Design

| Field | Value |
|---|---|
| Setups | One pre-registered strategy (ETF momentum + trend filter), frozen below |
| Horizons / variants | `not recorded` (monthly rebalance strategy; descriptive comparators listed below) |
| Cell count | 1 primary strategy, 2 tier flags (Tier A, Tier B); 7 descriptive comparators, not counted as pass cells |
| Entry rule | Signal date `s` = last trading day of each calendar month in SPY's calendar. Execution at the close of the next trading day `s+1`. New weights earn returns from the close of `s+1` to the close of `s+2` onward. Before `s+1` the previous weights apply. |
| Exit rule | `not recorded` (weight-based monthly rebalance; no stop/target exits) |
| 1R definition | `not recorded` |
| Costs | Cost on execution day: `(cost_bps/10000) * sum over all assets incl. SHY of |w_target_i - w_drifted_i|`, subtracted from that day's portfolio return. Frozen primary `cost_bps = 10`. |
| Sizing / position limit | Each selected asset gets weight 1/5. Every unfilled slot (1/5 each) is held in SHY. Weights drift with returns between rebalances: `w_i <- w_i*(1+r_i)/(1+r_p)` each day. |
| Capacity / slot competition | `ignored` (ETF universe; no slot competition model) |
| Cooldown / dedupe | `not recorded` (monthly rebalance) |
| Strategy seeds | `none` |
| Null / control family | `none` (benchmark is SPY buy-and-hold; descriptive comparators only) |
| Null draws and seeds | `not recorded` |
| Bootstrap resamples and seed | `2000 resamples, seed 17000` (month-block bootstrap CI for descriptive differences) |
| Benchmark | SPY buy-and-hold on Adj Close, no costs |

**Frozen strategy (copy verbatim as the Design section):**
- Risk assets (19): SPY QQQ IWM EFA EEM XLB XLE XLF XLI XLK XLP XLU XLV XLY TLT IEF LQD GLD VNQ. Cash proxy: SHY (never ranked).
- Signal date s = the last trading day of each calendar month in SPY's calendar.
- An asset is eligible at s only if it has at least 253 bars of Adj Close up to and including s.
- Momentum m = AdjClose [s-21]/AdjClose [s-252]-1 (trading-day offsets within the asset's own series; the most recent 21 days are skipped).
- Trend pass: AdjClose [s] > mean of the last 200 Adj Close values through s.
- Selection: among eligible assets that pass the trend test, take the 5 with the highest m (ties broken alphabetically by symbol). Each selected asset gets weight 1/5. Every unfilled slot (1/5 each) is held in SHY.
- Execution: at the close of the next trading day s+1. The new weights earn returns from the close of s+1 to the close of s+2 onward. Before s+1 the previous weights apply.
- Weights drift with returns between rebalances: w_i <- w_i*(1+r_i)/(1+r_p) each day.
- Cost on execution day: (cost_bps/10000) * sum over all assets incl. SHY of |w_target_i - w_drifted_i|, subtracted from that day's portfolio return. Frozen primary cost_bps = 10.

**Metrics (computed on daily returns inside the window):** CAGR using elapsed calendar years; Sharpe = mean(daily r)/std(daily r, ddof=1)*sqrt(252); max drawdown from daily equity (a negative number); Calmar; annual turnover (sum of dw/ 2 per year); share of days in SHY.

**Descriptive comparators (same code, same windows, no pass/fail):** top 3; top 8; trend filter only (equal weight all trend-passing eligible assets, rest SHY); momentum top 5 with no trend filter; primary strategy at cost_bps 0 and 25; 60/40 SPY/IEF rebalanced monthly; equal weight of the 19 assets rebalanced monthly. Also report the primary strategy's per-calendar-year returns, and its drawdown in 2008, 2020 and 2022.

## 5. Pass/fail criteria (fixed before the run)

State one primary rule. Do not add or change a criterion after seeing the result.

| Field | Value |
|---|---|
| Primary threshold | Tier A is met only if BOTH: `abs(MaxDD_strategy) < 0.6 * abs(MaxDD_SPY)` AND `Sharpe_strategy >= Sharpe_SPY`. Tier B is met only if `CAGR_strategy > CAGR_SPY`. Both evaluated on the HOLDOUT, net of `cost_bps=10`. Report the four combinations: A only, B only, both, neither. |
| Direction | `Tier A: lower drawdown magnitude and >= Sharpe; Tier B: higher CAGR` |
| Significance rule | `not used as pass criteria` — report descriptively the 95% month-block bootstrap CI (2000 resamples, seed 17000, whole calendar months of paired daily returns resampled with replacement) for `Sharpe_strategy - Sharpe_SPY`, `CAGR_strategy - CAGR_SPY` and the ratio `abs(MaxDD_strategy)/abs(MaxDD_SPY)`. If a CI includes zero (or 1 for the ratio) the report must say the bar was met on point estimates and that the difference is not statistically distinguishable. |
| p-value | `not used` |
| CI rule | Descriptive only; see Significance rule. |
| Multiple-comparison handling | one primary strategy, two tier flags. Descriptive comparators below are not counted as pass cells. |
| R and percent | `not applicable` |
| Pass action | record as a hypothesis only; the next step would be a forward paper test. No live change. |
| Fail action | record and stop; no re-run with other parameters; any new variant needs a new H-id and a new pre-registration. |
| Amendment rule | any post-run change here invalidates the confirmatory label |

## 6. Outputs and evidence

| Field | Value |
|---|---|
| Script | `scripts/research_etf_trend.py` |
| Flags | defaults only: `--snapshot-dir research_data/etf_20261124 --report docs/backtests/research/ETF_TREND_STUDY_H17.md --json-dir docs/backtests/research/etf_trend` |
| Report path | `docs/backtests/research/ETF_TREND_STUDY_H17.md` |
| JSON path | `docs/backtests/research/etf_trend/` (run artifact JSON) |
| Unit-test command | `python -m pytest -q backend/tests/test_research_etf_trend.py` plus the exact CI list from `.github/workflows/research.yml` |
| Lint command | exact CI ruff scope from `.github/workflows/research.yml` (including `scripts/research_etf_trend.py` when created) |
| Commit hash of the frozen pre-registration | `<filled after the pre-registration commit, recorded in work log F3 second commit>` |
| Commit hash(es) of the run | `<filled after the run>` |

## 7. Limits to restate with any result

- the 19 ETFs were chosen in 2026 from survivors (ETF survivorship is mild but not zero); 2005-2015 includes 2008; one universe, one sample path, ~21 years; yfinance data; costs are a flat assumption; no taxes; in-sample for the strategy family (12-1 momentum and a 200-day trend filter are literature defaults, not fitted here, but the author has seen general market history); EXPLORATORY, never the scorecard, D-75 pass bar, kill rule or any forward verdict.
- In-sample, survivorship-biased universe; no walk-forward.
- Exploratory: never the scorecard, D-75 pass bar, kill rule or any forward verdict.
- If capacity/slot competition is ignored, say so in the result table.
- If cells share signals or entries, state that the cells are not independent trials.
- If the universe benchmark is a same-date eligibility mean, state that it is not sector- or size-matched.

## 8. Amendment log

| Date | Field | Old value | New value | Reason | Effect on label |
|---|---|---|---|---|---|
| `not recorded` | `none` | `none` | `none` | no amendment before the run | `still EXPLORATORY` |

---

Reference: [D-84](../../DECISIONS/D-84-research-signal-information-and-exit-shape.md),
[D-85](../../DECISIONS/D-85-research-vol-matched-remeasurement.md),
[D-86](../../DECISIONS/D-86-research-pre2016-check-and-survivorship-estimate.md),
[H-13 / H-14 / H-15 / H-16 and the trial ledger](../HYPOTHESIS_LOG.md),
[ETF_DATA_QUALITY.md](ETF_DATA_QUALITY.md).