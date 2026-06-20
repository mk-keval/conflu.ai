# Phase 8: Advanced Screener - Context

**Gathered:** 2026-06-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Advanced Screener: Build on the Phase 3/7 screener foundation to add saved configurations, real-time alerts, screen sharing, and historical replay capabilities. This phase transforms the screener from a one-time analysis tool into a persistent, collaborative trading workspace.
</domain>

<decisions>
## Implementation Decisions

### Saved Screen Configurations
- **D-01:** Screen configurations stored as JSON in DuckDB (`screen_configs` table) with fields: `id`, `name`, `description`, `created_at`, `updated_at`, `filter_json` (serialized filter pipeline), `asset_classes`, `timeframes`, `is_public` (for sharing).
- **D-02:** CRUD API endpoints: `POST /api/v1/screens` (create), `GET /api/v1/screens` (list), `GET /api/v1/screens/{id}` (get), `PUT /api/v1/screens/{id}` (update), `DELETE /api/v1/screens/{id}` (delete).
- **D-03:** Frontend: "Save Screen" button in screener toolbar, "Load Screen" modal with search/filter, auto-save draft to localStorage every 30s.
- **D-04:** Screen versioning: Each save creates new version; UI shows version history with diff view (added/removed filters, changed thresholds).

### Real-Time Alerts
- **D-04:** Alert types: Price threshold, indicator cross (RSI < 30, MACD cross), signal trigger (screener match), volume spike, trend break.
- **D-05:** Alert conditions: Single condition or compound (AND/OR). Persisted in `alerts` table with `user_id`, `condition_json`, `is_active`, `cooldown_seconds` (default 5min 60s), `last_triggered_at`.
- **D-06:** Delivery: WebSocket push to frontend (real-time toast), optional email (Phase 10). Frontend shows toast with "View in Screener" deep-link.
- **D-07:** Alert evaluation: Runs on every new candle close (per timeframe). Uses Phase 3 indicator cache + Phase 6 WebSocket for real-time evaluation. Max 100 active alerts per user.

### Screen Sharing
- **D-08:** Share via URL: `/screener/{screen_id}?v={version}&share_token={token}`. Token = base64url(screen_id + version + expiry). Expiry options: 1h, 24h, 7d, never.
- **D-09:** Shared view is read-only: Shows screen config, current results, charts. "Fork to My Screens" button clones to user's account.
- **D-10:** Access control: Token-based (no login required for view). Optional password protection for private shares.

### Historical Screen Replay
- **D-12:** "Replay" button on saved screen: Re-runs screen logic at each historical timestamp (daily granularity) for last N years (default 2). Outputs: match count over time, signal quality metrics (win rate, avg return), equity curve if backtested.
- **D-13:** Replay uses Phase 2 historical data + Phase 3 indicator cache. Results cached in `screen_replay_results` table (screen_id, timestamp, match_count, signals_json).

### Frontend Integration
- **D-13:** Screener page: "Save" button in toolbar, "Load Screen" modal (searchable, filterable by tags/asset class), "Alerts" tab in sidebar, "Share" button with dropdown (copy link, QR code, email).
- **D-14:** Alerts panel: Real-time toast notifications, "Alerts Center" page with history, filter by status (active/triggered/expired), bulk enable/disable.
- **D-15:** Screen sharing modal: Generates link, QR code, expiry selector, optional password. Copies to clipboard.

### Configuration
- **D-15:** Backend settings: `max_saved_screens_per_user` (default 50), `max_alerts_per_user` (default 100), `default_share_expiry_days` (7), `max_replay_years` (2).

### OpenCode's Discretion
- **D-16:** Exact database schema for screens/alerts/replay tables.
- **D-17:** WebSocket event format for alert notifications (reuse Phase 6 `risk:` channel or new `alert:` channel).
- **D-18:** Frontend component structure for alert center (toast vs modal vs sidebar).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 1-7 Foundations
- `.planning/phases/01-foundation-core-infrastructure/01-CONTEXT.md` — Core decisions
- `.planning/phases/03-screener-engine/03-CONTEXT.md` — Screener engine decisions
- `.planning/phases/06-api-layer/06-CONTEXT.md` — API layer decisions
- `.planning/phases/07-frontend-core/07-CONTEXT.md` — Frontend architecture decisions

