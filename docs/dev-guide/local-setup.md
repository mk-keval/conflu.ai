# Local Development Setup

## Quick Start

```bash
# Backend
python -m venv .venv
source .venv/bin/activate
uv pip install -e ".[dev,test,observability]"

# Run with Docker
docker compose up -d
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CONFLU_CORE__LOG_LEVEL` | `INFO` | Log level |
| `CONFLU_CORE__LOG_JSON` | `true` | JSON log output |
| `CONFLU_CORE__DUCKDB_PATH` | `data/conflu.duckdb` | Database path |
| `CONFLU_API__HOST` | `0.0.0.0` | API bind address |
| `CONFLU_API__PORT` | `8000` | API port |
| `CONFLU_API__OTEL_EXPORTER_OTLP_ENDPOINT` | `` | OpenTelemetry endpoint |

## Docker Compose Profiles

- **Default** (`docker compose up`): API, worker, frontend, redis
- **With Observability** (`docker compose --profile observability up`): Adds Prometheus + Grafana for API metrics

## Debugging

- Backend debug port: `5678` (debugpy)
- Frontend dev server: `http://localhost:5173`
- API docs: `http://localhost:8000/docs`
- Grafana: `http://localhost:3000` (admin/admin) — requires `--profile observability`
- Prometheus: `http://localhost:9090` — requires `--profile observability`
