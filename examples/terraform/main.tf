# Example Terraform root module for homelab.core's `proxmox` role.
#
# Copy this directory into your own repository and edit the defaults in
# variables.tf. The role runs `terraform apply` here on every deploy, passing
# the `lxcs` map it builds from the `lxc` inventory group — see
# ../../docs/terraform.md for the full contract.
#
# The single-container module is pinned to a tag for reproducibility; bump the
# ref and re-run `terraform init -upgrade` to pick up a new release.

module "lxc" {
  source   = "git::https://github.com/wolfy6678/homelab-ansible-collection.git//terraform/modules/lxc?ref=v1.0.0"
  for_each = var.lxcs

  hostname        = coalesce(each.value.hostname, each.key)
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
