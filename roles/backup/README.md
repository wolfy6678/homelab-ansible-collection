# homelab.core.backup

File-level application-data backups with [restic](https://restic.net):
encrypted, deduplicated and off-site-capable, on a systemd timer, exporting
Prometheus metrics.

Complements the Proxmox `vzdump` backups the `proxmox` role can schedule — those
cover whole containers, these cover the data inside them.

## Enabling

A no-op until `backup_enabled: true` **and** a repository and password are set.
Both fail with a hint until then.

```yaml
backup_enabled: true
backup_restic_repository: sftp:backup@192.168.50.50:/srv/restic/homelab
backup_restic_password: !vault |
  ...
```

The repository URL is backend-agnostic:

| | |
| --- | --- |
| `sftp:backup@nas:/srv/restic/homelab` | a NAS over SSH |
| `rest:https://user:pass@nas:8000/homelab` | rest-server |
| `b2:my-bucket:homelab` | Backblaze B2, off-site |
| `s3:s3.amazonaws.com/my-bucket/homelab` | any S3-compatible store |

Backend credentials go in `backup_restic_env` (vault-encrypted), e.g.
`B2_ACCOUNT_ID` and `B2_ACCOUNT_KEY`.

> Keep a copy of the repository password **outside the homelab**. Without it the
> backups cannot be recovered, by you or anyone.

## What gets backed up

`backup_default_paths` is a `{short hostname: [paths]}` map and ships **empty** —
which applications you run, and where their data lives, is up to you. Adding a
host to the `backup` inventory group is only half the job: a host with no entry
backs up nothing, and the run fails saying so.

```yaml
backup_default_paths:
  homeassistant:
    - /home/homeassistant/.homeassistant
  otterwiki:
    - /var/lib/otterwiki
  jellyfin:
    - /var/lib/jellyfin
```

Set `backup_paths` directly on a host to bypass the map. `backup_exclude` adds
`--exclude` patterns applied to every path.

## Schedule and retention

Daily at `backup_schedule` (03:00) with a `backup_random_delay` spread (30
minutes), so co-located hosts don't all hit the repository at once.
`backup_retention` is applied by `restic forget --prune` after each run — 7
daily, 4 weekly, 6 monthly by default.

## Metrics

The wrapper writes `homelab_backup_*` metrics into node_exporter's textfile
directory (`backup_textfile_dir`, defaulting to the shared
`node_exporter_textfile_dir`): run status, duration, repository size. These
drive the Backups dashboard and the backup-stale and backup-failed Grafana
alerts.

## Example

```yaml
- name: Back up application data with restic
  hosts: backup
  roles:
    - homelab.core.backup
```

Run it last, so data is captured after every service is up to date.
