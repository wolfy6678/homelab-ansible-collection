# Changelog

All notable changes to this collection are documented here. This project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- A `truenas` role, for a baremetal TrueNAS storage server. Manages datasets,
  NFS/SMB exports, service accounts, the restic backup target, and the
  snapshot/scrub/S.M.A.R.T./alert schedules — a thin declarative slice, like
  the `opnsense` role; the pool and everything else done at install time stay
  in the installer. Driven through `midclt` over SSH rather than the REST API,
  which is deprecated in 25.10 and slated for removal in TrueNAS 26; its
  WebSocket replacement is not something a core Ansible module can speak.
  Wires into three existing roles: `backup` derives its restic repository URL
  from the NAS host, `prometheus` gains a `truenas` scrape job, and the NFS
  export's allowed hosts are derived from the `proxmox` and `jellyfin` groups.
  See `docs/truenas.md`.
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
- `backup_restic_repository` is derived from the `truenas` inventory group when
  there is one, rather than always being hand-written. Setting it explicitly
  still wins, and an inventory with no `truenas` group is unaffected — the
  `undef()` hint now mentions both routes.
- The `ansible-lint` CI job installs `community.docker`. Lint runs over the
  whole repository, so it covers the molecule scenarios under `extensions/`,
  which call `community.docker.docker_container`.

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
