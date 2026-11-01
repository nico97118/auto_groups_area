"""Regression coverage for discovery bursts and supported device lookups."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.core import Event
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.auto_groups_area.binary_sensor import (
    AreaBinarySensorGroupCoordinator,
)
from custom_components.auto_groups_area.const import CONF_INCLUDE_DEVICE_AREA, DOMAIN
from custom_components.auto_groups_area.cover import AreaCoverGroupCoordinator
from custom_components.auto_groups_area.light import AreaLightGroupCoordinator
from custom_components.auto_groups_area.sensor import AreaSensorGroupCoordinator
from custom_components.auto_groups_area.switch import AreaSwitchGroupCoordinator

COORDINATORS = [
    AreaLightGroupCoordinator,
    AreaSwitchGroupCoordinator,
    AreaCoverGroupCoordinator,
    AreaSensorGroupCoordinator,
    AreaBinarySensorGroupCoordinator,
]


@pytest.mark.parametrize("coordinator_type", COORDINATORS)
async def test_device_discovery_burst(hass, make_config_entry, coordinator_type):
    """Thousands of MQTT metadata events must schedule no group traversal."""
    coordinator = coordinator_type(hass, make_config_entry(), Mock())
    coordinator.async_update_all_groups = AsyncMock()
    update = AsyncMock()
    coordinator._device_area_updates._update = update
    for _ in range(2000):
        coordinator._handle_device_registry_updated(
            Event(
                dr.EVENT_DEVICE_REGISTRY_UPDATED,
                {
                    "action": "update",
                    "device_id": "mqtt-device",
                    "changes": {"sw_version": "old"},
                },
            )
        )
    await hass.async_block_till_done()
    coordinator.async_update_all_groups.assert_not_called()
    update.assert_not_called()
    assert coordinator._device_area_updates._task is None


@pytest.mark.parametrize("coordinator_type", COORDINATORS)
async def test_device_area_burst_and_unload(hass, make_config_entry, coordinator_type):
    """Batch all old/new areas, including removals, and cancel queued work."""
    coordinator = coordinator_type(hass, make_config_entry(), Mock())
    update = AsyncMock()
    coordinator._device_area_updates._update = update
    # A registry exposing only the supported lookup catches devices.get regressions.
    registry = Mock(spec=["async_get"])
    registry.async_get.return_value = SimpleNamespace(area_id="new")
    with patch(
        "custom_components.auto_groups_area.registry_updates.dr.async_get",
        return_value=registry,
    ):
        for i in range(1000):
            coordinator._handle_device_registry_updated(
                Event(
                    dr.EVENT_DEVICE_REGISTRY_UPDATED,
                    {
                        "action": "update",
                        "device_id": str(i),
                        "changes": {"area_id": "old"},
                    },
                )
            )
        coordinator._handle_device_registry_updated(
            Event(
                dr.EVENT_DEVICE_REGISTRY_UPDATED,
                {
                    "action": "remove",
                    "device_id": "gone",
                    "device": {"area_id": "removed"},
                },
            )
        )
        await hass.async_block_till_done()
        update.assert_awaited_once_with({"old", "new", "removed"})
        update.reset_mock()
        coordinator._handle_device_registry_updated(
            Event(
                dr.EVENT_DEVICE_REGISTRY_UPDATED,
                {"action": "create", "device_id": "created"},
            )
        )
        await coordinator.async_stop()
        await hass.async_block_till_done()
        update.assert_not_called()
        coordinator._options[CONF_INCLUDE_DEVICE_AREA] = False
        coordinator._handle_device_registry_updated(
            Event(
                dr.EVENT_DEVICE_REGISTRY_UPDATED,
                {
                    "action": "update",
                    "device_id": "ignored",
                    "changes": {"area_id": "old"},
                },
            )
        )
        await hass.async_block_till_done()
        update.assert_not_called()


async def test_real_device_move_and_clear(hass, setup_integration):
    """Actual HA events update group membership without a manual reload."""
    areas = ar.async_get(hass)
    old = areas.async_create("Old")
    new = areas.async_create("New")
    devices = dr.async_get(hass)
    device = devices.async_get_or_create(
        config_entry_id=setup_integration.entry_id, identifiers={(DOMAIN, "moving")}
    )
    devices.async_update_device(device.id, area_id=old.id)
    entity = er.async_get(hass).async_get_or_create(
        "light", "demo", "moving", device_id=device.id
    )
    hass.states.async_set(entity.entity_id, "on", {"supported_color_modes": ["onoff"]})
    await hass.services.async_call(DOMAIN, "reload", {}, blocking=True)
    await hass.async_block_till_done()
    assert entity.entity_id in hass.states.get("light.area_old").attributes["entity_id"]

    # No mapping API exists on this view; all five coordinators must use async_get.
    registry = Mock(spec=["async_get"], async_get=devices.async_get)
    with patch(
        "custom_components.auto_groups_area.light.dr.async_get", return_value=registry
    ):
        devices.async_update_device(device.id, area_id=new.id)
        await hass.async_block_till_done()
        assert entity.entity_id not in hass.states.get("light.area_old").attributes.get(
            "entity_id", []
        )
        assert (
            entity.entity_id
            in hass.states.get("light.area_new").attributes["entity_id"]
        )
        devices.async_update_device(device.id, area_id=None)
        await hass.async_block_till_done()
        assert entity.entity_id not in hass.states.get("light.area_new").attributes.get(
            "entity_id", []
        )


@pytest.mark.parametrize("coordinator_type", COORDINATORS)
async def test_large_registry_uses_supported_device_lookup(
    hass, make_config_entry, coordinator_type
):
    """Exercise membership scans with a registry that rejects deprecated mapping access."""
    domain = {
        AreaLightGroupCoordinator: "light",
        AreaSwitchGroupCoordinator: "switch",
        AreaCoverGroupCoordinator: "cover",
        AreaSensorGroupCoordinator: "sensor",
        AreaBinarySensorGroupCoordinator: "binary_sensor",
    }[coordinator_type]
    area_reg = ar.async_get(hass)
    areas = [area_reg.async_create(f"Room {i}") for i in range(10)]
    entities = {
        f"{domain}.member_{i}": SimpleNamespace(
            entity_id=f"{domain}.member_{i}",
            device_id=str(i),
            area_id=None,
            disabled_by=None,
            unique_id=str(i),
            platform="demo",
        )
        for i in range(1000)
    }
    devices = {
        str(i): SimpleNamespace(area_id=areas[i % len(areas)].id) for i in range(1000)
    }
    registry = Mock(spec=["async_get"], async_get=Mock(side_effect=devices.get))
    coordinator = coordinator_type(hass, make_config_entry(), Mock())
    with (
        patch(
            "custom_components.auto_groups_area.registry_updates.dr.async_get",
            return_value=registry,
        ),
        patch(
            "homeassistant.helpers.entity_registry.async_get",
            return_value=SimpleNamespace(entities=entities),
        ),
    ):
        await coordinator.async_update_all_groups()
    assert registry.async_get.call_count >= len(entities) * len(areas)
