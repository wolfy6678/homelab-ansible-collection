# OPNsense: firewall, metrics and log visualisation

The `opnsense` role manages a deliberately thin slice of the firewall — the
handful of resources the homelab services depend on. Everything else about the
firewall stays where it belongs: in the firewall, captured by a config backup.

This page covers that split, the API setup the role needs, and the two
monitoring integrations that live half on the firewall and half in this
collection.

The role is a complete no-op until `opnsense_manage_enabled: true`, so you can
run everything else in the collection without ever giving Ansible firewall
access.

---

## Division of responsibility

| Layer | Owns | Mechanism |
| --- | --- | --- |
| Your `config.xml` backup | Everything: interface assignment, NAT and port-forwards, system tunables, certificates, the long tail | The whole file, restored wholesale |
| The `opnsense` role | Unbound DNS host overrides pointing the Caddy hostnames at the reverse proxy; optionally a monitoring scrape rule | Declarative, per-resource, over the API |

Rule of thumb: the role owns its handful of resources, the config backup owns
everything else. Don't hand-edit a role-owned resource in the GUI and expect the
backup to win — on a restore-then-reconcile, the role re-asserts its slice.

`config.xml` is all-or-nothing (you cannot merge one section) and full of
secrets — hashed credentials, private keys, the very API secret the role uses.
It is a disaster-recovery snapshot, not a per-resource config tool. Keep the
repository holding it **private**, and never manage the same resource through
both mechanisms.

## Bootstrap order

The firewall is the gateway and the DNS resolver, so it exists before anything
else in the homelab, and part of it can only be done by hand.

### 1. The manual seed

Install OPNsense, and at the console assign the interfaces and set the LAN IP.
That is the one step both the config backup and the API depend on — you need a
reachable management address before either works. Then reach the web UI and
finish the wizard enough to log in.

### 2. Restore or configure the firewall

On a rebuild: System > Configuration > Backups > Restore, upload your latest
`config.xml`, and let it reboot fully configured. Consider enabling the built-in
Git backup (System > Configuration > Backups > Git) pointed at a **private**
repository, kept separate from your Ansible repo so machine-authored commits and
secrets stay out of that history.

On a fresh install with no backup, do the firewall configuration once in the
GUI; the first git-backup push then seeds the repository.

### 3. Enable the API

System > Access > Users — pick or add a user, then API keys > `+`. OPNsense
issues a key and secret pair. An admin-group user is simplest; to
least-privilege it, grant the "Services: Unbound (MVC)" and "Firewall: Rules"
effective privileges.

Then in `group_vars/opnsense/main.yml`:

```yaml
opnsense_manage_enabled: true
opnsense_api_key: "<api key>"
opnsense_api_secret: !vault |
  ...
```

The credentials are supplied to every module at once through the playbook's
`module_defaults` — see `examples/playbooks/opnsense.yml`.

### 4. Reconcile

```bash
ansible-playbook playbooks/opnsense.yml
```

This creates the Unbound host overrides so every Caddy-fronted hostname resolves
on the LAN, and, if enabled, the monitoring scrape rule. It is idempotent and
runs first in `site.yml`.

### Wildcard or explicit records?

`opnsense_unbound_wildcard: true` creates a single `*.<domain>` A record — least
upkeep, and it tracks new Caddy sites automatically. It is only safe when the
reverse proxy owns the entire zone.

If any name in that zone must resolve elsewhere internally, use explicit
records instead (`opnsense_unbound_wildcard: false`). The list is derived from
`caddy_sites` automatically, so each Caddy site gets a record and nothing else
does. The usual case is headscale: it serves its own public TLS and must keep
resolving to your public IP, so it is deliberately not a Caddy site — a
wildcard would hijack it internally and break the VPN for devices on the LAN.

## What the role does not manage

These have no clean API module, or depend on facts outside the inventory:

- **Port-forwards**, including the TCP 443 forward headscale needs. There is no
  destination-NAT module; do it in the GUI.
- **Interface assignment, VLANs and system tunables** — part of the manual seed
  and the config restore.
- **The monitoring plugins below** — installed and enabled in the GUI. The
  collection only points Prometheus and Alloy at them.

---

## Metrics

OPNsense is FreeBSD-based, so the Linux `node_exporter` role does not run on it.
Instead it ships exporter plugins that Prometheus scrapes directly.

Install both — they are complementary:

1. **`os-node_exporter`** (System > Firmware > Plugins). Enable it under
   Services > Node Exporter; it listens on `:9100`.
2. **`os-telegraf`**. Enable it under Services > Telegraf > General, then under
   *Input* enable the inputs the dashboard uses: `system` (CPU, memory, load,
   uptime, processes), `net` (per-interface traffic), `disk`/`diskio`, and `pf`
   (state table). Under *Output*, enable the **Prometheus** output and note its
   port (default `9273`).

Then point Prometheus at them in `group_vars/monitoring/main.yml`:

```yaml
prometheus_opnsense_target: "192.168.50.1:9100"
prometheus_opnsense_telegraf_target: "192.168.50.1:9273"
```

> The provisioned **OPNsense** Grafana dashboard is built against os-telegraf.
> On its own, `os-node_exporter` emits an almost-empty metric set on OPNsense —
> netisr, netstat, uname, boottime, but no CPU, memory or per-interface network
> — so the board stays blank without Telegraf.

A firewall rule is usually unnecessary: the stock "LAN to This Firewall" allow
already covers the scrape. If you have locked that down, set
`opnsense_monitoring_rule_enabled: true` and the role creates one pass rule per
port.

