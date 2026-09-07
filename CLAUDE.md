# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`homelab.core` — an Ansible **collection** of roles (no modules, no plugins) for
building a self-hosted homelab on Proxmox LXCs, plus one reusable Terraform
module. Targets are Debian-family/systemd; installs are native (tarball/source +
systemd unit), not containers.

The collection is **site-agnostic**: no inventory or group_vars ship here, and
no role default encodes a real address, domain, or credential. Consumers supply
all of that. `examples/` holds a complete, generic consumer repository
(`192.168.50.0/24`, `example.com`) — keep it that way, and keep new defaults
generic; anything site-specific belongs in the consumer's `group_vars`.

## Commands

Static validation plus two Molecule scenarios. CI
(`.github/workflows/ci.yml`) runs these:

```bash
# Dependencies ansible-lint needs on disk to resolve the modules roles call
ansible-galaxy collection install community.general community.proxmox oxlorg.opnsense

ansible-lint                       # production profile, from the repo root (~4 min)
ansible-lint roles/prometheus      # lint a single role
ansible-galaxy collection build --output-path dist   # catches galaxy.yml errors

terraform fmt -check -recursive terraform examples/terraform
cd terraform/modules/lxc && terraform init -backend=false && terraform validate

.github/scripts/check-version.sh   # galaxy.yml version == every documented pin

molecule test -s contracts         # seconds, no container
molecule test -s default           # builds a systemd container, ~3 min
molecule test --all                # both
```

Molecule needs `molecule`, the `docker` Python SDK and the `community.docker`
collection, and the collection itself installed (`ansible-galaxy collection
install . --force`) because the scenarios address roles by FQCN.

The two scenarios cover different things and both matter:

- **`contracts`** runs entirely on the controller. It asserts that every
  cross-group default collapses to empty on an inventory lacking that group,
  that the same defaults derive correctly once the groups exist, that
  `prometheus.yml.j2` renders valid YAML in both cases, that
  `services.yaml.j2` passes an unknown key through verbatim, and that the
  preflight assertions fail with a message naming the variable. Plays run in
  order and the bare-inventory play must come first — later plays `add_host`,
  which changes `groups` for the rest of the run. This is where the
  regressions actually happen, and it costs seconds.
- **`default`** converges `node_exporter`, `unattended_upgrades`, `mosquitto`
  and `backup` into a systemd container, checks idempotence, then asserts the
  end state: the binary symlink points into the versioned install dir, the
  units are enabled and running, `/metrics` serves the textfile collector, the
  restic repository was really initialised, and the secret-bearing files have
  the modes they should. Between them those four roles exercise every step of
  the service-install pattern.

Plus two checks that are awkward to run by hand and live in the workflow:

- **Artefact inspection** — asserts `build_ignore` kept `.terraform`, tfstate
  and tfvars out of the built tarball and that `roles/`, `docs/`, `examples/`
  and `terraform/modules/lxc/` went in. `build_ignore` patterns are fnmatched
  against the path *relative to the collection root* and `*` spans `/`, so a
  bare `.terraform` matches only a root-level one — this check exists because
  that exact mistake shipped a 40 MB provider binary.
