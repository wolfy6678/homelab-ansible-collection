# homelab.core.jellyfin

Jellyfin media server, including an automated first-run wizard and library
reconciliation. Installed from the official apt repository.

## Required variables

`jellyfin_admin_password` fails with a hint if unset. It is **set** on first run
only — but library reconciliation authenticates with it on every run, so if you
change it in the UI later, mirror the change in your vault.

## The wizard

Jellyfin's `/Startup` endpoints accept anonymous requests only until setup is
complete, then return 401. The role probes that to decide whether the wizard is
still open, so it runs exactly once per container and re-runs are clean.

(It deliberately does not gate on `StartupWizardCompleted` from
`/System/Info/Public`: that field is omitted from the payload while the server
is still warming up.)

## Libraries

`jellyfin_libraries` is reconciled on every run — missing libraries are created;
extras you add in the UI, and per-library settings you change there, are left
alone.

```yaml
jellyfin_libraries:
  - name: Movies
    type: movies       # any Jellyfin collectionType
    path: "{{ jellyfin_media_dir }}/movies"
```

## Storage

`jellyfin_media_dir` (default `/mnt/media`) is just an empty directory on the
container's rootfs unless you attach real storage. Mount the drive or NAS share
on the Proxmox host, then bind-mount it in via `lxc_overrides.mountpoints` in
your inventory — see [docs/terraform.md](../../docs/terraform.md).

In an unprivileged container, bind-mounted files appear owned by the host uid
+ 100000. Make the media world-readable on the host so the `jellyfin` user can
scan it.

## Example

```yaml
- name: Install and start Jellyfin
  hosts: jellyfin
  roles:
    - homelab.core.jellyfin
```
