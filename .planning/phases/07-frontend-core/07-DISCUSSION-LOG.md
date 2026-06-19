# Phase 7: Frontend Core - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-19
**Phase:** 7-frontend-core
**Areas discussed:** Technology Stack, Screener Table, Multi-Timeframe Charts, Backtest Dashboard, Risk Dashboard, State Management, Build & Deploy

---

## Technology Stack

| Option | Description | Selected |
|--------|-------------|----------|
| React 18 + TypeScript + Vite | Modern, fast HMR, great ecosystem | ✓ |
| Next.js | SSR/SSG, but overkill for SPA | |
| Vue 3 + Nuxt | Great DX, but team prefers React | |

**User's choice:** React 18 + TypeScript + Vite
**Notes:** Tailwind CSS for styling. TradingView Lightweight Charts for charts. TanStack Query + Zustand.

---

## Screener Table

| Option | Description | Selected |
|--------|-------------|----------|
| TanStack Virtual | Modern, performant, headless | ✓ |
| react-window | Mature, but older API | |
| ag-Grid | Feature-rich, but heavy/license | |

**User's choice:** TanStack Virtual
**Notes:** 50+ columns, sticky header, frozen symbol column. Real-time via WebSocket `screener:*` channels.

---

## Multi-Timeframe Charts

| Option | Description | Selected |
|--------|-------------|----------|
| TradingView Lightweight Charts | Purpose-built, performant, free | ✓ |
| Highcharts | Feature-rich, commercial license | |
| Chart.js + plugins | Flexible, but not finance-specific | |
| uPlot | Fast, but less finance-specific | |

**User's choice:** TradingView Lightweight Charts
**Notes:** Multi-chart sync (1D, 4H, 1H, 15m). Indicator overlays on separate panes.

---

## Backtest Dashboard

| Option | Description | Selected |
|--------|-------------|----------|
| Equity curve + drawdown + trades table + metrics | Full dashboard | ✓ |
| Minimal (equity + metrics only) | Lightweight | |
| Interactive deep-dive | Advanced | |

**User's choice:** Full dashboard
**Notes:** Equity curve, drawdown, trades table (virtualized), metrics cards. Trade expand → MAE/MFE.

---

## Risk Dashboard

| Option | Description | Selected |
|--------|-------------|----------|
| Heatmap + calculator + beta cards | Complete risk view | ✓ |
| Minimal (VaR + beta only) | Minimal | |
| Advanced (stress testing UI) | Advanced | |

**User's choice:** Complete risk dashboard
**Notes:** Correlation heatmap (recharts/D3), position size calculator, beta exposure cards, VaR gauge.

---

## State Management & API Integration

| Option | Description | Selected |
|--------|-------------|----------|
| TanStack Query + Axios + Zustand | Modern, powerful, typed | ✓ |
| SWR + fetch + Context | Simpler, less features | |
| RTK Query + Redux | Heavy, overkill | |

**User's choice:** TanStack Query + Axios + Zustand
**Notes:** Axios instance with interceptors (auth, request_id). WebSocket singleton with auto-reconnect.

---

## Build & Deploy

| Option | Description | Selected |
|--------|-------------|----------|
| Vite + Nginx Docker | Fast dev, production-ready | ✓ |
| Next.js static export | SSR not needed | |
| Vercel/Netlify | Managed, but less control | |

**User's choice:** Vite + Nginx Docker
**Notes:** Vite + TypeScript + SWC. Proxy `/api/*` in dev. Nginx reverse proxy in prod.

---

## OpenCode's Discretion

- Exact component hierarchy and file structure
- Chart library configuration details (grid, colors, tooltips)
- Virtualization library choice (TanStack Virtual vs react-window)

---

## Deferred Ideas

- Advanced charting: drawing tools, pattern recognition overlays
- Portfolio view: multi-position P&L, sector allocation
- Alerts UI: create/manage price/indicator/signal alerts
- Mobile-first responsive layouts
- Dark/light theme toggle persistence