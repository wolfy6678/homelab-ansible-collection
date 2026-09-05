#!/usr/bin/env python3
"""Managed by Ansible — do not edit on the host.

SMART disk-health metrics for node_exporter's textfile collector. Scans every
physical disk with smartctl (JSON output, smartmontools 7+) and writes
smartmon_* gauges: overall health, temperature, power-on hours, plus the
early-failure indicators (ATA reallocated sectors, NVMe wear/media errors).
Feeds the SMART row on the "Proxmox" Grafana dashboard and the disk-health
alert. Run by smart-metrics.timer as root (smartctl needs raw device access).

Usage: smart_metrics.py <textfile-dir>
"""
import json
import os
import subprocess
import sys
import tempfile


def smartctl(args):
    # smartctl uses its exit status as a bitmask (failing SMART attributes set
    # bits even when the command succeeds), so parse stdout regardless.
    out = subprocess.run(
        ["smartctl", "--json"] + args, capture_output=True, text=True, check=False
    ).stdout
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return {}


def gather():
    lines = {}  # metric name -> list of "name{labels} value"

    def emit(metric, labels, value):
        pairs = ", ".join(f'{k}="{v}"' for k, v in labels.items())
        lines.setdefault(metric, []).append(f"{metric}{{{pairs}}} {value}")

    for dev in smartctl(["--scan"]).get("devices", []):
        data = smartctl(["-a", "-d", dev.get("type", "auto"), dev["name"]])
        if not data:
            continue
        labels = {
            "disk": dev["name"],
            "model": data.get("model_name", "unknown"),
            "serial": data.get("serial_number", "unknown"),
        }
        if "smart_status" in data:
            emit("smartmon_device_smart_healthy", labels,
                 int(bool(data["smart_status"].get("passed"))))
        temp = data.get("temperature", {}).get("current")
        if temp is not None:
            emit("smartmon_temperature_celsius", labels, temp)
        hours = data.get("power_on_time", {}).get("hours")
        if hours is not None:
            emit("smartmon_power_on_hours", labels, hours)
        for attr in data.get("ata_smart_attributes", {}).get("table", []):
            if attr.get("id") == 5:
                emit("smartmon_reallocated_sectors", labels,
                     attr.get("raw", {}).get("value", 0))
        nvme = data.get("nvme_smart_health_information_log")
        if nvme:
            if "percentage_used" in nvme:
                emit("smartmon_nvme_percentage_used", labels, nvme["percentage_used"])
            if "media_errors" in nvme:
                emit("smartmon_nvme_media_errors", labels, nvme["media_errors"])
    return lines


HELP = {
    "smartmon_device_smart_healthy": "SMART overall health self-assessment (1 = passed).",
    "smartmon_temperature_celsius": "Current disk temperature.",
    "smartmon_power_on_hours": "Cumulative power-on hours.",
    "smartmon_reallocated_sectors": "ATA attribute 5 raw value — non-zero means the disk is remapping bad sectors.",
    "smartmon_nvme_percentage_used": "NVMe endurance used estimate (percent).",
    "smartmon_nvme_media_errors": "NVMe media and data integrity errors.",
}


def main():
    textfile_dir = sys.argv[1]
    os.makedirs(textfile_dir, exist_ok=True)
    metrics = gather()
    fd, tmp = tempfile.mkstemp(dir=textfile_dir, suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        for metric in sorted(metrics):
            f.write(f"# HELP {metric} {HELP[metric]}\n")
            f.write(f"# TYPE {metric} gauge\n")
            for line in metrics[metric]:
                f.write(line + "\n")
    os.chmod(tmp, 0o644)
    os.replace(tmp, os.path.join(textfile_dir, "smartmon.prom"))


if __name__ == "__main__":
    main()
