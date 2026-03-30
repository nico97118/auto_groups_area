"""Cover platform for Auto Groups by Area.

Creates one cover entity per area, by forwarding commands to member covers and
exposing aggregated state.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    CoverEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_SUPPORTED_FEATURES
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import StateType

from .const import (
    CONF_CREATE_WHEN_EMPTY,
    CONF_EXCLUDED_AREAS,
    CONF_EXCLUDED_ENTITIES,
    CONF_GROUP_PREFIX,
    CONF_INCLUDE_DEVICE_AREA,
    CONF_INCLUDED_AREAS,
    DEFAULT_OPTIONS,
    DOMAIN,
    merged_options,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Auto Groups by Area cover platform."""
    coordinator = AreaCoverGroupCoordinator(hass, config_entry, async_add_entities)
    entry_data = hass.data.setdefault(DOMAIN, {}).setdefault(config_entry.entry_id, {})
    entry_data.setdefault("coordinators", []).append(coordinator)
    await coordinator.async_start()


class AreaCoverGroupCoordinator:
    """Coordinate area cover-group creation and updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        self.hass = hass
        self.config_entry = config_entry
        self.async_add_entities = async_add_entities

        self.groups: dict[str, AreaCoverGroup] = {}

        self._unsub_entity_reg: Callable[[], None] | None = None
        self._unsub_area_reg: Callable[[], None] | None = None
        self._unsub_device_reg: Callable[[], None] | None = None
        self._options = {**DEFAULT_OPTIONS, **dict(config_entry.options)}

    async def async_start(self) -> None:
        """Start coordinator and do initial sync."""
        self._options = merged_options(self.config_entry.options)
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

    def _parse_area_name_list(self, raw: str) -> set[str]:
        items: list[str] = []
        for part in (raw or "").split(","):
            part = part.strip()
            if part:
                items.append(self._normalize_name(part))
        return set(items)

    def _parse_area_id_list(self, raw: object) -> set[str]:
        if isinstance(raw, list):
            return {str(v) for v in raw if isinstance(v, str) and v}
        if isinstance(raw, str):
            # Backward compatibility (older config stored comma-separated names)
            return set()
        return set()

    def _area_allowed(self, area: ar.AreaEntry) -> bool:
        """Return True if area should be managed based on include/exclude options."""
        included_raw = self._options[CONF_INCLUDED_AREAS]
        excluded_raw = self._options[CONF_EXCLUDED_AREAS]

        included_ids = self._parse_area_id_list(included_raw)
        excluded_ids = self._parse_area_id_list(excluded_raw)

        if included_ids:
            return area.id in included_ids
        if excluded_ids:
            return area.id not in excluded_ids

        # Backward compatibility: comma-separated area *names*
        included_names = (
            self._parse_area_name_list(included_raw)
            if isinstance(included_raw, str)
            else set()
        )
        excluded_names = (
            self._parse_area_name_list(excluded_raw)
            if isinstance(excluded_raw, str)
            else set()
        )
        normalized = self._normalize_name(area.name)
        if included_names:
            return normalized in included_names
        if excluded_names:
            return normalized not in excluded_names
        return True

    async def async_update_all_groups(self) -> None:
        """(Re)build/update all groups for all areas."""
        entity_reg = er.async_get(self.hass)
        area_reg = ar.async_get(self.hass)

        for area in area_reg.async_list_areas():
            if not self._area_allowed(area):
                continue
            await self._async_update_group_for_area(area, entity_reg)

    async def _async_update_group_for_area(
        self,
        area: ar.AreaEntry,
        entity_reg: er.EntityRegistry,
    ) -> None:
        """Update the group entity for one area."""
        device_reg = dr.async_get(self.hass)
        member_entity_ids: list[str] = []
        include_device_area = bool(self._options[CONF_INCLUDE_DEVICE_AREA])
        excluded_entities_raw = self._options.get(CONF_EXCLUDED_ENTITIES, [])
        excluded_entities = (
            set(excluded_entities_raw)
            if isinstance(excluded_entities_raw, list)
            else set()
        )

        for entry in entity_reg.entities.values():
            if not entry.entity_id.startswith("cover."):
                continue
            if entry.entity_id in excluded_entities:
                continue
            if entry.disabled_by is not None:
                continue

            # Entity directly assigned to area
            if entry.area_id == area.id:
                member_entity_ids.append(entry.entity_id)
                continue

            # Entity inherits area from its device assignment
            if include_device_area and entry.device_id:
                device = device_reg.devices.get(entry.device_id)
                if device is not None and device.area_id == area.id:
                    member_entity_ids.append(entry.entity_id)

        unique_id = f"{DOMAIN}_cover_{area.id}"
        # Protect against self-include: if the dynamic group entity itself
        # is assigned to this area, skip it and log a warning.
        filtered: list[str] = []
        for eid in member_entity_ids:
            reg_entry = entity_reg.entities.get(eid)
            if (
                reg_entry is not None
                and getattr(reg_entry, "unique_id", None) == unique_id
            ):
                _LOGGER.warning(
                    "Skipping self-include: dynamic cover group entity '%s' found in members of area '%s'",
                    eid,
                    area.name,
                )
                continue
            filtered.append(eid)
        member_entity_ids = filtered
        normalized_area_name = self._normalize_name(area.name)
        group_prefix = str(self._options[CONF_GROUP_PREFIX] or "")
        create_when_empty = bool(self._options[CONF_CREATE_WHEN_EMPTY])

        if not member_entity_ids and not create_when_empty:
            existing = self.groups.pop(unique_id, None)
            if existing is not None:
                _LOGGER.info("Removing empty cover group for area '%s'", area.name)
                await existing.async_remove()
            return

        if unique_id in self.groups:
            group = self.groups[unique_id]
            group.update_area(
                area_name=area.name, normalized_area_name=normalized_area_name
            )
            group.update_members(member_entity_ids)
            return

        group = AreaCoverGroup(
            unique_id=unique_id,
            area_id=area.id,
            area_name=area.name,
            normalized_area_name=normalized_area_name,
            group_prefix=group_prefix,
            member_entity_ids=member_entity_ids,
        )
        self.groups[unique_id] = group
        self.async_add_entities([group], update_before_add=True)

        _LOGGER.info(
            "Created cover group for area '%s' with %d member(s)",
            area.name,
            len(member_entity_ids),
        )

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
            if not self._area_allowed(area):
                continue
            await self._async_update_group_for_area(area, entity_reg)

    async def _async_remove_area(self, area_id: str) -> None:
        """Remove group entities for an area that was deleted."""
        to_remove: list[str] = []
        for unique_id in self.groups:
            if unique_id.endswith(f"_{area_id}"):
                to_remove.append(unique_id)

        for unique_id in to_remove:
            group = self.groups.pop(unique_id)
            await group.async_remove()

    @callback
    def _handle_entity_registry_updated(self, event: Event) -> None:
        """Handle entity registry updates."""
        entity_id: str | None = event.data.get("entity_id")
        if not entity_id or not entity_id.startswith("cover."):
            return

        old_area_id: str | None = event.data.get("old_area_id")
        new_area_id: str | None = event.data.get("area_id")

        self.hass.async_create_task(
            self._async_update_areas({old_area_id, new_area_id})
        )

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
            self.hass.async_create_task(
                self._async_update_areas({old_area_id, new_area_id})
            )
            return

        # Fallback: if event schema differs, do a full refresh (still cheap for typical setups).
        self.hass.async_create_task(self.async_update_all_groups())


class AreaCoverGroup(CoverEntity):
    """A cover entity representing all covers in an area."""

    _attr_should_poll = False
    _attr_icon = "mdi:blinds"

    def __init__(
        self,
        *,
        unique_id: str,
        area_id: str,
        area_name: str,
        normalized_area_name: str,
        group_prefix: str,
        member_entity_ids: list[str],
    ) -> None:
        self._attr_unique_id = unique_id
        self._area_id = area_id
        self._area_name = area_name
        self._normalized_area_name = normalized_area_name
        self._group_prefix = group_prefix
        self._member_entity_ids: list[str] = member_entity_ids

        self._attr_name = f"Area {area_name}"
        self._attr_suggested_object_id = (
            f"{self._group_prefix}{self._normalized_area_name}"
        )

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
        self._attr_suggested_object_id = (
            f"{self._group_prefix}{self._normalized_area_name}"
        )
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
    def is_closed(self) -> bool | None:
        """Return True if all known members are closed, False if any is open."""
        states = self._member_states()
        if not states:
            return None

        any_known = False
        for state in states:
            if state.state in {"unknown", "unavailable"}:
                continue
            any_known = True
            if state.state != "closed":
                return False

        return True if any_known else None

    @property
    def available(self) -> bool:
        """Return True.

        For cover area groups we prefer exposing an `unknown` state (when all
        members are unknown/unavailable or when the group is empty but created
        via `create_when_empty`) rather than reporting the group as unavailable.
        """
        return True

    @property
    def supported_features(self) -> int:
        """Expose the intersection of supported features across members."""
        features: int | None = None
        for state in self._member_states():
            raw = state.attributes.get(ATTR_SUPPORTED_FEATURES)
            if not isinstance(raw, int):
                continue
            features = raw if features is None else (features & raw)
        return features or 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "area_id": self._area_id,
            "area_name": self._area_name,
            "domain": "cover",
            "entity_id": list(self._member_entity_ids),
            "normalized_area_name": self._normalized_area_name,
        }

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Forward open_cover to member covers."""
        if not self._member_entity_ids:
            return

        await self.hass.services.async_call(
            "cover",
            "open_cover",
            {"entity_id": self._member_entity_ids, **kwargs},
            blocking=True,
            context=self._context,
        )

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Forward close_cover to member covers."""
        if not self._member_entity_ids:
            return
        await self.hass.services.async_call(
            "cover",
            "close_cover",
            {"entity_id": self._member_entity_ids, **kwargs},
            blocking=True,
            context=self._context,
        )

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Forward stop_cover to member covers."""
        if not self._member_entity_ids:
            return
        await self.hass.services.async_call(
            "cover",
            "stop_cover",
            {"entity_id": self._member_entity_ids, **kwargs},
            blocking=True,
            context=self._context,
        )

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Forward set_cover_position to member covers."""
        if not self._member_entity_ids:
            return
        await self.hass.services.async_call(
            "cover",
            "set_cover_position",
            {"entity_id": self._member_entity_ids, **kwargs},
            blocking=True,
            context=self._context,
        )

    @property
    def current_cover_position(self) -> int | None:
        """Expose the average position when all members report a position."""
        positions: list[int] = []
        for state in self._member_states():
            value = state.attributes.get(ATTR_CURRENT_POSITION)
            if not isinstance(value, int):
                return None
            positions.append(value)
        if not positions:
            return None
        return round(sum(positions) / len(positions))
