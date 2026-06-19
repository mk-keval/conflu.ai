# Phase 7: Frontend Core - Implementation Plan

**Created:** 2026-06-19
**Status:** Ready for execution
**Phase Goal:** React + TradingView Lightweight Charts + Tailwind — screener table, multi-timeframe charts, backtest dashboard, risk dashboard
**Depends on:** Phase 6 (API endpoints, WebSocket protocol)

---

## must_haves

Every task must collectively satisfy these goal-backward verification criteria:

1. `npm run dev` starts Vite dev server on port 5173, proxying `/api/*` to `localhost:8000`
2. Screener page renders virtualized table with 50+ sortable columns, frozen symbol column, real-time WS updates
3. Charts page renders 4 synchronized TradingView Lightweight Charts (1D, 4H, 1H, 15m) with indicator overlays
4. Backtest page runs backtest via API, shows equity curve, drawdown chart, virtualized trades table, metrics cards
5. Risk page shows correlation heatmap, position size calculator, beta exposure cards, VaR/CVaR gauges
6. WebSocket singleton connects to `/ws/stream`, auto-reconnects with exponential backoff
7. `npm run build` produces production bundle in `frontend/dist/`
8. `docker-compose up` starts frontend service on port 80, proxying API
9. LSP diagnostics clean on all TypeScript files
10. All types match backend Pydantic models (schemas.py) exactly

---

## Wave 1: Project Scaffolding & Foundation

**Wave goal:** Initialize the React + TypeScript project with all tooling, create shared types mirroring backend Pydantic models, set up API client and WebSocket infrastructure.

**Dependencies:** None (Phase 6 API is already deployed)

### Task 1.1: Initialize Vite + React + TypeScript Project

<read_first>
- `frontend/` directory (empty except `src/` with empty subdirs)
- `.planning/phases/07-frontend-core/07-RESEARCH.md` sections 9.1, 10 (full dependency lists and Vite config)
- `.planning/phases/07-frontend-core/07-CONTEXT.md` decisions D-01, D-19, D-20 (Vite build, Docker)
</read_first>

<action>
1. Create `frontend/package.json` with the following dependencies:
   - **Production:** `react@^18.3.1`, `react-dom@^18.3.1`, `react-router-dom@^6.26.0`, `@tanstack/react-query@^5.60.0`, `@tanstack/react-virtual@^3.11.0`, `lightweight-charts@^5.2.0`, `zustand@^5.0.0`, `axios@^1.7.0`, `recharts@^2.14.0`, `clsx@^2.1.0`, `tailwind-merge@^2.5.0`
   - **Dev:** `typescript@^5.6.0`, `vite@^5.4.0`, `@vitejs/plugin-react-swc@^4.7.0`, `tailwindcss@^3.4.0`, `postcss@^8.4.0`, `autoprefixer@^10.4.0`, `eslint@^9.0.0`, `eslint-plugin-react-hooks@^5.0.0`, `prettier@^3.3.0`, `prettier-plugin-tailwindcss@^0.6.0`, `@types/react@^18.3.0`, `@types/react-dom@^18.3.0`, `husky@^9.1.0`, `lint-staged@^15.2.0`
   - **Scripts:** `"dev": "vite"`, `"build": "tsc && vite build"`, `"preview": "vite preview"`, `"lint": "eslint src --ext .ts,.tsx"`, `"format": "prettier --write src"`, `"typecheck": "tsc --noEmit"`

2. Create `frontend/tsconfig.json` with strict mode, `jsx: "react-jsx"`, `paths: { "@/*": ["./src/*"] }`, `target: "ES2022"`, `moduleResolution: "bundler"`

3. Create `frontend/tsconfig.node.json` for Vite config (extends tsconfig, includes vite.config.ts)

4. Create `frontend/vite.config.ts` with:
   - `@vitejs/plugin-react-swc` plugin
   - `@/` path alias resolving to `./src`
   - Build output to `dist/`, `minify: 'terser'`, `sourcemap: false`
   - Rollup manual chunks: `vendor` (react, react-dom), `charts` (lightweight-charts), `query` (@tanstack/react-query)
   - Dev server on port 5173 with proxy: `/api` → `http://localhost:8000`, `/ws` → `ws://localhost:8000`

5. Create `frontend/index.html` with root `<div id="root">`, link to `src/main.tsx`, loading screen placeholder

6. Create `frontend/.eslintrc.cjs` with TypeScript + React hooks rules, `react-hooks/exhaustive-deps: warn`

7. Create `frontend/.prettierrc` with `semi: true`, `singleQuote: true`, `tabWidth: 2`, `trailingComma: 'es5'`, `plugins: ['prettier-plugin-tailwindcss']`

8. Create `frontend/postcss.config.js` with `tailwindcss` and `autoprefixer` plugins

9. Create `frontend/tailwind.config.ts` with:
   - `darkMode: 'class'`
   - Content paths: `['./index.html', './src/**/*.{js,ts,jsx,tsx}']`
   - Extended colors: `dark-50` through `dark-900`, `accent` (DEFAULT: `#7B68EE`, light: `#9B8BF4`, dark: `#5A4DD6`), `gain: '#22C55E'`, `loss: '#EF4444'`, `volume: '#60A5FA'`
   - Font family mono: `['JetBrains Mono', 'Fira Code', 'monospace']`

10. Create `frontend/src/vite-env.d.ts` with Vite reference types

11. Create `frontend/src/index.css` with Tailwind directives and base styles (dark background `bg-dark-800`, custom scrollbar, tabular numbers)

12. Create `frontend/src/main.tsx` with `ReactDOM.createRoot`, `QueryClientProvider`, `BrowserRouter`, `App` component wrapped in `WebSocketProvider`

13. Create `frontend/src/App.tsx` as routing shell with `React Router` routes: `/` → redirect to `/screener`, `/screener`, `/charts`, `/backtest`, `/backtest/result/:runId`, `/risk`
</action>

<acceptance_criteria>
- `frontend/package.json` contains all 12 production + 11 dev dependencies listed above
- `frontend/tsconfig.json` has `"strict": true`, `"jsx": "react-jsx"`, `"@/*"` path alias
- `frontend/vite.config.ts` has `/api` proxy to `http://localhost:8000` and `/ws` proxy to `ws://localhost:8000`
- `frontend/tailwind.config.ts` has `dark-800`, `accent`, `gain`, `loss` color definitions
- `frontend/src/main.tsx` imports `App` and renders with `QueryClientProvider` + `BrowserRouter`
- `frontend/src/App.tsx` defines routes for `/screener`, `/charts`, `/backtest`, `/backtest/result/:runId`, `/risk`
- `npm install` completes without errors in `frontend/` directory
</acceptance_criteria>

---

### Task 1.2: Create Shared TypeScript Types (Mirroring Backend Models)

<read_first>
- `backend/app/api/schemas.py` — All Pydantic models for screen, backtest, data, risk, WS
- `config.yaml` — frontend config section, risk defaults
- `.planning/phases/07-frontend-core/07-RESEARCH.md` sections 3.1-3.4 (API contract types)
</read_first>

<action>
Create the following files under `frontend/src/types/`:

**`frontend/src/types/api.ts`** — Generic API envelope types:
```typescript
interface MetaInfo { timestamp: string; request_id: string; duration_ms: number | null; }
interface ApiResponse<T> { data: T; meta: MetaInfo; }
interface ErrorDetail { code: string; message: string; details: Record<string, unknown> | null; request_id: string | null; }
interface ApiErrorResponse { error: ErrorDetail; }
```

**`frontend/src/types/screener.ts`**:
```typescript
interface ScreenRequest { config: string; symbols?: string[]; timeframes?: string[]; export_format?: 'json' | 'csv'; }
interface ScreenSymbolResult { symbol: string; score: number; matched_filters: string[]; indicator_values: Record<string, number>; }
interface SymbolInfo { symbol: string; asset_class: string; exchange: string; tv_ticker: string; name: string; active: boolean; }
```

**`frontend/src/types/backtest.ts`**:
```typescript
interface BacktestRequest { symbols: string[]; start: string; end: string; initial_cash: number; fees_bps: number; slippage_bps: number; position_sizing: 'fixed' | 'atr' | 'kelly'; sizing_params: Record<string, unknown>; signal_params: Record<string, unknown>; }
interface BacktestResultData { run_id: string; symbol: string; timeframe: string; metrics: Metrics | null; trades_count: number; duration_ms: number; }
interface Metrics { sharpe_ratio: number; sortino_ratio: number; calmar_ratio: number; max_drawdown_pct: number; win_rate: number; total_return_pct: number; profit_factor: number; expectancy: number; sqn: number; ulcer_index: number; }
interface Trade { run_id: string; trade_index: number; symbol: string; entry_time: string; exit_time: string; entry_price: number; exit_price: number; size: number; direction: 'Long' | 'Short'; pnl: number; fees: number; mae: number; mfe: number; hold_duration_bars: number; exit_reason: string; }
interface EquityPoint { timestamp: string; equity: number; }
interface OptimizationResult { fold: number; params: Record<string, unknown>; metrics: Metrics; }
```