### Existing Code Assets
- `backend/app/infrastructure/screener/engine.py` — ScreenEngine, filter pipeline
- `backend/app/infrastructure/screener/streaming.py` — WebSocket streaming for screener
- `backend/app/api/routers/screener.py` — Screener REST endpoints
- `backend/app/api/ws/channels.py` — WebSocket channel definitions (`screener:*`)
- `backend/app/domain/models.py` — ScreenResult, FilterRule, Signal models
- `backend/app/api/schemas.py` — API request/response models
- `frontend/src/components/screener/` — ScreenerPage, ScreenerTable, ScreenSelector
- `frontend/src/api/screener.ts` — Frontend API client
- `frontend/src/hooks/useWebSocket.ts` — WebSocket hook

### Project Requirements
- `REQUIREMENTS.md` — FR-008 (Saved screens), FR-009 (Alerts), FR-010 (Sharing), FR-011 (Replay)
- `.planning/ROADMAP.md` — Phase 8 success criteria

### External Documentation
- FastAPI WebSockets: https://fastapi.tiangolo.com/advanced/websockets/
- TanStack Query mutations: https://tanstack.com/query/latest/docs/react/guides/mutations
- Web Push API: https://developer.mozilla.org/en-US/docs/Web/API/Push_API

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets (from Phases 1-7)
- `backend/app/infrastructure/screener/engine.py` — `ScreenEngine`, `FilterPipeline`, filter registry
- `backend/app/infrastructure/screener/streaming.py` — `ScreenerStreamManager`, `ScreenerChannelProvider`
- `backend/app/api/routers/screener.py` — `POST /screen`, `GET /screens`
- `backend/app/api/ws/channels.py` — `ScreenerChannelProvider`
- `frontend/src/components/screener/ScreenerPage.tsx` — ScreenerTable, ScreenSelector
- `frontend/src/hooks/useWebSocket.ts` — WebSocket singleton hook
- `frontend/src/store/screenStore.ts` — Screen filter state, saved screens

### Established Patterns
- `@filter` / `@indicator` decorator registries
- Pydantic models for request/response validation
- TanStack Query for server state, Zustand for client state
- WebSocket singleton with exponential backoff + sequence tracking
- DuckDB for analytical queries, Parquet for storage

### Integration Points
- Phase 3 ScreenerEngine → New saved screen CRUD
- Phase 3 Streaming → Alert evaluation on new candle
- Phase 6 API → New REST endpoints for screens/alerts
- Phase 6 WebSocket → Alert push notifications (`alert:` channel)
- Phase 7 Frontend → ScreenerPage toolbar, AlertsCenter component

</code_context>

<specifics>
## Specific Ideas

- Alert deduplication: Group by symbol + condition within cooldown window
- Screen diff view: Side-by-side filter comparison (added/removed/modified)
- Alert sound: Web Audio API with configurable sound per severity
- Screen tags: User-defined tags for organization (swing, momentum, mean-reversion)
- Export screen results to CSV/JSON directly from shared view
- Keyboard shortcuts: `Cmd+S` save, `Cmd+Shift+S` save as, `Cmd+Shift+A` new alert

</specifics>

<deferred>
## Deferred Ideas

- Collaborative editing: Real-time multi-user screen editing (Google Docs style)
- Alert webhooks: POST to user-defined URL on trigger
- ML-based alert optimization: Suggest thresholds based on historical performance
- Screen marketplace: Public gallery with ratings/comments
- Mobile push notifications (Phase 10+)

None — discussion stayed within phase scope
</deferred>

---

*Phase: 8-Advanced Screener*
*Context gathered: 2026-06-20*