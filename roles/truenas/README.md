# homelab.core.truenas

Reconciles the storage resources the homelab depends on, on a baremetal
TrueNAS box: datasets, their NFS/SMB exports, the accounts that reach them, the
restic backup target, and the periodic snapshot/scrub/alerting plumbing.

A deliberately thin, declarative slice — the same bargain the `opnsense` role
strikes. Pool and vdev layout, disk replacement, apps, certificates, the network
config and everything else done at install time are **not** managed here. See
[docs/truenas.md](../../docs/truenas.md) for the division of responsibility and
the bootstrap runbook.

## Enabling

A no-op until `truenas_manage_enabled: true`, so a full site run never requires
the NAS to be reachable. While disabled nothing is evaluated, so the `undef()`
`truenas_pool` never fires.

## The playbook

Unlike `opnsense`, this role runs **on** the host. `midclt` talks to the
middleware over a root-owned socket, so the play needs `become`:

```yaml
- name: Configure the TrueNAS storage server
  hosts: truenas
  become: true
  roles:
    - homelab.core.truenas
```

TrueNAS disables root SSH login by default; connect as `truenas_admin` (or
whichever administrative account you created in the installer) and let it sudo.

## Why midclt and not the API

The REST API is deprecated as of TrueNAS 25.10 — it raises an alert when hit —
and is slated for removal in TrueNAS 26. Its replacement is JSON-RPC 2.0 over a
WebSocket, which no core Ansible module speaks. `midclt` is the local CLI onto
the same middleware, so it survives that transition and needs no extra
collection dependency. Each task queries current state first and acts only on
the difference, which is what a module would have done anyway.

## What is create-only

Per the collection's convention for anything a human also edits in a web UI:

| Resource | Behaviour |
| --- | --- |
| Datasets | Created if absent. Properties are never reconciled; `owner`/`group`/`mode` are applied only to datasets this run created. |
| Users, groups | Created if absent. A password or key rotated in the UI survives. |
| Snapshot tasks | Created if absent, matched on dataset + naming schema. |
| S.M.A.R.T. cron job | Created if absent, matched on its description. |
| NFS / SMB shares | Created **or updated** — allowed hosts and export options should track the inventory, and rewriting them cannot lose data. |
| Pool scrub | Updates the task TrueNAS already made for the pool, never adds a second. |
| Mail | Reconciled every run; it is a singleton config with no "already exists". |

Share drift is judged only on the keys you declared, so options set in the UI
that your inventory says nothing about are left alone.

## Lists are data

`truenas_datasets`, `truenas_nfs_shares`, `truenas_smb_shares`,
`truenas_users`, `truenas_groups` and `truenas_snapshot_tasks` all ship empty
and pass every key straight through to the middleware, so any option TrueNAS
accepts works with no role change. The only keys the role interprets are:

- `name` / `path` / `dataset` — relative to `truenas_pool`, so `media` means
  `<pool>/media` at `/mnt/<pool>/media`
- `owner`, `group`, `mode` on a dataset — stripped from the create payload and
  applied to the mounted directory

In 25.10 an NFS share's export field is `path` (singular). Older releases and
some third-party collections use a `paths` list; that shape is now rejected.

## Required variables

`truenas_pool` has no default — it is created in the installer, and guessing
`tank` would silently target the wrong pool.

These must be set in **`group_vars/truenas/`**, not as role defaults, because
another role reads them off this host via `hostvars` and role defaults are
invisible there:

| Variable | Read by | Why |
| --- | --- | --- |
| `truenas_backup_user` | `backup` | Composes `backup_restic_repository` |
| `truenas_backup_repo_path` | `backup` | Composes `backup_restic_repository` |
| `truenas_metrics_enabled` | `prometheus` | Gates the scrape job; undeclared means off |
| `truenas_metrics_port` | `prometheus` | Scrape target port |

The first two are asserted up front when `truenas_backup_target_enabled` is on,
so a missing one fails with an instruction rather than an undefined-variable
error inside the `backup` role on a different host.

## Backup target

`truenas_backup_target_enabled` creates the dataset, an unprivileged user whose
only credential is `truenas_backup_ssh_key`, the repository directory at 0700,
and enables SSH. The `backup` role then derives

```
sftp:<truenas_backup_user>@<nas>:<truenas_backup_repo_path>
```

so the repository URL and the thing it points at cannot drift. `restic init`
still happens on the backup host, on its first run.

The repo path must live inside the backup dataset; the role asserts it. A path
outside would work and quietly write the backups onto the parent dataset, where
the snapshot policy and quota do not apply.

## Metrics

TrueNAS ships **no** Prometheus endpoint. Reporting is Netdata, and its
OpenMetrics output only exists once the Netdata app is installed — which is why
`truenas_metrics_enabled` is undeclared (and so off) by default. Install the
app, then declare it and the port; the `prometheus` role adds the job. See
[docs/truenas.md](../../docs/truenas.md).

## S.M.A.R.T. tests

25.10 removed built-in S.M.A.R.T. test scheduling and migrated existing tasks
to cron, so `truenas_smart_test_enabled` creates a cron job running `smartctl`
over every physical disk — smartmontools is still shipped for exactly this. The
disk list is resolved when the job runs, so a replaced drive is covered without
another Ansible run. Install the Scrutiny app instead if you want history and
trending rather than a daily short test.

## Requirements

None beyond `ansible.builtin` — `midclt` ships with TrueNAS. Tested against
TrueNAS 25.10 (Goldeye).
