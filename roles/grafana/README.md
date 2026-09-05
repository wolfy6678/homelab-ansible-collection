# homelab.core.grafana

Grafana with datasources, dashboards and alerting all file-provisioned, so it
works on first start with no clicking. Installed from the official apt
repository.

## What it provisions

- A **Prometheus** datasource, and a **Loki** datasource when
  `grafana_loki_url` is set.
- **Nine dashboards**: Homelab Overview, Host Detail (drill-down by instance),
  Proxmox, Service Uptime (Gatus SLOs and certificate expiry), Backups,
  OPNsense, Headscale VPN, and — only when Loki is configured — OPNsense
  Security and Homelab Logs.
- Optionally, **alert rules and a Discord contact point**.

## Required variables

`grafana_admin_password` fails with a hint if unset. It seeds the initial login
only; a password later changed in the UI lives in Grafana's own database and
need not be mirrored back.

## Alerting

Set `grafana_discord_webhook_url` to enable. These are the infrastructure
failures Gatus cannot see: host down, root filesystem over 85%, memory over 92%
for 30 minutes, a backup stale beyond 36 hours or exiting non-zero, a
certificate inside 14 days, a disk failing SMART. Thresholds are the
`grafana_alert_*` variables. Empty disables alerting and removes the
provisioning file.

Anyone holding the webhook URL can post to the channel, so vault-encrypt it.

## Serving behind a reverse proxy

Set `grafana_root_url` to the full public URL with a trailing slash — the role
turns on `serve_from_sub_path` to match. If Prometheus is also served under a
prefix, `grafana_prometheus_url` must include that prefix so the datasource hits
the right API.

## Example

```yaml
- hosts: monitoring
  roles:
    - homelab.core.grafana
```

## Notes

Dashboard files are installed without notifying a restart: the file provider
rescans every 30 seconds, so restarting would only drop live sessions and
interrupt alert evaluation for nothing.

An empty panel almost always means a missing scrape target rather than a broken
dashboard — check Prometheus's target list first. The OPNsense board in
particular is built against `os-telegraf`; see
[docs/opnsense.md](../../docs/opnsense.md).
