# Inventory reference

The roles in this collection are driven by your inventory. They derive scrape
targets, proxy upstreams, DNS overrides, health checks and dashboard tiles from
inventory groups rather than from hard-coded host lists, so adding a host to a
group wires it into the rest of the stack.

That makes the inventory a **contract**. This page documents it. A complete
working example lives in [`examples/`](../examples/).

---

## Groups

Every group is optional — a role only needs the groups it reads, and every
cross-group reference is guarded, so an inventory without a `headscale` group
simply produces a Prometheus config with no headscale job.

| Group | Contains | Read by |
| --- | --- | --- |
| `proxmox` | The Proxmox VE host itself (addressed by name, no `ansible_host`) | `proxmox_node`, `proxmox`, `prometheus` (node + PVE scrape targets) |
| `lxc` | Every container this collection creates. Usually a parent group whose children are the per-service groups | `proxmox` (builds the Terraform map), `prometheus` (node scrape targets) |
| `caddy` | The reverse-proxy host | `caddy`, plus `gatus`, `opnsense`, `homepage`, `headscale` — all derive hostnames or IPs from it |
| `monitoring` | Prometheus + Grafana + Loki + Alloy collector | `prometheus`, `grafana`, `loki`, `alloy`, `monitoring_trmnl`, `opnsense` |
| `gatus` | Uptime monitor (often co-located on another host) | `gatus`, `prometheus` |
| `headscale` | VPN control server + subnet router | `headscale`, `prometheus`, `gatus` |
| `homepage` | Dashboard | `homepage` |
| `homeassistant` | Home Assistant | `homeassistant` |
| `mosquitto` | MQTT broker (often co-located on the Home Assistant host) | `mosquitto` |
| `jellyfin` | Media server | `jellyfin` |
| `otterwiki` | Wiki | `otterwiki` |
| `opnsense` | The firewall. **Not** under `lxc` — it is an existing appliance, and the role talks to its API from localhost | `opnsense` |
| `backup` | Hosts whose application data restic backs up. Not a container of its own | `backup` |

A group may hold a host that another group also holds — co-location is normal
(`gatus` on the homepage host, `mosquitto` on the Home Assistant host). Only
groups under `lxc` cause a container to be created.

### Group naming is not free

Several roles look up `groups['<name>'][0]`, so the group names above are part
of the contract. Renaming `monitoring` to `metrics`, for example, breaks the
Alloy push URL and the Grafana/Prometheus tiles.

## Host variables

| Variable | Where | Meaning |
| --- | --- | --- |
| `ansible_host` | Every LXC | The container's static IP. Terraform assigns it, and every derived URL in the collection is built from it. |
| `lxc_overrides` | Optional, per LXC | A dict merged into that container's Terraform definition — `memory`, `cores`, `rootfs_size`, `mountpoints`, `keyctl`, ... See [docs/terraform.md](terraform.md). |
| `lxc_subnet_prefix` | Optional, per LXC | CIDR prefix length appended to `ansible_host` (default `24`). |
| `lxc_tun` | Optional, per LXC | `true` passes `/dev/net/tun` into the container. Required for the headscale subnet router. |

The container's hostname comes from `inventory_hostname_short`, which is also
the Terraform map key, the Prometheus `instance` label and the
`backup_default_paths` key — so `monitoring.example.lan` in the inventory
becomes the container `monitoring` everywhere else. Keep those names short and
stable.

---

## Variables you must declare in the inventory

Most tunables are role defaults you may override. These are different: they
have **no role default and must be set in your inventory**, because another
role reads them from this host via `hostvars`, and *role defaults are invisible
in `hostvars`*. Declaring them in `defaults/main.yml` would make the reading
role see nothing.

The roles assert these up front, so a missing one fails immediately with an
instruction rather than an undefined-variable error mid-run.

| Variable | Put it in | Example | Read by |
| --- | --- | --- | --- |
| `node_exporter_textfile_dir` | `group_vars/all` | `/var/lib/node_exporter/textfile` | `node_exporter`, `backup`, `proxmox_node` |
| `gatus_port` | `group_vars/gatus` | `8080` | `gatus`, `prometheus` |
| `caddy_sites` | `group_vars/caddy` | see below | `caddy`, `gatus`, `opnsense`, `homepage` |
| `headscale_metrics_listen_addr` | `group_vars/headscale` | `"0.0.0.0:9090"` | `headscale`, `prometheus` |
| `headscale_fail2ban_enabled` | `group_vars/headscale` | `true` | `headscale`, `prometheus` |
| `headscale_fail2ban_exporter_enabled` | `group_vars/headscale` | `true` | `headscale`, `prometheus` |
| `headscale_fail2ban_exporter_port` | `group_vars/headscale` | `9191` | `headscale`, `prometheus` |
| `terraform_proxmox_*` (7 variables) | `group_vars/proxmox` | see [docs/terraform.md](terraform.md) | `proxmox` |

`caddy_sites` is the single source of the clean hostnames. The `gatus` role
derives its certificate checks from it and the `opnsense` role derives the
Unbound DNS overrides from it, which is why it lives in your inventory:

```yaml
# group_vars/caddy/main.yml
caddy_sites:
  - name: homepage
    upstream: "{{ hostvars[groups['homepage'][0]].ansible_host }}:3000"
  - name: jellyfin
    upstream: "{{ hostvars[groups['jellyfin'][0]].ansible_host }}:8096"
  # One hostname serving two apps, split by sub-path
  - name: monitoring
    default_redirect: /grafana/
    paths:
      - path: /grafana*
        upstream: "{{ hostvars[groups['monitoring'][0]].ansible_host }}:3000"
      - path: /prometheus*
        upstream: "{{ hostvars[groups['monitoring'][0]].ansible_host }}:9090"
```

### Required, but with a built-in hint

A second class of variable has no safe default either, but nothing else reads
it via `hostvars`, so it is declared in the role as
`{{ undef(hint='...') }}`. Leaving one unset fails the run with a message
naming the variable and what to set it to — you do not need a checklist for
these, just run and read the error. They are the credentials and site
identifiers: `grafana_admin_password`, `caddy_dns_api_token`,
`headscale_server_url`, `backup_restic_repository`, `backup_restic_password`,
`jellyfin_admin_password`, `otterwiki_admin_password`, `otterwiki_secret_key`,
`mosquitto_password`, `opnsense_api_key`/`_secret`,
`prometheus_pve_token_id`/`_secret`, `proxmox_backup_storage`,
`monitoring_trmnl_webhook_uuid`, and the Home Assistant integration
credentials.

## Where to put what

Ansible resolves group_vars by group depth, so a variable set on both a parent
and a child group takes the child's value. Two consequences worth knowing:

- Variables shared by hosts in *different* groups belong in `group_vars/all` —
  `node_exporter_textfile_dir` and the MQTT account are there for exactly this
  reason.
- A host in two groups (Home Assistant is in both `homeassistant` and
  `mosquitto`) reads variables from both. Declare each switch in exactly one
  place, or the deeper group silently wins.

Vault-encrypt every credential. The collection never embeds one and never
writes one to a world-readable file, but what your inventory holds is yours to
protect:

```bash
ansible-vault encrypt_string --vault-id homelab@prompt '<secret>' \
  --name 'grafana_admin_password'
```
