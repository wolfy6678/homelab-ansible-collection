output "vmid" {
  description = "Numeric vmid of the LXC container"
  value       = proxmox_lxc.this.vmid
}

output "id" {
  description = "Raw Proxmox resource id of the LXC container (node/lxc/<vmid>)"
  value       = proxmox_lxc.this.id
}
