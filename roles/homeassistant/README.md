# homelab.core.homeassistant

Home Assistant Core in a Python venv, with optional FoxESS Modbus and Hildebrand
Glow integrations and Energy dashboard wiring.

With no overrides the role installs HA and starts it; the rest of onboarding
happens in the browser at `:8123`. Everything below is opt-in.

## FoxESS Modbus (solar inverter)

`homeassistant_foxess_enabled: true` installs the custom component. It reads the
inverter directly over Modbus — no cloud — so it is a config-flow integration
with no YAML package and **no deploy-time secrets**. After the deploy, add
"FoxESS - Modbus" in the HA UI and enter the connection: for a Modbus TCP
adapter, the inverter's IP, port 502, and the slave/Device ID (default 247, set
on the inverter under Settings > Communication > RS485).

## Hildebrand Glow — two mutually exclusive routes

**Cloud (DCC / Bright API)** — `homeassistant_glow_dcc_enabled: true`. UK SMETS
meter data pulled from the DCC. No hardware, but roughly 30 minutes delayed
(half-hourly DCC data), not real-time. Configure it in the UI afterwards, or
have Ansible drive HA's config-flow REST API so a rebuilt HA reconfigures
itself:

```yaml
homeassistant_glow_dcc_autoconfigure: true
homeassistant_glow_dcc_username: !vault | ...
homeassistant_glow_dcc_password: !vault | ...
homeassistant_api_token: !vault | ...     # admin long-lived token
```

The integration sets no `unique_id`, so its flow is not idempotent — the role
checks for an existing entry and only creates one when none exists.

**Local MQTT (Glow IHD/CAD stick)** — near real-time. Enable the broker with
`mosquitto_enabled` in `group_vars/mosquitto`, then:

```yaml
homeassistant_glow_mqtt_enabled: true
homeassistant_glow_mqtt_device_id: "<12-hex MAC from the device's topic path>"
```

The role sets up HA's MQTT integration from the mosquitto credentials, templates
the Glow sensor package, and wires the sensors in. Set
`homeassistant_glow_mqtt_gas: false` for an electricity-only supply.

`mosquitto_enabled` is the master switch for the pair: true removes the DCC
integration automatically; false purges the broker so the two can never run at
once.

## Energy dashboard

Either route can wire its sensors into HA's Energy dashboard
(`*_energy_dashboard`, on by default) — grid source for electricity, gas source
for gas, with the unit-rate sensors as the price so HA computes cost.

This is **non-destructive**: a source is added only when none of that type
already exists.

## Example

```yaml
- name: Install and start Home Assistant
  hosts: homeassistant
  pre_tasks:
    - name: Wait for connection
      ansible.builtin.wait_for_connection:
        timeout: 300
  roles:
    - homelab.core.homeassistant
```

Run it **after** the mosquitto role: HA validates its MQTT config entry by
connecting to the broker, so the broker must already be up.