- **`examples/terraform` validation** — it sources the container module from a
  git tag that doesn't resolve on an unmerged branch, so CI copies it to
  `.ci-example-root/` *inside the checkout* (a Terraform local module source
  must be relative, so a `/tmp` copy can't reach the module) with `source`
  repointed at `../terraform/modules/lxc`, then inits and validates.

Pushing to `main` tags and releases when — and only when — `galaxy.yml` names a
version with no tag yet. See the Releases section of `CONTRIBUTING.md`.

To exercise a template change without a homelab, render it against a fake
inventory: a `connection: local` play with `hosts:` set to a made-up host, the
role's variables inlined, and an `ansible.builtin.template` task. This is how
the homepage, gatus and prometheus templates were verified against both a full
and a near-empty inventory.

## Architecture

### Inventory is the source of truth

Roles derive their config from inventory groups rather than duplicating host
lists — adding a host to a group wires it into the rest of the stack.
`docs/inventory.md` is the contract; the essentials:

- `prometheus` builds scrape jobs from `groups['lxc']` and `groups['proxmox']`,
  plus jobs guarded on `groups['gatus']`, `groups['headscale']`, and so on.
- `gatus` derives certificate checks, and `opnsense` derives Unbound overrides,
  from the Caddy host's `caddy_sites`.
- `proxmox` builds the Terraform `lxcs` map from `groups['lxc']`
  (`roles/proxmox/tasks/build_lxcs.yml`), keyed on `inventory_hostname_short`
  and merged with each host's `lxc_overrides`.

Three rules follow, and all three are easy to break:

1. **Role defaults are invisible in `hostvars`.** A variable another role reads
   cross-host must live in the consumer's `group_vars`, never in
   `defaults/main.yml`. `caddy_sites`, `gatus_port`,
   `headscale_metrics_listen_addr`, the three other `headscale_fail2ban_*`
   variables and `node_exporter_textfile_dir` are all in that category.
2. **Those variables get a preflight `assert`** at the top of the owning role's
   `tasks/main.yml`, so a missing one fails with an instruction rather than an
   undefined-variable error mid-run. Add one whenever you add a variable of this
   kind — it is the `undef(hint=...)` pattern's stand-in where defaults can't
   reach.
3. **Guard every cross-group reference** with `groups['x'] | default([])`, and
   guard the surrounding template block too, so a consumer inventory lacking
   that group renders a smaller valid config rather than erroring.

Ports and similar values are read from the owning role's host via `hostvars`
(e.g. `prometheus_gatus_port` reads `hostvars[groups['gatus'][0]].gatus_port`)
rather than mirrored into a second default that can drift.

### Service lists are data, not template code

Which services a user runs is theirs to declare, so the roles that would
otherwise hard-code a list ship empty and render whatever they are given:

- `homepage_services` — `services.yaml.j2` passes every key except `name`
  through to Homepage verbatim, so any service option or widget works with no
  role change. The `layout` block in `settings.yaml.j2` is *derived* from the
  group names so the two cannot drift.
- `gatus_endpoints` — `[]`; the derived `certificates` group is separate.
- `backup_default_paths` — `{}`.

Don't reintroduce a hard-coded service into these. Put it in
`examples/group_vars/` and the role README instead.

### Required variables

Variables with no safe default are declared in `defaults/main.yml` as
`{{ undef(hint='Set <var> to ... (vault-encrypt it)') }}`, so a run fails
immediately with an actionable message. This is why `meta/runtime.yml` requires
ansible-core >= 2.15. Follow the pattern; don't substitute an empty-string
default plus an `assert`.

### Service install pattern

Most service roles follow the same shape — copy it when adding one:

- system user (`system: true`, `create_home: false`)
- versioned install dir `/opt/<svc>/<version>`, binary symlinked into
  `/usr/local/bin` with `force: true`
- download via `unarchive`/`get_url` with `creates:` for idempotence (upgrades
  happen by bumping the pinned `<svc>_version`, which changes the path)
- config and systemd unit from `templates/`, each `notify:`-ing a single
  `Restart <svc>` handler (`daemon_reload: true`)

Multi-stage roles split into `tasks/install.yml`, `server.yml`, etc., pulled in
with `import_tasks` from `tasks/main.yml` (see `headscale`, `homeassistant`,
`otterwiki`).

### Create-only where humans edit

Admin users, first-run wizards, Proxmox backup jobs and Grafana state are
created if absent and never reconciled afterwards, so a password changed in a
web UI doesn't need mirroring back into a vault. Jellyfin's wizard probes
whether setup is still open before acting; OtterWiki's admin is created once.
Preserve this when touching those roles.

### Secrets

No credential is embedded anywhere. Tasks passing vaulted values to modules that
don't mask them set `no_log: true` (see `roles/proxmox/tasks/main.yml`).

### Terraform

`terraform/modules/lxc` is a reusable single-LXC module, consumed by git source
ref. The **root** module is deliberately not shipped — provider credentials, the
`lxcs` map and the state backend are site-specific — but `examples/terraform`
is a complete working one. The `proxmox` role runs `community.general.terraform`
against the consumer's root module at `proxmox_terraform_project_path`
(resolved relative to the playbook run dir) and reads back an `lxc_vmids`
output. See `docs/terraform.md` for the contract in both directions.

## Documentation layout

| | |
| --- | --- |
| `docs/getting-started.md` | End-to-end walkthrough |
| `docs/inventory.md` | Groups, host vars, the must-be-in-inventory variables |
| `docs/terraform.md` | Root-module contract |
| `docs/proxmox-node.md` | Manual PVE seed + what the role takes over |
| `docs/opnsense.md` | Firewall bootstrap, metrics plugins, IDS log pipeline |
| `roles/<name>/README.md` | Per-role: purpose, requirements, required vars, example |
| `roles/<name>/defaults/main.yml` | Every tunable, and *why* it is what it is |
| `examples/` | A complete consumer repo, mirrored by the docs |

Cross-references must stay inside this repository. The roles were extracted from
a private repo and once carried comments pointing at files that only exist
there (`site.yml`, `playbook-*.yml`, its `docs/*.md`); those are all repointed
now, so don't add new ones.

When you change a role's variables, the change lands in **four** places: the
default's comment, the role README, `examples/group_vars/`, and — if it alters
the contract — `docs/inventory.md`.

## Conventions

- Explain *why* a default is what it is in `defaults/main.yml`. The existing
  comments carry a lot of hard-won operational detail (DNS-01 propagation
  races, pve-exporter DNS churn, Prometheus route-prefix side effects, the
  fail2ban rule that would ban the Gatus prober). Keep that density.
- Variables are prefixed with the role name. `terraform_*` variables are the
  consumer-supplied Terraform inputs; `lxc_*` are per-host inventory vars.
- There are no `meta/main.yml` or `argument_specs.yml` files, and no task tags.
- Version bumps go in `galaxy.yml` and `CHANGELOG.md` (semver); tags are
  `vX.Y.Z`, and the README, `docs/`, `examples/requirements.yml` and the
  Terraform `source` refs all pin to them — bump them together, and run
  `.github/scripts/check-version.sh`, which is what CI gates the tag on. Tags
  are created by CI, never by hand.
- Add anything that shouldn't ship in the artefact to `build_ignore` in
  `galaxy.yml`.
