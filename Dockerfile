# =============================================================================
# Speedtest Exporter - Prometheus Metrics for Network Speed
# =============================================================================
# Multi-stage build with official Ookla Speedtest CLI
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Build Python Dependencies
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS builder

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        gnupg \
    && rm -rf /var/lib/apt/lists/*

# Build Python wheels for offline installation
WORKDIR /build
RUN python -m pip install --upgrade pip && \
    pip wheel --wheel-dir /wheels prometheus_client

# -----------------------------------------------------------------------------
# Stage 2: Minimal Runtime Image
# -----------------------------------------------------------------------------
FROM python:3.11-slim

# OCI Image Specification Labels
# https://github.com/opencontainers/image-spec/blob/main/annotations.md
LABEL org.opencontainers.image.title="speedtest-exporter" \
      org.opencontainers.image.description="Prometheus exporter for Ookla Speedtest metrics" \
      org.opencontainers.image.authors="Noah Nowak <nnowak@cryshell.com>" \
      org.opencontainers.image.url="https://github.com/barrax63/speedtest-kit" \
      org.opencontainers.image.source="https://github.com/barrax63/speedtest-kit" \
      org.opencontainers.image.documentation="https://github.com/barrax63/speedtest-kit/blob/main/README.md" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.base.name="docker.io/library/python:3.11-slim"

ENV DEBIAN_FRONTEND=noninteractive

# Install Ookla Speedtest CLI from official repository
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        gnupg \
    && rm -rf /var/lib/apt/lists/* \
    && curl -s https://packagecloud.io/install/repositories/ookla/speedtest-cli/script.deb.sh | bash \
    && apt-get update && apt-get install -y --no-install-recommends speedtest \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies from builder stage
COPY --from=builder /wheels /wheels
RUN python -m pip install --no-cache-dir /wheels/* && \
    rm -rf /wheels

# Create non-root user for security
RUN useradd -r -d /etc/speedtest -s /usr/sbin/nologin speeduser

# Setup application directory (matches docker-compose volume mount path)
RUN mkdir -p /etc/speedtest && \
    chown -R speeduser:speeduser /etc/speedtest

WORKDIR /etc/speedtest

# Copy script (will be overridden by volume mount in docker-compose)
COPY --chown=speeduser:speeduser speedtest_v3.py ./speedtest_v3.py

# Health check for Prometheus endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD timeout 2 bash -c '</dev/tcp/127.0.0.1/9110' || exit 1

# Run as non-root user
USER speeduser

# Prometheus metrics port
EXPOSE 9110

CMD ["python", "/etc/speedtest/speedtest_v3.py"]