**`frontend/src/types/data.ts`**:
```typescript
interface OHLCVCandle { timestamp: string; open: number; high: number; low: number; close: number; volume: number; }
interface OHLCVResponse { symbol: string; timeframe: string; candles: OHLCVCandle[]; }
interface IndicatorPoint { timestamp: string; value: number; }
interface IndicatorResponse { symbol: string; timeframe: string; indicators: Record<string, IndicatorPoint[]>; }
```

**`frontend/src/types/risk.ts`**:
```typescript
interface BetaResult { symbol: string; beta: number; r_squared: number; tracking_error: number; }
interface CorrelationResult { timestamp: string; window_days: number; symbols: string[]; correlation_matrix: number[][]; sector_matrix?: { rows: string[]; matrix: number[][] } | null; high_correlation_pairs: Array<{ symbols: [string, string]; correlation: number }>; diversification_score: number; }
interface VaRResult { var: number; cvar: number; confidence: number; method: string; }
interface PositionSizeRequest { symbols: string[]; method: 'atr' | 'kelly' | 'fixed'; cash: number; params: Record<string, unknown>; }
interface PositionSizeResult { sizes: Record<string, number>; method: string; cash: number; }
interface KellyRequest { backtest_run_id: string; max_dd_target: number; }
interface KellyResult { kelly_pct: number; half_kelly_pct: number; edge: number; odds: number; }
interface RiskSummary { portfolio_id: string; num_positions: number; total_exposure: number; var_95: number; cvar_95: number; beta_weighted: number; diversification_score: number; }
```

**`frontend/src/types/ws.ts`**:
```typescript
type ConnectionState = 'connecting' | 'connected' | 'disconnected' | 'reconnecting';
type WSChannelType = 'price' | 'indicator' | 'signal' | 'screener' | 'risk' | 'backtest';
interface WSSubscriptionMessage { type: 'subscribe' | 'unsubscribe'; channels: string[]; }
interface WSConnectedMessage { type: 'connected'; connection_id: string; timestamp: string; server_version: string; }
interface WSPriceUpdate { type: 'price_update'; channel: string; sequence: number; timestamp: string; data: { symbol: string; price: number; change_pct: number; volume: number; timestamp: string; }; }
interface WSIndicatorUpdate { type: 'indicator_update'; channel: string; sequence: number; data: { symbol: string; indicator: string; value: number; timestamp: string; }; }
interface WSScreenUpdate { type: 'screen_update'; channel: string; sequence: number; data: { screen_name: string; total_matched: number; total_symbols: number; symbols: ScreenSymbolResult[]; }; }
interface WSBacktestUpdate { type: 'backtest_update'; channel: string; sequence: number; data: { run_id: string; status: 'running' | 'complete' | 'error'; progress_pct: number; message: string; }; }
interface WSMessage = WSConnectedMessage | WSPriceUpdate | WSIndicatorUpdate | WSScreenUpdate | WSBacktestUpdate | { type: 'error' | 'pong' | 'resync_required'; [key: string]: unknown; };
```
</action>

<acceptance_criteria>
- `frontend/src/types/api.ts` exports `ApiResponse<T>`, `MetaInfo`, `ApiErrorResponse`, `ErrorDetail`
- `frontend/src/types/screener.ts` exports `ScreenRequest`, `ScreenSymbolResult`, `SymbolInfo`
- `frontend/src/types/backtest.ts` exports `BacktestRequest`, `BacktestResultData`, `Metrics`, `Trade`, `EquityPoint`, `OptimizationResult`
- `frontend/src/types/data.ts` exports `OHLCVCandle`, `OHLCVResponse`, `IndicatorPoint`, `IndicatorResponse`
- `frontend/src/types/risk.ts` exports `BetaResult`, `CorrelationResult`, `VaRResult`, `PositionSizeRequest`, `PositionSizeResult`, `KellyRequest`, `KellyResult`, `RiskSummary`
- `frontend/src/types/ws.ts` exports `ConnectionState`, `WSChannelType`, `WSMessage`, and all WS message interfaces
- `npx tsc --noEmit` produces zero errors in the types directory
</acceptance_criteria>

---

### Task 1.3: Create API Client Layer (Axios + TanStack Query Endpoints)

<read_first>
- `frontend/src/types/api.ts`, `screener.ts`, `backtest.ts`, `data.ts`, `risk.ts` (from Task 1.2)
- `.planning/phases/07-frontend-core/07-RESEARCH.md` section 5.1 (Axios instance, TanStack Query patterns)
- `.planning/phases/07-frontend-core/07-RESEARCH.md` section 7.1 (cache configuration table)
- `backend/app/api/schemas.py` — All endpoint models for accurate type mapping
</read_first>

<action>
1. Create `frontend/src/api/client.ts`:
   - Axios instance with `baseURL: import.meta.env.VITE_API_BASE_URL || ''`, `timeout: 30000`, JSON content type
   - Request interceptor: add `X-Request-ID` header via `crypto.randomUUID()`
   - Response interceptor: unwrap `response.data`, transform errors to `ApiErrorResponse.error` shape
   - Export `apiClient` as default

2. Create `frontend/src/api/screener.ts`:
   - `fetchScreen(config: string, symbols?: string[], timeframes?: string[]): Promise<ScreenSymbolResult[]>` — POST `/api/v1/screen`
   - `fetchSymbols(assetClass?: string, activeOnly?: boolean): Promise<SymbolInfo[]>` — GET `/api/v1/data/symbols`

3. Create `frontend/src/api/backtest.ts`:
   - `runBacktest(body: BacktestRequest): Promise<BacktestResultData>` — POST `/api/v1/backtest`
   - `fetchBacktest(runId: string): Promise<BacktestResultData>` — GET `/api/v1/backtest/{runId}`
   - `fetchTrades(runId: string): Promise<Trade[]>` — GET `/api/v1/backtest/{runId}/trades`
   - `fetchEquity(runId: string): Promise<EquityPoint[]>` — GET `/api/v1/backtest/{runId}/equity`

4. Create `frontend/src/api/data.ts`:
   - `fetchOHLCV(symbol: string, timeframe: string, start?: string, end?: string, limit?: number): Promise<OHLCVCandle[]>` — GET `/api/v1/data/{symbol}`
   - `fetchIndicators(symbol: string, timeframe: string, indicators?: string, limit?: number): Promise<IndicatorResponse>` — GET `/api/v1/indicators/{symbol}`

5. Create `frontend/src/api/risk.ts`:
   - `fetchBeta(symbols: string[], benchmark?: string, window?: number): Promise<BetaResult[]>` — GET `/api/v1/risk/beta`
   - `fetchCorrelation(symbols: string[], window?: number, groupBy?: string): Promise<CorrelationResult>` — GET `/api/v1/risk/correlation`
   - `fetchVaR(symbols: string[], confidence?: number, method?: string, horizon?: number): Promise<VaRResult>` — GET `/api/v1/risk/var`
   - `postPositionSize(body: PositionSizeRequest): Promise<PositionSizeResult>` — POST `/api/v1/risk/position-size`
   - `postKelly(body: KellyRequest): Promise<KellyResult>` — POST `/api/v1/risk/kelly`
   - `fetchRiskSummary(portfolioId?: string, symbols?: string[]): Promise<RiskSummary>` — GET `/api/v1/risk/summary`
</action>

<acceptance_criteria>
- `frontend/src/api/client.ts` exports Axios instance with request interceptor adding `X-Request-ID`
- `frontend/src/api/screener.ts` exports `fetchScreen` (POST) and `fetchSymbols` (GET)
- `frontend/src/api/backtest.ts` exports `runBacktest` (POST), `fetchBacktest`, `fetchTrades`, `fetchEquity` (GET)
- `frontend/src/api/data.ts` exports `fetchOHLCV` and `fetchIndicators` (GET)
- `frontend/src/api/risk.ts` exports `fetchBeta`, `fetchCorrelation`, `fetchVaR` (GET), `postPositionSize`, `postKelly` (POST)
- Each function returns correctly typed Promise based on the types in Task 1.2
- `npx tsc --noEmit` produces zero errors in the api directory
</acceptance_criteria>

---

### Task 1.4: Create WebSocket Layer (Singleton Hook + Channel Management)

<read_first>
- `backend/app/api/ws/handler.py` — Full WebSocket protocol (auth, connected, subscribe, unsubscribe, ping, resync)
- `backend/app/api/ws/manager.py` — Manager behavior for subscription handling
- `backend/app/api/ws/channels.py` — Channel constants and provider functions
- `frontend/src/types/ws.ts` (from Task 1.2)
- `.planning/phases/07-frontend-core/07-RESEARCH.md` sections 4.1-4.5, 8.1-8.4 (full WS protocol details)
</read_first>

