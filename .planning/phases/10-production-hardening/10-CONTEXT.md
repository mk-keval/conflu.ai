# Phase 10: Production Hardening - Context

**Gathered:** 2026-06-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Production Hardening: Transform the conflu.ai trading platform from a feature-complete application into a production-ready system. This phase covers CI/CD pipeline, containerization, observability stack, documentation, and performance optimization.
</domain>

<decisions>
## Implementation Decisions

### CI/CD Pipeline (GitHub Actions)
- **D-01:** GitHub Actions workflow with 4 jobs: lint/type-check, backend tests, frontend tests, build/push Docker images
- **D-02:** Triggers: push to main, PR to main, manual dispatch; matrix strategy for Python 3.11/3.12, Node 20/22
- **D-03:** Artifacts: test reports, coverage, Docker images (GHCR), SBOM (Syft)
- **D-04:** Deployment: staging auto-deploy on main, production requires manual approval
- **D-05:** Secrets management: GitHub Environments + OIDC for cloud provider auth

### Containerization
- **D-06:** Multi-stage Dockerfiles: builder (with dev deps) → runtime (distroless/Alpine); shared base image
- **D-07:** Backend: Python 3.11 slim, uv for fast installs, non-root user, healthcheck endpoint
- **D-010:** Frontend: Nginx + static files + API proxy; SPA fallback; gzip/brotli compression
- **D-11:** Docker Compose v2 override for local dev (hot reload) vs prod (optimized)
- **D-11:** Image scanning: Trivy in CI; SBOM generation

### Observability Stack
- **D-12:** Prometheus + Grafana: pre-built dashboards for API latency, error rates, cache hit rates, business metrics
- **D-13:** OpenTelemetry: auto-instrumentation (FastAPI, SQLAlchemy, Redis, HTTPX); OTLP export to Tempo/Jaeger
- **D-14:** Logging: structured JSON (structlog) → Loki; correlation IDs propagated via headers
- **D-15:** Alerting: PrometheusRule CRDs for latency/error rate/budget alerts; PagerDuty/Slack webhooks

### Documentation
- **D-16:** API docs: auto-generated from FastAPI OpenAPI spec → Redoc + Swagger UI
- **D-11:** Architecture docs: Mermaid diagrams (C4 model) in docs/architecture/; ADR log in docs/decisions/
- **D-13:** User guide: Getting started, screener guide, backtest guide, risk guide, API reference
- **D-18:** Developer guide: Contributing, coding standards, local dev setup, debugging tips

### Performance Benchmarks
- **D-18:** CI performance gates: 5000 symbols < 30s screen, 10yr backtest < 2s
- **D-19:** Load testing: k6 scripts for API/WS endpoints; CI gate on p95 < 200ms
- **D-20:** Profiling: py-spy / cProfile in CI; frontend bundle analysis (webpack-bundle-analyzer)

### Security
- **D-21:** Dependency scanning: pip-audit / npm audit in CI; Renovate for automated PRs
- **D-22:** Secret scanning: TruffleHog/GitLeaks in CI; pre-commit hooks
- **D-23:** Container hardening: non-root, read-only fs, dropped capabilities, seccomp profile

### OpenCode's Discretion
- **D-25:** Exact GitHub Actions YAML structure (matrix, caching strategy, reusable workflows)
- **D-26:** Grafana dashboard JSON vs code (Grafonnet/Tanka vs JSON)
- **D-27:** OpenTelemetry collector deployment (sidecar vs gateway)
- **D-29:** Documentation hosting (GitHub Pages vs ReadTheDocs vs Mintlify)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 1-9 Foundations
- `.planning/phases/01-foundation-core-infrastructure/01-CONTEXT.md` — Core decisions
- `.planning/phases/02-data-ingestion-pipeline/02-CONTEXT.md` — Data decisions
- `.planning/phases/03-screener-engine/03-CONTEXT.md` — Screener decisions
- `.planning/phases/04-backtest-engine/04-CONTEXT.md` — Backtest decisions
- `.planning/phases/05-risk-engine/05-CONTEXT.md` — Risk engine decisions
- `.planning/phases/06-api-layer/06-CONTEXT` — API layer decisions
- `.planning/phases/07-frontend-core/07-CONTEXT` — Frontend architecture
- `.planning/phases/08-advanced-screener/08-CONTEXT` — Advanced screener
- `.planning/phases/09-advanced-backtest/09-CONTEXT` — Advanced backtest decisions

### Existing Code Assets
- `.github/workflows/` — Existing CI workflows (if any)
- `Dockerfile` / `Dockerfile.frontend` / `docker-compose.yml` — Current containerization
- `backend/app/api/main.py` — FastAPI app factory
- `frontend/` — Vite + React app
- `docker-compose.yml` — Local dev stack
- `config.yaml` — Application config
- `pyproject.toml` / `package.json` — Dependencies
- `docs/` — Existing documentation structure

### External Documentation
- GitHub Actions: https://docs.github.com/en/actions
- Docker multi-stage: https://docs.docker.com/build/building/multi-stage/
- Prometheus: https://prometheus.io/docs/
- Grafana: https://grafana.com/docs/
- OpenTelemetry Python: https://opentelemetry.io/docs/instrumentation/python/
- WeasyPrint: https://weasyprint.org/

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets (from Phases 1-9)
- `.github/workflows/` — May have existing CI workflows
- `Dockerfile` / `Dockerfile.frontend` — Existing containerization
- `docker-compose.yml` — Local dev stack (backend, worker, redis, postgres?)
- `backend/app/api/main.py` — FastAPI app factory with lifespan
- `frontend/` — Vite + React 18 + TypeScript + Tailwind
- `backend/app/core/config.py` — Settings with pydantic-settings
- `backend/app/core/logging.py` — structlog configuration
- `backend/app/core/database.py` — DuckDB connection pool
- `pyproject.toml` / `package.json` — Dependencies + scripts

### Established Patterns
- Multi-stage Dockerfiles with shared base
- Structured logging with structlog + correlation IDs
- Pydantic Settings with YAML + env override
- DuckDB for analytics, Redis for caching/queues
- FastAPI + Pydantic + OpenAPI auto-docs
- React Query + Zustand + Tailwind + Lightweight Charts
- GitHub Actions with matrix strategy

### Integration Points
- Phase 1-9 outputs → CI/CD artifacts
- API layer (Phase 6) → health/readiness endpoints for k8s probes
- Frontend (Phase 7) → Vite build output served by Nginx
- Backtest engine (Phase 4/9) → performance test targets
- Risk engine (Phase 5) → metrics for Grafana dashboards

</code_context>

<specifics>
## Specific Ideas

- CI: Cache pip/uv cache + npm cache; use `uv` for Python installs
- Docker: Distroless base for production; `uv` for Python package installs
- Grafana: Provision datasources/dashboards via ConfigMaps; JSON model in repo
- OTEL: Auto-instrumentation for FastAPI + SQLAlchemy + httpx + Redis
- Docs: MkDocs Material + auto-generated API reference; deploy to GitHub Pages
- Performance gates: Fail CI if p95 > 200ms (API) or screen > 30s / 5000 symbols

</specifics>

<deferred>
## Deferred Ideas

- Canary deployments with Argo Rollouts / Flagger
- Chaos engineering (Litmus/Chaos Mesh)
- Full GitOps with ArgoCD / Flux
- Advanced profiling (py-spy continuous profiling)
- Cost optimization (spot instances, Graviton)

None — discussion stayed within phase scope
</deferred>

---

*Phase: 10-Production Hardening*
*Context gathered: 2026-06-20*