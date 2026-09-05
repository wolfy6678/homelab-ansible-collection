#!/usr/bin/env python3
"""Push a compact homelab infra-health summary to a private TRMNL plugin.

Reads per-host metrics from Prometheus (the node_exporter job) and POSTs a
small JSON payload of merge variables to a TRMNL private-plugin webhook. The
flow is outbound only — nothing inbound is exposed, so Prometheus/Grafana stay
LAN-only. Stdlib only (urllib); no pip dependencies.

Env:
  TRMNL_URL   full webhook endpoint incl. the plugin UUID (required)
  PROM_URL    Prometheus base URL (default http://localhost:9090)
  NODE_JOB    node_exporter job label (default "node")
  TIMEOUT     per-request timeout in seconds (default 10)
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

PROM = os.environ.get("PROM_URL", "http://localhost:9090").rstrip("/")
TRMNL = os.environ.get("TRMNL_URL", "").strip()
JOB = os.environ.get("NODE_JOB", "node")
TIMEOUT = float(os.environ.get("TIMEOUT", "10"))

# TRMNL's free tier rejects payloads over 2 KB with a 4xx.
MAX_BYTES = 2048


def prom_query(expr):
    """Run an instant query and return {instance: float}."""
    url = PROM + "/api/v1/query?" + urllib.parse.urlencode({"query": expr})
    with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:
        data = json.load(resp)
    if data.get("status") != "success":
        raise RuntimeError("prometheus query failed: %s" % expr)
    out = {}
    for r in data["data"]["result"]:
        out[r["metric"].get("instance", "?")] = float(r["value"][1])
    return out


def clamp_pct(x):
    return max(0, min(100, int(round(x))))


def main():
    if not TRMNL:
        sys.exit("TRMNL_URL is not set")

    j = 'job="%s"' % JOB
    up = prom_query("up{%s}" % j)
    cpu = prom_query(
        "100 - (avg by (instance) "
        "(rate(node_cpu_seconds_total{%s,mode=\"idle\"}[5m])) * 100)" % j
    )
    mem = prom_query(
        "(1 - node_memory_MemAvailable_bytes{%s} "
        "/ node_memory_MemTotal_bytes{%s}) * 100" % (j, j)
    )
    # fstype filter guards against a second series at "/" (overlay/tmpfs) that
    # would otherwise clobber the real root device in the by-instance dict.
    rootfs = '%s,mountpoint="/",fstype!~"tmpfs|overlay|squashfs"' % j
    disk = prom_query(
        "100 - (node_filesystem_avail_bytes{%s} "
        "/ node_filesystem_size_bytes{%s} * 100)" % (rootfs, rootfs)
    )
    load = prom_query("node_load1{%s}" % j)

    hosts = []
    for inst in sorted(up):
        alive = up[inst] >= 1
        row = {"n": inst, "u": 1 if alive else 0}
        if alive:
            if inst in cpu:
                row["c"] = clamp_pct(cpu[inst])
            if inst in mem:
                row["m"] = clamp_pct(mem[inst])
            if inst in disk:
                row["d"] = clamp_pct(disk[inst])
            if inst in load:
                row["l"] = round(load[inst], 1)
        hosts.append(row)

    up_count = sum(1 for h in hosts if h["u"])
    payload = {
        "merge_variables": {
            "up": up_count,
            "total": len(hosts),
            "ts": time.strftime("%H:%M"),
            "hosts": hosts,
        }
    }

    def encode():
        return json.dumps(payload, separators=(",", ":")).encode()

    # Keep the payload under TRMNL's cap by shedding detail, worst case first:
    # drop the least-critical column (load), then trim whole hosts off the tail
    # so the display still updates rather than the push failing outright.
    body = encode()
    if len(body) > MAX_BYTES:
        for h in hosts:
            h.pop("l", None)
        body = encode()
    dropped = 0
    while len(body) > MAX_BYTES and len(hosts) > 1:
        hosts.pop()
        dropped += 1
        body = encode()
    if dropped:
        print("warning: payload over %d B, dropped %d host row(s)"
              % (MAX_BYTES, dropped), file=sys.stderr)

    req = urllib.request.Request(
        TRMNL, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            code = resp.getcode()
    except urllib.error.HTTPError as e:
        # A rate-limit is transient (next tick retries) — don't fail the run,
        # which at deploy time would fail the play's validating push. Any other
        # HTTP error (e.g. a bad UUID -> 404) stays fatal so it surfaces loudly.
        if e.code == 429:
            print("skipped: TRMNL rate-limited (429); will retry next tick",
                  file=sys.stderr)
            return
        raise
    print("pushed %d/%d hosts up, %d bytes -> HTTP %d"
          % (up_count, len(hosts), len(body), code))


if __name__ == "__main__":
    main()
