# Template Validation Report — 2026-10-19 (honest reset)

**Status:** Current source of truth for per-template backtest evidence.
**Supersedes:** D-61 results (`docs/DECISIONS/D-61-elite-template-deployment.md`) and the D-61-era inline stats in `config/regime_screens.yaml`.
**Source data:** `docs/backtests/validation_20261019_191610.json` (19 templates × 30 symbols, generated 2026-10-19T19:15:30Z).
**Engine:** `external_backtest v2` — commits `a1eeeb3` (engine rewrite), `aa75481` (validation runner), `015d2fd` (fetcher window fix).

---

## 1. Why this run exists

The original D-61 run (2026-09-26, PF 3–52, ">55% WR") was produced by an engine with
four defects that flattered results:

1. **4h blind spot** — per-rule timeframes were dropped; rules written for 4h bars silently ran on daily bars. Five deployed templates were affected.
2. **Silent skips** — filters that could not be evaluated (fundamentals, rs_rank) passed every symbol instead of being recorded.
3. **Look-ahead / collapsed exits** — entries were shifted and holds were fixed 30–330 days; operators and timeframes were dropped in the filter compiler.
4. **Fetcher window bug (found while running this reset)** — `OHLCVFetcher.fetch_yahoo` ignored explicit `start`/`end` on a cold cache and returned full history (e.g. AAPL back to 1980), so the same backtest silently ran on different spans depending on cache state. Fixed in `015d2fd` with regression tests; the invalid first pass of this run was discarded.

On a correct engine the D-61 numbers collapse by an order of magnitude (PF 23–52 → 1.2–1.9) but mostly **stay positive** — the templates are real, the old numbers were not.

## 2. Method

| Setting | Value |
|---|---|
| Window | 2024-11-18 → 2026-10-19 (~700 days; yfinance 1h history limit — needed so 4h rules can be evaluated at all) |
| Universe | 30 liquid names, mega → upper-mid cap (`run_template_validation.py`); survivorship bias remains |
| Entries | Next bar's open after signal |
| Costs | 10 bps fee + 5 bps slippage per side |
| Exits | ATR stop 2.0× / target 3.0×, `max_hold_bars=15` (~3 weeks, swing horizon); same-bar stop+target → stop wins |
| Rules | Full filter objects per template; per-rule timeframes honored (4h resampled from 1h, TV-parity approximate) |
| Honesty | Every unavailable filter recorded in `not_applied_filters` — nothing silently passes |
| Capacity check | trades × avg hold ≤ available bars per symbol — 0 violations across the run; no fetch anomalies (prefetch audit: 1D = 480 bars, 1h = 3,324 bars for all 30 symbols) |

**North-star metric: expectancy per trade in R** (VISION.md). PF is context, not the goal.

## 3. Results (pooled across 30 symbols, sorted by expectancy R)

`★` = deployed in `config/regime_screens.yaml`. Small samples (<30 trades) in italics.

| Template | ★ | Trades | WR | PF | Exp R | AvgWin | AvgLoss | Hold |
|---|---|--:|--:|--:|--:|--:|--:|--:|
| institutional-swing-quality | ★ | 91 | 54.9% | 1.90 | **+0.325** | +1.31 | −0.87 | 8.4 |
| mean-reversion | ★ | 128 | 57.0% | 1.94 | **+0.322** | +1.15 | −0.81 | 8.8 |
| *institutional-trend-follower-mtf* | ★ | 24 | 58.3% | 1.73 | **+0.298** | +1.18 | −0.94 | 7.2 |
| quality-trend-fundamentals | | 110 | 52.7% | 1.67 | +0.276 | +1.32 | −0.89 | 8.4 |
| *vcp-breakout* | ★ | 34 | 52.9% | 1.63 | +0.271 | +1.25 | −0.83 | 8.0 |
| *trend-follower-v2* | ★ | 37 | 54.1% | 1.64 | +0.262 | +1.20 | −0.84 | 8.2 |
| high-conviction-stack | | 127 | 51.2% | 1.50 | +0.256 | +1.28 | −0.85 | 8.0 |
| statistical-mean-reversion | ★ | 80 | 53.7% | 1.50 | +0.254 | +1.11 | −0.85 | 9.1 |
| trend-pullback-v2 | ★ | 83 | 55.4% | 1.44 | +0.246 | +1.11 | −0.89 | 9.8 |
| volume-trend-accumulation | ★ | 94 | 52.1% | 1.46 | +0.214 | +1.23 | −0.89 | 8.1 |
| *52week-breakout* | ★ | 30 | 53.3% | 1.57 | +0.193 | +1.22 | −0.98 | 7.1 |
| low-vol-setup | ★ | 189 | 50.8% | 1.26 | +0.174 | +1.17 | −0.88 | 9.1 |
| volatility-expansion | ★ | 288 | 49.0% | 1.27 | +0.171 | +1.20 | −0.87 | 7.9 |
| trend-leader | | 113 | 47.8% | 1.35 | +0.157 | +1.14 | −0.85 | 7.5 |
| distribution | ★ | 64 | 50.0% | 1.42 | +0.142 | +1.09 | −0.81 | 9.3 |
| institutional-quality-v2 | ★ | 68 | 47.1% | 1.36 | +0.134 | +1.25 | −0.86 | 8.1 |
| bull-flag-continuation | ★ | 129 | 45.7% | 1.15 | +0.120 | +1.17 | −0.85 | 7.5 |
| trend-follower | | 146 | 42.5% | 1.04 | +0.073 | +1.17 | −0.84 | 7.7 |
| breakdown (SHORT) | | 20 | 35.0% | 0.66 | **−0.153** | +1.15 | −0.86 | 10.2 |