<action>
1. Create `frontend/src/ws/useWebSocket.ts`:
   - Singleton hook managing a single WebSocket connection
   - **State:** `connectionState: ConnectionState`, managed via `useState` (default `'disconnected'`)
   - **connect():** Create `WebSocket(url)`, set `onopen` → state to `'connected'`, reset reconnect attempts, resubscribe to all channels, send `resync` with stored sequences. `onmessage` → parse JSON, dispatch to registered handlers. `onclose` → state to `'disconnected'`, `scheduleReconnect()`. `onerror` → `ws.close()`
   - **scheduleReconnect():** Exponential backoff: `min(1000 * 2^attempt, 30000)`ms. Increment `reconnectAttemptRef`. Set state to `'reconnecting'`. Call `connect()` after delay.
   - **subscribe(channel):** Add to `subscriptionsRef` Set, send `{type: "subscribe", channels: [channel]}` if connected
   - **unsubscribe(channel):** Remove from `subscriptionsRef`, send `{type: "unsubscribe", channels: [channel]}` if connected
   - **send(data):** Send JSON if connected
   - **onMessage(handler):** Register message handler. Return unsubscribe function.
   - **lastSequence:** Store per-channel sequence numbers via localStorage key `ws_sequences`
   - Cleanup on unmount: close WS, clear timeouts
   - Export `useWebSocket` as default

2. Create `frontend/src/ws/WebSocketProvider.tsx`:
   - React context providing WS state and actions
   - `WSContext` with `{ connectionState, subscribe, unsubscribe, send, onMessage }`
   - `WebSocketProvider` component that calls `useWebSocket(url)` and wraps children in context
   - `useWS()` hook to consume context (throw if used outside provider)

3. Create `frontend/src/ws/channels.ts`:
   - Helper functions for channel name construction:
     - `priceChannel(symbol: string)` → `"price:{symbol}"`
     - `indicatorChannel(symbol: string, name: string)` → `"indicator:{symbol}:{name}"`
     - `signalChannel(symbol: string)` → `"signal:{symbol}"`
     - `screenerChannel(name: string)` → `"screener:{name}"`
     - `riskChannel(portfolioId: string)` → `"risk:{portfolioId}"`
     - `backtestChannel(runId: string)` → `"backtest:{runId}"`
   - `parseChannel(channel: string): { type: WSChannelType; params: string[] }` — Extract type and params from channel string
   - Sequence number persistence: `getStoredSequences()` (from localStorage), `storeSequence(channel, seq)` (to localStorage)
</action>

<acceptance_criteria>
- `frontend/src/ws/useWebSocket.ts` exports default hook with state, subscribe, unsubscribe, send, onMessage
- Exponential backoff formula: `Math.min(1000 * Math.pow(2, attempt), 30000)`
- `frontend/src/ws/WebSocketProvider.tsx` exports `WebSocketProvider` and `useWS()` hook
- `frontend/src/ws/channels.ts` exports `priceChannel()`, `indicatorChannel()`, `screenerChannel()`, `riskChannel()`, `backtestChannel()`, `parseChannel()`
- Sequence numbers persisted to localStorage key `ws_sequences`
- `npx tsc --noEmit` produces zero errors in the ws directory
</acceptance_criteria>

---

## Wave 2: Layout, State Management & Shared Hooks

**Wave goal:** Build the app shell (sidebar, header, routing), Zustand stores for all client state, and shared hooks. This wave depends on Wave 1 being complete (types, API client, WS).

**Dependencies:** Wave 1 complete

### Task 2.1: Create Zustand Stores

<read_first>
- `.planning/phases/07-frontend-core/07-RESEARCH.md` sections 5.4, 7.2 (Zustand patterns, store split)
- `frontend/src/types/screener.ts`, `backtest.ts`, `risk.ts` (for store type references)
- `config.yaml` — `screen` section for default config name, `compute.default_indicator_timeframe`
</read_first>

<action>
1. Create `frontend/src/store/screen.ts`:
   - `useScreenStore` with persisted Zustand middleware
   - **State:** `selectedConfig: string = 'trend-follower'`, `timeframes: string[] = ['1D', '4h']`, `columnVisibility: Record<string, boolean> = {}`, `columnOrder: string[] = []`
   - **Actions:** `setConfig(config)`, `setTimeframes(timeframes)`, `toggleColumn(column)`, `setColumnOrder(order)`
   - Persist key: `screen-store`

2. Create `frontend/src/store/chart.ts`:
   - `useChartStore` with persisted Zustand middleware
   - **State:** `selectedSymbol: string = 'AAPL'`, `activeTimeframes: string[] = ['1D', '4H', '1H', '15m']`, `activeIndicators: string[] = ['rsi', 'macd', 'ema_20', 'bb']`, `chartLayout: 'grid' | 'stacked' = 'grid'`
   - **Actions:** `setSymbol(symbol)`, `toggleTimeframe(tf)`, `toggleIndicator(name)`, `setChartLayout(layout)`
   - Persist key: `chart-store`

3. Create `frontend/src/store/backtest.ts`:
   - `useBacktestStore` with persisted Zustand middleware
   - **State:** `recentRunIds: string[] = []` (max 10), `selectedRunId: string | null = null`, `tradeFilter: { symbol?: string; dateRange?: [string, string]; direction?: 'Long' | 'Short' } = {}`
   - **Actions:** `addRunId(runId)`, `setSelectedRunId(runId)`, `setTradeFilter(filter)`, `clearTradeFilter()`
   - Persist key: `backtest-store`

4. Create `frontend/src/store/risk.ts`:
   - `useRiskStore` with persisted Zustand middleware
   - **State:** `selectedSymbols: string[] = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA']`, `activeView: 'correlation' | 'position-size' | 'beta' | 'var' = 'correlation'`, `varConfidence: number = 0.95`, `varMethod: 'historical' | 'parametric' | 'monte_carlo' = 'historical'`
   - **Actions:** `setSymbols(symbols)`, `setActiveView(view)`, `setVarConfidence(confidence)`, `setVarMethod(method)`
   - Persist key: `risk-store`

5. Create `frontend/src/store/ui.ts`:
   - `useUIStore` (no persistence — UI transient state)
   - **State:** `sidebarOpen: boolean = true`, `activeView: 'screener' | 'charts' | 'backtest' | 'risk' = 'screener'`, `theme: 'dark' | 'light' = 'dark'`
   - **Actions:** `toggleSidebar()`, `setActiveView(view)`, `setTheme(theme)`
</action>

<acceptance_criteria>
- `frontend/src/store/screen.ts` exports `useScreenStore` with `selectedConfig`, `timeframes`, `columnVisibility`, and corresponding actions
- `frontend/src/store/chart.ts` exports `useChartStore` with `selectedSymbol`, `activeTimeframes`, `activeIndicators`, and corresponding actions
- `frontend/src/store/backtest.ts` exports `useBacktestStore` with `recentRunIds` (max 10), `selectedRunId`, `tradeFilter`, and actions
- `frontend/src/store/risk.ts` exports `useRiskStore` with `selectedSymbols`, `activeView`, `varConfidence`, `varMethod`, and actions
- `frontend/src/store/ui.ts` exports `useUIStore` with `sidebarOpen`, `activeView`, `theme`, and actions
- Three stores (screen, chart, backtest, risk) use `persist` middleware from `zustand/middleware`
- `npx tsc --noEmit` produces zero errors in the store directory
</acceptance_criteria>

---

### Task 2.2: Create Shared Hooks

<read_first>
- `frontend/src/types/ws.ts` — WS connection state type
- `.planning/phases/07-frontend-core/07-RESEARCH.md` sections 6.6 (layout architecture), 5.3 (chart sync approach)
</read_first>

<action>
1. Create `frontend/src/hooks/useKeyboard.ts`:
   - `useKeyboard(keymap: Record<string, () => void>)` hook
   - Listen for `keydown` events, match against keymap, prevent default for matched keys
   - Register event listener on mount, cleanup on unmount
   - Support special keys: `?`, `/`, `Escape`, `ArrowUp`, `ArrowDown`

2. Create `frontend/src/hooks/useResizeObserver.ts`:
   - `useResizeObserver(ref: RefObject<HTMLElement>)` hook
   - Return `{ width: number; height: number }`
   - Use `ResizeObserver` API. Update on resize. Cleanup on unmount.
   - Initial values: `width: 0, height: 0`

3. Create `frontend/src/hooks/useSynchronizedCharts.ts`:
   - `useSynchronizedCharts(chartRefs: Map<string, IChartApi>)` hook
   - **Master chart pattern:** First entry in map is master, rest are slaves
   - Master chart: subscribe to `subscribeCrosshairMove`, subscribe to `timeScale().subscribeVisibleTimeRangeChange()`
   - On crosshair move: call `setCrosshairPosition(param.point, param.time)` on all slave charts
   - On visible time range change: call `timeScale().setVisibleRange(range)` on all slave charts
   - Throttle synchronization events to 60fps via `requestAnimationFrame`
   - Cleanup on unmount: unsubscribe all subscriptions
</action>

<acceptance_criteria>
- `frontend/src/hooks/useKeyboard.ts` exports `useKeyboard(keymap)` that registers `keydown` listeners
- `frontend/src/hooks/useResizeObserver.ts` exports `useResizeObserver(ref)` returning `{ width, height }`
- `frontend/src/hooks/useSynchronizedCharts.ts` exports `useSynchronizedCharts(chartRefs)` with master/slave crosshair + time sync
- Uses `requestAnimationFrame` for throttling chart sync events
- `npx tsc --noEmit` produces zero errors in the hooks directory
</acceptance_criteria>

