# Getting Started

## Prerequisites

- Python 3.11+
- Node.js 20+
- Docker & Docker Compose v2
- Git

## Local Development Setup

### 1. Clone the Repository

```bash
git clone https://github.com/keval/conflu.ai.git
cd conflu.ai
```

### 2. Backend Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install with uv (recommended)
pip install uv
uv pip install -e ".[dev,test,observability]"

# Or with pip
pip install -e ".[dev,test,observability]"
```

### 3. Frontend Setup

```bash
cd frontend
npm install
```

### 4. Run with Docker Compose

```bash
docker compose up -d
```

- Frontend: http://localhost:5173
- API: http://localhost:8000
- Swagger Docs: http://localhost:8000/docs

### 5. Initialize Database & Ingest Data

```bash
# Initialize DuckDB tables
python -m backend.app.infrastructure.ingest.cli --setup

# Ingest market data (run once to populate database)
# This fetches OHLCV from TradingView and stores in DuckDB
python -m backend.app.infrastructure.ingest.cli --asset-class crypto --timeframe 1D --dry-run  # Test first
python -m backend.app.infrastructure.ingest.cli --asset-class crypto --timeframe 1D  # Actual run

# Ingest all asset classes & timeframes
python -m backend.app.infrastructure.ingest.cli
```

### 6. Verify Installation

```bash
# Health check
curl http://localhost:8000/health

# Should return:
# {"status":"ok","service":"conflu-api","version":"0.2.0"}

# Test screener
curl -X POST http://localhost:8000/api/v1/screen \
  -H "Content-Type: application/json" \
  -d '{"config": "trend-follower"}'
```

## Configuration

See `config.yaml` for all configuration options. Environment variables override YAML settings:

- `CONFLU_CORE__LOG_LEVEL=DEBUG` for verbose logging
- `CONFLU_CORE__DUCKDB_PATH=/path/to/custom.duckdb` for custom database path

## Running Tests

```bash
# Backend tests
pytest backend/tests/ -v

# Frontend lint and type check
cd frontend && npm run lint && npm run typecheck
```
