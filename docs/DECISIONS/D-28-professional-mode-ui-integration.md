# D-28: Professional Mode UI & Integration Architecture

**Status:** Accepted
**Date:** 2026-07-26
**Depends on:** D-27 (Professional Mode Backend Architecture)

## Context

Phase 8 introduces a "Professional Mode" for working professionals with zero market knowledge. The backend services (D-27) provide the data layer; this ADR covers the frontend UI architecture, education strategy, alert integration, and graduation path.

## Key Design Decisions

### D1: Workflow Layer, Not Replacement

**Decision:** Professional Mode is a **new entry point** (Header toggle → `/pro/*` routes) that sits **on top of** existing pages. No feature duplication — it links to existing pages for depth.

**Rationale:**
- Existing Screener, Ticker Analysis, Portfolio, Charts serve advanced users
- Professional Mode simplifies the experience without removing functionality
- Users graduate from "guided" → "explorer" → "power user" — the existing UI serves the latter two

**Consequences:**
- 4 new frontend pages under `/pro/*` routes, none overlap existing routes
- Header toggle switches between Guided (Professional) and Explorer (full) modes
- All existing pages untouched — risk level LOW

### D2: Inline + Progressive Education

**Decision:** Every metric shows a `?` tooltip → static template explanation → optional LLM-enhanced context.

**Education Stack:**
| Layer | Source | Cost | Cache |
|-------|--------|------|-------|
| Static template (30+ metrics) | `education.ts` | $0 | N/A |
| Enhanced (LLM) | `/api/v1/professional/education/{metric}` | ~$0.001/call | 24h in localStorage |
| Concept explainer cards | `ConceptExplainer` component | $0 | N/A |
| Full browser | `ConceptExplorer` component | $0 | N/A |

**Components:**
- `EducationTooltip` — hover tooltip for individual metrics (static + LLM)
- `ConceptExplainer` — inline cards for broader concepts (sector rotation, risk-on/off)
- `ConceptExplorer` — full-page browser with search (metrics/modules/glossary)

**Consequences:**
- 30+ metrics have static templates covering TECHNICAL, FUNDAMENTAL, EARNINGS, SENTIMENT, GROWTH
- LLM enhancement is off by default (env flag `CONFLU_PROFESSIONAL_LLM_EDUCATION_ENABLED`)
- All education text targets "34-year-old marketing manager with zero trading experience"

### D3: Dual-Channel Alerts

**Decision:** Two-tier notification system — email for scheduled, in-app push for real-time.

| Alert Type | Channel | Timing |
|------------|---------|--------|
| Morning Brief | Email (6 AM) + In-app banner | Scheduled (cron) |
| Stop Hit | In-app push | Real-time (polling) |
| Target Hit (1R/2R) | In-app push | Real-time |
| Earnings Tomorrow | Email (evening prior) | Scheduled (cron) |
| Regime Change | Email + In-app | On detection |
| Weekly Review | Email (Sunday 7 PM) | Scheduled (weekly) |

**Implementation:**
- **Backend:** `AlertService` (in-memory queue) + APScheduler for cron jobs
- **Email:** `EmailSender` with SendGrid (log-only fallback when no API key)
- **Frontend:** `NotificationBell` component + Zustand store with persist
- **Email templates:** Inline HTML (no file templates for v1), mobile-friendly, max-width 600px

**Consequences:**
- SendGrid on free tier covers expected volume (100 emails/day)
- In-app notifications survive page reload (localStorage persist)
- Email dispatch is safe-by-default — logs HTML when no API key configured

### D4: Time-Gated Graduation with Manual Override

**Decision:** Default = Professional Mode ON with time-gated feature unlocks. User can disable anytime.

**Unlock Schedule:**
| Feature | Unlock Day | Rationale |
|---------|------------|-----------|
| Morning Brief, Verdict, Watchlist | 1 | Core workflow — needed immediately |
| All 21 screens | 14 | After 2 weeks, ready to explore |
| Deep analysis (8 tabs) | 30 | 1 month of daily briefs builds context |
| Backtest engine, portfolio | 60 | 2 months before strategy evaluation |
| Full charts | 90 | 3 months before technical analysis |

**Implementation:**
- `startDate` stored in localStorage (set when user first enables Pro Mode)
- `getUnlockedFeatures(daysActive)` computes current unlocked set
- Locked features show 🔒 badge with "Unlocks in N days" tooltip
- Graduation progress bar in Settings shows overall completion

**Consequences:**
- Time-gating prevents overwhelm — user sees only relevant features
- Manual override respects autonomy — toggle in header or settings
- No complex action tracking needed — purely time-based

## Architecture Overview

### Frontend File Map

```
frontend/src/
├── types/professional.ts          — 12 interfaces + UNLOCK_SCHEDULE
├── api/professional.ts            — 7 API functions (react-query)
├── store/professional.ts          — Zustand store (persisted)
├── hooks/
│   ├── useProMode.ts              — Derived hook (unlock state)
│   ├── useEducation.ts            — Education content hook + API hooks
│   └── useAlerts.ts               — Existing alerts hook (extended)
├── components/professional/
│   ├── MorningBriefPage.tsx        — Full morning brief dashboard
│   ├── SimpleVerdictPage.tsx       — One-click verdict
│   ├── WatchlistBuilderPage.tsx    — Watchlist builder
│   ├── ProSettingsPage.tsx         — Settings + graduation progress
│   ├── TickerCard.tsx              — Reusable ticker card
│   ├── EducationTooltip.tsx        — Hover metric education
│   ├── ConceptExplainer.tsx        — Inline concept cards
│   ├── ConceptExplorer.tsx         — Full concept browser
│   ├── MarketInternalsStrip.tsx    — VIX/breadth/futures strip
│   ├── SectorHeatmapMini.tsx       — Sector rotation mini heatmap
│   ├── NotificationBell.tsx        — In-app notification center
│   └── GraduationProgress.tsx      — Feature unlock progress
├── components/layout/Header.tsx    — (Modified) Toggle + bell
└── App.tsx                         — (Modified) 4 /pro/* routes
```

### Integration Points

| Existing Module | Integration |
|----------------|-------------|
| `TVScreenEngine.screen()` | MorningBriefService runs 3 screens |
| `EliteSignalProcessor` | RS Rating, Inst Quality, Conviction |
| `RiskEngine.position_size()` | PositionSizer use (delegated) |
| `SectorRotationService` | Sector heatmap data |
| `MarketRegimeService` | Regime badge |
| `PortfolioStore` | Watchlist → Portfolio flow |

## Consequences

**Positive:**
- Professional users get a guided workflow; existing users unchanged
- All new files in separate directories — zero risk to existing features
- Education system is cost-controlled (static by default, LLM opt-in)
- Graduation path prevents user overwhelm
- Email works without SendGrid setup (log-only dev mode)

**Neutral:**
- 5 new backend services to maintain
- 12 new frontend components to maintain
- APScheduler adds a new dependency (`apscheduler` package)
- Email HTML templates are inline (harder to edit, but simpler for v1)

**Negative:**
- Graduation is time-based, not competency-based — users who learn fast still wait
- Education templates need manual updates as new metrics are added
- No real brokerage integration yet (deferred to v1.1)
- LLM education costs could scale with users (mitigated by caching + fallback)

## Related Decisions
- D-27: Professional Mode Backend Architecture (service design, API endpoints)
