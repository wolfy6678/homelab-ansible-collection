# homelab.core.mosquitto

Mosquitto MQTT broker. Typically co-located on the Home Assistant host, for
devices that publish locally — a Hildebrand Glow IHD/CAD, say, which pushes
near real-time meter data that Home Assistant subscribes to at localhost while
the device connects to the host's LAN IP.

## Enabling

The whole role is a **no-op** until `mosquitto_enabled: true`. Setting it back
to false **purges** the broker.

Declare that switch in `group_vars/mosquitto` and nowhere else. The Home
Assistant host is usually in both the `mosquitto` and `homeassistant` groups,
and a copy in `group_vars/homeassistant` would win on group-depth precedence and
silently make the switch inert.

## Credentials

`allow_anonymous` is off, so a password is required once enabled;
`mosquitto_password` fails with a hint until set.

Put `mosquitto_username` and `mosquitto_password` in **`group_vars/all`**, not
`group_vars/mosquitto`: they are a single shared account used by Home
Assistant's MQTT integration, the device itself, and any other client you add —
including hosts that are not in the `mosquitto` group and so cannot read that
group's vars.

## Example

```yaml
- name: Install and start Mosquitto
  hosts: mosquitto
  roles:
    - homelab.core.mosquitto
```

Run it before Home Assistant.