---

### Task 2.3: Create Shared UI Utilities

<read_first>
- `.planning/phases/07-frontend-core/07-RESEARCH.md` sections 6.1 (lib directory), 5.5 (colors, format patterns)
- `config.yaml` — Timeframes list, frontend.chart_config section
</read_first>

<action>
1. Create `frontend/src/lib/cn.ts`:
   - Export `cn()` function using `clsx` + `tailwind-merge` pattern:
     ```typescript
     import { clsx, type ClassValue } from 'clsx';
     import { twMerge } from 'tailwind-merge';
     export function cn(...inputs: ClassValue[]): string { return twMerge(clsx(inputs)); }
     ```

2. Create `frontend/src/lib/constants.ts`:
   - `TIMEFRAMES = ['1D', '4H', '1H', '15m'] as const`
   - `INDICATOR_COLORS = { rsi: '#7B68EE', macd: '#22C55E', ema_20: '#F59E0B', ema_50: '#EF4444', bb_upper: '#60A5FA', bb_lower: '#60A5FA', atr: '#EC4899' } as const`
   - `SCREEN_TEMPLATES = ['trend-follower', 'momentum-breakout', 'mean-reversion', 'high-volume', 'low-volatility'] as const`
   - `ASSET_CLASSES = ['equities', 'crypto', 'forex', 'commodities', 'indices'] as const`
   - `WS_URL = 'ws://localhost:8000/ws/stream'`
   - `STALE_TIMES = { screen: 5000, ohlcv: 30000, indicators: 10000, backtest: Infinity, risk: 30000, symbols: Infinity }`

3. Create `frontend/src/lib/format.ts`:
   - `formatPrice(value: number, decimals?: number): string` — `$123.45` for equities, `$1,234.56` format
   - `formatPct(value: number): string` — `+12.34%` or `-5.67%`
   - `formatPnL(value: number): string` — `+$1,234.56` or `-$567.89`
   - `formatDate(isoString: string): string` — `2026-06-19`
   - `formatDateTime(isoString: string): string` — `2026-06-19 14:30:00`
   - `formatNumber(value: number, decimals?: number): string` — `1,234.56` with commas
   - `formatLargeNumber(value: number): string` — `1.2M`, `3.4B`
</action>

<acceptance_criteria>
- `frontend/src/lib/cn.ts` exports `cn()` using `clsx` + `twMerge`
- `frontend/src/lib/constants.ts` exports `TIMEFRAMES` (4 values), `INDICATOR_COLORS` (9 colors), `SCREEN_TEMPLATES` (5 templates), `STALE_TIMES` (6 entries)
- `frontend/src/lib/format.ts` exports `formatPrice`, `formatPct`, `formatPnL`, `formatDate`, `formatDateTime`, `formatNumber`, `formatLargeNumber`
- `formatPct(12.34)` produces `"+12.34%"`, `formatPnL(-567.89)` produces `"-$567.89"`
- `npx tsc --noEmit` produces zero errors in the lib directory
</acceptance_criteria>

---

### Task 2.4: Create Layout Components (AppShell, Sidebar, Header, ErrorBoundary)

<read_first>
- `.planning/phases/07-frontend-core/07-RESEARCH.md` section 6.6 (layout architecture diagram)
- `frontend/src/store/ui.ts` (from Task 2.1)
- `frontend/src/ws/WebSocketProvider.tsx` (from Task 1.4)
</read_first>

<action>
1. Create `frontend/src/components/layout/AppShell.tsx`:
   - **Structure:** `<div className="flex h-screen bg-dark-800">` → Sidebar (left) + `<div className="flex flex-col flex-1">` → Header (top) + Main Content (`<Outlet />`)
   - Responsive: Sidebar hides on screens < 1280px (use `hidden lg:flex`)
   - Uses `useUIStore` for `sidebarOpen` state

2. Create `frontend/src/components/layout/Sidebar.tsx`:
   - **Nav items:** Screener (icon: grid/table), Charts (icon: bar-chart), Backtest (icon: trending-up), Risk (icon: shield)
   - **Active state:** Highlight current route via `useLocation()`, use `accent` color for active
   - **Styling:** `w-56 bg-dark-900 border-r border-dark-600 p-4`, nav items: `flex items-center gap-2 p-2 rounded hover:bg-dark-500 transition-colors`
   - Use `react-router-dom` `NavLink` for each route
   - **Connection indicator:** Small colored dot at bottom: green = connected, red = disconnected, yellow = reconnecting (from `useWS()`)

3. Create `frontend/src/components/layout/Header.tsx`:
   - **Content:** App title "conflu.ai" (left), global search input (center), connection status badge (right)
   - **Search input:** Placeholder "Search symbols... (/)", keyboard shortcut `/` focuses it, `Escape` blurs
   - **Connection status:** Badge showing "Connected" / "Disconnected" / "Reconnecting..." with colored dot, via `useWS()` hook
   - **Styling:** `h-14 bg-dark-900 border-b border-dark-600 px-4 flex items-center gap-4`

4. Create `frontend/src/components/layout/ErrorBoundary.tsx`:
   - Class component implementing `componentDidCatch` and `getDerivedStateFromError`
   - **Props:** `fallback?: ReactNode` (optional custom fallback), `onError?: (error: Error, errorInfo: ErrorInfo) => void`
   - **State:** `{ hasError: boolean; error: Error | null }`
   - **Default fallback:** Centered card with error icon, message, and "Try Again" button that calls `setState({ hasError: false })`
   - **Styling:** `flex items-center justify-center h-full bg-dark-800 text-dark-50`

5. Create `frontend/src/components/layout/LoadingSkeleton.tsx`:
   - Generic loading skeleton with `className` prop
   - Animated pulse: `animate-pulse bg-dark-500 rounded`
   - **Sub-components:** `SkeletonLine` (full-width bar), `SkeletonCard` (card with multiple lines), `SkeletonTable` (header + rows)
</action>

<acceptance_criteria>
- `frontend/src/components/layout/AppShell.tsx` renders Sidebar + Header + `<Outlet />` in flex layout
- `frontend/src/components/layout/Sidebar.tsx` renders 4 NavLink items (Screener, Charts, Backtest, Risk) with connection indicator dot at bottom
- `frontend/src/components/layout/Header.tsx` shows "conflu.ai" title, search input with `/` shortcut, connection status badge
- `frontend/src/components/layout/ErrorBoundary.tsx` catches errors, shows fallback with "Try Again" button
- `frontend/src/components/layout/LoadingSkeleton.tsx` exports `SkeletonLine`, `SkeletonCard`, `SkeletonTable`
- `npx tsc --noEmit` produces zero errors in layout directory
</acceptance_criteria>

---

## Wave 3: Screener & Charts Modules

**Wave goal:** Build the screener table with virtualization and real-time updates, and the multi-timeframe synchronized charts module.

**Dependencies:** Wave 2 complete

### Task 3.1: Create Screener Page and Screen Selector

<read_first>
- `.planning/phases/07-frontend-core/07-RESEARCH.md` section 6.2 (screener data flow)
- `frontend/src/api/screener.ts` (from Task 1.3)
- `frontend/src/store/screen.ts` (from Task 2.1)
- `frontend/src/types/screener.ts` (from Task 1.2)
</read_first>

<action>
1. Create `frontend/src/components/screener/ScreenerPage.tsx`:
   - **Page layout:** `<div className="flex flex-col h-full">` → toolbar (ScreenSelector + ColumnToggle + ExportButtons) + ScreenerTable (fills remaining space)
   - **TanStack Query:** `useQuery({ queryKey: ['screen', selectedConfig], queryFn: () => fetchScreen(selectedConfig, undefined, timeframes), staleTime: STALE_TIMES.screen, refetchInterval: 30_000 })`
   - **WS integration:** Subscribe to `screener:{selectedConfig}` channel on mount. On `screen_update` WS message, update query cache via `queryClient.setQueryData()` with delta merge (Strategy B from research: merge `ScreenSymbolResult[]` by symbol — update matching symbols in-place, add new ones, preserve unmatched)
   - **Symbols query:** `useQuery({ queryKey: ['symbols'], queryFn: fetchSymbols, staleTime: STALE_TIMES.symbols })` for dropdown autocomplete
   - Loading state: Show `SkeletonTable`
   - Error state: Show ErrorBoundary fallback
   - Empty state: "No results. Try a different screen configuration."

2. Create `frontend/src/components/screener/ScreenSelector.tsx`:
   - `<select>` dropdown populated from `SCREEN_TEMPLATES` constant
   - On change: call `useScreenStore.setConfig(value)` which triggers TanStack Query refetch
   - **Styling:** `bg-dark-600 border border-dark-400 rounded px-3 py-1.5 text-sm text-dark-50`
   - Show current selected config name

3. Create `frontend/src/components/screener/ColumnToggle.tsx`:
   - Dropdown button showing "Columns" label with active count
   - Click opens a popover panel with checkbox list of all column names
   - Checkbox toggle calls `useScreenStore.toggleColumn(column)`
   - Search input at top to filter column list
   - Close on Escape or click outside
   - **Styling:** Dropdown panel: `absolute top-full right-0 mt-1 bg-dark-700 border border-dark-500 rounded shadow-lg p-2 w-56 max-h-80 overflow-y-auto z-50`

