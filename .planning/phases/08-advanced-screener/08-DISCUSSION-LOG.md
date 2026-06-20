# Phase 8: Advanced Screener - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-20
**Phase:** 8-advanced-screener
**Areas discussed:** Saved Screen Configurations, Real-Time Alerts, Screen Sharing, Historical Screen Replay, Frontend Integration

---

## Saved Screen Configurations

| Option | Description | Selected |
|--------|-------------|----------|
| DuckDB table + JSON filter pipeline | Persistent, queryable, versioned | ✓ |
| localStorage only | Simple, but no sharing/versioning | |
| File-based (YAML/JSON) | Portable, but no query/index | |

**User's choice:** DuckDB table with JSON filter pipeline
**Notes:** Table: `screen_configs` (id, name, description, created_at, updated_at, filter_json, asset_classes, timeframes, is_public). Versioning: each save creates new row; UI shows version history with diff.

---

## Real-Time Alerts

| Option | Description | Selected |
|--------|-------------|----------|
| Per-candle evaluation | On every candle close, evaluate all alerts | ✓ |
| Polling-based | Client polls every N seconds | |
| Server-sent events only | Push-only, no client poll | |

**User's choice:** Per-candle evaluation on new candle close
**Notes:** Uses Phase 3 indicator cache + Phase 6 WebSocket. Max 100 active alerts/user. Alert types: price threshold, indicator cross, signal trigger, volume spike, trend break. Compound conditions (AND/OR). Delivery: WS push + toast.

---

## Screen Sharing

| Option | Description | Selected |
|--------|-------------|----------|
| URL with token (read-only) | `/screener/{id}?v={v}&token={token}` | ✓ |
| Embedded iframe | Embed in external sites | |
| Collaborative editing | Real-time multi-user | Deferred |

**User's choice:** Token-based URL sharing
**Notes:** `/screener/{id}?v={v}&token={token}`. Token = base64url(id + version + expiry). Expiry: 1h, 24h, 7d, never. Read-only view with "Fork to My Screens". Optional password.

---

## Historical Screen Replay

| Option | Description | Selected |
|--------|-------------|----------|
| Daily granularity replay | Re-run at each daily close for N years | ✓ |
| Intraday replay | Re-run at each intraday candle | Too heavy |
| Signal quality only | Match count + win rate only | |

**User's choice:** Daily granularity replay
**Notes:** Re-runs screen logic at each daily close for last N years (default 2). Outputs: match count over time, signal quality metrics (win rate, avg return), equity curve if backtested. Cached in `screen_replay_results` table.

---

## Frontend Integration

| Option | Description | Selected |
|--------|-------------|----------|
| Toolbar buttons + modal | Save/Load/Share/Alerts in toolbar | ✓ |
| Dedicated "My Screens" page | Separate page for management | |
| Command palette only | Cmd+K style | |

**User's choice:** Toolbar + modal
**Notes:** "Save" button, "Load Screen" modal (searchable, filterable by tags), "Alerts" tab in sidebar, "Share" dropdown (copy link, QR, email).

---

## OpenCode's Discretion

- Exact database schema for screens/alerts/replay tables
- WebSocket event format for alert notifications (reuse Phase 6 `risk:` channel or new `alert:` channel)
- Frontend component structure for alert center (toast vs modal vs sidebar)

---

## Deferred Ideas

- Collaborative editing: Real-time multi-user screen editing (Google Docs style)
- Alert webhooks: POST to user-defined URL on trigger
- ML-based alert optimization: Suggest thresholds based on historical performance
- Screen marketplace: Public gallery with ratings/comments
- Mobile push notifications (Phase 10+)