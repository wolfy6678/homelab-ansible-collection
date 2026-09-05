# homelab.core.monitoring_trmnl

Opt-in: a systemd timer on the monitoring host that queries Prometheus for
per-host CPU, memory, root-disk and load, and POSTs a compact summary to a
private [TRMNL](https://usetrmnl.com) e-ink plugin webhook.

Outbound-only by design. TRMNL's official Grafana plugin would need Grafana
publicly reachable; this keeps Prometheus and Grafana LAN-only.

## Setup

1. In the TRMNL dashboard, create a Private Plugin with strategy **Webhook**.
2. Copy the id at the end of its webhook URL (after `/custom_plugins/`).
3. Set it here and enable:

```yaml
monitoring_trmnl_enabled: true
monitoring_trmnl_webhook_uuid: !vault |
  ...
```

4. Paste your Liquid markup into the plugin's editor to render the payload.

The role is a no-op until both are set; the UUID is the only credential.

## Example

Runs on the monitoring host, alongside the Prometheus it queries:

```yaml
- name: Push infra health to TRMNL
  hosts: monitoring
  roles:
    - homelab.core.monitoring_trmnl
```

## Variables

| Variable | Default | |
| --- | --- | --- |
| `monitoring_trmnl_schedule` | `"*:0/10"` | systemd `OnCalendar`. TRMNL's free tier allows 12 requests/hour, so 5 minutes is the floor and 10 leaves headroom. TRMNL+ allows 30/hour. |
| `monitoring_trmnl_randomized_delay_sec` | `15` | Jitter, so it never fires exactly on the minute. |
| `monitoring_trmnl_base_url` | `https://trmnl.com` | Override for a self-hosted / BYOS server. |
| `monitoring_trmnl_node_job` | `node` | The Prometheus job whose per-instance metrics are summarised. |
