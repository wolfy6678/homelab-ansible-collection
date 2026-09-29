# TrueNAS: storage, shares and the backup target

The `truenas` role manages a deliberately thin slice of a baremetal TrueNAS
box — the datasets, exports and accounts the rest of the homelab depends on,
plus the backup target and the periodic maintenance that is easy to forget.
Everything about the *machine* stays where it belongs: in the installer, the
web UI, and a config backup.

This page covers that split, the bootstrap order, and the three integrations
that live half on the NAS and half in this collection.

The role is a complete no-op until `truenas_manage_enabled: true`, so you can
run everything else in the collection before the NAS exists.

---

## Division of responsibility

| Layer | Owns | Mechanism |
| --- | --- | --- |
| The installer and web UI | Disks, pool and vdev layout, network config, the administrative account, certificates, apps, updates | By hand, once |
| A saved config backup | The whole system configuration, for disaster recovery | `System > General > Manage Configuration > Download File` |
| The `truenas` role | Datasets, NFS/SMB exports, service accounts, the restic backup target, snapshot/scrub/S.M.A.R.T. schedules, alert mail | Declarative, per-resource, over `midclt` |

Rule of thumb: the role owns resources you would otherwise create by clicking
through the same five forms every time you add a service. It does not own the
pool. Creating a zpool is a one-time, hardware-specific, destructive act with
no sensible default — vdev topology depends on how many disks you have and what
you are willing to lose — so it stays in the installer where the UI can warn
you.

## Why `midclt`, not the API

TrueNAS has had three automation surfaces and is down to one:

- **REST (`/api/v2.0`)** — deprecated as of 25.10, which raises an alert when
  an endpoint is hit, and slated for full removal in TrueNAS 26.
- **JSON-RPC 2.0 over WebSocket** — the supported API from 25.04 onward, and
  versioned so an integration can pin a release. No core Ansible module speaks
  WebSocket, and this collection ships no modules or plugins.
- **`midclt`** — the local CLI onto the same middleware the WebSocket API
  fronts. Available on the box, unaffected by the REST removal, no dependency.

So the play SSHes in and drives `midclt`. Each task queries current state first
and acts only on the difference — the same thing a module would do, minus the
module.

This is the one place the collection's usual pattern is inverted: `opnsense` is
managed *from* localhost over an API, `truenas` is managed *on* the host.

## Bootstrap order

### 1. Install, by hand

Install TrueNAS, set a static address, and create the administrative account
(TrueNAS disables root SSH login; `truenas_admin` is the convention). Then
create the pool — `Storage > Create Pool` — and remember the name you gave it.

Enable SSH (`System > Services`) and add your Ansible control machine's public
key to the administrative account.

### 2. Put the NAS in the inventory

It is baremetal, not a container, so it goes alongside `proxmox` and
`opnsense` — **not** under `lxc`:

```yaml
truenas:
  hosts:
    nas.example.lan:
      ansible_host: 192.168.50.10
      ansible_user: truenas_admin
```

### 3. Declare what only the inventory can hold

Four variables must live in `group_vars/truenas/` rather than in the role's
defaults, because another role reads them off this host via `hostvars` and
*role defaults are invisible in `hostvars`*:

| Variable | Read by |
| --- | --- |
| `truenas_backup_user` | `backup` |
| `truenas_backup_repo_path` | `backup` |
| `truenas_metrics_enabled` | `prometheus` |
| `truenas_metrics_port` | `prometheus` |

See [docs/inventory.md](inventory.md) for the full list of variables in this
category.

### 4. Enable the role

```yaml
# group_vars/truenas/main.yml
truenas_manage_enabled: true
truenas_pool: tank
```

and run the play. `examples/group_vars/truenas/main.yml` is a complete worked
version.

---

## Integration 1: media, and why the LXC cannot mount it

An unprivileged LXC cannot mount NFS itself. The path runs:

```
TrueNAS export  ->  mounted on the Proxmox host  ->  bind-mounted into the LXC
```

The role owns the first hop only. It creates the dataset and the export, and
derives the export's allowed hosts from the inventory —
`truenas_homelab_clients` resolves to the Proxmox host and the Jellyfin
container, guarded so an inventory with neither renders an empty list.

