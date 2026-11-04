# Session Log: 2026-10-19 — Template Validation Honest Reset (VISION.md, engine rewrite, re-validation)

> Application source changed: `external_backtest.py` (engine rewrite), `fetcher.py`
> (window fix — now git-tracked), `run_template_validation.py` (new runner),
> `config/regime_screens.yaml` (caveat header), `tv_screener.py` (API wiring),
> tests (`test_backtest_external.py`, `test_data_fetcher.py`, regime fixtures),
> `VISION.md` (new), `.gitignore`. Decision: **D-70**.

**Date:** 2026-10-19
**Branch:** `fix/technical-tab-empty`
**Scope:** backtest engine + validation runner + data fetcher integrity + trust documents

## Prompt

Follow-up to the reliability audit: the system recommends trades to a 9-5 user, but
the evidence behind those recommendations could not be trusted. Approved plan —
**"full validation also vision md"**: (1) clean up known test/config debt and write
`VISION.md` with pre-registered success/kill criteria; (2) full validation reset —
rewrite the leaky backtest path, re-run every deployed template on a broader
universe with a swing horizon, no silent skips, and report honestly.

## What changed

### Stage 1 — cleanup + vision (`4ce6381`)

- Fixed 4 stale `regime_selector` tests (fixtures pointed at deleted `short-squeeze`).
- Added regime-map guard test (every deployed screen must exist under `config/screens/`).
- **`VISION.md`**: north-star metric = expectancy per trade in R; success criteria;
  kill rule (expectancy ≤ 0 after 30+ closed trades = stop); honesty rules
  (no silent skips, no cherry-picked windows, superseded evidence marked).

### Stage 2/3 — honest engine + runner (`a1eeeb3`, `aa75481`)

- **Engine rewrite (`external_backtest v2`)** — `signal_filters`: full filter rule
  objects (operators + per-rule timeframes preserved); 4h rules evaluated on 4h bars
  (resampled from 1h); entries at **next bar's open**; ATR stop 2.0× / target 3.0×,
  stop-first same-bar tie-break; `max_hold_bars` analysis; direction-aware shorts;
  single CAGR formula (fixes `annualized_return` unit bug); honesty semantics — every
  unavailable filter recorded as `not_applied_filters`, unknown indicator → strict
  FAIL, 4h rule without intraday → symbol hard-excluded (no silent passes).
- API `/backtest/external` wired to the new engine (filters + direction + stop/target/max_hold).
- 13 engine tests + a template-coverage guard; runner `run_template_validation.py`
  (30-name universe, trailing ~700d, `--max-hold`, hard window abort).

### Stage 4 — re-validation (+ the bug found on the way)

- **First pass was invalid and caught by construction**: capacity invariant
  (trades × avg hold > available bars) flagged AAPL/XOM holding positions before the
  window start. Root cause: `OHLCVFetcher.fetch_yahoo` **ignored `start`/`end` on a
  cold cache** (`period="max"` default → AAPL 11,555 bars from 1980; XOM 16,308 from
  1962) while cache reads returned the windowed 480 — i.e. the same backtest silently
  ran on different spans depending on cache state; also affected live
  `/backtest/external` first touch. Fixed in **`015d2fd`**: window always honored
  (end+1d for yfinance exclusivity, slice to window before validate/cache/return);
  3 regression tests (`test_data_fetcher.py`); runner hard-abort guard. Also: `.gitignore`
  `data/` scoped to `/data/`, `/backend/data/`, `/backend/app/data/` — the blanket rule
  had swallowed the whole `backend/app/infrastructure/data/` package (`fetcher.py` was
  **never tracked**); cache purged (60 files); invalid first JSON deleted.
- **Corrected run** → `docs/backtests/validation_20261019_191610.json`: 19 templates ×
  30 symbols, 0 capacity violations, no fetch anomalies (prefetch audit: 1D 480 /
  1h 3,324 bars for all 30). Honest numbers: best expectancy +0.325 R (PF 1.90) /
  worst deployed +0.120 R (PF 1.15); only `breakdown` (short, not deployed) negative.
- **Report + caveats (`d99b9bc`)**: `docs/backtests/VALIDATION_REPORT.md` (per-template
  verdicts, deployed-set review flags, not-applied filter matrix, caveats, reproduce
  steps); `config/regime_screens.yaml` header caveat + D-61 superseded banner.

### Stage 5 — docs

- D-70 decision + this session log + index updates.

## Test evidence

- Full backend suite: **880 passed, 2 failed** — both e2e environmental: live
  TradingView warm-up timeout (documented D-69) and `test_swagger_ui_loads`
  (reproduced on a stashed pre-change tree — not caused by this work).
- Targeted: engine + fetcher = 16 passed.
- GitNexus `detect_changes` before each commit: docs/config-only edits, 0 affected
  processes, risk low.

## Notes / next

- **Not pushed** — 27 commits local on `fix/technical-tab-empty`; user decides when.
- **User smoke test pending**: Workflow → Daily Routine → Run After-Close (one go) → Journal tab.
- **Weight review pending (user)**: bull-flag-continuation weakest deployed yet top
  `choppy` weight; quality-trend-fundamentals / high-conviction-stack candidates;
  `strong_trend` weights sit on 24–37 trade samples.
- **Forward evidence**: run the EOD loop for 4–6 weeks toward ≥30 closed paper trades (VISION.md kill rule).
- Old D-61 evidence (`backtest_results_20260926_060935.json`) retained, marked do-not-cite.
