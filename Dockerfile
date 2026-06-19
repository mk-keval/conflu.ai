# Stage 1: Builder
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir --user .

# Stage 2: Runtime
FROM python:3.11-slim AS runtime

# Create non-root user
RUN groupadd -r conflu && useradd -r -g conflu -d /app -s /bin/false conflu

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local

# Ensure local bin is in PATH
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY backend/ ./backend/
COPY config.yaml ./

# Create data directory with write permissions
RUN mkdir -p /app/data && chown -R conflu:conflu /app/data

USER conflu

# Default command (overridden by docker-compose)
CMD ["python", "-c", "import conflu; print('conflu.ai ready')"]
