# homelab.core

[![CI](https://github.com/wolfy6678/homelab-ansible-collection/actions/workflows/ci.yml/badge.svg)](https://github.com/wolfy6678/homelab-ansible-collection/actions/workflows/ci.yml)

Ansible roles for building a self-hosted homelab on Proxmox LXC containers —
reverse proxy, a full metrics + logs stack, VPN, media, home automation,
backups and host hardening.

These roles are extracted from a running homelab. They are opinionated
(Debian/systemd, native installs over containers where practical) but carry no
site-specific defaults: every address, domain and credential is a variable you
supply from your own inventory.

**New here? Start with [docs/getting-started.md](docs/getting-started.md)** —
it walks from a bare Proxmox host to a running homelab, and
[`examples/`](examples/) is a complete consumer repository you can copy.

## Requirements

- `ansible-core` >= 2.15
- Terraform >= 1.3, if you use the `proxmox` role to provision containers
- Debian-family targets (developed against Debian 13 "trixie" LXCs)
- Collection dependencies are installed automatically: `community.general`,
  `community.proxmox`, `oxlorg.opnsense`

## Installation

```bash
ansible-galaxy collection install git+https://github.com/wolfy6678/homelab-ansible-collection.git,v1.0.0
```

Or pin it in a `requirements.yml`:

```yaml
collections:
  - name: https://github.com/wolfy6678/homelab-ansible-collection.git
    type: git
    version: v1.0.0
```

```bash
ansible-galaxy collection install -r requirements.yml
```

## Usage

Reference roles by their fully-qualified name:

```yaml
- name: Install the monitoring stack
  hosts: monitoring
  roles:
    - homelab.core.prometheus
    - homelab.core.loki
    - homelab.core.alloy
    - homelab.core.grafana
```

Each role has a `README.md` covering what it does, what it needs and how it
wires into the rest; `roles/<name>/defaults/main.yml` documents every tunable
and, more usefully, why it is what it is.

Required variables with no safe default use `undef(hint=...)`, and the handful
that must live in your inventory are asserted at the start of the run — so a
misconfiguration fails immediately with a message telling you what to set,
rather than half-configuring a host.

## Documentation

| | |
| --- | --- |
| [Getting started](docs/getting-started.md) | Bare Proxmox host to running homelab |
| [Inventory reference](docs/inventory.md) | The groups, host vars and variables the roles derive everything from |
| [Terraform](docs/terraform.md) | The root module you supply, and the contract it must meet |
| [The Proxmox host](docs/proxmox-node.md) | The manual seed, and what `proxmox_node` takes over |
| [OPNsense](docs/opnsense.md) | Firewall bootstrap, metrics plugins, IDS log visualisation |
| [`examples/`](examples/) | A complete consumer repository: inventory, group_vars, playbooks, Terraform |

## Roles

### Platform

| Role | Purpose |
| --- | --- |
| [`proxmox_node`](roles/proxmox_node) | Post-install config of a Proxmox VE host: no-subscription apt repos, LXC OS template download, SMART disk-health metrics; optional nag removal and a least-privilege Terraform API user |
| [`proxmox`](roles/proxmox) | Builds a Terraform `lxcs` map from the `lxc` inventory group, applies it, and starts the containers |
| [`unattended_upgrades`](roles/unattended_upgrades) | Automatic security patching on every host |
| [`opnsense`](roles/opnsense) | Reconciles OPNsense firewall resources over the API: Unbound DNS overrides, optional scrape rules |

### Networking and access

| Role | Purpose |
| --- | --- |
| [`caddy`](roles/caddy) | Caddy reverse proxy with HTTPS and clean hostnames; ACME DNS-01 or an internal CA |
| [`headscale`](roles/headscale) | Self-hosted Tailscale control server plus a co-located subnet router, with automatic Let's Encrypt TLS, a tailnet ACL and fail2ban |

### Observability

| Role | Purpose |
| --- | --- |
| [`node_exporter`](roles/node_exporter) | Prometheus node_exporter agent with the textfile collector enabled |
| [`prometheus`](roles/prometheus) | Prometheus server plus `prometheus-pve-exporter`, scrape config derived from inventory |
| [`loki`](roles/loki) | Grafana Loki log store |
| [`alloy`](roles/alloy) | Grafana Alloy log collector — journald everywhere, plus an OPNsense syslog/Suricata pipeline with GeoIP enrichment |
| [`grafana`](roles/grafana) | Grafana with provisioned datasources, nine starter dashboards and optional Discord alerting |
| [`gatus`](roles/gatus) | Gatus uptime monitoring, built from source, exporting Prometheus metrics |
| [`monitoring_trmnl`](roles/monitoring_trmnl) | Opt-in push of a compact infra-health summary to a TRMNL e-ink plugin webhook |

### Services

| Role | Purpose |
| --- | --- |
| [`homepage`](roles/homepage) | gethomepage.dev dashboard with service widgets |
| [`homeassistant`](roles/homeassistant) | Home Assistant Core in a venv, with optional FoxESS Modbus and Hildebrand Glow integrations and Energy dashboard wiring |
| [`mosquitto`](roles/mosquitto) | Mosquitto MQTT broker |
| [`jellyfin`](roles/jellyfin) | Jellyfin media server, including automated first-run wizard and library reconciliation |
| [`otterwiki`](roles/otterwiki) | OtterWiki, a git-backed markdown wiki, with optional push mirroring to GitHub |
| [`backup`](roles/backup) | restic file-level backups on a systemd timer, with Prometheus metrics |

## Terraform LXC module

The collection also ships a reusable Terraform module for a single Proxmox LXC
at `terraform/modules/lxc`, used by the `proxmox` role's workflow. Source it
straight from git:

```hcl
module "lxc" {
  source   = "git::https://github.com/wolfy6678/homelab-ansible-collection.git//terraform/modules/lxc?ref=v1.0.0"
  for_each = var.lxcs

  hostname        = each.key
  ip              = each.value.ip
  target_node     = each.value.target_node
  ostemplate      = each.value.ostemplate
  memory          = each.value.memory
  cores           = each.value.cores
  rootfs_size     = each.value.rootfs_size
  bridge          = each.value.bridge
  gateway         = each.value.gateway
  mountpoints     = each.value.mountpoints
  keyctl          = each.value.keyctl
  storage         = var.proxmox_lvm_storage
  password        = var.proxmox_lxc_password
  ssh_public_keys = var.proxmox_ssh_key
}
```

Deliberately **not** shipped here: the Terraform root module. Provider
credentials, your `lxcs` map and its defaults, and the state backend are
site-specific and belong in your own repository — see
[docs/terraform.md](docs/terraform.md) and
[`examples/terraform/`](examples/terraform/) for a complete working one.

## Design notes

- **Inventory is the source of truth.** Roles derive scrape targets, proxy
  upstreams, DNS overrides and health checks from inventory groups rather than
  duplicating host lists, so adding a host wires it into the rest of the stack.
  Every cross-group reference is guarded, so a partial inventory just produces a
  smaller config rather than an error.
- **Service lists are data, not templates.** Which services you run is yours to
  declare: `caddy_sites`, `gatus_endpoints`, `homepage_services` and
  `backup_default_paths` ship empty or derive from your inventory, and are
  passed through to the underlying tool's own schema — so a new service or
  widget never needs a change to a role.
- **Create-only where humans edit.** Admin users, backup jobs and first-run
  wizards are created if absent and never modified afterwards, so a password
  changed in a web UI doesn't need mirroring back into your vault.
- **Secrets stay yours.** No role embeds a credential; every one is a variable
  you supply, and vault-encrypting them is your inventory's job.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) — it covers the checks CI runs and the
rules that keep the collection site-agnostic.

## Licence

MIT — see [LICENSE](LICENSE).
