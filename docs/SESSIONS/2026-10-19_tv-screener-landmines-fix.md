# Session Log: 2026-10-19 — TVScreener Landmines Fix (pipe-suffix timeframes + live column names)

> Application source changed: `tv_specialist.py`, `snapshot_engine.py`,
> `filter_sweep_engine.py`, `external_backtest.py` + tests. Direct follow-up to the
> skill deep upgrade (`ce8700e`), which flagged these as open findings.

**Date:** 2026-10-19
**Branch:** fix/technical-tab-empty
**Scope:** TV screener integrational layer + local-eval twin frames

## Prompt

"lets fix" — the two landmines surfaced by the live probe during the skill upgrade:

1. `FILTER_MAP` / `SNAPSHOT_COLUMNS` used dead TV field casing
   (`STOCH.K`/`STOCH.D`/`BB.middle`) — silently null upstream.
2. `set_property('interval', …)` is a server no-op — every "multi-TF" query
   actually returned 1D data, making TF-weighted scoring and per-TF intersects
   meaningless.

## Impact analysis (GitNexus, pre-edit)

| Target | Risk | Blast radius |
|---|---|---|
| `build_query` | LOW | direct: `discover`; depth-2: `discover_multi_tf`; 0 processes |
| `compile_filters` | LOW | 1 direct, 0 processes, 1 module |
| `fetch_snapshot` | LOW | 1 direct, 0 processes |
| `TVScreenerSpecialist` | LOW | 0 processes |

## What changed

### 1) Live column names (Stoch casing + BB basis)

- `tv_specialist.py` `FILTER_MAP`: stoch builders now use `Stoch.K`/`Stoch.D`
  (TV fields are case-sensitive; `STOCH.K` returns null).
- `tv_specialist.py` `SNAPSHOT_COLUMNS`: `STOCH.K`→`Stoch.K`, `STOCH.D`→`Stoch.D`,
  `BB.middle`→`BB.basis`.
- Local-eval twin frames renamed **in lockstep** (they feed the same FILTER_MAP):
  - `filter_sweep_engine._compute_indicators`: `BB.basis`, `Stoch.K`, `Stoch.D`
    (`filter_sweep_engine` passes these frames into
    `specialist.evaluate_filters_local`, so names must match FILTER_MAP exactly).
  - `external_backtest._compute_indicators` + its rename map: same renames.

### 2) Pipe-suffix timeframes (replaces the no-op `interval` property)

- New helpers in `tv_specialist.py`: `_TF_SUFFIX` (1m…1M incl. `4h`→`|240`),
  `_TF_AWARE_PREFIXES` (live-verified whitelist: EMA/SMA/RSI/MACD./BB./Stoch./
  CCI/ADX/ATR/close/volume/VWAP/relative_volume_10d_calc), `_tf_suffix()`,
  `_tf_column()`, `_strip_tf_suffix()`, `_make_col_factory()`.
- `compile_filters()`: each rule is compiled on **its own** `timeframe` — non-1D
  rules get suffixed columns on both sides of comparisons; fundamentals
  (`market_cap_basic`, …) are never suffixed.
- `build_query()`: `set_property('interval', …)` **removed**; select list is
  suffixed by the config's primary timeframe.
- `discover()`: strips pipe suffixes from the result frame
  (`EMA20|240` → `EMA20`) so the scorer/engine/frontend see base names.
- `snapshot_engine.fetch_snapshot()`: `set_property('interval', '1D')` removed
  (daily base by construction; non-1D rules remain the documented divergence).
- **Bonus latent bug fixed**: single-filter configs previously sent
  `filter2: "greater"` (a string; `where2` requires an And/Or operation dict) —
  `compile_filters()` now always wraps in `And(...)`.
- `price_near_ema` now wraps its EMA in `col()` so `below_pct()` receives the
  suffixed name on TF queries (raw string column args bypass the factory;
  payload is identical on 1D).

### 3) Tests

- `test_tv_specialist.py`: +`TestLiveColumnNames` (2), +`TestTimeframeSuffixes` (5)
  — select suffixing, per-rule mixed-TF suffixes, 1D untouched, single-filter
  And-wrapping, discover() suffix stripping.
- `test_tv_local_eval.py`: +`test_stoch_filters_use_live_column_names`
  (live names resolve; dead `STOCH.K` still fails closed).

### 4) Skill sync

- `.claude/skills/tvscreener-specialist/SKILL.md` §9 rewritten: findings #1/#2
  marked fixed with the exact mechanism; remaining items re-scoped (dead selects,
  `relative_strength_rank` product decision, optional single-query cross-TF).
- Global mirror `~/.claude/skills/tvscreener-specialist/` re-synced (SHA256-identical).

## Live verification (post-fix, production endpoint)

- **Suffix whitelist probe** — 20 daily|4h pairs, all suffixed columns non-null
  and different from daily: `EMA20/50/200|240`, `SMA20|240`, `RSI|240`,
  `MACD.macd/signal/hist|240`, `BB.upper/basis/lower|240`, `Stoch.K|240`,
  `CCI20|240`, `ADX|240`, `ATR|240`, `volume|240`, `volume_change|240`,
  `VWAP|240`, `relative_volume_10d_calc|240`.
- **Same-ticker 4h vs 1D** (NVDA): RSI 35.99 vs 42.04; EMA20 223.24 vs 224.81;
  rvol 0.076 vs 0.599 — genuinely different frames.
- **Server-side gate proof**: `RSI > 39.02` (mid-point) → 4h query returned
  **0** matches, 1D returned **1** (NVDA) — the server honored `RSI|240`.
- **Full `discover()` path**: 4h config → 13,774 matches, `timeframe="4h"`,
  `raw_data` columns stripped back to base names.

## Tests

- Targeted TV suite: **96 passed** (`test_tv_specialist`, `test_tv_local_eval`,
  `test_screen_batch`, `test_tv_engine`, `test_elite_snapshot_parity`) — with the
  follow-up `price_near_ema` test the focused re-run is **49 passed** for
  `test_tv_specialist` + `test_tv_local_eval`.
- Full backend suite: **862 passed, 5 failed** — all 5 pre-existing/known
  (4× `test_regime_selector` from the deleted `short-squeeze.yaml`; 1× e2e
  Playwright request timeout: live-TV warm-up exceeds the 30 s budget).
  Baseline before this change: 854 passed / 5 failed → +8 new tests,
  zero regressions.

## Remaining / follow-ups

- `relative_strength_rank` is still dead upstream: `rs_rank_min/max` need a
  product decision (rewire to local `Perf.*`-based RS, or drop). Not changed here.
- Snapshot-path divergence for non-1D rules stays (documented in
  `snapshot_engine.py`; feature flag off by default).
- `discover_multi_tf()` still runs per-TF queries + client-side intersect — now
  meaningful; single-query cross-TF filters (skill §10 cookbook #3) are possible
  if we want to collapse it.
- Dead selects (`OBV`, `supertrend*`, `price`, `ipo_date`, `institutional_ownership`,
  `short_float`, `float_shares`) remain in `SNAPSHOT_COLUMNS` — harmless nulls;
  don't gate on them.
