# homelab.core.caddy

Caddy reverse proxy: fronts the homelab's web services with HTTPS and clean
hostnames (`<name>.<your-domain>`). Installed from the official Cloudsmith apt
repository.

## TLS modes

**`internal`** (default) — Caddy's own local CA issues a certificate per site.
Nothing external is needed, but browsers won't trust it until you install the
root CA from
`/var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt` on each
device.

**`acme`** — real Let's Encrypt certificates via the DNS-01 challenge. Trusted
everywhere with nothing to install, and the services still stay LAN-only: your
resolver points the names at Caddy internally, and only transient
`_acme-challenge` TXT records ever appear in the public zone. Needs a domain you
own, `caddy_acme_email`, and a scoped DNS API token.

The role installs the matching `caddy-dns` plugin into the apt binary via
`caddy add-package` — the stock package ships none.

## Required variables

`caddy_sites` — **defined in your inventory, not here.** It is the single source
of the clean hostnames: the `gatus` role derives its certificate-expiry checks
from it and the `opnsense` role derives the LAN DNS overrides from it, both via
`hostvars`, where role defaults are invisible.

```yaml
# group_vars/caddy/main.yml
caddy_sites:
  - name: jellyfin
    upstream: "{{ hostvars[groups['jellyfin'][0]].ansible_host }}:8096"

  # One hostname, two apps, split by sub-path. Each app must be configured to
  # serve from its prefix (grafana_root_url, prometheus_external_url), because
  # the prefix is passed through un-stripped.
  - name: monitoring
    default_redirect: /grafana/
    paths:
      - path: /grafana*
        upstream: "{{ hostvars[groups['monitoring'][0]].ansible_host }}:3000"
      - path: /prometheus*
        upstream: "{{ hostvars[groups['monitoring'][0]].ansible_host }}:9090"
```

In `acme` mode, `caddy_dns_api_token` is required too — scoped to that zone
only, and vault-encrypted.

## Example

```yaml
- name: Install and start the Caddy reverse proxy
  hosts: caddy
  roles:
    - homelab.core.caddy
```

Run it **after** the services it proxies, so every upstream answers when the
first certificate is issued.

## Notes

Two DNS-01 defaults exist because of a real failure mode, and are worth
understanding before you change them. `caddy_dns_resolvers` points the
propagation check at public resolvers, because your LAN resolver is
split-horizon authoritative for the zone and cannot see the public TXT record
Caddy just wrote. And `caddy_dns_propagation_timeout: "-1"` disables Caddy's own
propagation self-check entirely: against public recursive resolvers it races
negative caching, and batches of sites get stuck timing out while the record is
live at the authoritative nameserver. Letting the ACME CA do the lookup — it
queries the authoritative NS directly — is reliable; the 30-second
`caddy_dns_propagation_delay` is the safety margin.

For the names to resolve on your LAN, either let the `opnsense` role manage the
Unbound overrides, or add them by hand.
