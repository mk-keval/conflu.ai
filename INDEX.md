# conflu.ai — Trading Intelligence Platform

## Project Index

### Documentation
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) — Project architecture & data flow
- [SESSION LOGS](docs/SESSIONS/) — Per-session activity logs
- [CHANGELOG.md](CHANGELOG.md) — Significant changes & architecture decisions

### Current GSD Phases (v1.0 — TV Screener Architecture)
- **[Phase 1: TV Screener Specialist](.planning/phases/01-tv-screener-phase1/SUMMARY.md)** — ✅ TV Screener discovery, filter map, confluence scoring, API endpoints
- **[Phase 2: Deep Analysis Orchestrator](.planning/phases/02-deep-analysis-phase2/SUMMARY.md)** — ✅ On-demand OHLCV + backtest + risk for TV-discovered tickers

### Completed & In-Progress Phases
- **Phase 3: Cleanup & Consolidation** — ✅ Deleted 23 old files, cleaned router registrations
- **Phase 4: Production Hardening** — 🔄 Waves 1–5: rate limiter, cache, API hardening, 67 tests, docs — [Session Log](docs/SESSIONS/2026-06-26_phase-04-production-hardening.md)

### GSD Artifacts
- [ROADMAP](.planning/roadmap/ROADMAP.md) — Project roadmap
- [Intel: Codebase](.planning/intel/CODEBASE.md) — Codebase overview for AI agents
- [Intel: TV Screener Reference](.planning/intel/TV_SCREENER_REFERENCE.md) — Quick reference for tradingview-screener

### AI Agent Skills
- [TV Screener Specialist](.claude/skills/tvscreener-specialist/SKILL.md) — TradingView Screener package mastery
- [GitNexus: Exploring](.claude/skills/gitnexus/gitnexus-exploring/SKILL.md) — Codebase navigation
- [GitNexus: Impact Analysis](.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md) — Change safety analysis
- [GitNexus: Debugging](.claude/skills/gitnexus/gitnexus-debugging/SKILL.md) — Bug tracing
- [GitNexus: Refactoring](.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md) — Safe code restructuring

### Developer Documentation
- [MkDocs Portal](mkdocs.yml) — Material-themed documentation site
- [Getting Started](docs/getting-started.md) — Local dev setup guide
- [API Reference](docs/API.md) — REST API documentation
- [Contributing Guide](docs/dev-guide/contributing.md) — Contribution workflow
- [Coding Standards](docs/dev-guide/coding-standards.md) — Code style & quality rules
- [Local Setup](docs/dev-guide/local-setup.md) — Environment configuration
- [Debugging Guide](docs/dev-guide/debugging.md) — Debugging techniques

### Architecture Decisions
- [Decision Log Index](docs/DECISIONS/index.md) — Architecture Decision Records
- ADR-004: TradingView Screener Integration
- ADR-001: DuckDB for Analytics Database (amended: optional, backtest/risk OHLCV only)
- ADR-002: vectorbt for Backtesting
- ADR-003: FastAPI for REST & WebSocket API
- ADR-005: Parquet Partitioning Strategy
- ADR-006: structlog for Structured Logging
- ADR-007: React + TypeScript for Frontend (⚠️ superseded — frontend removed)
- ADR-008: Prometheus + Grafana for Observability
- D-32: TV Screener-First Alignment — DuckDB Optional, IndicatorCache Retired

### CI/CD & Infrastructure
- [CI Pipeline](.github/workflows/ci.yml) — Lint, test, security scan
- [Docker Compose](docker-compose.yml) — Full stack with observability
- [Container Builds](Dockerfile) — Multi-stage backend (uv + distroless)

