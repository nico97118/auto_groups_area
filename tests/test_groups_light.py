from __future__ import annotations

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from custom_components.auto_groups_area.const import (
    CONF_CREATE_WHEN_EMPTY,
    CONF_EXCLUDED_ENTITIES,
    CONF_INCLUDE_DEVICE_AREA,
    DOMAIN,
)


@pytest.mark.usefixtures("setup_integration")
async def test_light_group_created_from_entity_area(hass: HomeAssistant) -> None:
    await async_setup_component(hass, "light", {})

    area_reg = ar.async_get(hass)
    area = area_reg.async_create("Salon")

    entity_reg = er.async_get(hass)
    entity_reg.async_get_or_create("light", "demo", "lamp", area_id=area.id)
    hass.states.async_set("light.demo_lamp", "on", {"supported_color_modes": ["onoff"]})

    # Trigger a reload to build groups.
    await hass.services.async_call(DOMAIN, "reload", {}, blocking=True)
    await hass.async_block_till_done()

    state = hass.states.get("light.area_salon")
    assert state is not None
    assert state.attributes["area_id"] == area.id
    assert "light.demo_lamp" in state.attributes["entity_id"]


@pytest.mark.usefixtures("setup_integration")
async def test_light_group_includes_device_area_when_enabled(hass: HomeAssistant) -> None:
    await async_setup_component(hass, "light", {})

    area_reg = ar.async_get(hass)
    area = area_reg.async_create("Bureau")

    device_reg = dr.async_get(hass)
    device = device_reg.async_get_or_create(config_entry_id="test", identifiers={("demo", "dev1")})
    device_reg.async_update_device(device.id, area_id=area.id)

    entity_reg = er.async_get(hass)
    entity_reg.async_get_or_create("light", "demo", "desk", device_id=device.id)
    hass.states.async_set("light.demo_desk", "on", {"supported_color_modes": ["onoff"]})

    await hass.services.async_call(DOMAIN, "reload", {}, blocking=True)
    await hass.async_block_till_done()

    state = hass.states.get("light.area_bureau")
    assert state is not None
    assert "light.demo_desk" in state.attributes["entity_id"]


async def test_light_group_excludes_entities(hass: HomeAssistant, config_entry) -> None:
    await async_setup_component(hass, "light", {})

    config_entry.options = {CONF_EXCLUDED_ENTITIES: ["light.demo_skip"]}
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    area_reg = ar.async_get(hass)
    area = area_reg.async_create("Cuisine")

    entity_reg = er.async_get(hass)
    entity_reg.async_get_or_create("light", "demo", "skip", area_id=area.id)
    entity_reg.async_get_or_create("light", "demo", "ok", area_id=area.id)

    hass.states.async_set("light.demo_skip", "on", {"supported_color_modes": ["onoff"]})
    hass.states.async_set("light.demo_ok", "on", {"supported_color_modes": ["onoff"]})

    await hass.services.async_call(DOMAIN, "reload", {}, blocking=True)
    await hass.async_block_till_done()

    state = hass.states.get("light.area_cuisine")
    assert state is not None
    assert "light.demo_ok" in state.attributes["entity_id"]
    assert "light.demo_skip" not in state.attributes["entity_id"]


async def test_light_no_empty_group_by_default(hass: HomeAssistant, config_entry) -> None:
    await async_setup_component(hass, "light", {})

    config_entry.options = {CONF_CREATE_WHEN_EMPTY: False}
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    area_reg = ar.async_get(hass)
    area_reg.async_create("EmptyArea")

    await hass.services.async_call(DOMAIN, "reload", {}, blocking=True)
    await hass.async_block_till_done()

    assert hass.states.get("light.area_emptyarea") is None


async def test_light_include_device_area_toggle(hass: HomeAssistant, config_entry) -> None:
    await async_setup_component(hass, "light", {})

    config_entry.options = {CONF_INCLUDE_DEVICE_AREA: False}
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    area_reg = ar.async_get(hass)
    area = area_reg.async_create("Garage")

    device_reg = dr.async_get(hass)
    device = device_reg.async_get_or_create(config_entry_id="test", identifiers={("demo", "dev2")})
    device_reg.async_update_device(device.id, area_id=area.id)

    entity_reg = er.async_get(hass)
    entity_reg.async_get_or_create("light", "demo", "car", device_id=device.id)
    hass.states.async_set("light.demo_car", "on", {"supported_color_modes": ["onoff"]})

    await hass.services.async_call(DOMAIN, "reload", {}, blocking=True)
    await hass.async_block_till_done()

    # Should NOT create group because entity isn't directly assigned to area and include_device_area is disabled.
    assert hass.states.get("light.area_garage") is None
