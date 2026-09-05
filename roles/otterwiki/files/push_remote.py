#!/usr/bin/env python3
"""Push the wiki content repository to the configured git remote.

Runs inside the OtterWiki virtualenv using OtterWiki's own RepositoryManager
(the same code path as its auto-push), so SSH key handling matches the
running service.  Requires OTTERWIKI_SETTINGS with GIT_REMOTE_PUSH_*
configured.  Prints "Everything up-to-date" (without pushing) when the
remote already has the local HEAD — Ansible keys changed_when off this.
"""

import sys
import time

from otterwiki.server import app, storage
from otterwiki.repomgmt import RepositoryManager

with app.app_context():
    if not app.config.get("GIT_REMOTE_PUSH_ENABLED"):
        print("GIT_REMOTE_PUSH_ENABLED is not set", file=sys.stderr)
        sys.exit(1)
    remote_url = app.config.get("GIT_REMOTE_PUSH_URL")
    private_key = app.config.get("GIT_REMOTE_PUSH_PRIVATE_KEY") or None
    manager = RepositoryManager(storage)

    # On a first-run race the content repo can have its working tree populated
    # (home.md) but zero commits; head.commit then raises ValueError. Nothing to
    # push yet — the role's repository.yml recovery commits it on the next pass.
    if not storage.repo.head.is_valid():
        print("Local repository has no commits yet; nothing to push")
        sys.exit(0)

    branch = storage.repo.active_branch.name
    local_sha = storage.repo.head.commit.hexsha

    # git prints "Everything up-to-date" to stderr, which the push helper
    # discards — compare refs ourselves so the no-op case is detectable and the
    # task doesn't report "changed" on every run. Retry a few times so a
    # transient SSH/agent hiccup doesn't silently lose that detection and make a
    # genuine no-op look changed. Uses the manager's (private) SSH helpers so the
    # deploy key applies; fine while otterwiki_version stays pinned.
    remote_ref = ""
    for attempt in range(3):
        ssh_env = manager._setup_ssh_environment(private_key)
        try:
            remote_ref = storage.repo.git.ls_remote(
                remote_url, f"refs/heads/{branch}"
            )
            break
        except Exception:
            # unreachable remote / bad credentials / transient hiccup — on the
            # last attempt fall through to the push, which reports it cleanly
            remote_ref = ""
        finally:
            manager._restore_ssh_environment(*ssh_env)
        if attempt < 2:
            time.sleep(1)
    if remote_ref.split("\t")[0] == local_sha:
        print("Everything up-to-date")
        sys.exit(0)

    success, output = manager.push_to_remote(remote_url, private_key)
    print(output)
    sys.exit(0 if success else 1)
