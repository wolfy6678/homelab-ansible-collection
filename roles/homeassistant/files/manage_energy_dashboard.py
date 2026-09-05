#!/usr/bin/env python3
"""Manage Home Assistant Energy-dashboard sources for the Glow meter (DCC or MQTT).

Energy prefs have no REST endpoint, so this talks to the WebSocket API. Run it with
the Home Assistant venv interpreter (which provides aiohttp).

Environment:
  HASS_URL            base URL, default http://localhost:8123
  HASS_TOKEN          an admin long-lived access token (energy/save_prefs is admin)
  ACTION              add | remove   (default add)
  DISCOVER_PLATFORM   optional integration platform to discover the meter sensors
                      from (e.g. hildebrandglow_dcc), classified by entity_id
                      suffix usage_today/cost_today and electricity/gas. Used for
                      the DCC route and for removing its sources before teardown.
  When not discovering, pass entity ids explicitly (the MQTT route):
    STAT_ELEC_FROM, STAT_ELEC_COST, ELEC_PRICE_ENTITY
    STAT_GAS_FROM,  STAT_GAS_COST,  GAS_PRICE_ENTITY
  (stat_cost is a running-cost sensor; *_PRICE_ENTITY is a unit-rate entity used as
  entity_energy_price so HA computes cost = consumption x price.)

add:    ensure a grid (electricity) and/or gas source exist — non-destructive, only
        added when no source of that type is present. Exits 3 (NOTREADY) when a
        declared consumption entity is not registered yet, so the caller can retry.
remove: drop any grid/gas source whose stat_energy_from matches the resolved
        electricity/gas consumption entity. Idempotent.

Prints one status line (CHANGED:/OK:) and exits 0 on success; 3 = NOTREADY; 1 = error.
"""

from __future__ import annotations

import asyncio
import os
import sys

import aiohttp


class WSError(Exception):
    """A WebSocket command returned an error or the socket closed early."""


async def ws_command(ws: aiohttp.ClientWebSocketResponse, msg_id: int, payload: dict):
    """Send one command and return the matching result message."""
    await ws.send_json({"id": msg_id, **payload})
    async for msg in ws:
        if msg.type is not aiohttp.WSMsgType.TEXT:
            continue
        data = msg.json()
        if data.get("id") == msg_id and data.get("type") == "result":
            return data
    raise WSError("WebSocket closed before a result was received")


def discover(entities: list[dict], platform: str) -> dict[str, str]:
    """Map elec_from/elec_cost/gas_from/gas_cost from an integration's entities."""
    out: dict[str, str] = {}
    for ent in entities:
        if ent.get("platform") != platform or ent.get("disabled_by") is not None:
            continue
        eid = ent["entity_id"]
        supply = "elec" if "electricity" in eid else "gas" if "gas" in eid else None
        if supply is None:
            continue
        if eid.endswith("usage_today"):
            out[f"{supply}_from"] = eid
        elif eid.endswith("cost_today"):
            out[f"{supply}_cost"] = eid
    return out


def _env(name: str) -> str | None:
    return os.environ.get(name) or None


def resolve_spec(entities: list[dict]) -> dict[str, str | None]:
    """Resolve consumption/cost/price entity ids from discovery or explicit env."""
    platform = _env("DISCOVER_PLATFORM")
    if platform:
        d = discover(entities, platform)
        return {
            "elec_from": d.get("elec_from"),
            "elec_cost": d.get("elec_cost"),
            "elec_price": None,
            "gas_from": d.get("gas_from"),
            "gas_cost": d.get("gas_cost"),
            "gas_price": None,
        }
    return {
        "elec_from": _env("STAT_ELEC_FROM"),
        "elec_cost": _env("STAT_ELEC_COST"),
        "elec_price": _env("ELEC_PRICE_ENTITY"),
        "gas_from": _env("STAT_GAS_FROM"),
        "gas_cost": _env("STAT_GAS_COST"),
        "gas_price": _env("GAS_PRICE_ENTITY"),
    }


def build_source(kind: str, spec: dict[str, str | None]):
    """Build a grid (electricity) or gas energy source dict, or None if no meter."""
    stat_from = spec[f"{'elec' if kind == 'grid' else 'gas'}_from"]
    if not stat_from:
        return None
    prefix = "elec" if kind == "grid" else "gas"
    source: dict = {"type": kind, "stat_energy_from": stat_from}
    if kind == "grid":
        source["cost_adjustment_day"] = 0.0
    if spec[f"{prefix}_cost"]:
        source["stat_cost"] = spec[f"{prefix}_cost"]
    elif spec[f"{prefix}_price"]:
        source["entity_energy_price"] = spec[f"{prefix}_price"]
    return source


