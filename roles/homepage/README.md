# homelab.core.homepage

The [gethomepage.dev](https://gethomepage.dev) dashboard — the homelab's front
door. Built from source with pnpm and served by systemd.

## The tile list is data

`homepage_services` is rendered straight through: every key on an item except
`name` is passed to Homepage verbatim, so the whole service schema — icons,
descriptions, `siteMonitor`, `ping`, widgets — works with no change to this
role. It ships **empty**, because which services you run is up to you.

```yaml
homepage_services:
  - group: Infrastructure
    items:
      - name: Proxmox
        icon: proxmox.svg
        href: https://pve.example.lan:8006
        description: Proxmox VE hypervisor
        siteMonitor: https://pve.example.lan:8006
        widget:
          type: proxmox
          url: https://pve.example.lan:8006
          username: "root@pam!homepage"
          password: "{{ vault_homepage_proxmox_token_secret }}"

  - group: Applications
    items:
      - name: Jellyfin
        icon: jellyfin.svg
        href: "http://{{ hostvars[groups['jellyfin'][0]].ansible_host }}:8096"
        description: Media server
        siteMonitor: "http://{{ hostvars[groups['jellyfin'][0]].ansible_host }}:8096"
```

`examples/group_vars/homepage/main.yml` has a full version covering every
service in this collection.

The `layout` block in Homepage's settings is **derived** from these group names,
so the two can't drift apart. Use `homepage_layout` to override per-group
options (keyed by group name) — the default is a 2-column row.

`homepage_widgets` is the header info-widget list, also passed through verbatim,
defaulting to resource usage, a search box and a clock.

## Widget credentials

Widgets need API tokens, and some can only be created after the service is set
up — the Home Assistant long-lived token and the Jellyfin API key both come
after their first-run onboarding. Add those widget blocks on a later run.

Vault-encrypt every one. They appear in `homepage_services` like any other key.

## Host header allow-list

Homepage rejects unknown `Host` headers with "Host validation failed". The role
builds `homepage_allowed_hosts` from `ansible_host`, `inventory_hostname` and
`homepage.<caddy_base_domain>` — the last read from the `caddy` group so it
tracks a domain rename. If you proxy Homepage under a different name, override
it, or browsing that name fails.

## Example

```yaml
- name: Install and start homepage
  hosts: homepage
  roles:
    - homelab.core.homepage
```

The build is skipped when the checkout is unchanged and a previous build
completed, so re-runs are fast. A failed or interrupted build is retried on the
next run.
