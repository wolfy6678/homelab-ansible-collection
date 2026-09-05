# Example consumer repository

A complete, working skeleton for a homelab built with `homelab.core`. Copy this
directory into your own git repository, replace the example values, and you have
the "consuming repo" the collection expects.

```
ansible.cfg              vault prompt + inventory location
requirements.yml         the collection and its dependencies
inventory/hosts.yml      the fleet: groups, IPs, per-container sizing
group_vars/              your settings — one directory per inventory group
playbooks/               one playbook per service
site.yml                 all of them, in dependency order
terraform/               the Terraform root module (see docs/terraform.md)
```

Everything is deliberately generic: LAN `192.168.50.0/24`, firewall `.1`,
Proxmox host `.2`, containers `.100+`, domain `example.com`. Search for those
and replace them with yours.

Every credential is shown as a commented-out `!vault` block. Fill them in with:

```bash
ansible-vault encrypt_string --vault-id homelab@prompt '<secret>' --name '<var>'
```

Terraform's inputs are the exception — they are passed to it as a `.tfvars`
file, which has no vault support. `terraform.tfvars` therefore holds the Proxmox
API password, the LXC root password and your SSH key in clear text; the shipped
`.gitignore` keeps it out of git, and only `terraform.tfvars.example` is
tracked. (Running the `proxmox` role instead passes those values from your
vaulted `group_vars/proxmox/terraform.yml`, so you only need the `.tfvars` file
when you run Terraform by hand.)

Start with [docs/getting-started.md](../docs/getting-started.md), which walks
through this skeleton in order.
