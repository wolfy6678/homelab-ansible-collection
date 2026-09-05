# homelab.core.gatus

[Gatus](https://github.com/TwiN/gatus) endpoint monitoring, exporting its
results as Prometheus metrics. Built from the tagged source tarball with a
pinned Go toolchain, because upstream ships Docker images only.

Often co-located on the homepage host rather than given a container of its own.

## Required variables

`gatus_port` must be set in `group_vars/gatus` — the `prometheus` role reads it
via `hostvars` to build the scrape target, and role defaults are invisible
there. The role asserts it.

`gatus_endpoints` ships **empty**: which services exist depends entirely on your
inventory. Derive URLs from the inventory rather than hard-coding IPs:

```yaml
gatus_endpoints:
  - name: jellyfin
    url: "http://{{ hostvars[groups['jellyfin'][0]].ansible_host }}:8096/health"
  - name: otterwiki
    url: "http://{{ hostvars[groups['otterwiki'][0]].ansible_host }}/-/healthz"
  - name: grafana
    url: "http://{{ hostvars[groups['monitoring'][0]].ansible_host }}:3000/api/health"
  - name: prometheus
    url: >-
      http://{{ hostvars[groups['monitoring'][0]].ansible_host }}:9090{{
      hostvars[groups['monitoring'][0]].prometheus_route_prefix | default('') }}/-/healthy
  - name: home-assistant
    url: "http://{{ hostvars[groups['homeassistant'][0]].ansible_host }}:8123"
  - name: homepage
    url: "http://{{ hostvars[groups['homepage'][0]].ansible_host }}:3000"
  # headscale over its real public hostname: validates the full chain and
  # tracks expiry. Without headscale_server_url, fall back to a TCP connect:
  #   url: "tcp://{{ hostvars[groups['headscale'][0]].ansible_host }}:443"
  #   conditions: ["[CONNECTED] == true"]
  - name: headscale
    url: "{{ gatus_headscale_server_url }}/health"
    conditions:
      - "[STATUS] == 200"
      - "[CERTIFICATE_EXPIRATION] > {{ gatus_certificate_min_validity }}"
```

Each entry takes `name` and `url`, plus optional `group`, `interval` and
`conditions` (default `["[STATUS] == 200"]`).

## Certificate monitoring — automatic

A `certificates` group is appended to whatever you configure, derived from
`caddy_sites` via `hostvars`: one HTTPS check per clean hostname, validating the
served chain end-to-end and exporting
`gatus_results_certificate_expiration_seconds`. That metric drives the
Certificate Expiry panel and the Grafana cert alert. Add or rename a Caddy site
and it is monitored automatically; the whole group is skipped when there is no
`caddy` group.

Checks fail below `gatus_certificate_min_validity` (240h). Caddy renews about 30
days out, so ten days left means renewal is broken.

## Discord alerting

Set `gatus_discord_webhook_url` (vault-encrypted — anyone with it can post to
the channel) to alert on every endpoint after
`gatus_alert_failure_threshold` consecutive failures, with a recovery
notification after `gatus_alert_success_threshold` successes.

## Example

```yaml
- name: Install Gatus
  hosts: gatus
  roles:
    - homelab.core.gatus
```

`gatus_port` and `gatus_endpoints` belong in `group_vars/gatus/main.yml` — the
first because `prometheus` reads it via `hostvars`, the second because it is
site-specific. See [`examples/group_vars/gatus/`](../../examples/group_vars/gatus/).

## Notes

The role adds an `/etc/hosts` entry pinning the headscale public hostname to its
LAN IP, because that name is split-horizon with no LAN record and hairpin NAT is
typically not configured. The public certificate still validates — SNI carries
the hostname.

Prometheus scrapes `/metrics` on the same `gatus_port`, which is what fills the
Service Health panels on the Homelab Overview dashboard.
