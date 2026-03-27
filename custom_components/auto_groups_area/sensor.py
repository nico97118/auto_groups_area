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

from .const import (
    AGGREGATION_LAST,
    AGGREGATION_MAX,
    AGGREGATION_MEAN,
    AGGREGATION_MIN,
    CONF_CREATE_WHEN_EMPTY,
    CONF_EXCLUDED_AREAS,
    CONF_EXCLUDED_ENTITIES,
    CONF_GROUP_PREFIX,
    CONF_HUMIDITY_AGGREGATION,
    CONF_ILLUMINANCE_AGGREGATION,
    CONF_INCLUDE_DEVICE_AREA,
    CONF_INCLUDED_AREAS,
    CONF_TEMPERATURE_AGGREGATION,
    DEFAULT_OPTIONS,
    DOMAIN,
    merged_options,
)
from .logging_helpers import diff_lists, format_list

_LOGGER = logging.getLogger(__name__)


class Aggregation(str):
    MAX = "max"
    MEAN = "mean"
    MIN = "min"
    LAST = "last"


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
        self._options = {**DEFAULT_OPTIONS, **dict(config_entry.options)}

    async def async_start(self) -> None:
        self._options = merged_options(self.config_entry.options)
        included_raw = self._options.get(CONF_INCLUDED_AREAS)
        excluded_raw = self._options.get(CONF_EXCLUDED_AREAS)
        if (
            isinstance(included_raw, list)
            and isinstance(excluded_raw, list)
            and included_raw
            and excluded_raw
        ):
            _LOGGER.warning(
                "Both %s and %s are set; %s takes precedence (entry_id=%s)",
                CONF_INCLUDED_AREAS,
                CONF_EXCLUDED_AREAS,
                CONF_INCLUDED_AREAS,
                self.config_entry.entry_id,
            )
        _LOGGER.debug(
            "Starting sensor coordinator (entry_id=%s, create_when_empty=%s, include_device_area=%s, excluded_entities=%d, agg_temp=%s, agg_humidity=%s, agg_illuminance=%s)",
            self.config_entry.entry_id,
            bool(self._options[CONF_CREATE_WHEN_EMPTY]),
            bool(self._options[CONF_INCLUDE_DEVICE_AREA]),
            len(self._options.get(CONF_EXCLUDED_ENTITIES, []) or []),
            self._options.get(CONF_TEMPERATURE_AGGREGATION),
            self._options.get(CONF_HUMIDITY_AGGREGATION),
            self._options.get(CONF_ILLUMINANCE_AGGREGATION),
        )
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
            return set()
        return set()

    def _area_allowed(self, area: ar.AreaEntry) -> bool:
        included_raw = self._options[CONF_INCLUDED_AREAS]
        excluded_raw = self._options[CONF_EXCLUDED_AREAS]

        included_ids = self._parse_area_id_list(included_raw)
        excluded_ids = self._parse_area_id_list(excluded_raw)
        if included_ids:
            return area.id in included_ids
        if excluded_ids:
            return area.id not in excluded_ids

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

    def _aggregation_for_group(self, group_key: str) -> Aggregation:
        if group_key == "illuminance":
            raw = str(self._options[CONF_ILLUMINANCE_AGGREGATION])
        elif group_key == "humidity":
            raw = str(self._options[CONF_HUMIDITY_AGGREGATION])
        elif group_key == "temperature":
            raw = str(self._options[CONF_TEMPERATURE_AGGREGATION])
        else:
            raw = AGGREGATION_MEAN

        if raw == AGGREGATION_MAX:
            return Aggregation.MAX
        if raw == AGGREGATION_MIN:
            return Aggregation.MIN
        if raw == AGGREGATION_LAST:
            return Aggregation.LAST
        return Aggregation.MEAN

    async def async_update_all_groups(self) -> None:
        entity_reg = er.async_get(self.hass)
        area_reg = ar.async_get(self.hass)

        areas = list(area_reg.async_list_areas())
        created = updated = removed = 0
        allowed = 0
        _LOGGER.debug(
            "Sync sensor groups start (entry_id=%s, areas_total=%d)",
            self.config_entry.entry_id,
            len(areas),
        )

        for area in areas:
            if not self._area_allowed(area):
                continue
            allowed += 1
            try:
                c, u, r = await self._async_update_groups_for_area(area, entity_reg)
            except Exception:
                _LOGGER.exception(
                    "Failed to sync sensor groups for area '%s' (entry_id=%s)",
                    area.name,
                    self.config_entry.entry_id,
                )
                continue
            created += c
            updated += u
            removed += r

        _LOGGER.info(
            "Sync sensor groups done (entry_id=%s, areas_allowed=%d/%d, created=%d, updated=%d, removed=%d)",
            self.config_entry.entry_id,
            allowed,
            len(areas),
            created,
            updated,
            removed,
        )

    async def _async_update_groups_for_area(
        self,
        area: ar.AreaEntry,
        entity_reg: er.EntityRegistry,
    ) -> tuple[int, int, int]:
        device_reg = dr.async_get(self.hass)
        include_device_area = bool(self._options[CONF_INCLUDE_DEVICE_AREA])
        create_when_empty = bool(self._options[CONF_CREATE_WHEN_EMPTY])
        group_prefix = str(self._options[CONF_GROUP_PREFIX] or "")
        excluded_entities_raw = self._options.get(CONF_EXCLUDED_ENTITIES, [])
        excluded_entities = (
            set(excluded_entities_raw)
            if isinstance(excluded_entities_raw, list)
            else set()
        )

        def _area_entity_ids(device_class: SensorDeviceClass) -> list[str]:
            entity_ids: list[str] = []
            for entry in entity_reg.entities.values():
                if not entry.entity_id.startswith("sensor."):
                    continue
                if entry.entity_id in excluded_entities:
                    continue
                if entry.disabled_by is not None:
                    continue

                if entry.area_id == area.id:
                    if self._is_matching_device_class(entry, device_class):
                        entity_ids.append(entry.entity_id)
                    continue

                if entry.device_id:
                    if include_device_area:
                        device = device_reg.devices.get(entry.device_id)
                        if device is not None and device.area_id == area.id:
                            if self._is_matching_device_class(entry, device_class):
                                entity_ids.append(entry.entity_id)
            return entity_ids

        normalized_area_name = self._normalize_name(area.name)
        created = updated = removed = 0

        for group_key, (
            label,
            device_class,
            default_aggregation,
        ) in SENSOR_GROUP_DEFS.items():
            unique_id = f"{DOMAIN}_sensor_{group_key}_{area.id}"
            member_entity_ids = _area_entity_ids(device_class)
            aggregation = self._aggregation_for_group(group_key) or default_aggregation
            _LOGGER.debug(
                "Area '%s' sensor group scan (entry_id=%s, group=%s, aggregation=%s, members=%d)",
                area.name,
                self.config_entry.entry_id,
                group_key,
                aggregation,
                len(member_entity_ids),
            )

            if not member_entity_ids and not create_when_empty:
                existing = self.groups.pop(unique_id, None)
                if existing is not None:
                    _LOGGER.info(
                        "Removing empty %s group for area '%s'", group_key, area.name
                    )
                    await existing.async_remove()
                    removed += 1
                continue

            if unique_id in self.groups:
                group = self.groups[unique_id]
                added, removed_members = diff_lists(
                    group._member_entity_ids, member_entity_ids
                )
                if added or removed_members:
                    _LOGGER.debug(
                        "Updating sensor group (entry_id=%s, unique_id=%s, members=%d -> %d, added=%s, removed=%s)",
                        self.config_entry.entry_id,
                        unique_id,
                        len(group._member_entity_ids),
                        len(member_entity_ids),
                        format_list(added),
                        format_list(removed_members),
                    )
                group.update_area(
                    area_name=area.name, normalized_area_name=normalized_area_name
                )
                group.update_members(member_entity_ids)
                updated += 1
                continue

            group = AreaAggregatedSensor(
                unique_id=unique_id,
                area_id=area.id,
                area_name=area.name,
                normalized_area_name=normalized_area_name,
                group_prefix=group_prefix,
                group_key=group_key,
                label=label,
                device_class=device_class,
                aggregation=aggregation,
                member_entity_ids=member_entity_ids,
            )
            self.groups[unique_id] = group
            self.async_add_entities([group], update_before_add=True)
            created += 1
            _LOGGER.debug(
                "Created sensor group (entry_id=%s, unique_id=%s, members=%s)",
                self.config_entry.entry_id,
                unique_id,
                format_list(member_entity_ids),
            )

        return created, updated, removed

    def _is_matching_device_class(
        self, entry: er.RegistryEntry, device_class: SensorDeviceClass
    ) -> bool:
        """Return True if registry entry belongs to the requested device class.

        Prefer the entity registry's stored device class to avoid startup timing issues
        where the entity state is not yet available.
        """
        raw = getattr(entry, "original_device_class", None) or getattr(
            entry, "device_class", None
        )
        if not isinstance(raw, str):
            state = self.hass.states.get(entry.entity_id)
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
                _LOGGER.debug(
                    "Area id '%s' not found during sensor update (entry_id=%s)",
                    area_id,
                    self.config_entry.entry_id,
                )
                continue
            if not self._area_allowed(area):
                continue
            try:
                await self._async_update_groups_for_area(area, entity_reg)
            except Exception:
                _LOGGER.exception(
                    "Failed to update sensor groups for area '%s' (entry_id=%s)",
                    area.name,
                    self.config_entry.entry_id,
                )

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
        _LOGGER.debug(
            "Entity registry updated for sensor (entry_id=%s, entity_id=%s, old_area_id=%s, new_area_id=%s)",
            self.config_entry.entry_id,
            entity_id,
            old_area_id,
            new_area_id,
        )
        self.hass.async_create_task(
            self._async_update_areas({old_area_id, new_area_id})
        )

    @callback
    def _handle_area_registry_updated(self, event: Event) -> None:
        action: str | None = event.data.get("action")
        area_id: str | None = event.data.get("area_id")

        _LOGGER.debug(
            "Area registry updated (entry_id=%s, action=%s, area_id=%s)",
            self.config_entry.entry_id,
            action,
            area_id,
        )
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
        _LOGGER.debug(
            "Device registry updated (entry_id=%s, action=%s, old_area_id=%s, new_area_id=%s)",
            self.config_entry.entry_id,
            action,
            old_area_id,
            new_area_id,
        )
        if old_area_id or new_area_id:
            self.hass.async_create_task(
                self._async_update_areas({old_area_id, new_area_id})
            )
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
        group_prefix: str,
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
        self._group_prefix = group_prefix
        self._group_key = group_key
        self._aggregation = aggregation
        self._member_entity_ids = member_entity_ids

        self._attr_name = f"Area {area_name} {label}"
        self._attr_suggested_object_id = (
            f"{self._group_prefix}{self._normalized_area_name}_{self._group_key}"
        )
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
        self._attr_suggested_object_id = (
            f"{self._group_prefix}{self._normalized_area_name}_{self._group_key}"
        )
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
        if self._aggregation == Aggregation.LAST:
            latest_value: float | None = None
            latest_changed: float | None = None
            for state in self._member_states():
                if state.state in {"unknown", "unavailable"}:
                    continue
                try:
                    value = float(state.state)
                except (TypeError, ValueError):
                    continue
                changed = getattr(state, "last_changed", None)
                ts = changed.timestamp() if changed is not None else None
                if ts is None or latest_changed is None or ts > latest_changed:
                    latest_changed = ts
                    latest_value = value
            return latest_value

        values = self._member_values()
        if not values:
            return None
        if self._aggregation == Aggregation.MAX:
            return max(values)
        if self._aggregation == Aggregation.MIN:
            return min(values)
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
