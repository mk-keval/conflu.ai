---
name: tvscreener-specialist
description: Master of the `tradingview-screener` Python package (v3.2.2) — complete Query/Column/And/Or API, filter-operation map, pipe timeframes (selects AND filters), live-verified column registry with dead-column list (OBV, supertrend, BB.middle, wrong-case STOCH.K…), index symbolset formats (SPX 498 / NDX 97 / RUT 1903), ticker batching, scan2/options, rate-limit & error modes; compiles conflu.ai screen YAMLs into optimal TV queries and feeds the confluence pipeline. Use for any TV screener question — columns, filter syntax, multi-timeframe, universes, batching — or when editing tv_specialist.py / config/screens/*.yaml.
trigger: /tvscreener-specialist
---

# TV Screener Specialist — packaged mastery of `tradingview-screener`

**Scope:** TradingView Screener discovery for the conflu.ai screening pipeline (and any
ad-hoc TV query work). Covers the full public API of `tradingview-screener` v3.2.2, the
live-verified column/ops truth tables, and the repo's `tv_specialist.py` integration.

**Evidence:** everything marked ✅/❌ below was probed live on **2026-10-19** (package
3.2.2, market `america`, top-mcap rows) plus source reads of the installed package.
Re-verify any time with `scripts/probe_columns.py` (ships with this skill).

**Triggers:** "screen the market using TV", "how do I use tradingview-screener for X",
"what TV columns are available", "how to filter by MACD/RSI/EMA in TV", "multi-timeframe
screening with TV", "TV Screener rate limits", "TV index constituents", "ATR entry/SL".

---

## 0. Golden rules (read first)

1. **Unknown columns are silently accepted → all-`None`.** A wrong/unknown field in
   `select()` does NOT error; it returns a column of `None`. Never trust a column name
   without a probe. (Real example: `STOCH.K` → None, `Stoch.K` → works.)
2. **Default range is `[0, 50]`.** Always `.limit(n)` explicitly. Batch pulls via
   `set_tickers` need `limit >= len(tickers)` or rows get truncated silently.
3. **Timeframes live in the column name** (`RSI|60`, `close|240`, `EMA20|1W`), in
   `select()` AND in `where()`. The top-level `interval` payload key is ignored (§4).
4. **Column-to-column comparisons** are the way to compare fields
   (`col('close') > col('EMA200')`); put the other column as a `Column`/name, not a value.
5. **There is no `Not()` operator.** Invert at the map level (`nequal`, `not_in`,
   `has_none_of`, `not_between`, `nmatch`) — repo convention, same as `FILTER_MAP`.
6. **Snapshot only, no history.** TV returns current values; deep history lives in the
   repo's DuckDB/yfinance paths.

---

## 1. Package surface (v3.2.2)

```python
from tradingview_screener import Query, Column, col, And, Or
from tradingview_screener import (stocks, coin, crypto, crypto_dex,
                                  forex, futures, bond, cfd, options)
from tradingview_screener.util import format_technical_rating
```

- One module per concern: `query.py` (Query/And/Or), `column.py` (Column/col),
  `screeners.py` (preset builders), `models.py` (TypedDict payload schema), `util.py`.
- **No `__version__` attribute** — use `importlib.metadata.version("tradingview-screener")`.
- `py.typed` shipped; everything is sync (wrap in `run_in_executor` for async, as the repo does).

### The `Query` object — method → payload key

| Method | Payload key | Notes |
|---|---|---|
| `Query(market='america')` | `markets` | default payload = primary US stocks, sorted by market cap desc |
| `.select(*cols)` | `columns` | **replaces** TV defaults entirely |
| `.where(*exprs)` | `filter` | expressions AND-joined; **replaces** the whole `filter` list |
| `.where2(op)` | `filter2` | `op` must be wrapped in `And()`/`Or()`; nests freely; coexists with `filter` |
| `.order_by(col, ascending=True, nulls_first=False)` | `sort` | |
| `.limit(n)` / `.offset(n)` | `range` | `range=[offset, limit]`, default `[0, 50]` |
| `.set_markets(*m)` | `markets` | 1 market → `/{market}/scan`; 0 or 2+ → `/global/scan` |
| `.set_tickers(*t)` | `symbols.tickers` | `'EXCH:SYM'`; **resets markets → `/global/scan`** |
| `.set_index(*i)` | `symbols.symbolset` + `preset` | format `SYML:{source};{SYMBOL}` (§5); resets markets |
| `.set_property(k, v)` | arbitrary | raw escape hatch (e.g. `ignore_unknown_fields`); no validation |
| `.get_scanner_data(**kw)` | — | → `(totalCount, pd.DataFrame)`; `**kw` forwarded to `requests.post` (`cookies=`, `timeout=`, `proxies=`) |
| `.get_scanner_data_raw(**kw)` | — | raw dict (`{'totalCount', 'data':[{'s','d'}]}`) |
| `.copy()` | — | independent deep copy; `.order_by`/`.limit`/`.where` are chainable (return `Self`) |

`get_scanner_data` sends `POST <url>` with `json=payload`, default `timeout=20`,
`raise_for_status()` with the response body appended to the error message.
**No retry/backoff inside the library** — retries are app-side (§8).

## 2. Column filters — full operation map

Every `Column` method returns a payload dict; comparisons produce the same dicts the TV
API consumes. Right-hand side may be a literal **or another column** (`Column` instance
or plain name string).

| Python | TV `operation` | Meaning |
|---|---|---|
| `col(x) > v` | `greater` | |
| `col(x) >= v` | `egreater` | |
| `col(x) < v` / `<= v` | `less` / `eless` | |
| `== v` / `!= v` | `equal` / `nequal` | |
| `.crosses(other)` | `crosses` | crosses in either direction (fresh event) |
| `.crosses_above(other)` / `.crosses_below(other)` | `crosses_above` / `crosses_below` | fresh cross only |
| `.between(a, b)` / `.not_between(a, b)` | `in_range` / `not_in_range` | |
| `.isin([...])` / `.not_in([...])` | `in_range` / `not_in_range` | same ops as between — TV overloads them |
| `.has('common')` / `.has_none_of([...])` | `has` / `has_none_of` | **set fields** (`typespecs`); right may be str or list |
| `.in_day_range(a, b)` / `.in_week_range` / `.in_month_range` | `in_day_range`… | relative windows, e.g. earnings `in_day_range(0, 0)` = today |
| `.above_pct(other, 1.03)` / `.below_pct(other, 1.03)` | `above%` / `below%` | x is ≥3% above / ≤ below other |
| `.between_pct(other, 1.2, 1.5)` / `.not_between_pct(...)` | `in_range%` / `not_in_range%` | |
| `.like('apple')` / `.not_like('apple')` | `match` / `nmatch` | substring match (`col LIKE '%apple%'`) |
| `.empty()` / `.not_empty()` | `empty` / `nempty` | null checks (right omitted) |

- `smatch` exists in the schema (`models.py`) but has no Python method — use raw dicts
  if ever needed.
- `col(x) == v` **returns a dict**, not a bool — never use `==` on Columns in Python code.
- `And(*exprs)` / `Or(*exprs)` build nested `{'operation': {...}}` trees for `where2`;
  nesting is unlimited. `where2()` + `where()` can be combined (both payload keys ship).

## 3. Timeframes — pipe suffixes (the ONLY working mechanism)

Append `|INTERVAL` to any timeframe-aware column name:

| TF | suffix | TF | suffix |
|---|---|---|---|
| 1 min | `close\|1` | 2 h | `close\|120` |
| 5 min | `close\|5` | 4 h | `close\|240` |
| 15 min | `close\|15` | 1 week | `close\|1W` |
| 30 min | `close\|30` | 1 month | `close\|1M` |
| 1 hour | `close\|60` | **1 day** | **no suffix** |

- ✅ Works in `select()` — live: `RSI` 60.59 (1D) vs `RSI|60` 49.09 vs `RSI|1W` 65.21.
- ✅ Works in `where()` — live: `.where(col('RSI|1W') > col('RSI'))` matched 6,962 rows;
  the package README itself filters on `col('MACD.macd|1') >= col('MACD.signal|1')`.
  **Cross-timeframe server-side filtering in ONE request is real** — no client-side
  intersection needed for filter purposes.
- ❌ Top-level `interval` property is **ignored** by the scan endpoint (live: identical
  daily values). `set_property('interval', ...)` is a no-op — only pipe suffixes change TF.
- DataFrame columns keep the pipe verbatim: `df['RSI|60']`.
- Friendly labels → codes: `1m→1, 5m→5, 15m→15, 30m→30, 1h→60, 2h→120, 4h→240,
  1D→(none), 1W→1W, 1M→1M`.

## 4. Live-verified column registry (2026-10-19, v3.2.2)

### ✅ Verified working (non-null on top-mcap US stocks)

| Category | Columns |
|---|---|
| Price/action | `close`, `change`, `gap`, `premarket_change`, `High.All`, `Low.All`, `price_52_week_high`, `price_52_week_low` |
| Volume/liquidity | `volume`, `average_volume_10d_calc`, `relative_volume_10d_calc`, `volume_change`, `VWAP`, `Value.Traded` |
| Trend | `EMA9`, `EMA10`, `EMA20`, `EMA21`, `EMA50`, `EMA100`, `EMA150`, `EMA200`, `SMA20`, `SMA50`, `SMA200` |
| Momentum | `RSI` (=14), `RSI7`, `RSI21`, `Stoch.K`, `Stoch.D`, `CCI20`, `MACD.macd`, `MACD.signal`, `MACD.hist`, `Recommend.All` (numeric −1…1), `TechRating_1D`/`.tr` (string labels) |
| Volatility/risk | `ATR`, `BB.upper`, `BB.basis` (middle band!), `BB.lower`, `Volatility.D`, `beta_1_year`, `beta_5_year` |
| Performance | `Perf.W`, `Perf.1M`, `Perf.3M`, `Perf.6M`, `Perf.Y` |
| Fundamentals | `market_cap_basic`, `market_cap_calc`, `price_earnings_ttm`, `earnings_per_share_diluted_ttm`, `dividends_yield_current` |
| Meta/classification | `name`, `sector`, `industry`, `exchange`, `country`, `type`, `typespecs`, `update_mode` |
| Sentiment | `AnalystRating` (`StrongBuy`/`Buy`/`Hold`/`Sell`/`StrongSell`) |

`format_technical_rating(x)` maps numeric ratings (−1…1) to labels:
`≥0.5 Strong Buy`, `≥0.1 Buy`, `≥−0.1 Neutral`, `≥−0.5 Sell`, else `Strong Sell`.

### ❌ Verified dead / wrong name (all-None — do NOT use)

| Dead name | Use instead / note |
|---|---|
| `STOCH.K`, `STOCH.D` | **`Stoch.K`, `Stoch.D`** (case-sensitive!) |
| `RSI14` | `RSI` (14 is the default period) |
| `ADX14`, `ATR14`, `CCI` | `ADX`, `ATR`, `CCI20` |
| `BB.width`, `BB.middle` | `BB.basis` is the working middle band; width = compute locally `(BB.upper−BB.lower)/BB.basis` |
| `Perf.M` | `Perf.1M` |
| `price` | `close` |
| `ipo_date`, `institutional_ownership`, `short_float`, `float_shares`, `free_float`, `turnover`, `postmarket_change`, `price_earnings_forward` | no live data via this endpoint |
| `relative_strength_rank`, `relative_strength_rating`, `relative_strength` | no live data — compute RS locally (repo: `Perf.*` enrichment in P1.3) |
| `OBV`, `supertrend`, `supertrend.up`, `supertrend.down` | no live data (repo carries them in snapshots for future-proofing; treat as None) |

> Caveat: absence was measured as all-null across top-mcap rows. A legitimately sparse
> field could also show null — re-probe before trusting any new name.
> Wrong-case duplicates (`STOCH.K`) prove TV silently null-fills unknowns.

## 5. Universes: markets, tickers, indexes

- `set_markets('america')` → `POST /america/scan`. Also single countries (`italy`,
  `germany`, `hongkong`, …), asset classes (`crypto`, `forex`, `futures`, `cfd`, `coin`,
  `bond`, `options`, `euronext`). Multiple → `/global/scan` with `markets: [...]`.
- `set_tickers('NASDAQ:AAPL', 'NYSE:GME', ...)` — **batch many symbols in ONE request**
  (repo's `ingest/scanner.py` pattern). Reminder: raise `.limit()` to the batch size.
- `set_index(...)` — index constituents via `SYML:{source};{SYMBOL}` (live-verified):

| Index | symbolset | Live count |
|---|---|---|
| S&P 500 | `SYML:SP;SPX` | 498 ✅ |
| Nasdaq 100 | `SYML:NASDAQ;NDX` | 97 ✅ |
| Russell 2000 | `SYML:TVC;RUT` | 1,903 ✅ |
| ❌ dead variants | `SYML:NDX;NDX` (0), `SYML:SP;RUT` (0), `SYML:NASDAQ;RUT` (0) | |

## 6. Screener presets (module-level constructors)

`stocks(market='america')`, `coin()`, `crypto()`, `crypto_dex()`, `forex()`,
`futures()`, `bond()`, `cfd()`, `options(underlying)` — each returns a fully-primed
`Query` (sensible default columns + sort) that you can chain on.

- `options('NASDAQ:AAPL')` uses the **scan2** endpoint and returns Greeks/IV columns
  (`delta`, `gamma`, `iv`, `theta`, `vega`, `strike`, `expiration`, …); filter by date via
  `.where(col('expiration') == 20260427)` and sort by `strike`.
- scan2 responses have a different shape — see §7.

## 7. Responses, pagination, scan2

- Normal scan → `{'totalCount', 'data': [{'s': 'NASDAQ:AAPL', 'd': [values…]}]}`;
  `get_scanner_data()` returns `(totalCount, df)` with `ticker` first, then one column
  per requested name (as written — pipes included).
- scan2 (options) → `{'totalCount', 'fields', 'symbols': [{'s', 'f'}], 'time'}`;
  `get_scanner_data()` handles both automatically (columns come from `fields`).
- `totalCount` = full match count, independent of `range`; loop for pagination:

```python
offset, size, frames, total = 0, 500, [], None
while True:
    n, df = q.offset(offset).limit(size).get_scanner_data()
    total = n
    frames.append(df)
    if len(df) < size:
        break
    offset += size
```

## 8. Rate limits, delays, error modes

| Constraint | Value |
|---|---|
| Cost | Free, no API key needed |
| Delay | `update_mode = delayed_streaming_900` → ~15 min delayed (live-verified) |
| Real-time | Pass session cookies: `get_scanner_data(cookies=...)`. `rookiepy` browser-cookie loader or `{'sessionid': ...}` (README); free account is enough for streaming equities |
| Library retry | **None** — plain `requests.post(json=..., timeout=20)` + `raise_for_status()`; error message gets the response body appended |
| Quota | No published number; README: "be mindful of server load and potential bans" — batch with `set_tickers`, reuse/cache results, don't poll |
| 4xx/5xx | Raised as `HTTPError`; 429s under bursts must be retried app-side |
| Unknown fields | Silently null in results (§0.1); unknown `preset`/malformed payload can 400 |
| Cold start | First query in a fresh process pays pandas import — use generous timeouts (repo: 30 s) |
| History | None — snapshot only |

Repo-side resilience (reuse this, don't rebuild): `backend/app/infrastructure/ingest/scanner.py`
— thread-pool execution, exponential backoff + jitter retries, per-market circuit breaker.

## 9. conflu.ai repo mapping (tv_specialist.py integrational layer)

Flow: `ScreenConfig` (YAML, `configs.py`) → `TVScreenerSpecialist.build_query()` →
`Query`; filters compile through `FILTER_MAP` (single source of truth) via `where2(And(...))`,
or evaluate **locally** against a snapshot DataFrame via `tv_local_eval.py` (One-Snapshot-
Multi-Screen path in `snapshot_engine.py`). Output `TVDiscoveryResult(tickers, raw_data, …)` →
`tv_engine.py` (TF-weighted stacking) → `confluence_scorer.py` → `elite_signal.py` →
API router `tv_screener.py`. 19 templates in `config/screens/*.yaml` (+ `regime_screens.yaml`),
validated against `FILTER_MAP` at load time.

Confluence scoring inputs = selected TV columns only:
- Fixed ranges: **Trend 30 / Momentum 25 / Volume 20 / Quality 15 / Fundamental 10**.
- Regime-adaptive weights (used when `regime` is passed): `strong_trend` 40/30/15/10/5;
  `ranging` 15/20/25/25/15; `high_vol` 20/15/30/25/10; `low_vol` 25/25/15/20/15.
- TF weights in `tv_engine.py`: `1D` 0.50, `4h` 0.25, `1W` 0.25, `2h` 0.15, `30m` 0.10.

### ⚠️ Open findings from the 2026-10-19 probe (fix path documented, not yet applied)

1. `SNAPSHOT_COLUMNS` + `FILTER_MAP` stoch filters use `STOCH.K/STOCH.D` (dead) →
   switch to `Stoch.K/Stoch.D`.
2. `BB.middle` (dead) → `BB.basis`; `relative_strength_rank` (dead) → keep RS computed
   locally from `Perf.*` (as the P1.3 path already does).
3. Snapshot selects (`price`, `ipo_date`, `institutional_ownership`, `short_float`,
   `float_shares`, `OBV`, `supertrend*`) are all-null — harmless, but don't gate on them.
4. `build_query()`/`snapshot_engine` set `set_property('interval', ...)` — **no-op
   upstream**; per-TF behavior must come from pipe suffixes per column (`EMA20|240`,
   `RSI|60`) in `select` and/or `where`, or per-TF queries. Today every "TF" query
   actually returns 1D data.
5. `where2` can now do cross-TF filters in ONE query — the client-side intersect in
   `discover_multi_tf()` can be simplified if desired.

## 10. Cookbook

```python
# 1) Minimal screen
Query().select('name', 'close', 'volume', 'relative_volume_10d_calc').limit(10).get_scanner_data()

# 2) Fresh breakout with column comparisons + nesting
q = Query().select('close', 'EMA50', 'RSI', 'MACD.macd', 'MACD.signal', 'relative_volume_10d_calc')
q.where2(And(col('close').crosses_above(col('EMA50')),
             Or(col('MACD.macd') > col('MACD.signal'), col('RSI') > 60)))
q.order_by('relative_volume_10d_calc', ascending=False).limit(25)

# 3) Multi-timeframe in one request (selects + filters)
q = Query().select('close', 'RSI', 'RSI|1W', 'EMA20|240')
q.where(col('close') > col('EMA20|240'), col('RSI|1W') > 50)

# 4) Batch quotes for a watchlist (images/limits: set limit!)
Query().select('close', 'volume', 'VWAP').set_tickers('NASDAQ:AAPL', 'NYSE:GME').limit(2)

# 5) Index scan
Query().select('close', 'relative_volume_10d_calc').set_index('SYML:SP;SPX').limit(10)

# 6) Options chain
options('NASDAQ:AAPL').select('strike', 'bid', 'ask', 'iv', 'delta').where(col('expiration') == 20260427).order_by('strike').limit(20)

# 7) Real-time via cookies
_, df = Query().select('exchange', 'update_mode').limit(1).get_scanner_data(cookies=cookies)
```

## 11. Usage protocol & handoff

1. Receives `ScreenConfig` YAML (or raw requirements) → 2. compiles optimal TV query
(§1–§3) → 3. executes with error/limit discipline (§7–§8) → 4. returns
`TVDiscoveryResult` (tickers + raw DataFrame) → 5. reports any filter that couldn't be
pushed to TV (local fallback).

Handoff: `ConfluenceScorer` (TV columns only) → `DeepAnalysisOrchestrator` (OHLCV +
backtest for top-N) → alerting. Implementation files are listed in §9.

## Limitations

| Limitation | Workaround |
|---|---|
| Snapshot only, no history | DuckDB/yfinance for OHLCV history |
| ~15 min delayed unauthenticated | Cookies for streaming (`update_mode` to verify) |
| Unknown columns silently null | Probe before use (`scripts/probe_columns.py`) |
| `Not()` absent | Use negated ops (`nequal`, `not_in`, `has_none_of`, `nmatch`) |
| No custom indicator formulas | Push standard indicators; compute custom locally |
| Silent truncation at `range` end | Always `.limit(n)` ≥ expected rows |
| scan2 (options) payload differs | Let `get_scanner_data()` handle it; don't hand-parse |
