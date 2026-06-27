# ADR-007: React + TypeScript Frontend

**Status:** Superseded
**Date:** 2026-06-18

## Context
Need a modern, type-safe frontend framework for building the trading dashboard with real-time charting and complex state management.

## Decision
Use React 18 with TypeScript, Vite for build tooling, Tailwind CSS for styling, Zustand for global state, React Query for server state, and TradingView Lightweight Charts for financial charts.

## Consequences
- **Positive**: Type safety, excellent developer experience with Vite, fast builds
- **Negative**: Large node_modules, bundle size needs monitoring
- **Mitigation**: Code splitting, lazy loading, bundle analysis in CI
