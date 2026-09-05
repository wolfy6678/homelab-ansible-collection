# The first six are passed in by the homelab.core `proxmox` role from the
# terraform_proxmox_* variables in group_vars/proxmox/. Running terraform by
# hand instead? Copy terraform.tfvars.example to terraform.tfvars.

variable "proxmox_api_url" {
  type        = string
  description = "Proxmox API endpoint, e.g. https://pve.example.lan:8006/api2/json"
}

variable "proxmox_user" {
  type        = string
  description = "Proxmox user Terraform authenticates as, e.g. root@pam"
}

variable "proxmox_password" {
  type        = string
  sensitive   = true
  description = "Password for proxmox_user"
}

variable "proxmox_lxc_password" {
  type        = string
  sensitive   = true
  description = "Root password set inside every created container"
}

variable "proxmox_lvm_storage" {
  type        = string
  description = "Proxmox storage ID for container root filesystems, e.g. local-lvm"
}

variable "proxmox_ssh_key" {
  type        = string
  description = "SSH public key injected for root, so Ansible can reach the containers"
}

variable "proxmox_tls_insecure" {
  type        = bool
  default     = true
  description = "Skip API certificate verification. Proxmox ships a self-signed cert; set false once you trust the PVE CA where Terraform runs."
}

# THIS is the file to edit. The role only ever supplies `ip` plus whatever the
# host sets in `lxc_overrides`, so every other setting falls back to the
# optional() defaults below — they are your fleet-wide container defaults.
variable "lxcs" {
  description = "Containers to create, keyed by short hostname. Built from the `lxc` inventory group by the homelab.core proxmox role."
  type = map(object({
    ip          = string
    hostname    = optional(string)
    target_node = optional(string, "pve")
    ostemplate  = optional(string, "local:vztmpl/debian-13-standard_13.1-2_amd64.tar.zst")
    memory      = optional(number, 2048)
    cores       = optional(number, 2)
    rootfs_size = optional(string, "8G")
    keyctl      = optional(bool, false)
    bridge      = optional(string, "vmbr0")
    gateway     = optional(string, "192.168.50.1")
    mountpoints = optional(list(object({
      storage = string
      mp      = string
      size    = optional(string, "0G")
      volume  = optional(string)
    })), [])
  }))
  default = {}
}
