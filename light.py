"""Light platform for Auto Groups by Area.

Creates one light entity per area that mirrors the behavior of a "Light group" helper
created from the UI, by forwarding turn_on/turn_off to member lights and exposing
aggregated state/attributes.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import StateType

from .const import DEFAULT_DOMAINS, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Auto Groups by Area light platform."""
    coordinator = AreaLightGroupCoordinator(hass, config_entry, async_add_entities)
    entry_data = hass.data.setdefault(DOMAIN, {}).setdefault(config_entry.entry_id, {})
    entry_data.setdefault("coordinators", []).append(coordinator)
    await coordinator.async_start()


class AreaLightGroupCoordinator:
    """Coordinate area light-group creation and updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        self.hass = hass
        self.config_entry = config_entry
        self.async_add_entities = async_add_entities

        self.domains = DEFAULT_DOMAINS
        self.groups: dict[str, AreaLightGroup] = {}

        self._unsub_entity_reg: Callable[[], None] | None = None
        self._unsub_area_reg: Callable[[], None] | None = None
        self._unsub_device_reg: Callable[[], None] | None = None

    async def async_start(self) -> None:
        """Start coordinator and do initial sync."""
        self._unsub_entity_reg = self.hass.bus.async_listen(
            er.EVENT_ENTITY_REGISTRY_UPDATED, self._handle_entity_registry_updated
        )
        self._unsub_area_reg = self.hass.bus.async_listen(
            ar.EVENT_AREA_REGISTRY_UPDATED, self._handle_area_registry_updated
        )
        self._unsub_device_reg = self.hass.bus.async_listen(
            dr.EVENT_DEVICE_REGISTRY_UPDATED, self._handle_device_registry_updated
        )

        await self.async_update_all_groups()

    async def async_stop(self) -> None:
        """Stop coordinator (listeners)."""
        if self._unsub_entity_reg is not None:
            self._unsub_entity_reg()
            self._unsub_entity_reg = None
        if self._unsub_area_reg is not None:
            self._unsub_area_reg()
            self._unsub_area_reg = None
        if self._unsub_device_reg is not None:
            self._unsub_device_reg()
            self._unsub_device_reg = None

    def _normalize_name(self, name: str) -> str:
        """Normalize area name for object_id-like usage."""
        name = name.lower()
        name = re.sub(r"[^\w\s-]", "", name)
        name = re.sub(r"[-\s]+", "_", name)
        return name

    async def async_update_all_groups(self) -> None:
        """(Re)build/update all groups for all areas."""
        entity_reg = er.async_get(self.hass)
        area_reg = ar.async_get(self.hass)

        for area in area_reg.async_list_areas():
            for domain in self.domains:
                await self._async_update_group_for_area(area, domain, entity_reg)

    async def _async_update_group_for_area(
        self,
        area: ar.AreaEntry,
        domain: str,
        entity_reg: er.EntityRegistry,
    ) -> None:
        """Update the group entity for one area."""
        if domain != "light":
            return

        device_reg = dr.async_get(self.hass)
        member_entity_ids: list[str] = []

        for entry in entity_reg.entities.values():
            if not entry.entity_id.startswith("light."):
                continue
            if entry.disabled_by is not None:
                continue

            # Entity directly assigned to area
            if entry.area_id == area.id:
                member_entity_ids.append(entry.entity_id)
                continue

            # Entity inherits area from its device assignment
            if entry.device_id:
                device = device_reg.devices.get(entry.device_id)
                if device is not None and device.area_id == area.id:
                    member_entity_ids.append(entry.entity_id)

        unique_id = f"{DOMAIN}_{domain}_{area.id}"
        normalized_area_name = self._normalize_name(area.name)

        # Avoid creating empty groups. If a group already exists and becomes empty, remove it.
        if not member_entity_ids:
            existing = self.groups.pop(unique_id, None)
            if existing is not None:
                _LOGGER.info("Removing empty light group for area '%s'", area.name)
                await existing.async_remove()
            return

        if unique_id in self.groups:
            group = self.groups[unique_id]
            group.update_area(area_name=area.name, normalized_area_name=normalized_area_name)
            group.update_members(member_entity_ids)
            return

        group = AreaLightGroup(
            unique_id=unique_id,
            area_id=area.id,
            area_name=area.name,
            normalized_area_name=normalized_area_name,
            member_entity_ids=member_entity_ids,
        )
        self.groups[unique_id] = group
        self.async_add_entities([group], update_before_add=True)

        _LOGGER.info(
            "Created light group for area '%s' with %d member(s)",
            area.name,
            len(member_entity_ids),
        )

    @callback
    def _handle_entity_registry_updated(self, event: Event) -> None:
        """Handle entity registry updates."""
        entity_id: str | None = event.data.get("entity_id")
        if not entity_id:
            return

        if not any(entity_id.startswith(f"{domain}.") for domain in self.domains):
            return

        old_area_id: str | None = event.data.get("old_area_id")
        new_area_id: str | None = event.data.get("area_id")

        self.hass.async_create_task(self._async_update_areas({old_area_id, new_area_id}))

    @callback
    def _handle_area_registry_updated(self, event: Event) -> None:
        """Handle area registry updates."""
        action: str | None = event.data.get("action")
        area_id: str | None = event.data.get("area_id")

        if action in {"create", "update"} and area_id:
            self.hass.async_create_task(self._async_update_areas({area_id}))
            return

        if action == "remove" and area_id:
            self.hass.async_create_task(self._async_remove_area(area_id))

    @callback
    def _handle_device_registry_updated(self, event: Event) -> None:
        """Handle device registry updates (device moved between areas)."""
        action: str | None = event.data.get("action")
        if action not in {"create", "update", "remove"}:
            return

        old_area_id: str | None = event.data.get("old_area_id")
        new_area_id: str | None = event.data.get("area_id")

        # When a device changes area, entity registry may not change, so update both areas.
        if old_area_id or new_area_id:
            self.hass.async_create_task(self._async_update_areas({old_area_id, new_area_id}))
            return

        # Fallback: if event schema differs, do a full refresh (still cheap for typical setups).
        self.hass.async_create_task(self.async_update_all_groups())

    async def _async_update_areas(self, area_ids: set[str | None]) -> None:
        """Update groups for the given areas."""
        area_ids.discard(None)
        if not area_ids:
            return

        entity_reg = er.async_get(self.hass)
        area_reg = ar.async_get(self.hass)

        for area_id in area_ids:
            area = area_reg.async_get_area(area_id)
            if area is None:
                continue
            for domain in self.domains:
                await self._async_update_group_for_area(area, domain, entity_reg)

    async def _async_remove_area(self, area_id: str) -> None:
        """Remove group entities for an area that was deleted."""
        to_remove: list[str] = []
        for unique_id in self.groups:
            if unique_id.endswith(f"_{area_id}"):
                to_remove.append(unique_id)

        for unique_id in to_remove:
            group = self.groups.pop(unique_id)
            await group.async_remove()


class AreaLightGroup(LightEntity):
    """A light entity representing all lights in an area."""

    _attr_should_poll = False
    _attr_icon = "mdi:lightbulb-group"

    def __init__(
        self,
        *,
        unique_id: str,
        area_id: str,
        area_name: str,
        normalized_area_name: str,
        member_entity_ids: list[str],
    ) -> None:
        self._attr_unique_id = unique_id
        self._area_id = area_id
        self._area_name = area_name
        self._normalized_area_name = normalized_area_name
        self._member_entity_ids: list[str] = member_entity_ids

        # Using "Area <name>" produces entity_id like "light.area_<name>" after slugify.
        self._attr_name = f"Area {area_name}"

        self._unsub_member_state: Callable[[], None] | None = None

    async def async_added_to_hass(self) -> None:
        """Register listeners once added."""
        self._async_subscribe_to_member_state()

    async def async_will_remove_from_hass(self) -> None:
        """Clean up listeners."""
        if self._unsub_member_state is not None:
            self._unsub_member_state()
            self._unsub_member_state = None

    def update_area(self, *, area_name: str, normalized_area_name: str) -> None:
        """Update area display name."""
        self._area_name = area_name
        self._normalized_area_name = normalized_area_name
        self._attr_name = f"Area {area_name}"
        self.async_write_ha_state()

    @callback
    def update_members(self, member_entity_ids: list[str]) -> None:
        """Update group membership."""
        if member_entity_ids == self._member_entity_ids:
            return
        self._member_entity_ids = member_entity_ids
        self._async_subscribe_to_member_state()
        self.async_write_ha_state()

    @callback
    def _async_subscribe_to_member_state(self) -> None:
        """Subscribe to state changes of member entities."""
        if self._unsub_member_state is not None:
            self._unsub_member_state()
            self._unsub_member_state = None

        if not self.hass or not self._member_entity_ids:
            return

        @callback
        def _member_state_changed(_: Event) -> None:
            self.async_write_ha_state()

        self._unsub_member_state = async_track_state_change_event(
            self.hass, self._member_entity_ids, _member_state_changed
        )

    def _member_states(self) -> list[StateType]:
        states: list[StateType] = []
        for entity_id in self._member_entity_ids:
            states.append(self.hass.states.get(entity_id))
        return [s for s in states if s is not None]

    @property
    def is_on(self) -> bool:
        """Return True if any member is on."""
        for state in self._member_states():
            if state.state == "on":
                return True
        return False

    @property
    def available(self) -> bool:
        """Return True if at least one member is available."""
        states = self._member_states()
        if not states:
            return False
        return any(state.state not in {"unavailable", "unknown"} for state in states)

    def _avg_int_attr(self, attr: str) -> int | None:
        values: list[int] = []
        for state in self._member_states():
            if state.state != "on":
                continue
            value = state.attributes.get(attr)
            if isinstance(value, int):
                values.append(value)
        if not values:
            return None
        return round(sum(values) / len(values))

    def _avg_tuple2_attr(self, attr: str) -> tuple[float, float] | None:
        values: list[tuple[float, float]] = []
        for state in self._member_states():
            if state.state != "on":
                continue
            value = state.attributes.get(attr)
            if (
                isinstance(value, (list, tuple))
                and len(value) == 2
                and all(isinstance(v, (int, float)) for v in value)
            ):
                values.append((float(value[0]), float(value[1])))
        if not values:
            return None
        return (sum(v[0] for v in values) / len(values), sum(v[1] for v in values) / len(values))

    def _avg_tuple3_attr(self, attr: str) -> tuple[int, int, int] | None:
        values: list[tuple[int, int, int]] = []
        for state in self._member_states():
            if state.state != "on":
                continue
            value = state.attributes.get(attr)
            if (
                isinstance(value, (list, tuple))
                and len(value) == 3
                and all(isinstance(v, int) for v in value)
            ):
                values.append((int(value[0]), int(value[1]), int(value[2])))
        if not values:
            return None
        return (
            round(sum(v[0] for v in values) / len(values)),
            round(sum(v[1] for v in values) / len(values)),
            round(sum(v[2] for v in values) / len(values)),
        )

    @property
    def brightness(self) -> int | None:
        return self._avg_int_attr(ATTR_BRIGHTNESS)

    @property
    def hs_color(self) -> tuple[float, float] | None:
        return self._avg_tuple2_attr(ATTR_HS_COLOR)

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        return self._avg_tuple3_attr(ATTR_RGB_COLOR)

    @property
    def color_temp_kelvin(self) -> int | None:
        return self._avg_int_attr(ATTR_COLOR_TEMP_KELVIN)

    @property
    def supported_color_modes(self) -> set[ColorMode]:
        # Some HA versions reject certain legacy modes (notably "xy").
        allowed: set[ColorMode] = set()
        for name in ("ONOFF", "BRIGHTNESS", "COLOR_TEMP", "HS", "RGB", "RGBW", "RGBWW", "WHITE"):
            mode = getattr(ColorMode, name, None)
            if mode is not None:
                allowed.add(mode)

        modes: set[ColorMode] = set()
        for state in self._member_states():
            raw = state.attributes.get(ATTR_SUPPORTED_COLOR_MODES)
            if isinstance(raw, (list, tuple)):
                for mode in raw:
                    try:
                        parsed = ColorMode(mode)
                        if parsed in allowed:
                            modes.add(parsed)
                    except Exception:  # pragma: no cover
                        continue
        return modes or ({ColorMode.ONOFF} if hasattr(ColorMode, "ONOFF") else set())

    @property
    def color_mode(self) -> ColorMode | None:
        """Expose a best-effort current color mode."""
        for state in self._member_states():
            if state.state != "on":
                continue
            raw = state.attributes.get(ATTR_COLOR_MODE)
            if isinstance(raw, str):
                try:
                    return ColorMode(raw)
                except Exception:  # pragma: no cover
                    continue
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "area_id": self._area_id,
            "area_name": self._area_name,
            "domain": "light",
            "entity_id": list(self._member_entity_ids),
            "normalized_area_name": self._normalized_area_name,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Forward turn_on to member lights."""
        if not self._member_entity_ids:
            return

        await self.hass.services.async_call(
            "light",
            "turn_on",
            {"entity_id": self._member_entity_ids, **kwargs},
            blocking=True,
            context=self._context,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Forward turn_off to member lights."""
        if not self._member_entity_ids:
            return
        await self.hass.services.async_call(
            "light",
            "turn_off",
            {"entity_id": self._member_entity_ids, **kwargs},
            blocking=True,
            context=self._context,
        )
