# Pre-registration template — research harness experiment

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
| Hypothesis ID (H-nn) | `<H-nn>` |
| Task / experiment ID | `<E-n>` |
| Title | `<one line>` |
| Date written (before run) | `<YYYY-MM-DD>` |
| Author | `<name>` |
| Evidence label | `EXPLORATORY` (research harness) / `MEASUREMENT` |
| Status | `draft` / `frozen` / `run` / `amended` |
| Decision ADR / linked decision | `<D-nn or not recorded>` |

## 2. Question and metric

| Field | Value |
|---|---|
| Research question (one sentence) | `<question>` |
| Single primary metric | `<metric name and units, e.g. mean excess in bp, mean r_net in R>` |
| Direction tested | `higher` / `lower` / `two-sided` |
| Secondary metrics | `<names and units, or not recorded>` |
| What result would change a live decision? | `none — exploratory only` or `<specific decision>` |
| What is explicitly out of scope? | `<list>` |

## 3. Data and scope

| Field | Value |
|---|---|
| Loader | `download_daily` on `.cache/research`, then `add_indicators` |
| Requested span | `<YYYY-MM-DD> -> <YYYY-MM-DD or latest>` |
| Actual panel | `<filled after run; before run write pending>` |
| Universe | current S&P 500 snapshot (survivorship-biased) / `<other>` |
| Exclusions | `NON_TRADABLE` |
| Signal source | `SETUPS[<name>](df)` at the close of day `t` |
| Eligibility | `eligible(df)` at the signal bar |
| Evaluation / entry start | `2016-01-01` (2015 is indicator warm-up) |
| Panel-end rule | `<drop paths past panel end / mark to market>` |
| Symbols tradable / dropped | `<filled after run; before run write pending>` |
| Code revision / dirty flag | `<recorded from the run artifact>` |

## 4. Design

| Field | Value |
|---|---|
| Setups | `<comma-separated SETUPS keys>` |
| Horizons / variants | `<e.g. 1, 5, 10, 20, 60>` or `<B0..B4 with rules>` |
| Cell count | `<setups> x <horizons or variants> = <N> cells` |
| Entry rule | `<signal at t, entry at open of t+1, ATR14 of signal bar, skip NaN/<=0>` |
| Exit rule | `<stops, targets, trails, time exits, order and tie-breaks>` |
| 1R definition | `<e.g. 2 * ATR for every variant>` |
| Costs | `<bps per side and the r_net / r_gross formulas>` |
| Sizing / position limit | `<e.g. none — one trade at a time; or portfolio rules>` |
| Capacity / slot competition | `ignored` or `<modelled>` |
| Cooldown / dedupe | `<none / previous accepted event <= N bars>` |
| Strategy seeds | `<list and count, or none>` |
| Null / control family | `<matched_random_signals / permuted / shifted / none>` |
| Null draws and seeds | `<n draws, seed range>` |
| Bootstrap resamples and seed | `<n resamples, seed>` |
| Benchmark | `<same-date eligible universe mean / other / not recorded>` |

## 5. Pass/fail criteria (fixed before the run)

State one primary rule. Do not add or change a criterion after seeing the result.

| Field | Value |
|---|---|
| Primary threshold | `<e.g. mean excess > 0 bp, or gap / null std > 2>` |
| Direction | `higher` / `lower` |
| p-value definition | `<one-sided formula and which tail>` |
| p-value threshold | `<e.g. p_high < 0.05>` |
| CI rule | `<e.g. month-block bootstrap lower bound > 0>` |
| Multiple-comparison handling | `<e.g. Bonferroni over N cells / none — exploratory only>` |
| Pass action | `<record as hypothesis only / no live change>` |
| Fail action | `<record and stop / no re-run with a new window>` |
| Amendment rule | any post-run change here invalidates the confirmatory label |

## 6. Outputs and evidence

| Field | Value |
|---|---|
| Script | `<scripts/research_*.py>` |
| Flags | `<--flags actually used>` |
| Report path | `<docs/backtests/research/*.md>` |
| JSON path | `<docs/backtests/research/.../*.json>` |
| Unit-test command | `<pytest command>` |
| Lint command | `<ruff check command, exact CI scope>` |
| Commit hash of the frozen pre-registration | `<filled after the pre-registration commit>` |
| Commit hash(es) of the run | `<filled after the run>` |

## 7. Limits to restate with any result

- In-sample, survivorship-biased universe; no walk-forward.
- Exploratory: never the scorecard, D-75 pass bar, kill rule or any forward verdict.
- If capacity/slot competition is ignored, say so in the result table.
- If cells share signals or entries, state that the cells are not independent trials.
- If the universe benchmark is a same-date eligibility mean, state that it is not
  sector- or size-matched.

## 8. Amendment log

| Date | Field | Old value | New value | Reason | Effect on label |
|---|---|---|---|---|---|
| `<YYYY-MM-DD>` | `<field>` | `<old>` | `<new>` | `<reason>` | `still EXPLORATORY` / `invalidated` |

---

Reference: [D-84](../../DECISIONS/D-84-research-signal-information-and-exit-shape.md),
[H-13 / H-14 and the trial ledger](../HYPOTHESIS_LOG.md),
[EVENT_STUDY.md](EVENT_STUDY.md), [EXIT_STUDY.md](EXIT_STUDY.md).
