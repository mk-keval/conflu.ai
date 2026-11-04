# Session Log: 2026-10-19 — TVScreener Specialist Skill Deep Upgrade (live-verified v3.2.2)

> Environment/tooling work (skill + docs; no application source changed). Companion to the
> dependency security remediation session and the `af0f8d3` tvscreener 3.2.2 bump.

**Date:** 2026-10-19
**Branch:** fix/technical-tab-empty
**Scope:** `.claude/skills/tvscreener-specialist/` (project, tracked) + `~/.claude/skills/tvscreener-specialist/` (global copy)

## Prompt

After the security pass the user asked: "lets upgrade it, also I think there is a relevant
skill for tvscreener as well, so after package, skill should be also updated, make it more
useful, allowing proper features utilization in depth!"

The package was already at the latest release (`af0f8d3` → tradingview-screener 3.2.2; no
4.x exists on PyPI), so the depth work went into the skill.

## Findings (live probes, 2026-10-19)

~15 read-only scan requests against the production endpoint (package 3.2.2, market
`america`, top-mcap rows). Key results:

- **Pipe timeframes work in `select()` AND `where()`** — `col('RSI|1W') > col('RSI')`
  matched 6,962 rows server-side; the package README's own example filters on
  `col('MACD.macd|1') >= col('MACD.signal|1')`. (The previous skill wrongly claimed
  cross-TF filters were impossible in a single request.)
- **Top-level `interval` payload key is IGNORED** — `set_property('interval', '60')`
  returned byte-identical daily values (AAPL RSI 60.59 vs 49.09 for `RSI|60`).
- **Dead / wrong-name columns** (all-null over top-mcap rows): `STOCH.K`/`STOCH.D`
  (correct: `Stoch.K`/`Stoch.D` — case-sensitive), `OBV`, `supertrend(.up/.down)`,
  `BB.middle` (working middle band: `BB.basis`), `BB.width`, `RSI14` (use `RSI`),
  `ADX14`/`ATR14` (use `ADX`/`ATR`), `CCI` (use `CCI20`), `Perf.M` (use `Perf.1M`),
  `price`, `ipo_date`, `institutional_ownership`, `short_float`, `float_shares`,
  `free_float`, `turnover`, `postmarket_change`, `price_earnings_forward`,
  `relative_strength_rank`, `relative_strength_rating`, `relative_strength`.
- **Index symbolsets**: `SYML:SP;SPX` → 498 ✅, `SYML:NASDAQ;NDX` → 97 ✅ (the old
  `NDX;NDX` variant returns 0), `SYML:TVC;RUT` → 1,903 ✅ (the old `SP;RUT` returns 0).
- `update_mode` live-confirms `delayed_streaming_900` (~15 min delay; cookies → streaming).

## What changed

- `SKILL.md` rewritten as a verified reference: golden rules (silent-null columns, default
  `[0,50]` range, pipe timeframes first), full `Query` method → payload-key map, complete
  Column operator → TV-operation table, pipe-TF table with proof, ✅/❌ column registry
  carrying the 2026-10-19 evidence date, universe/index formats, screeners presets,
  pagination, rate limits/error modes, conflu.ai mapping (FILTER_MAP → `where2`, snapshot
  engine, local eval, confluence weights), cookbook, refreshed file table.
- Added `scripts/probe_columns.py` — reusable live verifier (standard working + dead
  registry; `--extra` for candidates). Re-running it re-dates the registry.
- Both copies synced (project + `~/.claude/skills/`); OpenCode hot-reloaded the new
  description live.

## Repo findings surfaced (not yet fixed — see §9 "Open findings" in the skill)

1. `SNAPSHOT_COLUMNS` + `FILTER_MAP` stoch rules use `STOCH.K`/`STOCH.D` (dead) →
   switch to `Stoch.K`/`Stoch.D`.
2. `BB.middle` (dead) → `BB.basis`; `relative_strength_rank` (dead) → RS stays local
   (the P1.3 `Perf.*` enrichment path).
3. `set_property('interval', ...)` is a no-op → every repo "TF" query actually returns 1D
   data; `tv_engine.py`'s TF weighting currently stacks daily data. Fix path: pipe suffixes
   per column (`EMA20|240`, `RSI|60`) or keep per-TF queries with real `|INTERVAL` columns.
4. Cross-TF filters in ONE query are now possible — `discover_multi_tf()`'s client-side
   intersect can be simplified if desired.

## Verification

- Probe script executed standalone from the skill dir (2 requests): working/dead groups
  classify as expected.
- Project and global `SKILL.md` + script SHA256-identical.
- OpenCode confirmed the updated skill live (new description appeared in the skills list).

## Files

- `.claude/skills/tvscreener-specialist/SKILL.md` (rewritten; tracked)
- `.claude/skills/tvscreener-specialist/scripts/probe_columns.py` (new)
- `~/.claude/skills/tvscreener-specialist/` (mirror — outside repo)
- `docs/index.md` (entry added)
