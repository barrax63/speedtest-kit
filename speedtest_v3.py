#!/usr/bin/env python3
import subprocess
import json
import time
import logging
from prometheus_client import Gauge, CollectorRegistry
from prometheus_client.core import REGISTRY
from http.server import HTTPServer
from prometheus_client.exposition import MetricsHandler

# ------------------------------------------------------------------
# Preferred server IDs (first usable ID wins; order them by proximity)
# Comment out for auto-selected server
# 48042 - htp GmbH Hannover
# 31469 - Deutsche Telekom Hamburg
# 30906 - Deutsche Telekom Düsseldorf
SERVER_IDS = ["31469", "30906"]
# ------------------------------------------------------------------

# Prometheus registry and gauges
registry = CollectorRegistry()
g_download = Gauge(
    "speedtest_download",
    "Download speed in bits per second",
    ["timestamp"],
    registry=registry,
)
g_upload = Gauge(
    "speedtest_upload",
    "Upload speed in bits per second",
    ["timestamp"],
    registry=registry,
)
g_jitter = Gauge(
    "speedtest_jitter", "Jitter time in milliseconds", ["timestamp"], registry=registry
)
g_ping = Gauge(
    "speedtest_ping", "Ping time in milliseconds", ["timestamp"], registry=registry
)
g_packetloss = Gauge(
    "speedtest_packetloss", "Packet loss in percent", ["timestamp"], registry=registry
)
g_bytes_sent = Gauge(
    "speedtest_bytes_sent",
    "Bytes sent during the test",
    ["timestamp"],
    registry=registry,
)
g_bytes_received = Gauge(
    "speedtest_bytes_received",
    "Bytes received during the test",
    ["timestamp"],
    registry=registry,
)
g_elapsed_time = Gauge(
    "speedtest_elapsed_time",
    "Elapsed time for the test in seconds",
    ["timestamp"],
    registry=registry,
)
g_server_info = Gauge(
    "speedtest_server_info",
    "Server information",
    ["timestamp", "id", "name", "location", "country", "ip"],
    registry=registry,
)
g_client_info = Gauge(
    "speedtest_client_info",
    "Client information",
    ["timestamp", "ip", "vpn", "isp"],
    registry=registry,
)
g_result_info = Gauge(
    "speedtest_result_info",
    "Result information",
    ["timestamp", "url"],
    registry=registry,
)

# Log to stdout/stderr (no file)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

OOKLA_BIN = "speedtest"
OOKLA_OPTS = ["--accept-license", "--accept-gdpr", "-f", "json-pretty", "-u", "bps"]


def run_speedtest():
    """Run Ookla CLI against the first usable server in SERVER_IDS if present."""
    pref_servers = globals().get("SERVER_IDS", [])

    logging.info(
        "Running Ookla speedtest (preferred servers: %s)",
        ", ".join(map(str, pref_servers)) if pref_servers else "auto-selected",
    )

    for sid in (pref_servers or [None]):
        target = sid if sid else "auto"
        cmd = [OOKLA_BIN] + (["-s", str(sid)] if sid else []) + OOKLA_OPTS
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=180, check=True
            )
        except subprocess.CalledProcessError as exc:
            logging.warning("Server %s failed (%s). Trying next ID.", target, exc)
            continue  # try next ID
        except subprocess.TimeoutExpired:
            logging.warning("Server %s timed out. Trying next ID.", target)
            continue

        # Parse JSON and convert into the structure expected by update_metrics()
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            logging.error("JSON parse error for server %s: %s", target, exc)
            continue

        # ---- map Ookla fields -----------------------------------------------------
        results = {
            "download": (data.get("download") or {}).get("bandwidth", 0) * 8,
            "upload": (data.get("upload") or {}).get("bandwidth", 0) * 8,
            "jitter": (data.get("ping") or {}).get("jitter", 0),
            "ping": (data.get("ping") or {}).get("latency", 0),
            "packetloss": data.get("packetLoss", 0),
            "bytes_sent": (data.get("upload") or {}).get("bytes", 0),
            "bytes_received": (data.get("download") or {}).get("bytes", 0),
            "elapsed_time": (
                (data.get("upload") or {}).get("elapsed", 0)
                + (data.get("download") or {}).get("elapsed", 0)
            ) / 1000,
            "timestamp": data.get("timestamp", ""),
            "server": {
                "id": (data.get("server") or {}).get("id", "unknown"),
                "name": (data.get("server") or {}).get("name", "unknown"),
                "location": (data.get("server") or {}).get("location", "unknown"),
                "country": (data.get("server") or {}).get("country", "unknown"),
                "ip": (data.get("server") or {}).get("ip", "unknown"),
            },
            "client": {
                "ip": (data.get("interface") or {}).get("externalIp", "unknown"),
                "vpn": (data.get("interface") or {}).get("isVpn", "unknown"),
                "isp": data.get("isp", "unknown"),
            },
            "result": {
                "url": (data.get("result") or {}).get("url", "unknown"),
            },
        }

        logging.info("Speedtest results (%s): %s", target, results)
        return results

    logging.error("All preferred servers failed or unavailable")
    return None


def update_metrics(results):
    if results is None:
        logging.error("No results to update metrics with")
        return

    ts_label = str(int(time.time()))

    for g in (
        g_download,
        g_upload,
        g_jitter,
        g_ping,
        g_packetloss,
        g_bytes_sent,
        g_bytes_received,
        g_elapsed_time,
        g_server_info,
        g_client_info,
        g_result_info,
    ):
        g.clear()

    g_download.labels(timestamp=ts_label).set(results["download"])
    g_upload.labels(timestamp=ts_label).set(results["upload"])
    g_jitter.labels(timestamp=ts_label).set(results["jitter"])
    g_ping.labels(timestamp=ts_label).set(results["ping"])
    g_packetloss.labels(timestamp=ts_label).set(results["packetloss"])
    g_bytes_sent.labels(timestamp=ts_label).set(results["bytes_sent"])
    g_bytes_received.labels(timestamp=ts_label).set(results["bytes_received"])
    g_elapsed_time.labels(timestamp=ts_label).set(results["elapsed_time"])

    srv = results["server"]
    g_server_info.labels(
        ts_label, srv["id"], srv["name"], srv["location"], srv["country"], srv["ip"]
    ).set(1)

    cli = results["client"]
    g_client_info.labels(ts_label, cli["ip"], cli["vpn"], cli["isp"]).set(1)

    res = results["result"]
    g_result_info.labels(ts_label, res["url"]).set(1)


class SpeedtestCollector:
    """Prometheus collector that runs a speed test on every scrape."""

    def collect(self):
        update_metrics(run_speedtest())
        return registry.collect()


if __name__ == "__main__":
    # Remove default collectors and register our own
    for collector in list(REGISTRY._collector_to_names.keys()):
        REGISTRY.unregister(collector)
    REGISTRY.register(SpeedtestCollector())

    httpd = HTTPServer(("0.0.0.0", 9110), MetricsHandler)
    logging.info("Exporter listening on port 9110")
    httpd.serve_forever()
