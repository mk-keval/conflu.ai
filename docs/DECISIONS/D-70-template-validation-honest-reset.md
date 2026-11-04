# D-70: Template Validation Honest Reset — Engine, Runner, and Fetcher Window Fix

**Date**: 2026-10-19
**Status**: Accepted — engine/runner/fetcher applied and re-validated; deployed-screen weights not yet re-tuned (user decision pending)
**Branch**: `fix/technical-tab-empty`

## Context

- The system recommends trades to a user who does not trade for a living. Its supporting evidence was **not trustworthy**: the D-61 backtest (PF 3–52, ">55% WR") came from an engine with a **4h-timeframe blind spot** (per-rule TFs dropped), **silent skips** (unavailable filters passed everything), and **look-ahead/collapsed exits** (shifted entries, fixed 30–330 day holds, dropped operators).
- Forward evidence was ~zero: 3 open paper trades, 0 closed, 0 rejections, 0 runs.
- User approved the plan "full validation also vision md": cleanup the known defects, rewrite the leaky backtest path honestly, re-validate the deployed templates on a broader universe and swing horizon, and write down what "trustworthy" means (VISION.md).

## Decisions

1. **Validation-honesty semantics (3 tiers, no silent passes).**
   - Fundamentals / offline-unavailable filters → recorded per template as `not_applied_filters`, excluded from the pass mask; validation covers the **technical subset only**.
   - Unknown indicator / missing column / negate operator → strict **FAIL** for that rule (recorded), never a silent pass.
   - A 4h rule with no intraday data available → symbol **hard-excluded** and recorded.
2. **Engine rewrite (`external_backtest v2`).** Templates now evaluate their **full filter rule objects** (`signal_filters` supersedes the lossy `signal_params`), per-rule timeframes honored (4h resampled from 1h), entries at **next bar's open**, ATR stop 2.0× / target 3.0× with stop-first same-bar tie-break, `max_hold_bars` swing cap, direction-aware shorts, single CAGR formula (kills the `annualized_return` unit bug).
3. **Honest runner** (`run_template_validation.py`): trailing ~700-day window (yfinance 1h cap — required for 4h rules), 30-name universe, `max_hold_bars=15`; **hard-aborts** if any fetched frame falls outside the declared window.
4. **Fetcher data-integrity rule: cold fetch must equal cache read.** `OHLCVFetcher.fetch_yahoo` ignored explicit `start`/`end` on a cold cache and returned full history (`period="max"`), so the same backtest silently ran on different spans depending on cache state (AAPL back to 1980; also affecting the live `/backtest/external` first touch). Fixed in `015d2fd`: window honored (end+1d for yfinance exclusivity, sliced to `[start, end]` before validate/cache/return) + 3 regression tests.
5. **Repo hygiene.** `.gitignore` `data/` downsized to `/data/`, `/backend/data/`, `/backend/app/data/` (the blanket rule had swallowed `backend/app/infrastructure/data/`); `fetcher.py` force-tracked — it was never in git.
6. **Weights not auto-changed.** `config/regime_screens.yaml` weights were left as-is; header now carries a superseded-stats caveat and the review is flagged to the user (see report § 4).

## Evidence

- **First pass of the re-validation was invalid and discarded**, caught by a capacity invariant (trades × avg hold > available bars) plus single-symbol repro and cache inspection — that is what surfaced the fetcher bug. The polluted cache was purged and the invalid JSON deleted.
- **Corrected run** (`docs/backtests/validation_20261019_191610.json`): 19 templates × 30 symbols, ~700 days, **0 capacity violations**, no fetch anomalies (prefetch audit: 1D = 480 bars, 1h = 3,324 bars for all 30 symbols).
- Honest results (expectancy R / PF): institutional-swing-quality +0.325/1.90; mean-reversion +0.322/1.94; institutional-trend-follower-mtf +0.298/1.73 (24 trades); quality-trend-fundamentals +0.276/1.67 (not deployed); vcp-breakout +0.271/1.63; trend-follower-v2 +0.262/1.64; … bull-flag-continuation +0.120/1.15 (weakest deployed); breakdown (short) −0.153/0.66 (only loser, not deployed). Full table: `docs/backtests/VALIDATION_REPORT.md`.
- Tests: engine + API 13 new tests, fetcher 3 regression tests, template-coverage guard; full backend suite **880 passed / 2 e2e environmental** (live TradingView warm-up timeout; `test_swagger_ui_loads` proven pre-existing via stash).

## Consequences

- **Positive:** template numbers are now believable and reproducible; 4h rules are actually evaluated; every skip is visible; identical data cold vs cached — the P0 "same backtest, different spans" class of bug is dead and regression-guarded.
- **Trade-offs / honest read:** on a correct engine the edge is **modest and realistic** (PF ~1.0–1.9, exp R ~0.07–0.33), not the fairy-tale PF 23–52. The system remains an evidence-gathering experiment until the paper loop yields ≥30 closed trades (VISION.md keep/kill criteria — expectancy ≤ 0 after 30+ closed trades = stop).
- **Open (user decision):** weight review against the new numbers — bull-flag-continuation is the weakest deployed (PF 1.15) yet holds the top `choppy` weight; quality-trend-fundamentals / high-conviction-stack outperform most deployed screens but sit outside `regime_screens.yaml`; `strong_trend`'s 80–95 weights sit on thin samples (24–37 trades).
- **Not done:** walk-forward validation, fundamentals applied offline (DuckDB path), portfolio-level constraints.

## Related

- Supersedes all performance statistics in **D-61** (numbers void; deployment changes remain operative) and the inline stats in `config/regime_screens.yaml`.
- Report: `docs/backtests/VALIDATION_REPORT.md` · Data: `docs/backtests/validation_20261019_191610.json`
- `VISION.md` (success/kill criteria + honesty rules) · `docs/PAPER_TRADING/README.md` (scorecard)
- Commits: `4ce6381` (stage 1) · `a1eeeb3` (engine) · `aa75481` (runner) · `015d2fd` (fetcher) · `d99b9bc` (report + caveats)
- Session: [2026-10-19 template validation honest reset](../SESSIONS/2026-10-19_template-validation-honest-reset.md)
