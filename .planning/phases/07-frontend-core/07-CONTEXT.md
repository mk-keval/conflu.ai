# Phase 7: Frontend Core - Context

**Gathered:** 2026-06-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Frontend Core: React + TradingView Lightweight Charts + Tailwind. Deliverables: virtualized screener table, multi-timeframe synchronized charts, backtest dashboard, risk dashboard. Consumes Phase 6 API endpoints.
</domain>

<decisions>
## Implementation Decisions

### Technology Stack
- **D-01:** React 18 with TypeScript (Vite build). Tailwind CSS for styling. TradingView Lightweight Charts for charts.
- **D-02:** TanStack Query (React Query) for server state management. Axios for HTTP. Zustand for client state.
- **D-03:** ESLint + Prettier + TypeScript strict mode. Husky pre-commit hooks.

### Screener Table
- **D-04:** Virtualized table using TanStack Virtual (react-window replacement). 50+ columns, sticky header, frozen symbol column.
- **D-05:** Real-time updates via WebSocket subscription to `/ws/stream` (channels: `screener:*`). Optimistic UI for filter changes.
- **D-06:** Column definitions driven by API schema. Hover tooltips show indicator definitions from Phase 3 dictionary.

### Multi-Timeframe Charts
- **D-06:** TradingView Lightweight Charts with multiple chart instances (1D, 4H, 1H, 15m). Synchronized crosshair + time sync.
- **D-07:** Indicator overlays: price (candles), volume, indicators (RSI, MACD, EMA, BB, ATR) on separate panes.
- **D-08:** Chart data fetched via `/api/v1/indicators/{symbol}?timeframes=1D,4H,1H,15m`. WebSocket for live updates.

### Backtest Dashboard
- **D-09:** Equity curve chart (area), drawdown chart (area), trades table (virtualized), metrics cards grid.
- **D-10:** Trade list with expandable rows showing entry/exit, MAE/MFE, PnL. Filter by date range, symbol.

### Risk Dashboard
- **D-11:** Correlation heatmap (D3.js or recharts). Position size calculator (ATR-based). Beta exposure cards.
- **D-12:** VaR/CVaR gauge charts. Kelly sizing recommendation card.

### State Management & API Integration
- **D-13:** TanStack Query for all server state. Axios instance with interceptors (auth, request_id). Base URL from env.
- **D-014:** WebSocket connection managed by singleton hook. Auto-reconnect with exponential backoff.
- **D-15:** Request cancellation on unmount. Optimistic updates for filter/sort.

### UI/UX
- **D-16:** Tailwind CSS with custom theme (dark mode default). Responsive: desktop > tablet > mobile.
- **D-17:** Loading skeletons, error boundaries, empty states. Toasts for errors/warnings.
- **D-18:** Keyboard shortcuts (?, / for search, Esc to close modals). Accessibility: ARIA labels, focus management.

### Build & Deploy
- **D-19:** Vite + TypeScript + SWC. Production build outputs to `dist/`. Docker multi-stage for Nginx.
- **D-20:** Proxy `/api/*` to backend in dev. Production: Nginx reverse proxy.

### OpenCode's Discretion
- **D-20:** Exact component hierarchy and file structure.
- **D-21:** Chart library configuration details (grid, colors, tooltips).
- **D-22:** Virtualization library choice (TanStack Virtual vs react-window).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 1-6 Foundations
- `.planning/phases/01-foundation-core-infrastructure/01-CONTEXT.md` — Core decisions
- `.planning/phases/06-api-layer/06-CONTEXT.md` — API endpoints, WebSocket protocol
- `.planning/phases/03-screener-engine/03-CONTEXT.md` — Screener filter dictionary
- `.planning/phases/04-backtest-engine/04-CONTEXT.md` — Backtest result models
- `.planning/phases/05-risk-engine/05-CONTEXT.md` — Risk models

### API Contracts (Phase 6)
- `backend/app/api/schemas.py` — Request/response models
- `backend/app/api/ws/channels.py` — WebSocket channel definitions
- `config.yaml` — API base URL, WS path

### Existing Code Assets
- `backend/app/api/schemas.py` — Pydantic models for all API responses
- `backend/app/api/ws/channels.py` — Channel definitions (`price:`, `indicator:`, `signal:`, `risk:`)
- `backend/app/infrastructure/screener/engine.py` — Screener result shape
- `backend/app/infrastructure/backtest/models.py` — Backtest result models
- `backend/app/infrastructure/risk/models.py` — Risk models

### External Documentation
- TradingView Lightweight Charts: https://tradingview.github.io/lightweight-charts/
- TanStack Query: https://tanstack.com/query/latest
- TanStack Virtual: https://tanstack.com/virtual/latest
- Tailwind CSS: https://tailwindcss.com/docs
- Zustand: https://github.com/pmndrs/zustand

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets (from Phases 1-6)
- `backend/app/api/schemas.py` — API response models for all endpoints
- `backend/app/api/ws/channels.py` — WebSocket channel definitions
- `backend/app/infrastructure/screener/engine.py` — Screener result structure
- `backend/app/infrastructure/backtest/models.py` — Backtest result models
- `backend/app/infrastructure/risk/models.py` — Risk models

### Established Patterns
- TypeScript strict + React Query for data fetching
- WebSocket singleton pattern (Phase 6 `WebSocketManager`)
- API response envelope: `{data: T, meta: {timestamp, request_id}}`
- Error envelope: `{error: {code, message, details, request_id}}`

### Integration Points
- Phase 6 `/api/v1/screen` → Screener table
- Phase 6 `/api/v1/backtest/*` → Backtest dashboard
- Phase 6 `/api/v1/indicators/{symbol}` → Charts
- Phase 6 `/api/v1/risk/{symbol}` → Risk dashboard
- Phase 6 `/ws/stream` → Real-time updates for all views

</code_context>

<specifics>
## Specific Ideas

- Screener table: Column visibility toggle, CSV export, saved filter presets
- Charts: Synchronized crosshair across timeframes, indicator toggle panel
- Backtest: Trade expand → MAE/MFE chart, equity curve hover values
- Risk: Position size calculator with live ATR fetch, correlation matrix hover details

</specifics>

<deferred>
## Deferred Ideas

- Advanced charting: drawing tools, pattern recognition overlays
- Portfolio view: multi-position P&L, sector allocation
- Alerts UI: create/manage price/indicator/signal alerts
- Mobile-first responsive layouts
- Dark/light theme toggle persistence

None — discussion stayed within phase scope
</deferred>

---

*Phase: 7-Frontend Core*
*Context gathered: 2026-06-19*