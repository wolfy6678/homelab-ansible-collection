# homelab.core.prometheus

Prometheus, plus `prometheus-pve-exporter` for Proxmox API metrics. Installed
from the pinned upstream release tarball.

**The scrape config is derived from your inventory.** There is no target list to
maintain: adding a host to the `lxc` group adds a scrape target, and each
service job appears only when its group exists.

## Jobs it builds

| Job | Source | Condition |
| --- | --- | --- |
| `prometheus` | itself | always |
| `node` | every host in `lxc`, plus the `proxmox` host | when either group exists |
| `gatus` | the `gatus` group | when the group exists |
| `headscale` | the `headscale` group | when the group exists |
| `fail2ban` | the headscale host's exporter | when both fail2ban flags are on |
| `pve` | the Proxmox API via pve-exporter | when enabled and a `proxmox` group exists |
| `opnsense` / `opnsense-telegraf` | the firewall's exporter plugins | when the targets are set |

Ports come from the owning service's inventory variables via `hostvars` — one
source, no hand-mirrored defaults to drift. Every group reference is guarded, so
a partial inventory renders a valid config.

## Required variables

`prometheus_pve_token_id` and `prometheus_pve_token_secret` when
`prometheus_pve_exporter_enabled` is on (it is by default) — both fail with a
hint if unset. The token needs the `PVEAuditor` role; the setup steps are in
`examples/group_vars/monitoring/main.yml`.

Set `prometheus_pve_exporter_enabled: false` to skip it. node_exporter on the
PVE host still gives you host metrics.

## Serving behind a reverse proxy

To serve Prometheus under a sub-path, set `prometheus_external_url` to the full
public URL with a trailing slash and `prometheus_route_prefix` to its path.
That moves **everything** under the prefix — UI, API, `/metrics` and
`/-/healthy` — so three other things must agree: the self-scrape `metrics_path`
(handled), Grafana's datasource URL (`grafana_prometheus_url`), and the Gatus
health check (which reads `prometheus_route_prefix` via `hostvars` itself).
Leave both empty to serve at the root.

## Example

```yaml
- name: Install and start the monitoring stack
  hosts: monitoring
  roles:
    - homelab.core.prometheus
    - homelab.core.loki
    - homelab.core.alloy
    - homelab.core.grafana
```

## Notes

`prometheus_proxmox_pin_ip` exists because pve-exporter re-resolves the PVE
hostname on every API request — about twenty per scrape, since pveproxy doesn't
keep connections alive. At a 15-second interval that is roughly a hundred DNS
queries a minute. Setting it to the PVE host's IP pins the name in
`/etc/hosts` here, while keeping the scrape target on the hostname so the
`instance` labels (and the dashboard queries built on them) are unchanged.

Retention is 90 days by default; the TSDB is the reason the monitoring container
wants a larger root filesystem.
