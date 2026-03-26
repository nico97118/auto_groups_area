"""Sensor platform for Auto Groups by Area.

Creates one sensor per area and per type:
- illuminance: max of member sensors
- humidity: average of member sensors
- temperature: average of member sensors
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Iterable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import StateType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class Aggregation(str):
    MAX = "max"
    MEAN = "mean"


SENSOR_GROUP_DEFS: dict[str, tuple[str, SensorDeviceClass, Aggregation]] = {
    "illuminance": ("Illuminance", SensorDeviceClass.ILLUMINANCE, Aggregation.MAX),
    "humidity": ("Humidity", SensorDeviceClass.HUMIDITY, Aggregation.MEAN),
    "temperature": ("Temperature", SensorDeviceClass.TEMPERATURE, Aggregation.MEAN),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Auto Groups by Area sensor platform."""
    coordinator = AreaSensorGroupCoordinator(hass, config_entry, async_add_entities)
    entry_data = hass.data.setdefault(DOMAIN, {}).setdefault(config_entry.entry_id, {})
    entry_data.setdefault("coordinators", []).append(coordinator)
    await coordinator.async_start()


class AreaSensorGroupCoordinator:
    """Coordinate area sensor group creation and updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        self.hass = hass
        self.config_entry = config_entry
        self.async_add_entities = async_add_entities

        self.groups: dict[str, AreaAggregatedSensor] = {}

        self._unsub_entity_reg: Callable[[], None] | None = None
        self._unsub_area_reg: Callable[[], None] | None = None
        self._unsub_device_reg: Callable[[], None] | None = None

    async def async_start(self) -> None:
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
        name = name.lower()
        name = re.sub(r"[^\w\s-]", "", name)
        name = re.sub(r"[-\s]+", "_", name)
        return name

    async def async_update_all_groups(self) -> None:
        entity_reg = er.async_get(self.hass)
        area_reg = ar.async_get(self.hass)

        for area in area_reg.async_list_areas():
            await self._async_update_groups_for_area(area, entity_reg)

    async def _async_update_groups_for_area(
        self,
        area: ar.AreaEntry,
        entity_reg: er.EntityRegistry,
    ) -> None:
        device_reg = dr.async_get(self.hass)

        def _area_entity_ids(device_class: SensorDeviceClass) -> list[str]:
            entity_ids: list[str] = []
            for entry in entity_reg.entities.values():
                if not entry.entity_id.startswith("sensor."):
                    continue
                if entry.disabled_by is not None:
                    continue

                if entry.area_id == area.id:
                    if self._is_matching_device_class(entry.entity_id, device_class):
                        entity_ids.append(entry.entity_id)
                    continue

                if entry.device_id:
                    device = device_reg.devices.get(entry.device_id)
                    if device is not None and device.area_id == area.id:
                        if self._is_matching_device_class(entry.entity_id, device_class):
                            entity_ids.append(entry.entity_id)
            return entity_ids

        normalized_area_name = self._normalize_name(area.name)

        for group_key, (label, device_class, aggregation) in SENSOR_GROUP_DEFS.items():
            unique_id = f"{DOMAIN}_sensor_{group_key}_{area.id}"
            member_entity_ids = _area_entity_ids(device_class)

            if not member_entity_ids:
                existing = self.groups.pop(unique_id, None)
                if existing is not None:
                    _LOGGER.info(
                        "Removing empty %s group for area '%s'", group_key, area.name
                    )
                    await existing.async_remove()
                continue

            if unique_id in self.groups:
                group = self.groups[unique_id]
                group.update_area(area_name=area.name, normalized_area_name=normalized_area_name)
                group.update_members(member_entity_ids)
                continue

            group = AreaAggregatedSensor(
                unique_id=unique_id,
                area_id=area.id,
                area_name=area.name,
                normalized_area_name=normalized_area_name,
                group_key=group_key,
                label=label,
                device_class=device_class,
                aggregation=aggregation,
                member_entity_ids=member_entity_ids,
            )
            self.groups[unique_id] = group
            self.async_add_entities([group], update_before_add=True)

    def _is_matching_device_class(self, entity_id: str, device_class: SensorDeviceClass) -> bool:
        state = self.hass.states.get(entity_id)
        if state is None:
            return False
        raw = state.attributes.get("device_class")
        if not isinstance(raw, str):
            return False
        try:
            parsed = SensorDeviceClass(raw)
        except Exception:
            return False
        return parsed == device_class

    async def _async_update_areas(self, area_ids: set[str | None]) -> None:
        area_ids.discard(None)
        if not area_ids:
            return

        entity_reg = er.async_get(self.hass)
        area_reg = ar.async_get(self.hass)

        for area_id in area_ids:
            area = area_reg.async_get_area(area_id)
            if area is None:
                continue
            await self._async_update_groups_for_area(area, entity_reg)

    async def _async_remove_area(self, area_id: str) -> None:
        to_remove: list[str] = []
        for unique_id in self.groups:
            if unique_id.endswith(f"_{area_id}"):
                to_remove.append(unique_id)
        for unique_id in to_remove:
            group = self.groups.pop(unique_id)
            await group.async_remove()

    @callback
    def _handle_entity_registry_updated(self, event: Event) -> None:
        entity_id: str | None = event.data.get("entity_id")
        if not entity_id or not entity_id.startswith("sensor."):
            return
        old_area_id: str | None = event.data.get("old_area_id")
        new_area_id: str | None = event.data.get("area_id")
        self.hass.async_create_task(self._async_update_areas({old_area_id, new_area_id}))

    @callback
    def _handle_area_registry_updated(self, event: Event) -> None:
        action: str | None = event.data.get("action")
        area_id: str | None = event.data.get("area_id")

        if action in {"create", "update"} and area_id:
            self.hass.async_create_task(self._async_update_areas({area_id}))
            return

        if action == "remove" and area_id:
            self.hass.async_create_task(self._async_remove_area(area_id))

    @callback
    def _handle_device_registry_updated(self, event: Event) -> None:
        action: str | None = event.data.get("action")
        if action not in {"create", "update", "remove"}:
            return

        old_area_id: str | None = event.data.get("old_area_id")
        new_area_id: str | None = event.data.get("area_id")
        if old_area_id or new_area_id:
            self.hass.async_create_task(self._async_update_areas({old_area_id, new_area_id}))
            return

        self.hass.async_create_task(self.async_update_all_groups())


class AreaAggregatedSensor(SensorEntity):
    """Sensor entity aggregating measurements in an area."""

    _attr_should_poll = False

    def __init__(
        self,
        *,
        unique_id: str,
        area_id: str,
        area_name: str,
        normalized_area_name: str,
        group_key: str,
        label: str,
        device_class: SensorDeviceClass,
        aggregation: Aggregation,
        member_entity_ids: list[str],
    ) -> None:
        self._attr_unique_id = unique_id
        self._area_id = area_id
        self._area_name = area_name
        self._normalized_area_name = normalized_area_name
        self._group_key = group_key
        self._aggregation = aggregation
        self._member_entity_ids = member_entity_ids

        self._attr_name = f"Area {area_name} {label}"
        self._attr_device_class = device_class
        self._attr_state_class = SensorStateClass.MEASUREMENT

        self._unsub_member_state: Callable[[], None] | None = None

    async def async_added_to_hass(self) -> None:
        self._async_subscribe_to_member_state()

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_member_state is not None:
            self._unsub_member_state()
            self._unsub_member_state = None

    def update_area(self, *, area_name: str, normalized_area_name: str) -> None:
        self._area_name = area_name
        self._normalized_area_name = normalized_area_name
        self._attr_name = f"Area {area_name} {SENSOR_GROUP_DEFS[self._group_key][0]}"
        self.async_write_ha_state()

    @callback
    def update_members(self, member_entity_ids: list[str]) -> None:
        if member_entity_ids == self._member_entity_ids:
            return
        self._member_entity_ids = member_entity_ids
        self._async_subscribe_to_member_state()
        self.async_write_ha_state()

    @callback
    def _async_subscribe_to_member_state(self) -> None:
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

    def _member_states(self) -> Iterable[StateType]:
        for entity_id in self._member_entity_ids:
            state = self.hass.states.get(entity_id)
            if state is not None:
                yield state

    def _member_values(self) -> list[float]:
        values: list[float] = []
        for state in self._member_states():
            if state.state in {"unknown", "unavailable"}:
                continue
            try:
                values.append(float(state.state))
            except (TypeError, ValueError):
                continue
        return values

    @property
    def native_unit_of_measurement(self) -> str | None:
        unit: str | None = None
        for state in self._member_states():
            raw = state.attributes.get("unit_of_measurement")
            if not isinstance(raw, str):
                continue
            if unit is None:
                unit = raw
            elif unit != raw:
                return None
        return unit

    @property
    def available(self) -> bool:
        return bool(self._member_values())

    @property
    def native_value(self) -> float | None:
        values = self._member_values()
        if not values:
            return None
        if self._aggregation == Aggregation.MAX:
            return max(values)
        return sum(values) / len(values)

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "area_id": self._area_id,
            "area_name": self._area_name,
            "entity_id": list(self._member_entity_ids),
            "group_key": self._group_key,
            "aggregation": self._aggregation,
        }

