# D-71: Two-Month Paper-Trade Replay — Simulated Screen Ledger in the Journal

**Date**: 2026-10-19
**Status**: Accepted — replay ledger, API, Journal UI and runner implemented; results are simulated evidence, not forward evidence
**Branch**: `fix/technical-tab-empty`

## Context

- The user is a 9-5 non-trader who needs to **see whether the system's picks would have
  made or lost money**. The forward journal is the honest evidence path, but it only
  contained 3 open trades (entered 2026-10-05/06) and zero closed trades — there was
  nothing to inspect.
- Request: run the daily job "backwards" over the past ~2 months and log the trades so
  the user can check winners/losers, P&L and reliability in the app.
- The live discovery path cannot be replayed exactly: **TradingView's screener only
  answers "now"** (ranking, confluence counts, catalysts and the live gate are all
  live-only). The replay therefore evaluates the *deployed screen templates* against
  historical OHLCV — the same templates the live pipeline chooses by regime.
- The user feared too few signals from the validated 30-name universe; a broad universe
  is required, but Yahoo rate limits mean fetching must be batched.

## Decisions

1. **Simulation, clearly separated from forward evidence.** A replay chain is built in
   the journal DB (`replay_runs`, `replay_trades`) and surfaced under a **Live / 2-month
   replay** toggle in the Journal tab. It never touches `paper_trades`, `/expectancy`,
   the scorecard or the kill rule.
2. **Replay = deployed templates + regime as-of + screen selector parity.**
   - The pure `compute_regime_from_frames(macro, breadth)` is extracted from the live
     `compute_market_regime_sync`; the replay slices macro/sector frames at each signal
     day (`df.loc[:date]`) so no future data leaks into the label.
   - `load_screen_mix()` re-implements `RegimeScreenSelector`'s top-3 + defensive-swap +
     backfill rules from `config/regime_screens.yaml`, keeps the YAML stem and weight,
     and is parity-tested against the live selector for all 5 regimes.
   - Signals are evaluated at each day's close and entered at the **next bar's open**
     (the live brief is pre-market and acts on the next open).
3. **Broad, rate-limit-aware universe.** Current S&P 500 constituents (503 symbols) in
   `config/replay_universe_sp500.txt` (Wikipedia with a browser UA; survivorship bias is
   disclosed). yfinance is called in **20-symbol chunks** with retries/per-symbol
   fallback and a 1s gap; data is cached under `.cache/replay/` (daily ~760d for
   indicator warm-up, hourly ~200d for 4h rules).
4. **Conservative, validation-consistent trade mechanics.** Same engine as D-70:
   next-open entries, ATR stop 2.0× / target 3.0×, stop-first same-bar tie-break,
   15-bar swing cap, 10 bps fees + 5 bps slippage per side, shorts direction-aware.
   Dedupe is one entry per `(signal_date, symbol)`: the highest-priority selected screen
   wins and the others are recorded in `also_signaled_by`. Everything is closed by the
   end of the data window.
5. **Position size is hypothetical and transparent.** 1% risk per trade on a $100k
   account → `shares = risk_usd / |entry − stop|`; `$ P&L` is rebuilt from fills with
   fees/slippage, while R is the engine's raw-price `r_multiple` (report-consistent).
6. **Engine trade rows now expose the journal fields**: `signal_date`, `stop_price`,
   `target_price`, `atr`, `risk_per_share`, `direction` (no behavior change).
7. **Runner is a first-class artifact.** `python run_paper_replay.py` (repo root) writes
   the ledger and a `docs/backtests/replay_<timestamp>.json` artifact; `--days`,
   `--max-per-day`, `--templates`, `--refresh-data`, `--refresh-universe`, `--no-write`
   are supported. Engine per-symbol INFO chatter is suppressed by default.

## Evidence

