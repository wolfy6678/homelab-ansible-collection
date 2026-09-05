# homelab.core.node_exporter

The Prometheus `node_exporter` agent: CPU, memory, disk and network metrics.
Installed from the pinned upstream release tarball.

Run it on **every** host including the Proxmox hypervisor, so the monitoring
stack sees the guests and the machine underneath them.

## Requirements

`node_exporter_textfile_dir` must be set in `group_vars/all`. The role asserts
it up front.

That variable is not a role default on purpose: the `backup` and `proxmox_node`
roles write `.prom` files into the same directory and read the same variable. A
file dropped anywhere else is silently never scraped, so there is one source of
truth for the path.

## The textfile collector

The exporter runs with `--collector.textfile.directory`, which turns that
directory into a drop box: any job that writes a `.prom` file there gets its
metrics scraped alongside the built-in collectors. In this collection:

- `backup` writes `homelab_backup_*` — run status, duration, repository size
- `proxmox_node` writes `smartmon_*` — disk health, temperature, wear

Writers `mkdir -p` the directory themselves, so they don't depend on role
ordering.

## Example

```yaml
- name: Install node_exporter on all LXCs and the Proxmox host
  hosts: lxc:proxmox
  roles:
    - homelab.core.node_exporter
```

Prometheus derives its scrape targets from the same groups, so a host added to
`lxc` is scraped without touching the Prometheus config.
