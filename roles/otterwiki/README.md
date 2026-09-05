# homelab.core.otterwiki

[OtterWiki](https://otterwiki.com) — a git-backed markdown wiki — in a venv,
with optional push mirroring to an external git remote.

Every page edit is a git commit in `otterwiki_repository_dir`, so the wiki's
history is a real repository you can clone.

## Required variables

Both fail with a hint if unset:

- `otterwiki_admin_password` — the admin user is created **once** and never
  modified afterwards, so changing it in the UI later is safe.
- `otterwiki_secret_key` — signs the session cookie. It must stay stable across
  runs or every session is invalidated. Generate one with:

  ```bash
  python3 -c "import secrets; print(secrets.token_hex(32))"
  ```

`ADMIN_USER_EMAIL` is pinned to `otterwiki_admin_email`, so no other
registration can ever become admin.

## Permissions

`otterwiki_read_access`, `otterwiki_write_access` and
`otterwiki_attachment_access` take `ANONYMOUS`, `REGISTERED` or `APPROVED`.

With no SMTP configured, email confirmation is disabled and registrations are
auto-approved — so `REGISTERED` effectively means "anyone on the LAN who signs
up".

## Push mirroring

Set `otterwiki_git_push_url` to mirror the wiki content to an external remote,
e.g. a private GitHub repo. OtterWiki then auto-pushes after every wiki change,
and the role pushes at deploy time — which also validates the credentials,
since auto-push failures otherwise only surface in the service log.

Use an SSH URL with `otterwiki_git_push_private_key` (the vault-encrypted
private half of a deploy key with write access). A token-in-URL HTTPS remote
also works, but OtterWiki logs the URL on every push.

## Example

```yaml
- name: Install and start OtterWiki
  hosts: otterwiki
  roles:
    - homelab.core.otterwiki
```

## Note

Settings saved in the admin UI's Repository management page are stored in the
database and **override** these file-based values.
