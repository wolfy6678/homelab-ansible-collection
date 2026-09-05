# homelab.core.alloy

Grafana Alloy — the log collector that feeds Loki. One role, two deployment
shapes:

**On the monitoring host** (all defaults on): receives remote syslog from
OPNsense, parses Suricata alerts and firewall blocks, GeoIP-enriches the source
IP, *and* collects the local journal.

**On every other host** (`alloy_syslog_enabled: false`,
`alloy_geoip_enabled: false`): a journal-only agent shipping journald to Loki —
this is what fills the "Homelab Logs" dashboard.

```yaml
- name: Install Alloy log agents
  hosts: lxc:proxmox:!monitoring
  roles:
    - role: homelab.core.alloy
      alloy_syslog_enabled: false
      alloy_geoip_enabled: false
```

Run the agents **after** the monitoring host, so Loki exists before they push.
They retry, so a first-deploy gap only delays log flow — the ordering just
avoids the error noise.

## Requirements

A `monitoring` group: the Loki push URL is derived from it, so the same default
works for the co-located collector and every remote agent. To push to a Loki
that isn't in the inventory, set `alloy_loki_push_url` instead. The role
asserts one of the two before it installs anything.

## Labels

The journal pipeline labels logs with `host` (the inventory short name, matching
the Prometheus `instance` label so you can pivot between metrics and logs),
`unit`, and `priority`. The syslog pipeline adds `logtype` — the OPNsense
sub-system, taken from the syslog app-name, which is why the firewall must ship
**RFC5424**.

## GeoIP

Defaults to the DB-IP City Lite database: free, CC-BY, and no signup or API key,
unlike MaxMind GeoLite2. The URL carries the current year-month, with a
previous-month fallback covering the first days of a month before that file
publishes. Point `alloy_geoip_db_url` at MaxMind's URL to use that instead; it
lands at the same path either way.

Refresh by deleting the `.mmdb` and re-running.

Country code is indexed as a Loki label — bounded at around 250 values — while
city, latitude and longitude ride along as structured metadata, so the label
index stays small.

## Notes

Unmatched lines are stored raw rather than dropped, so you can inspect the real
format in Grafana Explore (`{job="opnsense"}`) and refine the parsing against
live data.

`alloy_syslog_max_message_length` is 32 KiB because Suricata `eve.json` alert
records carry full alert metadata and overflow the 8 KiB syslog default.

The firewall-side setup — the syslog target, and the syslog-ng snippet that
ships real IDS alerts — is in [docs/opnsense.md](../../docs/opnsense.md).
