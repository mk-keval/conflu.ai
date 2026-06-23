# Stage 1 — uv-builder: Install dependencies with uv
FROM python:3.12-slim AS builder

# Install uv
RUN pip install uv --no-cache-dir

WORKDIR /build

# Copy dependency files and source code for layer caching
COPY pyproject.toml ./
COPY backend/ ./backend/

# Install main dependencies
RUN uv pip install --system . --no-cache-dir

# Install observability extras
RUN uv pip install --system ".[observability]" --no-cache-dir

# Clean caches
RUN rm -rf /root/.cache/pip /root/.cache/uv

# Stage 2 — runtime: Distroless production image
FROM gcr.io/distroless/python3-debian12:nonroot AS runtime

ENV PYTHONPATH=/app

# Copy installed site-packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages

# Copy application code
COPY backend/ /app/backend/
COPY config.yaml /app/config.yaml

USER nonroot:nonroot
WORKDIR /app

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]

EXPOSE 8000

LABEL org.opencontainers.image.source=https://github.com/keval/conflu.ai

CMD ["python", "-m", "uvicorn", "backend.app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Stage 3 — dev: Development image with reload and debug tools
FROM python:3.12-slim AS dev

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages

# Copy application code
COPY backend/ /app/backend/
COPY config.yaml /app/config.yaml

# Install dev/test dependencies
RUN pip install --no-cache-dir -e ".[dev,test,observability]" 2>/dev/null || true

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "backend.app.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
