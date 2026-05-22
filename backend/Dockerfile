# ClinNote AI — Backend Dockerfile
# ====================================
# Multi-stage build for minimal production image

# ---------------------------------------------------------------------------
# Stage 1: Builder — install dependencies
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies (for asyncpg, cryptography, bcrypt)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libssl-dev \
    libffi-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---------------------------------------------------------------------------
# Stage 2: Runtime — lean production image
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY . .

# Create non-root user for security
RUN groupadd --gid 1001 clinnote && \
    useradd --uid 1001 --gid clinnote --shell /bin/bash --create-home clinnote && \
    chown -R clinnote:clinnote /app

USER clinnote

# Environment defaults (override via docker-compose / k8s secrets)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT=8000

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# ---------------------------------------------------------------------------
# Startup command
# ---------------------------------------------------------------------------
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--loop", "uvloop", \
     "--http", "httptools", \
     "--log-level", "info", \
     "--access-log"]
