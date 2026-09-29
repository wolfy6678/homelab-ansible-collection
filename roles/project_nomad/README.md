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

## Configuration as code

After the stack is up the role drives the admin's HTTP API — the same calls
the first-run setup wizard makes — from five variables. All ship empty, so an
unconfigured host gets exactly upstream's out-of-the-box NOMAD.

| Variable | Semantics |
| --- | --- |
| `project_nomad_settings` | Admin settings, `key: value`. **Reconciled** — a declared key is set back every run, so it stops being editable in the UI. Undeclared keys are left alone. |
| `project_nomad_apps` | Apps to install, by NOMAD service name. **Create-only** — missing ones are installed and waited for; nothing is ever uninstalled. |
| `project_nomad_wikipedia` | Wikipedia edition: `none`, `top-mini`, `top-nopic`, `all-mini`, `all-nopic`, `all-maxi`. |
| `project_nomad_content_tiers` | Curated ZIM collections, `category: tier`. Cumulative and **grow-only**. |
| `project_nomad_map_collections` | Curated offline map collections, by slug (upstream's are US regions). |

```yaml
project_nomad_settings:
  ui.hasVisitedEasySetup: true   # skip the setup wizard; this file is the setup
  contentAutoUpdate.enabled: true
project_nomad_apps:
  - nomad_kiwix_server           # the Information Library — serves every ZIM
  - nomad_kolibri
  - nomad_cyberchef
project_nomad_wikipedia: all-nopic
project_nomad_content_tiers:
  medicine: medicine-standard
  survival: survival-essential
```

App names: `nomad_kiwix_server`, `nomad_kolibri`, `nomad_cyberchef`,
`nomad_flatnotes`, `nomad_stirling_pdf`, `nomad_filebrowser`,
`nomad_calibreweb`, `nomad_it_tools`, `nomad_excalidraw`,
`nomad_meshtastic_web`, `nomad_meshtasticd`, `nomad_meshcore_web`,
`nomad_homebox`, `nomad_vaultwarden`, `nomad_jellyfin` — and `nomad_ollama`,
the AI Assistant. Content categories are `medicine`, `survival`, `education`,
`diy`, `agriculture` and `computing`, each with `<category>-essential`,
`-standard` and `-comprehensive` tiers. Unknown names, tiers, collections and
setting keys fail the run with the valid choices; declaring ZIM content without
`nomad_kiwix_server` fails too, since nothing else serves it.

Downloads are **started, not waited for** — a full Wikipedia takes hours. Watch
them in the UI. The admin keys each job on its URL, so a re-run mid-download
neither restarts nor duplicates anything. A file that keeps failing there is
usually a stale entry in upstream's catalogue (a ZIM the Kiwix mirror has
since replaced), not this role.

Why the split between reconciled and create-only: settings are a handful of
values with one right answer, but apps and content are also added from the
UI, and a run that uninstalled what someone installed by hand — or deleted a
100 GB download — would be worse than drift. Remove things from the UI, which
keeps the admin's records consistent.

## The AI Assistant is off

The AI Assistant (Ollama, plus the Qdrant vector database it depends on) is
installed only if `project_nomad_apps` lists `nomad_ollama`. NOMAD never
installs it on its own either: it is seeded as not installed and the setup
wizard leaves it unticked. NOMAD has no setting to hide or disable it, though,
so anyone who reaches the Command Center can still install it from the UI — if
that matters, restrict who reaches it.

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
