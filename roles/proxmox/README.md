# homelab.core.proxmox

Provisions the LXC fleet. Builds a Terraform `lxcs` map from the `lxc`
inventory group, applies it against **your** Terraform root module, starts the
containers, and handles the two things Terraform can't.

## What it does

1. Walks `groups['lxc']` and builds one map entry per host — keyed by
   `inventory_hostname_short`, with `ip` from `ansible_host` (plus
   `lxc_subnet_prefix`, default `/24`) merged over that host's `lxc_overrides`.
2. Runs `terraform apply` at `proxmox_terraform_project_path`.
3. Starts each container by the vmid the root module outputs.
4. Adds `/dev/net/tun` passthrough to containers flagged `lxc_tun: true`, and
   reboots them.
5. Optionally creates a scheduled `vzdump` backup job covering every guest.

## Requirements

- Terraform on the machine running Ansible, and a **root module you supply** —
  the collection ships only the reusable single-container module. See
  [docs/terraform.md](../../docs/terraform.md), and
  [examples/terraform](../../examples/terraform) for a working one.
- The seven `terraform_proxmox_*` variables in `group_vars/proxmox`. The role
  asserts them before doing anything.
- `community.general` and `community.proxmox` (installed with the collection).

## Example

```yaml
- name: Create Proxmox LXCs using Terraform
  hosts: proxmox
  gather_facts: false
  roles:
    - homelab.core.proxmox
```

Destroy the fleet by setting `terraform_proxmox_state: absent`.

## Notes

`proxmox_terraform_project_path` (default `../../terraform/`) resolves relative
to the directory you run `ansible-playbook` from, **not** to the playbook file.

The Terraform task is `no_log: true`: it carries the vaulted Proxmox and
container root passwords, and the Terraform module does not mark them sensitive.

Scheduled `vzdump` backups are create-only. To change the schedule or retention
afterwards, edit the job in Datacenter > Backup, or delete it there and re-run.
