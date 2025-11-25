# Speedtest Kit (Speedtest Exporter + Grafana Alloy)

This Docker setup provides a production-ready internet speedtest exporter (Ookla CLI + Prometheus metrics) and Grafana Alloy for scraping and remote write, optimized for slim images and hardened runtime.

## Features

- Ookla Speedtest CLI with Prometheus metrics on port 9110
- Grafana Alloy for scraping and forwarding metrics (remote_write)
- Security hardened: no-new-privileges, AppArmor, dropped capabilities
- Minimal added capabilities for Alloy data directory initialization (CHOWN, FOWNER, DAC_OVERRIDE, SETUID, SETGID)
- Read-only containers with tmpfs for ephemeral writes
- Structured logging: JSON logging with rotation (10MB max, 5 files)
- Health checks without triggering expensive speedtests
- Resource limits: configurable CPU and memory constraints

## Directory Structure

```
.
├── Dockerfile             # Speedtest exporter container build
├── docker-compose.yml     # Service orchestration (speedtest + alloy)
├── config.alloy.sample    # Sample Grafana Alloy configuration
├── speedtest_v3.py        # Speedtest exporter script (mounted read-only)
└── README.md              # This file
```

## Setup Instructions

### 1. Clone the repository

```bash
git clone https://github.com/barrax63/speedtest-kit.git
cd speedtest-kit
```

### 1. Prepare Grafana Alloy configuration

Copy the `config.alloy.sample` file and save it as `config.alloy`. Then replace the `<YOUR_PROMETHEUS_ENDPOINT>`, `<YOUR_USERNAME>` and `<YOUR_PASSWORD>` ìnside with your Grafana credentials:

```hcl
        endpoint {
                url = "https://<YOUR_PROMETHEUS_ENDPOINT>.grafana.net/api/prom/push"
                basic_auth {
                        username = "<YOUR_USERNAME>"
                        password = "<YOUR_PASSWORD>"
                }
        }
```

Notes:
- The exporter runs a test at each scrape, so the interval is set to 60 minutes to avoid unnecessary bandwidth usage.

### 3. Build and Start

```bash
# Build the speedtest exporter image
docker compose build

# Start both services
docker compose up -d

# Follow logs
docker compose logs -f speedtest
docker compose logs -f alloy
```

## Maintenance

### Update

```bash
git pull
docker compose build --no-cache
docker compose up -d --pull always
```

### Change Scrape Interval
- Edit `config.alloy` and adjust `scrape_interval`.
- Restart Alloy:
```bash
docker compose restart alloy
```

## Security Considerations

1. Dropped Capabilities: Services use `cap_drop: [ALL]` by default; Alloy re-adds the minimal required caps.
2. Minimal Capabilities for Alloy:
   - CHOWN, FOWNER, DAC_OVERRIDE, SETUID, SETGID to initialize and write to `/var/lib/alloy/data`.
3. AppArmor: Default Docker AppArmor profile is enforced.
4. No New Privileges: Prevents privilege escalation in both containers.
5. Read-only Filesystem: Speedtest container uses `read_only: true` with `tmpfs` for `/tmp`.
6. Immutable Config: `config.alloy` and `speedtest_v2.py` are mounted read-only.
7. Healthcheck Safety: Speedtest healthcheck uses a TCP socket check to avoid triggering a test.
8. Resource Limits: CPU/memory limits and reservations are set for both services.

## Notes and Tips

- The exporter runs a speed test on every scrape; keep the scrape interval conservative (e.g., 60m).
- If you need a non-triggering liveness probe, consider adding a lightweight `/healthz` endpoint in the exporter and point the healthcheck there.
- If Alloy storage permissions fail on a different host, ensure the volume/bind mount is writable by the Alloy runtime user or keep the minimal capabilities as provided.

## License

This project is licensed under the Apache License 2.0 - see the LICENSE file for details.