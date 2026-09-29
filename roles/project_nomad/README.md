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
the first-run setup wizard makes — from seven variables. All ship empty, so an
unconfigured host gets exactly upstream's out-of-the-box NOMAD.

| Variable | Semantics |
| --- | --- |
| `project_nomad_settings` | Admin settings, `key: value`. **Reconciled** — a declared key is set back every run, so it stops being editable in the UI. Undeclared keys are left alone. |
| `project_nomad_apps` | Apps to install, by NOMAD service name. **Create-only** — missing ones are installed and waited for; nothing is ever uninstalled. |
| `project_nomad_wikipedia` | Wikipedia edition: `none`, `top-mini`, `top-nopic`, `all-mini`, `all-nopic`, `all-maxi`. |
| `project_nomad_content_tiers` | Curated ZIM collections, `category: tier`. Cumulative and **grow-only**. |
| `project_nomad_map_collections` | Curated offline map collections, by slug (upstream's are US regions). |
| `project_nomad_map_regions` | Map packs for anywhere, by country or continent. **Create-only**. See [Map packs](#map-packs). |
| `project_nomad_app_urls` | Launch-URL overrides for each app's "Open" button, `service_name: URL`. **Reconciled** for declared apps. See [Behind Caddy](#behind-caddy). |

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

## Map packs

`project_nomad_map_collections` only covers upstream's curated catalogue, which
is US regions. `project_nomad_map_regions` covers everywhere else. It uses the
same feature as the UI's Maps → "Extract a region", cutting packs out of
Protomaps' latest global build:

```yaml
project_nomad_map_regions:
  - countries: [GB, IE]        # ISO 3166-1 alpha-2, any case
    label: British Isles       # optional: the title shown in the UI
  - countries: [FR]
    maxzoom: 12                # optional, 0-15, default 15 (full street detail)
  - group: europe              # a continent: africa, europe, north-america, ...
    maxzoom: 10
```

Each entry takes exactly one of `countries` or `group`. Unknown codes, groups
or zoom levels fail the run, and the message lists the valid groups. Each zoom
level down roughly quarters a pack's size, so a whole continent at z15 is
large. Consider a lower `maxzoom` for big areas.

The role only ever adds packs. NOMAD doesn't check whether it already has a
pack; every request starts a new extraction. So the role works out the file
NOMAD would write, using the same naming rule:

- the group's ID when the countries exactly match a group;
- the lower-cased code for a single country;
- otherwise `custom-<hash>`.

It then skips any pack that is already on disk or still extracting, whichever
global build it came from, so a new monthly build doesn't re-extract
everything. A failed extraction is retried on the next run. To refresh a pack,
delete it in the UI and re-run. Changing `maxzoom` extracts a second copy, so
delete the old one in the UI.

## Calibre-Web

NOMAD's Calibre-Web (`nomad_calibreweb`) starts unconfigured: every page
redirects to its "Database configuration" screen, and it logs in with the
well-known `admin` / `admin123`. When `nomad_calibreweb` is in
`project_nomad_apps`, the role finishes that first run.

**Library:** handled automatically. NOMAD copies an empty Calibre library into
its books folder, mounted at `/books`, before it starts the app, and keeps an
existing library if one is there. The role points Calibre-Web at `/books`
while no library path is set, then restarts it through NOMAD's API, because
Calibre-Web only reads the path at startup. A path changed in the UI later is
left alone. If `/books/metadata.db` is missing, the run fails and says so,
rather than pointing Calibre-Web at nothing.

**Login:** set
`project_nomad_calibreweb_admin_password` (vault-encrypted), and optionally
`project_nomad_calibreweb_admin_user`, and the role replaces that login:

```yaml
project_nomad_calibreweb_admin_user: jack   # default: admin
project_nomad_calibreweb_admin_password: "{{ vault_nomad_calibreweb_password }}"
```

This happens **once**, and only while the `admin` account still has the
factory password: `admin` is renamed and given the new password. After that
the role never touches the account, so a password changed in Calibre-Web later
sticks.

Both changes are written to the container's settings database, as the
container's own user. On a fresh install the role first waits for Calibre-Web's
first start to finish.

## Behind Caddy

NOMAD's content apps each publish their own port on the LXC, and an app's
"Open" button links to `http://<the host you browsed to>:<port>`. Through a
clean Caddy hostname that link goes nowhere. To fix it, give each app its own
`caddy_sites` entry and point NOMAD's launch URL at it with
`project_nomad_app_urls`:

```yaml
# group_vars/caddy/main.yml
caddy_sites:
  - name: nomad
    upstream: "{{ hostvars[groups['project_nomad'][0]].ansible_host }}:8080"
  - name: kiwix
    upstream: "{{ hostvars[groups['project_nomad'][0]].ansible_host }}:8090"

# group_vars/project_nomad/main.yml
project_nomad_url: https://nomad.example.com
project_nomad_app_urls:
  nomad_kiwix_server: https://kiwix.example.com
```

Values must be full `http://` or `https://` URLs, and the role checks this
before calling NOMAD. NOMAD's own validation would silently turn a bare
hostname into plain `http://` and mangle any other scheme. Declared apps are
**reconciled**: set back every run, like `project_nomad_settings`. Setting `""` restores NOMAD's default link, and
undeclared apps keep whatever the UI set. The launch URL only changes the link.
The app itself still has to be reachable at that address, which is what the
Caddy site is for.

Default app ports, from upstream's service catalogue (the app's **Open** link
shows the actual port if you are unsure):

| App | Port |
| --- | --- |
| Information Library (Kiwix) | 8090 |
| Data Tools (CyberChef) | 8100 |
| Notes (Flatnotes) | 8200 |
| Stirling PDF | 8400 |
| File Browser | 8410 |
| Calibre Web | 8420 |
| IT Tools | 8430 |
| Excalidraw | 8440 |
| Meshtastic Web | 8450 |
| Homebox | 8470 |
| Jellyfin | 8490 |
| MeshCore Web | 8500 |

Caveats:

- **The AI Assistant** is served by the Command Center at `/chat`, so it needs
  no site of its own.
- **Vaultwarden** (8480) serves its own self-signed HTTPS. The `caddy` role
  proxies to plain HTTP upstreams and doesn't skip certificate checks, so it
  can't front Vaultwarden yet.
- **Dozzle's** "Service Logs & Metrics" link ignores launch URLs and is always
  built from `project_nomad_dozzle_port`
  ([upstream #1324](https://github.com/Crosstalk-Solutions/project-nomad/issues/1324)).

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
