# homelab.core.headscale

Self-hosted [headscale](https://headscale.net) — a Tailscale control server —
with a Tailscale subnet router co-installed on the same host, so one node
exposes the whole homelab LAN to your remote devices. Plus automatic Let's
Encrypt TLS, a tailnet ACL, and fail2ban on the public endpoint.

This is typically the **only** internet-facing service in the homelab.

## Before the first run

Both of these must be in place, or the play times out waiting for headscale to
serve:

1. A **public DNS record** for `headscale_server_url`'s hostname, pointing at
   your home's public IP (a DDNS hostname is fine).
2. A **port-forward of TCP 443** to this container.

headscale then obtains its certificate on first start via TLS-ALPN-01, which is
why only port 443 needs forwarding.

The container also needs `/dev/net/tun` for subnet routing — set `lxc_tun: true`
on the host in your inventory and the `proxmox` role handles the passthrough.
Because that reboots the container, this role waits for the connection and
gathers facts itself, so its playbook sets `gather_facts: false`.

## Required variables

`headscale_server_url` fails with a hint if unset. Four more must be declared in
`group_vars/headscale` because the `prometheus` role reads them via `hostvars`,
where role defaults are invisible — the role asserts all four:

```yaml
headscale_metrics_listen_addr: "0.0.0.0:9090"
headscale_fail2ban_enabled: true
headscale_fail2ban_exporter_enabled: true
headscale_fail2ban_exporter_port: 9191
```

Set the site topology too — the collection ships these generic so it encodes
nobody's LAN: `headscale_advertise_routes`, `headscale_dns_split` and
`headscale_acl_dns_server`.

## The ACL

`headscale_acl_enabled` is on by default and replaces headscale's allow-all
policy: enrolled devices may reach only your LAN resolver and the Caddy reverse
proxy. The clean hostnames keep working from your phone, but SSH, the hypervisor
and firewall admin UIs, and direct service ports are not reachable from a
device that might be lost or stolen. Add `"<your-lan>/24:*"` to
`headscale_acl_dsts` to restore full access, or set `headscale_acl_enabled:
false`.

The rules apply to `"*"` rather than the tailnet user deliberately: headscale
loads the policy at startup, but on a fresh deploy the user only exists after
the server is up, so a user reference would be a chicken-and-egg. With a
single-user tailnet the two are equivalent.

## fail2ban

The public endpoint sees constant scanner noise, so fail2ban bans sources that
spray junk TLS handshakes or 4xx path probes — six hits in ten minutes earns a
one-hour ban, doubling for repeat offenders. It reads the journal directly and
bans via nftables, and an exporter ships ban counts to Prometheus.

`headscale_fail2ban_ignoreip` includes your LAN prefix, and that entry is
essential rather than cosmetic: the Gatus health check TCP-probes port 443 every
minute, and each probe logs exactly the handshake-error line the filter matches.
Without the exemption, the Gatus host is banned within minutes.

Banned yourself anyway? SSH in from the LAN:

```bash
fail2ban-client set headscale unbanip <ip>
```

Disabling fail2ban later stops the role managing it but does not uninstall it.

## Enrolling devices

After deploy, register a device against the control server and approve it:

```bash
headscale nodes list
headscale nodes register --user homelab --key <nodekey>
```

The subnet router is registered and its routes approved automatically.

## Example

```yaml
- name: Install and start Headscale
  hosts: headscale
  gather_facts: false   # the role waits for the connection, then gathers
  roles:
    - homelab.core.headscale
```

## Notes

`headscale_base_domain` (MagicDNS) must **not** be a suffix of the
`headscale_server_url` hostname.

Debugging the certificate path? Point `headscale_acme_url` at Let's Encrypt
staging to avoid burning the failed-validation limit — but staging issues an
untrusted certificate, so the readiness gate won't pass; watch
`journalctl -u headscale` instead. autocert caches per hostname regardless of
directory, so delete `/var/lib/headscale/cache` before switching back.