async def get_sources(ws, msg_id: int) -> list:
    """Current energy_sources (ERR_NOT_FOUND = dashboard never configured)."""
    prefs = await ws_command(ws, msg_id, {"type": "energy/get_prefs"})
    if prefs.get("success"):
        return list(prefs["result"].get("energy_sources", []))
    if prefs.get("error", {}).get("code") == "not_found":
        return []
    raise WSError(f"energy/get_prefs failed: {prefs.get('error')}")


async def run() -> int:
    url = os.environ.get("HASS_URL", "http://localhost:8123").rstrip("/")
    token = os.environ.get("HASS_TOKEN")
    action = os.environ.get("ACTION", "add")
    if not token:
        print("ERROR: HASS_TOKEN is not set", file=sys.stderr)
        return 1
    if action not in ("add", "remove"):
        print(f"ERROR: unknown ACTION {action!r}", file=sys.stderr)
        return 1

    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(f"{url}/api/websocket", heartbeat=30) as ws:
            hello = await ws.receive_json()
            if hello.get("type") != "auth_required":
                print(f"ERROR: unexpected greeting: {hello}", file=sys.stderr)
                return 1
            await ws.send_json({"type": "auth", "access_token": token})
            if (await ws.receive_json()).get("type") != "auth_ok":
                print("ERROR: authentication failed (check HASS_TOKEN)", file=sys.stderr)
                return 1

            msg_id = 0
            msg_id += 1
            reg = await ws_command(ws, msg_id, {"type": "config/entity_registry/list"})
            if not reg.get("success", False):
                raise WSError(f"entity_registry/list failed: {reg.get('error')}")
            entities = reg["result"]
            present = {
                e["entity_id"] for e in entities if e.get("disabled_by") is None
            }
            spec = resolve_spec(entities)

            msg_id += 1
            sources = await get_sources(ws, msg_id)

            if action == "add":
                wanted = [x for x in (spec["elec_from"], spec["gas_from"]) if x]
                if not wanted:
                    # Discovery found nothing yet → the integration's sensors
                    # haven't registered; signal retry (matches the old script).
                    # Explicit mode with no ids given = genuinely nothing to do.
                    if os.environ.get("DISCOVER_PLATFORM"):
                        print(
                            "NOTREADY: no meter sensors discovered yet for "
                            f"{os.environ['DISCOVER_PLATFORM']}",
                            file=sys.stderr,
                        )
                        return 3
                    print("OK: no consumption entities to add")
                    return 0
                missing = [x for x in wanted if x not in present]
                if missing:
                    print(f"NOTREADY: entities not registered yet: {missing}",
                          file=sys.stderr)
                    return 3
                have = {s.get("type") for s in sources}
                added = []
                for kind in ("grid", "gas"):
                    if kind in have:
                        continue
                    source = build_source(kind, spec)
                    if source:
                        sources.append(source)
                        added.append(kind)
                if not added:
                    print(f"OK: energy sources already present ({sorted(have)})")
                    return 0
                save = await ws_command(
                    ws, msg_id + 1,
                    {"type": "energy/save_prefs", "energy_sources": sources},
                )
                if not save.get("success", False):
                    raise WSError(f"energy/save_prefs failed: {save.get('error')}")
                print(f"CHANGED: added energy sources: {', '.join(added)}")
                return 0

            # action == "remove"
            targets = {x for x in (spec["elec_from"], spec["gas_from"]) if x}
            if not targets:
                print("OK: nothing to remove (no meter entities resolved)")
                return 0
            kept = [s for s in sources if s.get("stat_energy_from") not in targets]
            if len(kept) == len(sources):
                print("OK: no matching energy sources to remove")
                return 0
            save = await ws_command(
                ws, msg_id + 1,
                {"type": "energy/save_prefs", "energy_sources": kept},
            )
            if not save.get("success", False):
                raise WSError(f"energy/save_prefs failed: {save.get('error')}")
            print(f"CHANGED: removed energy sources referencing {sorted(targets)}")
            return 0


def main() -> int:
    try:
        return asyncio.run(run())
    except (WSError, aiohttp.ClientError, OSError, TypeError, ValueError) as exc:
        # TypeError/ValueError cover aiohttp's receive_json() when the handshake
        # frame is not TEXT/JSON (HA closes or errors the socket mid-upgrade) —
        # report cleanly with rc 1 instead of dumping an opaque traceback.
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
