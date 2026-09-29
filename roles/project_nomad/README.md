# homelab.core.project_nomad

[Project NOMAD](https://github.com/Crosstalk-Solutions/project-nomad) — an
offline-first knowledge server: Wikipedia and other ZIM archives via Kiwix,
books, courses, maps and optional local AI, managed from a web "Command
Center".

**This is the one role in the collection that runs containers.** NOMAD's admin
app installs every content service by starting sibling containers through the
Docker socket, so there is no native install to be had. The role installs
Docker Engine from Docker's apt repository and runs NOMAD's management stack
(admin, MySQL, Redis, Dozzle, disk collector) from a templated version of
upstream's compose file. Content apps are then installed from the UI.

## Requirements

- **x86_64.** Upstream publishes amd64 images only; the role asserts it.
- **The LXC's `keyctl` feature**, for Docker inside an unprivileged container
  (`nesting` is always on in the Terraform module):

  ```yaml
  project_nomad:
    hosts:
      nomad.example.lan:
        ansible_host: 192.168.50.109
        lxc_overrides:
          keyctl: true
  ```

- **Storage.** Content is large — full English Wikipedia alone is ~100 GB.
  Either size `rootfs_size` for it or bind-mount bigger storage in with
  `lxc_overrides.mountpoints` and point `project_nomad_storage_dir` at the
  mount.
- The `community.docker` collection (a dependency of `homelab.core`, installed
  with it).

## Required variables

All three fail with a hint if unset; vault-encrypt them:

- `project_nomad_app_key` — at least 16 characters (`openssl rand -hex 32`).
- `project_nomad_db_password`, `project_nomad_db_root_password` — MySQL
  applies these **only** when it initialises an empty data directory. Changing
  them afterwards does not change the password, it breaks the admin's
  connection; rotate inside MySQL first.

## Differences from upstream's installer

- **Pinned images.** Upstream tracks `:latest` with `pull_policy: always`, so a
  restart could upgrade the admin and migrate its database. Here the admin runs
  the `project_nomad_version` tag; upgrade by bumping it. Never step it down —
  the migrations are forward-only.
- **No UI updater.** Upstream's updater sidecar upgrades NOMAD by rewriting the
  image tag in `compose.yml`, which this role owns, so the next run would
  revert it. It is left out and the UI reports system updates as unavailable.
  Content apps (Kiwix, Ollama, …) still update from the UI.
- **Secrets from the inventory** rather than generated at install, and the
  database is never wiped (upstream's installer deletes it on every run).
- **No GPU setup.** Upstream detects an NVIDIA/AMD GPU and configures the
  container runtime for Ollama. GPU passthrough into an LXC is a Proxmox-side
  job this role doesn't attempt; without it the AI assistant runs on CPU.

## The AI Assistant is off

NOMAD's AI Assistant (Ollama, plus the Qdrant vector database it depends on)
is **not installed** by this role, and NOMAD never installs it on its own: it
is seeded as not installed, the first-run setup wizard leaves it unticked, and
it only appears if someone installs it from the UI. NOMAD has no setting to
hide or disable it, so the role doesn't pretend to manage it — if you'd rather
nobody can, restrict who reaches the Command Center. Removing it again is
done from the UI too, which keeps the admin's records consistent.

## Ports

| Port | Service |
| --- | --- |
| `project_nomad_port` (8080) | Command Center |
| `project_nomad_dozzle_port` (9999) | Dozzle log viewer — **unauthenticated**; set `project_nomad_dozzle_enabled: false` to drop it |

The admin publishes further ports for each content app it installs.

If you front the Command Center with Caddy, set `project_nomad_url` to the
clean hostname — the admin builds absolute links from it.

## Example

```yaml
- name: Install and start Project NOMAD
  hosts: project_nomad
  roles:
    - homelab.core.project_nomad
```
