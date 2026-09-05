# homelab.core.opnsense

Reconciles the OPNsense firewall resources the homelab services depend on, over
the OPNsense API. A deliberately thin, declarative slice: Unbound DNS host
overrides for the reverse proxy, plus an optional monitoring scrape rule.

Interface assignment, NAT port-forwards, system tunables and certificates are
**not** managed here — they belong in your `config.xml` backup. See
[docs/opnsense.md](../../docs/opnsense.md) for the full division of
responsibility and the bootstrap runbook.

## Enabling

A no-op until `opnsense_manage_enabled: true`, so a full site run never requires
firewall API access. While disabled the modules never run, so the
`undef()` API credentials are never evaluated.

Create the key/secret under System > Access > Users > API keys.

## The playbook

The API connection is supplied through `module_defaults`, not through role
variables, and the play runs from localhost — it never SSHes into the firewall:

```yaml
- name: Reconcile OPNsense firewall resources
  hosts: opnsense
  connection: local
  gather_facts: false
  module_defaults:
    group/oxlorg.opnsense.all:
      firewall: "{{ ansible_host }}"
      api_key: "{{ opnsense_api_key }}"
      api_secret: "{{ opnsense_api_secret }}"
      ssl_verify: "{{ opnsense_ssl_verify }}"
  roles:
    - homelab.core.opnsense
```

## DNS overrides

`opnsense_unbound_domain` must match `caddy_base_domain`.

`opnsense_unbound_wildcard: true` creates a single `*.<domain>` record — least
upkeep, tracks new Caddy sites automatically, and safe **only** when the reverse
proxy owns the whole zone.

Otherwise the explicit per-name list is derived from `caddy_sites` via
`hostvars`, so each Caddy site gets a record and nothing else does. That
matters when a name in the same zone must resolve elsewhere internally —
headscale's public hostname is the usual case, and a wildcard would hijack it
and break the VPN for LAN devices.

Records use `match_fields` excluding `value`, so changing the Caddy IP updates
the record in place rather than creating a duplicate.

## Monitoring rule

`opnsense_monitoring_rule_enabled` (off) creates one pass rule per port in
`opnsense_monitoring_ports`, letting the monitoring host scrape the firewall's
exporters. Usually unnecessary — the stock "LAN to This Firewall" allow already
covers it. Enable it if you have locked that down.

## Requirements

The `oxlorg.opnsense` collection, installed with `homelab.core`. Its version
schema tracks OPNsense releases, so pin the line matching your firewall
(`25.7.x` = OPNsense 25.7).
