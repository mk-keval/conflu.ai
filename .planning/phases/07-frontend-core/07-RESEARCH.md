# Phase 7: Frontend Core — Research

**Created:** 2026-06-19
**Status:** Ready for planning
**Context:** Phase 1 foundation (DuckDB, config, logging, indicators) + Phase 2 ingestion (Parquet OHLCV, symbol metadata) + Phase 3 screener (filter pipeline, indicator cache) + Phase 4 backtest (BacktestEngine, TradeLedger, PositionSizer) + Phase 5 risk (RiskEngine, VaRCalculator, BetaHedger, CorrelationAnalyzer, KellyOptimizer) + Phase 6 API (FastAPI REST + WebSocket, auth, rate limiting, observability) exist in completed state.

---

## Table of Contents

1. [Project State & Codebase Assessment](#1-project-state--codebase-assessment)
2. [Critical Architecture: What Phase 6 Already Built for Phase 7](#2-critical-architecture-what-phase-6-already-built-for-phase-7)
3. [API Contract Analysis: All Endpoints the Frontend Consumes](#3-api-contract-analysis-all-endpoints-the-frontend-consumes)
4. [WebSocket Protocol Deep Dive](#4-websocket-protocol-deep-dive)
5. [Technology Stack Deep Dive](#5-technology-stack-deep-dive)
   - 5.1 TanStack Query v5 — Server State Management
   - 5.2 TanStack Virtual — Table Virtualization
   - 5.3 TradingView Lightweight Charts v5 — Charting
   - 5.4 Zustand — Client State Management
   - 5.5 Tailwind CSS — Styling
6. [Component Architecture & File Structure](#6-component-architecture--file-structure)
   - 6.1 Directory Layout
   - 6.2 Screener Module
   - 6.3 Charts Module
   - 6.4 Backtest Module
   - 6.5 Risk Module
   - 6.6 Shared Module
7. [State Management Strategy](#7-state-management-strategy)
   - 7.1 Server State (TanStack Query)
   - 7.2 Client State (Zustand)
   - 7.3 WebSocket State
   - 7.4 URL State
8. [WebSocket Integration Strategy](#8-websocket-integration-strategy)
   - 8.1 Singleton Hook Pattern
   - 8.2 Auto-Reconnect with Exponential Backoff
   - 8.3 Channel Subscription Management
   - 8.4 Reconnection & Sequence Numbers
9. [Build & Deploy Configuration](#9-build--deploy-configuration)
   - 9.1 Vite + TypeScript + SWC
   - 9.2 Dev Proxy to Backend
   - 9.3 Docker Multi-Stage Build
   - 9.4 Tailwind Configuration
10. [Dependencies](#10-dependencies)
11. [Risks & Mitigations](#11-risks--mitigations)
12. [Open Questions for Planning](#12-open-questions-for-planning)

---

## 1. Project State & Codebase Assessment

### Current State (after Phase 1-6 completion)

| Aspect | Status | Reusable for Phase 7 |
|--------|--------|----------------------|
| Backend REST API | ✅ 16+ endpoints across 4 routers (screener, backtest, data, risk) | Full data contract for frontend |
| Backend WebSocket | ✅ `/ws/stream` with 6 channel types (price, indicator, signal, screener, risk, backtest) | Real-time data source |
| API response envelope | ✅ `{data: T, meta: {timestamp, request_id, duration_ms}}` | Standard fetch/WS response shape |
| Error envelope | ✅ `{error: {code, message, details, request_id}}` | Error handling pattern |
| Docker Compose | ✅ `api` service on port 8000, `redis` on 6379 | Dev proxy target, Nginx reverse proxy |
| DuckDB database | ✅ `data/conflu.duckdb` with OHLCV, indicators, symbol metadata | Data source behind API |
| Frontend directory | ❌ **Empty** — `frontend/src/{components,hooks,lib}/` exist but are empty | Greenfield |
| `package.json` | ❌ **Does not exist** — no Node.js project initialized | Must create |
| Vite config | ❌ **Does not exist** | Must create |
| Tailwind config | ❌ **Does not exist** | Must create |
| TypeScript config | ❌ **Does not exist** | Must create |
| Docker config (Nginx) | ❌ **Does not exist** — only backend Dockerfile exists | Must create `frontend/Dockerfile` + Nginx config |
| `docker-compose.yml` | ✅ Has `api`, `worker`, `redis` services | Add `frontend` service |
| `config.yaml` | ✅ API settings: `cors_origins: ["http://localhost:5173"]` | Already allows Vite dev server |

### Key Insight: Phase 7 is a Greenfield Build on Top of Phase 6

Phase 7 has **zero frontend code to refactor**. Every decision is from scratch. The research must:
1. Properly define the component hierarchy and data flow
2. Select and configure the right libraries for each concern
3. Design a state management architecture that works with both REST and WebSocket data
4. Ensure a smooth developer experience with Vite proxy and Docker

### What Phase 7 Must Create

```
frontend/
├── package.json
├── tsconfig.json
├── tsconfig.node.json
├── vite.config.ts
├── tailwind.config.ts / postcss.config.js
├── index.html
├── .eslintrc.cjs
├── .prettierrc
├── Dockerfile
├── nginx.conf
└── src/
    ├── main.tsx                    # React entry point
    ├── App.tsx                     # Root layout + routing
    ├── index.css                   # Tailwind imports + global styles
    ├── vite-env.d.ts              # Vite type declarations
    ├── api/                        # API layer
    │   ├── client.ts               # Axios instance with interceptors
    │   ├── endpoints.ts            # Typed API endpoint functions
    │   └── types.ts                # API response/request TypeScript types
    ├── ws/                         # WebSocket layer
    │   ├── useWebSocket.ts         # Singleton WS hook with auto-reconnect
    │   ├── channels.ts             # Channel type definitions
    │   └── types.ts                # WS message types
    ├── store/                      # Zustand client state
    │   ├── useScreenStore.ts       # Selected screen, filters, column visibility
    │   ├── useChartStore.ts        # Timeframe selection, indicator toggles
    │   ├── useBacktestStore.ts     # Selected backtest run, trade filters
    │   └── useRiskStore.ts         # Portfolio selection, risk params
    ├── hooks/                      # Shared React hooks
    │   ├── useKeyboard.ts          # Keyboard shortcut handling
    │   └── useResizeObserver.ts    # Container resize tracking
    ├── components/                 # UI components
    │   ├── layout/                 # App shell, sidebar, header
    │   ├── screener/               # Screener table, filters, exports
    │   ├── charts/                 # Multi-timeframe chart instances
    │   ├── backtest/               # Backtest dashboard
    │   └── risk/                   # Risk dashboard
    ├── lib/                        # Utility functions
    │   ├── format.ts               # Number formatting (prices, pct, PnL)
    │   └── constants.ts            # Timeframes, colors, defaults
    └── types/                      # Shared TypeScript types (mirrors backend models)
        ├── screener.ts
        ├── backtest.ts
        ├── risk.ts
        ├── data.ts
        └── ws.ts
```

---

## 2. Critical Architecture: What Phase 6 Already Built for Phase 7

### 2.1 REST API is Fully Wired

Phase 6 created a complete REST API. The frontend consumes these **without needing any backend changes**:

| Router | Endpoints | Frontend Consumer |
|--------|-----------|-------------------|
| `screener.py` | `POST /api/v1/screen` | Screener table |
| `backtest.py` | `POST /api/v1/backtest`, `POST /api/v1/backtest/optimize`, `POST /api/v1/backtest/monte-carlo`, `GET /api/v1/backtest/{run_id}`, `GET /api/v1/backtest/{run_id}/trades`, `GET /api/v1/backtest/{run_id}/equity` | Backtest dashboard |
| `data.py` | `GET /api/v1/data/{symbol}`, `GET /api/v1/data/symbols`, `GET /api/v1/indicators/{symbol}`, `GET /api/v1/indicators` | Charts, symbol selector |
| `risk.py` | `GET /api/v1/risk/{symbol}`, `GET /api/v1/risk/beta`, `GET /api/v1/risk/correlation`, `GET /api/v1/risk/var`, `POST /api/v1/risk/kelly`, `POST /api/v1/risk/position-size`, `GET /api/v1/risk/summary` | Risk dashboard |

### 2.2 WebSocket is Fully Wired

Phase 6's `ws/handler.py`, `ws/manager.py`, and `ws/channels.py` provide:

- **Single endpoint**: `ws://localhost:8000/ws/stream`
- **Channel-based subscriptions**: `price:`, `indicator:`, `signal:`, `screener:`, `risk:`, `backtest:`
- **Message types**: `subscribe`, `unsubscribe`, `ping`, `resync`
- **Server messages**: typed JSON with `type`, `channel`, `sequence`, `timestamp`, `data`
- **Auto-reconnection**: history buffer (100 messages), resync protocol
- **Connected handshake**: Server sends `{type: "connected", connection_id, timestamp, server_version}`

### 2.3 API Response Envelope Is Standardized

Every API response follows the same shape:

```typescript
// TypeScript types for Phase 7 (mirrors backend Pydantic models)
interface ApiResponse<T> {
  data: T;
  meta: {
    timestamp: string;    // ISO 8601
    request_id: string;   // UUID
    duration_ms: number | null;
  };
}

interface ApiError {
  error: {
    code: string;         // Machine-readable: "RATE_LIMIT_EXCEEDED"
    message: string;      // Human-readable
    details: Record<string, unknown> | null;
    request_id: string | null;
  };
}
```

### 2.4 CORS Is Already Configured

```yaml
# config.yaml
api:
  cors_origins: ["http://localhost:5173"]  # Vite dev server
```

No backend changes needed for local development. For production, update `cors_origins` or use Nginx reverse proxy (same origin).

### 2.5 Docker Points to Backend Port 8000

Existing `docker-compose.yml` has the API on port 8000. The frontend Docker setup (to be created in Phase 7) will use Nginx to reverse-proxy `/api/*` and `/ws/*` to the backend service.

---

## 3. API Contract Analysis: All Endpoints the Frontend Consumes

### 3.1 Screener Endpoints

#### `POST /api/v1/screen`

**Request:**
```typescript
interface ScreenRequest {
  config: string;                    // e.g., "trend-follower"
  symbols?: string[];                // Optional subset
  timeframes?: string[];             // e.g., ["1D", "4h"]
  export_format?: "json" | "csv";
}
```

**Response (standard `ApiResponse`):**
```typescript
interface ScreenSymbolResult {
  symbol: string;
  score: number;
  matched_filters: string[];
  indicator_values: Record<string, number>;
}

// data is ScreenSymbolResult[]
```

**Used by:** Screener table component. Fetched on screen selection, filter change. Real-time updates via WebSocket `screener:*` channel.

#### `GET /api/v1/data/symbols`

**Query params:** `asset_class` (optional), `active_only` (default true)

**Response:**
```typescript
interface SymbolInfo {
  symbol: string;
  asset_class: string;
  exchange: string;
  tv_ticker: string;
  name: string;
  active: boolean;
}
```

**Used by:** Symbol selector / search in screener, chart symbol picker.

### 3.2 Chart / Data Endpoints

#### `GET /api/v1/indicators/{symbol}`

**Query params:** `timeframe`, `indicators` (comma-separated), `limit`

**Response:**
```typescript
interface IndicatorResponse {
  symbol: string;
  timeframe: string;
  indicators: Record<string, Array<{ timestamp: string; value: number }>>;
}
```

**Used by:** Multi-timeframe charts. Fetched for chart rendering. Each timeframe has its own query.

#### `GET /api/v1/data/{symbol}`

**Query params:** `timeframe`, `start`, `end`, `limit`

**Response:**
```typescript
interface OHLCVResponse {
  symbol: string;
  timeframe: string;
  candles: Array<{
    timestamp: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
  }>;
}
```

**Used by:** Charts as primary data source for candlestick series.

### 3.3 Backtest Endpoints

#### `POST /api/v1/backtest`

**Request:**
```typescript
interface BacktestRequest {
  symbols: string[];
  start: string;        // ISO datetime
  end: string;          // ISO datetime
  initial_cash: number; // default 100000
  fees_bps: number;     // default 10
  slippage_bps: number; // default 5
  position_sizing: "fixed" | "atr" | "kelly";
  sizing_params: Record<string, unknown>;
  signal_params: Record<string, unknown>;
}
```

**Response:**
```typescript
interface BacktestResultData {
  run_id: string;
  symbol: string;
  timeframe: string;
  metrics: Metrics | null;
  trades_count: number;
  duration_ms: number;
}
```

**Used by:** Backtest dashboard — run a new backtest.

#### `GET /api/v1/backtest/{run_id}/equity`

**Response:**
```typescript
// data = Array<{ timestamp: string; equity: number }>
```

**Used by:** Equity curve chart in backtest dashboard.

#### `GET /api/v1/backtest/{run_id}/trades`

**Response:**
```typescript
// data = Array<{
//   run_id: string;
//   trade_index: number;
//   symbol: string;
//   entry_time: string;
//   exit_time: string;
//   entry_price: number;
//   exit_price: number;
//   size: number;
//   direction: "Long" | "Short";
//   pnl: number;
//   fees: number;
//   mae: number;
//   mfe: number;
//   hold_duration_bars: number;
//   exit_reason: string;
// }>
```

**Used by:** Trades table in backtest dashboard. Expandable rows show MAE/MFE.

### 3.4 Risk Endpoints

#### `GET /api/v1/risk/beta`

**Query params:** `symbols[]`, `benchmark`, `window`

**Response:**
```typescript
// data = Array<{
//   symbol: string;
//   beta: number;
//   r_squared: number;
//   tracking_error: number;
// }>
```

**Used by:** Beta exposure cards in risk dashboard.

#### `GET /api/v1/risk/correlation`

**Query params:** `symbols[]`, `window`, `group_by`

**Response:**
```typescript
// data = {
//   timestamp: string;
//   window_days: number;
//   symbols: string[];
//   correlation_matrix: number[][];
//   sector_matrix?: { rows: string[]; matrix: number[][] };
//   high_correlation_pairs: Array<{ symbols: [string, string]; correlation: number }>;
//   diversification_score: number;
// }
```

**Used by:** Correlation heatmap in risk dashboard.

#### `GET /api/v1/risk/var`

**Query params:** `symbols[]`, `confidence`, `method`, `horizon`

**Response:**
```typescript
// data = {
//   var: number;
//   cvar: number;
//   confidence: number;
//   method: string;
// }
```

**Used by:** VaR/CVaR gauge charts in risk dashboard.

#### `POST /api/v1/risk/position-size`

**Request:**
```typescript
interface PositionSizeRequest {
  symbols: string[];
  method: "atr" | "kelly" | "fixed";
  cash: number;
  params: Record<string, unknown>;
}
```

**Response:**
```typescript
// data = { sizes: Record<string, number>, method: string, cash: number }
```

**Used by:** Position size calculator in risk dashboard.

---

## 4. WebSocket Protocol Deep Dive

### 4.1 Endpoint & Connection Lifecycle

```typescript
// Connect
const ws = new WebSocket("ws://localhost:8000/ws/stream");

// Connection handshake (optional auth)
// Client sends:
{ "type": "auth", "api_key": "..." }

// Server accepts:
{ "type": "connected", "connection_id": "...", "timestamp": "...", "server_version": "0.2.0" }

// Server rejects (if auth configured):
{ "type": "error", "code": "AUTH_FAILED", "message": "..." }
// Then closes with code 4001
```

### 4.2 Client → Server Messages

| Type | Purpose | Payload |
|------|---------|---------|
| `subscribe` | Subscribe to channels | `{ "type": "subscribe", "channels": ["price:AAPL", "screener:trend-follower"] }` |
| `unsubscribe` | Unsubscribe from channels | `{ "type": "unsubscribe", "channels": ["price:MSFT"] }` |
| `ping` | Keepalive | `{ "type": "ping" }` |
| `resync` | Replay missed messages | `{ "type": "resync", "last_sequence": 140 }` |
| `auth` | Authenticate (if API keys configured) | `{ "type": "auth", "api_key": "..." }` |

### 4.3 Server → Client Messages

```typescript
// Price update
{
  "type": "price_update",
  "channel": "price:AAPL",
  "sequence": 142,
  "timestamp": "2026-06-19T14:30:00.123Z",
  "data": {
    "symbol": "AAPL",
    "price": 198.50,
    "change_pct": 1.2,
    "volume": 15234000,
    "timestamp": "2026-06-19T14:30:00.000Z"
  }
}

// Indicator update
{
  "type": "indicator_update",
  "channel": "indicator:AAPL:rsi_14",
  "sequence": 87,
  "data": {
    "symbol": "AAPL",
    "indicator": "rsi_14",
    "value": 42.5,
    "timestamp": "2026-06-19T14:30:00.000Z"
  }
}

// Screen update
{
  "type": "screen_update",
  "channel": "screener:trend-follower",
  "sequence": 55,
  "data": {
    "screen_name": "trend-follower",
    "total_matched": 47,
    "total_symbols": 5000,
    "symbols": [
      { "symbol": "AAPL", "score": 100.0, "matched_filters": ["price_above_ema_200"] }
    ]
  }
}

// Server error
{
  "type": "error",
  "channel": "price:BADSYMBOL",
  "code": "SYMBOL_NOT_FOUND",
  "message": "Symbol 'BADSYMBOL' not found in active universe"
}

// Pong (response to client ping)
{
  "type": "pong",
  "timestamp": "2026-06-19T14:30:00.123Z"
}

// Resync required (too many missed messages)
{
  "type": "resync_required",
  "message": "Too many messages missed. Reconnect for full state.",
  "current_sequence": 200
}
```

### 4.4 Channel Name Convention

```
price:{symbol}           — Real-time price updates (1s interval)
indicator:{symbol}:{name} — Indicator value updates (5s interval)
signal:{symbol}          — Screener signal updates
screener:{name}          — Screener run results (full + delta)
risk:{portfolio_id}      — Risk metric updates
backtest:{run_id}        — Backtest progress updates
```

### 4.5 Reconnection Protocol

The server maintains a per-connection history buffer (100 messages). A client that disconnects and reconnects sends its last-known sequence number:

```
1. Client disconnects (network issue)
2. Client reconnects → receives "connected" message, sequence resets
3. Client sends: { "type": "resync", "last_sequence": 140 }  // using persisted sequence
4. Server replays messages 141+ from history buffer
5. If >100 messages missed → server sends "resync_required" (client must re-fetch full state)
```

The frontend must persist `lastSequence` per channel in localStorage or Zustand to enable resync across page refreshes.

---

## 5. Technology Stack Deep Dive

### 5.1 TanStack Query v5 — Server State Management

**Version:** v5 (current stable: v5.60+)
**Package:** `@tanstack/react-query`

**Key findings from v5 docs:**

1. **Object signature only** — v5 removed positional args. All queries use `{ queryKey, queryFn, ... }`.

2. **Automatic cancellation** — Pass `signal` from `queryFn` to Axios for automatic request cancellation on unmount:

```typescript
import { useQuery } from '@tanstack/react-query';
import axios from 'axios';

const { data, isLoading, error } = useQuery({
  queryKey: ['screen', configName],
  queryFn: async ({ signal }) => {
    const response = await axios.post('/api/v1/screen', { config: configName }, { signal });
    return response.data.data; // unwrap ApiResponse envelope
  },
  staleTime: 5_000,        // 5s — screener data refreshes frequently
  refetchInterval: 30_000,  // Poll every 30s as fallback (WS is primary)
});
```

3. **Query key structure recommendation:**
```typescript
// Screener
['screen', configName]
['symbols', assetClass]
['screen', configName, { symbols, timeframes }]  // parameterized

// Charts
['indicators', symbol, { timeframe, indicators }]
['ohlcv', symbol, { timeframe, start, end }]

// Backtest
['backtest', runId]
['backtest', runId, 'trades']
['backtest', runId, 'equity']

// Risk
['risk', 'beta', { symbols, benchmark }]
['risk', 'correlation', { symbols, window }]
['risk', 'var', { symbols, confidence, method }]
['risk', 'position-size', { symbols, method, cash }]
```

4. **Mutations for POST endpoints:**
```typescript
const runBacktest = useMutation({
  mutationFn: async (body: BacktestRequest) => {
    const response = await axios.post('/api/v1/backtest', body);
    return response.data.data;
  },
  onSuccess: (data) => {
    queryClient.invalidateQueries({ queryKey: ['backtest', data.run_id] });
  },
});
```

5. **Axios instance with interceptors** — Single client for all HTTP calls:

```typescript
// api/client.ts
import axios from 'axios';

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',  // '' = same origin via proxy
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
});

// Request interceptor: add request_id
apiClient.interceptors.request.use((config) => {
  config.headers.set('X-Request-ID', crypto.randomUUID());
  return config;
});

// Response interceptor: unwrap ApiResponse
apiClient.interceptors.response.use(
  (response) => response.data,  // Unwraps to { data, meta }
  (error) => {
    // Transform error into ApiError shape
    return Promise.reject(error.response?.data?.error || error);
  },
);
```

### 5.2 TanStack Virtual — Table Virtualization

**Version:** v3 (beta, but production-ready)
**Package:** `@tanstack/react-virtual`

**Key findings from v3 docs:**

1. **Row virtualization only** — v3 supports row virtualization (vertical scrolling). Column virtualization is experimental. For the screener table with 50+ columns, the approach is: **sticky columns (CSS) + horizontal scroll** for columns, **TanStack Virtual** for rows.

2. **API surface (v3):**
```typescript
import { useVirtualizer } from '@tanstack/react-virtual';

const virtualizer = useVirtualizer({
  count: rows.length,
  getScrollElement: () => parentRef.current,
  estimateSize: () => 48,      // Fixed row height
  overscan: 5,                 // Extra rows outside viewport
});
```

3. **Table structure:**
```tsx
<div ref={parentRef} style={{ height: '100%', overflow: 'auto' }}>
  <table style={{ position: 'relative', height: `${virtualizer.getTotalSize()}px` }}>
    <thead> {/* sticky header, outside virtual area */} </thead>
    <tbody>
      {virtualizer.getVirtualItems().map((virtualRow) => (
        <tr
          key={virtualRow.key}
          style={{
            position: 'absolute',
            top: 0,
            transform: `translateY(${virtualRow.start}px)`,
          }}
        >
          {/* Frozen symbol column (left sticky via CSS) */}
          <td className="sticky left-0 z-10 bg-gray-800">
            {rows[virtualRow.index].symbol}
          </td>
          {/* Scrollable columns */}
          {columns.map((col) => (
            <td key={col.key}>{rows[virtualRow.index][col.key]}</td>
          ))}
        </tr>
      ))}
    </tbody>
  </table>
</div>
```

4. **Key design decisions:**
   - **Fixed row height** (48px) for scrolling performance. Variable row heights are possible via `measureElement` but add complexity.
   - **Frozen columns**: Use CSS `position: sticky; left: 0` with `z-index` on the symbol column. The rest of columns scroll horizontally.
   - **Column resizing**: Not included in TanStack Virtual. Use CSS resize or a 3rd-party library if needed. Deferred to Phase 8.
   - **Sorting**: Implemented via click handlers on column headers. Sorted data is fed into the virtualizer.

### 5.3 TradingView Lightweight Charts v5 — Charting

**Version:** v5.2
**Package:** `lightweight-charts`

**Key findings from v5 docs:**

1. **Multiple chart instances** — Each timeframe (1D, 4H, 1H, 15m) gets its own `createChart()` call with a separate container element. They are NOT sub-panes — they are independent chart instances synchronized via event handlers.

2. **Crosshair synchronization:**
```typescript
import { createChart, CrosshairMode } from 'lightweight-charts';

const charts: IChartApi[] = [];
const timeframes = ['1D', '4H', '1H', '15m'];

timeframes.forEach((tf) => {
  const container = document.getElementById(`chart-${tf}`);
  const chart = createChart(container, {
    width: container.clientWidth,
    height: 300,
    crosshair: { mode: CrosshairMode.Normal },
    layout: { background: { color: '#1a1a2e' }, textColor: '#d1d4dc' },
    grid: { vertLines: { color: '#2a2a3e' }, horzLines: { color: '#2a2a3e' } },
    timeScale: { borderColor: '#2a2a3e' },
  });

  // Subscribe to crosshair move events for cross-chart sync
  chart.subscribeCrosshairMove((param) => {
    if (param.time) {
      charts.forEach((c) => {
        if (c !== chart) {
          c.setCrosshairPosition(param.point, param.time);
        }
      });
    }
  });

  charts.push(chart);
});
```

3. **Multi-pane layout** — Use `chart.addPane()` to create separate panes for indicators (RSI, MACD). Each pane has its own series. `chart.addPane()` returns `IPaneApi` which can be used to control pane height:

```typescript
const mainPane = chart;  // Main chart
const rsiPane = chart.addPane();
const macdPane = chart.addPane();

// Add series to specific panes
const rsiSeries = chart.addSeries(LineSeries, {
  priceScaleId: 'rsi',
  color: '#7b68ee',
}, rsiPane);
```

Alternatively, render separate chart instances stacked vertically for simpler implementation.

4. **Series types needed:**
   - `CandlestickSeries` — OHLCV price data (main chart)
   - `HistogramSeries` — Volume (overlay on main chart or separate pane)
   - `LineSeries` — Indicator lines (RSI, MACD line, EMA overlays)
   - `AreaSeries` — Equity curve, drawdown

5. **Updating data:**
```typescript
// Full data set
candleSeries.setData(candles);

// Real-time update (single bar)
candleSeries.update({
  time: newTimestamp,
  open: newOpen,
  high: newHigh,
  low: newLow,
  close: newClose,
});
```

6. **Time scale synchronization** — Use `chart.timeScale().subscribeVisibleTimeRangeChange()` to sync visible range across charts:

```typescript
charts.forEach((chart, i) => {
  if (i === 0) return;  // Master chart
  chart.timeScale().setVisibleRange({ from: masterFrom, to: masterTo });
});
```

### 5.4 Zustand — Client State Management

**Package:** `zustand`

**Key patterns for Phase 7:**

```typescript
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface ScreenStore {
  selectedConfig: string;
  timeframes: string[];
  columnVisibility: Record<string, boolean>;
  columnOrder: string[];
  // Actions
  setConfig: (config: string) => void;
  toggleColumn: (column: string) => void;
}

export const useScreenStore = create<ScreenStore>()(
  persist(
    (set) => ({
      selectedConfig: 'trend-follower',
      timeframes: ['1D', '4h'],
      columnVisibility: {},
      columnOrder: [],
      setConfig: (config) => set({ selectedConfig: config }),
      toggleColumn: (column) =>
        set((state) => ({
          columnVisibility: {
            ...state.columnVisibility,
            [column]: !state.columnVisibility[column],
          },
        })),
    }),
    { name: 'screen-store' },
  ),
);
```

**State split by concern:**

| Store | Purpose | Persist? |
|-------|---------|----------|
| `useScreenStore` | Selected screen config, column visibility, column order | Yes |
| `useChartStore` | Selected symbol, timeframe visibility, indicator toggles | Yes |
| `useBacktestStore` | Recent runs, selected run ID, trade table filters | Yes |
| `useRiskStore` | Portfolio ID, selected symbols, active risk view | Yes |
| `useUIStore` | Sidebar open/closed, active view, theme | Yes |

**Important:** Zustand stores are for **client-only state** (UI state, preferences). All **server state** (API data) stays in TanStack Query. This separation prevents duplication.

### 5.5 Tailwind CSS — Styling

**Key configuration points:**

1. **Dark mode default:**
```typescript
// tailwind.config.ts
export default {
  darkMode: 'class',  // Use class-based dark mode
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // Dark theme colors matching TradingView dark
        dark: {
          50: '#C9D1D9',
          100: '#B1BAC4',
          200: '#8B949E',
          300: '#6E7681',
          400: '#484F58',
          500: '#30363D',
          600: '#21262D',
          700: '#161B22',
          800: '#0D1117',
          900: '#010409',
        },
        // Brand accent
        accent: {
          DEFAULT: '#7B68EE',   // Medium slate blue
          light: '#9B8BF4',
          dark: '#5A4DD6',
        },
        // Financial colors
        gain: '#22C55E',
        loss: '#EF4444',
        volume: '#60A5FA',
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
    },
  },
  plugins: [],
};
```

2. **Base styles (`index.css`):**
```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  html {
    @apply bg-dark-800 text-dark-50;
    font-feature-settings: 'tnum' on;  /* Tabular numbers for price alignment */
  }

  /* Custom scrollbar for dark theme */
  ::-webkit-scrollbar {
    width: 8px;
    height: 8px;
  }
  ::-webkit-scrollbar-track {
    @apply bg-dark-800;
  }
  ::-webkit-scrollbar-thumb {
    @apply bg-dark-500 rounded;
  }
}
```

3. **Responsive breakpoints:** Desktop-first (as minimal viable). Tablet/mobile enhanced later (deferred to Phase 8).

---

## 6. Component Architecture & File Structure

### 6.1 Directory Layout

```
frontend/src/
├── main.tsx                      # ReactDOM.createRoot, QueryClientProvider
├── App.tsx                       # Router, layout shell
├── index.css                     # Tailwind + globals
│
├── api/                          # HTTP/API layer
│   ├── client.ts                 # Axios instance (interceptors, base URL)
│   ├── screener.ts               # screen(), exportScreen()
│   ├── backtest.ts               # runBacktest(), getBacktest(), getTrades(), getEquity()
│   ├── data.ts                   # getOHLCV(), getIndicators(), getSymbols()
│   └── risk.ts                   # getBeta(), getCorrelation(), getVaR(), postPositionSize(), postKelly()
│
├── ws/                           # WebSocket layer
│   ├── useWebSocket.ts           # Singleton hook (connect, reconnect, subscribe)
│   ├── channels.ts               # Channel helpers (screenerChannel, priceChannel, etc.)
│   └── types.ts                  # WS message TypeScript interfaces
│
├── store/                        # Zustand client state
│   ├── screen.ts
│   ├── chart.ts
│   ├── backtest.ts
│   ├── risk.ts
│   └── ui.ts
│
├── hooks/                        # Shared hooks
│   ├── useKeyboard.ts            # Keyboard shortcut manager
│   ├── useResizeObserver.ts      # Container resize tracking
│   └── useSynchronizedCharts.ts  # Cross-chart crosshair/time sync
│
├── components/
│   ├── layout/
│   │   ├── AppShell.tsx          # Sidebar + main content area
│   │   ├── Sidebar.tsx           # Navigation: Screener, Charts, Backtest, Risk
│   │   ├── Header.tsx            # Search bar, connection status, theme toggle
│   │   └── ErrorBoundary.tsx     # Per-view error boundary
│   │
│   ├── screener/
│   │   ├── ScreenerPage.tsx      # Page wrapper (fetches, wires WS)
│   │   ├── ScreenSelector.tsx    # Dropdown to pick screen template
│   │   ├── ScreenerTable.tsx     # Virtualized table with TanStack Virtual
│   │   ├── ScreenerRow.tsx       # Single row (virtualized, memo'd)
│   │   ├── ColumnHeader.tsx      # Sortable, resizable column header
│   │   ├── ColumnToggle.tsx      # Dropdown to show/hide columns
│   │   └── ExportButtons.tsx     # CSV/JSON export triggers
│   │
│   ├── charts/
│   │   ├── ChartsPage.tsx        # Page wrapper (symbol picker, timeframe grid)
│   │   ├── SymbolSearch.tsx      # Symbol search/autocomplete
│   │   ├── ChartPane.tsx         # Single chart instance (Candlestick + indicators)
│   │   ├── ChartToolbar.tsx      # Indicator toggle, timeframe switch
│   │   ├── IndicatorPanel.tsx    # Side panel showing active indicator values
│   │   └── ChartSkeleton.tsx     # Loading skeleton
│   │
│   ├── backtest/
│   │   ├── BacktestPage.tsx      # Page wrapper
│   │   ├── BacktestForm.tsx      # Config form (symbols, date range, sizing)
│   │   ├── MetricsCards.tsx      # Grid of metric cards (Sharpe, Sortino, etc.)
│   │   ├── EquityCurveChart.tsx  # Area series of equity over time
│   │   ├── DrawdownChart.tsx     # Area series of drawdown
│   │   ├── TradesTable.tsx       # Virtualized trade list with expandable rows
│   │   ├── TradeDetail.tsx       # Expanded row: MAE/MFE, entry/exit details
│   │   └── OptimizationResult.tsx # Walk-forward fold results
│   │
│   └── risk/
│       ├── RiskPage.tsx          # Page wrapper
│       ├── CorrelationHeatmap.tsx # D3.js or Recharts heatmap
│       ├── PositionSizer.tsx     # ATR/Kelly position size calculator form
│       ├── BetaCards.tsx         # Beta exposure per symbol
│       ├── VarGauge.tsx          # VaR/CVaR gauge/donut chart
│       └── KellyResult.tsx       # Kelly recommendation card
│
├── lib/
│   ├── format.ts                 # formatPrice(), formatPct(), formatPnL(), formatDate()
│   ├── constants.ts              # TIMEFRAMES, INDICATOR_COLORS, SCREEN_TEMPLATES
│   └── cn.ts                     # clsx + tailwind-merge utility
│
└── types/                        # Shared TypeScript types
    ├── screener.ts               # ScreenResult, ScreenConfig, FilterDef
    ├── backtest.ts               # BacktestRecord, Trade, Metrics, EquityPoint
    ├── risk.ts                   # BetaResult, CorrelationMatrix, VaRResult, KellyResult
    ├── data.ts                   # OHLCVCandle, IndicatorPoint, SymbolInfo
    └── ws.ts                     # WSMessage, WSChannelType, ConnectionState
```

### 6.2 Screener Module Data Flow

```
User selects screen template (ScreenSelector)
  → Zustand: useScreenStore.setConfig("trend-follower")
  → TanStack Query refetches: ['screen', 'trend-follower']
  → Axios POST /api/v1/screen { config: "trend-follower" }
  → Response: ApiResponse<ScreenSymbolResult[]>
  → ScreenerTable renders virtualized rows

WebSocket screener:trend-follower channel
  → Real-time updates arrive as screen_update messages
  → Merge into query cache via queryClient.setQueryData
  → Or update separate "ws updates" store for delta merging

User clicks column header
  → Sort data client-side (data is typically <5000 rows)
  → Update virtualizer (reset index, maintain scroll position)

User toggles column visibility
  → Zustand: useScreenStore.toggleColumn("volume_rvol")
  → Columns re-render, virtualizer unchanged
```

### 6.3 Charts Module Data Flow

```
User selects symbol (SymbolSearch)
  → Zustand: useChartStore.setSymbol("AAPL")

For each active timeframe (1D, 4H, 1H, 15m):
  → TanStack Query: ['ohlcv', 'AAPL', { timeframe: '1D' }]
  → Axios GET /api/v1/data/AAPL?timeframe=1D&limit=500
  → CandleSeries.setData(candles)

For each active indicator:
  → TanStack Query: ['indicators', 'AAPL', { timeframe: '1D', indicators: 'rsi,macd' }]
  → LineSeries.setData(indicatorPoints)

Crosshair interaction:
  → subscribeCrosshairMove on master chart (1D)
  → setCrosshairPosition on slave charts (4H, 1H, 15m)

Time range scroll:
  → subscribeVisibleTimeRangeChange on master chart
  → setVisibleRange on slave charts

WebSocket indicator:AAPL:rsi_14 channel:
  → Real-time indicator updates
  → chartSeries.update(latestPoint)

User toggles indicator
  → Zustand: useChartStore.toggleIndicator('rsi')
  → Add/remove line series from chart instance
```

### 6.4 Backtest Module Data Flow

```
User configures backtest (BacktestForm)
  → Triggers useMutation:
    Axios POST /api/v1/backtest { symbols, start, end, sizing... }

On success:
  → Navigate to results view with run_id
  → TanStack Query: ['backtest', run_id]
  → TanStack Query: ['backtest', run_id, 'equity']
  → TanStack Query: ['backtest', run_id, 'trades']

MetricsCards:
  → Reads from backtest query result → renders metric grid

EquityCurveChart:
  → Reads equity query → AreaSeries.setData(equityPoints)

DrawdownChart:
  → Computed from equity curve (client-side: peak - current)

TradesTable:
  → Reads trades query → virtualized table
  → Expand row → shows TradeDetail (MAE/MFE chart via mini chart)
```

### 6.5 Risk Module Data Flow

```
CorrelationHeatmap:
  → TanStack Query: ['risk', 'correlation', { symbols, window }]
  → Axios GET /api/v1/risk/correlation?symbols=AAPL,MSFT,...&window=30
  → Render heatmap using Recharts or D3.js

PositionSizer:
  → Form inputs: symbol, method, cash, params
  → useMutation: POST /api/v1/risk/position-size
  → Display result: { symbol: "$42,500" }

BetaCards:
  → TanStack Query: ['risk', 'beta', { symbols, benchmark }]
  → Grid of cards showing beta, R², tracking error per symbol

VarGauge:
  → TanStack Query: ['risk', 'var', { symbols, confidence, method }]
  → Gauge chart showing VaR/CVaR values
```

### 6.6 Shared Module: Layout

```
AppShell
├── Sidebar
│   ├── Screener link
│   ├── Charts link
│   ├── Backtest link
│   └── Risk link
├── Header
│   ├── Symbol search (global)
│   ├── Connection status indicator (WS connected/disconnected)
│   └── User menu (future)
└── Main Content
    └── <Outlet /> (React Router)
```

---

## 7. State Management Strategy

### 7.1 Server State (TanStack Query)

**ALL data from the backend lives in TanStack Query.** This includes:
- Screen results
- OHLCV candles
- Indicator values
- Backtest runs, trades, equity curves
- Risk metrics (beta, correlation, VaR, position sizes)

**Cache configuration defaults:**

| Pattern | `staleTime` | `gcTime` | `refetchInterval` | Notes |
|---------|-------------|----------|-------------------|-------|
| Screener results | 5s | 5min | 30s (fallback) | WS is primary update |
| OHLCV data | 30s | 10min | — | Historical data, rarely changes |
| Indicator data | 10s | 10min | 60s (fallback) | WS for live indicators |
| Backtest results | Infinity | 30min | — | Immutable once complete |
| Risk beta/correlation | 30s | 10min | — | Re-fetched on demand |
| Symbols list | Infinity | 1hr | — | Static data |

**WebSocket integration with TanStack Query:**
```typescript
// When WS screen_update arrives:
const queryClient = useQueryClient();

// Update the query cache directly
queryClient.setQueryData(['screen', 'trend-follower'], (oldData) => {
  if (!oldData) return oldData;
  // Merge delta updates into existing data
  return {
    ...oldData,
    data: mergeSymbolResults(oldData.data, update.symbols),
  };
});
```

### 7.2 Client State (Zustand)

**Zustand stores hold:**
- UI state (selected tabs, active views, sidebar state)
- User preferences (column order, column visibility, indicator toggles)
- Form state (backtest form inputs, position sizer inputs)
- Selection state (selected screen config, selected symbol, selected timeframe)

**Persistence:** Use `zustand/middleware/persist` with `localStorage` for user preferences.

### 7.3 WebSocket State

**Managed by `useWebSocket` hook:**
- Connection state: `'connecting' | 'connected' | 'disconnected' | 'reconnecting'`
- Active subscriptions: `Set<string>`
- Sequence numbers: `Map<string, number>` (channel → last sequence)
- Reconnect attempts: `number` (for exponential backoff)

**WebSocket state is NOT stored in Zustand.** The `useWebSocket` hook manages its own internal state and exposes it to components via React context:

```typescript
// ws/WebSocketProvider.tsx
const WebSocketContext = createContext<WebSocketContextType | null>(null);

export function WebSocketProvider({ children }: { children: ReactNode }) {
  const ws = useWebSocket('ws://localhost:8000/ws/stream');
  return (
    <WebSocketContext.Provider value={ws}>
      {children}
    </WebSocketContext.Provider>
  );
}

export function useWS() {
  return useContext(WebSocketContext)!;
}
```

### 7.4 URL State

**React Router** manages:
- Current view: `/screener`, `/charts`, `/backtest`, `/risk`
- Backtest run ID: `/backtest/result/{run_id}`
- Symbol selection: `/charts?symbol=AAPL`
- Screen config: `/screener?config=trend-follower`

Use `useSearchParams()` for filter/selection params that should be shareable via URL.

---

## 8. WebSocket Integration Strategy

### 8.1 Singleton Hook Pattern

A single WebSocket connection is shared across all components. The `useWebSocket` hook:

1. **Connects once** on app mount (rendered in `WebSocketProvider`)
2. **Manages subscriptions** based on which views are active
3. **Dispatches messages** to TanStack Query cache updaters
4. **Handles reconnection** with exponential backoff

```typescript
// ws/useWebSocket.ts (simplified)
export function useWebSocket(url: string) {
  const [state, setState] = useState<ConnectionState>('disconnected');
  const wsRef = useRef<WebSocket | null>(null);
  const subscriptionsRef = useRef<Set<string>>(new Set());
  const reconnectAttemptRef = useRef(0);
  const maxReconnectDelay = 30_000; // 30s max

  const connect = useCallback(() => {
    const ws = new WebSocket(url);
    ws.onopen = () => {
      setState('connected');
      reconnectAttemptRef.current = 0;
      // Resubscribe to all channels
      subscriptionsRef.current.forEach((ch) => {
        ws.send(JSON.stringify({ type: 'subscribe', channels: [ch] }));
      });
    };
    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      handleMessage(message);
    };
    ws.onclose = () => {
      setState('disconnected');
      scheduleReconnect();
    };
    wsRef.current = ws;
  }, [url]);

  const subscribe = useCallback((channel: string) => {
    subscriptionsRef.current.add(channel);
    wsRef.current?.send(JSON.stringify({ type: 'subscribe', channels: [channel] }));
  }, []);

  const unsubscribe = useCallback((channel: string) => {
    subscriptionsRef.current.delete(channel);
    wsRef.current?.send(JSON.stringify({ type: 'unsubscribe', channels: [channel] }));
  }, []);

  const scheduleReconnect = useCallback(() => {
    const delay = Math.min(
      1000 * Math.pow(2, reconnectAttemptRef.current),
      maxReconnectDelay
    );
    reconnectAttemptRef.current++;
    setState('reconnecting');
    setTimeout(connect, delay);
  }, [connect]);

  useEffect(() => { connect(); return () => wsRef.current?.close(); }, [connect]);

  return { state, subscribe, unsubscribe, ws: wsRef.current };
}
```

### 8.2 Auto-Reconnect with Exponential Backoff

```
Attempt 1: 1s delay
Attempt 2: 2s delay
Attempt 3: 4s delay
Attempt 4: 8s delay
Attempt 5: 16s delay
Attempt 6+: 30s delay (capped)
```

On reconnect:
1. Re-establish WebSocket connection
2. Re-authenticate if needed
3. Re-subscribe to all active channels
4. Send `resync` with last sequence numbers to recover missed messages
5. If `resync_required` → re-fetch full state from REST API

### 8.3 Channel Subscription Management

Subscriptions are **view-driven**: when a user visits the screener page, the component subscribes to `screener:*` and `price:*` channels. When they navigate away, it unsubscribes.

```typescript
// In ScreenerPage.tsx
const { subscribe, unsubscribe } = useWS();
const { selectedConfig } = useScreenStore();

useEffect(() => {
  const channel = `screener:${selectedConfig}`;
  subscribe(channel);
  return () => unsubscribe(channel);
}, [selectedConfig, subscribe, unsubscribe]);
```

### 8.4 Reconnection & Sequence Numbers

```typescript
// ws/channels.ts — sequence number persistence
const SEQUENCE_STORAGE_KEY = 'ws_sequences';

function getStoredSequences(): Record<string, number> {
  try {
    return JSON.parse(localStorage.getItem(SEQUENCE_STORAGE_KEY) || '{}');
  } catch {
    return {};
  }
}

function storeSequence(channel: string, seq: number) {
  const sequences = getStoredSequences();
  sequences[channel] = seq;
  localStorage.setItem(SEQUENCE_STORAGE_KEY, JSON.stringify(sequences));
}
```

On reconnect, the `useWebSocket` hook reads stored sequences and sends a `resync` message for each channel.

---

## 9. Build & Deploy Configuration

### 9.1 Vite + TypeScript + SWC

```typescript
// vite.config.ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react-swc';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    minify: 'terser',
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom'],
          charts: ['lightweight-charts'],
          query: ['@tanstack/react-query'],
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
});
```

### 9.2 Dev Proxy to Backend

The Vite dev server proxies `/api/*` and `/ws/*` to the backend on port 8000. This means:
- Frontend dev: `npm run dev` → `http://localhost:5173`
- API requests: `fetch('/api/v1/screen')` → proxied to `http://localhost:8000/api/v1/screen`
- WebSocket: `new WebSocket('ws://localhost:5173/ws/stream')` → proxied to `ws://localhost:8000/ws/stream`
- No CORS issues in development (same origin via proxy)
- `VITE_API_BASE_URL` env var defaults to `''` (empty = same origin)

### 9.3 Docker Multi-Stage Build

```dockerfile
# frontend/Dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

```nginx
# frontend/nginx.conf
server {
    listen 80;
    server_name localhost;
    root /usr/share/nginx/html;
    index index.html;

    # API proxy
    location /api/ {
        proxy_pass http://api:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # WebSocket proxy
    location /ws/ {
        proxy_pass http://api:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }

    # SPA fallback
    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

### 9.4 Tailwind Configuration

```javascript
// tailwind.config.js
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      // ... as defined in §5.5
    },
  },
  plugins: [],
};
```

**`postcss.config.js`:**
```javascript
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

---

## 10. Dependencies

### 10.1 Production Dependencies

| Package | Version (approx) | Purpose |
|---------|------------------|---------|
| `react` | `^18.3.0` | UI framework |
| `react-dom` | `^18.3.0` | DOM renderer |
| `react-router-dom` | `^6.26.0` | Client-side routing |
| `@tanstack/react-query` | `^5.60.0` | Server state management |
| `@tanstack/react-virtual` | `^3.11.0` | Table/row virtualization |
| `lightweight-charts` | `^5.2.0` | Financial charting |
| `zustand` | `^5.0.0` | Client state management |
| `axios` | `^1.7.0` | HTTP client |
| `recharts` | `^2.14.0` | Correlation heatmap, gauge charts |
| `clsx` | `^2.1.0` | Conditional class names |
| `tailwind-merge` | `^2.5.0` | Class name merging |

### 10.2 Dev Dependencies

| Package | Version (approx) | Purpose |
|---------|------------------|---------|
| `typescript` | `^5.6.0` | Type checking |
| `@vitejs/plugin-react-swc` | `^4.7.0` | Vite React + SWC plugin |
| `vite` | `^5.4.0` | Build tool |
| `tailwindcss` | `^3.4.0` | Utility CSS |
| `postcss` | `^8.4.0` | CSS processing |
| `autoprefixer` | `^10.4.0` | Browser prefixes |
| `eslint` | `^9.0.0` | Linting |
| `eslint-plugin-react-hooks` | `^5.0.0` | React hooks lint rules |
| `prettier` | `^3.3.0` | Code formatting |
| `prettier-plugin-tailwindcss` | `^0.6.0` | Tailwind class sorting |
| `@types/react` | `^18.3.0` | React type definitions |
| `@types/react-dom` | `^18.3.0` | React DOM types |
| `husky` | `^9.1.0` | Pre-commit hooks |
| `lint-staged` | `^15.2.0` | Lint staged files |

### 10.3 Docker Compose Extension

Add to existing `docker-compose.yml`:

```yaml
frontend:
  build:
    context: ./frontend
    dockerfile: Dockerfile
  container_name: conflu-frontend
  ports:
    - "80:80"
  depends_on:
    api:
      condition: service_healthy
  restart: unless-stopped
```

---

## 11. Risks & Mitigations

### High Risk

| Risk | Description | Likelihood | Impact | Mitigation |
|------|-------------|------------|--------|------------|
| **TanStack Virtual v3 is beta** | v3 is still in beta. API may change. Fewer examples than v2. | Medium | High | Pin exact version. Use v2 (react-virtual v2) as fallback if v3 issues arise. v2 API is more mature with more examples. |
| **WebSocket reconnection complexity** | The WS protocol has sequence numbers, resync, auth, and multiple channel types. Coordinating reconnection with REST fallback is non-trivial. | High | High | Build a dedicated `useWebSocket` singleton hook. Write comprehensive tests for reconnection scenarios. Use the "resync_required" signal to fall back to REST. |
| **50+ column table performance** | 5000 rows × 50+ columns of data rendered every update cycle could cause jank. Column virtualization is experimental in TanStack Virtual. | Medium | High | Start with row virtualization only + CSS horizontal scroll. Monitor performance. If scrolling is janky, add column virtualization or reduce visible columns to user's selection. |
| **Multi-chart synchronization edge cases** | Synchronizing crosshair + time scale across 4 chart instances has edge cases: programmatic vs user-initiated moves, race conditions, performance with 4x data rendering. | Medium | High | Build a dedicated `useSynchronizedCharts` hook. Use a "master chart" pattern (1D is master). Throttle synchronization events. |

### Medium Risk

| Risk | Description | Likelihood | Impact | Mitigation |
|------|-------------|------------|--------|------------|
| **Intersection between WS and TanStack Query** | Real-time updates via WS can conflict with TanStack Query refetches (stale data being replaced by fresh data). | Medium | Medium | Design a clear data flow: WS updates go directly into query cache via `setQueryData`. Use `staleTime` to prevent refetches during active WS updates. On WS disconnect, fall back to polling via `refetchInterval`. |
| **Dark theme CSS effort** | Tailwind dark mode requires all components to have dark variants. Missing dark styles = poor UX. | Low | Medium | Start with dark-only (default). Apply dark variants consistently from the start. Defer light theme to Phase 8. |
| **Recharts for correlation heatmap** | Recharts does not have a built-in heatmap chart. Must build custom using Recharts primitives or use D3.js. | Medium | Medium | Use D3.js directly for the heatmap (it's a simple grid of colored rects). Use Recharts for gauge charts. Split concerns cleanly. |

### Low Risk

| Risk | Description | Likelihood | Impact | Mitigation |
|------|-------------|------------|--------|------------|
| **No package.json script standardization** | Multiple scripts (dev, build, lint, format, typecheck) needed. Missing any = DX friction. | Low | Low | Define in `package.json` scripts section upfront: `dev`, `build`, `preview`, `lint`, `format`, `typecheck`. |
| **CORS in production** | If not using Nginx proxy, CORS headers from backend must include the production frontend origin. | Low | Low | Use Nginx reverse proxy (same origin) for production. If not, update `cors_origins` in `config.yaml`. |
| **TradingView Lightweight Charts version compatibility** | v5.2 API may differ from v4. Examples found online may be for v4. | Low | Medium | Pin to `lightweight-charts@^5.2.0`. Follow the official v5 docs (already researched). The v5 API is stable. |

---

## 12. Open Questions for Planning

### Technology Selection

1. **Column virtualization:** Do we need column virtualization for 50+ columns, or is CSS horizontal scroll sufficient? (Decision needed: D-04 suggests 50+ columns, but TanStack Virtual's column virtualization is experimental. Recommend starting with horizontal scroll + column toggle. Add column virtualization in Phase 8 if needed.)

2. **Heatmap library:** Recharts vs D3.js for the correlation heatmap? Recharts has no native heatmap. D3.js is more flexible but adds a dependency. (Recommendation: D3.js — the heatmap is a simple color grid, D3.js handles it cleanly. Use Recharts for all other charts.)

3. **Gauge charts:** Recharts doesn't have native gauge charts. Options: custom SVG, Recharts PieChart with donut, or a dedicated gauge library. (Recommendation: Custom gauge using Recharts PieChart + SVG text overlay.)

### Architecture

4. **Component splitting for ScreenerTable:** Should the 50+ columns be lazily loaded/rendered, or always present? Trade-off: DOM weight vs scroll responsiveness.

5. **Trade expand detail:** Should MAE/MFE in expanded trade rows show a mini tradingview chart or static values? (Recommendation: Static values for Phase 7. Mini charts deferred to Phase 9.)

6. **Error boundaries:** Should each dashboard (screener, charts, backtest, risk) have its own error boundary, or one app-level boundary? (Recommendation: Per-view error boundaries to prevent one dashboard crash from taking down the entire app.)

### Data Flow

7. **WS delta merging strategy:** When a `screen_update` delta arrives, how does the frontend merge it with the existing query cache? Three strategies:
   - **Strategy A:** Replace entire data (simple, but loses scroll position)
   - **Strategy B:** Patch matching symbols in-place (complex merge logic, preserves scroll)
   - **Strategy C:** Keep separate "baseline" (REST) + "deltas" (WS) and combine on render
   - (Recommendation: Strategy B for screener with custom merge function. Strategy C for risk metrics which are simpler.)

8. **Backtest result persistence:** Should the backtest dashboard store recent run IDs in localStorage so users can return to them? Or always require re-running? (Recommendation: Store last 10 run IDs in Zustand (persisted) for quick recall.)

### Styling

9. **Responsive breakpoints:** Phase 7 desktop-first. What's the minimum supported width? (Recommendation: 1280px minimum. Tablet/mobile deferred to Phase 8.)

10. **CSS component library:** Should we use a pre-built component library (Radix UI, Headless UI) for modals, dropdowns, and popovers? (Recommendation: Radix UI for accessible primitive components. It pairs well with Tailwind.)

### Build & Deploy

11. **Docker Compose integration:** Should the frontend be served from the existing `Dockerfile` (monolith that also serves the API) or a separate `frontend/Dockerfile`? (Recommendation: Separate — cleaner separation, independent scaling, matches the existing multi-service pattern in `docker-compose.yml`.)

12. **Environment variables:** Which variables should be configurable?
    - `VITE_API_BASE_URL` — Backend URL (default: '' = same origin via proxy)
    - `VITE_WS_URL` — WebSocket URL (default: auto-derived from API_BASE_URL)
    - `VITE_APP_TITLE` — Browser tab title
    - (Recommendation: Minimum viable — just `VITE_API_BASE_URL`. Derive WS URL from it.)

---

*Phase: 7-Frontend Core*
*Research completed: 2026-06-19*
