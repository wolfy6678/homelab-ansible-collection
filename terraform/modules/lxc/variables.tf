variable "hostname" {
  type        = string
  description = "Hostname to assign to the LXC container"
}

variable "ip" {
  type        = string
  description = "Static IP address (CIDR) for the LXC container (e.g. 192.168.50.100/24)"
}

variable "target_node" {
  type        = string
  description = "Proxmox node name on which to create the LXC container"
}

variable "ostemplate" {
  type        = string
  description = "Proxmox OS template to use for the LXC container"
}

variable "memory" {
  type        = number
  description = "Memory (MB) allocated to the LXC container"
}

variable "cores" {
  type        = number
  description = "Number of CPU cores allocated to the LXC container"
}

variable "rootfs_size" {
  type        = string
  description = "Root filesystem size for the LXC container (e.g. 8G)"
}

variable "bridge" {
  type        = string
  description = "Proxmox network bridge to attach the LXC container to"
}

variable "gateway" {
  type        = string
  description = "Default gateway for the LXC container network interface"
}

variable "storage" {
  type        = string
  description = "Proxmox storage ID to use for the LXC rootfs (e.g. local-lvm)"
}

variable "ssh_public_keys" {
  type        = string
  description = "SSH public key(s) to inject into the LXC container for root access"
}

variable "password" {
  type        = string
  sensitive   = true
  description = "Root password to set inside the LXC container"
}

variable "mountpoints" {
  type = list(object({
    storage = string
    mp      = string
    size    = string
    volume  = optional(string)
  }))
  description = <<-EOT
    Extra mountpoints for the LXC container; key/slot are derived from list
    position. For a bind mount (host directory, e.g. an external drive or NAS
    mounted on the Proxmox host) set storage AND volume to the host path and
    size to 0G; for a storage-backed volume set storage to a Proxmox storage ID,
    size to the volume size, and leave volume unset.
  EOT
}

variable "keyctl" {
  type        = bool
  default     = false
  description = "Enable the keyctl LXC feature (needed alongside nesting to run Docker inside an unprivileged container)"
}
