"""Coalesce device area changes without traversing registries for metadata updates."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from typing import Protocol

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN


class AreaGroupMembership(Protocol):
    """Membership snapshot exposed by each area's group entity."""

    _area_id: str
    _member_entity_ids: list[str]


class DeviceAreaUpdates:
    """Batch affected areas for one coordinator on the event loop."""

    def __init__(
        self,
        hass: HomeAssistant,
        update: Callable[[set[str | None]], Awaitable[None]],
    ) -> None:
        self.hass = hass
        self._update = update
        self._areas: set[str | None] = set()
        self._task: asyncio.Task | None = None
        self._stopped = False

    @callback
    def handle(self, event: Event) -> None:
        """Read HA's changes/removed-device payload; ignore unrelated updates."""
        if self._stopped:
            return
        areas: set[str | None] = set()
        action = event.data.get("action")
        if action == "update":
            changes = event.data.get("changes", {})
            if "area_id" not in changes:
                return
            areas.add(changes["area_id"])
        elif action == "remove":
            areas.add(event.data.get("device", {}).get("area_id"))
        elif action != "create":
            return

        if action != "remove" and (device_id := event.data.get("device_id")):
            device = dr.async_get(self.hass).async_get(device_id)
            if device is not None:
                areas.add(device.area_id)
        self.schedule(areas)

    @callback
    def schedule(self, areas: set[str | None]) -> None:
        """Queue areas for a shared, bounded refresh task."""
        if self._stopped:
            return
        self._areas.update(areas)
        self._areas.discard(None)
        if self._areas and self._task is None:
            self._task = self.hass.async_create_task(self._async_flush())

    async def _async_flush(self) -> None:
        try:
            while self._areas:
                # Let already queued registry events join this batch. Yield between
                # batches too, so discovery cannot monopolize the event loop.
                await asyncio.sleep(0)
                areas, self._areas = self._areas, set()
                await self._update(areas)
        finally:
            self._task = None

    async def async_stop(self) -> None:
        """Cancel pending work before the coordinator is unloaded."""
        self._stopped = True
        self._areas.clear()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass


@callback
def entity_event_areas(
    hass: HomeAssistant,
    event: Event,
    *,
    domain: str,
    include_device_area: bool,
    groups: Iterable[AreaGroupMembership],
) -> set[str | None]:
    """Resolve old/current areas without relying on nonexistent event fields.

    Removal events contain only the entity ID. Existing memberships retain the
    areas that must be refreshed, including for entities renamed or deleted in
    the same event-loop turn. Preserve the platforms' existing membership rules.
    """
    entity_id = event.data.get("entity_id", "")
    if not entity_id.startswith(f"{domain}."):
        return set()
    action = event.data.get("action")
    changes = event.data.get("changes", {})
    old_entity_id = event.data.get("old_entity_id", entity_id)
    if action == "update" and not (
        {"area_id", "device_id", "disabled_by", "device_class", "original_device_class"}
        & changes.keys()
        or old_entity_id != entity_id
    ):
        return set()
    if action not in {"create", "update", "remove"}:
        return set()

    entry = er.async_get(hass).async_get(entity_id)
    # Our own group registrations/state writes must not feed back into rebuilds.
    if entry is not None and entry.platform == DOMAIN:
        return set()
    areas: set[str | None] = {
        group._area_id
        for group in groups
        if entity_id in group._member_entity_ids
        or old_entity_id in group._member_entity_ids
    }
    if action == "remove" or entry is None:
        return areas

    areas.add(entry.area_id)
    areas.add(changes.get("area_id", entry.area_id))
    if include_device_area:
        registry = dr.async_get(hass)
        for device_id in {entry.device_id, changes.get("device_id", entry.device_id)}:
            if device_id and (device := registry.async_get(device_id)) is not None:
                areas.add(device.area_id)
    areas.discard(None)
    return areas
