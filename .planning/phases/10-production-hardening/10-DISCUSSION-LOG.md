# Phase 10: Production Hardening - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-20
**Phase:** 10-production-hardening
**Areas discussed:** CI/CD Pipeline, Containerization, Observability Stack, Documentation, Performance Benchmarks, Security

---

## CI/CD Pipeline

| Option | Description | Selected |
|--------|-------------|----------|
| GitHub Actions | Native, free for public, good ecosystem | ✓ |
| GitLab CI | Self-hosted option | |
| Jenkins | Legacy, heavy | |
| Buildkite | Good UI, paid | |

**User's choice:** GitHub Actions
**Notes:** Matrix strategy for Python 3.11/3.12 × Node 20/22. Reusable workflows for shared steps. OIDC for cloud auth.

---

## Containerization

| Option | Description | Selected |
|--------|-------------|----------|
| Multi-stage Dockerfile | Builder → runtime; distroless/Alpine | ✓ |
| Single-stage | Simple but bloated | |
| Nix/Buildpacks | Reproducible, steeper learning | |

**User's choice:** Multi-stage Dockerfile
**Notes:** Backend: Python 3.11-slim + uv; Frontend: Nginx + static; distroless base for prod

---

## Observability Stack

| Option | Description | Selected |
|--------|-------------|----------|
| Prometheus + Grafana + Loki + Tempo | Full stack, CNCF graduated | ✓ |
| OpenTelemetry + Jaeger + Prometheus | Vendor-neutral | |
| Datadog / New Relic | SaaS, expensive | |

**User's choice:** Prometheus + Grafana + Loki + Tempo (OTLP export)
**Notes:** Auto-instrumentation via OTEL Python; Prometheus metrics + Loki logs + Tempo traces

---

## Documentation

| Option | Description | Selected |
|--------|-------------|----------|
| MkDocs Material + auto API | Modern, searchable, versioned | ✓ |
| Sphinx + Sphinx-AutoAPI | Python-native | |
| Redocly / Redoc | OpenAPI rendering | |

**User's choice:** MkDocs Material + auto-generated API reference
**Notes:** Auto-generated from FastAPI OpenAPI; deploy to GitHub Pages

---

## Performance Benchmarks

| Option | Description | Selected |
|--------|-------------|----------|
| CI gates: screen 5000<30s, backtest 10yr<2s | Hard gates in CI | ✓ |
| Load testing: k6 scripts in CI | Gate on p95 < 200ms | ✓ |
| Bundle analysis: webpack-bundle-analyzer | CI gate on bundle size | |

**User's choice:** All three
**Notes:** CI gates in GitHub Actions; k6 scripts in repo; bundle size limit 500KB gzipped

---

## Security

| Option | Description | Selected |
|--------|-------------|----------|
| Trivy + pip-audit + npm audit | CI scanning | ✓ |
| TruffleHog / GitLeaks | Secret scanning | ✓ |
| Renovate | Automated dependency updates | ✓ |
| Distroless base | Minimal attack surface | ✓ |

**User's choice:** All four
**Notes:** Distroless base images; Renovate for automated PRs; TruffleHog in CI; pip-audit/npm audit

---

## OpenCode's Discretion

- Exact GitHub Actions YAML structure
- Grafana dashboard provisioning (JSON vs Grafonnet)
- OTEL collector deployment pattern
- Documentation hosting platform

---

## Deferred Ideas

- Canary deployments (Argo Rollouts)
- Chaos engineering (Litmus)
- GitOps (ArgoCD/Flux)
- Continuous profiling (py-spy)
- Cost optimization (spot/Graviton)