# Session Log: 2026-10-19 — Two-Month Paper-Trade Replay (Journal → Replay)

> Application source changed: engine trade-row fields, regime pure-function
> extraction, new replay data/orchestration/store modules, workflow API,
> Journal tab Live/Replay toggle, runner + universe file, tests. Decision: **D-71**.

**Date:** 2026-10-19
**Branch:** `fix/technical-tab-empty`
**Scope:** historical replay of the deployed screen templates + inspectable in-app ledger

## Prompt

The user wants to check the system's reliability: run the daily job backwards over
the past ~2 months and log the paper trades so they can inspect profit/loss and
winners/losers in the app. The existing forward journal had only 3 open trades and
nothing closed. The user is not attached to those entries; capturing the last two
months is the priority. The universe should be broader than the validated 30 names
(but rate-limit aware), and the replay must be labeled as simulation.

## Design (D-71)

- **Impossible to replay exactly:** TradingView's screener is live-only, so the replay
  evaluates the deployed `config/regime_screens.yaml` templates with the D-70 honest
  engine — not the exact live brief (ranking/confluence/catalysts/gate excluded).
- **Regime as-of:** extracted `compute_regime_from_frames()` from
  `compute_market_regime_sync()`; replay slices macro + sector-breadth frames at each
  signal day and reuses the live scoring/weighting model. No look-ahead (tested).
- **Screen selection parity:** `load_screen_mix()` mirrors `RegimeScreenSelector`
  (top-3 primaries, defensive swap, load-failure backfill) and keeps YAML stem/weight;
  parity-tested for all 5 regimes.
- **Universe/data:** current S&P 500 (503 names) committed as
  `config/replay_universe_sp500.txt`; batched yfinance (20/chunk, retries, fallback),
  cached daily ~760d + hourly ~200d under `.cache/replay/`.
- **Mechanics:** signals at close → next-open entry; ATR 2.0 stop / 3.0 target;
  15-bar cap; stop-first same-bar tie-break; 10 bps fees + 5 bps slippage/side;
  dedupe per `(signal_date, symbol)` by screen rank (`also_signaled_by` records the
  rest); optional `--max-per-day` (default keeps all).
- **Ledger:** separate `replay_runs`/`replay_trades` tables; `GET/DELETE
  /api/v1/workflow/replay`; Journal tab **Live journal / 2-month replay** toggle with
  summary + winners/losers filters + trade table. Never feeds expectancy/kill rule.

## What changed

| Area | File |
|------|------|
| Engine trade rows | `backend/app/infrastructure/backtest/external_backtest.py` — `signal_date`, `direction`, `stop_price`, `target_price`, `atr`, `risk_per_share` |
| Regime pure function | `backend/app/infrastructure/market/regime.py` — `compute_regime_from_frames` + `_score_breadth` |
| OHLCV fetch/cache | `backend/app/infrastructure/backtest/replay_data.py` (new) |
| Orchestration | `backend/app/infrastructure/backtest/replay.py` (new) |
| Ledger store | `backend/app/domain/workflow/replay_store.py` (new) |
| API | `backend/app/api/routers/workflow.py` — `GET/DELETE /workflow/replay` |
| Runner | `run_paper_replay.py` (new), `config/replay_universe_sp500.txt` (new) |
| API client | `frontend/src/api/workflow.ts` — replay types + `getReplayJournal` |
| Journal UI | `frontend/src/components/workflow/JournalTab.tsx` — Live/Replay toggle, summary, filters, table |
| Generated API types | `frontend/src/types/__generated__/` (typegen) |
| Tests | `backend/tests/test_replay.py` (new), `backend/tests/test_backtest_external.py`, `frontend/.../journalTab.test.ts` |
| Docs | `docs/DECISIONS/D-71…`, this log, indexes, `docs/PAPER_TRADING/README.md` |

## Verification

- Replay tests: 8 passing (label-map guard, screen-mix parity, no-look-ahead,
  orchestration/gating/dedupe/day-cap/P&L, store, API).
