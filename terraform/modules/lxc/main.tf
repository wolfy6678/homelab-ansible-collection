terraform {
  # Deliberately unversioned: the root module owns the pin, because the choice
  # is site-specific — telmate/proxmox 3.x is published only as release
  # candidates, which Terraform excludes from range constraints, so a consumer
  # has to pin exactly (see examples/terraform/provider.tf). This module's
  # resource schema is valid on both the 2.9 and 3.0 lines; adding a constraint
  # here would only take that choice away.
  required_providers {
    proxmox = {
      source = "telmate/proxmox"
    }
  }
}

resource "proxmox_lxc" "this" {
  target_node     = var.target_node
  hostname        = var.hostname
  ostemplate      = var.ostemplate
  password        = var.password
  memory          = var.memory
  cores           = var.cores
  ssh_public_keys = var.ssh_public_keys

  # Start on creation and bring the container back up automatically after a
  # Proxmox host reboot (the provider defaults both to false, which would leave
  # every service down until someone re-runs the play or `pct start`s by hand).
  onboot = true
  start  = true

  features {
    nesting = true
    keyctl  = var.keyctl
  }

  rootfs {
    storage = var.storage
    size    = var.rootfs_size
  }

  dynamic "mountpoint" {
    for_each = var.mountpoints
    content {
      key     = tostring(mountpoint.key)
      slot    = mountpoint.key
      storage = mountpoint.value.storage
      volume  = mountpoint.value.volume
      mp      = mountpoint.value.mp
      size    = mountpoint.value.size
    }
  }

  network {
    name   = "eth0"
    bridge = var.bridge
    ip     = var.ip
    gw     = var.gateway
  }
}
