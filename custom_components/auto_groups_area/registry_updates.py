"""Coalesce device area changes without traversing registries for metadata updates."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr


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
        action = event.data.get("action")
        if action == "update":
            changes = event.data.get("changes", {})
            if "area_id" not in changes:
                return
            self._areas.add(changes["area_id"])
        elif action == "remove":
            self._areas.add(event.data.get("device", {}).get("area_id"))
        elif action != "create":
            return

        if action != "remove" and (device_id := event.data.get("device_id")):
            device = dr.async_get(self.hass).async_get(device_id)
            if device is not None:
                self._areas.add(device.area_id)
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
