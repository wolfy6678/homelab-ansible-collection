# Provisioning the containers with Terraform

The `proxmox` role does not create containers itself. It:

1. builds a Terraform `lxcs` map from the `lxc` inventory group,
2. runs `terraform apply` against **your** root module,
3. starts the containers, passes `/dev/net/tun` into any flagged with
   `lxc_tun`, and optionally configures scheduled `vzdump` backups.

The collection ships the reusable single-container module
(`terraform/modules/lxc`) but deliberately **not** the root module: provider
credentials, the state backend and your container defaults are site-specific
and belong in your own repository, under your own version control.

A complete, working root module is in
[`examples/terraform/`](../examples/terraform/) — copy it and edit the
defaults.

## Pinning the provider

Pin `telmate/proxmox` to an **exact** version in your root module:

```hcl
proxmox = {
  source  = "telmate/proxmox"
  version = "3.0.2-rc07"
}
```

The 3.x line is still published only as release candidates, and Terraform
excludes pre-releases from range constraints — so `version = "~> 3.0"` fails
with *"no available releases match the given constraints"* rather than
resolving to the RC. A range like `~> 2.9` works but silently gives you the
older line.

The container module deliberately declares no version constraint of its own, so
this choice stays yours; its resource schema is valid on both lines.

## What the root module must provide

`roles/proxmox/tasks/main.yml` passes these variables in and reads one output
back, so a root module has to match on both sides.

### Input variables

| Variable | Comes from | Notes |
| --- | --- | --- |
| `proxmox_api_url` | `terraform_proxmox_api_url` | e.g. `https://pve.example.lan:8006/api2/json` |
| `proxmox_user` | `terraform_proxmox_user` | `root@pam`, or a dedicated user — see [docs/proxmox-node.md](proxmox-node.md) |
| `proxmox_password` | `terraform_proxmox_password` | vault-encrypted |
| `proxmox_lxc_password` | `terraform_proxmox_lxc_password` | root password set inside each container; vault-encrypted |
| `proxmox_lvm_storage` | `terraform_proxmox_lvm_storage` | e.g. `local-lvm` |
| `proxmox_ssh_key` | `terraform_proxmox_ssh_key` | public key injected for root SSH — this is how Ansible gets in afterwards |
| `lxcs` | built from the inventory | see below |

`terraform_proxmox_state` is passed to the `community.general.terraform`
module's `state`, not to the module: `present` to converge, `absent` to
destroy the fleet.

The whole task is `no_log: true` because those variables carry vaulted
credentials the Terraform module does not mark sensitive.

### The `lxcs` map

`build_lxcs.yml` produces one entry per host in the `lxc` group:

```hcl
lxcs = {
  monitoring = { ip = "192.168.50.108/24", memory = 4096, rootfs_size = "20G" }
  caddy      = { ip = "192.168.50.107/24", cores = 1, memory = 512 }
}
```

The key is `inventory_hostname_short`. The `ip` is `ansible_host` plus
`lxc_subnet_prefix` (default `/24`). **Everything else comes from that host's
`lxc_overrides` dict** — so the root module must supply defaults for every
other setting the container module needs (`target_node`, `ostemplate`,
`memory`, `cores`, `rootfs_size`, `bridge`, `gateway`, `mountpoints`,
`keyctl`). The example root module does this with an optional-attribute object
type and a `defaults` local.

### Required output

```hcl
output "lxc_vmids" {
  value = { for name, m in module.lxc : name => m.vmid }
}
```

The role reads `outputs.lxc_vmids.value` to start each container by vmid and to
find the ones needing TUN passthrough. Without this output the apply succeeds
but nothing starts.

## Pointing the role at it

`proxmox_terraform_project_path` (default `../../terraform/`) is resolved
**relative to the directory you run `ansible-playbook` from**, not relative to
the playbook file. Set it explicitly if your layout differs:

```yaml
# group_vars/proxmox/main.yml
proxmox_terraform_project_path: "{{ playbook_dir }}/../terraform"
```

## Using the container module directly

The module is consumable straight from git if you'd rather write your own root
module from scratch:

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

It creates an unprivileged container with `nesting` on, `onboot = true` and
`start = true`, a single `eth0` on the given bridge with a static IP, and any
extra mountpoints you pass.

### Mountpoints

For a bind mount of a host directory (an external drive or NAS mounted on the
PVE host), set `storage` **and** `volume` to the host path and `size` to `0G`:

```yaml
lxc_overrides:
  mountpoints:
    - storage: /mnt/media
      volume: /mnt/media
      mp: /mnt/media
      size: 0G
```

For a storage-backed volume, set `storage` to a Proxmox storage ID and `size`
to the volume size, and leave `volume` unset.

In an unprivileged container a bind-mounted file appears owned by the host uid
+ 100000, so make the content world-readable on the host if a service inside
needs to read it.

## Running Terraform by hand

Nothing stops you — the role's apply is idempotent and shares the state file:

```bash
cd terraform
terraform init
terraform plan
```

Keep the state somewhere durable. The example module uses local state for
simplicity; a shared or remote backend is worth setting up before the fleet
grows.
