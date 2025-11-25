# ---- Build stage: install Python deps ----
FROM python:3.11-slim AS build

# Prevent interactive apt and ensure basic tools
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates gnupg \
  && rm -rf /var/lib/apt/lists/*

# Install Python deps into a wheelhouse (prometheus_client only)
WORKDIR /app
RUN python -m pip install --upgrade pip \
 && pip wheel --wheel-dir /wheels prometheus_client

# ---- Final stage: minimal runtime with Ookla speedtest ----
FROM python:3.11-slim

# Add Ookla repo and install speedtest CLI
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates gnupg \
 && rm -rf /var/lib/apt/lists/* \
 && curl -s https://packagecloud.io/install/repositories/ookla/speedtest-cli/script.deb.sh | bash \
 && apt-get update && apt-get install -y --no-install-recommends speedtest \
 && rm -rf /var/lib/apt/lists/*

# Copy wheels from build stage and install locally
COPY --from=build /wheels /wheels
RUN python -m pip install --no-cache-dir /wheels/*

# Copy your exporter script into container
WORKDIR /etc/speedtest
# Replace the following COPY with your actual path/filename in the repo
# e.g., COPY speedtest_v3.py ./speedtest_v3.py
COPY speedtest_v3.py ./speedtest_v3.py

# Non-root user for security
RUN useradd -r -s /usr/sbin/nologin speeduser \
 && chown -R speeduser:speeduser /etc/speedtest
USER speeduser

# Expose Prometheus metrics port
EXPOSE 9110

# Run the exporter
CMD ["python", "/etc/speedtest/speedtest_v3.py"]
