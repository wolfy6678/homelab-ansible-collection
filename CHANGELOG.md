# Changelog

All notable changes to this collection are documented here. This project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.0] - 2026-11-16

### Changed

Upstream version bumps. All except Dozzle are minor or patch releases within
the same major version.

| Role | Variable | From | To |
| --- | --- | --- | --- |
| `headscale` | `headscale_version` | 0.29.1 | 0.29.7 |
| `loki` | `loki_version` | v3.7.3 | v3.7.10 |
| `prometheus` | `prometheus_version` | v3.12.0 | v3.16.0 |
| `prometheus` | `prometheus_pve_exporter_version` | 3.9.0 | 3.12.0 |
| `node_exporter` | `node_exporter_version` | v1.11.1 | v1.12.1 |
| `alloy` | `alloy_version` | v1.17.1 | v1.22.0 |
| `gatus` | `gatus_version` | v5.36.0 | v5.38.0 |
| `gatus` | `gatus_go_version` | 1.26.3 | 1.26.11 |
| `otterwiki` | `otterwiki_version` | 2.20.6 | 2.26.3 |
| `project_nomad` | `project_nomad_version` | 1.34.1 | 1.35.1 |
| `homeassistant` | `homeassistant_foxess_version` | v1.15.0 | v1.16.0 |
| `project_nomad` | `project_nomad_dozzle_image` | amir20/dozzle:v10.0 | amir20/dozzle:v11.4.3 |

The Go toolchain stays on the 1.26 line, because Gatus v5.38.0's `go.mod`
still declares go 1.26.3. The 1.26.11 patch release brings the standard
library's security fixes into the built binary.

The `project_nomad` role now runs Dozzle with the setup wizard, release and
image update checks, and anonymous analytics switched off
(`DOZZLE_DISABLE_SETUP_WIZARD=true`, `DOZZLE_RELEASE_CHECK_MODE=manual`,
`DOZZLE_IMAGE_CHECK_MODE=off`, `DOZZLE_NO_ANALYTICS=true`). Dozzle has no login
in NOMAD's stack, and v11 turns all four on by default.

### Upgrade notes

Every bump below was deployed to a live homelab running the roles' own
templates, and checked after deploy. Only the NOMAD upgrade needs action
from you. The rest of this section covers upstream changes that only
matter if your inventory uses features the roles don't set up themselves.

#### Before you upgrade

- **`project_nomad`: back up the database first.** NOMAD 1.34.1 to 1.35.1
  runs schema migrations that only go forward, and the role can't roll them
  back. Dump the database on the NOMAD host before deploying:

  ```sh
  docker exec nomad_mysql sh -c \
    'mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction --routines --databases nomad' \
    | gzip > /path/to/nomad-before-1.35.1.sql.gz
  ```

  Store it on the content volume or off the host, not on the rootfs.
- **`headscale`: copy the database if you want a way back.** 0.29.7 trims
  stored hostnames, endpoints and routes to new size limits when it starts,
  drops zoned IPv6 endpoints and oversized Hostinfo, and doesn't say whether
  that can be undone. Stop the service and copy
  `/var/lib/headscale/db.sqlite`, along with its `-wal` and `-shm` files if
  they exist.

#### Behaviour changes to know about

- **`headscale` 0.29.2 to 0.29.7** (no breaking changes upstream):
  - Metrics are only served on `headscale_metrics_listen_addr`, and no
    longer over the Noise protocol. The role's preflight assert already
    requires that address.
  - 0.29.7 is a security release. Upstream recommends Tailscale v1.104.4 or
    newer on every node, especially nodes using Tailscale SSH. The role's
    subnet router follows Tailscale's apt repo, but your phones and other
    clients need updating themselves.
  - `http_requests_total` and `http_request_duration_seconds` now count all
    traffic, not just OPTIONS requests. The names are the same, but any
    dashboard or alert built on their values will shift.
  - Expired tagged nodes need a valid pre-auth key to re-register.
  - Single-address routes inside the tailnet's node IP range are no longer
    served.
- **`otterwiki` 2.20.6 to 2.26.3**, a security-heavy range. 2.22.0 rejects
  invalid git revisions, a fix upstream says to install promptly. Things
  that look different afterwards:
  - Symlinks that point outside the repository are blocked by default
    (2.25.2). Set `GIT_ALLOW_EXTERNAL_SYMLINKS` in OtterWiki's settings if
    your wiki relies on them.
  - Attachments are served sandboxed, and active content is forced to
    download (2.26.0).
  - Uploaded filenames are NFKC-normalised (2.24.1).
  - Webhook hashes are now HMACs keyed by `SECRET_KEY` (2.20.7). Rotating
    `otterwiki_secret_key` changes them.
  - The role's `GIT_REMOTE_PUSH_PRIVATE_KEY` (inline key content) still
    works. Mirror pushes were verified after the upgrade.