- Engine tests: 2 new trade-field tests; full backend suite **894 passed**, only the
  known environmental Playwright e2e timeout failed.
- Frontend: typecheck + production build pass; JournalTab tests 15 passing.

## Replay result

**371 entries** (16,864 raw engine signals → 383 regime-gated → 371 deduped) across
**500 usable S&P 500 names** and **12 deployed screens**, **2026-08-20 → 2026-10-19**
(42 sessions; regime mix choppy 21 / neutral 15 / strong_trend 6; SPY +0.5%, VIX 16→18):

- **114 W / 257 L — win rate 30.7%, expectancy −0.203R, PF 0.63, −$99.8k hypothetical**
  at 1% risk/trade on $100k (net of 10 bps fees + 5 bps slippage per side).
- Regime split: choppy 242 trades (−0.322R, PF 0.49, −$93.7k) · neutral 111 (+0.005R,
  PF 1.01) · strong_trend 18 (+0.121R, PF 1.46). Exits: stop 185 / target 67 / time 75 /
  eod 44.
- Screens: statistical-mean-reversion +0.162R (PF 1.52),
  institutional-trend-follower-mtf +0.183R, trend-follower-v2 +0.021R; worst:
  low-vol-setup −0.357R (97 trades), bull-flag-continuation −0.346R (88 trades),
  volume-trend-accumulation −0.253R, trend-pullback-v2 −0.226R, 52week-breakout −0.150R.
- Ledger run #2 stored; artifact `docs/backtests/replay_20261019_202541.json`; inspect in
  **Workflow → Journal → 2-month replay** (All / Winners / Losers).

## Honest read

- This is **simulated screen/template evidence, not forward evidence** and not a P&L
  promise. The TV live brief cannot be reconstructed; the gate is not applied; the
  universe is today's S&P 500 (survivorship bias); 4h rules are approximated from 1h
  resampling; all signals are assumed takeable.
- **The deployed basket lost money in this window** — almost entirely on choppy-regime
  days. That is a real, inspectable finding, not a bug: the D-70 validation edge
  (+0.07…+0.33R) was measured over ~700 days of mixed tape on a 30-name sample; this
  window was range-bound and the momentum/volatility screens whipsawed (185 stop exits).
- Use the replay to inspect behavior and level/exit quality; use the forward journal for
  the scorecard and the kill rule (VISION.md). The pending weight review (D-70 §4) now
  has a concrete additional signal: the choppy weight set is the losing cluster.

## Addendum (same day) — user decision: forward run + review backlog

After the results were presented, the user accepted **Option 1**: no rule changes now —
run the live paper loop forward (~30 closed trades / 4–6 weeks) and decide with real
evidence. Two structural critiques were raised and confirmed against code/numbers:

1. **Exit design caps winners** — best-case win ≈ +1.5R (3 ATR target / 2 ATR stop),
   replay avg win +1.05R; break-even win rate ≈ 40–44% but the replay delivered 30.7%
   (26.4% in choppy). The user's "1.05R is crap" read is correct in context.
2. **Regime response gap** — "Cautious" → choppy serves continuation screens
   (bull-flag-continuation, trend-pullback-v2, low-vol-setup; 242 trades, each ≈ −0.35R)
   while the mean-reversion menu sits under **"ranging", which the detector can never
   produce** (`_REGIME_LABEL_MAP` values are strong_trend/neutral/choppy/high_vol only).
   The only positive screen, statistical-mean-reversion (+0.162R, PF 1.52, WR 44.8%),
   traded via the neutral menu's defensive slot — the system never selected mean
   reversion *because the tape was choppy*.

Captured as the pre-registered review agenda in
`docs/PAPER_TRADING/FORWARD_TEST_REVIEW.md` (items A–D: exit RR ceiling with MFE check,
choppy/ranging menu gap, per-screen forward confirmation, gate effectiveness).
Trigger: **30 closed forward trades or ≈ 2026-11-30**. Daily action: Workflow → Daily
Routine → Run After-Close (one go).
