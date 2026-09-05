# The Proxmox VE host

The `proxmox_node` role configures a Proxmox host *after* it is installed. The
bare-metal install and the network setup are the manual seed — they need
physical access and site-specific decisions, so they stay out of the collection.

This page covers both halves: what you do by hand, and what the role then takes
over.

---

## The manual seed

1. **Install Proxmox VE** from the ISO onto the machine. Give it a static IP on
   your LAN and a hostname that resolves — the collection addresses the host by
   name from several places (`terraform_proxmox_api_url`, the Prometheus scrape
   target, the pve-exporter target), so an entry in your LAN DNS is worth
   creating now.

2. **Check the bridge.** The installer creates `vmbr0` bridged onto the physical
   NIC. That is what the containers attach to, and it is the default in the
   example Terraform root module. If yours differs, set `bridge` in the root
   module's `lxcs` defaults.

3. **Add your SSH key** for root:

   ```bash
   ssh-copy-id root@pve.example.lan
   ```

   Ansible connects as root over SSH — no `become`, because you are already
   root.

4. **Decide on storage.** The example uses `local-lvm` for container root
   filesystems (`terraform_proxmox_lvm_storage`). If you want scheduled
   container backups, add a backup-capable storage now: Datacenter > Storage >
   Add, an NFS/CIFS share or a Proxmox Backup Server, with content type
   "VZDump backup file".

That is the whole seed. Everything below is automated.

## What the role does

Run it with `playbooks/proxmox-node.yml`, before provisioning containers.

### apt repositories (on by default)

A fresh install points at the subscription-only enterprise repository, so `apt`
fails without a subscription. The role replaces it with `pve-no-subscription`
using the canonical PVE 9 layout — a deb822 `.sources` file whose suite is the
Debian codename — and disables `pve-enterprise.sources` and `ceph.sources` if
present. Idempotent: a host already switched over reports no change.

Set `proxmox_node_manage_repos: false` to leave apt alone.

### The container OS template (on by default)

Runs `pveam update`, then downloads the templates in
`proxmox_node_templates` — by default the Debian 13 standard image the example
Terraform module clones. Skipped when the file is already in the cache.

If you change the template here, change `ostemplate` in the Terraform root
module's `lxcs` defaults to match.

### SMART disk metrics (on by default)

Installs `smartmontools` and a systemd timer that writes `smartmon_*` gauges
into node_exporter's textfile directory every 15 minutes: overall health,
temperature, reallocated sectors, NVMe wear and media errors. These feed the
Proxmox dashboard and the "disk failing" Grafana alert — early warning for a
dying disk. Read-only against the disks, which is why it is on by default.

This is also why `node_exporter_textfile_dir` must be set in `group_vars/all`,
and why the node_exporter playbook targets `lxc:proxmox` rather than just `lxc`.

### The subscription nag (opt-in)

`proxmox_node_remove_subscription_nag: true` patches the widget toolkit
JavaScript to suppress the "No valid subscription" login dialog. Purely
cosmetic, guarded so it patches only once, and reverted whenever
`proxmox-widget-toolkit` updates.

### A dedicated Terraform user (opt-in)

By default Terraform authenticates as `root@pam`. To use a least-privilege
identity instead, set:

```yaml
proxmox_node_terraform_user_enabled: true
```

The role then creates a PVE role holding exactly the privileges the LXC
provider needs, a `terraform@pve` user, and an API token — each step gated on
the resource not already existing, so re-runs are no-ops.

**The token secret is printed once.** Proxmox never reveals it again. Capture it
from the play output, vault-encrypt it, and switch Terraform over in
`group_vars/proxmox/terraform.yml`:

```yaml
terraform_proxmox_user: "terraform@pve"
terraform_proxmox_token_id: "terraform@pve!ansible"
terraform_proxmox_token_secret: !vault |
  ...
```

If you lose the secret, delete the token in the PVE UI (Datacenter >
Permissions > API Tokens) and re-run to have a new one issued.

## Monitoring the host

The host is scraped like any other machine: `playbooks/node-exporter.yml`
targets `lxc:proxmox`, so node_exporter runs on the hypervisor too, and
Prometheus derives that target from the `proxmox` inventory group.

On top of host metrics, `prometheus-pve-exporter` adds per-guest, storage and
cluster metrics from the Proxmox API. It needs a read-only API token — the
setup steps are in `examples/group_vars/monitoring/main.yml`, and the exporter
is enabled by default (`prometheus_pve_exporter_enabled`).

One operational note baked into the defaults: pve-exporter re-resolves the PVE
hostname on *every* API request, roughly twenty per scrape, because pveproxy
does not keep connections alive. On a 15-second scrape interval that floods a
LAN resolver with around a hundred queries a minute. Setting
`prometheus_proxmox_pin_ip` to the host's IP pins the name in the monitoring
container's `/etc/hosts` and stops it, while keeping the scrape target on the
hostname so the `instance` labels are unchanged.

## Container backups

The `proxmox` role can create a scheduled `vzdump` job covering every guest —
whole-container restore points, complementary to the file-level restic backups.
Off by default; see `examples/group_vars/proxmox/backup.yml`.

The job is create-only. To change the schedule or retention afterwards, edit it
in Datacenter > Backup, or delete it there and re-run.
