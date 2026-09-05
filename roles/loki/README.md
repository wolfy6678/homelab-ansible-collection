# homelab.core.loki

Grafana Loki — the log store behind the OPNsense Security and Homelab Logs
dashboards. Installed from the pinned upstream release zip.

Runs on the monitoring host alongside Prometheus and Grafana. The `alloy` role
ships logs into it; the `grafana` role provisions the datasource that reads it.

Metrics go to Prometheus; logs go here. A map of connection origins needs
per-source-IP data — very high cardinality, an anti-pattern for a metrics store
— which is exactly what a log store is for.

## Variables worth knowing

| Variable | Default | |
| --- | --- | --- |
| `loki_retention` | `720h` | 30 days. Must be a multiple of 24h; the compactor enforces it. |
| `loki_max_query_series` | `50000` | Loki's stock 500 fails on a single day of scanner traffic. The Security dashboard's distinct-IP panels group by `src_ip`, materialising one series per blocked IP before the outer `count()`/`topk()` collapses them. Instant queries return one sample per series, so a high ceiling costs little. |
| `loki_querier_max_concurrent` | `8` | Loki splits a query per day and shard, so a 30-day panel fans out to hundreds of subqueries. The stock 4 makes a dashboard refresh queue for tens of seconds. |

## Example

```yaml
- hosts: monitoring
  roles:
    - homelab.core.loki      # before grafana, so the datasource is live at start
    - homelab.core.grafana
```

Setting `grafana_loki_url: ""` disables the datasource and the log dashboards
without removing Loki itself.