4. Create `frontend/src/components/screener/ExportButtons.tsx`:
   - Two buttons: "Export CSV" and "Export JSON"
   - On click: call `fetchScreen(config, undefined, timeframes, export_format)` with export format
   - Handle response: Create Blob, trigger download via `URL.createObjectURL()`
   - Show loading state on export button while fetching
   - **Styling:** `flex gap-2`, buttons: `px-3 py-1.5 text-sm rounded bg-dark-600 hover:bg-dark-500`
</action>

<acceptance_criteria>
- `frontend/src/components/screener/ScreenerPage.tsx` uses `useQuery(['screen', ...])` to fetch screen data, subscribes to WS `screener:*` channel
- WS delta merge updates query cache via `queryClient.setQueryData()` — matching symbols updated, new symbols added
- Loading state shows `SkeletonTable`, error state shows fallback, empty state shows "No results" message
- `frontend/src/components/screener/ScreenSelector.tsx` renders `<select>` with 5 options from `SCREEN_TEMPLATES`
- `frontend/src/components/screener/ColumnToggle.tsx` renders popover with search input and checkbox list
- `frontend/src/components/screener/ExportButtons.tsx` renders "Export CSV" and "Export JSON" buttons that trigger file download
- `npx tsc --noEmit` produces zero errors in screener directory
</acceptance_criteria>

---

### Task 3.2: Create Virtualized Screener Table

<read_first>
- `.planning/phases/07-frontend-core/07-RESEARCH.md` sections 5.2 (TanStack Virtual API), 6.2 (table data flow)
- `frontend/src/types/screener.ts` — `ScreenSymbolResult` with `indicator_values: Record<string, number>`
- `frontend/src/store/screen.ts` — Column visibility and order
</read_first>

<action>
1. Create `frontend/src/components/screener/ScreenerTable.tsx`:
   - **TanStack Virtual:** Use `useVirtualizer` with `estimateSize: () => 48`, `overscan: 5`
   - **Parent ref:** Wrap table in scrollable `<div ref={parentRef}>` with `overflow: auto` and `flex-1`
   - **Structure:**
     ```
     <div ref={parentRef} className="flex-1 overflow-auto">
       <table className="w-full">
         <thead className="sticky top-0 z-20 bg-dark-700">
           <tr>{columns.map(col => <ColumnHeader key={col.key} column={col} />)}</tr>
         </thead>
         <tbody style={{ position: 'relative', height: `${virtualizer.getTotalSize()}px` }}>
           {virtualizer.getVirtualItems().map(virtualRow => (
             <ScreenerRow key={virtualRow.key} data={rows[virtualRow.index]} style={{ transform: `translateY(${virtualRow.start}px)` }} columns={visibleColumns} />
           ))}
         </tbody>
       </table>
     </div>
     ```
   - **Columns:** Dynamically built from `ScreenSymbolResult` keys: `symbol`, `score`, `matched_filters`, plus all keys from `indicator_values`
   - **Sorting:** Click column header to sort asc/desc. Show sort indicator (▲/▼). Maintain sort state locally via `useState`. Sort data clientside before passing to virtualizer.
   - **Frozen symbol column:** `sticky left-0 z-10 bg-dark-700` CSS on symbol column header and cells
   - **Styling:** `table-layout: fixed`, cells: `px-3 py-2 text-sm border-b border-dark-600 whitespace-nowrap`
   - **Hover tooltip:** On indicator value cells, show tooltip with indicator description

2. Create `frontend/src/components/screener/ScreenerRow.tsx`:
   - `React.memo` wrapped component for performance
   - Props: `data: ScreenSymbolResult`, `style: React.CSSProperties`, `columns: ColumnDef[]`
   - Render each column cell based on type: number → `formatPrice`/`formatPct`, string → direct, array → join with `, `
   - Color code score: `score >= 80 ? 'text-gain' : score >= 50 ? 'text-yellow-400' : 'text-dark-200'`
   - Apply `style` for absolute positioning from virtualizer

3. Create `frontend/src/components/screener/ColumnHeader.tsx`:
   - Clickable header cell with column name and sort indicator
   - Props: `column: { key: string; label: string }`, `sortKey: string | null`, `sortDir: 'asc' | 'desc' | null`, `onSort: (key: string) => void`
   - On click: call `onSort(column.key)`. Cycle: none → asc → desc → none
   - Show ▲ when sorted asc, ▼ when sorted desc
</action>

<acceptance_criteria>
- `frontend/src/components/screener/ScreenerTable.tsx` uses `useVirtualizer({ count, getScrollElement, estimateSize: () => 48, overscan: 5 })`
- Columns are dynamically built from `ScreenSymbolResult` keys + `indicator_values` keys
- Frozen symbol column uses `sticky left-0 z-10 bg-dark-700` CSS
- Sorting cycles through none → asc → desc → none on column header click
- `frontend/src/components/screener/ScreenerRow.tsx` is wrapped in `React.memo`, applies `style.transform` for virtual positioning
- `frontend/src/components/screener/ColumnHeader.tsx` shows sort direction indicator (▲/▼)
- `npx tsc --noEmit` produces zero errors
</acceptance_criteria>

---

### Task 3.3: Create Charts Page and Symbol Search

<read_first>
- `.planning/phases/07-frontend-core/07-RESEARCH.md` section 6.3 (charts data flow)
- `frontend/src/api/data.ts` (from Task 1.3)
- `frontend/src/store/chart.ts` (from Task 2.1)
- `frontend/src/types/data.ts` (from Task 1.2)
</read_first>

<action>
1. Create `frontend/src/components/charts/ChartsPage.tsx`:
   - **Layout:** Top toolbar (SymbolSearch + ChartToolbar) + chart grid below
   - **Data fetching:** For each active timeframe in `useChartStore.activeTimeframes`, use `useQuery` with key `['ohlcv', symbol, { timeframe }]` calling `fetchOHLCV(symbol, timeframe)`. For each active indicator, use `useQuery` with key `['indicators', symbol, { timeframe, indicators }]` calling `fetchIndicators(symbol, timeframe, indicatorName)`
   - **Error boundary:** Wrap in `<ErrorBoundary>` with chart-specific fallback
   - **Loading:** Show `ChartSkeleton` for each chart in grid
   - **WS integration:** Subscribe to `indicator:{symbol}:*` channels on page mount. On `indicator_update` WS message, call `chartSeries.update(latestPoint)` on the corresponding chart instance
   - Render timeframe selector (1D, 4H, 1H, 15m) — clicking toggles visibility via `useChartStore.toggleTimeframe()`

2. Create `frontend/src/components/charts/SymbolSearch.tsx`:
   - Search input with autocomplete dropdown
   - On mount, fetch symbols via `useQuery(['symbols'], fetchSymbols)`
   - Filter symbols by input text (match `symbol` or `name` fields)
   - Show top 10 matching results in dropdown
   - On select: call `useChartStore.setSymbol(selectedSymbol)`
   - **Keyboard:** Arrow keys navigate results, Enter selects, Escape closes
   - **Styling:** `relative`, input: `bg-dark-600 border border-dark-400 rounded px-3 py-1.5 w-64 text-sm`, dropdown: `absolute top-full left-0 mt-1 w-64 bg-dark-700 border border-dark-500 rounded shadow-lg z-50`

3. Create `frontend/src/components/charts/ChartToolbar.tsx`:
   - **Indicator toggle buttons:** RSI, MACD, EMA 20, BB — each as toggle chip
   - Active indicators highlighted with `accent` color
   - On click: `useChartStore.toggleIndicator(name)`
   - **Timeframe checkboxes:** 1D, 4H, 1H, 15m — toggle chart visibility
</action>

<acceptance_criteria>
- `frontend/src/components/charts/ChartsPage.tsx` fetches OHLCV data for each active timeframe via `useQuery(['ohlcv', symbol, { timeframe }])`
- Fetches indicator data for each active indicator via `useQuery(['indicators', symbol, { timeframe, indicators }])`
- Subscribes to `indicator:{symbol}:*` WS channels, calls `chartSeries.update()` on updates
- `frontend/src/components/charts/SymbolSearch.tsx` filters by `symbol` and `name`, shows top 10 in dropdown, navigable with arrow keys
- `frontend/src/components/charts/ChartToolbar.tsx` renders toggleable indicator chips and timeframe checkboxes
- `npx tsc --noEmit` produces zero errors
</acceptance_criteria>

---

### Task 3.4: Create Multi-Timeframe Chart Panes

<read_first>
- `.planning/phases/07-frontend-core/07-RESEARCH.md` section 5.3 (Lightweight Charts v5 API, series types, multi-pane)
- `frontend/src/store/chart.ts` — activeTimeframes, activeIndicators
- `frontend/src/types/data.ts` — OHLCVCandle, IndicatorPoint
- `frontend/src/hooks/useSynchronizedCharts.ts` (from Task 2.2)
- `frontend/src/hooks/useResizeObserver.ts` (from Task 2.2)
</read_first>