The second hop is a normal `fstab` entry on the Proxmox host. The third is
`lxc_overrides.mountpoints` in your inventory, which the `proxmox` role passes
to Terraform — the commented example in `examples/inventory/hosts.yml` shows
the shape. `jellyfin_media_dir` is the path *inside* the container and is
deliberately not derived from the export path: they are different filesystems'
views of the same data, and one is not computable from the other.

In an unprivileged container, bind-mounted files appear owned by the host uid
+100000. Making the media group-readable on the NAS is the simplest fix; the
`jellyfin` role's defaults explain the rest.

## Integration 2: the restic backup target

`truenas_backup_target_enabled` creates a dataset, an unprivileged user whose
only credential is an SSH public key, the repository directory at 0700, and
enables SSH. The `backup` role then composes

```
sftp:<truenas_backup_user>@<nas>:<truenas_backup_repo_path>
```

out of the same two variables, so the URL and the thing it points at cannot
drift. Nothing else changes: `restic init`, the schedule, retention and the
textfile metrics all stay in the `backup` role.

Set `backup_restic_repository` explicitly to override — an off-site bucket, or
a NAS this collection does not manage.

The repository path must sit inside the backup dataset, and the role asserts
that. A path outside it would work, and quietly write the backups onto the
parent dataset where the snapshot policy and quota do not apply.

**Keep an off-site copy too.** A backup on the same LAN as the thing it backs
up survives a dead container; it does not survive a fire or a theft. The
`backup` role's defaults document the B2/S3 shape for a second repository.

## Integration 3: metrics

TrueNAS ships **no** Prometheus endpoint. Reporting has been Netdata since
23.10, and its OpenMetrics output is reachable only once the Netdata app is
installed, on port 20489:

```
http://<nas>:20489/api/v1/allmetrics?format=prometheus
```

Install the app (`Apps > Discover > netdata`), then declare it:

```yaml
# group_vars/truenas/main.yml
truenas_metrics_enabled: true
truenas_metrics_port: 20489
```

The `prometheus` role adds a `truenas` job with `instance: truenas`. Undeclared
means off, so no job appears until there is genuinely something to scrape —
the same convention `headscale_fail2ban_enabled` follows.

A query string is not legal in Prometheus's `metrics_path`, so the job splits
the endpoint into `metrics_path: /api/v1/allmetrics` plus
`params: {format: [prometheus]}`. That is why the two are separate variables in
the `prometheus` role rather than one URL.

The alternative, if you would rather not run the app, is TrueNAS's Graphite
export pointed at a `graphite_exporter` on the monitoring host. This collection
does not deploy one.

---

## Maintenance the role sets up

| Task | Variable | Note |
| --- | --- | --- |
| Periodic snapshots | `truenas_snapshot_tasks` | Create-only. A retention policy is yours to choose, so the collection ships none. |
| Pool scrub | `truenas_scrub_schedule` | *Updates* the task TrueNAS already made for the pool. Empty leaves the stock schedule alone. |
| S.M.A.R.T. tests | `truenas_smart_test_enabled` | A cron job, for the reason below. |
| Alert mail | `truenas_mail_*` | The one thing here that is reconciled every run. |

### S.M.A.R.T. tests are a cron job now

25.10 **removed** built-in S.M.A.R.T. test scheduling. Existing tasks were
migrated to cron on upgrade, `smartmontools` is still shipped for third-party
scripts, and the API method that remains (`disk.smart_test`) is documented as
unsupported. So the role schedules a cron job running `smartctl` across every
physical disk, resolving the disk list when the job runs so a replaced drive is
covered without another Ansible run.

If you want history and trending rather than a daily pass/fail, install the
Scrutiny app instead and leave `truenas_smart_test_enabled` off.

### Set up the mail alerts

`truenas_mail_*` is the highest-value thing on this page and the one most often
left unset. It is how TrueNAS tells you a disk is failing. Vault-encrypt
`truenas_mail_password`.

## Upgrades

The role targets **TrueNAS 25.10 (Goldeye)**. Two things to know before moving
to TrueNAS 26 when it lands:

- REST is removed there. This role does not use it, but check anything else
  you point at the NAS — 25.10.1 and later raise an alert naming the caller.
- The middleware API is versioned now, so `midclt` method names are stable
  within a release line. If a method here disappears, the version notes will
  say what replaced it.