**Exit mix is healthy** — no template relies on time-stops alone; stops and targets both fire (e.g. isq: 38 target / 34 stop / 19 time; vol-expansion: 98 target / 117 stop / 66 time).

## 4. What this means for the deployed set

Nothing was changed automatically — these are observations for a weight review (user decision).

**Deployed and healthy (PF ≥ 1.4, exp ≥ 0.19):** mean-reversion, institutional-swing-quality, institutional-trend-follower-mtf, vcp-breakout, trend-follower-v2, statistical-mean-reversion, trend-pullback-v2, volume-trend-accumulation, 52week-breakout, distribution (borderline).

**Deployed but thin:** 52week-breakout carries the top weight in `strong_trend` (95) and `neutral` (95) on only 30 trades (PF 1.57). institutional-trend-follower-mtf is the strongest of the set (PF 1.73) but only 24 trades.

**Deployed but weakest:** bull-flag-continuation (PF 1.15, exp +0.120, 129 trades) — yet it holds the **top choppy weight (85)** and 75 in neutral. First candidate for a downgrade or replacement.

**Deployed in `high_vol`:** all four are positive but modest (1.27–1.90). institutional-swing-quality is the strongest deployed template anywhere; volatility-expansion trades a lot (288) with the thinnest per-trade edge (0.171).

**Not deployed but stronger than most deployed:** quality-trend-fundamentals (exp 0.276, PF 1.67, 110 trades) and high-conviction-stack (exp 0.256, PF 1.50, 127 trades) — candidates to enter `neutral` / `ranging`. Note both rely on fundamentals in live use (recorded as not-applied here), so live selectivity will differ.

**Do not deploy:** breakdown (short) is the only negative template (PF 0.66, exp −0.153, 20 trades). trend-follower (PF 1.04) and trend-leader (PF 1.35) stay out for now.

## 5. Filters not applied during validation (offline)

All templates except `low-vol-setup` ran without at least one fundamental/fundamental-adjacent filter:

| Filter group | Templates |
|---|---|
| `market_cap_gt`, `exchange_in` | all except low-vol-setup |
| `country_in` | all above except institutional-trend-follower-mtf, institutional-swing-quality, volume-trend-accumulation |
| `eps_positive`, `pe_max` | institutional-swing-quality, quality-trend-fundamentals, high-conviction-stack, volume-trend-accumulation, institutional-quality-v2 |
| `rs_rank_min` | vcp-breakout, trend-follower-v2, trend-pullback-v2 |
| `analyst_rating_in` | volume-trend-accumulation |

**Impact:** these templates were validated on their **technical subset only**. The live TV screener applies the fundamentals when data is available, so live signals may be fewer and less noisy than backtest signals. Treat backtest counts as an upper bound on live trade frequency.

## 6. Caveats

- **Survivorship bias** — the universe is today's liquid names; no delisted/fallen names. Screen-behavior evidence, not a P&L promise.
- **Single window, mostly one regime** (late-2024 → 2026, largely constructive). No walk-forward yet; expect regression in hostile regimes.
- **Stop/target fills assumed at the level** — no gap-through slippage on either side.
- **4h parity approximate** — 1h bars resampled to calendar 4h buckets; TV's own 4h bars can differ at the seams.
- **Sample sizes** — 24–288 pooled trades; per-symbol counts are often 0–6. Read pooled numbers only.
- **No portfolio layer** — fees and slippage applied per trade, but no sizing, correlation, or exposure limits.

## 7. Reproduce

```powershell
python run_template_validation.py                 # full: 30 symbols, ~30 min (rate-limited fetches)
python run_template_validation.py --universe quick  # 8 symbols smoke
```

Output lands in `docs/backtests/validation_<UTC-timestamp>.json`. The runner hard-aborts if any fetched frame falls outside the declared window (guards against the `015d2fd` bug class returning).

## 8. Provenance

| Commit | What |
|---|---|
| `4ce6381` | VISION.md, stale test fixtures, regime-map guard |
| `a1eeeb3` | honest engine rewrite (+13 tests, API wiring) |
| `aa75481` | validation runner |
| `015d2fd` | fetcher window fix (+regression tests), `.gitignore` scoping, `fetcher.py` force-tracked |

Old evidence (`backtest_results_20260926_060935.json`, repo root) is retained for reference only — **do not cite its numbers**.
