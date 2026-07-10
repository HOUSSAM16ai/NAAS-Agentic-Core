# Stage 1: Builder
FROM python:3.12-slim as builder

WORKDIR /app

# Performance optimizations
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100

# Install build dependencies
# Use cache mount to prevent re-downloading apt indexes
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
COPY constraints.txt .
# Use cache mount for pip to persist downloads
# OPTIMIZATION: Install CPU-only torch first to prevent downloading 2GB+ CUDA wheels
# This fixes "Codespaces not launching" due to timeout/storage exhaustion
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu && \
    pip install -r requirements.txt -c constraints.txt

# Stage 2: Final Runtime
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
# Ensure /app is in PYTHONPATH so absolute imports work
ENV PYTHONPATH="/app:$PYTHONPATH"

# Install runtime system dependencies
# libpq-dev is needed for asyncpg/psycopg2
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    procps \
    iproute2 \
    libpq-dev \
    ca-certificates \
    tar \
    && rm -rf /var/lib/apt/lists/*

# =============================================================================
# Mission Control — Grafana OSS + Prometheus as native binaries
# =============================================================================
# Replaces the Docker-compose-based observability stack (which required a
# devcontainer feature that couldn't build on this base image — see
# CLAUDE.md §6.13/§6.16). Native binaries run as supervised processes started
# by .devcontainer/supervisor.sh. No Docker socket, no privileged mode, no
# rebuild required.
#
# Sizes: Grafana ~270MB, Prometheus ~80MB. ~350MB added to the final image.
# Auto-detects CPU architecture (amd64 vs arm64) so this also works on Apple
# silicon Codespaces and ARM-based local dev hosts.
# =============================================================================
ARG GRAFANA_VERSION=11.3.0
ARG PROMETHEUS_VERSION=2.55.0

RUN set -eux; \
    arch="$(dpkg --print-architecture)"; \
    case "$arch" in \
        amd64) gf_arch=amd64; prom_arch=amd64 ;; \
        arm64) gf_arch=arm64; prom_arch=arm64 ;; \
        *) echo "Unsupported architecture: $arch" >&2; exit 1 ;; \
    esac; \
    mkdir -p /opt; \
    # ---- Grafana OSS ----------------------------------------------------- \
    curl -fsSL "https://dl.grafana.com/oss/release/grafana-${GRAFANA_VERSION}.linux-${gf_arch}.tar.gz" \
        -o /tmp/grafana.tar.gz; \
    tar -xzf /tmp/grafana.tar.gz -C /opt; \
    ln -s "/opt/grafana-v${GRAFANA_VERSION}" /opt/grafana; \
    rm -f /tmp/grafana.tar.gz; \
    # ---- Prometheus ------------------------------------------------------ \
    curl -fsSL "https://github.com/prometheus/prometheus/releases/download/v${PROMETHEUS_VERSION}/prometheus-${PROMETHEUS_VERSION}.linux-${prom_arch}.tar.gz" \
        -o /tmp/prometheus.tar.gz; \
    tar -xzf /tmp/prometheus.tar.gz -C /opt; \
    ln -s "/opt/prometheus-${PROMETHEUS_VERSION}.linux-${prom_arch}" /opt/prometheus; \
    rm -f /tmp/prometheus.tar.gz; \
    # ---- Data + log dirs (writable by appuser later) -------------------- \
    mkdir -p /var/lib/grafana /var/lib/prometheus /var/log/grafana /var/log/prometheus; \
    # ---- Sanity checks --------------------------------------------------- \
    /opt/grafana/bin/grafana-server -v; \
    /opt/prometheus/prometheus --version

# Install Node.js 20 (LTS) manually to avoid devcontainer feature GPG errors
# D-161 (ISS-127): NEVER `npm install -g npm@latest` here. npm@12.0.0 dropped
# Node 20 support (EBADENGINE: requires ^22.22.2 || ^24.15.0 || >=26.0.0) and
# broke EVERY Codespace build on EVERY branch with error 1302 the moment it was
# published — a time bomb, no repo commit involved (creation.log 2026-07-09).
# NodeSource's nodejs already bundles a compatible npm (10.8.2, lockfileVersion 3
# support). Any future npm upgrade must be PINNED to a Node-20-compatible major.
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs

# Create app user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

COPY --from=builder /usr/local/lib/python3.12/site-packages/ /usr/local/lib/python3.12/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

COPY . .

# Grant permissions
RUN chown -R appuser:appuser /app

# Set default user (can be overridden by devcontainer)
USER appuser

# Standard port
EXPOSE 8000

# Run Uvicorn targetting the exposed app instance
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
