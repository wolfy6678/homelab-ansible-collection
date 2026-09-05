# Contributing

Issues and pull requests are welcome. The collection is deliberately
site-agnostic, so the bar for a change is that it works on an inventory that
looks nothing like the one it was developed against.

## Running the checks

CI is offline static validation — there is no test suite and no Molecule, so
these are the checks, and they are the same ones the workflow runs:

```bash
# ansible-lint needs these on disk to resolve the modules the roles call
ansible-galaxy collection install community.general community.proxmox oxlorg.opnsense

ansible-lint                                         # production profile, from the repo root
ansible-lint roles/prometheus                        # or a single role
ansible-galaxy collection build --output-path dist   # catches galaxy.yml errors

terraform fmt -check -recursive terraform examples/terraform
cd terraform/modules/lxc && terraform init -backend=false && terraform validate

.github/scripts/check-version.sh                     # version pins agree everywhere
```

CI additionally inspects the built artefact (that `build_ignore` kept Terraform
state, tfvars and provider binaries out, and that `roles/`, `docs/`, `examples/`
and the Terraform module went in) and validates `examples/terraform` with its
module `source` repointed at the working tree — the shipped `source` is a git
tag that cannot resolve on an unmerged branch.

To exercise a template change without a homelab, render it against a fake
inventory: a `connection: local` play with `hosts:` set to a made-up host, the
role's variables inlined, and an `ansible.builtin.template` task. Render it
twice — once against a full inventory and once against one missing the groups
your change touches.

## Releases

Pushing to `main` runs everything above and then, **only if `galaxy.yml` names a
version that isn't tagged yet**, creates the `vX.Y.Z` tag and a GitHub release
with the artefact CI just verified attached and the changelog section as its
notes. Ordinary commits find their tag already present and release nothing.

So a release is a version bump. In one commit:

1. `galaxy.yml` — the new version
2. `CHANGELOG.md` — a `## [X.Y.Z]` section (CI refuses to release without one)
3. `README.md`, `docs/`, `examples/requirements.yml` and every Terraform
   `?ref=` — all pin the new tag

`.github/scripts/check-version.sh` enforces 1–3 and is worth running before you
push; CI runs it too, and will not tag if it fails.

## What the roles must not do

- **No site-specific defaults.** No role default may encode a real address,
  domain, hostname or credential. `examples/` is generic on purpose
  (`192.168.50.0/24`, `example.com`); keep it that way.
- **No hard-coded service lists.** `caddy_sites`, `gatus_endpoints`,
  `homepage_services` and `backup_default_paths` are the consumer's data. New
  services belong in `examples/group_vars/` and the role README, not in a
  template.
- **Guard every cross-group reference** with `groups['x'] | default([])`, and
  guard the surrounding template block too, so an inventory without that group
  renders a smaller valid config instead of failing.
- **Required variables fail early.** A variable with no safe default is declared
  as `{{ undef(hint='...') }}`. One that another role reads via `hostvars`
  cannot have a role default at all — those get a preflight `assert` in the
  owning role, naming the file to put it in.

## Conventions

- Variables are prefixed with the role name.
- Explain *why* a default is what it is in `defaults/main.yml`. That is where
  the operational detail lives, and it is the most valuable part of the role.
- A variable change lands in four places: the default's comment, the role
  `README.md`, `examples/group_vars/`, and — if it changes the contract between
  roles — [`docs/inventory.md`](docs/inventory.md).
- Version bumps are semver, and tagging is automatic — see
  [Releases](#releases) above for the four files a bump has to touch.
