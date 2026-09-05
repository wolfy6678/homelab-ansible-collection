# Getting started

This walks from a bare Proxmox host to a running homelab: a reverse proxy with
real HTTPS, a metrics and logs stack, a VPN, media, home automation, and
backups.

It assumes you can already SSH to a Proxmox VE host as root, and that you have
somewhere to run `ansible-playbook` from (your laptop is fine).

Budget an evening. Nothing here is irreversible — the containers are declared in
Terraform and can be destroyed and rebuilt.

---

## 1. What you need first

- **A Proxmox VE host**, installed and on the network, reachable by name from
  your LAN. See [docs/proxmox-node.md](proxmox-node.md) for the bare-metal seed
  this collection deliberately does not automate.
- **`ansible-core` >= 2.15** and **Terraform >= 1.3** on the machine you deploy
  from.
- **An SSH keypair** whose public half gets injected into every container. This
  is how Ansible reaches them after provisioning.
- **A LAN with static addressing available** for the containers. They get static
  IPs from Terraform, not DHCP.
- Optional but recommended: **a domain you own**, for browser-trusted
  certificates on the internal hostnames. Without one you can still use Caddy's
  internal CA — you'll just install its root certificate on your devices.

## 2. Set up the consuming repository

The collection ships roles. Your inventory, your secrets and your Terraform root
module are yours, in your own git repository. Start from the skeleton:

```bash
git init homelab && cd homelab
# copy the examples/ directory out of the collection, or from the repo:
curl -sL https://github.com/wolfy6678/homelab-ansible-collection/archive/refs/tags/v1.0.0.tar.gz \
  | tar xz --strip-components=2 '*/examples'
```

You should now have `ansible.cfg`, `inventory/`, `group_vars/`, `playbooks/`,
`site.yml`, `terraform/` and `requirements.yml`.

Install the collection and its dependencies:

```bash
ansible-galaxy collection install -r requirements.yml
```

## 3. Describe your fleet

Edit `inventory/hosts.yml`. This is the one file everything else derives from —
scrape targets, proxy upstreams, DNS records, dashboard tiles and health checks
all come from these groups. [docs/inventory.md](inventory.md) is the full
reference; the short version:

- Put your Proxmox host in the `proxmox` group, addressed by **name**, with no
  `ansible_host`.
- Put each service in its own group under `lxc`, with an `ansible_host` (its
  static IP) and optional `lxc_overrides` for sizing.
- Delete the services you don't want. Nothing is mandatory, and every
  cross-reference between roles is guarded.

The short hostname becomes the container name, the Prometheus `instance` label
and the Terraform map key, so keep it short.

## 4. Fill in the settings

Work through `group_vars/`. Each file is commented with what it needs and why.
The ones you cannot skip:

| File | What it needs |
| --- | --- |
| `group_vars/all/main.yml` | `node_exporter_textfile_dir` |
| `group_vars/proxmox/terraform.yml` | Proxmox API URL, credentials, storage ID, SSH public key |
| `group_vars/caddy/main.yml` | your base domain and `caddy_sites` |
| `group_vars/gatus/main.yml` | `gatus_port` |
| `group_vars/monitoring/main.yml` | `grafana_admin_password` |
| `group_vars/headscale/main.yml` | the public URL and the four monitoring variables — only if you deploy headscale |

Vault-encrypt every secret as you go:

```bash
ansible-vault encrypt_string --vault-id homelab@prompt '<secret>' \
  --name 'grafana_admin_password'
```

Paste the output into the relevant `group_vars` file. `ansible.cfg` already
prompts for the vault password once per run.

You do not need an exhaustive checklist here. Anything required and missing
fails the run immediately with a message naming the variable and what to set it
to — that is what the `undef(hint=...)` defaults and the roles' preflight
assertions are for.

## 5. Point Terraform at your Proxmox host

Edit `terraform/variables.tf` — specifically the `optional()` defaults on the
`lxcs` variable. Those are your fleet-wide container defaults: the PVE node
name, the OS template, the bridge, the gateway, and the baseline memory/cores/
disk. Per-container exceptions go in `lxc_overrides` in the inventory, not here.

See [docs/terraform.md](terraform.md) for the full contract between the role and
the root module.

## 6. Deploy

```bash
ansible-playbook site.yml
```

That runs everything in dependency order: firewall DNS, then the PVE host, then
the containers, then hardening, then metrics agents, then each service, then the
reverse proxy, then the monitoring stack, then backups. The
[`examples/site.yml`](../examples/site.yml) comments explain each ordering
constraint.

Expect the first run to take a while: several services are built from source or
downloaded as release tarballs.

To iterate on one service, run just its playbook — they are all standalone and
idempotent:

```bash
ansible-playbook playbooks/monitoring.yml
```

## 7. Finish the manual steps

Some things genuinely cannot be automated from here, and the roles are built so
that they don't block the rest of the deploy:

- **Certificates.** In `internal` TLS mode, install Caddy's root CA on your
  devices from
  `/var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt`. In `acme`
  mode there is nothing to install, but your LAN resolver must point the clean
  hostnames at the Caddy container — the `opnsense` role does this for you, or
  add the overrides by hand.
- **Headscale.** Create the public DNS record and forward TCP 443 to the
  container *before* the first run, or the play times out waiting for a
  certificate. Then enrol devices with `headscale nodes register`.
- **Home Assistant.** Onboarding happens in the browser at `:8123`.
- **API keys for widgets.** The Home Assistant and Jellyfin Homepage widgets
  need tokens that can only be created after those services are set up. Add
  them to `homepage_services` and re-run on a later pass.
- **OPNsense metrics and IDS logs.** Plugin installs and a syslog target — see
  [docs/opnsense.md](opnsense.md).

## 8. Check it worked

- Homepage at `https://homepage.<your-domain>` — every tile should be green.
- Grafana at `https://monitoring.<your-domain>/grafana/`, with nine dashboards
  already provisioned. "Homelab Overview" is the one to look at first.
- Prometheus targets at `/prometheus/targets` — everything `UP`.
- Gatus at `https://gatus.<your-domain>` for per-endpoint uptime and certificate
  expiry.

If a Grafana panel is empty, the usual cause is a missing scrape target rather
than a broken dashboard: check Prometheus's target list first.

## Where to go next

- [docs/inventory.md](inventory.md) — the full inventory contract
- [docs/terraform.md](terraform.md) — provisioning
- [docs/proxmox-node.md](proxmox-node.md) — the PVE host seed
- [docs/opnsense.md](opnsense.md) — firewall, metrics and IDS log visualisation
- `roles/<name>/README.md` — per-role documentation
- `roles/<name>/defaults/main.yml` — every tunable, with the reasoning