## Recent Activity
- **2026-08-21** — Swing Parity Wave 1 **complete** (D-33): P0.2 plan-geometry invariants (stop-beyond-zone, R/R ≥ 2 via structural stop → target extension → reasoned downgrade, WATCH→ACCUMULATE promotion on validated geometry, breakout-candle rvol conviction floor, treasury emission path with caps + NAV caveat, HOLD level-leak fixed) · P0.3 classifier calibration (biotech product-revenue path without profitability gate, pre-profit demotion exemption — KURA wrongful refusal eliminated; MSTR = treasury_asset+operating with spec-correct regime guards). Gates: 459 tests passed, lsp clean, detect_changes MEDIUM/in-scope, no schema changes. Live Stage-3 replay: ADBE RR 1.8→2.58, MELI WATCH c2→ACCUMULATE c4 RR 2.92 (veteran parity), BULL valid plan T≈12.63. [Decision D-33](docs/DECISIONS/D-33-synthesis-geometry-invariants-classifier-calibration.md) · [Session Log](docs/SESSIONS/2026-08-21_swing-parity-wave1-p0.2-p0.3-completion.md)
- **2026-08-21** — Swing Parity Wave 1 (paused mid-wave for model-config fix): Oracle + Elite-Trader critiques re-fired → plan v1.1; P0.1 sticky-empty-cache fix shipped+green; P0.2 mid-TDD (6 red spec tests) and P0.3 near-complete left uncommitted on disk. Resume: `.sisyphus/plans/RESUME-2026-08-21-swing-parity.md`. [Session Log](docs/SESSIONS/2026-08-21_swing-parity-wave1-critiques-and-p0.1.md)
- **2026-08-21** — Elite trader methodology vs app audit (analysis-only): ~85% match; gaps = external RS vs SPX, ICT microstructure, insider depth; issues = KURA clinical-stage misclassification, 20.7s cold analysis, VP render gap. [Session Log](docs/SESSIONS/2026-08-21_app-audit-elite-trader-methodology.md)
- **2026-08-21** — Elite institutional swing trading research (research-only, no code changes): 5 high-conviction setups (KURA, BULL, MELI, ADBE, MSTR) with full trade plans (entry/stop/targets/R:R/position sizing), liquidity/order-flow mapping, methodology + resources documented. [Session Log](docs/SESSIONS/2026-08-21_elite-swing-trading-research.md)
- **2026-08-16** — TV Screener-First alignment (D-32): DuckDB confirmed optional/non-load-bearing (only on-demand backtest/risk OHLCV, ADR-001 amended); indicator-cache precompute retired (D-23); fixed `/health/ready`, backtest equity table, `deep_analyze` include flags (blocking bug), singleton TVScreenEngine (cache/rate-limiter now effective), Morning Brief verdict/score/RSI bugs, pinned tradingview-screener 3.2.1 (where2 filter regression), loosened 7 zero-match presets; Prometheus request middleware active, rate-limit counter, docker healthchecks/secrets, `.env` restored; frontend API envelope + types + react-query server state (D-32). [Decision D-32](docs/DECISIONS/D-32-tv-screener-first-alignment.md)
- **2026-07-31** — Glass terminal responsive shell: frosted glass layout panels over ink background with teal/indigo ambient glow, new MobileNav bottom bar with "More" drawer, sidebar desktop-only, TickerTape integrated. [Session Log](docs/SESSIONS/2026-07-31_glass-terminal-responsive-shell.md)
- **2026-07-24** — Portfolio page (store + UI), WorkflowBar step indicator, Dashboard landing page, sector focus banner with "Best for today" regime badges. [Branch: fix/elite-trader-gaps]
- **2026-07-10** — UI bug fixes: regime popup z-index (header z-10→z-30), ticker analysis input bg-dark-700→bg-surface, "+1 more findings" now a clickable `<button>`, replaced undefined `dark-*` Tailwind classes across 3 files. All verified via Playwright (0 console errors across all pages). [Session Log](docs/SESSIONS/2026-07-10_ui-fix-playwright-verification.md)
- **2026-07-07** — Added Sector Rotation Smart Money Tracker: backend API for 11 sector ETFs with 1D/1W relative strength, momentum scoring, volume divergence analysis, rotation phase detection, and smart money flow signals. Frontend with heatmap grid, detail panel, rotation flows visualization, and educational content. [Session Log](docs/SESSIONS/2026-07-07_sector-rotation-feature.md)
- **2026-07-03** — Fixed chart crash (React hooks violation) and 4H black space (height inconsistency). Docs cleanup: removed stale references to old DuckDB screener, dead API routers, deleted CLAUDE.md duplicate. [Session Log](docs/SESSIONS/ses_20260703213318.md)
- **2026-06-30** — Scoring calibration, SHORT screens, MTF weighted stacking, all 5 factors in UI. [Session Log](docs/SESSIONS/2026-06-30_scoring-calibration-and-short-screens.md)
- **2026-06-28** — Table visual redesign: single-line cells, proportional column widths, zebra striping, sticky column fix, 40px rows, compact confluence display. [Session Log](docs/SESSIONS/2026-06-28_table-visual-redesign.md)

## Archive: v0.1 Foundation (Legacy)
The original 10-phase plan is archived. Phases 1–2 (Data Ingestion) retained for backtest OHLCV. Phases 3–10 replaced by TV Screener architecture. See [STATE.md](STATE.md) for details.