---

## Log visualisation and the IDS map

This is a **logs** pipeline — Loki and Alloy — separate from the metrics
pipeline above:

```
OPNsense (Suricata IDS + filterlog)
   │  remote syslog, RFC5424, TCP :1514
   ▼
Alloy ── parse ── GeoIP-enrich source IP ──► Loki
   │                                          │
   └────────────── Grafana "OPNsense Security" ┘
```

A map of where connections originate needs per-source-IP data — very high
cardinality, and an anti-pattern for a metrics store. These are geolocated log
events, so they belong in a log store.

### 1. Enable Suricata

Suricata is in the OPNsense base system; there is no plugin to install.

Under Services > Intrusion Detection > Administration, tick **Enabled** and
**Promiscuous mode**, and select the **WAN** interface (add LAN later for
east-west visibility). Leave **IPS mode off** to start with: pure IDS detects
and alerts, whereas IPS drops traffic and a bad rule can break your network.

On the **Download** tab, enable at least the free **ET open/emerging-\***
ruleset, click *Enable selected*, then *Download & Update Rules*, and set a
daily schedule under Administration > Schedule.

A WAN-facing box is scanned constantly, so alerts appear quickly.

### 2. Ship the logs

System > Settings > Logging / Targets > `+`:

| Field | Value |
| --- | --- |
| Transport | **TCP** |
| Applications | **filter** and **suricata** (or empty for all) |
| Hostname | your monitoring container's IP |
| Port | `1514` |
| Protocol (RFC) | **RFC 5424** |

RFC5424 is not optional. Alloy routes logs by the syslog app-name
(`suricata`, `filterlog`), and RFC3164 does not carry it cleanly — without it
the `logtype` label, and all the per-type parsing, stay empty.

No firewall rule is needed: the traffic originates from the firewall itself.

### 3. Deploy the collection side

Already wired — `playbooks/monitoring.yml` installs Loki and Alloy and
provisions the Loki datasource and the **OPNsense Security** dashboard. The
GeoIP database defaults to DB-IP City Lite (free, CC-BY, no signup or key) and
is fetched once to `/var/lib/alloy/geoip/geoip-city.mmdb`. Delete it and re-run
to refresh; DB-IP publishes monthly. Set `alloy_geoip_db_url` to use MaxMind
GeoLite2 instead, or `grafana_loki_url: ""` to disable the whole logs stack.

### 4. Verify

```bash
curl -s http://<monitoring-ip>:3100/ready     # Loki: "ready"
curl -s http://127.0.0.1:12345/-/ready        # Alloy, on the monitoring host

curl -sG http://<monitoring-ip>:3100/loki/api/v1/query_range \
  --data-urlencode 'query={job="opnsense"}' --data-urlencode 'limit=5' \
  | jq '.data.result | length'
```

Then open Dashboards > OPNsense Security in Grafana.

Nothing is ever dropped: every syslog line is stored raw even when no parsing
regex matches it, so you can inspect the real format in Grafana's Explore
(`{job="opnsense"}`) and refine from there.

### 5. Ship real IDS alerts (eve.json)

OPNsense's remote syslog forwards Suricata's *service* log — daemon messages
like "Engine started" — but **not** its `eve.json` alert records. So out of the
box, the alerts you see in the OPNsense UI are not in Loki.

The fix is a small syslog-ng snippet on the firewall. syslog-ng is OPNsense's
syslog daemon, and `/usr/local/etc/syslog-ng.conf.d/` is its documented
extension point: files there survive reboots and firmware updates.

Create `/usr/local/etc/syslog-ng.conf.d/suricata-eve.conf` over SSH as root:

```
# Ship Suricata eve.json alert records to Alloy :1514.
# app-name "suricata-eve" is what Alloy routes and parses on — don't change it.
source s_suricata_eve {
  file("/var/log/suricata/eve.json" flags(no-parse) program-override("suricata-eve"));
};
filter f_suricata_eve_alert {
  message("\"event_type\":\\s*\"alert\"" type(pcre));
};
destination d_monitoring_eve {
  syslog("<monitoring-ip>" transport("tcp") port(1514));
};
log {
  source(s_suricata_eve);
  filter(f_suricata_eve_alert);
  destination(d_monitoring_eve);
};
```

Then `service syslog-ng restart`. Verify with `{logtype="suricata-eve"}` in
Grafana Explore; the IDS Alerts panels fill from the same stream, parsed for
signature, severity, category and source, and GeoIP-enriched like the firewall
blocks.

Notes:

- The filter means only *alert* records leave the firewall. `eve.json` also
  carries flow, DNS and TLS events, which would be pure noise and volume here.
- Alloy accepts messages up to 32 KiB (`alloy_syslog_max_message_length`)
  because alert records with packet metadata overflow the 8 KiB syslog default.
  If you see truncated JSON in Loki, raise it, and set syslog-ng's
  `log_msg_size()` on the firewall side too.

### What this is not

It does not replace the OPNsense UI. Suricata's own Alerts view is the source of
truth; this is long-term retention, visualisation and the map. The geomap plots
**blocked-connection** origins from filterlog — every hostile source the
firewall dropped, geolocated — while IDS alerts get their own panels fed by the
eve.json stream.

Country code is indexed as a Loki label (bounded, around 250 values); city,
latitude and longitude ride along as structured metadata so the label index
stays small. That is why the geomap reads `geoip_location_latitude` and
`geoip_location_longitude` as fields rather than labels.
