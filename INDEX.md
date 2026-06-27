# conflu.ai — Trading Intelligence Platform

## Project Index

### Documentation
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) — Project architecture & data flow
- [SESSION LOGS](docs/SESSIONS/) — Per-session activity logs
- [CHANGELOG.md](CHANGELOG.md) — Decision log & significant changes

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
- ADR-001: DuckDB for Analytics Database
- ADR-002: vectorbt for Backtesting
- ADR-003: FastAPI for REST & WebSocket API
- ADR-005: Parquet Partitioning Strategy
- ADR-006: structlog for Structured Logging
- ADR-007: React + TypeScript for Frontend (⚠️ superseded — frontend removed)
- ADR-008: Prometheus + Grafana for Observability

### CI/CD & Infrastructure
- [CI Pipeline](.github/workflows/ci.yml) — Lint, test, security scan
- [Docker Compose](docker-compose.yml) — Full stack with observability
- [Container Builds](Dockerfile) — Multi-stage backend (uv + distroless)

## Archive: v0.1 Foundation (Legacy)
The original 10-phase plan is archived. Phases 1–2 (Data Ingestion) retained for backtest OHLCV. Phases 3–10 replaced by TV Screener architecture. See [STATE.md](STATE.md) for details.
