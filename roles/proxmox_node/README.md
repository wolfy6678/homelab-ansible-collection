# homelab.core.proxmox_node

Post-install configuration of a Proxmox VE host — the layer below the
containers. Codifies what the rest of the collection assumes about a fresh PVE
node.

Runs **on the PVE host over SSH**, as root. The bare-metal install and the
network setup stay manual: see [docs/proxmox-node.md](../../docs/proxmox-node.md).

## What it does

| | Default | |
| --- | --- | --- |
| Replaces the enterprise apt repo with `pve-no-subscription` | on | so `apt` works without a subscription |
| Downloads the LXC OS template | on | the image Terraform clones |
| SMART disk-health metrics via a systemd timer | on | read-only; feeds the Proxmox dashboard and the failing-disk alert |
| Removes the subscription nag | off | cosmetic, and undone by widget-toolkit updates |
| Creates a least-privilege Terraform API user | off | create-only; the token secret is printed once |

All of it is idempotent — an already-configured host reports no change.

## Requirements

- The host in the `proxmox` inventory group.
- `node_exporter_textfile_dir` set in `group_vars/all` (the SMART timer writes
  there).

## Example

```yaml
- name: Configure the Proxmox VE host (post-install)
  hosts: proxmox
  become: false   # already connecting as root@pam
  roles:
    - homelab.core.proxmox_node
```

Run it **before** provisioning containers, so the template and repos exist when
Terraform runs.

## Notes

If you change `proxmox_node_templates`, change `ostemplate` in your Terraform
root module to match — nothing cross-checks them.

Enabling `proxmox_node_terraform_user_enabled` prints the new API token secret
exactly once. Capture it from the play output; Proxmox never reveals it again.
