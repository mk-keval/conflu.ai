# Ablation: same-day slot recycling (D-82)

- Generated: 2026-11-16
- Question: how much of the D-81 → D-82 per-trade expectancy move does
  `allow_same_day_recycling` account for?
- Engine: commit `7628660` (D-82 engine plus the T8 clean-tree guard). No engine, indicator
  or control code was changed for this ablation.
- Reproduce: `python scripts/run_research_baseline.py --setup <name>
  --allow-same-day-recycling --tag recycle_on` — every other flag default, including
  `--end` = today (2026-11-16).
- Sources: D-82 default values come from the four `*_20261113_*.json` artifacts (panel
  ending 2026-11-12); recycle-on values come from the four `*_20261116_*_recycle_on.json`
  artifacts (panel ending 2026-11-16). All figures are read from each artifact's `metrics`,
  `p_values.matched_random` and `control_summary.matched_random.r_net_mean_mean`.
  D-81 expectancy values are the published D-81 baseline table
  (`docs/DECISIONS/D-81-research-baseline-v2-honesty-and-controls.md`).
- Trade statistics use each artifact's evaluation window (uncensored trades with
  `exit_date >= 2016-01-01`).

## breakout_52week

| Book | n | Expectancy net | PF | CAGR | Max DD | p (matched) | Control expectancy mean |
|---|---|---|---|---|---|---|---|
| D-82 default (no recycling) | 1684 | +0.0333 | 1.07 | +1.49% | -21.11% | 0.6452 | +0.0447 |
| recycle on | 1871 | -0.0004 | 1.00 | -0.40% | -34.36% | 0.9032 | +0.0301 |

## low_vol_setup

| Book | n | Expectancy net | PF | CAGR | Max DD | p (matched) | Control expectancy mean |
|---|---|---|---|---|---|---|---|
| D-82 default (no recycling) | 1746 | +0.0280 | 1.05 | +1.59% | -31.60% | 0.3871 | +0.0217 |
| recycle on | 1964 | -0.0007 | 1.00 | -0.81% | -43.54% | 0.7097 | +0.0130 |

## statistical_mean_reversion

| Book | n | Expectancy net | PF | CAGR | Max DD | p (matched) | Control expectancy mean |
|---|---|---|---|---|---|---|---|
| D-82 default (no recycling) | 1680 | +0.0489 | 1.11 | +2.45% | -23.45% | 0.2903 | +0.0350 |
| recycle on | 1861 | -0.0007 | 1.00 | -1.01% | -35.27% | 0.6129 | +0.0082 |

## volume_trend_accumulation

| Book | n | Expectancy net | PF | CAGR | Max DD | p (matched) | Control expectancy mean |
|---|---|---|---|---|---|---|---|
| D-82 default (no recycling) | 2120 | -0.0039 | 0.99 | -0.57% | -35.64% | 1.0000 | +0.0492 |
| recycle on | 2376 | +0.0032 | 1.01 | -1.06% | -42.90% | 0.9677 | +0.0313 |

## Share of the D-81 → D-82 expectancy move

Share = (D-82 default − recycle on) / (D-82 default − D-81), computed on expectancy net.

| Setup | D-81 | D-82 default | recycle on | Numerator | Denominator | Share |
|---|---|---|---|---|---|---|
| breakout_52week | -0.008 | +0.033339 | -0.000449 | +0.033788 | +0.041339 | +81.7% |
| low_vol_setup | 0.000 | +0.027993 | -0.000665 | +0.028658 | +0.027993 | +102.4% |
| statistical_mean_reversion | -0.001 | +0.048896 | -0.000669 | +0.049566 | +0.049896 | +99.3% |
| volume_trend_accumulation | +0.018 | -0.003933 | +0.003202 | -0.007135 | -0.021933 | +32.5% |

On expectancy net, the recycling flag accounts for +81.7% / +102.4% / +99.3% / +32.5% of the
D-81 → D-82 move for breakout_52week, low_vol_setup, statistical_mean_reversion and
volume_trend_accumulation respectively; every denominator exceeded 0.02 R in absolute value,
so no setup falls into the "not meaningful" case.

## Seed noise

Across-seed std is from `DIAGNOSTICS.md` (20 candidate seeds, 42..61); matched-control std is
the same document's newest-artifact column (the four `*_20261116_*_recycle_on.json` runs).

| Setup | Across-seed std (20 seeds) | Matched-control std |
|---|---|---|
| breakout_52week | 0.0140 | 0.0229 |
| low_vol_setup | 0.0198 | 0.0232 |
| statistical_mean_reversion | 0.0188 | 0.0222 |
| volume_trend_accumulation | 0.0230 | 0.0167 |

Across-seed std is below the matched-control std for breakout_52week, low_vol_setup and
statistical_mean_reversion and above it for volume_trend_accumulation.
