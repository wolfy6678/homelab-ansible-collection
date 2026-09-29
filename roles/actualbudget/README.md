# homelab.core.actualbudget

[Actual Budget](https://actualbudget.org) — a local-first envelope budgeting
app — installed natively: the pinned `@actual-app/sync-server` npm package
(which also serves the web UI) in a versioned directory under
`/opt/actualbudget`, run by systemd as an unprivileged user.

## Requirements

- A Debian-family LXC with outbound HTTPS (NodeSource and the npm registry).
- **HTTPS in front of it.** The web client uses `SharedArrayBuffer`, which
  browsers only allow in a secure context — over plain `http://<ip>:5006` the
  UI refuses to load. Put it behind the `caddy` role (see the example below);
  `http://localhost` is the only plain-HTTP origin that works.

## Required variables

- `actualbudget_server_password` — fails with a hint if unset. It is set
  **once**, through Actual's bootstrap API, the first time the role runs
  against a fresh server. After that the role never changes it (but see
  [Changing the password in the UI](#changing-the-password-in-the-ui)).

  This password unlocks the server. It is *not* a budget's end-to-end
  encryption key: you set that per budget in the client, and the server never
  sees it.

Setting the password at deploy time is deliberate. Until a fresh server has a
password, anyone who can reach the UI can set one and take the server.

## OpenID (optional)

Set `actualbudget_openid_enabled: true` with `actualbudget_openid_discovery_url`,
`_client_id` and `_client_secret`. Register
`<actualbudget_openid_server_hostname>/openid/callback` as a redirect URI with
your provider. The hostname defaults to
`https://<actualbudget_caddy_site_name>.<caddy_base_domain>` (the site name is
`budget` unless you set it) when there is a `caddy` group; otherwise set
`actualbudget_openid_server_hostname` yourself. Set `actualbudget_openid_enforce: true` to take
the password option off the login screen.

- **The first user to log in through OpenID becomes the server owner, and
  that can't be changed later.** Log in yourself right after the run that
  enables it.
- The settings go in a root-only `/etc/actualbudget/openid.env`, written only
  *after* the password has been set. A server that starts with OpenID
  configured sets itself up for OpenID and never gets a password. Written this
  way, the password stays in place as an inactive login method, which the role
  needs for its API steps.
- "Enforce" only hides the password option. `/account/login` still accepts
  the password, so keep it strong.
- Setting `actualbudget_openid_enabled` back to `false` removes the env file
  and calls Actual's own "switch to password" action. **That deletes every
  OpenID user and their budget access grants.** Don't just delete the env file
  by hand: OpenID would stay active with no config, and nobody could log in
  through the UI.

## Bank sync credentials (optional)

`actualbudget_bank_sync_secrets` takes Actual's server-wide bank-sync secrets
as `{name: value}`, passed through verbatim:

```yaml
actualbudget_bank_sync_secrets:
  gocardless_secretId: "{{ vault_actualbudget_gocardless_secret_id }}"
  gocardless_secretKey: "{{ vault_actualbudget_gocardless_secret_key }}"
```

The known names are `gocardless_secretId`/`_secretKey`,
`pluggyai_clientId`/`_clientSecret` and
`enablebanking_applicationId`/`_secretKey`. The role only sets secrets that are
missing, because Actual's API can report that a secret exists but never returns
its value. A key you rotate in the UI is never undone. To rotate one from
Ansible, delete it in the UI first. SimpleFIN doesn't fit this pattern: its
setup token works only once, and Actual exchanges it for an access key when
you first connect, so link it in the UI.

## Changing the password in the UI

This is safe as long as the role never needs to log in. Setting bank-sync
secrets and switching OpenID off both log in with
`actualbudget_server_password`. After a UI change, those runs fail at login
with a message saying so, until you update the vault to match.

## Upgrades

Bump `actualbudget_version`. The new version installs into its own directory,
the `actual-server` symlink moves to it, and the service restarts. Database
migrations run when the server starts. The old version's directory is left in
place, so rolling back means setting the pin back to the old version.

## Data and backups

Everything lives in `actualbudget_data_dir` (`/var/lib/actualbudget`):
`server-files/` holds the account database, and `user-files/` holds every
synced budget. Add that path to `backup_default_paths`. Clients also keep a
full local copy of each budget, so a lost server is recoverable from any
client. A backup avoids depending on that.

## Upload limits

Actual caps sync uploads at 20 MB (50 MB for encrypted budgets). A long
history with attachments can pass that, and clients then report an unclear
sync error. Raise `actualbudget_upload_*_limit_mb` if that happens.

## Example

```yaml
- name: Install and start Actual Budget
  hosts: actualbudget
  roles:
    - homelab.core.actualbudget
```

With a clean hostname from the `caddy` role:

```yaml
# group_vars/caddy/main.yml
caddy_sites:
  - name: budget
    upstream: "{{ hostvars[groups['actualbudget'][0]].ansible_host }}:5006"
```

Health check for `gatus` (`/health` returns `{"status":"UP"}`):

```yaml
gatus_endpoints:
  - name: actualbudget
    url: "http://{{ hostvars[groups['actualbudget'][0]].ansible_host }}:5006/health"
```