- **`prometheus` v3.12.0 to v3.16.0.** The role's own config and flags are
  unaffected. If you've added scrape or remote-write settings of your own,
  note that:
  - credentials are no longer forwarded on a cross-host redirect (3.13.0);
  - `__meta_hetzner_datacenter` is gone for hcloud targets (3.14.0);
  - `--log.level` is deprecated in favour of `runtime.log_level` (3.15.0).
    The role doesn't set it.
  - Several `prometheus_remote_storage_metadata_*` metrics are no longer
    exposed for Remote Write 2.0 queues (3.16.0).
- **`prometheus` pve-exporter 3.9.0 to 3.12.0** needs Python 3.11 or newer
  (3.10.0). Debian 12 and 13 meet that; Debian 11 doesn't. Tracebacks are
  now suppressed unless you raise `--log.level` (3.12.0). Metric names and
  labels are unchanged.
- **`alloy` v1.17.1 to v1.22.0** has breaking changes upstream, but only in
  components the role's config doesn't use: OpenTelemetry (`otelcol.*`),
  `loki.enrich`/`prometheus.enrich`, Kafka, Hetzner discovery,
  `prometheus.operator.*`, and `loki.write` with `wal` enabled. If you've
  extended the Alloy config with any of those, read the 1.18.0 to 1.22.0
  upstream changelog sections first. In particular, from 1.21.0 a
  `loki.write` `wal` block won't load without `--stability.level=experimental`,
  and the `tenant` label is gone from `loki.write` metrics.
- **`node_exporter` v1.11.1 to v1.12.1** has no breaking changes. hwmon chip
  labels are now disambiguated when they collide, and the filesystem
  collector's mount-options label is comma-separated, so a few series can
  change their label values.
- **`gatus` v5.36.0 to v5.38.0** has no breaking changes. Maintenance windows
  on external, DNS and SSH endpoints are now validated, which matters if
  your `gatus_endpoints` declare them.
- **`project_nomad` 1.35.x:** oversized custom app URLs are now rejected
  (`project_nomad_app_urls`), map marker notes are capped at 500 characters,
  and 11 curated ZIMs were re-pointed to new upstream files. Dozzle v10 to
  v11 needs no config change.
- **`homeassistant` foxess_modbus v1.16.0:** if your inverter isn't running
  the latest manager firmware, select its version under Settings > Devices
  & Services > FoxESS - Modbus > Configure > Version settings.
- **`loki` v3.7.4 to v3.7.10** is bug fixes only.

#### Rolling back, and cleaning up

`prometheus`, `loki`, `alloy`, `node_exporter` and `gatus` install each
version into its own directory (`/opt/<name>/<version>/`) and point the
binary or service at it. To roll back, set the role's `*_version` variable to
the old value and re-run the play. The previous version's directory is kept
for exactly that, so nothing is downloaded or rebuilt. Once you're happy with
the new version, you can delete the old directories, and the old Go toolchain
under `/usr/local/go-<version>` on the Gatus host. `headscale` keeps the
previous `.deb` alongside the new one. `otterwiki` and pve-exporter are
pip-installed, so pinning the old version reinstalls it. NOMAD can't be
rolled back without the database dump above.

## [1.2.2] - 2026-11-16

### Fixed

- `project_nomad`: the role now supports `--check`. Its read-only API calls
  and the Calibre-Web probe run with `check_mode: false`, because the
  conditions on the write tasks are built from what they return. Before, a dry
  run failed at the first settings comparison. Writes are still skipped under
  `--check`, the wait for app installs is skipped, and the launch-URL
  rejection check ignores PUTs that check mode never made. A normal run
  behaves exactly as before.

## [1.2.1] - 2026-11-16

### Fixed

- `project_nomad`: MySQL now runs with `--skip-log-bin`. MySQL 8 keeps binary
  logs by default and only expires them when it rotates to a new file, so
  NOMAD's content imports (the drug-label dataset) built up about 6 GB of
  binlog that nothing reads. That filled a 16G rootfs and stalled every
  database write. Existing binlog files are not deleted. On a host that is
  already deployed, run `PURGE BINARY LOGS BEFORE NOW()` before the upgrade.

## [1.2.0] - 2026-09-29

### Added

- `actualbudget` role: the Actual Budget sync server, which also serves the web
  UI. It installs the pinned `@actual-app/sync-server` from npm into a versioned
  directory on NodeSource Node.js 22 and runs it under systemd. The server
  password is set once through Actual's bootstrap API, so the fresh server is
  never left open for anyone to claim, and after that the role never changes
  it. The examples add a `budget` Caddy site (the UI only loads over HTTPS), a
  Gatus check, a Homepage tile and a backup path.
  - Optional OpenID login, configured through Actual's own environment
    variables. It is switched on only after the password exists. Switching it
    off is reconciled too, through Actual's `/openid/disable`, which deletes
    OpenID users; the README spells this out. The public hostname is derived
    from the Caddy host's `caddy_base_domain`.
  - Optional bank-sync credentials (`actualbudget_bank_sync_secrets`), passed
    through by Actual's own secret names and set only if missing, so a key
    rotated in the UI is never undone.