- Full run (`python run_paper_replay.py`, 2026-10-19): **371 entries** from 16,864 raw
  engine signals → 383 regime-gated → 371 deduped (12 cross-screen overlaps), across
  **500 usable S&P 500 names** and **12 deployed screens**, window
  **2026-08-20 → 2026-10-19** (42 sessions). Regime mix: choppy 21 / neutral 15 /
  strong_trend 6. Market context: SPY +0.5% (range-bound), VIX 16 → 18.
- Result (simulated; **R-multiples are gross, dollar P&L is net of 10 bps fees +
  5 bps slippage per side**): **114 W / 257 L — win rate 30.7%, expectancy −0.203R
  (gross; ≈ −0.27R net), PF 0.63, hypothetical P&L −$99.8k at 1% risk per trade on
  $100k**. Exit mix: stop 185 / target 67 / time 75 / end-of-window 44.
- The bleed concentrated in the **choppy regime**: 242 trades, WR 26.4%,
  expectancy −0.322R, PF 0.49 (−$93.7k). Neutral: 111 trades ≈ flat (+0.005R, PF 1.01).
  Strong-trend: 18 trades, +0.121R, PF 1.46.
- Per screen: only **statistical-mean-reversion** (+0.162R, PF 1.52),
  **institutional-trend-follower-mtf** (+0.183R, 6 trades) and **trend-follower-v2**
  (+0.021R, 9 trades) were positive; **low-vol-setup** (−0.357R, 97 trades) and
  **bull-flag-continuation** (−0.346R, 88 trades) led the losses.
- Artifact: `docs/backtests/replay_20261019_202541.json`; ledger run #2 in
  `replay_runs` / `replay_trades` (viewable in Journal → 2-month replay).
- Tests: 8 replay tests (mapping parity, as-of no-look-ahead, orchestration/gating/
  dedupe/day-cap/P&L math, store round-trip, API round-trip), 2 engine trade-field
  tests, 3 frontend `filterReplayRows` tests; full backend suite 894 passed (1 known
  Playwright e2e timeout); frontend typecheck/build pass.

## Consequences

- **What it proves:** the deployed templates, run over a broad recent universe with the
  exact same conservative engine, produced 371 closed entries: 114 winners / 257 losers,
  expectancy −0.203R, PF 0.63, −$99.8k hypothetical at 1% risk — the in-app ledger shows
  every trade, level and exit reason.
- **Result read (honest):** over this specific 2-month range-bound window the deployed
  basket **lost money**, nearly all of it on choppy-regime days (242 trades, −0.322R);
  only mean-reversion and two trend screens were positive. This does **not** contradict
  D-70 (different window, regime mix, and no live gate); it is exactly why forward,
  gated evidence stays the decider and why the pending weight review (D-70 §4) matters —
  the choppy weight set (bull-flag-continuation / trend-pullback-v2 / low-vol-setup) is
  the cluster this replay flags.
- **What it does not prove:** exact live-brief performance. The TV screener ranking,
  confluence score, catalysts, liquidity/earnings checks and 7-step gate are not
  replayed; the universe is today's S&P 500 (survivorship), 4h rules are approximated
  from 1h resampling, and the simulation assumes every signal is takeable (no portfolio
  constraints). It is **not** a P&L promise and **not** forward evidence.
- **Why it is still useful:** it turns "trust me" into an inspectable ledger: the user
  can see whether the screens picked winners or losers over the recent regime mix, and
  the same engine/R pipeline produced the D-70 validation numbers. Forward expectancy
  remains the north-star metric (VISION.md); this replay must never be pooled into it.
- **Operational:** a fresh replay replaces the previous one (`DELETE /workflow/replay`
  also clears it). Data cache can be refreshed with `--refresh-data`.

## Related

- D-70 (honest engine, validation reset) — replay uses the same engine and exit rules.
- D-68 (SQLite journal, Journal tab) — replay tables live in the same DB file but are a
  separate ledger; single-file policy preserved.
- `docs/backtests/VALIDATION_REPORT.md` — template-level evidence the replay is based on.
- Session: [2026-10-19 paper-trade replay](../SESSIONS/2026-10-19_paper-trade-replay-2mo.md)