<action>
1. Create `frontend/src/components/charts/ChartPane.tsx`:
   - **Props:** `timeframe: string`, `symbol: string`, `isMaster: boolean`, `onChartReady: (tf: string, chart: IChartApi) => void`
   - **Create chart:** On mount, `createChart(containerRef.current, { ... })` with dark theme config:
     - `layout: { background: { color: '#1a1a2e' }, textColor: '#d1d4dc' }`
     - `grid: { vertLines: { color: '#2a2a3e' }, horzLines: { color: '#2a2a3e' } }`
     - `crosshair: { mode: CrosshairMode.Normal }`
     - `timeScale: { borderColor: '#2a2a3e', timeVisible: true }`
     - `rightPriceScale: { borderColor: '#2a2a3e' }`
   - **Candlestick series:** `chart.addSeries(CandlestickSeries, { upColor: '#22C55E', downColor: '#EF4444', borderVisible: false, wickUpColor: '#22C55E', wickDownColor: '#EF4444' })`. Call `.setData(candles)` where candles are mapped from OHLCVCandle[] with `{ time: timestamp/1000 as unix, open, high, low, close }` format
   - **Volume series:** `chart.addSeries(HistogramSeries, { color: '#60A5FA', priceFormat: { type: 'volume' } }, volumePane)` on separate pane
   - **Indicator series:** For each active indicator, add appropriate series:
     - RSI: `chart.addSeries(LineSeries, { color: '#7B68EE', lineWidth: 2 }, rsiPane)` on separate pane
     - MACD: `chart.addSeries(LineSeries, { color: '#22C55E' }, macdPane)` + signal line
     - EMA: `chart.addSeries(LineSeries, { color: '#F59E0B', lineWidth: 1 })` overlay on main pane
     - BB: `chart.addSeries(LineSeries, { color: '#60A5FA', lineStyle: 2 })` upper/lower overlay
   - **Resize handling:** Use `useResizeObserver(containerRef)`. On resize, call `chart.resize(width, height)`. Set height: `300px` per chart, or `400px` for master 1D
   - **Cleanup:** On unmount, call `chart.remove()`. On symbol change, call `.setData(newCandles)` or `.update(latestCandle)`
   - **Time scale format:** Use `chart.timeScale().applyOptions({ tickMarkFormatter: ... })` for proper date formatting
   - Report chart ready via `onChartReady(timeframe, chart)` for crosshair synchronization

2. Create `frontend/src/components/charts/ChartSkeleton.tsx`:
   - Placeholder while chart data is loading
   - Dark background (`bg-dark-800`) with animated pulse lines mimicking candlestick shapes
   - Height matches chart pane (300px)
</action>

<acceptance_criteria>
- `frontend/src/components/charts/ChartPane.tsx` calls `createChart()` with dark theme config (background `#1a1a2e`, text `#d1d4dc`)
- Adds `CandlestickSeries` with upColor `#22C55E` and downColor `#EF4444`
- Adds indicator series on separate panes: RSI line, MACD line, EMA overlay, BB overlay
- Calls `chart.resize(width, height)` on container resize via `useResizeObserver`
- Uses `subscribeCrosshairMove` to report to parent for synchronization
- `ChartSkeleton.tsx` renders animated pulse placeholder matching chart dimensions
- `npx tsc --noEmit` produces zero errors
</acceptance_criteria>

---

### Task 3.5: Create Indicator Panel

<read_first>
- `config.yaml` — frontend.chart_config.indicators list
- `.planning/phases/07-frontend-core/07-RESEARCH.md` section 6.3 (indicator panel in component tree)
</read_first>

<action>
1. Create `frontend/src/components/charts/IndicatorPanel.tsx`:
   - **Side panel** showing values for each active indicator at the current crosshair position
   - **Props:** `symbol: string`, `indicatorValues: Record<string, number | null>`
   - **Display:** For each indicator in `useChartStore.activeIndicators`, show:
     - Name (e.g., "RSI (14)")
     - Current value (formatted to 2 decimal places)
     - Color coding: green for bullish zone, red for bearish, yellow for neutral
   - **Layout:** `w-48 bg-dark-900 border-l border-dark-600 p-3 text-sm space-y-2`
   - **Auto-hide:** Hidden when no indicator values available
</action>

<acceptance_criteria>
- `frontend/src/components/charts/IndicatorPanel.tsx` renders list of indicator names with color-coded values
- Layout: `w-48 bg-dark-900 border-l border-dark-600 p-3 text-sm space-y-2`
- `npx tsc --noEmit` produces zero errors
</acceptance_criteria>

---

## Wave 4: Backtest & Risk Dashboards

**Wave goal:** Build the backtest dashboard (form, equity curve, drawdown, trades table, metrics) and risk dashboard (correlation heatmap, position sizer, beta cards, VaR gauges).

**Dependencies:** Wave 2 complete (stores, layout, API client)

### Task 4.1: Create Backtest Page and Form

<read_first>
- `.planning/phases/07-frontend-core/07-RESEARCH.md` section 6.4 (backtest data flow)
- `frontend/src/api/backtest.ts` (from Task 1.3)
- `frontend/src/store/backtest.ts` (from Task 2.1)
- `frontend/src/types/backtest.ts` (from Task 1.2)
- `backend/app/api/schemas.py` — `BacktestRequest` model fields and defaults
- `config.yaml` — backtest section (default cash, fees, slippage)
</read_first>

<action>
1. Create `frontend/src/components/backtest/BacktestPage.tsx`:
   - **Layout:** Two-panel: left sidebar with BacktestForm + recent runs list, right panel with results (conditional — shown only when a run is selected)
   - **TanStack Query mutations:** `useMutation({ mutationFn: runBacktest, onSuccess: (data) => { addRunId(data.run_id); setSelectedRunId(data.run_id); navigate to result view; invalidateQueries(['backtest', data.run_id]) } })`
   - **Backtest queries (when selectedRunId exists):**
     - `useQuery(['backtest', selectedRunId], () => fetchBacktest(selectedRunId))`
     - `useQuery(['backtest', selectedRunId, 'equity'], () => fetchEquity(selectedRunId))`
     - `useQuery(['backtest', selectedRunId, 'trades'], () => fetchTrades(selectedRunId))`
   - **Results layout:** MetricsCards (top row), EquityCurveChart + DrawdownChart (middle row, two columns), TradesTable (bottom, fills remaining)
   - **Recent runs:** List of recent run IDs from `useBacktestStore.recentRunIds`. Click to navigate to that run's results. Show run date/time.
   - **WS integration:** Subscribe to `backtest:{runId}` channel while viewing a running backtest. Update progress.
   - Loading: Show `SkeletonCard` for each chart area
   - Empty state: "Run a backtest to see results"
   - Error state: ErrorBoundary fallback

2. Create `frontend/src/components/backtest/BacktestForm.tsx`:
   - **Fields:**
     - `symbols` — multi-select input with symbol autocomplete. Min 1.
     - `start` / `end` — date inputs (ISO format). Defaults: start = 1 year ago, end = today.
     - `initial_cash` — number input, default 100000
     - `fees_bps` — number input, default 10
     - `slippage_bps` — number input, default 5
     - `position_sizing` — select: "fixed", "atr", "kelly". Default "fixed".
     - `sizing_params` — JSON textarea (optional, hidden behind "Advanced" toggle)
   - **Submit button:** "Run Backtest" — disabled while mutation is pending
   - **Validation:** Symbols required, start < end, cash > 0
   - **Styling:** `bg-dark-700 rounded p-4 space-y-3`, labels: `text-sm text-dark-200`, inputs: `w-full bg-dark-600 border border-dark-400 rounded px-2 py-1.5 text-sm`
</action>

<acceptance_criteria>
- `frontend/src/components/backtest/BacktestPage.tsx` uses `useMutation` for POST `/api/v1/backtest`, navigates to results on success
- Shows metrics cards, equity curve, drawdown chart, trades table when `selectedRunId` is set
- Lists up to 10 recent run IDs from `useBacktestStore.recentRunIds`
- `frontend/src/components/backtest/BacktestForm.tsx` renders all fields with correct defaults from `config.yaml`: `initial_cash=100000`, `fees_bps=10`, `slippage_bps=5`, `position_sizing='fixed'`
- Submit button disabled while mutation is loading
- `npx tsc --noEmit` produces zero errors
</acceptance_criteria>

---

### Task 4.2: Create Backtest Charts (Equity & Drawdown)

<read_first>
- `.planning/phases/07-frontend-core/07-RESEARCH.md` sections 6.4 (equity curve, drawdown data flow), 5.3 (AreaSeries API)
- `frontend/src/types/backtest.ts` — `EquityPoint`
- `frontend/src/api/backtest.ts` — `fetchEquity`
</read_first>

