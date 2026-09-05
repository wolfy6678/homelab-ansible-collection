terraform {
  required_version = ">= 1.3"
  required_providers {
    proxmox = {
      source = "telmate/proxmox"
      # The 3.x line is still published as release candidates, and Terraform
      # excludes pre-releases from range constraints, so pin exactly.
      version = "3.0.2-rc07"
    }
  }

  # Local state is fine to start with, but it lives wherever you run Ansible
  # from and is not backed up. Move it somewhere durable before you rely on it.
  # backend "s3" { ... }
}

provider "proxmox" {
  pm_api_url      = var.proxmox_api_url
  pm_user         = var.proxmox_user
  pm_password     = var.proxmox_password
  pm_tls_insecure = var.proxmox_tls_insecure
}
