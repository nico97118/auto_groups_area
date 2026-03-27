"""Diagnostics support for Auto Groups by Area."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntry

from .const import DOMAIN, enabled_platforms

TO_REDACT: list[str] = []


def _coordinator_diagnostics(coordinator: Any) -> dict[str, Any]:
    groups = getattr(coordinator, "groups", None)
    group_count = len(groups) if isinstance(groups, dict) else None

    group_summaries: list[dict[str, Any]] = []
    if isinstance(groups, dict):
        for unique_id, group in groups.items():
            member_ids = getattr(group, "_member_entity_ids", None)
            if not isinstance(member_ids, list):
                member_ids = getattr(group, "_member_entity_ids", [])

            group_summaries.append(
                {
                    "unique_id": unique_id,
                    "entity_id": getattr(group, "entity_id", None),
                    "name": getattr(group, "name", None),
                    "members_count": len(member_ids)
                    if isinstance(member_ids, list)
                    else None,
                }
            )

    return {
        "type": f"{coordinator.__class__.__module__}.{coordinator.__class__.__name__}",
        "groups_count": group_count,
        "groups": group_summaries,
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    coordinators = []
    if isinstance(entry_data, dict):
        coordinators = entry_data.get("coordinators", [])

    return {
        "entry": {
            "entry_id": entry.entry_id,
            "title": entry.title,
            "version": entry.version,
            "minor_version": entry.minor_version,
            "source": entry.source,
        },
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "entry_options": async_redact_data(dict(entry.options), TO_REDACT),
        "enabled_platforms": [p.value for p in enabled_platforms(entry.options)],
        "runtime": {
            "coordinators": [
                _coordinator_diagnostics(coordinator)
                for coordinator in (coordinators or [])
            ],
        },
    }


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    device_reg = dr.async_get(hass)
    entity_reg = er.async_get(hass)

    entities = []
    for entity_entry in er.async_entries_for_device(entity_reg, device.id):
        entities.append(
            {
                "entity_id": entity_entry.entity_id,
                "domain": entity_entry.domain,
                "area_id": entity_entry.area_id,
                "disabled_by": entity_entry.disabled_by,
            }
        )

    device_data = device_reg.devices.get(device.id)
    device_area_id = device_data.area_id if device_data is not None else None

    # Best-effort: identify groups that currently include one of this device's entities.
    entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    coordinators = (
        entry_data.get("coordinators", []) if isinstance(entry_data, dict) else []
    )
    entity_ids = {e["entity_id"] for e in entities}
    included_by_groups: list[dict[str, Any]] = []
    for coordinator in coordinators or []:
        groups = getattr(coordinator, "groups", None)
        if not isinstance(groups, dict):
            continue
        for unique_id, group in groups.items():
            member_ids = getattr(group, "_member_entity_ids", None)
            if isinstance(member_ids, list) and entity_ids.intersection(member_ids):
                included_by_groups.append(
                    {
                        "unique_id": unique_id,
                        "entity_id": getattr(group, "entity_id", None),
                        "name": getattr(group, "name", None),
                    }
                )

    return {
        "device": {
            "id": device.id,
            "name": device.name,
            "manufacturer": device.manufacturer,
            "model": device.model,
            "area_id": device_area_id,
        },
        "entities": entities,
        "included_by_groups": included_by_groups,
    }