<action>
1. Create `frontend/src/components/backtest/EquityCurveChart.tsx`:
   - **Props:** `equityData: EquityPoint[]`, `initialCash: number`
   - **Lightweight Charts:** Create chart with `createChart()` in dark theme (same colors as ChartPane)
   - **Series:** `chart.addSeries(AreaSeries, { topColor: 'rgba(34, 197, 94, 0.3)', bottomColor: 'rgba(34, 197, 94, 0.0)', lineColor: '#22C55E', lineWidth: 2 })`
   - **Data:** Map `EquityPoint[]` to `{ time: unix_timestamp, value: equity }` format. Set initial cash as baseline.
   - **Format:** `priceFormat: { type: 'custom', formatter: (price) => formatPrice(price) }`
   - **Horizontal line:** Draw initial cash level as reference line
   - **Title:** "Equity Curve" — rendered outside chart as `<h3>` label
   - Resize via `useResizeObserver`, height: `320px`

2. Create `frontend/src/components/backtest/DrawdownChart.tsx`:
   - **Props:** `equityData: EquityPoint[]`
   - **Calculation:** Compute drawdown client-side: `drawdown[i] = (equity[i] / peak - 1) * 100` where peak is running max
   - **Series:** `chart.addSeries(AreaSeries, { topColor: 'rgba(239, 68, 68, 0.3)', bottomColor: 'rgba(239, 68, 68, 0.0)', lineColor: '#EF4444', lineWidth: 2 })`
   - **Data:** Map computed drawdown to `{ time: unix_timestamp, value: drawdown_pct }`
   - **Format:** `priceFormat: { type: 'custom', formatter: (price) => formatPct(price) }`
   - **Title:** "Drawdown"
   - Resize via `useResizeObserver`, height: `320px`

3. Create `frontend/src/components/backtest/MetricsCards.tsx`:
   - **Props:** `metrics: Metrics | null`
   - **Cards grid:** 3 columns, responsive. Each card shows metric name + formatted value.
   - **Metrics displayed:** Sharpe Ratio, Sortino Ratio, Calmar Ratio, Max DD%, Win Rate%, Total Return%, Profit Factor, Expectancy, SQN, Ulcer Index
   - **Color coding:** Positive metrics green (`text-gain`), negative red (`text-loss`). Sharpe > 2 green, 1-2 yellow, < 1 red. Max DD worse than -20% red.
   - **Styling:** `grid grid-cols-3 gap-3`, each card: `bg-dark-700 rounded p-3`, metric name: `text-xs text-dark-300 uppercase tracking-wide`, value: `text-lg font-mono font-semibold`
</action>

<acceptance_criteria>
- `frontend/src/components/backtest/EquityCurveChart.tsx` renders `AreaSeries` with topColor `rgba(34,197,94,0.3)` and lineColor `#22C55E`
- `frontend/src/components/backtest/DrawdownChart.tsx` computes drawdown from equity data (peak-based running max), renders `AreaSeries` in red
- `frontend/src/components/backtest/MetricsCards.tsx` renders 10 metric cards in `grid-cols-3` layout
- Each MetricsCard shows metric name and value with color coding (green/red/yellow)
- `npx tsc --noEmit` produces zero errors
</acceptance_criteria>

---

### Task 4.3: Create Trades Table with Expandable Rows

<read_first>
- `frontend/src/types/backtest.ts` — `Trade` type with all fields
- `frontend/src/api/backtest.ts` — `fetchTrades`
- `.planning/phases/07-frontend-core/07-RESEARCH.md` section 6.4 (trades table, trade detail expand)
</read_first>

<action>
1. Create `frontend/src/components/backtest/TradesTable.tsx`:
   - **TanStack Virtual:** `useVirtualizer({ count: trades.length, estimateSize: () => 40, overscan: 5 })` for row virtualization
   - **Columns:** Trade Index, Symbol, Direction (Long/Short with color), Entry Price, Exit Price, Size, PnL (color coded), MAE, MFE, Hold Duration, Exit Reason
   - **Sortable columns:** Click header to sort asc/desc
   - **Expandable rows:** Click a row to toggle expansion showing `TradeDetail` component
   - **Filter bar:** Symbol search filter, Direction dropdown (All/Long/Short), date range filter. All via `useBacktestStore.tradeFilter`.
   - **Styling:** Cell padding `px-2 py-1.5 text-xs font-mono`, sticky header `bg-dark-700`, PnL colored `text-gain` / `text-loss`
   - **Summary footer:** Row showing total PnL, win/loss count, avg MAE/MFE

2. Create `frontend/src/components/backtest/TradeDetail.tsx`:
   - **Props:** `trade: Trade`
   - **Content:**
     - Entry/Exit details card: symbol, direction, entry_price, exit_price, size, entry_time, exit_time
     - PnL breakdown: gross PnL, fees, net PnL, return%
     - MAE/MFE bar: simple horizontal bar showing entry → exit path with MAE as red line, MFE as green line
     - Exit reason badge
   - **Styling:** `bg-dark-800 p-3 rounded border border-dark-500 grid grid-cols-2 gap-3 text-xs`
</action>

<acceptance_criteria>
- `frontend/src/components/backtest/TradesTable.tsx` uses `useVirtualizer` for row virtualization with `estimateSize: () => 40`
- Columns include Trade Index, Symbol, Direction, Entry/Exit Price, Size, PnL, MAE, MFE, Hold Duration, Exit Reason
- Clicking a row toggles expansion showing `TradeDetail`
- PnL cells colored `text-gain` for positive, `text-loss` for negative
- Summary footer shows total PnL, win/loss count, avg MAE/MFE
- `frontend/src/components/backtest/TradeDetail.tsx` shows entry/exit details, PnL breakdown, MAE/MFE bar, exit reason badge
- `npx tsc --noEmit` produces zero errors
</acceptance_criteria>

---

### Task 4.4: Create Risk Page with Correlation Heatmap

<read_first>
- `.planning/phases/07-frontend-core/07-RESEARCH.md` section 6.5 (risk data flow, heatmap approach using D3.js)
- `frontend/src/api/risk.ts` — `fetchCorrelation`
- `frontend/src/types/risk.ts` — `CorrelationResult`
- `frontend/src/store/risk.ts` — `selectedSymbols`, `activeView`
</read_first>

<action>
1. Create `frontend/src/components/risk/RiskPage.tsx`:
   - **Layout:** Top tab bar (Correlation, Position Sizer, Beta, VaR) + content area for active view
   - Tabs use `useRiskStore.setActiveView()`
   - **Correlation view:** CorrelationHeatmap component
   - **Position Sizer view:** PositionSizer component
   - **Beta view:** BetaCards component
   - **VaR view:** VarGauge component + KellyResult
   - **Symbol selector:** Multi-select input for choosing symbols (defaults to `useRiskStore.selectedSymbols`)
   - **TanStack Query (correlation):** `useQuery({ queryKey: ['risk', 'correlation', { symbols, window }], queryFn: () => fetchCorrelation(symbols, 30) })` — only fetch when activeView is 'correlation'
   - Loading: `SkeletonCard` grid, Error: ErrorBoundary fallback

2. Create `frontend/src/components/risk/CorrelationHeatmap.tsx`:
   - **Props:** `data: CorrelationResult | undefined`, `isLoading: boolean`
   - **Implementation:** Use Recharts or custom SVG for heatmap grid
   - **Grid:** N×N matrix where N = `symbols.length`. Each cell colored by correlation value: -1 (dark red) → 0 (dark gray) → +1 (dark green)
   - **Color scale:** `[-1, -0.5, 0, 0.5, 1]` → `['#7F1D1D', '#991B1B', '#374151', '#166534', '#15803D']`
   - **Labels:** Row labels (symbol names) on left, column labels on top
   - **Cell interaction:** Hover shows tooltip with pair name and exact correlation value
   - **Layout:** Responsive square grid, max size 600×600px, scroll if too large
   - **Diversification score:** Display below heatmap as a metric card: `data.diversification_score` with color code ( > 0.7 green, > 0.4 yellow, else red)

3. Since Recharts doesn't have a native heatmap, implement using custom `<rect>` SVG elements within an `<svg>` container. Calculate cell size based on N symbols: `cellSize = min(availableWidth, 600) / N`
</action>

<acceptance_criteria>
- `frontend/src/components/risk/RiskPage.tsx` renders 4 tab buttons (Correlation, Position Sizer, Beta, VaR) and conditionally shows the active view
- `frontend/src/components/risk/CorrelationHeatmap.tsx` renders N×N colored grid with SVG `<rect>` elements
- Heatmap color scale maps -1 to dark red (`#7F1D1D`), 0 to gray (`#374151`), +1 to dark green (`#15803D`)
- Hovering a cell shows tooltip with pair name and correlation value
- Diversification score displayed below heatmap with color coding
- `npx tsc --noEmit` produces zero errors
</acceptance_criteria>

---

### Task 4.5: Create Risk Dashboard Components (PositionSizer, BetaCards, VaRGauge, KellyResult)

<read_first>
- `frontend/src/api/risk.ts` — `postPositionSize`, `fetchBeta`, `fetchVaR`, `postKelly`
- `frontend/src/types/risk.ts` — `PositionSizeRequest`, `BetaResult`, `VaRResult`, `KellyResult`
- `config.yaml` — risk section (defaults: risk_per_trade, atr_multiplier, beta_window_days, var defaults)
</read_first>

