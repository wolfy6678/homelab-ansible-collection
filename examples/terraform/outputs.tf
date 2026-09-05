# REQUIRED by the homelab.core `proxmox` role: it reads this map to start each
# container by vmid and to find the ones needing /dev/net/tun passed through.
output "lxc_vmids" {
  description = "Map of short hostname to the created container's vmid"
  value       = { for name, m in module.lxc : name => m.vmid }
}
