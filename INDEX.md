# conflu.ai — Trading Intelligence Platform

## Project Index

### Documentation
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) — Project architecture & data flow
- [SESSION LOGS](docs/SESSIONS/) — Per-session activity logs
- [CHANGELOG.md](CHANGELOG.md) — Decision log & significant changes

### Phases
- [Phase 1: Foundation & Core Infrastructure](.planning/phases/01-foundation-core-infrastructure/01-SUMMARY.md) — ✅ Completed 2026-06-18
- [Phase 2: Data Ingestion Pipeline](.planning/phases/02-data-ingestion-pipeline/02-SUMMARY.md) — ✅ Completed 2026-06-19
- [Phase 3: Screener Engine](.planning/phases/03-screener-engine/03-SUMMARY.md) — ✅ Completed 2026-06-19
- [Phase 4: Backtest Engine](.planning/phases/04-backtest-engine/04-SUMMARY.md) — ✅ Completed 2026-06-19
- [Phase 5: Risk Management Engine](.planning/phases/05-risk-engine/05-SUMMARY.md) — ✅ Completed 2026-06-19
- [Phase 6: API Layer](.planning/phases/06-api-layer/06-SUMMARY.md) — ✅ Completed 2026-06-19
- [Phase 7: Frontend Core](.planning/phases/07-frontend-core/07-SUMMARY.md) — ✅ Completed 2026-06-19
- [Phase 8: Advanced Screener](.planning/phases/08-advanced-screener/08-CONTEXT.md) — ✅ Completed 2026-06-19
- [Phase 9: Advanced Backtest](.planning/phases/09-advanced-backtest/09-CONTEXT.md) — ✅ Completed 2026-06-19
- [Phase 10: Production Hardening](.planning/phases/10-production-hardening/10-SUMMARY.md) — ✅ Completed 2026-06-20

### Developer Documentation
- [MkDocs Portal](mkdocs.yml) — Material-themed documentation site (serve with `mkdocs serve`)
- [API Reference](docs/scripts/gen_api_ref.py) — Auto-generated Python API docs via mkdocstrings
- [Getting Started](docs/getting-started.md) — Local dev setup guide
- [Contributing Guide](docs/dev-guide/contributing.md) — Contribution workflow & conventions
- [Coding Standards](docs/dev-guide/coding-standards.md) — Code style & quality rules
- [Local Setup](docs/dev-guide/local-setup.md) — Environment configuration
- [Debugging Guide](docs/dev-guide/debugging.md) — Debugging techniques & debugpy config

### Architecture Decisions
- [Decision Log Index](docs/decisions/index.md) — 8 Architecture Decision Records
- ADR-001: DuckDB for Analytics Database
- ADR-002: vectorbt for Backtesting
- ADR-003: FastAPI for REST & WebSocket API
- ADR-004: TradingView Screener Integration
- ADR-005: Parquet Partitioning Strategy
- ADR-006: structlog for Structured Logging
- ADR-007: React + TypeScript for Frontend
- ADR-008: Prometheus + Grafana for Observability

### CI/CD & Infrastructure
- [CI Pipeline](.github/workflows/ci.yml) — Lint, test, security scan, Docker build, benchmarks
- [Deploy Pipeline](.github/workflows/deploy.yml) — Staging → production with approval gates
- [Security Scanning](.github/workflows/security-scan.yml) — Weekly secrets, deps, container scanning
- [Container Builds](Dockerfile) — Multi-stage backend (uv + distroless) & frontend (nginx-unprivileged)
- [Docker Compose](docker-compose.yml) — Full stack with observability services
- [Production Override](docker-compose.prod.yml) — Resource limits & restart policies

### Observability Stack
- [Prometheus](config/prometheus/prometheus.yml) — Metrics collection & alerting rules
- [Grafana](config/grafana/dashboards/api-overview.json) — API overview dashboard (provisioned)
- [Loki](config/loki/loki-config.yml) — Log aggregation
- [Tempo](config/tempo/tempo-config.yml) — Distributed tracing
- [OTEL Collector](config/otel-collector/otel-collector-config.yml) — Telemetry pipeline

### Performance & Load Testing
- [API Load Test](config/k6/api-load-test.js) — k6 staged ramp to 100 users, p95<200ms
- [WebSocket Load Test](config/k6/ws-load-test.js) — Connection pool test, p95<500ms
- [Screen Benchmark](config/k6/performance-benchmark.js) — 29-symbol screen <30s
- [Backend Benchmarks](config/benchmarks/run-backend-benchmarks.py) — 5000-symbol screen + 10yr backtest
- [Frontend Benchmarks](config/benchmarks/run-frontend-benchmarks.sh) — Bundle size <500KB gzipped

### Test Status
- **Total tests**: 198 (51 Phase 1 + 75 Phase 2 + 67 Phase 5 + 5 Phase 6)
- **Status**: ✅ All passing
- **Phase 1 suites**: config (11), database (7), models (12), indicators (8), logging (6)
- **Phase 2 suites**: scanner (7), symbol_map (11), quality (8), models (7), fetcher (6), writer (4), metrics (7), CLI (11)
- **Phase 5 suites**: risk_models (16), risk_beta (6), risk_correlation (5), risk_var (8), risk_kelly (7), risk_position_sizing (4), risk_streaming (7), risk_engine (9)
- **Phase 6 suites**: api (5)

### Recent Activity
1. **2026-06-20**: Phase 10 completed — Production Hardening (CI/CD, container hardening, observability stack, MkDocs portal, ADRs, k6 load tests, performance benchmarks)
2. **2026-06-19**: Phase 9 completed — Advanced Backtest (4 engines, 4 API endpoints, 4 frontend components: BacktestOptimizer, RegimeDetector, ReportGenerator, StrategyComparator)
3. **2026-06-19**: Phase 8 completed — Advanced Screener (6 plans, 30+ files: AlertEngine, ScreenReplay, Screen Sharing, API routers, frontend components, WebSocket integration)
4. **2026-06-19**: Phase 7 completed — Frontend Core (React 18 + TypeScript, TradingView charts, backtest dashboard, risk analytics, Docker)
5. **2026-06-19**: Phase 6 completed — API Layer (FastAPI REST + WebSocket, rate limiting, observability, error envelopes)
6. **2026-06-19**: Phase 5 completed — Risk Management Engine (67 tests, 11 source files, 8 test files)
7. **2026-06-19**: Phase 4 completed — Backtest Engine (vectorbt Portfolio simulation, walk-forward, Monte Carlo)
8. **2026-06-19**: Phase 3 completed — Screener Engine (vectorized filters, indicator cache, WebSocket streaming)
9. **2026-06-19**: Phase 2 completed — Data Ingestion Pipeline (75 tests, 9 source files, 8 test files)
10. **2026-06-18**: Phase 1 completed — Foundation & Core Infrastructure (51 tests, 17 source files)