<action>
1. Create `frontend/src/components/risk/PositionSizer.tsx`:
   - **Form fields:**
     - `symbols` — multi-select input for symbols (min 1)
     - `method` — select: "atr", "kelly", "fixed"
     - `cash` — number input, default 100000
     - `params` — dynamic fields based on method: ATR shows `atr_multiplier` (default 2.0), Kelly shows no additional, Fixed shows `position_pct` (default 0.02)
   - **Calculate button:** Calls `useMutation({ mutationFn: () => postPositionSize(body) })`
   - **Result display:** Table showing symbol → position size (formatted as `formatPrice`). Total column.
   - **Styling:** `space-y-4`, card: `bg-dark-700 rounded p-4`

2. Create `frontend/src/components/risk/BetaCards.tsx`:
   - **Props:** `symbols: string[]`
   - **TanStack Query:** `useQuery({ queryKey: ['risk', 'beta', { symbols }], queryFn: () => fetchBeta(symbols) })`
   - **Cards grid:** `grid grid-cols-2 lg:grid-cols-3 gap-3`
   - Each card shows: symbol (bold), beta value (formatted to 2 decimal places), R², tracking error
   - **Color coding:** Beta < 0.5 green (low risk), 0.5-1.0 yellow (market-like), > 1.0 red (high volatility)
   - **Loading:** `SkeletonCard` placeholders

3. Create `frontend/src/components/risk/VarGauge.tsx`:
   - **Props:** `symbols: string[]`
   - **TanStack Query:** `useQuery({ queryKey: ['risk', 'var', { symbols, confidence: 0.95, method: 'historical' }], queryFn: () => fetchVaR(symbols, 0.95, 'historical') })`
   - **Display:** Two gauge charts (VaR and CVaR) using Recharts PieChart with donut layout
     - Donut value arc shows VaR/CVaR as percentage of portfolio
     - Center text shows `formatPct(value)`
     - Color: VaR/CVaR < -5% red, -2% to -5% yellow, > -2% green
   - **Confidence selector:** Radio buttons for 95% / 99%
   - **Method selector:** Select for "historical", "parametric", "monte_carlo"
   - **Layout:** Two columns, each `flex-1`, gauge height 200px

4. Create `frontend/src/components/risk/KellyResult.tsx`:
   - **Props:** `backtestRunId: string`
   - **TanStack Query:** `useQuery({ queryKey: ['risk', 'kelly', backtestRunId], queryFn: () => postKelly({ backtest_run_id: backtestRunId, max_dd_target: 0.25 }) })` (POST to read endpoint)
   - **Display:** Card showing: Kelly % (optimal), Half-Kelly % (recommended), Edge, Odds
   - **Recommendation text:** "Risk up to X% per trade based on backtest statistics"
   - **Styling:** `bg-dark-700 rounded p-4`, kelly values: `text-2xl font-mono font-bold text-accent`
</action>

<acceptance_criteria>
- `frontend/src/components/risk/PositionSizer.tsx` renders form with symbols, method (3 options), cash (default 100000), dynamic params fields based on method
- Calculate button calls `useMutation` for POST `/api/v1/risk/position-size`, shows results table
- `frontend/src/components/risk/BetaCards.tsx` renders cards in `grid-cols-2 lg:grid-cols-3` with beta value, R², tracking error
- Beta color coding: < 0.5 green, 0.5-1.0 yellow, > 1.0 red
- `frontend/src/components/risk/VarGauge.tsx` renders two Recharts PieChart donut gauges (VaR and CVaR)
- Has confidence radio buttons (95%/99%) and method select (3 options)
- `frontend/src/components/risk/KellyResult.tsx` shows Kelly%, Half-Kelly%, Edge, Odds in accent-colored text
- `npx tsc --noEmit` produces zero errors
</acceptance_criteria>

---

## Wave 5: Docker, Build Configuration & Integration

**Wave goal:** Add Docker multi-stage build for frontend, integrate with docker-compose, verify full build pipeline, and run integration test.

**Dependencies:** Waves 3 and 4 complete

### Task 5.1: Create Frontend Docker Configuration

<read_first>
- `Dockerfile` (backend — for pattern reference)
- `docker-compose.yml` — existing services (api, worker, redis) for frontend service addition
- `.planning/phases/07-frontend-core/07-RESEARCH.md` sections 9.3, 10.3 (Dockerfile, nginx.conf, docker-compose extension)
- `config.yaml` API section — `cors_origins` for production update
</read_first>

<action>
1. Create `frontend/Dockerfile`:
   ```dockerfile
   # Stage 1: Builder
   FROM node:20-alpine AS builder
   WORKDIR /app
   COPY package.json package-lock.json ./
   RUN npm ci
   COPY . .
   RUN npm run build

   # Stage 2: Nginx
   FROM nginx:alpine
   COPY nginx.conf /etc/nginx/conf.d/default.conf
   COPY --from=builder /app/dist /usr/share/nginx/html
   EXPOSE 80
   CMD ["nginx", "-g", "daemon off;"]
   ```

2. Create `frontend/nginx.conf`:
   ```nginx
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
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
       }

       # WebSocket proxy
       location /ws/ {
           proxy_pass http://api:8000;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection "upgrade";
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }

       # SPA fallback — serve index.html for all non-file routes
       location / {
           try_files $uri $uri/ /index.html;
       }
   }
   ```

3. Update `docker-compose.yml` — add frontend service:
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

4. Create `frontend/.dockerignore`:
   ```
   node_modules
   dist
   .git
   *.md
   ```
</action>

<acceptance_criteria>
- `frontend/Dockerfile` has two stages: `node:20-alpine` builder with `npm run build`, `nginx:alpine` runtime
- `frontend/nginx.conf` has `location /api/` proxy to `http://api:8000` and `location /ws/` proxy with Upgrade header
- `frontend/nginx.conf` has `try_files $uri $uri/ /index.html` SPA fallback
- `docker-compose.yml` has `frontend` service with build context `./frontend`, port `80:80`, depends_on `api: service_healthy`
- `frontend/.dockerignore` excludes `node_modules`, `dist`, `.git`
</acceptance_criteria>

---

### Task 5.2: Build Verification & Integration Test

<read_first>
- All files created in Waves 1-5
- `.planning/phases/07-frontend-core/07-RESEARCH.md` section 1 (project state assessment)
</read_first>

<action>
1. Install dependencies: Run `cd frontend && npm install` — verify clean install with no peer dependency warnings
2. Type check: Run `npx tsc --noEmit` — must exit 0
3. Build: Run `npm run build` — must produce `frontend/dist/` directory with `index.html`, `assets/` subdirectory
4. Verify build output contains: `index.html`, JS chunks for vendor/charts/query
5. Verify `frontend/dist/index.html` references correct asset paths
6. Run `npm run lint` — zero errors (warnings allowed)
7. Final check: `npm run typecheck` — zero errors
</action>

<acceptance_criteria>
- `npm install` completes in `frontend/` directory without errors
- `npx tsc --noEmit` exits 0
- `npm run build` produces `frontend/dist/index.html` with JS/CSS asset references
- `frontend/dist/assets/` contains at least 3 JS chunks (vendor, charts, query)
- `npm run lint` exits 0 (warnings OK, errors not OK)
- `npm run typecheck` exits 0
</acceptance_criteria>

---

## Verification Criteria

After all tasks are complete, verify the following:

1. **Build verification:** `cd frontend && npm run build` produces `/dist/index.html` with correct asset paths
2. **Type safety:** `npx tsc --noEmit` produces zero errors
3. **Lint:** `npm run lint` produces zero errors (warnings allowed)
4. **File structure:** All 70+ source files exist under `frontend/src/` matching the architecture in RESEARCH.md section 6.1
5. **Docker:** `docker-compose build frontend` succeeds
6. **Component hierarchy:** AppShell → {Sidebar, Header, Outlet}, Outlet renders correct page per route
7. **Data flow:** API client → TanStack Query → Components. WS → useWebSocket → query cache updates
8. **No backend changes:** All API endpoints consumed are from Phase 6. `git diff -- backend/` shows zero changes

## Risk Mitigations

| Risk | Mitigation in Plan |
|------|-------------------|
| **TanStack Virtual v3 beta** | Task 3.2 — Row virtualization only (stable). Column virtualization deferred. Pin version in package.json. |
| **WebSocket reconnection** | Task 1.4 — Dedicated `useWebSocket` singleton hook with exponential backoff, resync protocol, sequence persistence. |
| **50+ column performance** | Task 3.2 — Row virtualization, CSS horizontal scroll, column toggle via Zustand. Monitor during execution. |
| **Multi-chart sync edge cases** | Task 2.2 — Dedicated `useSynchronizedCharts` hook with master/slave pattern, requestAnimationFrame throttling. |
| **WS / TanStack Query conflict** | Task 3.1 — WS updates go into query cache via `setQueryData`. `staleTime: 5000` prevents refetch during WS activity. Polling fallback only when WS disconnected. |
| **Recharts no heatmap** | Task 4.4 — Custom SVG `<rect>` grid heatmap. Recharts for gauge charts (PieChart donut). |
