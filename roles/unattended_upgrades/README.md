# homelab.core.unattended_upgrades

Automatic security patching on every host. Installs `unattended-upgrades`,
enables the periodic timers, and sets the reboot behaviour.

Debian's default origins already scope this to the security suite, so the role
adds no origin patterns of its own — it configures the machinery and gets out of
the way.

## Variables

| Variable | Default | |
| --- | --- | --- |
| `unattended_upgrades_auto_reboot` | `false` | A kernel update that needs a reboot waits for your next maintenance window rather than bouncing a service at 04:00. |
| `unattended_upgrades_reboot_time` | `"04:00"` | Only used when auto-reboot is on. |
| `unattended_upgrades_mail` | `""` | Address for failure reports. Needs a working MTA on the host. |

## Example

```yaml
- name: Configure automatic security upgrades
  hosts: lxc
  roles:
    - homelab.core.unattended_upgrades
```

Run it early — right after provisioning — so containers are patched from the
moment they exist.