- `project_nomad_app_urls`: launch-URL overrides for NOMAD's content apps, set
  through the admin's `custom-url` API, so each app's "Open" button can point
  at a Caddy hostname rather than `<host>:<port>`. Declared apps are
  reconciled every run; `""` restores NOMAD's default link. The README lists
  the default app ports for the Caddy upstreams, and the examples add `nomad`,
  `kiwix` and `cyberchef` sites.
- `project_nomad_map_regions`: map packs for any country or continent, cut
  from Protomaps' global build through NOMAD's extract API. The curated
  collections only cover US regions. Only ever added: the role mirrors NOMAD's
  file naming and skips a pack already on disk or still extracting, from any
  build date, and retries one whose extraction failed.
- Calibre-Web's first run is automated. It is pointed at the Calibre library
  NOMAD seeds in `/books`, then restarted through NOMAD's API, since it reads
  the path only at startup. With `project_nomad_calibreweb_admin_user` and
  `_password` set, the factory `admin`/`admin123` login is replaced too. Both
  happen once, only while still unconfigured, so later changes in Calibre-Web
  stick.

### Fixed

- `homepage` reran the NodeSource setup script on every run. The script now
  writes `nodesource.sources`, not the `nodesource.list` its `creates:` guard
  checked for.

## [1.1.0] - 2026-09-29

### Added

- `project_nomad` role: Project NOMAD, the offline knowledge server, with its
  admin image pinned and its secrets from the inventory. It installs Docker
  Engine in the LXC — NOMAD's admin starts every content app as a container, so
  there is no native install — and needs `keyctl` on the container. Its
  settings, apps, Wikipedia edition, curated content and map collections are
  declared in the inventory and applied through NOMAD's API: settings are
  reconciled every run, apps and content only ever added. The AI Assistant
  stays off unless `nomad_ollama` is listed. Adds a dependency on
  `community.docker`.
- Molecule tests, run in CI on every push. `contracts` asserts the inventory
  contract on the controller in seconds — guarded defaults collapsing to empty
  on an inventory without the group they read, deriving correctly when it is
  present, the Prometheus and Homepage templates rendering valid config either
  way, and each preflight assertion failing with a message naming the variable.
  `default` converges `node_exporter`, `unattended_upgrades`, `mosquitto` and
  `backup` into a systemd container, checks idempotence, and asserts the end
  state.

### Changed

- The preflight assertions now reject a variable that is declared but left
  empty, not only one that is undefined. `node_exporter_textfile_dir: ""` used
  to pass `is defined` and fail later inside the role.

## [1.0.0] - 2026-09-05

First public release. The roles come from a running homelab and are used daily,
but nothing in them encodes that homelab: every address, domain, credential and
service list is a variable you supply from your own inventory.

### Added

- Platform roles: `proxmox_node`, `proxmox`, `unattended_upgrades`, `opnsense`
- Networking roles: `caddy`, `headscale`
- Observability roles: `node_exporter`, `prometheus`, `loki`, `alloy`,
  `grafana`, `gatus`, `monitoring_trmnl`
- Service roles: `homepage`, `homeassistant`, `mosquitto`, `jellyfin`,
  `otterwiki`, `backup`
- A reusable Terraform module for a single Proxmox LXC at
  `terraform/modules/lxc`, consumed by the `proxmox` role's workflow
- A `README.md` for every role: what it does, what it needs, an example play,
  and the operational detail that isn't obvious from the tasks
- Documentation: [getting started](docs/getting-started.md), the
  [inventory contract](docs/inventory.md), the
  [Terraform root-module contract](docs/terraform.md), the
  [Proxmox host](docs/proxmox-node.md) seed, and
  [OPNsense](docs/opnsense.md) bootstrap, metrics plugins and log pipeline
- [`examples/`](examples/) — a complete consumer repository: inventory,
  `group_vars` for every group, one playbook per service, `site.yml` in
  dependency order, and a working Terraform root module
- Preflight assertions in `alloy`, `gatus`, `headscale`, `node_exporter`,
  `opnsense` and `proxmox` for the variables that cannot have role defaults
  because another role reads them via `hostvars`. A missing one fails at the
  start of the run with an instruction, rather than as an undefined-variable
  error partway through. Variables that *can* have defaults but have no safe
  value use `undef(hint=...)`, which is why `meta/runtime.yml` requires
  ansible-core >= 2.15
